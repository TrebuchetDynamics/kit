# One native Android device across repositories

From **any working directory**, run the script from your Kit checkout as your
normal testing user (replace the absolute checkout path):

```sh
/path/to/kit/waydroid-universal-setup.sh
```

Review the script first. This is an **operator-run host change**, not part of Kit
installation. It asks for ordinary sudo authorization, installs missing packages,
initializes native Waydroid, enables its container at boot and enables a lingering
headless user service. It does not install APKs, accounts, Maestro or project tests.
No VM, emulator, SELinux relaxation, firewall change or ADB authorization bypass is
provided. If this user has a graphical Waydroid session, default setup transfers
it to the managed headless service in the same invocation. **Open GUI apps will be
interrupted.** There is no extra flag, manual stop or second confirmation; ordinary
sudo admission still applies. A device is reported ready only after the managed
session, authorized ADB, Android boot, release and ABI checks succeed.
**Live qualification is still outstanding**; fixture tests are not installation or
reboot evidence. Prior run `374a5fbe` remains prior environment evidence, not proof.

## Host capabilities, not a distro allowlist

The read-only admission command makes no files, sudo calls or downloads:

```sh
/path/to/kit/waydroid-universal-setup.sh --check
```

Required: Linux x86_64 or aarch64 (official native image architectures), systemd
system and user managers with D-Bus, a normal PAM login and `XDG_RUNTIME_DIR`,
Android Binder IPC (loaded nodes or available `binder_linux` module), memfd or
ashmem, cgroups and container namespaces. Bash, Python 3 with `os.memfd_create`
(unless ashmem is present), GNU timeout/coreutils, util-linux flock and sudo must
already be installed, including systemd's `busctl` with JSON output support.
Waydroid's distro package supplies LXC/networking helpers;
Weston must include the headless backend and `--use-pixman`. Official images,
working DNS/HTTPS, storage for downloaded archives plus extracted Android images,
and working local DHCP/Waydroid networking are also necessary.

- APT: installs missing `waydroid`, `weston`, `adb` from **already configured**
  repositories. Configure Waydroid's official repository first if absent.
- DNF: installs missing `waydroid`, `weston`, `android-tools`. Admission uses cached
  package metadata; configure repositories/refresh metadata yourself if missing.
- Other Linux distributions/package managers: install those native capabilities
  using the distribution's supported Waydroid instructions, then run the same
  script. An unknown distro name is not rejected. No arbitrary third-party
  repository is added and no distribution is claimed qualified from fixtures.
- Non-systemd init, absent Binder, missing namespaces or unsupported official image
  architecture stop before setup changes and name the prerequisite. This is safe
  refusal, **not a working Android device**. A successful preflight is not proof
  that kernel policy, graphics, network or Android will boot.

Fedora x86_64 is a reference observation, not a support boundary. Ubuntu and other
native-capable hosts are in scope; real cross-distribution runs remain required.
SELinux/AppArmor stay enabled. Diagnose denials against the distro's Waydroid
policy rather than disabling security. Restricted containers/WSL often lack native
requirements; supplying a distro name does not establish the capabilities.

## What persists and how retries work

One host Waydroid container is shared by one testing user, not one per repository.
A different or missing session UID, ambiguous display, foreign loaded user unit,
or colliding `wayland-kit` socket/lock refuses takeover. A running session is
recognized as managed only with the current UID, `wayland-kit` display and an
active owned `kit-waydroid.service`. A stopped device starts as needed; a working
managed session is not stopped or restarted on repeat.

`--check` reports a planned same-user graphical transfer without sudo, writes,
stops or service changes. Classification uses non-activating system-bus queries,
not `waydroid status` (whose D-Bus proxy can activate a stopped manager).
Default setup finishes capability, image/data, ownership,
package and sudo checks before disrupting the GUI. Under the existing setup lock
it re-reads the session UID, display and process identity immediately before one
bounded, **unprivileged** `waydroid session stop`. Changed identity refuses the stop.
It then waits for successful system-bus container `GetSession` evidence of **no
session**. A successful stop exit or a `STOPPED` status line alone is insufficient:
upstream can hide D-Bus errors in both commands. Loss of the manager fails closed,
without starting a competing session. Ownership is checked again before activation.
Startup uses the existing user-systemd/Weston `--session` path, not an extra unmanaged
session. The active owned unit and expected UID/display are confirmed before ADB
boot, release and ABI verification, and checked again before printing readiness.
No global service restart or speculative GUI rollback is performed.

