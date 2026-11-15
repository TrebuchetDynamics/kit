# Orbi lifecycle reference

Branch-only detail for `/orbi`. The steps live in
[SKILL.md](../SKILL.md); this page explains the interface, discovery, isolation
and recovery a lifecycle operator needs. It restates neither the provider
contract nor the protection policy: read
[GitHub-native development](../../../docs/github-native.md) for those.

## Interface

```sh
python3 -B <loaded-skill>/scripts/orbi_control.py [status|setup|start|stop|help] \
  [--repo-dir PATH] [--config PATH] [--dry-run] [--json]
```

- Omitted action means `status`. A bare `orbi` runs one Runner tick and is never
  the lifecycle entry.
- `help` takes no repository, reads no deployment and is available on every
  platform. It is the only action that needs no deployment context; `status`
  still binds a repository and reports an absent deployment. Help accepts and
  ignores `--repo-dir`, `--config` and `--dry-run`.
- `--repo-dir` names the repository checkout; the helper resolves the canonical
  worktree, then verifies its GitHub origin against the native config.
- `--config` names one existing native `orbi.toml`. Without it, visible local
  configs and installed units are discovered. Multiple configs for the same
  repository are ambiguous and refused, even with an explicit `--config`.
- New-deployment `setup` accepts `--pi-providers PATH --pi-provider ID --pi-model ID`
  together, plus optional `--pi-thinking LEVEL`. These flags are setup-only and
  cannot change an existing deployment's selection. Help accepts and ignores them.
  The metadata path is relative to the current directory unless absolute.
- `--dry-run` prints the plan. It creates no config, scratch file, lock or
  receipt and runs no install, fetch, label change or activation.
- `--json` prints one document. Text mode prints flattened `key=value` lines
  for lifecycle actions; `help` prints a compact human block with usage, actions,
  mutation classes, options, limits and next steps.
- Every subprocess is an argv list; no shell interpolation. Provider/model IDs
  are reported, but credential values and environment values are never printed.
  Raw child stderr is not echoed.

Minimum compatible Python is 3.11 (standard library only, including
`tomllib`). The helper fails before mutations when that interpreter is
unavailable.

## Repository and deployment

- One repository per deployment. `source_repos` must contain exactly the
  verified `OWNER/REPO` origin. `repo_dir` must resolve to the canonical
  checkout.
- A new deployment gets a collision-resistant unit name derived from the
  repository (`<slug>-<8 hex>`) and exactly one slot. New configs set
  `keep_failed_worktrees = true` and `human_review_gate = false`: the optional
  human-acceptance label gate is off, not required CI or independent AI review.
- New configs derive `git_transport` from the verified origin: `ssh` for
  `git@github.com:OWNER/REPO.git` or `ssh://git@github.com/OWNER/REPO.git`, and
  `https` for `https://github.com/OWNER/REPO.git`. Setup never rewrites a remote;
  unsupported transports fail before staging.
- Existing configs, explicit review-policy settings, pins, schedules, credentials
  and attempts are preserved. A reused deployment keeps its pin; a changed pin is a deliberate owner
  operation, never a setup side effect.
- The initial supported source is the verified retention-capable pin
  `sha:ce97e015ca433a9312e5bdf69353be58ab394fd9`. Never silently upgrade it.
- Deployment/config paths and provider/env paths must not traverse symlinks,
  including parent directories. Validate the raw paths before resolving or writing.
- Native configs and installed unit identities own deployment state. There is
  no new registry, queue or mandatory state file.

## Isolation

The deployment's `.orbi/env` carries the same isolation values the helper puts
in every command it launches:

```
PYTHONPATH=<deploy_home>/src
UV_TOOL_DIR=<deploy_home>/.orbi/uv-tools
UV_TOOL_BIN_DIR=<deploy_home>/.orbi/bin
PYTHONDONTWRITEBYTECODE=1
PATH=<verified node bin>:<verified pi bin>:<deploy_home>/.orbi/bin:<home>/.local/bin:/usr/local/bin:/usr/bin:/bin
```

`PYTHONPATH` alone is insufficient: a first tick or a packaging change can run
`refresh_cli_install` and reinstall the tool. The deployment-local uv
directories keep that write inside the deployment. Never fabricate
`.orbi/cli-install.json`; upstream owns it.

Upstream native units still use `~/.local/bin/orbi`. This composition depends
on a compatible existing shared bootstrap while isolating source and uv writes;
it is not a fully self-contained deployment executable. Verify the bootstrap
before activation and fail closed. Live isolation remains separately
unqualified.

Unrelated `.orbi/env` entries are preserved. Credentials are never copied,
printed or written into provider metadata; a literal credential in
`pi_providers` is refused. Provider/model metadata must match published model
metadata, and stored Pi authentication stays in Pi's user agent directory.

## Setup

`setup` stages the official Orbi checkout at the verified pin, writes the
native config and `.orbi/env`, copies verified provider metadata only, installs a
missing user-local bootstrap with `uv tool install --editable --python <compatible>`
only when no conflicting installation exists, and validates with
`orbi check`. It reports `prepared`, not scheduler-installed or running.

Upstream `orbi setup` and `install-units` activate timers at this pin, so both
are deliberately deferred to an explicit `start`. Setup never enables a timer
to disable it again. No sudo, system package, automated login or shell-profile
change is used.

### First-deployment provider bootstrap

Pi must already have working authentication. No donor deployment is required:
use Pi's regular local `models.json` (or another credential-free catalog with
published metadata) and explicitly select its provider/model and optional reasoning:

```sh
python3 -B <loaded-skill>/scripts/orbi_control.py setup --repo-dir /path/to/repo \
  --pi-providers /path/to/models.json --pi-provider openai \
  --pi-model gpt-6.1-sol --pi-thinking high --dry-run --json
```

