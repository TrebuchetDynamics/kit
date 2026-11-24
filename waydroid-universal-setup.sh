#!/usr/bin/env bash
# Standalone native Waydroid provisioning. See docs/waydroid.md.
set -Eeuo pipefail
export LC_ALL=C
STATE=/var/lib/waydroid
DROPIN=/etc/systemd/system/waydroid-container.service.d/kit-headless.conf
UNIT=kit-waydroid.service
SELF=$(readlink -f -- "${BASH_SOURCE[0]}")
PAYLOAD="$HOME/.local/share/kit-waydroid/waydroid-universal-setup.sh"
USER_UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
WAIT=180
ACTION=setup
TRANSFER_STAGE=''
TRANSFER_STATE=''
fail() {
    printf 'waydroid-setup: %s\n' "$*" >&2
    if [[ -n $TRANSFER_STAGE ]]; then
        printf 'waydroid-setup: transfer stage=%s; %s. No GUI rollback attempted. Inspect waydroid status, systemctl --user status kit-waydroid.service, journalctl --user -u kit-waydroid.service and journalctl -u waydroid-container.service; repair the reported cause, then retry setup (or --status if headless is running).\n' "$TRANSFER_STAGE" "$TRANSFER_STATE" >&2
    fi
    exit 1
}
usage() {
    cat <<'EOF'
Usage: waydroid-universal-setup.sh [--check | --status | --stop] [--wait SECONDS]
  (no action)  Check prerequisites, ask for sudo, transfer same-user GUI to managed
               headless (interrupts open GUI apps), provision and verify Android.
  --check      Read-only checks and planned same-user transfer; no sudo or writes.
  --status     Connect/query ADB as this user; wait for authorized Android boot.
  --stop       Disable this user's headless service; preserve Android data/keys.
  --wait       Per-stage session/device wait (default 180 seconds, max 3600).
  --help       Show this help. Operator/removal guide: docs/waydroid.md
EOF
}
while (($#)); do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --check) ACTION=check ;;
        --status) ACTION=status ;;
        --stop) ACTION=stop ;;
        --session) ACTION=session ;; # User service only; never a sudo target.
        --wait) shift; (($#)) || fail '--wait needs seconds'; WAIT=$1 ;;
        *) fail "Unknown option: $1 (use --help)" ;;
    esac
    shift
done
if ! [[ $WAIT =~ ^[0-9]{1,4}$ ]] || ((10#$WAIT == 0 || 10#$WAIT > 3600)); then
    fail '--wait must be 1..3600 seconds'
fi
WAIT=$((10#$WAIT))

# Waydroid status reports DHCP leases; UNKNOWN is transient, not a serial.
device_ip() {
    local status ip
    status=$(timeout 10 waydroid status) || return 1
    ip=$(awk -F': *|:\t' '/^IP address:/ {gsub(/[[:space:]]/, "", $2); print $2}' <<< "$status")
    python3 - "$ip" <<'PY'
import ipaddress, sys
try:
    ip = ipaddress.IPv4Address(sys.argv[1])
    if ip.is_unspecified or ip.is_loopback or ip.is_multicast: raise ValueError()
    print(ip)
except ValueError:
    sys.exit(1)
PY
}
verify_device() {
    local end=$((SECONDS + WAIT)) ip='' serial='' state='' reason=ip version abi
    while ((SECONDS < end)); do
        if ip=$(device_ip); then
            serial="$ip:5555"
            timeout 10 adb connect "$serial" >/dev/null 2>&1 || true
            state=$(timeout 10 adb devices | awk -v s="$serial" '$1 == s {print $2}') || state=''
            case "$state" in
                unauthorized) reason=authorization ;;
                device)
                    reason=boot
                    if [[ $(timeout 10 adb -s "$serial" shell getprop sys.boot_completed | tr -d '\r') == 1 ]]; then
                        version=$(timeout 10 adb -s "$serial" shell getprop ro.build.version.release | tr -d '\r') &&
                        abi=$(timeout 10 adb -s "$serial" shell getprop ro.product.cpu.abi | tr -d '\r') ||
                            fail 'Android properties unavailable; check adb devices and adb shell getprop, then retry --status.'
                        [[ -n $version && -n $abi ]] || fail 'Android properties empty; inspect adb shell getprop and retry --status.'
                        printf 'ADB serial: %s\nAndroid: %s\nABI: %s\n' "$serial" "$version" "$abi"
                        return
                    fi ;;
                *) reason=connection ;;
            esac
        else
            reason=ip
        fi
        sleep 1
    done
    case "$reason" in
        ip) fail 'No container IP after wait. Inspect waydroid status and journalctl -u waydroid-container; repair DHCP/waydroid0 networking, then retry --status.' ;;
        authorization) fail "ADB authorization pending. Open Android UI and approve this user's ADB fingerprint (see docs/waydroid.md), then retry --status. Do not replace keys." ;;
        connection) fail "ADB not connected ($serial, state=${state:-absent}). Check container TCP 5555 and host firewall; retry --status. Do not expose ADB externally." ;;
        boot) fail 'Android boot timeout. Inspect journalctl --user -u kit-waydroid and journalctl -u waydroid-container; repair boot/rendering and retry --status --wait 300.' ;;
    esac
}

