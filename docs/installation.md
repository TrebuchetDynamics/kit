# Installation and profile effects

> **GitHub-native delivery:** GitHub Issues own executable work; Orbi owns delivery.
> Preserve existing task data, attempts, worktrees and
> recovery evidence. Orbi remains paused and live-unqualified; see
> [setup and migration](github-native.md).

Source: [setup orchestrator](../scripts/setup_bundle.py), [source installer](../install-plugins.sh),
[profile defaults](../scripts/runtime_defaults.py), [native skill provisioning](../scripts/install_skills.py).

The native setup bodies live in [`src/kit_runtime/install/`](../src/kit_runtime/install/).
Their Python entrypoints live in `scripts/`, including `scripts/setup_bundle.py`
and `scripts/install-graphify.py`. Only `__init__.py` stays at the repository root:
Hermes requires that adapter beside `plugin.yaml` to load the plugin.
Keep the entrypoints, same-release `src/kit_bootstrap.py` and `src/kit_runtime/`
payload together; a single copied
installer is not standalone. Preflight rejects missing declared source payloads
before installation stages. This layout does not change setup targets or policy.

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
For example, `/update-kit --only pi,tx` narrows outer components. A restriction that
still selects Hermes while excluding another component is refused before mutation:
Hermes can run a nested **broader full-suite** refresh. Exclude Hermes (for example
`--only pi,tx` or `--skip hermes`) or separately authorize unrestricted full-suite
behavior. Outer flags do not constrain nested updates. Menu selection is not supported
by the updater; use explicit flags. No-restarts requests are refused before mutation;
`--no-reload` defers Hermes setup wiring, not other affected-host restarts.

Read-only/questions-only/`--dry-run` (also `--list`) shows intended source path/argv
with unavailable facts `NOT_CHECKED`. It does not clone, fetch, create directories
or locks, probe hosts or write caches. Resolve the helper from the loaded skill,
not cwd; direct invocation is `python3 -B <loaded-skill>/scripts/update_kit.py --dry-run`.

The helper serializes update-kit invocations through installation. This is **not**
a global/native Hermes lock: preexisting live/unknown consumers and concurrent
native ownership hold. Resolve native ownership receipts and wait for idle owners
before retrying. It conservatively checks source open files/processes, linked Hermes
gateway receipts and native updater locks; scan uncertainty also holds. A fresh
clone is staged in a unique sibling; failures retain that directory for diagnosis.
Existing source requires updater provenance, same-user ownership, non-symlink safe
paths, fixed origin, clean attached `main`, no extra worktrees and no local-ahead or
diverged history. Repair holds manually while preserving source, edits, history and
evidence; the helper never resets, stashes, cleans, forces, repins or deletes it.

It fetches only fixed upstream and fast-forwards `main`, then invokes that fetched
checkout's `bash install.sh update --no-pull` once, including equal-SHA reinstalls.
`--no-pull` suppresses only the outer installer pull; unrestricted Hermes native
updates may fetch source and launch another full-suite refresh. The receipt reports
old, helper-selected and final SHA, explicitly noting secondary changes. It does
not promise a single immutable revision across nested updates. Installer output
owns component outcomes; nonzero/partial failure propagates and successful host
items remain installed, not rolled back. Repair the reported cause and retry only
compatible selected failures. Reload/reopen the current agent session for discovery;
package refresh does not reload a running agent. Installation, activation and live
qualification remain separate, and Orbi stays paused.

## Full suite from a checkout

`./install.sh` installs the full suite for every available host with verbose output.
Use `--menu` when you want to select components interactively:

```sh
./install.sh
./install.sh --menu
./install.sh --dry-run
./install.sh --only codex
```