The setup uses explicit official channels on initialization:
`https://ota.waydro.id/system` and `https://ota.waydro.id/vendor` (VANILLA upstream
default). It checks config, image headers/timestamps, rootfs, base properties and
LXC config after init, because init can exit successfully without initialization.
It then checks actual device boot. Fresh initialization adds software rendering
properties before generating Waydroid's base properties; existing rendering
choices are preserved.

A complete initialization is skipped on repeats: no image download/upgrade or
key rotation. For interrupted *initial* downloads, rerun the command. Waydroid
validates downloaded hashes and retains valid peer-image timestamps; a missing or
invalid image header resets only its timestamp. A newer upstream image may be
selected during incomplete initialization. Incomplete state alongside existing
Android data or overlay files refuses reinitialization (empty initial overlay
scaffolding can be retried): restore known-good images/config
from backup rather than force-initializing or deleting overlays. Unreadable overlay
subdirectories also refuse setup; they are not assumed empty. Initialization is
rechecked after acquiring the setup lock so a just-completed peer run is not
reinitialized from an earlier snapshot. Do not use
`waydroid init --force` as a routine retry. Keep `~/.android/adbkey*` unchanged.

Owned artifacts:

- `/etc/systemd/system/waydroid-container.service.d/kit-headless.conf` adds
  `Restart=on-failure` to the package's root container service.
- `~/.config/systemd/user/kit-waydroid.service` (or `$XDG_CONFIG_HOME/systemd/user`)
  runs Weston headless, the Waydroid user session and unprivileged ADB reconnect.
- `~/.local/share/kit-waydroid/waydroid-universal-setup.sh` is the durable user
  service executable; the source checkout can move afterward. A setup lock is
  retained beside it. The setup's `XDG_DATA_HOME` is persisted in the user unit so
  reboot uses the same Android user data. Use that same environment for status.
- `loginctl enable-linger USER` starts the user manager after reboot without login.

No sudoers file or passwordless grant is created; there is **nothing to revoke
with visudo**. systemd recovers failed services under their existing identities.
Setup keeps its operator-approved sudo timestamp alive only during provisioning;
normal testing and reconnect do not call sudo. Manual container repair can still
require ordinary sudo. Android data and ADB keys are never removed by the script.

## Authorization and ordinary testing