# A single user service owns both child processes, reconnecting ADB after DHCP/reboot.
# systemd kills the entire cgroup on failure; no passwordless recovery grant exists.
run_session() {
    export WAYLAND_DISPLAY=wayland-kit
    local weston_pid session_pid end ip
    weston --backend=headless-backend.so --use-pixman --socket="$WAYLAND_DISPLAY" --idle-time=0 --no-config &
    weston_pid=$!
    trap 'kill "$weston_pid" "${session_pid:-$weston_pid}" 2>/dev/null || true' EXIT
    end=$((SECONDS + 30))
    until [[ -S ${XDG_RUNTIME_DIR:?}/$WAYLAND_DISPLAY ]]; do
        kill -0 "$weston_pid" 2>/dev/null || fail 'Headless Weston exited; inspect user service journal.'
        ((SECONDS < end)) || fail 'Headless Weston socket timeout; inspect user service journal.'
        sleep 1
    done
    waydroid session start &
    session_pid=$!
    while kill -0 "$weston_pid" 2>/dev/null && kill -0 "$session_pid" 2>/dev/null; do
        if ip=$(device_ip); then
            timeout 10 adb connect "$ip:5555" >/dev/null 2>&1 || true
        fi
        sleep 5
    done
    fail 'Waydroid session or Weston exited; systemd will retry. Inspect user service journal.'
}

# Config, image headers and generated LXC state, not `waydroid init` exit status.
# Do not reinitialize a damaged existing device: upstream init can remove overlays.
image_state() {
    python3 - "$STATE" "${XDG_DATA_HOME:-$HOME/.local/share}/waydroid/data" <<'PY'
import configparser, os, pathlib, sys
p = pathlib.Path(sys.argv[1])
user_data = pathlib.Path(sys.argv[2])
cfg = configparser.ConfigParser()
try:
    if (p / 'waydroid.cfg').exists():
        with (p / 'waydroid.cfg').open() as f: cfg.read_file(f)
    images = pathlib.Path(cfg.get('waydroid', 'images_path', fallback=str(p / 'images')))
    valid = True
    for name in ('system', 'vendor'):
        try:
            with (images / (name + '.img')).open('rb') as f:
                f.seek(1024); header = f.read(58)
            # ext4 or EROFS; complete boot verification still follows.
            ok = len(header) == 58 and (header[56:58] == b'\x53\xef' or header[:4] == b'\xe2\xe1\xf5\xe0')
            ok = ok and (cfg.getint('waydroid', name + '_datetime', fallback=0) > 0 or cfg.get('waydroid', name + '_ota', fallback='') == 'None')
        except FileNotFoundError:
            ok = False
        valid = valid and ok
    complete = valid and (p / 'rootfs').is_dir() and (p / 'lxc/waydroid/config').is_file() and (p / 'waydroid_base.prop').is_file()
    def overlay_has_data(path):
        # rglob silently skips permission-denied subtrees: those are NOT empty.
        # Never follow symlinks, and fail closed if we cannot inspect a directory.
        try:
            entries = os.scandir(path)
        except FileNotFoundError:
            return False
        with entries:
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False) or overlay_has_data(entry.path):
                    return True
        return False
    # Empty scaffolding can remain when init stops before LXC config generation.
    if complete: print('complete')
    elif (p / 'data').exists() or user_data.exists() or overlay_has_data(p / 'overlay_rw'): print('damaged')
    else: print('incomplete')
