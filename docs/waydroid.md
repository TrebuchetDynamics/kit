# One native Android device across repositories

From **any working directory**, run the script from your Kit checkout as your
normal testing user (replace the absolute checkout path):

```sh
/path/to/kit/waydroid-universal-setup.sh
```

Review the script first. This is an **operator-run host change**, not part of Kit
installation. It asks for ordinary sudo authorization when needed, installs
missing packages, initializes native Waydroid, enables its container at boot and
enables a lingering headless user service. It does not install APKs, accounts,
Maestro or project tests.
No VM, emulator, SELinux relaxation, firewall change or ADB authorization bypass is
provided. If this user has a graphical Waydroid session, default setup transfers
it to the managed headless service in the same invocation. **Open GUI apps will be
interrupted.** There is no extra flag, manual stop or second confirmation; ordinary
sudo admission still applies when privileged work is needed. A device is reported
ready only after the managed session, authorized ADB, Android boot, release and ABI
checks succeed.
No graphical login is required for setup, operation or recovery. An incoming
same-user graphical session is transferred, not a supported steady state.
**Live qualification is still outstanding**; fixture tests are not installation or
reboot evidence. Prior run `374a5fbe` remains prior environment evidence, not proof.

## Read the setup progress

Setup prints eight numbered results in order: prerequisites, sudo, packages,
transfer, initialization, container service, user service, and Android
verification. Each result includes elapsed seconds. Package installation, image
initialization and the Android boot wait announce when they start. During the boot
wait, a changed reason (`ip`, `connection`, `authorization` or `boot`) is reported
at most once every 15 seconds.

For example, on a first run that needs Weston and fresh images (excerpt):

```text
packages: starting (installing weston)
[3/8] packages: changed (installed weston) 12s
initialization: starting (running waydroid init)
[5/8] initialization: changed (images and configuration ready) 212s
[6/8] container service: changed (container drop-in, container service, linger) 2s
[7/8] user service: changed (service executable, user unit, user service) 3s
Android verification: starting (waiting for Android boot)
Android boot wait: boot
[8/8] Android verification: unchanged (Android ready) 25s
Summary: 8 changed (packages, initialization, container drop-in, container service, linger, service executable, user unit, user service); 1 unchanged (graphical transfer)
```

Run the same command again on the ready host (excerpt):

```text
[2/8] sudo: skipped (no privileged changes needed) 0s
[3/8] packages: unchanged (waydroid, weston, adb present) 0s
[5/8] initialization: unchanged (already initialized) 0s
Summary: 0 changed (none); 9 unchanged (packages, initialization, container drop-in, container service, linger, service executable, user unit, user service, graphical transfer)
```

The summary comes before the final `ADB serial:`, `Android:` and `ABI:` lines.
If provisioning completed but Android verification fails (for example, ADB
authorization is pending), setup still reports what changed, without the ready
report. A failed stage points to the existing error on stderr.
Add `--verbose` to see external commands (including `sudo -n -- ...`)
on stderr before they run. It does not trace environment contents, captured
session data or terminal input; password entry still belongs to sudo.

## Host capabilities, not a distro allowlist

The read-only admission command prints the same numbered stages, skipping work
that would change the host or connect to Android. It makes no files, sudo calls
or downloads:

```sh
/path/to/kit/waydroid-universal-setup.sh --check
```

Required: Linux x86_64 or aarch64 (official native image architectures), systemd
system and user managers with D-Bus, a normal PAM login and `XDG_RUNTIME_DIR`,
Android Binder IPC (loaded nodes or available `binder_linux` module), memfd or
ashmem, cgroups and container namespaces. Bash, Python 3 with `os.memfd_create`
(unless ashmem is present), GNU timeout/coreutils, util-linux flock and sudo must
already be installed, including systemd's `busctl` with JSON output support.
Setup also uses `cmp` from diffutils to compare installed files.
Waydroid's distro package supplies LXC/networking helpers;
Weston must include the headless backend and `--use-pixman`. Its private
`wayland-kit` socket is not a desktop environment requirement; neither `DISPLAY`
nor an inherited desktop `WAYLAND_DISPLAY` is needed. Official images,
working DNS/HTTPS, storage for downloaded archives plus extracted Android images,
and working local DHCP/Waydroid networking are also necessary.