On the first connection Android may show an RSA authorization prompt. Approve the
fingerprint for **this user's** ADB key and select “Always allow” if appropriate.
A headless compositor has no interactive screen. Use trusted local/remote desktop
access to view Android; do not inject keys or turn off secure ADB. For example,
from a graphical **Wayland** terminal as the same user, temporarily replace the
headless compositor with a nested visible one (requires Weston's Wayland backend):

```sh
systemctl --user stop kit-waydroid.service
# WAYLAND_DISPLAY here must still name the desktop compositor's socket.
weston --backend=wayland-backend.so --use-pixman --socket=wayland-kit --idle-time=0 --no-config
# In a second terminal, same user:
WAYLAND_DISPLAY=wayland-kit waydroid session start
# In a third terminal:
WAYLAND_DISPLAY=wayland-kit waydroid show-full-ui
```

Run the status command to trigger ADB connection, approve the visible prompt, then
stop that temporary session (`waydroid session stop`), close nested Weston and run
`systemctl --user start kit-waydroid.service`. On an X11 desktop use Weston's
`--backend=x11-backend.so` instead. A machine without any trusted interactive display
path must first acquire one to approve authorization; unattended setup cannot
legitimately bypass this gate.

```sh
~/.local/share/kit-waydroid/waydroid-universal-setup.sh --status --wait 180
# Only after ready: ADB serial: <actual IP>:5555 / Android: <version> / ABI: <abi>
# Use that actual serial, in either unrelated project directory:
cd /path/to/repository-one
adb -s ACTUAL_SERIAL shell getprop ro.build.version.release
cd /path/to/unrelated-repository
adb -s ACTUAL_SERIAL shell getprop ro.product.cpu.abi
```

The service reconnects after DHCP/reboot. IP/serial can change after reboot;
query `--status` again. No sudo or repo configuration is needed. Always select the
reported serial if other ADB devices exist. ADB keys remain private to this user;
never publish them or expose the Android ADB port to untrusted networks.

Failure diagnostics are distinct, and return nonzero without a ready report:

| Error | Next action |
| --- | --- |
| `No container IP` | Inspect `waydroid status` and container journal; repair waydroid0/DHCP/network policy. UNKNOWN may be transient; retry status. |
| `ADB authorization pending` | View and approve the Android prompt for the current key; retry status. |
| `ADB not connected` | Check Android TCP 5555 and local firewall, without opening ADB externally. |
| `Android boot timeout` | Inspect journals/rendering and retry with `--wait 300`. Never wipe data to conceal failure. |
| `Android properties unavailable` | Check `adb devices` and `adb shell getprop`, then retry status after restoring the connection. |

Transfer failures also report the stage (`stop`, `release`, `provision`, `start`
or `adb`), whether GUI stop was attempted/release confirmed and whether headless
startup was requested/confirmed. Stop failure, timeout, continued ownership or failed
D-Bus readback prevents headless activation. After release, a startup or ADB failure
does not restore the GUI automatically. Inspect the reported status/journals below,
repair the cause, then retry default setup; if managed headless is running, retry
`--status`. For authorization failure, use the visible approval procedure above;
never replace keys or bypass Android authorization.

Each external observation is bounded; the wait deadline is checked between calls.
`--wait` (default 180 seconds) also bounds the release and managed-session observation
loops separately; the stop command itself has a 30-second timeout.
For service state/logs (unprivileged journal access depends on distro policy):

```sh
systemctl status waydroid-container.service
systemctl --user status kit-waydroid.service
journalctl --user -u kit-waydroid.service -n 100 --no-pager
journalctl -u waydroid-container.service -n 100 --no-pager
```

## Opt out or remove (data preserved)

Stop/disable just the owned user session:

```sh
~/.local/share/kit-waydroid/waydroid-universal-setup.sh --stop
```

To remove this setup, after inspecting that these are still the owned artifacts:

```sh
rm -- "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/kit-waydroid.service"
systemctl --user daemon-reload
rm -r -- "$HOME/.local/share/kit-waydroid"
sudo rm -- /etc/systemd/system/waydroid-container.service.d/kit-headless.conf
sudo systemctl daemon-reload
# Only if no other Waydroid consumer needs the container:
sudo systemctl disable --now waydroid-container.service
# Only if no other user services need lingering, and you did not have it before:
sudo loginctl disable-linger "$USER"
```

Packages are not uninstalled. `/var/lib/waydroid`, the user's Waydroid data home
(`${XDG_DATA_HOME:-$HOME/.local/share}/waydroid`) and `~/.android` remain intact.
Back them up before any separately authorized destructive reset. Setup does not
record/restore prior service enablement or lingering; decide those shared host
settings with the operator rather than blindly disabling unrelated services.

## Operator live evidence still required

Record non-secret host/kernel, Waydroid/Weston versions, commands, real exit codes
and journals for: clean install; second run with unchanged data/keys and no init;
interruption during initial download followed by recovery; reboot without login
and automatic Android startup; authorized boot/actual serial/version/ABI; and
unprivileged queries from two unrelated working directories. Include native
non-Fedora evidence and relevant kernel/package/init differences, not just one
successful distribution. Separately authorize a default-setup run from this user's
graphical session: confirm the interruption warning, release, owned headless session
and authorized boot serial/version/ABI; repeat without a bounce and compare preserved
images/data/overlays/keys. Do not post keys, private account identities or APK data.
These checks require operator authorization and are **not performed by offline
fixtures or by the delivery runner**.

Contracts: [official installation](https://docs.waydro.id/usage/install-on-desktops),
[Waydroid CLI](https://docs.waydro.id/usage/waydroid-command-line-options),
[pinned status semantics](https://github.com/waydroid/waydroid/blob/a1a1936a7ed74e1537deeb3420302997869d8a4d/tools/actions/status.py),
[pinned stop semantics](https://github.com/waydroid/waydroid/blob/a1a1936a7ed74e1537deeb3420302997869d8a4d/tools/actions/session_manager.py),
[pinned GetSession contract](https://github.com/waydroid/waydroid/blob/a1a1936a7ed74e1537deeb3420302997869d8a4d/tools/actions/container_manager.py),
[official initialization source](https://github.com/waydroid/waydroid/blob/main/tools/actions/initializer.py),
[official image handling](https://github.com/waydroid/waydroid/blob/main/tools/helpers/images.py),
[ADB](https://developer.android.com/tools/adb),
[DNF commands](https://dnf.readthedocs.io/en/latest/command_ref.html).