except (OSError, configparser.Error, ValueError) as e:
    print('Cannot inspect Waydroid initialization: ' + str(e), file=sys.stderr)
    sys.exit(1)
PY
}

# Upstream status swallows D-Bus failures as STOPPED. GetSession must succeed
# and return an empty a{ss} to prove release; never auto-activate a lost manager.
manager_session() {
    local reply
    reply=$(timeout 10 busctl --system --auto-start=no --timeout=10 --json=short call \
        id.waydro.Container /ContainerManager id.waydro.ContainerManager GetSession) || return 1
    python3 - "$reply" <<'PYBUS'
import json, sys
try:
    reply = json.loads(sys.argv[1])
    if reply['type'] != 'a{ss}' or not isinstance(reply['data'], list) or len(reply['data']) != 1:
        raise ValueError('Invalid GetSession signature')
    session = reply['data'][0]
    if not isinstance(session, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in session.items()):
        raise ValueError('Invalid GetSession dictionary')
    if session:
        uid, display, pid = (session[k] for k in ('user_id', 'wayland_display', 'pid'))
        if not uid.isdecimal() or not pid.isdecimal() or int(pid) <= 0:
            raise ValueError('Invalid session UID/PID')
        if not display or display == 'None' or any(c in display for c in '|\n\r\t'):
            raise ValueError('Invalid session display')
        print('|'.join((uid, display, pid)))
except (ValueError, KeyError, TypeError):
    sys.exit(1)
PYBUS
}

