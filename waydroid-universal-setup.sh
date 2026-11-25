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
    printf 'waydroid-setup: %s\n' "$1" >&2
    if [[ -n $TRANSFER_STAGE ]]; then
        printf 'waydroid-setup: transfer stage=%s; %s. No GUI rollback attempted. Inspect waydroid status, systemctl --user status kit-waydroid.service, journalctl --user -u kit-waydroid.service and journalctl -u waydroid-container.service; repair the reported cause, then retry setup (or --status if headless is running).\n' "$TRANSFER_STAGE" "$TRANSFER_STATE" >&2
    fi
    exit "${2:-1}"
}
usage() {
    cat <<'EOF'
Usage: waydroid-universal-setup.sh [--check | --status | --stop] [--wait SECONDS]
  (no action)  Check prerequisites, ask for sudo if needed, transfer same-user GUI
               to managed headless (interrupts open GUI apps), and verify Android.
  --check      Read-only checks and planned same-user transfer; no sudo or writes.
               Missing DNF dependencies return nonzero; cache evidence only.
  --status     Connect/query ADB as this user; wait for authorized Android boot.
  --stop       Disable this user's headless service; preserve Android data/keys.
  --wait       Per-stage session/device wait (default 180 seconds, max 3600).
  --help       Show this help. Operator/removal guide: docs/waydroid.md
No graphical login is required; Weston uses a private headless Wayland socket.
Setup/status exit: 0 verified ready, 2 authorization pending; other failures nonzero.
Pending means Android does not trust the current user's ADB key. Keep headless
running and keys unchanged; retry --status only after valid Android authorization
for that same key exists. Kit cannot provide unattended first-time authorization.
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
    local session status ip
    # Do not let status auto-activate an absent manager (--status is read-only
    # apart from the documented unprivileged ADB connection).
    session=$(manager_session) || return 1
    [[ -n $session ]] || return 1
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
                        # ADB can take minutes; do not publish readiness for a
                        # different owner/session that appeared during that wait.
                        if [[ $ACTION == setup ]]; then confirm_managed; fi
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
        authorization) fail "ADB authorization pending. Android does not trust the current user's ADB key. Headless service and existing keys are preserved. Retry --status only after valid Android authorization for this same key exists; Kit cannot provide unattended first-time authorization. See docs/waydroid.md. Do not replace keys." 2 ;;
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
    local fragment active=false unit_state manager_owner owner display pid
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
    # `waydroid status` uses an auto-activating D-Bus proxy, even in --check.
    # Probe ownership without activation, then read the manager directly. Upstream
    # cannot have an initialized session without both its config and rootfs.
    manager_owner=$(timeout 10 busctl --system --auto-start=no --timeout=10 call \
        org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus \
        NameHasOwner s id.waydro.Container) || fail 'Cannot inspect system bus ownership; repair D-Bus before setup.'
    case "$manager_owner" in
        'b true')
            if [[ -f $STATE/waydroid.cfg && -d $STATE/rootfs ]]; then
                SESSION_ID=$(manager_session) || fail 'Cannot verify Waydroid manager GetSession; inspect the container journal and retry setup.'
            fi ;;
        'b false') ;;
        *) fail 'Ambiguous Waydroid manager ownership; inspect the system bus before setup.' ;;
    esac
    if [[ -n $SESSION_ID ]]; then
        IFS='|' read -r owner display pid <<< "$SESSION_ID"
        [[ $owner == "$(id -u)" ]] || fail "Foreign or ambiguous Waydroid session (uid=${owner:-missing}); coordinate with its operator before setup."
        if [[ $display == wayland-kit ]]; then
            [[ $active == true && $fragment == "$USER_UNITS/$UNIT" ]] || fail 'Conflicting wayland-kit display without an owned active user service; resolve it before setup.'
            SESSION_KIND=managed
        else
            [[ $active == false ]] || fail 'User service is active alongside a graphical session; inspect and resolve the conflict before setup.'
            SESSION_KIND=graphical
        fi
    else
        [[ $active == false ]] || fail 'Ambiguous stopped session or active user service; inspect ownership before setup.'
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
            local candidate evidence rc
            for tool in "${missing[@]}"; do
                candidate=$tool
                [[ $tool != adb ]] || candidate=android-tools
                PACKAGES+=("$candidate")
                # Mapping is not proof of availability. Normal setup resolves once,
                # after sudo under setup.lock, without relying on the user's cache.
                if [[ $ACTION == check ]]; then
                    if evidence=$(timeout 30 dnf --cacheonly list --available "$candidate" 2>&1); then
                        printf 'Missing binary: %s; DNF candidate: %s; available in cached metadata only (fresh availability unverified).\n' "$tool" "$candidate"
                    else
                        rc=$?
                        printf 'Missing binary: %s; DNF candidate: %s; availability unknown without refreshing metadata (cache-only inspection exit %s).\n%s\n' "$tool" "$candidate" "$rc" "$evidence" >&2
                        [[ $rc != 124 ]] || printf 'Cache-only DNF inspection timed out after 30 seconds.\n' >&2
                    fi
                fi
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
    if [[ ${1:-} != quiet ]]; then
        printf 'Prerequisite inspection (%s); initialization: %s; missing packages: %s\n' "$arch" "$INIT_STATE" "${PACKAGES[*]:-none}"
    fi
}