Use the actual catalog's IDs and published capabilities; never invent model
limits. Inspect the preview, then remove `--dry-run` to prepare. The file must
contain a `providers` object with the selected provider's `baseUrl`, API (at
provider or model level), and a `models` list. The selected model needs an `id`
and positive integer `contextWindow`/`maxTokens`. Literal `apiKey` values and
provider/model header values (including `modelOverrides` headers) are refused;
use only `$VARIABLE` or `${VARIABLE}` references for those fields. Even static
headers must use references because arbitrary header names can carry credentials.
Referenced values are not copied. Do not pass `auth.json` or migrate credentials.
File and parent symlinks, missing/invalid files, unknown models and incomplete selectors
fail before locks, staging or writes. Preview creates no deployment files or
receipts and performs no scheduler changes.

Without bootstrap flags, setup retains the existing donor-reuse path. An existing
target always keeps its own provider/model/reasoning, config and pin; bootstrap
flags are refused even if they repeat its selection. Rerun without them.
An unrelated deployment is never changed. A prepared result proves neither
scheduler activation nor model inference or protected delivery.

## Start

`start` requires a prepared, unambiguous target and an owner scheduling request.
Existing explicit pauses, cutover requirements and human-only gates must first
be resolved for that operation. The skill and offline checks do not release the
paused/live-unqualified contract. It re-reads unit ownership,
the pinned source, provider metadata, Node/Pi compatibility, GitHub and Pi
authentication and the shared bootstrap. It runs upstream `setup` and
`install-units` with the scoped environment, enables only instances
`1..max_concurrency` of this deployment's timer, and starts the first service
instance only when no instance is active or activating. A repeated start never
restarts or duplicates a live worker.

Start resumes only the explicitly named deployment. It never issues issue
pauses or blocked work and never touches another deployment. Enforced
administrators, strict required CI, independent review and human-only
acceptance stay in place; a doctor warning about enforced admins never
authorizes a protection change.

## Stop, status and drain

`stop` enumerates this deployment's owned timer instances, including installed
surplus instances up to the pinned five-instance bound, and runs only
`systemctl --user disable --now <timer>`. It never runs `stop`, `kill` or
`restart` on a service. A pre-existing invocation may finish; later issue
phases may wait for a start. Re-read the service states and report `draining`
while any is active or activating, `stopped` only when all service states were
observed as inactive or failed. Failed, empty or unknown state reads leave drain
unverified: report `scheduler_unavailable`, preserving any disabled-timer evidence.
Drain does not promise that an issue reaches merge: report remaining review and
merge work.

`status` is read-only. Upstream `orbi status` fetches refs through `freeze_base`
at this pin, so use read-only `orbi doctor` plus explicit `gh`, scheduler and
local reads. Missing evidence is `unavailable`, never an empty queue. Status
and dry-run create no config, lock, receipt or scratch file and suppress child
Python bytecode writes.

macOS supports status and help; setup/start/stop are refused before side effects.
Other platforms support help only; lifecycle actions fail clearly. Secrets never appear in commands, output or
error receipts.

## Ownership and discovery limits

Visible local deployments are the canonical checkout's `orbi.toml`, configs
under `$XDG_DATA_HOME/*/orbi.toml`, the explicit `--config`, and configs named
by installed `orbi*.service` units. A remote machine's ownership is not
visible; report it as unavailable and never claim a cross-machine lock or
aggregate capacity guarantee. `max_concurrency` is per deployment.

## Partial failure and recovery

Mutations report the step that succeeded and the step that failed with a
precise `error=` and `fix=` line. Do not rerun a command unchanged after a
timeout. Typical repairs:

- `provider_unavailable` with no deployment: supply the complete explicit
  bootstrap selectors and published local Pi metadata; creating a donor first
  is not required. For an existing partial deployment, repair its native
  `pi_providers`/`pi_provider`/`pi_model` selection deliberately, then rerun helper
  setup without bootstrap flags. No credentials are copied.
- `invalid_provider_selection`, `credential_copy_refused` or a symlink refusal:
  correct the selectors or use regular credential-free metadata paths, then
  preview again. These failures occur before preparation writes.
- `provider_override_refused`: omit bootstrap flags to preserve the existing
  target's selection. They cannot repair or replace an existing selection.
- `validation_failed` with `error.mutated: true`: files may already be prepared,
  but validation did not pass. Inspect the native config, provider metadata and
  check failure; repair the cause and rerun helper `setup` without bootstrap
  inputs (or non-activating `orbi check --config PATH`). Never run upstream
  `orbi setup`/`install-units` as routine preparation recovery. Use helper
  `status` to observe scheduler state separately, not `start` to repair metadata.
- `prerequisite_missing`: install the named command; no sudo is used.
- `bootstrap_incompatible` or `bootstrap_conflict`: repair or replace the
  user-local Orbi bootstrap deliberately; never force-reinstall a shared tool
  as part of another deployment's start.
- `unit_conflict` or `ambiguous_deployment`: keep one task pool per repository
  and remove or repoint the duplicate config or unit ownership.
- `source_drift` or `pin_mismatch`: check out the configured pin explicitly.
- `setup_failed`, `install_units_failed` or a timeout during either start step:
  upstream may already have activated timers or started workers. The error marks
  activation as `possible` and includes a read-only scheduler snapshot (or
  `unavailable`) and completed/failed steps. Inspect that evidence and the cause
  before recovery; never repeat activation unchanged or stop workers to undo it.
  Observation failure does not replace the original activation error.
- `scheduler_unavailable`: verify the systemd user session; status reports the
  same condition as unavailable evidence.

Offline tests and `doctor` do not qualify a live loop. Real issue pickup, PR,
independent review, required CI and protected merge remain live acceptance.