- APT: installs missing `waydroid`, `weston`, `adb` from **already configured**
  repositories. If APT cannot find `waydroid`, see the [official Waydroid desktop
  installation instructions](https://docs.waydro.id/usage/install-on-desktops).
  Recent Ubuntu releases provide `waydroid` in `universe`.
- DNF: maps missing `waydroid`, `weston`, `adb` binaries to `waydroid`, `weston`,
  `android-tools`. Ordinary setup does not require a warm/readable user cache:
  after sudo authorization, under the setup lock, one bounded
  `dnf --refresh install -y` transaction resolves and installs only the mapped
  missing packages (and their dependencies) from **already enabled** repositories.
  There is no separate metadata refresh or reliance on root sharing the user cache.
  With all binaries present, no DNF install or refresh runs. No repositories are
  added/enabled, signature policy changed or broad upgrade requested.
  `--check` uses only `dnf --cacheonly list --available` inspection: it names each
  missing binary/candidate and returns nonzero for missing DNF dependencies, even
  if a candidate appears in cached metadata. Failed/insufficient cached inspection
  means **availability unknown**, not package absence; fresh availability cannot
  be verified without modifying the cache. Run ordinary setup for authorized
  fresh resolution, rather than prewarming metadata yourself.
- pacman (Omarchy and other Arch hosts): maps missing `waydroid`, `weston`, `adb`
  binaries to `waydroid`, `weston`, `android-tools`, provided by Arch's official
  `extra` repository. `--check` uses `pacman -Si` against the local sync database
  only, reports candidates as available or unknown, and returns nonzero for
  missing binaries. Setup uses one `pacman -S --needed --noconfirm` transaction
  for the missing packages after sudo authorization and under the setup lock.
  It uses existing sync databases and enabled repositories, with no AUR helper
  or added repository. Keep the system and sync databases in sync: if the
  database lacks a package, run `sudo pacman -Syu` yourself first, then retry
  setup. Setup runs neither a database refresh (`-Sy`) nor a system upgrade
  (`-Syu`). Arch does not support partial upgrades.
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

## Sudo admission, cancellation and safe retry

Setup inspects prerequisites before and after acquiring its per-user lock, but
prints just one prerequisites result. `--check` remains read-only and sudo-free.
Setup calls sudo and keeps its authorization alive only if it needs to install
packages, finish initialization, update the container drop-in, enable or start
`waydroid-container.service`, or enable linger. A ready host skips sudo entirely,
including the cached-authorization check. Cached or passwordless sudo authorization
works without a terminal when privileged work is needed. If interaction
is required, setup needs a controlling terminal: log in normally and rerun the
same setup command **in that same terminal**. Do not pipe credentials, put them in
arguments/environment variables, or send them to an agent or log.

The admission prompt uses bounded foreground execution (five minutes, followed by
up to five seconds for forced termination). Ordinary sudo owns password input and
terminal echo; setup does not read, store or log passwords. Press **Ctrl-C once**
to cancel. Admission interruption returns **130**, timeout returns **124** (or
**137** if forced termination was needed), and authorization rejection returns
**1**, with distinct diagnostics. Repair authorization or terminal state if needed,
then rerun the same command when ready. Admission failure does not install packages,
stop sessions or change units; the local setup directory/lock file can remain.
The lock is released on exit; do not delete it to bypass a running setup.

After admission, privileged steps and credential refresh use **noninteractive
sudo**. Expired/revoked authorization fails the affected step instead of opening a
second password prompt. The diagnostic identifies the failed stage; refresh helpers
are stopped and reaped on exit. There is no automatic authorization retry or rollback.
Once provisioning begins, cancellation or failure **can leave partial host changes**
(packages, initialization, GUI transfer or service configuration). Inspect the
reported stage, package-manager state, `waydroid status` and service journals below;
preserve Android data and ADB keys, repair the reported cause, then retry setup.
If a `daemon-reload` failed after the unit file was installed, retry the reload
for the affected manager (`sudo systemctl daemon-reload` or
`systemctl --user daemon-reload`) before rerunning setup. If managed headless is
already running, use `--status` to verify it. A failed step is not a ready device
and is not evidence that earlier changes were undone.

## What persists and how retries work

One host Waydroid container is shared by one testing user, not one per repository.
A different or missing session UID, ambiguous display, foreign loaded user unit,
or colliding `wayland-kit` socket/lock refuses takeover. A running session is
recognized as managed only with the current UID, `wayland-kit` display and an
active owned `kit-waydroid.service`. Setup only writes the container drop-in,
user unit and service executable when they are missing or their bytes differ.
The service executable is kept as an independent file, not a symlink to the
checkout. If it is identical but has lost its execute permission, setup
restores that permission without recopying it. Setup runs `daemon-reload` for
the corresponding manager only after changing a unit file or drop-in, and runs
`enable --now` only for a unit that is not enabled or not active. A working
managed session is not stopped or restarted on repeat, even when setup updates
its executable. The new copy takes effect at the next restart. To apply it now,
run `systemctl --user restart kit-waydroid.service` when an interruption is
acceptable. An unchanged repeat still verifies Android and prints the ADB serial,
Android version and ABI.

`--check` reports a planned same-user graphical transfer without sudo, writes,
stops or service changes. Classification uses non-activating system-bus queries,
not `waydroid status` (whose D-Bus proxy can activate a stopped manager).
Default setup finishes capability, image/data, ownership, package and any
required sudo checks before disrupting the GUI. Under the existing setup lock it
re-reads the session UID, display and process identity immediately before one
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

Android must already trust **the current user's unchanged ADB key**. A previously
authorized key can proceed without a desktop, after the normal serial, boot,
release and ABI checks. Secure ADB requires Android-side RSA trust; a successful
headless startup or ADB connection attempt does not grant that trust.

If Android reports `unauthorized`, setup and `--status` return **exit 2** with
`ADB authorization pending` after the bounded wait, not a ready report. The managed
headless service stays running and existing data and keys stay intact. Do not stop
it, switch to a graphical session, replace/inject keys or disable secure ADB to
conceal this result. Kit cannot provide unattended first-time authorization and
does not offer a graphical authorization recovery procedure.

Retry `--status` only after valid Android authorization for this same user's key
exists. Establishing that trust is an external prerequisite, not something setup
or repeated status calls can approve. If it cannot be satisfied, the device remains
non-ready; leave headless operation and keys intact. Once valid trust exists,
`--status` can verify readiness without restarting or changing display mode:

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

Setup/status return 0 only for verified readiness and 2 for authorization pending.
Other failures return nonzero. Failure diagnostics return no ready report:

| Error | Next action |
| --- | --- |
| `DNF resolution/install failed` | Read the retained DNF diagnostic: explicit no match differs from repository metadata, DNS/network or permission failures. Repair the reported package/repository/access cause using the distro's official instructions, then retry ordinary setup. A user-cache failure alone does not prove absence. No GUI stop or device service activation has occurred. |
| `DNF resolution/install timed out after 1800 seconds` | Inspect DNF/package-manager state and connectivity before retrying setup; the transaction may have partially installed packages. GUI transfer and device activation have not begun. |
| `No container IP` | Inspect `waydroid status` and container journal; repair waydroid0/DHCP/network policy. UNKNOWN may be transient; retry status. |
| `ADB authorization pending` (exit 2) | Missing Android trust for the current user's key. Keep headless running and keys intact; retry status only after valid authorization for that same key exists. Kit cannot establish first-time trust unattended. |
| `ADB not connected` | Check Android TCP 5555 and local firewall, without opening ADB externally. |
| `Android boot timeout` | Inspect journals/rendering and retry with `--wait 300`. Never wipe data to conceal failure. |
| `Android properties unavailable` | Check `adb devices` and `adb shell getprop`, then retry status after restoring the connection. |

Transfer failures also report the stage (`stop`, `release`, `provision`, `start`
or `adb`), whether GUI stop was attempted/release confirmed and whether headless
startup was requested/confirmed. Stop failure, timeout, continued ownership or failed
D-Bus readback prevents headless activation. After release, a startup or ADB failure
does not restore the GUI automatically. Inspect the reported status/journals below,
repair the cause, then retry default setup; if managed headless is running, retry
`--status`. Authorization pending is different: headless startup has succeeded,
but Android trust for the current user's key is missing. Keep that service running;
retry `--status` only when the authorization prerequisite above is satisfied, not
by restoring a GUI or replacing keys. No graphical recovery is required or offered.

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
For DNF, also verify one ordinary invocation with missing Weston and a cold user
cache: authorized fresh resolution/install must precede headless capability checks
and any GUI transfer. Capture repository/package errors without disrupting the GUI
when resolution fails. Fake DNF tests do not prove package availability on Fedora.
On Omarchy, verify a clean setup with missing packages resolved from Arch `extra`,
then repeat setup and confirm it performs no pacman install and preserves Android
state and keys.
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
