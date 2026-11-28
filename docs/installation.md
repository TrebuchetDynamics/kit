# Installation

> **GitHub-native delivery:** GitHub Issues own executable work; Orbi owns delivery.
> Preserve existing task data, attempts, worktrees and
> recovery evidence. For activation and live qualification, see
> [setup and migration](github-native.md).

Source: [suite installer](../install.sh), [installer implementation](../scripts/install_menu.py).
Kit installs into Claude Code, Codex and Pi (through Pi-Bolt), plus the `tx`
launcher and the Orbi CLI. Kit no longer supports Hermes; `./install.sh --only hermes`
fails with that message and changes nothing.

## Update Kit

Explicit `/update-kit` loads [one canonical workflow](../skills/update-kit/SKILL.md)
on every packaged host. Its [standard-library helper](../skills/update-kit/scripts/update_kit.py)
requires Python 3.11+, Git, bash and lsof on Linux/macOS. It downloads the complete
`https://github.com/TrebuchetDynamics/kit.git`, branch `main`, into the persistent
`${XDG_DATA_HOME:-$HOME/.local/share}/kit/source`. `XDG_DATA_HOME` must be absolute;
correct it or unset it on an error. Keep it on persistent storage, not `/tmp` or a
host package/plugin cache. No project/developer checkout is discovered or adopted.
Keep source after installation because native installs can link to it.