# Never ask for a second password after admission, including during long downloads.
root() {
    local rc
    if timeout --foreground --kill-after=5 1800 sudo -n -- "$@"; then return; else rc=$?; fi
    printf 'waydroid-setup: Privileged step failed during %s: %s (exit %s). Sudo is noninteractive; inspect the diagnostic above and repair authorization or the command before retrying setup.\n' "$setup_stage" "$1" "$rc" >&2
    return "$rc"
}
sudo_failure() {
    case "$1" in
        124) fail 'Sudo authorization timed out; no host provisioning performed. Retry setup in the same terminal when ready.' "$1" ;;
        130) fail 'Sudo authorization interrupted; no host provisioning performed. Retry setup in the same terminal when ready.' "$1" ;;
        143) fail 'Sudo authorization terminated; no host provisioning performed. Retry setup in the same terminal when ready.' "$1" ;;
        137) fail 'Sudo authorization forcibly terminated (possibly after timeout); inspect terminal state and retry setup in the same terminal.' "$1" ;;
        1) fail 'Sudo authorization rejected; no host provisioning performed. Repair sudo authorization and retry setup in the same terminal.' "$1" ;;
        *) fail "Sudo authorization failed (exit $1); no host provisioning performed. Repair the reported cause and retry setup in the same terminal." "$1" ;;
    esac
}
sudo_admission() {
    local rc
    # Cached/passwordless access works even without a controlling terminal.
    if timeout --foreground --kill-after=5 10 sudo -n -v 2>/dev/null; then return; else rc=$?; fi
    [[ $rc == 1 ]] || sudo_failure "$rc"
    if ! ( : </dev/tty ) 2>/dev/null; then
        fail 'Sudo authorization needs interaction but no controlling terminal is available; no host provisioning performed. Log in normally and retry setup in the same terminal (do not pipe credentials).'
    fi
    # Keep sudo in the terminal's foreground job; sudo alone handles password input
    # and echo restoration. The script never reads, stores or forwards a password.
    if timeout --foreground --kill-after=5 300 sudo -v; then return; else rc=$?; fi
    sudo_failure "$rc"
}
setup_cleanup() {
    local rc=$?
    trap - EXIT
    if [[ -n $keepalive ]]; then
        kill "$keepalive" 2>/dev/null || true
        wait "$keepalive" 2>/dev/null || true
    fi
    [[ -z $stage ]] || rm -rf -- "$stage"
    exec 9>&-
    exit "$rc"
}
setup_failure() {
    local rc=$1 reason=$2
    if [[ $setup_stage == admission ]]; then
        fail "$reason during admission; no host provisioning performed. Retry setup in the same terminal." "$rc"
    fi
    fail "$reason during $setup_stage (exit $rc); host provisioning may be partial. No rollback attempted. Inspect package/device state and service journals; preserve data and keys, repair the cause, then retry setup (or --status if headless is running)." "$rc"
}
same_artifact() {
    # Don't open a FIFO or device just to compare bytes. Bound regular-file
    # comparisons too, in case a path changes or its filesystem stops responding.
    [[ -f $2 ]] || return 1
    local rc
    if timeout --kill-after=2 10 cmp -s -- "$1" "$2"; then return 0; else rc=$?; fi
    [[ $rc == 1 ]] || fail "Cannot compare $2 (exit $rc); check permissions and filesystem access, then retry setup." "$rc"
    return 1
}
container_ready() {
    [[ $(timeout 10 systemctl is-enabled waydroid-container.service 2>/dev/null) == enabled ]] &&
        timeout 10 systemctl is-active --quiet waydroid-container.service
}
setup() {
    keepalive='' stage='' setup_stage=admission
    trap setup_cleanup EXIT
    trap 'sudo_failure 130' INT
    trap 'sudo_failure 143' TERM
    trap 'setup_failure $? "Setup failed"' ERR
    command -v cmp >/dev/null || fail 'Missing prerequisite: cmp (diffutils). Install it before setup.'
    preflight quiet
    local expected_kind=$SESSION_KIND expected_id=$SESSION_ID
    # All read-only admission checks precede files, package installs and sudo.
    mkdir -p "$HOME/.local/share/kit-waydroid"
    exec 9>>"$HOME/.local/share/kit-waydroid/setup.lock"
    flock -n 9 || fail 'Another setup is running for this user; wait for it to finish.'
    # Admission is only a snapshot. A peer may finish between it and this lock;
    # never force that newly initialized device through init using stale state.
    preflight
    local -A artifact_changes=([dropin]=unchanged [user_unit]=unchanged [payload]=unchanged)
    local container_needs_enable=0 needs_sudo=0 linger user
    stage=$(mktemp -d)
    cat > "$stage/container.conf" <<EOF
# kit-waydroid user=$(id -u)
[Service]
Restart=on-failure
RestartSec=5
EOF
    same_artifact "$stage/container.conf" "$DROPIN" || artifact_changes[dropin]=changed
    container_ready || container_needs_enable=1
    user=$(id -un)
    linger=$(timeout 10 loginctl show-user "$user" --property=Linger --value) &&
        [[ $linger == yes || $linger == no ]] || fail 'Cannot inspect user linger; repair systemd-logind and retry setup.'
    if ((${#PACKAGES[@]} || container_needs_enable)) ||
        [[ $INIT_STATE != complete || ${artifact_changes[dropin]} == changed || $linger == no ]]; then
        needs_sudo=1
        sudo_admission
    fi
    setup_stage=packages
    trap 'setup_failure 130 "Setup interrupted"' INT
    trap 'setup_failure 143 "Setup terminated"' TERM
    if ((needs_sudo)); then
        # Reap only this refresher and its current child. Background wait lets TERM
        # interrupt either sleep or validation; timeout bounds sudo's termination.
        (child=''
         trap 'trap - TERM; kill "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; exit' TERM
         while :; do
             sleep 60 & child=$!; wait "$child" || exit
             timeout --kill-after=5 10 sudo -n -v & child=$!; wait "$child" || exit
         done
        ) </dev/null >/dev/null 2>&1 9>&- &
        keepalive=$!
    fi
    if ((${#PACKAGES[@]})); then
        if [[ $MANAGER == dnf ]]; then
            # One fresh resolution/install transaction; keep DNF's diagnostics
            # (no match, repo/network/access errors) rather than guessing absence.
            local rc reason
            if root dnf --refresh install -y "${PACKAGES[@]}"; then
                :
            else
                rc=$?
                reason="failed (exit $rc)"
                [[ $rc != 124 ]] || reason='timed out after 1800 seconds'
                fail "DNF resolution/install $reason for: ${PACKAGES[*]}. Inspect DNF diagnostics above; repair the reported package/repository/network/access cause, then retry setup. No GUI stop or device service activation performed." "$rc"
            fi
        else
            root "$MANAGER" install -y "${PACKAGES[@]}"
        fi
    fi
    local tool
    for tool in waydroid weston adb; do
        command -v "$tool" >/dev/null || fail "Package install did not provide $tool; inspect package logs."
    done
    local help
    help=$(timeout 10 weston --help)
    [[ $help == *headless* && $help == *--use-pixman* ]] || fail 'Installed Weston lacks headless/pixman support; no device services configured.'
    [[ $(timeout 10 systemctl show waydroid-container.service --property=LoadState --value) == loaded ]] || fail 'Missing waydroid-container.service; install the distro systemd integration.'
    setup_stage=transfer
    transfer_session "$expected_kind" "$expected_id"
    setup_stage=initialization
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
    setup_stage=container-service
    if [[ ${artifact_changes[dropin]} == changed ]]; then
        [[ -d ${DROPIN%/*} ]] || root install -d -m 755 "${DROPIN%/*}"
        root install -m 644 "$stage/container.conf" "$DROPIN"
        root systemctl daemon-reload
    fi
    # Package installation or initialization may have enabled/started it already.
    if ((container_needs_enable || ${#PACKAGES[@]})) || [[ $INIT_STATE != complete ]]; then
        container_ready || root systemctl enable --now waydroid-container.service
    fi
    [[ $linger == yes ]] || root loginctl enable-linger "$user"
    setup_stage=user-service
    if [[ $SELF != "$PAYLOAD" ]]; then
        if ! same_artifact "$SELF" "$PAYLOAD"; then
            install -m 755 "$SELF" "$PAYLOAD"
            artifact_changes[payload]=changed
        elif [[ ! -x $PAYLOAD ]]; then
            # An identical copy restored without its mode still has to start.
            chmod 755 "$PAYLOAD"
        fi
    fi
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
    if ! same_artifact "$stage/user.service" "$USER_UNITS/$UNIT"; then
        mkdir -p "$USER_UNITS"
        install -m 644 "$stage/user.service" "$USER_UNITS/$UNIT"
        timeout 15 systemctl --user daemon-reload
        artifact_changes[user_unit]=changed
    fi
    # Last competing-owner/socket check before activating the managed service.
    [[ -z $TRANSFER_STAGE ]] || TRANSFER_STAGE=start
    classify_session
    local observed
    observed=$(manager_session) || fail 'Cannot verify manager before managed startup; inspect container journal and retry setup.'
    if [[ $SESSION_KIND == managed ]]; then
        [[ $observed == "$SESSION_ID" ]] || fail 'Managed session identity changed before start; inspect ownership and retry setup.'
        if [[ ${artifact_changes[payload]} == changed ]]; then
            printf 'The new payload takes effect at the next service restart. To apply it now: systemctl --user restart %s\n' "$UNIT"
        fi
    else
        [[ -z $observed && $SESSION_KIND == stopped ]] || fail 'Competing session appeared before managed start; inspect ownership and retry setup.'
    fi
    if [[ $SESSION_KIND != managed || $(timeout 10 systemctl --user is-enabled "$UNIT") != enabled ]]; then
        [[ -z $TRANSFER_STAGE ]] || TRANSFER_STATE='GUI stopped; managed headless startup requested'
        timeout 30 systemctl --user enable --now "$UNIT" || fail 'Managed headless service activation failed; inspect user service journal and retry setup.'
    fi
    setup_stage=verification
    confirm_managed
    [[ -z $TRANSFER_STAGE ]] || { TRANSFER_STAGE=adb; TRANSFER_STATE='GUI stopped; managed headless session confirmed'; }
    verify_device
}

case "$ACTION" in
    check)
        preflight
        if [[ $SESSION_KIND == graphical ]]; then
            printf 'Planned same-user graphical transfer: open GUI apps will be interrupted; stop, confirm release, start managed headless, verify Android.\n'
        fi
        if [[ $MANAGER == dnf ]] && ((${#PACKAGES[@]})); then
            fail "Missing DNF dependencies: ${PACKAGES[*]}; --check cannot verify fresh availability without modifying the cache. After inspecting diagnostics, run ordinary setup for authorized fresh resolution/install."
        fi ;;

    status) verify_device ;;
    stop) timeout 30 systemctl --user disable --now "$UNIT"; printf 'Headless session disabled; Android data, images and ADB keys preserved. See docs/waydroid.md for host opt-out.\n' ;;
    session) run_session ;;
    setup) setup ;;
esac