# Read-only classification; SESSION_ID binds the owner/display/process snapshot.
# An active unit elsewhere or an unowned wayland-kit socket is not ours to replace.
classify_session() {
    SESSION_KIND=stopped
    SESSION_ID=''
    local fragment active=false unit_state status owner display session_state
    fragment=$(timeout 10 systemctl --user show "$UNIT" --property=FragmentPath --value) || fail 'Cannot inspect user unit ownership; repair user systemd before setup.'
    if [[ -n $fragment && $fragment != "$USER_UNITS/$UNIT" ]]; then
        fail "Foreign loaded $UNIT ($fragment); resolve the unit conflict before setup."
    fi
    if [[ -n $fragment || -e $USER_UNITS/$UNIT ]]; then
        [[ -f $USER_UNITS/$UNIT ]] && grep -qx '# Managed by waydroid-universal-setup.sh' "$USER_UNITS/$UNIT" || fail "Foreign $USER_UNITS/$UNIT; preserve it and resolve the name conflict."
    fi
    unit_state=$(timeout 10 systemctl --user show "$UNIT" --property=ActiveState --value) || fail 'Cannot inspect user service state; repair user systemd before setup.'
    case "$unit_state" in
        active|reloading) active=true ;;
        inactive|failed) ;;
        *) fail "Ambiguous user service state ($unit_state); inspect $UNIT before setup." ;;
    esac
    if command -v waydroid >/dev/null; then
        status=$(timeout 10 waydroid status) || fail 'Cannot inspect current Waydroid session; repair it before setup.'
        session_state=$(sed -n 's/^Session:[[:space:]]*//p' <<< "$status")
        owner=$(sed -n 's/^Session user:.*(\([0-9]*\)).*/\1/p' <<< "$status")
        display=$(sed -n 's/^Wayland display:[[:space:]]*//p' <<< "$status")
        case "$session_state" in
            RUNNING)
                [[ $owner == "$(id -u)" && -n $display && $display != None ]] || fail "Foreign or ambiguous Waydroid session (uid=${owner:-missing}); coordinate with its operator before setup."
                SESSION_ID=$(manager_session) || fail 'Cannot verify Waydroid manager GetSession; inspect the container journal and retry setup.'
                [[ $SESSION_ID == "$owner|$display|"* ]] || fail 'Waydroid status and manager identity disagree; inspect the session and retry setup.'
                if [[ $display == wayland-kit ]]; then
                    [[ $active == true && $fragment == "$USER_UNITS/$UNIT" ]] || fail 'Conflicting wayland-kit display without an owned active user service; resolve it before setup.'
                    SESSION_KIND=managed
                else
                    [[ $active == false ]] || fail 'User service is active alongside a graphical session; inspect and resolve the conflict before setup.'
                    SESSION_KIND=graphical
                fi ;;
            STOPPED)
                [[ -z $owner && -z $display && $active == false ]] || fail 'Ambiguous stopped session or active user service; inspect ownership before setup.' ;;
            *) fail 'Unknown Waydroid session state; inspect waydroid status before setup.' ;;
        esac
    fi
    if [[ $SESSION_KIND != managed ]]; then
        local socket="${XDG_RUNTIME_DIR}/wayland-kit" path
        for path in "$socket" "$socket.lock"; do
            [[ ! -e $path && ! -L $path ]] || fail "Conflicting headless display artifact $path; inspect its owner and resolve before setup."
        done
    fi
}

transfer_session() {
    local expected_kind=$1 expected_id=$2 end observed
    # Prerequisites and sudo/package admission have finished. Rebind immediately
    # before mutation, still under setup.lock; no action on the earlier snapshot.
    classify_session
    [[ $SESSION_KIND == "$expected_kind" && $SESSION_ID == "$expected_id" ]] || fail 'Session identity changed during setup; inspect ownership and retry setup. No session stopped.'
    [[ $SESSION_KIND == graphical ]] || return 0
    TRANSFER_STAGE=stop
    TRANSFER_STATE='GUI stop attempted; headless not started'
    trap 'fail "Setup command failed (exit $?)."' ERR
    printf 'Transferring this user to managed headless: open GUI apps will be interrupted.\n'
    timeout 30 waydroid session stop || fail 'Graphical transfer stop failed or timed out; release is unconfirmed.'
    TRANSFER_STAGE=release
    end=$((SECONDS + WAIT))
    while :; do
        observed=$(manager_session) || fail 'Graphical transfer release readback failed; manager unavailable, not evidence of STOPPED.'
        if [[ -z $observed ]]; then break; fi
        [[ $observed == "$expected_id" ]] || fail 'Graphical transfer owner changed during release; refusing competing headless startup.'
        ((SECONDS < end)) || fail 'Graphical transfer release timeout; manager still reports a session.'
        sleep 1
    done
    TRANSFER_STATE='GUI stopped and release confirmed; headless not started'
    TRANSFER_STAGE=provision
    printf 'Graphical transfer: manager confirmed no session.\n'
}

confirm_managed() {
    local end=$((SECONDS + WAIT)) observed
    while :; do
        observed=$(manager_session) || fail 'Managed startup GetSession failed; inspect the container manager.'
        if [[ -n $observed ]]; then
            [[ $observed == "$(id -u)|wayland-kit|"* ]] || fail 'Managed startup has a foreign or unexpected session UID/display.'
            classify_session
            [[ $SESSION_KIND == managed ]] || fail 'Managed startup unit ownership not confirmed.'
            return
        fi
        ((SECONDS < end)) || fail 'Managed headless startup timeout; user service has not registered its session.'
        sleep 1
    done
}