Before execution, the workflow explains the [full-suite effects](#full-suite-from-a-checkout):
all available components by default, possible Pi-Bolt bootstrap and active supported
integration restarts only for proven effective changes. Unchanged reruns still check for updates,
but request no service restarts. It delegates native prompts, availability/skips, verbose output
and nonzero partial-failure behavior rather than implementing host update logic.
For example, `/update-kit --only pi,tx` narrows the components. Menu selection is
not supported by the updater; use explicit flags. No-restarts requests are refused
before mutation, because the installer restarts proven affected services.

Read-only/questions-only/`--dry-run` (also `--list`) shows intended source path/argv
with unavailable facts `NOT_CHECKED`. It does not clone, fetch, create directories
or locks, probe hosts or write caches. Resolve the helper from the loaded skill,
not cwd; direct invocation is `python3 -B <loaded-skill>/scripts/update_kit.py --dry-run`.

The helper serializes update-kit invocations through installation. This is **not**
a global lock: preexisting live/unknown consumers of the source hold. Wait for idle
consumers before retrying. It conservatively checks source open files and
processes; scan uncertainty also holds. A fresh
clone is staged in a unique sibling; failures retain that directory for diagnosis.
Existing source requires updater provenance, same-user ownership, non-symlink safe
paths, fixed origin, clean attached `main`, no extra worktrees and no local-ahead or
diverged history. Repair holds manually while preserving source, edits, history and
evidence; the helper never resets, stashes, cleans, forces, repins or deletes it.

It fetches only fixed upstream and fast-forwards `main`, then invokes that fetched
checkout's `bash install.sh update --no-pull` once, including equal-SHA reinstalls.
`--no-pull` suppresses only the outer installer pull. The receipt reports old,
helper-selected and final SHA. Installer output
owns component outcomes; nonzero/partial failure propagates and successful host
items remain installed, not rolled back. Repair the reported cause and retry only
compatible selected failures. Reload/reopen the current agent session for discovery;
package refresh does not reload a running agent. The installer can activate Orbi
when that component is selected; it does not qualify live delivery.

## Full suite from a checkout

`./install.sh` installs the full suite for every available host with live progress.
Use `--menu` when you want to select components interactively:

```sh
./install.sh
./install.sh --menu
./install.sh --dry-run
./install.sh --only codex
```

The suite includes the Pi package, the Pi-Bolt native executable, the Orbi CLI,
the `tx` launcher, and Claude Code and Codex plugins
with their complete portable skill suites, including [bundled Ponytail](cross-host.md#bundled-ponytail-on-every-host).
All Kit skills apply its shared method within their existing authority; no
separate Ponytail plugin, hooks or persistent modes are installed. Existing external
Ponytail installs are not changed or removed. `--full` (`--all`) is the default; `--skip` excludes components. Host CLIs
for Claude Code and Codex must already be installed: full mode reports missing hosts as skipped, while
`--only` reports a requested missing host as failed. Pi-Bolt is installed first;
the `pi` item requires that destination executable to install Kit. A simple
shell launcher whose target is missing or not executable also counts as unavailable.
Fresh portable installs use Claude marketplace `kit` and Codex marketplace
`kit-marketplace`; the plugin name remains `kit`. During an actual install, the
installer validates canonical and legacy registrations and installed Kit IDs before
marketplace/plugin changes. Owned canonical sources are reused without removal or
re-addition; Claude updates preserve installed scope, while Codex snapshot upgrades
leave an installed plugin's effective enablement/scope alone. Legacy/coexisting,
foreign, unknown or stale sources hold that component for
manual ownership reconciliation or host qualification.
No registry/settings rewrite or cache uninstall is attempted. Codex requires
`plugin marketplace list --json` and filtered `plugin list --marketplace NAME --json`
for the Kit marketplace; Claude requires `plugin list --json`. Missing interfaces or invalid
output fail closed. Codex lists show effective configuration, not all persisted
scopes. CLI initialization may write cache/auth state; these are not read-only
probes. Availability detection does not start host CLIs or change settings.
Dry-run invokes no registry probes or mutations and reports registry/migration status
as `NOT_CHECKED`, with planned validation. The tmux launcher needs `tmux`.
The owner's accepted tx rules (2026-11-16) for this suite installer are:

- A replaced `~/.local/bin/tx` (or `KIT_BIN_DIR/tx`) moves to
  `~/.local/state/kit/backups/tx.bak`, then `.bak.1` and increasing numbers. Only
  the newest five command backups are kept, in replacement order. Keep this state
  directory off `PATH`; no new `tx.bak*` executables are created in the bin directory.
  A symlinked `tx` is moved aside, never written through.
- Bash, zsh and fish completion files are generated from the installed `tx`.
  Missing files are written; regular files with different content are replaced,
  with their previous content saved beside them as `<name>.bak`, then `.bak.1`
  and so on without overwriting earlier completion backups. Identical files,
  symlinks (including dangling symlinks) and other non-regular targets are kept.
  The tx detail line reports each shell completion as `written`, `replaced` or `kept`.
- Existing tmux configuration and helpers (`git-status.sh`, `short-path.sh`,
  `copy.sh`) are kept, including dangling symlinks; only missing files are installed.

Existing `tx.bak*` files in the bin directory are not removed automatically.
After checking that you no longer need them for recovery, use this manual cleanup
command in Bash (it prompts before each removal):

```sh
rm -i -- "${KIT_BIN_DIR:-$HOME/.local/bin}"/tx.bak*
```

These rules do not change the separate [tmux installer](../tmux/README.md#install):
`tmux/install.sh` and `tx install` still use their existing timestamp backups,
including backups beside the command in the bin directory.

The installer rejects unknown `--only` and `--skip` names before changing the
checkout. Non-preview suite runs take a nonblocking advisory lock before any
automatic stash or pull, and hold it across re-execution through component
installs, service restarts and the summary. The lock is beside the resolved binary
directory: `~/.local/bin.kit-install.lock` by default, or `<KIT_BIN_DIR>.kit-install.lock`.
Overlapping runs targeting that directory fail immediately with the lock path and
holder PID, without stashing, pulling, touching the receipt or installing anything.
Let the holder finish, then retry the same command. Do not delete or replace the
lock file: doing so permits separate writers. If the lock path or a `KIT_BIN_DIR`
alias is inside the Git checkout, use a `KIT_BIN_DIR` outside the checkout or run
with `--no-pull` so Git cannot stash or replace the lock or its alias. The kernel
releases the lock when the installer and any child holding a copy of its lock
descriptor have closed it, including after a crash. The persistent file and its
old PID alone are not a live lock; only a successful acquisition replaces the
old PID. Dry-run and list take no lock and write no receipt. For
unpacked releases and runs with automatic checkout preparation disabled, menu
cancellation also takes no lock and writes no receipt. This serializes suite
installers for the same binary directory, not unrelated manual host commands or
native updater ownership.

Output streams during each install step, including native prompts. By default
each component shows its heading, the host tool's own output, the result and its
time; commands that change the system (the Orbi CLI install and service restarts)
are shown too. Use `--verbose` (or `--dry-run`) to also print each step's contract
and every helper command, all service decisions and completed Orbi deployment steps.
The default summary's `services` row drops routine notes (skipped units, inputs
with no active consumer); holds, restarts and failures stay verbatim, and it reads
`no restarts needed` when nothing else applies.
`--quiet` shows summaries and failure diagnostics, while leaving native output
visible when input is a terminal. The failure
transcript in quiet mode is limited to its last 16,384 characters. Colors are
automatic on terminals (`NO_COLOR=1` or `TERM=dumb` disables them); use
`--color always`, `--color never`, or `--color auto` to override. Each summary
reports installed, planned, skipped and failed components with total elapsed
time. A failed command or marketplace qualification refusal stops that component,
continues independent components, and causes a nonzero exit. A source mismatch
or stale legacy registration is not treated as installation success.
Non-JSON or truncated output gets a bounded diagnostic fallback. Successful
components remain installed; retry a failed one with `./install.sh --only ITEM`.

Both entrypoints check and apply available updates on every run under existing source/pin policies.
Successful refresh is separate from effective installed change. The installer compares installed
identity/revision, executable and payload bytes, modes, symlink targets and relevant settings.
Timestamps, updater success messages and checkout HEAD alone are not change evidence.
Installed evidence is captured before automatic stash/pull and carried across installer re-execution,
so source-linked packages retain their original baseline. This may inspect candidate hosts before
menu selection; only the final selection can update payloads or request restarts.
Outside the [Orbi fleet refresh](#orbi-cli), an unchanged repeat with no pending restart work
requests no service restarts. Only complete changed payloads are eligible for this
consumer restart pass; it affects supported host integrations only.
On Linux user systemd, active `kit-*` units
must reference the affected executable or configuration input before one `try-restart` is requested.
The prefix alone proves no ownership. This consumer restart pass leaves stopped, paused, unrelated and Orbi deployment units untouched; Orbi has its own [fleet refresh](#orbi-cli).
A tx-only change without a proven active consumer restarts nothing. Unknown installed inputs or
unit references are held with the named input/service and an inspection/retry action, not reported as unchanged.
Hosts without Linux user systemd report restarts unavailable. Restart failures make installation fail.
The installer saves observed changes beside its lock before moving on to the next component. If it is
interrupted or a restart fails, fix the reported problem and rerun with the same selection. The installer
rechecks the affected consumers even if the refreshed payload is now unchanged. Unverified unit references leave restart work pending. The installer records successful restarts even if a later
restart is interrupted, so retries can skip those units for the same payload. Once the restart work is
complete, an unchanged repeat requests no restart. A failed payload holds its consumer while
independent successful changes remain eligible.

Preview/list/menu cancellation perform no updates or restarts. Existing
machine-readable `item`, `status` and `exit` fields remain; additive change evidence
and a separate service decision explain checks versus activation.

`--dry-run` prints selected commands without installing. Host security and
dependency prompts still apply; full mode does not supply consent flags.

Every install and every `update` refresh an already registered Pi package with
`pi-bolt update`; a registration whose directory is missing is installed instead. A
complete-looking skill folder set is not proof of current content, so a kept package
is never an option: an edited or removed skill in the installed checkout reaches Pi
on the next run, and a skill folder a release added (for example `orbi`) appears with
its `/skill:<name>` and command. The reason line names what is out of date — an
update request, a missing skill folder, or the ordinary refresh. A refresh that
cannot reach the source fails the Pi item with its cause and a nonzero exit, and the
next install retries it. An unreadable package directory is not reported as
incomplete by the post-refresh check. Empty package filters are still reconciled so
skills and commands remain enabled. `./install.sh --only pi` does the same for one
component.

After Pi-Bolt reports success, Kit reads the package registration again and checks for
every shipped skill folder. Missing registration or skills makes installation fail
before package filters are changed. For example, `PI_OFFLINE=1` can make Pi-Bolt skip
updates with exit code zero; Kit reports the incomplete result and the retry action.

<a id="pi-harness-bootstrap"></a>

### Kit Pi package through Pi-Bolt

Pi-Bolt is the only Pi harness Kit installs. `./install.sh --only pi-bolt,pi`
bootstraps or refreshes Pi-Bolt first, then installs and enables Kit through it.
The `pi` key remains the package component for menu, `--only` and `--skip`
compatibility. `./install.sh --only pi` requires an already usable destination
`pi-bolt`; it does not install a harness itself. `--full --skip pi` continues
to refresh other components without installing or updating the Pi package.

Only the absolute `pi-bolt` in the Kit binary directory (`~/.local/bin`, or
`KIT_BIN_DIR`) is verified with `--version` and used for `list`,
`install git:github.com/TrebuchetDynamics/kit` or
`update git:github.com/TrebuchetDynamics/kit`. No `pi` or alternate `pi-bolt` on PATH
is used. A missing, non-executable, broken or unverifiable destination fails with
`./install.sh --only pi-bolt,pi` as the repair command, without any package download.
The package and native executable items share Pi-Bolt's supported platforms.

An existing stock Pi is never executed, removed or updated by Kit. It shares
`~/.pi/agent`, so it sees the refreshed Kit package too. The existing package settings
step clears only empty Kit filters after successful package verification, preserving
nonempty filters and unrelated settings. No sessions or credentials are changed.

Package commands have a ten-minute limit; destination version checks have a
30-second limit. A command timeout stops its descendants and reports failure.
Package failures report the cause and return nonzero; independent selected components
continue. Repair the cause and retry `./install.sh --only pi`. Completed upstream
changes are not rolled back. Preview/list execute no Pi command or download and write no receipt.
Menu cancellation performs no package refresh or download; pre-pull installed-evidence reads may run
before selection. The suite restarts only proven active consumers of changed
package content or effective settings; no agent/model is started by the package step.

Offline tests exercise isolated homes and fake upstream/package responses, not a
real upstream installation, package refresh, model run or live skill discovery.

### Pi-Bolt native executable

Default/full/menu and `update` include `pi-bolt`. Use `./install.sh --only pi-bolt`
to install it alone or `--skip pi-bolt` to leave it untouched. Every install and
`update` checks freshness before downloading the bootstrap script for an existing
installation. Kit uses HTTPS GitHub release metadata: stable `releases/latest`,
`releases/tags/<PIBOLT_VERSION>` for an explicit tag, or the highest numeric
`bolt-vX.Y.Z` tag among the first 30 releases for upstream's beta selection.
The lookup has a 10-second connection timeout, a 30-second transfer limit, and
at most five HTTPS-only redirects. A transfer rate cap also bounds downloads
when older curl versions do not know the response size upfront. Kit rejects
responses larger than 1 MiB for a single release or 8 MiB for the beta list,
which includes assets for each release.
Preview performs no live lookup.

A current result requires the **Pi-Bolt version inside the banner**, not the
leading Pi version, plus a healthy build manifest/assets, the requested
platform/variant and install root, effective channel, and the selected Kit BIN
symlink to the expected upstream command. A proven match leaves the payload and
links untouched and runs no bootstrap, archive download or installer shell.
`PIBOLT_VERSION`, `PIBOLT_CHANNEL`, `PIBOLT_VARIANT` and `PIBOLT_INSTALL` retain
upstream meanings; default x86-64 selection follows upstream's AVX2/libc rules.
With no channel override, upstream selects the latest stable release for this
install but preserves any stored beta channel for future `pi-bolt update` calls;
an explicit channel override must match the stored channel to skip installation.
Special modes (including Termux, mirrors, `PIBOLT_NO_PATH=1` and explicit Paseo
registration) use the official installer directly. Missing, stale, broken, locally
compiled or otherwise unproven builds use the official install/repair path. A failed or malformed
release lookup for an existing installation reports `Pi-Bolt release check failed`,
preserves it without reinstalling, and asks to retry `./install.sh --only pi-bolt`.
This is a failed check, not an unchanged success. Pi package freshness/skill repairs
and other suite components' native checks still run independently.

Kit downloads the [official installer](https://pi-bolt.opensec.in/install.sh) into a
private temporary file with HTTPS-only redirects, five redirects at most, a 15-second
connection timeout, a 300-second transfer limit and a 1 MiB size limit, then runs
the published file unmodified with `sh`. The run cannot prompt and installs no
optional extensions (`PIBOLT_YES=1`, `PIBOLT_EXTENSIONS=no`). `PIBOLT_BIN_DIR` is
the Kit binary directory (`~/.local/bin`, or `KIT_BIN_DIR`); the payload keeps
upstream's `~/.pi-bolt` default (or `PIBOLT_INSTALL` override). Kit verifies the linked `pi-bolt --version` and
never writes through a broken link. Upstream owns release selection, channel,
signature and checksum verification, and `pi-bolt update`; Kit pins no version and
edits no shell profile. An upstream failure can leave a partial installation: no
rollback is claimed or performed.

Supported targets are GNU/Linux x86-64 or ARM64 (glibc or musl, including Termux)
and macOS on Apple silicon. Other platforms are skipped by default and fail when
explicitly requested with `--only pi-bolt`. Pi-Bolt reads the same `~/.pi/agent`
configuration and Pi packages as Pi, so the installed Kit package serves both.

### Orbi CLI

Plain `./install.sh`, full, menu selection, `--only orbi`, and `update` all use
the same Orbi behavior when selected. Use `--skip orbi` to leave Orbi untouched.
`--list` and `--dry-run` do not change units or engines.

On Linux, selecting Orbi authorizes stopping, updating and restarting all
verified deployments on the local systemd host, **including deliberately
paused deployments**, even if the engine is already current. No approval record
or prompt is required. The installer inventories installed and loaded units and
queued jobs in the system and user managers, including other local accounts with
unit evidence. Remote machines, containers and separate namespaces are outside
that inventory. If a local account's user unit folders cannot be listed due to
permissions, the installer leaves it unchecked only if there is no runtime
entry for its UID, the linger directory can be listed and has no marker for the
account, and no readable unit evidence names Orbi. The Orbi receipt records only
the unchecked account names, and the final Orbi summary line lists them as
`not checked: <accounts> (home unreadable, no running manager, no linger)`.
This skip does not fail the refresh. Unverified
coverage for other accounts, inaccessible managers, ambiguous unit/config/owner
bindings or missing noninteractive write access hold the entire Orbi fleet
before any stop.

Each manager may list up to 2048 installed or loaded services and timers. The
installer checks only units whose manager-reported command, environment,
working directory or unit paths mention Orbi; it does not parse unrelated unit
files. At most 256 Orbi units per manager are checked in detail. A drop-in is
treated as an override, except a root-owned vendor file in
`/usr/lib/systemd/{system,user}/service.d/` that only sets
`TimeoutStopFailureMode` or `TimeoutStartFailureMode` in `[Service]`, such as
Fedora's `10-timeout-abort.conf`.

The deployment file and engine execution owner must match the installing account;
Kit does not switch users or invoke sudo. During inventory, it removes group/other
write bits only from the installing account's own regular Orbi service and timer
templates in its user unit directory, without changing their contents. The Orbi
receipt lists each changed path in `repaired_unit_fragments`, even if a later check
holds the fleet. Other writable fragments still hold the refresh; verify their
binding and owner before applying the reported permission fix. The installer checks
the current exact engine pin and runs `orbi check` before any stop, then validates
the new pin and runs the check again before activation.

It disables/stops verified triggers and cancels owned queued starts before stopping
owned services through systemd, without a natural-drain wait. After proving fleet
quiescence, it syncs each deployment once, locks the newest official stable release
as an exact commit, and runs `orbi check` before activation. It reads back enabled,
active scheduling separately from requested service starts. No new deployment,
unit topology, credential setup or bare Orbi tick is part of the refresh.

The Orbi stage shows one row per successful deployment: the configured repository
name, result, and configured slot count. Pass `--verbose` to see the completed
steps as well. A hold or failure always shows the available completed steps and
failure location. The final Orbi line reports counts and unchecked accounts,
without repeating the deployment rows.

Only installed deployment configs (under Orbi's data and config folders, or
`ORBI_CONFIG`) can hold the fleet. An `orbi.toml` in the directory you run the
installer from that no installed service uses, such as a copied template, is
reported as ignored. The refresh removes group and other write permission from
your own unit templates and from your own `~/.local/bin/orbi` executable (uv
creates it group-writable under the common `002` umask) instead of holding.
Unchecked system accounts below the login UID range are counted, not named.

On a partial failure, the installer exits nonzero but continues independent
components. Inspect the named config and manager-qualified units in the Orbi
receipt, repair the failed step and deliberately re-evaluate the fleet with
`./install.sh --only orbi`. A failed refresh may leave deployments stopped or
partly updated. It is not a rollback. A deployment that a failed refresh left on
the release tag it was applying (for example after a transient fetch failure)
is resumed by the next run rather than held. Deployments the refresh never
touched are counted in one line; `--verbose` lists them. On macOS, the installer never mutates launchd
or claims a deployment update; existing deployments or unverifiable coverage are
reported as held. Offline verification does not qualify this behavior on a live host.

After a completed refresh, or on a verified host with no installed deployment
(CLI-only), the installer brings the `orbi` CLI to the newest official stable
release of [orbi-build/orbi](https://github.com/orbi-build/orbi). It resolves the
release on every run with the same tag rule as the fleet refresh, so no Orbi
version is pinned in Kit. A missing CLI, or one reporting another version, is
installed from that release's exact commit:

```sh
uv tool install --force --python 3.14 git+https://github.com/orbi-build/orbi.git@<release commit>
```

This uses the immutable Git revision, not the upstream shell installer or PyPI,
and the installed CLI must report the release's version. A CLI already on that
release is kept. An editable uv install, which is how deployments install the CLI,
is kept because it follows its checkout, which the refresh moves to the newest release.
When an older CLI earlier on PATH is not the one replaced, the result says so.
A held or failed refresh leaves the CLI untouched.
Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) first;
uv provisions the compatible Python. A missing prerequisite, an unresolvable release
or a failed install fails this component with a diagnostic; other components
continue. Kit does not bootstrap uv or Git.

The executable defaults to `~/.local/bin/orbi` (or `KIT_BIN_DIR`);
`UV_TOOL_BIN_DIR` takes precedence and `UV_TOOL_DIR` retains uv's normal meaning.
Add the selected binary directory to PATH yourself; Kit does not edit shell profiles.
The installer verifies `orbi --version`, including a user-local CLI not yet on PATH.
List/preview do not execute uv or Orbi. A broken existing launcher is reported,
not overwritten; repair it using its deployment's supported procedure.

CLI installation does not call `orbi setup`, `install-units`, a bare tick or a
scheduler mutation.
See [GitHub-native setup](github-native.md#one-repository-per-deployment).

### Removed runner installation

There is no private runner bootstrap. Existing
private Pi directories, credentials, task data and recovery state must not be
removed as package cleanup. They are not shared with Orbi automatically. See
[cutover and qualification](github-native.md#cutover).

## Migrate from the retired executor

Kit planning publishes GitHub Issues for Orbi. Preserve existing task data,
attempts, worktrees and recovery evidence.

Existing jobs, IDs, schedules, pause state, execution history and private
state are preserved. Do not rewire legacy executor jobs or create new timers as
part of a Kit update. The task/executor migration helper is removed; reconcile
unfinished work through [GitHub migration](github-native.md#cutover).
Kit does not schedule or revive the removed executor.