The suite includes the Pi package, the Pi-Bolt native executable, the Orbi CLI,
the `tx` launcher, Hermes fleet setup, and Claude Code and Codex plugins
with their complete portable skill suites, including [bundled Ponytail](cross-host.md#bundled-ponytail-on-every-host).
All Kit skills apply its shared method within their existing authority; no
separate Ponytail plugin, hooks or persistent modes are installed. Existing external
Ponytail installs are not changed or removed. `--full` (`--all`) is the default; `--skip` excludes components. Host CLIs
for Hermes, Claude Code and Codex must already be installed: full mode reports missing hosts as skipped, while
`--only` reports a requested missing host as failed. Pi-Bolt is installed first;
the `pi` item requires that destination executable to install Kit. Hermes is optional. A simple
shell launcher whose target is missing or not executable also counts as unavailable;
full mode skips it without running Hermes setup. Fresh portable installs use Claude marketplace `kit` and Codex marketplace
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
as `NOT_CHECKED`, with planned validation. Hermes also needs a Hermes
home (`~/.hermes`, or `--hermes-home`/`HERMES_HOME`); a default home that does not
exist yet counts as missing. The tmux launcher needs `tmux`.
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

Non-preview suite runs take a nonblocking advisory lock before writing the private
installer receipt or running any component, and hold it through service restarts
and the summary. The lock is beside the resolved binary directory:
`~/.local/bin.kit-install.lock` by default, or `<KIT_BIN_DIR>.kit-install.lock`.
Overlapping runs targeting that directory fail immediately with the lock path and
holder PID, without touching the receipt or installing anything. Let the holder
finish, then retry the same command. Do not delete or replace the lock file to
bypass a refusal: doing so permits separate writers. The kernel releases the lock
when the installer exits, including after a crash; the persistent file and its old
PID alone are not a live lock. Retry normally after confirming the old installer
and any child host commands have ended; only a successful lock acquisition replaces
old PID metadata. Dry-run, list and menu preview/cancellation take no lock and
create no receipt or lock file. This serializes suite installers for the same
binary directory, not unrelated manual host commands or native updater ownership.

Output streams during each install step, including native prompts. Verbose output
is on by default (`--verbose`) and shows shell-quoted commands; `--quiet` shows summaries and failure diagnostics,
while leaving native output visible when input is a terminal. The failure
transcript in quiet mode is limited to its last 16,384 characters. Colors are
automatic on terminals (`NO_COLOR=1` or `TERM=dumb` disables them); use
`--color always`, `--color never`, or `--color auto` to override. Each summary
reports installed, planned, skipped and failed components with total elapsed
time. A failed command or marketplace qualification refusal stops that component,
continues independent components, and causes a nonzero exit. A source mismatch
or stale legacy registration is not treated as installation success.
For a structured updater receipt, the summary includes its status, cause (including
per-profile recovery errors) and supported next action, rather than its closing
JSON brace. Non-JSON or truncated output gets a bounded diagnostic fallback.
Successful components remain installed; retry just Hermes with
`./install.sh --only hermes` (and the same `--hermes-home` if supplied).

Both entrypoints check and apply available updates on every run under existing source/pin policies.
Successful refresh is separate from effective installed change. The installer compares installed
identity/revision, executable and payload bytes, modes, symlink targets and relevant settings.
Timestamps, updater success messages and checkout HEAD alone are not change evidence.
Installed evidence is captured before automatic stash/pull and carried across installer re-execution,
so source-linked packages retain their original baseline. This may inspect candidate hosts before
menu selection; only the final selection can update payloads or request restarts.
A healthy unchanged repeat requests no service restarts, including nested host refreshes.

Only complete changed payloads are eligible. Restarts affect supported host integrations only.
On Linux user systemd, active `kit-*` units
must reference the affected executable or configuration input before one `try-restart` is requested.
The prefix alone proves no ownership. This consumer restart pass leaves stopped, paused, unrelated and Orbi deployment units untouched; Orbi has its own [fleet refresh](#orbi-cli).
A tx-only change without a proven active consumer restarts nothing. Unknown installed inputs or
unit references are held with the named input/service and an inspection/retry action, not reported as unchanged.
Hosts without Linux user systemd report restarts unavailable. Restart failures make installation fail.
A failed payload holds its consumer while independent successful changes remain eligible.

Hermes owns gateway disposition on both setup and installed-update paths. Its native
`gateway_restart` fields (including `deferred`, `pending` and `not_needed`) reach the outer receipt;
the suite never overrides them with `try-restart`. Setup owns profile wiring and requests no process restart.
Nested host refreshes return content evidence to the outer installer, which deduplicates by unit.
The outer installer also retains host evidence before native Hermes apply can change shared source,
including when `--no-pull` is set or only Hermes is selected.
The inherited installer lock keeps that nested work under the same writer without admitting a second installer.
Preview/list/menu cancellation perform no updates or restarts. `--no-reload` defers Hermes setup wiring,
not other affected-host restarts. Existing machine-readable `item`, `status` and `exit` fields remain;
additive change evidence, native gateway fields and a separate service decision explain checks versus activation.

`--dry-run` prints selected commands without installing. `--hermes-home`,
`--bundle-only`, `--no-reload` and `--yes-deps` apply only to Hermes. When a
profile already has its own plugin clone, Hermes is updated with `scripts/update_bundle.py`,
which supports none of those three and can restart gateways on ordinary updates, so passing one fails the
Hermes item instead of being ignored. Host security and dependency prompts still
apply; full mode does not supply consent flags.

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
`pi-bolt`; it does not install a harness itself. `--full --skip hermes,pi` continues
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
`update` runs the upstream installer again: a present `pi-bolt` is refreshed rather
than kept, so a stale native build never survives an install.

Kit downloads the [official installer](https://pi-bolt.opensec.in/install.sh) into a
private temporary file with HTTPS-only redirects, five redirects at most, a 15-second
connection timeout, a 300-second transfer limit and a 1 MiB size limit, then runs
the published file unmodified with `sh`. The run cannot prompt and installs no
optional extensions (`PIBOLT_YES=1`, `PIBOLT_EXTENSIONS=no`). `PIBOLT_BIN_DIR` is
the Kit binary directory (`~/.local/bin`, or `KIT_BIN_DIR`); the payload keeps
upstream's `~/.pi-bolt` default. Kit verifies the linked `pi-bolt --version` and
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
the same Orbi behavior when selected. A delegated installer (for example, the
Hermes suite refresh) inherits it. Use `--skip orbi` to leave Orbi untouched,
including in delegated refreshes. When both the top-level installer and a
delegate would select Orbi, the top-level installer runs the refresh once.
`--list` and `--dry-run` do not change units or engines.

On Linux, selecting Orbi authorizes stopping, updating and restarting all
verified deployments on the local systemd host, **including deliberately
paused deployments**, even if the engine is already current. No approval record
or prompt is required. The installer inventories installed and loaded units and
queued jobs in the system and user managers, including other local accounts with
unit evidence. Remote machines, containers and separate namespaces are outside
that inventory. Inaccessible managers, ambiguous unit/config/owner bindings or
missing noninteractive write access hold the entire Orbi fleet before any stop.
The deployment file and engine execution owner must match the installing account;
Kit does not switch users, invoke sudo or make access changes. The installer
checks the current exact engine pin and runs `orbi check` before any stop, then
validates the new pin and runs the check again before activation.

It disables/stops verified triggers and cancels owned queued starts before stopping
owned services through systemd, without a natural-drain wait. After proving fleet
quiescence, it syncs each deployment once, locks the newest official stable release
as an exact commit, and runs `orbi check` before activation. It reads back enabled,
active scheduling separately from requested service starts. No new deployment,
unit topology, credential setup or bare Orbi tick is part of the refresh.

On a partial failure, the installer exits nonzero but continues independent
components. Inspect the named config and manager-qualified units in the Orbi
receipt, repair the failed step and deliberately re-evaluate the fleet with
`./install.sh --only orbi`. A failed refresh may leave deployments stopped or
partly updated. It is not a rollback. On macOS, the installer never mutates launchd
or claims a deployment update; existing deployments or unverifiable coverage are
reported as held. Offline verification does not qualify this behavior on a live host.

On a verified host with no installed deployment, the component is CLI-only.
A missing CLI uses the [XelHaku/orbi fork](https://github.com/XelHaku/orbi) at commit
`1a8b2f9603f6258cb105293f238a8d3f775f3393`, which adds the host-only
`pi_executable` setting for Pi-compatible CLIs such as Pi-Bolt:

```sh
uv tool install --python 3.14 git+https://github.com/XelHaku/orbi.git@1a8b2f9603f6258cb105293f238a8d3f775f3393
```

This uses the immutable Git revision, not the upstream shell installer or PyPI.
Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) first;
uv provisions the compatible Python. A missing prerequisite or failed install
fails this component with a diagnostic; other components continue. Kit does not
bootstrap uv or Git, or force-reinstall a conflicting tool.

The executable defaults to `~/.local/bin/orbi` (or `KIT_BIN_DIR`);
`UV_TOOL_BIN_DIR` takes precedence and `UV_TOOL_DIR` retains uv's normal meaning.
Add the selected binary directory to PATH yourself; Kit does not edit shell profiles.
The installer verifies `orbi --version`, including a user-local CLI not yet on PATH.
List/preview do not execute uv or Orbi. A broken existing launcher is reported,
not overwritten; repair it using its deployment's supported procedure.

A working existing global CLI is kept, including on `install.sh update`.
The CLI pin is separate from deployment release pins; CLI bootstrap does not
call `orbi setup`, `install-units`, a bare tick or a scheduler mutation.
See [GitHub-native setup](github-native.md#one-repository-per-deployment).

### Removed runner installation

There is no private runner bootstrap. Existing
private Pi directories, credentials, task data and recovery state must not be
removed as package cleanup. They are not shared with Orbi automatically. See
[cutover and qualification](github-native.md#cutover).

## Install

Prerequisites: configured Hermes, Bash and Python 3.12+ with PyYAML, which setup and
update need to read `plugin.yaml` and profile policy. Install it with
the distribution `python3-yaml` package if you use the system interpreter, or in
the active virtual environment with `python3 -m pip install PyYAML`. Verify the
installer's interpreter with `python3 -c 'import yaml'`. If PyYAML is missing
during suite installer manifest discovery, Kit warns before changing the plugin
and still reports the Hermes component as failed.
Full setup also needs Git and `uv` when `graphify` is not already installed. Setup
now checks these prerequisites before starting installation stages; later runtime
failures can still leave partial setup.
See [compatibility](testing.md#compatibility) for the verified environment.

Setup is broader than installing this plugin: the current source inventory targets
all profiles for Graphify and speech support. Existing memory providers, store
bindings and capture policies are preserved. Kit does not provision external memory.

```sh
hermes plugins install TrebuchetDynamics/kit
hermes plugins enable kit
hermes kit setup --yes-deps
hermes kit doctor
```

This Hermes install fetches Git source from `TrebuchetDynamics/kit`, not an npm
release. The package name `@trebuchet/kit` does not establish npm publication;
creating an npm scope is not a prerequisite for Git-source verification.

From a local checkout, one command performs the complete installation for every
existing live profile:

```sh
bash install-plugins.sh --yes-deps
```

The Hermes item in `install.sh`, `install-plugins.sh`, and `hermes kit setup`
share the same complete setup path: bundled skills, plugin installation/enablement, profile
configuration, per-profile readiness checks, and running-gateway command
refresh. No manual symlinks or per-profile enable commands are needed. Use
`--dry-run` to preview, `--bundle-only` to install only this bundle and its native
skills, or `--no-reload` to explicitly defer gateway wiring. Dependency consent
and native security scans still apply; a blocked dependency or failed readiness
check returns nonzero and reports setup as incomplete.

Fresh native/source installs and isolated registration probes use `plugins/kit`
and enable `kit`; setup finalizes through `hermes -p PROFILE kit finalize`.
Source setup requires the `timeout` executable and bounds each Kit enablement to
120 seconds; a timeout reports incomplete setup, not successful activation.
Duplicate or foreign registrations require ownership reconciliation, not a second installation.

Registrations are checked before setup mutates components. Duplicate registrations refuse,
even if they resolve to the same source; missing/malformed manifests and foreign
sources also hold with path/source diagnostics. Preserve both paths and private
state, reconcile the reported registration/ownership with its owner, then repeat
the preview. No runtime directory move or purge is needed. Expected source-install
symlinks remain supported; other existing safety checks still apply. `--dry-run`
performs no installation, enablement or reload.

Plugins are enabled per profile. For a named profile, use that profile's home for
the link and `hermes -p PROFILE plugins enable kit` to enable it.
`hermes kit setup` installs and enables the sources in
[plugins/PLUGINS.md](../plugins/PLUGINS.md), including any external skill repositories
it lists (currently none), Graphify's Hermes integration and speech support. It also links and enables
Kit itself in every existing live profile, preserving existing plugin
installations. After creating another profile, rerun setup or, from this checkout,
run `bash install-plugins.sh --bundle-only` to add just this bundle and its defaults
across profiles. The links depend on keeping this checkout installed. It applies
[our defaults](../plugins/defaults.json): toolset gateway injection plus the
`interactive` runtime policy. A fresh profile receives `approvals.mode: manual`,
destructive-slash and MCP-reload confirmations enabled, and `agent.max_turns: 90`.
Without an explicit policy setting, existing approval and turn values are preserved;
only missing values receive interactive defaults. Installing or updating never
silently selects autonomous policy for an existing profile.

To explicitly select a policy for one profile, set
`plugins.entries.kit.settings.runtime_policy` to `interactive` or `autonomous`.
An explicit policy reapplies its approval and turn values on every plugin load.
`autonomous` sets `approvals.mode: off`, disables destructive-slash (`/new`, `/clear`,
`/reset`, `/undo`) and MCP-reload confirmations, and sets `agent.max_turns: unlimited`.
It disables terminal command approval prompts in CLI and messaging sessions.
For example, **only for a profile you intend to run unattended**:

```sh
hermes -p PROFILE config set plugins.entries.kit.settings.runtime_policy autonomous
```

Plugin loading also sets Telegram command-menu priority and installs the bundle's
managed cron helper script. No setup command is needed after enabling the plugin.
Writes occur only when values differ. Other settings, including explicit deny rules,
are preserved; Hermes hard blocks and the runner's gates still apply. Your own
`skills.disabled` entries stay, except that the bundle enables its own skills.
External skill catalogs and memory providers are not managed. Setup also clears
per-platform skill disable lists.

To opt out of automatic policy application, first run
`hermes -p PROFILE config set plugins.entries.kit.settings.apply_runtime_defaults false`,
then restore desired values. The opt-out takes precedence over either policy:
it writes no approval, turn, gateway-injection or skill-list policy, but still
maintains the bundle's Telegram menu entries. It does not undo earlier changes.

Setup, including `--bundle-only`, honors the same opt-out: it skips the approval,
gateway-injection and skill-disable-list settings for that profile and says so in
its preview.
Full setup checks every profile and refreshes live commands.
Native plugin loading provisions missing bundled skills, so full setup is not
required for the core questions-only interview. Use setup for external integrations
and fleet-wide provisioning; native installation does not perform
those steps. Saving interview decisions through docs-sync additionally requires
the relevant file/terminal tools. Direct source evidence is sufficient for routine
task and document repairs; Graphify is useful for uncertain cross-component
relationships, or required when the request explicitly calls for it.
Use `hermes kit setup --dry-run` to preview target profiles.

### Verify a pre-rename profile

Before invoking Hermes (which can load plugins and write defaults), identify the
authorized profile and read its configuration without booting Hermes. Retain a
private baseline of its approvals mode, Telegram command-menu priority,
`apply_runtime_defaults` opt-out and explicit `runtime_policy`, including whether
each value is absent. Record the runner executable, state-directory location and
saved-job identities/statuses too; keep credentials and profile identities out of Git.

Install from clean Git source, record its revision, and load Kit in that same
profile. Compare the effective settings against the baseline. An opt-out must
remain effective, approval values must follow the selected policy, and custom menu
priorities must survive (Kit still adds current workflow entries and removes retired
bundle entries). Observe the migration warning and any writes under
`plugins.entries.kit`, then confirm the runner CLI, existing state directory and
saved jobs still resolve without recreating or resuming them. Preserve the legacy
entry during this comparison; removing it would hide the compatibility check.

Report isolated fixture/native-loader checks separately from live qualification.
A fixture, a Git-source install or a saved approval alone proves neither a live
profile migration nor npm publication. If the live profile or its pre-rename
baseline is unavailable, retain that qualification as pending rather than replacing
it with a newly invented profile.

## Preflight before fleet writes

Every complete setup starts with [read-only preflight](../scripts/setup_preflight.py).
It inventories all live profiles and prints planned skill copies, preserved
existing skills, plugin links, approval/gateway settings and memory effects.
Each profile's selected runtime policy and effective values are shown, including
preserved approval/turn values and opt-outs. Previews never change policy selections.
Unknown policy names fail before policy writes. `--dry-run` runs preflight only and
exits without installation stages.
Full previews contact Git source servers with bounded timeouts; core previews
need no dependency network access.

Checks include executable availability, the required Hermes skill/injection APIs,
strict YAML parsing (including duplicate keys), writable installation paths,
existing skill/plugin conflicts and source accessibility. Existing memory provider
selection does not block setup and is left unchanged.
Compatibility is inspected from local Hermes source without loading its plugins;
the configuration parser uses Hermes's managed Python and does not print config
values or parser excerpts that could contain credentials. Unrecognized runtime
layouts fail visibly instead of being assumed compatible.

A failed preflight exits nonzero before changing profile configuration, plugins,
skills or memory. This guarantee starts at the setup orchestrator: invoking it
through `hermes kit setup` may already have loaded the plugin and applied its
runtime defaults. Use `bash install-plugins.sh --dry-run` for a preview that does not boot
Hermes. The internal `--sources-only` adapter and standalone helper scripts are
not the complete setup entry point.

Preflight is not a transaction or a security-scan approval. Native scans still
run during dependency installation; rejection, package resolution failures,
network changes, concurrent edits and later runtime failures can leave partial
setup after preflight passes. No rollback is implied. Source reachability alone
does not certify a pinned version or a usable integration. Profiles linked to
another bundle checkout are blocked until that installation is explicitly
updated/removed, avoiding finalization through stale code.

## Bundled Grill Me

`skills/grill-me/SKILL.md` (version 2.1.1) adapts the MIT-licensed official
`official/software-development/grill-me` skill (version 2.0.0) with
mattpocock/skills grilling guidance, preserving their attribution. `/grill-me` (CLI)
and `/grill_me` (Telegram) remain typeable compatibility commands that run
`plan-with-me` in challenge mode with this skill as its reference; `/grill_me` is not
shown in the Telegram menu. Enabling/loading Kit installs missing bundled
skills and shared support files into that profile's native skill directory, using
the same offline provisioner as full setup. Existing flat and categorized skills
are preserved; an incomplete existing slot is never replaced and is logged as a
warning while the remaining skills and every command still register.
Ordinary plugin loading writes only inside the owning profile: its config,
`scripts/`, and missing bundled native skills and shared support under `skills/`.
It never installs network dependencies, changes sibling profiles, or
reloads a gateway. Full setup provisions native skills across all
profiles before external plugin setup.
Setup refreshes running gateway command handlers and checks their activation
receipts automatically. It does not send test messages or restart ongoing turns.
Existing sessions can retain prior tools, prompts and memory providers; those
changes apply to new sessions. A stopped gateway is reported as not running,
not as a tested messaging connection.

## Telegram setup

Enabling/loading Kit applies its gateway-injection setting in the
owning profile. There is no YAML wiring step. This lets a skill command queue an
agent turn in the chat where it was invoked. Full setup refreshes running gateway
commands and verifies activation receipts; `--no-reload` explicitly defers that.
Existing CLI chats must be reopened to receive a new plugin/tool inventory.

See [tested compatibility](testing.md#compatibility) for the recorded Hermes revision
and required plugin APIs. Hermes needs its normal model and Telegram
configuration; individual skills may require their own tools.


## Limits of the opt-out

The runtime-defaults opt-out covers plugin loading and setup's bundle policy
settings only. Full setup still installs external integrations, so do not use it
as a policy-preserving reinstall.
Back up configurations first and review [removal and recovery](uninstall.md).

Updating this page: reconcile changes to setup flags, profile discovery, runtime
policy writes and native provisioning against the source links above.

## Migrate from the retired executor

Kit planning publishes GitHub Issues for Orbi. Preserve existing task data,
attempts, worktrees and recovery evidence.

Existing jobs, IDs, schedules, pause state, execution history and private profile
state are preserved. Do not rewire legacy executor jobs or create new timers as
part of a Kit update. The task/executor migration helper is removed; reconcile
unfinished work through [GitHub migration](github-native.md#cutover).

## Update all profiles

Run terminal `hermes kit update` from an authorized profile. It waits for
the updater and prints a structured receipt with outcome, revisions, files, local
edits, settings, menus and gateway restart status. `hermes kit update --check`
fetches upstream and previews without advancing checkouts or writing profile skills/
configuration; it still writes Git fetch metadata and its receipt. There is no
chat-maintenance command or terminal update-status form.

Old profile payloads, including retired skills, need an authorized normal update
and host reload. Provisioning deliberately preserves existing copies: source deletion
or reinstall alone does not retire them. Updates remove retired first-party files,
including edited/categorized copies, while retaining backups and unrelated profile/
recovery data; an unchanged retry is a no-op.

After a changed all-profile update activates successfully, the updater also runs
that fetched release's `install.sh --full --skip hermes,pi -q` once from its updated
plugin checkout. This refreshes the remaining selected components through the
same supported installer used for initial setup, including `tx` and the
Claude Code/Codex plugins. It does not install the retired executor or TUI.
Hermes was just updated; Pi package updates are separate host maintenance,
not a responsibility of the removed runner. Missing host CLIs are skipped. No privilege escalation or consent flags
are supplied, and stdin is closed so background updates cannot wait for a person's
answer. Native host security/dependency requirements still apply.

Host refresh is best effort, with a five-minute limit for the whole installer run;
on timeout its process group is stopped. It never rolls back or fails a successful
Hermes update. The receipt's `hosts` list records `item`, `status` and `exit` for
`pi-bolt`, `tx`, `claude`, `codex` and `orbi`, and chat status adds one `Hosts:` line.
Completed items retain their outcomes if a later item times out; remaining items
report `timeout`. An unavailable installer reports `unavailable`; missing or invalid
item reports use the installer's failure exit, or `unreported` if it exited zero.
Skipped/unavailable/timed-out items have no item exit code (`null`). The installer
writes incremental JSONL progress to `KIT_INSTALL_REPORT` when that internal
environment variable is set; native output is not parsed as a receipt.

`--check`, scoped local deployments, and pin/unpin operations never run the host
installer. An `up_to_date` update skips it too: a no-op rerun does not retry failed
host items. To retry those independently, run `./install.sh --full --skip hermes,pi`
from the updated checkout. Existing user config, including `~/.tmux.conf`, is
preserved. Regular shell completions refresh with adjacent backups; command
replacements use the bounded state-directory backups described above.
Offline fixture checks exercise preview mode and a real `install.sh --only tx`
without contacting host services; they do not establish live plugin acceptance.

An update also self-heals each profile: plugin activation re-applies the bundle's
command menu, approval and gateway-injection settings, and finalize fails the
profile if they did not land (profiles that opted out of runtime defaults are not
checked). `settings_healed` lists profiles whose config changed.
An update that starts while a restart it requested is between gateways (the old one
gone, the new one `starting`) waits up to 5 minutes for the new one before activating
profiles, then finalizes any profile whose commands are not wired yet again after 15,
30 and 60 seconds, instead of reporting `incomplete`. A draining gateway still serves,
so an update then goes ahead and joins that restart.

Because Telegram menus refresh only when the gateway reconnects, an update that
changed code, skills or settings restarts the gateway once when every profile
activated cleanly and a gateway is running, but only while no chat or API turn is in
flight, so Hermes never has to force one. The updater reads Hermes' `active_agents`
from the root's `gateway_state.json` and subtracts cron runs (jobs holding a
`fire_claim`), which Hermes runs in restart-safe external workers; with several
recurring jobs a moment free of cron runs rarely comes, so they do not hold the
restart. When no chat turn is in flight it requests `hermes gateway restart` at once
(`gateway_restart: requested`). Otherwise, or when the gateway's activity cannot be
read (for example while it is starting or draining), it reports `deferred` with
`gateway_restart_waiting_on` and starts a detached waiter that checks every 30
seconds for up to 6 hours. The waiter restarts at the first quiet check and sets
the receipt to `requested`; if another restart loaded the update first it records
`reloaded`; if the gateway never went quiet it records `deferred_expired` with the
next step and restarts nothing. Cron schedules persist (a job mid-run during a
restart is marked `unknown` and not retried; its next tick runs normally).
Otherwise it reports `not_running`, or `not_needed` for a no-op or incomplete
activation. A later update can join an outstanding requested restart. It can join
an outstanding deferred restart only if its waiter watches the same running
gateway. If the deferred waiter watches a different gateway or has no recorded
gateway PID, the update makes its own restart decision. An update that joins
reports `pending`, so a burst of updates restarts the gateway once; that restart
loads the newest release, and its outcome reaches the latest receipt with
`gateway_restart_covers`, the number of updates it covers. The waiter never
restarts while an update is still applying files: it shares the update lock and
waits for the next check. The waiter records its outcome in the durable receipt;
a subsequent update also records a completed requested restart. `completed` includes `gateway_restart_result` (new gateway PID,
start time, observed menu resends and interruptions); `restart_failed` means the
old gateway still runs. `restart.json` retains the outcome. These receipt fields
are evidence, not a promise of the former chat summary. To restart immediately
anyway, run `hermes gateway restart` under your normal service authority;
Hermes then waits for chat turns up to `agent.restart_after_turn_timeout`. Drift,
error and check results carry no `gateway_restart` field. Only the gateway recorded
in the root's `gateway.pid` is detected and restarted; a separately running
named-profile gateway keeps its old menu until you restart it.

Telegram shows a chat's own command list ahead of the default, private and group
lists that Hermes refreshes, so a leftover chat-scoped list never updates. On an applied update (not check mode or drift), for each
profile bot token in that profile's `.env`, the update checks the chats in `TELEGRAM_ALLOWED_USERS` and
`TELEGRAM_HOME_CHANNEL` and deletes a chat-scoped list only when it still contains
a retired bundle command; that chat then uses the refreshed private or group list.
Chat lists without retired names are left alone. Each chat is checked
independently, so one failing chat does not stop the others. `chat_menus_healed`
reports cleared chats by their last four digits, plus any `failed` chats the
same way when only some chats fail; an unreachable Bot API is reported and never
fails the update.

`status` is the chat form handled by the plugin; it is not a positional argument
to the terminal command `hermes kit update`. Terminal update forms below wait
for completion. The durable result is stored at the Hermes installation root in
`maintenance/toolset-update/latest.json`; named profiles share that update status.

Terminal equivalents wait for completion:

```sh
hermes kit update --check
hermes kit update
```

Only one update or check runs at a time. A second one waits up to 10 seconds (a
deferred-restart waiter holds the lock only briefly per check), then exits with
code 3 and `{"status": "busy", "running": {...}}` naming the running update's PID,
mode (`update` or `check`) and start time; it changes nothing and leaves that
update's receipt in place.

A named-profile invocation still targets every existing live profile under the
same Hermes root. The updater fetches the official Kit `main` branch,
checks each distinct installed Git checkout, and normally accepts clean equal or
fast-forward revisions. A verified managed checkout with rewritten upstream history
can instead use [managed checkout recovery](#managed-checkout-recovery).
Dirty checkouts, unproven local commits, unsafe paths and skill
merge conflicts stop preflight before checkout/profile writes. Review and commit
or move local changes yourself; the updater never stashes, resets or force-pulls.
Non-Git plugin distributions need a supported Git installation before this update.

Bundled native skill copies are synchronized, including shared references and
upstream deletions of unmodified files. Every released skill file is reset to the
release byte for byte. A profile that edited its installed copy (Hermes' background
skill review rewrites them, agents add lessons there) gets the release; its old copy
is saved in the update's backup and listed under `local_edits` as `reset`, so port
any lesson that should reach every profile into the bundle. Kept edits used to block
every later release of that file. A copy whose bytes match that same path in trusted
upstream history (at most 100 path-changing commits, cached per checkout) is an
older release, refreshed without a report; history unavailable in a shallow checkout
is fetched first. Check mode reports the same `local_edits` without applying them.
A skill file removed from the bundle is deleted from profiles, together
with folders that leaves empty, even when the shared checkout had already advanced; an
edited copy goes too, saved in the backup and listed as `removed`. The update is
idempotent: a second run with no new release writes nothing, reports no local edits,
leaves no backup and needs no gateway restart.
An exact byte match establishes historical content, not whether someone intended
to pin it. There is no per-file pin setting in this updater: review intentional
pins before invoking an update, and retain them outside the managed copy if needed.
Missing bundle installations
are linked to the updated source. Native enablement loads the plugin and applies
its documented runtime defaults; per-profile bundle-only finalization verifies
registrations and refreshes gateway commands. Separate native checkouts remain
separate. It does not upgrade unrelated plugins, Hermes Agent or external imports.
Existing setup prerequisites still apply; this is not a policy-neutral operation.

`maintenance/toolset-update/latest.json` in the root Hermes home records status,
source revisions, profiles, reset or removed `local_edits` and the backup location.
Managed-checkout recovery has separate merge evidence; ordinary skill-copy reset
is not a three-way merge. Terminal updates print updater/setup output;
`run.log` holds requested gateway restart output;
per-run backups include original skill files and a manifest. An `incomplete` result
may follow partial application: preserve the backups, fix the reported cause and
rerun. There is no automatic rollback. A stopped gateway is reported by setup;
an unreachable live gateway is not treated as verified wiring.

Workers and schedules are not restarted or changed. Update between active tasks
after quiescing or reconciling running workers because runtime/helper files change.
Historical byte matching does not establish compatibility with an active run or
its pinned execution files, manifests or evidence; update receipts do not qualify
that compatibility. Existing conversations may
retain already-loaded instructions; open a new conversation to load updated skills.
Plugin registration and stale Telegram menus require the normal authorized
update/reload path; source changes alone do not refresh running hosts.

### Managed checkout recovery

A negative `merge-base --is-ancestor` result is not a Git failure. The updater
classifies it separately from actual Git/network failures and locally advanced
checkouts. A shallow checkout gets one trusted fetch with at most 1,000 additional
history levels; if negative ancestry remains shallow, recovery defers rather than
assuming a rewrite. Equal/fast-forward updates retain their normal path.

Automatic recovery requires a same-user standalone `plugins/kit` checkout,
the expected plugin identity, a native `plugins/.install-metadata.json` record
bound to the trusted upstream, and HEAD matching its saved installed revision or
a trusted tracking tip captured **before fetch**. A clean tree or matching URL
alone is insufficient. Dirty/untracked files, extra Git worktrees, shared object
stores, unknown provenance, an unselected profile link, a live gateway or a live/
unknown helper consumer prevent replacement. Quiesce consumers yourself and
reconcile the reported evidence; recovery never kills or restarts them.

The updater stages the exact trusted fetched main commit and reuses the scoped
native transaction below: all selected consumers are preflighted and scanned,
worker-handoff locks are held, the complete original checkout (including `.git`)
is moved into an owned backup, and native installation publishes the staged local
URI without force or enablement. When native admission uses the manifest-named Kit
slot, the verified candidate returns to the journaled physical slot before readiness;
interrupted publication retains its original backup and resumable evidence. Selected
links to that canonical checkout remain links; their source is recovered once. Additional native metadata fields and other
plugins' records are retained, and the bundle record keeps its trusted source
binding. New unselected consumers or foreign source/profile edits on retry defer
instead of becoming a new baseline.

Unlike ordinary release synchronization, **recovery three-way merges native skill
customizations against the original checkout**. Compatible edits and executable/
file permissions survive; conflicting edits or edited deletions defer without
resetting them. Original skill bytes and modes, source/base revisions and exact
merged output are retained in the transaction backup/manifest. Configuration,
runtime-policy opt-outs, credentials, jobs and paused schedules are not rewritten.
Recovery performs no profile finalization, gateway activation or host refresh.

`maintenance/toolset-update/recovery.json` journals per-profile phases and errors;
`latest.json` includes that recovery result. Native readiness alone does not complete
the run: originally selected independent fast-forward/profile writes also retain
frozen targets, original bytes/modes and resumable backups until their publication
reads back. A retry does not enlist new profiles or overwrite newer foreign edits.
Keep the referenced backup and staged source.
Rerun the same all-profile update, or `./install.sh --only hermes`, to resume
that original target and backup, even after upstream moves. An empty failed slot
can be restored from its original checkout; partial native output and newer foreign
edits are never deleted or overwritten to roll back. Read-back checks the exact
published HEAD, tracked bytes, profile output, permissions and source binding before
success. An unchanged retry validates the completed recovery without reinstalling,
rescanning, resetting preserved customizations or creating a new backup.

`python3 scripts/update_bundle.py --hermes-home /path/to/home --dry-run` only previews;
it performs no fetch, staging or state/profile writes. `--check` retains its
fetch/check semantics, but performs no recovery publication. Installer `--dry-run`
and `--skip hermes` never execute recovery. Offline real-Git fixtures cover recovery,
shared consumers, preservation, refusals and interrupted retry; they do not qualify
native scanner acceptance, a live profile reinstall or Telegram delivery.

### Linked profiles and pinned clones

A fresh source install links each profile's `plugins/kit` to the checkout; verified
legacy physical slots remain in place. Both names participate in shared-consumer
and live-use protections. The profile loads whatever that checkout holds at the next gateway restart,
including commits that were never released. A profile whose plugin is its own clone
changes only when an update advances it.
`hermes kit doctor --json` lists the linked profiles; nothing converts them
automatically.

To pin one profile, preview it, then run it:

```sh
hermes kit pin NAME --dry-run
hermes kit pin NAME
```

Pinning clones the checkout at the revision the link resolves to now, saves the
link under `maintenance/toolset-update/pinned/NAME-*/` and puts the clone in its
place, so the profile stays on the same revision. It refuses, writing nothing, when
the checkout has uncommitted changes (the profile would lose them on its next
restart), when that revision is not yet on upstream `main` as last fetched (the next
update could not advance the clone), or while an update runs. The gateway loads the
clone at its next restart. `hermes kit pin --unpin NAME` restores the
saved link and moves the clone beside it instead of deleting it; it also takes
`--dry-run`.

## Complete bundled skill installation

Native plugin loading provisions every bundled skill and its support files into
the selected profile, including Impeccable, Beautify GitHub README, Autoresearch,
Grill Me, Ponytail and the pinned engineering protocols. No separate hub installation
is needed for these skills.
Fleet setup provisions the same bundle across existing live profiles. Existing
local or categorized skill installations are preserved rather than overwritten.
Existing `shared/` support directories receive missing Markdown files only, with
atomic no-replace publication; local edits stay intact. A symlinked shared directory
is refused rather than written through. This also makes the new Ponytail method
available when installing over an older profile; use the normal updater to refresh
existing skill contents. If the old external Ponytail plugin owns a command, setup
and doctor require the corresponding `kit:ponytail-*` skill registration and
report it under `bundled_skill_fallbacks`; they do not treat the external command
as a Kit handler or remove it. Other foreign command collisions remain errors.
`hermes kit doctor --core` checks registration; full setup and full diagnostics
still apply to external integrations such as Graphify. This does not install
the entire public skill catalog or guarantee optional browser/service readiness.
Impeccable’s upstream launcher may download its versioned engine on first use
(or use an existing configured engine). The bundled snapshot does not contain
or attest that external binary; instruction loading has a documented fallback.

## Deploy an exact local revision to selected profiles

`hermes kit update` remains the all-profile upstream update. For an
already reviewed local fix, use the scoped updater from a clean checkout:

```bash
python3 scripts/update_bundle.py --hermes-home /path/to/hermes-home \
  --profile project-a --profile project-b \
  --source /path/to/reviewed-checkout --revision <full-40-character-commit> \
  --native-python /path/to/hermes-python --check
```

Remove `--check` to apply that exact selection and revision. All four local-mode
options are required; profile selectors never silently fall back to the fleet.
The source must be a clean standalone Git checkout at the supplied commit.
Local mode does not fetch, pull, advance the source checkout, expand the selection,
change enablement, reload gateways, restart workers or change schedules. Use the
Python interpreter from the installed Hermes environment, where `hermes_cli` and
its dependencies are importable; the Hermes source used for native admission is
resolved from the `hermes` on `PATH`. Missing native APIs fail closed.

Preflight holds the updater lock and checks tracked source closure, installed
checkout and skill drift and actual process references to the selected installation;
the worker handoff lock is taken before each profile is staged. Even `--check`
creates `maintenance/toolset-update/` and its lock file.
Historical Kanban cards, including missing, malformed, blocked or done records, are
not ownership leases or deployment vetoes and are not queried to establish safety.
Preserve actual active consumers and candidates; uncertain process/workspace ownership
still defers the affected deployment. Independent eligible selections continue.
Source symlinks and submodules are refused; selected installation links are supported.
The updater replaces only the selected plugin slot with an isolated checkout,
preserving shared source, other profiles' links and active runtimes.
Customized or ambiguous native skill copies defer deployment instead of merging
unreviewed content. Native registration is checked in a disposable home; this
proves the installed bundle registers there, not live gateway wiring or product
recovery. An existing process can retain loaded instructions until its ordinary
restart. The helper-launch lock coordinates this repository's launcher; it is not
an operating-system barrier against unrelated native/manual launches.

Each profile gets a staged Git checkout and its own native security scan. Staging
and linked-source snapshots are published atomically only after clone, pinned
checkout and closure checks finish; interrupted temporary clones are never reused. Scanning
disabled, a caution requiring confirmation, or a dangerous verdict stops that
profile before publication. There is no force option, scanner-approval cache or
inherited approval from another profile or revision. After scan admission and
fresh source/destination checks, the selected plugin slot is moved into its backup
and the native `plugins install` implementation installs the local staged URI at
the exact commit with force and enablement both false. Native manifest, kill-list,
security and dependency admission still apply. Missing dependency consent or any
native refusal is reported as incomplete; no dependency override is supplied.
The native manager owns any dependency-environment publication and its existing
runtime protection. The updater does not migrate or rewrite active cards.

`maintenance/toolset-update/scoped.json` records the local deployment separately
from the legacy updater receipt. Each run's backup directory retains a manifest,
original skill bytes, original plugin slot, and a Git snapshot of a previously
linked source. Successful profiles record installed SHA-256 hashes and the native
registration probe's commands. After a failure while the plugin slot is moved aside,
the original plugin is moved back if the slot is still empty; partial native output is preserved for inspection, never erased.
An interruption can leave plugin and skill publication at different phases.
Rerun the same command to resume the original source, selection, staging and
backup. A different revision/selection, including the same profiles in a different order,
is refused while that run is incomplete.

If the original source is gone and **publication never began**, inspect the receipt
and its backup manifest, then cancel only that exact attempt:

```bash
sha256sum /path/to/hermes-home/maintenance/toolset-update/scoped.json
python3 scripts/update_bundle.py --hermes-home /path/to/hermes-home \
  --cancel-scoped <receipt-sha256> --check
# After inspecting the preview, repeat without --check.
```

Cancellation takes the updater lock, requires matching receipt/backup evidence,
and refuses any recorded publication phase (including `backed_up`), saved plugin
slot, malformed state or archive collision. It archives the original receipt
unchanged as `scoped-cancelled-<receipt-sha256>.json` beside the active journal;
all staging and backups remain. It does not require the vanished source, alter
profiles, restart services or accept a scanner caution. Retry a reviewed deployment
normally afterward; native admission still applies. Partially published attempts
must instead resume their original recovery path. Never delete their journal to
force another deployment.

Completed unchanged deployments perform no native installation or scan; drift is
still checked. Retain the run directory: native installation provenance points to its staged local
source, and its original backups support later reconciliation.
Offline tests use real Git repositories and fake native admission; they do not
establish live scanner acceptance, dependency admission, Telegram delivery or
original-task recovery.

## Scheduled self-repair

Kit does not schedule or revive the removed executor. Preserve existing per-profile
jobs and their paused state. Native Hermes maintenance helpers do not authorize
new delivery services or imply a live repair completed. Orbi remains paused until
separately qualified under [the cutover gates](github-native.md).