PACKAGES=()
MANAGER=''
preflight() {
    PACKAGES=()
    MANAGER=''
    [[ $(uname -s) == Linux ]] || fail 'Native Waydroid requires Linux; no VM/emulator fallback.'
    [[ $(id -u) != 0 ]] || fail 'Run as the testing user, not root; setup requests sudo when needed.'
    local tool
    for tool in timeout python3 systemctl loginctl sudo flock busctl; do
        command -v "$tool" >/dev/null || fail "Missing prerequisite: $tool. Install it before setup."
    done
    [[ -d /run/systemd/system ]] || fail 'Missing systemd system manager. Boot with systemd before setup.'
    timeout 10 systemctl show --property=Version --value >/dev/null || fail 'System manager unavailable; repair systemd first.'
    timeout 10 systemctl --user show-environment >/dev/null || fail 'Missing user systemd/D-Bus session. Log in through PAM and retry as the testing user.'
    [[ -d ${XDG_RUNTIME_DIR:-/nonexistent} ]] || fail 'Missing XDG_RUNTIME_DIR. Log in through PAM before setup.'
    # Probe available driver, not distro identity; do not modprobe during preflight.
    if ! timeout 10 modinfo binder_linux >/dev/null 2>&1 && [[ ! -d /sys/module/binder_linux && ! -c /dev/binder && ! -c /dev/binderfs/binder-control ]]; then
        fail 'Missing Android Binder kernel support. Install/boot a kernel with CONFIG_ANDROID_BINDER_IPC (binder_linux), then retry; no fallback.'
    fi
    python3 - <<'PY' || fail 'Missing memfd/ashmem support. Boot a Waydroid-capable kernel before setup.'
import os
if not os.path.exists('/dev/ashmem'):
    fd = os.memfd_create('waydroid-preflight'); os.close(fd)
PY
    [[ -d /sys/fs/cgroup && -e /proc/self/ns/net && -e /proc/self/ns/mnt ]] || fail 'Missing cgroups or kernel namespaces; enable native container support before setup.'
    local arch
    arch=$(uname -m)
    [[ $arch == x86_64 || $arch == aarch64 ]] || fail "No configured official native image architecture for $arch; use a Waydroid-supported native architecture."
    if [[ -f $DROPIN ]] && ! grep -qx "# kit-waydroid user=$(id -u)" "$DROPIN"; then
        fail "Container already has a foreign $DROPIN; keep its ownership and resolve with the operator."
    fi
    INIT_STATE=$(image_state) || fail 'Cannot safely read existing initialization; repair config permissions/contents before setup.'
    [[ $INIT_STATE != damaged ]] || fail 'Existing Android state has incomplete images/config. Preserve data and restore known-good images/config from backup; do not force-init.'
    classify_session
    local missing=()
    for tool in waydroid weston adb; do
        command -v "$tool" >/dev/null || missing+=("$tool")
    done
    if ((${#missing[@]})); then
        if command -v apt-get >/dev/null && command -v apt-cache >/dev/null; then
            MANAGER=apt-get
            PACKAGES=("${missing[@]}")
            for tool in "${PACKAGES[@]}"; do
                timeout 30 apt-cache show "$tool" >/dev/null 2>&1 || fail "Missing package $tool in configured APT repositories. Follow official Waydroid distro installation instructions, then retry."
            done
        elif command -v dnf >/dev/null; then
            MANAGER=dnf
            for tool in "${missing[@]}"; do
                [[ $tool != adb ]] || tool=android-tools
                PACKAGES+=("$tool")
                # cache-only: admission must not refresh/download repository metadata.
                timeout 30 dnf --cacheonly list --available "$tool" >/dev/null 2>&1 || fail "Missing cached DNF package $tool. Configure official distro repositories and refresh metadata, then retry."
            done
        else
            fail "Missing dependencies: ${missing[*]}. Install native Waydroid, Weston and ADB using your distribution's packages, then retry (automatic install supports APT/DNF)."
        fi
    fi
    if command -v weston >/dev/null; then
        local help
        help=$(timeout 10 weston --help)
        [[ $help == *headless* && $help == *--use-pixman* ]] || fail 'Weston lacks headless/pixman backend options. Install a Weston build with headless support.'
    fi
    printf 'Prerequisites available (%s); initialization: %s; missing packages: %s\n' "$arch" "$INIT_STATE" "${PACKAGES[*]:-none}"
}

root() { timeout 1800 sudo -- "$@"; }
setup() {
    preflight
    local expected_kind=$SESSION_KIND expected_id=$SESSION_ID
    # All read-only admission checks precede files, package installs and sudo.
    mkdir -p "$HOME/.local/share/kit-waydroid"
    exec 9>"$HOME/.local/share/kit-waydroid/setup.lock"
    flock -n 9 || fail 'Another setup is running for this user; wait for it to finish.'
    # Admission is only a snapshot. A peer may finish between it and this lock;
    # never force that newly initialized device through init using stale state.
    preflight
    timeout 300 sudo -v || fail 'Operator sudo authorization required; no host setup performed.'
    # Refresh only the operator-approved timestamp during long image downloads.
    (trap 'kill "${sleeper:-}" 2>/dev/null || true; exit' TERM
     while :; do sleep 60 & sleeper=$!; wait "$sleeper"; timeout 10 sudo -n -v || exit; done
    ) </dev/null >/dev/null 2>&1 9>&- &
    keepalive=$!
    stage=''
    trap 'kill "$keepalive" 2>/dev/null || true; wait "$keepalive" 2>/dev/null || true; rm -rf -- "$stage"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    stage=$(mktemp -d)
    if ((${#PACKAGES[@]})); then
        root "$MANAGER" install -y "${PACKAGES[@]}"
    fi
    local tool
    for tool in waydroid weston adb; do
        command -v "$tool" >/dev/null || fail "Package install did not provide $tool; inspect package logs."
    done
    local help
    help=$(timeout 10 weston --help)
    [[ $help == *headless* && $help == *--use-pixman* ]] || fail 'Installed Weston lacks headless/pixman support; no device services configured.'
    [[ $(timeout 10 systemctl show waydroid-container.service --property=LoadState --value) == loaded ]] || fail 'Missing waydroid-container.service; install the distro systemd integration.'
    transfer_session "$expected_kind" "$expected_id"
    if [[ $INIT_STATE != complete ]]; then
        # Configure fresh software rendering BEFORE init generates base properties.
        # No existing data/overlays are admitted to this recovery path.
        root install -d -m 755 "$STATE"
        root python3 - "$STATE/waydroid.cfg" <<'PY'
import configparser, os, pathlib, sys, tempfile
p = pathlib.Path(sys.argv[1]); c = configparser.ConfigParser()
if p.exists():
    with p.open() as f: c.read_file(f)
if not c.has_section('properties'): c.add_section('properties')
for k, v in [('ro.hardware.gralloc', 'default'), ('ro.hardware.egl', 'swiftshader')]:
    if not c.has_option('properties', k): c.set('properties', k, v)
# An interrupted extraction may have a saved timestamp but no usable image.
# Reset only that image's timestamp, retaining its valid peer and all ADB keys.
images = pathlib.Path(c.get('waydroid', 'images_path', fallback=str(p.parent / 'images')))
if c.has_section('waydroid'):
    for name in ('system', 'vendor'):
        try:
            with (images / (name + '.img')).open('rb') as f:
                f.seek(1024); h = f.read(58)
            valid = len(h) == 58 and (h[56:58] == b'\x53\xef' or h[:4] == b'\xe2\xe1\xf5\xe0')
        except FileNotFoundError:
            valid = False
        if not valid: c.set('waydroid', name + '_datetime', '0')
fd, path = tempfile.mkstemp(dir=p.parent)
with os.fdopen(fd, 'w') as f: c.write(f)
os.chmod(path, p.stat().st_mode & 0o777 if p.exists() else 0o644)
os.replace(path, p)
PY
        # Upstream checks download hashes and retains valid image timestamps.
        # Never force, delete data/overlays, or reset keys.
        root waydroid init -c https://ota.waydro.id/system -v https://ota.waydro.id/vendor
        [[ $(image_state) == complete ]] || fail 'Waydroid initialization incomplete despite init returning. Inspect waydroid log and retry setup; keep downloaded images/data.'
    fi
    cat > "$stage/container.conf" <<EOF
# kit-waydroid user=$(id -u)
[Service]
Restart=on-failure
RestartSec=5
EOF
    root install -d -m 755 "${DROPIN%/*}"
    root install -m 644 "$stage/container.conf" "$DROPIN"
    root systemctl daemon-reload
    root systemctl enable --now waydroid-container.service
    root loginctl enable-linger "$(id -un)"
    mkdir -p "$USER_UNITS"
    [[ $SELF == "$PAYLOAD" ]] || install -m 755 "$SELF" "$PAYLOAD"
    cat > "$stage/user.service" <<'EOF'
# Managed by waydroid-universal-setup.sh
[Unit]
Description=Kit headless Waydroid and unprivileged ADB reconnect
After=dbus.socket
StartLimitIntervalSec=0
[Service]
ExecStart="%h/.local/share/kit-waydroid/waydroid-universal-setup.sh" --session
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
[Install]
WantedBy=default.target
EOF
    # The user's Android data location must survive a login-less reboot too.
    python3 - "$stage/user.service" "${XDG_DATA_HOME:-$HOME/.local/share}" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
v = sys.argv[2].replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('\n', '\\n').replace('\r', '\\r')
s = p.read_text().replace('[Service]\n', '[Service]\nEnvironment="XDG_DATA_HOME=' + v + '"\n')
p.write_text(s)
PY
    install -m 644 "$stage/user.service" "$USER_UNITS/$UNIT"
    timeout 15 systemctl --user daemon-reload
    # Last competing-owner/socket check before activating the managed service.
    [[ -z $TRANSFER_STAGE ]] || TRANSFER_STAGE=start
    classify_session
    local observed
    observed=$(manager_session) || fail 'Cannot verify manager before managed startup; inspect container journal and retry setup.'
    if [[ $SESSION_KIND == managed ]]; then
        [[ $observed == "$SESSION_ID" ]] || fail 'Managed session identity changed before start; inspect ownership and retry setup.'
    else
        [[ -z $observed && $SESSION_KIND == stopped ]] || fail 'Competing session appeared before managed start; inspect ownership and retry setup.'
    fi
    [[ -z $TRANSFER_STAGE ]] || TRANSFER_STATE='GUI stopped; managed headless startup requested'
    timeout 30 systemctl --user enable --now "$UNIT" || fail 'Managed headless service activation failed; inspect user service journal and retry setup.'
    confirm_managed
    [[ -z $TRANSFER_STAGE ]] || { TRANSFER_STAGE=adb; TRANSFER_STATE='GUI stopped; managed headless session confirmed'; }
    verify_device
}

case "$ACTION" in
    check)
        preflight
        if [[ $SESSION_KIND == graphical ]]; then
            printf 'Planned same-user graphical transfer: open GUI apps will be interrupted; stop, confirm release, start managed headless, verify Android.\n'
        fi ;;

    status) verify_device ;;
    stop) timeout 30 systemctl --user disable --now "$UNIT"; printf 'Headless session disabled; Android data, images and ADB keys preserved. See docs/waydroid.md for host opt-out.\n' ;;
    session) run_session ;;
    setup) setup ;;
esac
