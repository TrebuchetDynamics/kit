# Orbi lifecycle reference

Branch-only detail for `/orbi`. The steps live in
[SKILL.md](../SKILL.md); this page explains the interface, discovery, isolation
and recovery a lifecycle operator needs. It restates neither the provider
contract nor the protection policy: read
[GitHub-native development](../../../docs/github-native.md) for those.

## Interface

Public skill syntax on all hosts: `/orbi setup` maps to helper `start` and
expresses scheduling intent. It prepares/validates if absent, then activates only
when existing gates are resolved; valid existing targets skip preparation and
retain exact saved selectors. `/orbi setup --prepare-only` maps to helper `setup`.
The canonical skill consumes the public-only flag, forwarding all other supported
arguments literally. Default `setup --dry-run` previews start without writes;
`setup --prepare-only --dry-run` previews only preparation. Reject public
`setup --resume-setup` before any helper invocation/mutation unless `--prepare-only`
is explicit; show `setup --prepare-only --resume-setup` with the original arguments.
Help/status never implicitly prepare or start. See the canonical mapping in
[SKILL.md](../SKILL.md#common-path).

**Direct Python helper syntax** below is unchanged: helper `setup` is always
non-activating, and `--prepare-only` is not a helper flag. Unqualified helper action
names in the technical sections below refer to this direct interface, not public
setup's default mapping.

```sh
python3 -B <loaded-skill>/scripts/orbi_control.py [status|setup|start|update|stop|help] \
  [--repo-dir PATH] [--config PATH] [--dry-run] [--json] \
  [--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]] \
  [--resume-setup] [--harness {pi-bolt,pi}] [--stop]
```

- Omitted action means `status`. A bare `orbi` runs one Runner tick and is never
  the lifecycle entry.
- `help` takes no repository, reads no deployment and is available on every
  platform. It is the only action that needs no deployment context; `status`
  still binds a repository and reports an absent deployment. Help accepts and
  ignores `--repo-dir`, `--config`, `--dry-run` and all setup inputs.
- `--repo-dir` names the repository checkout; the helper resolves the canonical
  worktree, then verifies its GitHub origin against the native config.
- `--config` names one existing native `orbi.toml`. Without it, visible local
  configs and installed units are discovered. Multiple configs for the same
  repository are ambiguous and refused, even with an explicit `--config`.
- New-deployment `setup` and an authorized absent-target `start` accept `--pi-providers PATH --pi-provider ID --pi-model ID`
  together, plus optional `--pi-thinking LEVEL`. Existing-target start rejects
  these flags; omit them to retain its selection. Help accepts and ignores them.
  The metadata path is relative to the current directory unless absolute.
- `--harness {pi-bolt,pi}` selects an installed executable for new `setup` or
  absent-target `start` preparation. Omission defaults to Pi-Bolt. A missing selected command is an
  exact prerequisite failure, not permission to install or fall back. Existing
  managed deployments reuse their saved selection; setup accepts a matching explicit
  selector as a no-op and refuses a conflicting one. Existing start rejects either. Legacy deployments refuse a selector
  with deliberate migration guidance. Help accepts and ignores it.
- Setup-only `--resume-setup` is the explicit legacy missing-provider exception:
  require `--config PATH` and complete matching provider inputs. It never changes
  a saved selection, pin or present provider file. See bounded resume below.
- `update` accepts `--repo-dir`, `--config`, `--dry-run`, `--json` and update-only
  `--stop`. The last flag explicitly authorizes pausing owned timers without
  another prompt, never service interruption or restart.
  Provider, resume and harness selectors are refused: an update preserves the
  saved selection.
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
  `sha:ce97e015ca433a9312e5bdf69353be58ab394fd9`. Setup never upgrades it; only
  the deliberate `update` below advances a deployment past that pin.

## Release update

```text
/orbi update --stop --dry-run
/orbi update --stop
```

`update --stop` pauses the selected deployment and updates only once idle. It
validates ownership, source cleanliness, saved harness/provider and prerequisites
before touching timers, then revalidates under the existing deployment lock.
It disables only owned timers (including inactive-but-enabled and active instances)
and requires fresh disabled/inactive readback. Unknown/foreign ownership, incomplete
inventory or unreadable scheduler evidence refuses safely, without syncing.
Loaded/installed instances and pending jobs are enumerated in addition to configured
slots and the normal status scan; surplus workers and queued starts are not ignored.

If workers are active/draining or jobs remain, the receipt has `status: draining`,
`engine_update: deferred`, `scheduler_confirmation: timers_disabled`,
confirmed disabled timers, `pending_services` and the
exact `resume_command` to deliberately retry after they finish. Engine source and
pin are untouched. There is no polling, background continuation, service stop/kill,
worker cancellation or automatic restart. Retrying does not carry saved restart
intent: scheduling stays stopped.

Once fresh idle/no-pending-start evidence is available, this path uses the same
release synchronization, exact pinning and non-activating validation described below.
It **never calls public `install-units`**, because that installer enables timers,
even briefly. Unit refresh is `deferred` to the next separately authorized `start`,
which already installs units. It reports engine `updated`/`up_to_date`, unit refresh
`deferred` with that reason, and `scheduler_confirmation: stopped` only after final
scheduler readback proves disabled/inactive timers and no pending work. On failure,
completed disables, the failed stage, actual scheduler evidence (or `unavailable`)
and `resume_command` remain visible; no timer re-enable rollback is attempted.
`--stop --dry-run` previews pause/drain and conditional update without writes,
locks, fetch or unit actions. Selectors and protected start gates are unchanged.

### Plain update compatibility

`update` advances one prepared deployment to the newest official release and
repairs its owned units. It needs the same evidence as setup plus a stopped and
drained deployment: readable scheduler evidence, no active or activating service
and no enabled timer. A live worker or enabled timer refuses as `update_busy`
before any write. Tracked changes in the deployment checkout refuse as
`source_dirty`; update never discards or force-checks-out work.

Under the deployment lock it rechecks ownership, source, checkout cleanliness and
inactivity, then:

1. writes the upstream `release` channel into `engine_source_track`;
2. runs upstream `sync-engine-source`, which fetches the official tags, resolves
the newest semver release (pre-releases excluded), dereferences the annotated tag
and checks that commit out detached; it fails closed and is never retried
unchanged;
3. reads the resulting HEAD and locks it as `sha:<commit>`, so later ticks verify
one exact commit instead of tracking a moving tag;
4. validates with non-activating `orbi check`;
5. refreshes this deployment's owned units with upstream `orbi install-units`
when they are installed, which re-renders the deployment templates and enables
configured timers; a deployment with no installed unit reports
`refresh_units: deferred` and leaves first installation to `start`;
6. disables every owned timer that install enabled, restoring the verified
inactive state, and reports the names in `disabled_timers`;
7. observes the scheduler again and reports `pending_services`.

The config must declare exactly one `engine_source_track` line; update rewrites
that literal and preserves every other byte. An engine that predates the upstream
release channel fails the sync closed and is reported as
`sync_engine_source_failed`; that deployment needs a deliberate source repair, not
a second retry.

It reports `updated`, or `up_to_date` when the release commit did not move; both
still refresh units and validate. `previous.track`/`previous.head` name the
observed starting point, and `deployment.deployed_commit` the locked release.
Origin, slots, provider metadata, harness selection, `.orbi/env` and unrelated
config bytes are preserved. Update never enables scheduling as an outcome: run
`start` under its own authority afterwards. Rollback is a deliberate owner edit
of `engine_source_track` to the previous tag or sha; there is no second state.
`update --dry-run` performs no write, fetch or lock and reports `planned`.
- Deployment/config paths and provider/env paths must not traverse symlinks,
  including parent directories. Validate the raw paths before resolving or writing.
- Native configs and installed unit identities own deployment state. There is
  no new registry, queue or mandatory state file.

## Isolation

The deployment's `.orbi/env` carries the same isolation values the helper puts
in every command it launches:

```
HOME=<verified-auth-home>
PYTHONPATH=<deploy_home>/src
UV_TOOL_DIR=<deploy_home>/.orbi/uv-tools
UV_TOOL_BIN_DIR=<deploy_home>/.orbi/bin
PYTHONDONTWRITEBYTECODE=1
PATH=<deploy_home>/.orbi/harness-bin:<deploy_home>/.orbi/bin:<home>/.local/bin:<verified tool bins>:...
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

Unrelated `.orbi/env` entries and modes are preserved byte-for-byte. Credentials are never copied,
printed or written into provider metadata; a literal credential in
`pi_providers` is refused. Provider/model metadata must match published model
metadata, and stored Pi authentication stays in Pi's user agent directory.

### Harness selection and evidence

New setup resolves `pi-bolt` (or explicit `--harness pi`) from the caller's PATH
before any lock or write. Normal installed symlinks resolve to a verified absolute
executable. The generated executable `.orbi/harness-bin/pi` uses a safely quoted
shell `exec ABSOLUTE_TARGET "$@"`; it preserves argv, exit status and signals.
Only this owned directory is prepended to the deployment PATH. No global alias,
native harness TOML setting, upstream patch or automatic harness installation is
used. The pinned [command builder](https://github.com/orbi-build/orbi/blob/ce97e015ca433a9312e5bdf69353be58ab394fd9/src/orbi/pi_command.py)
calls `pi` for implementers and reviewers; both therefore use this same routing.

`.orbi/env` is the persistence owner: `KIT_ORBI_HARNESS` is `pi-bolt` or `pi`,
`KIT_ORBI_HARNESS_EXECUTABLE` is the resolved absolute target, and
`KIT_ORBI_HARNESS_SOURCE` is `default` or `explicit`. Managed `HOME` pins the auth
home too. Helper launches use persisted routing/credentials rather than ambient
PATH or shell-only credentials. The [native loader](https://github.com/orbi-build/orbi/blob/ce97e015ca433a9312e5bdf69353be58ab394fd9/src/orbi/config.py)
otherwise lets ambient variables win via `setdefault`.

Managed values use single-quoted literals shared by the native loader and systemd
`EnvironmentFile`: no single/double quotes, backslashes, NUL, newlines, controls or
edge whitespace inside a value. Interior spaces work. Individual executable,
deployment and PATH-component paths must be absolute and colon-free; the complete
validated PATH is colon-joined and then quoted. Launcher shell quoting is a
separate operation, not env-file escaping. Unsupported values fail before writes.
Unrelated credential lines are never decoded and re-encoded for publication.

Setup/status/start include `deployment.harness` with `management` (`managed` or
`legacy`), `requested_kind` (`pi-bolt`, `pi` or null), `selection_source`
(`default`, `explicit`, `legacy`), `launcher`, `executable` and `state`
(`verified`, `unavailable`, `drift`, `unknown`). Verification is configured and
resolved-now file/executable evidence, **not observation of a running process**.
Setup records an `observed_version` only after the selected `--version` probe;
status performs no harness/auth probe, refresh, install or write. A preview's
unpublished launcher is `unknown`, not verified. No deployment means unconfigured:
Pi-Bolt is only the new-setup default, not an active selection.

Legacy configs without these fields keep their stored PATH and remain unmanaged.
When reliable, status resolves that stored effective `pi` without inferring its
kind from a version string. With no stored PATH it reports ambient helper
resolution and unverified service resolution separately. Repeated setup does not
migrate legacy deployments. Missing/partial metadata, an altered launcher, an
unavailable/redirected target or changed managed routing blocks activation; inspect
and repair deliberately, never regenerate from today's default.

Pinned [Pi session preparation](https://github.com/orbi-build/orbi/blob/ce97e015ca433a9312e5bdf69353be58ab394fd9/src/orbi/pi_session.py)
merges enabled extension env into the final child. Managed activation refuses an
incompatible extension PATH/HOME or any extension agent-directory override, even
though normal per-run provider preparation supplies `PI_CODING_AGENT_DIR` later.
Byte-equivalent PATH/HOME overrides are accepted. Incompatible inherited auth-home
or agent-directory overrides also refuse. Neither extensions nor legacy configs
are rewritten to bypass this guard.

## Setup

Public preparation-only uses `/orbi setup --prepare-only`. Direct helper `setup` stages the official Orbi checkout at the verified pin, writes the
verified provider metadata, harness launcher and `.orbi/env` atomically, publishes the native config
last, installs a
missing user-local bootstrap with `uv tool install --editable --python <compatible>`
only when no conflicting installation exists, and validates with
`orbi check`. It reports `prepared`, not scheduler-installed or running.

Before locks, staging or writes, setup checks supported transport and explicit
metadata, path/ownership evidence, available tools/authentication and observable
scheduler activity. An existing config's transport mismatch is a deliberate
**deployment-local** `git_transport` repair, never `git remote set-url` or upstream
activating setup. For a missing bootstrap, it runs the read-only system Python
probe and `uv tool list` first. Failed or timed-out listing is unverified, not
conflict-free. Compatible system Python selects `python3`; absent/older system
Python selects the existing uv `3.14` provisioning fallback. The selection is in
`prerequisites.python`. Network/provisioning failures remain possible during install.
Dry-run lists checked prerequisites separately from planned/unrun staging,
installation and validation; it cannot qualify checks requiring a staged deployment.
Ownership, file identities, source and inactive/no-worker evidence are rechecked
under lock. Unknown activity or unreadable timer enablement is not permission to
repair. Setup refuses enabled (including runtime-enabled) or active target timers
as well as active/unknown worker states; separately
authorized stop/drain and readable inactive evidence are required first.

Files use same-directory atomic publication: complete bytes or absence, not
truncated native config/provider/env. Existing modes and unrelated env entries
are preserved; new provider/env files are `0600`, new config is `0644`. If killed
before config publication, a retry can reuse an official pinned staged checkout
and byte-equivalent intended provider/launcher/env files. Saved harness fields
retain selection across a config-last retry; conflicting bytes or modes refuse. Conflicting files are refused
before the lock, not overwritten. No recovery registry or fabricated cli-install
receipt is created. Temporary publication files left by a killed process are
not a readiness authority and are not automatically deleted on retry.

Upstream `orbi setup` and `install-units` activate timers at this pin, so both
are deliberately deferred to helper `start` (public default setup or start). Helper setup never enables a timer
to disable it again. No sudo, system package, automated login or shell-profile
change is used.

### First-deployment provider bootstrap

Authentication must already be provisioned; setup never logs in. No donor deployment is required:
use Pi's regular local `models.json` (or another credential-free catalog with
published metadata) and explicitly select its provider/model and optional reasoning:

```sh
python3 -B <loaded-skill>/scripts/orbi_control.py setup --repo-dir /path/to/repo \
  --pi-providers /path/to/models.json --pi-provider PUBLISHED_PROVIDER_ID \
  --pi-model PUBLISHED_MODEL_ID --pi-thinking SUPPORTED_LEVEL --dry-run --json
```

Use the actual catalog's IDs and published capabilities; never invent model
limits. Inspect the preview, then remove `--dry-run` to prepare. The file must
contain a `providers` object with the selected provider's `baseUrl`, API (at
provider or model level), and a `models` list. The selected model needs an `id`
and positive integer `contextWindow`/`maxTokens`. Literal `apiKey` values and
provider/model header values (including `modelOverrides` headers) are refused;
use only `$VARIABLE` or `${VARIABLE}` references for those fields. Even static
headers must use references because arbitrary header names can carry credentials.
Referenced values are not copied. For each effective implementer/reviewer provider
(deduplicated), preflight checks declared key/header names in the deployment's
persisted `.orbi/env` and the final compatible extension environment. A nonempty
shell-only key is not service-ready. Missing references name the exact variable
and env-file location to provision **separately**; setup does not write keys.
A pre-provisioned credential-only env file in an official pinned staged checkout
is preserved while managed fields are appended. A fresh custom-provider setup may
therefore need separately authorized source staging and env provisioning first.
Env-file-only values are checked in memory without rewriting their original lines.
This route reports `references_available`, not successful authentication/inference,
and works when the custom provider is absent from the user's global catalog.

With no declared references, preflight runs the selected target's
`auth check --provider ID --no-refresh` against the existing `HOME/.pi/agent`
catalog/auth home, without shell-only keys. Failure is `auth_unverified`, with the
missing provider/catalog/auth input to repair; schema validation is not an auth
pass. Upstream still merges deployment providers into per-run models and links
user `auth.json`; dry-run makes no temporary profile and copies no credentials.
Full custom-provider model invocation remains unrun. Do not pass `auth.json` or migrate credentials.
File and parent symlinks, missing/invalid files, unknown models and incomplete selectors
fail before locks, staging or writes. Preview creates no deployment files or
receipts and performs no scheduler changes.

Without bootstrap flags, setup retains the existing donor-reuse path. An existing
target always keeps its own provider/model/reasoning, config and pin; bootstrap
flags are refused even if they repeat its selection. Rerun without them.
The explicit bounded resume below is the only exception.
An unrelated deployment is never changed. A prepared result proves neither
scheduler activation nor model inference or protected delivery.

### Explicit bounded legacy resume

At the public surface, use `/orbi setup --prepare-only --resume-setup --config PATH`
with the complete matching provider inputs below (and preserve `--dry-run` if requested).
Without `--prepare-only`, refuse before mutation and give that corrected command.
The direct helper command below stays non-activating for recovery/automation.

Only for an existing valid native config whose saved `pi_providers` names the
missing deployment-local `.orbi/pi-providers.json`:

```sh
python3 -B <loaded-skill>/scripts/orbi_control.py setup --repo-dir /path/to/repo \
  --config /path/to/deployment/orbi.toml --resume-setup \
  --pi-providers /path/to/models.json --pi-provider SAVED_PROVIDER_ID \
  --pi-model SAVED_MODEL_ID --dry-run --json
```

Use the **saved** IDs, not the illustrative ones. Omitted `--pi-thinking` inherits
the saved value; a supplied value must match exactly. Inspect the preview, then
remove `--dry-run`. Metadata/capabilities and credential references use normal
validation. The canonical repo, supported source pin, official staged origin,
local ownership, deployment-local config/provider paths and inactive/no-worker
evidence must verify before and under lock. Resume fills only the absent provider,
then prepares env and validates without activation. Repetition may reuse the
identical intended provider bytes as a no-op. It never replaces a present invalid,
changed or non-equivalent file. Malformed config, symlinks, foreign/external paths,
duplicate ownership, a changed pin, unknown checkout or active/unknown activity
are not resume states: preserve evidence and deliberately repair the exact
reported config/path/ownership/source/activity problem. Normal setup still refuses
all bootstrap selectors on existing targets, even identical selections.

If an installed helper rejects `--resume-setup` (or older first-machine flags),
report the absolute **loaded helper path** and available installed Kit package/source
revision, not the unrelated Orbi engine pin. Use that helper's context-free `help`
to identify its contract. Recommend a separately authorized Kit update and host
reload; do not silently update, invoke activating upstream setup, or rewrite the
project origin. A stale installed helper is different from a genuinely unsupported
transport or an owner-required repair.

## Activation evidence

The owner's request to start scheduling and the evidence that permits that operation
are different inputs. Preserve already-settled intent; do not ask the owner to approve
the same start again. Read the bound deployment's status, repository instructions,
applicable [cutover checklist](../../../docs/github-native.md#cutover), and any existing
issue/PR or qualification record relevant to that repository and requested stage.
Collect evidence read-only. Do not change labels, protections, units or credentials
while deciding whether activation is allowed. Help itself performs none of these reads.

Before an actual start, give a short evidence report:

- **Request and target:** name the owner request, repository/deployment and operation
  (for example first pilot versus rollout); do not infer authority from a successful preview.
- **Observed:** cite the helper status/preview and relevant checklist or existing record
  by path/URL and the specific evidence it supplies. Reuse applicable evidence, not stale
  or unrelated approvals. If no record was found in the inspected sources, say so and
  name those sources; absence of a record is not itself a new activation gate.
- **Missing or unknown:** name each applicable check that is unresolved, not just
  “cutover required.” Depending on the requested stage, this can be unsettled legacy
  pool ownership, release/worktree-placement compatibility, unreadable scheduler state,
  protected CI/review evidence, pilot delivery/recovery proof before expansion, or fleet
  capacity evidence. Apply the existing checklist, not a new gate or mandatory receipt.
  Do not demand rollout qualification as a prerequisite to an otherwise authorized pilot.
- **Next safe action:** name the read-only check that can resolve each unknown, or the
  exact external input/owner-controlled repair needed, and which operation stays held.
  Do not ask for a generic “cutover record,” manufacture approval, or reconfirm settled
  owner intent. Keep explicit pauses and human-only gates until their actual requirements
  are satisfied. [#12](https://github.com/TrebuchetDynamics/kit/issues/12),
  [#13](https://github.com/TrebuchetDynamics/kit/issues/13) and
  [#20](https://github.com/TrebuchetDynamics/kit/issues/20) retain live qualification/rollout
  ownership; this guidance does not release them.

If GitHub reports **unprotected main**, report that observed branch state and the
missing protection evidence; it is not an access error. If protection or rules reads
return **HTTP 403**, report access denied and those details as unknown, not absent or
passing. Both observations can coexist: report each with its source, without claiming
that the 403 proves no rules exist. Next: obtain a read-only protection/rules view from
an identity with access, or have the repository owner establish the required protections
through its governance path if missing. Never weaken protections or invent a review
approval to clear the blocker. See [protection diagnostics](../../../docs/github-native.md#read-protection-diagnostics-safely).

### Offline guidance examples

These are walkthrough inputs, not current host observations or live qualification.
Use disposable fake hosts only; do not contact the named repositories' real hosts.

- **Arenaton:** given `deployment.state=absent`, scheduler unavailable, an owner start
  request, GitHub reporting main unprotected, and protection/rules HTTP 403: explain
  that authorized implicit-target start will prepare, validate, then activate in one
  invocation. Offer `start --dry-run` only as a write-free preview, with staged checks
  deferred. Scheduler activity and rule details are unknown; the branch response is
  separately unprotected. Cite the applicable cutover checklist and any found record;
  if none was found, say so. Name the unresolved ownership/pause/qualification checks
  applicable to this stage, not a blanket missing approval. Next: restore readable
  scheduler evidence and obtain the read-only protection view/owner repair above.
  Hold activation on the unresolved applicable checks; no redundant setup or consent loop.
- **fecim-lattice-tools:** given a previously prepared Pi-Bolt slot with saved
  `openai-codex/gpt-6.2-sol`, validated config and no enabled timers or inference:
  preparation is not activation or live qualification, and this is not evidence of
  model failure. New public `/orbi setup` expresses scheduling intent and delegates
  to existing-target `start`, skips preparation and retains that exact saved selection;
  omit provider/model/harness selectors. Once applicable pause/cutover/branch/CI/human
  gates are evidenced, invoke once without another approval prompt. If a gate is
  missing, name that blocker and the read-only check or owner repair; do not silently
  prepare or claim started. `/orbi setup --dry-run` previews this start route;
  `/orbi setup --prepare-only --dry-run` previews non-activating preparation instead.
  This walkthrough does not inspect or change the reported deployment.
- **SalmaListApi:** given a setup preview returning `setup_busy`, one active/owned timer
  and zero observed running services: report “scheduling is active, but no worker was
  observed within the scan.” Use `status`, not setup, to inspect; this is not stopped or
  a request to install extra instances. A valid existing start skips setup and retains
  saved selection, subject to its existing authority/gates. Offer stop/drain only if
  deliberately re-preparing or pausing, preserve workers, and verify inactivity before
  setup. Missing reads or out-of-scan activity remain unknown, not zero.

## Start

Public `/orbi setup` delegates to this exact helper start path, not another
activation implementation. `--prepare-only` deliberately opts out. Gate failure
holds activation with the specific blocker/repair, never a silent preparation-only
success. Resolved, already-authorized activation needs no second approval.

After explicit scheduling authority and resolved gates, a first deployment can use:

```text
/orbi status
/orbi setup --dry-run --pi-providers /path/to/models.json --pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID
/orbi setup --prepare-only --harness pi --pi-providers /path/to/models.json --pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID
/orbi start --dry-run --pi-providers /path/to/models.json --pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID
/orbi start --pi-providers /path/to/models.json --pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID
/orbi start --dry-run
/orbi stop
```

These are alternatives, not a sequence to run blindly: only public setup with
`--prepare-only` stays non-activating. If it already prepared the target, omit the bootstrap/harness
selectors on start. Replace placeholder IDs/paths with published catalog evidence;
optional `--pi-thinking LEVEL` must also match supported reasoning. Planned,
prepared, activated and live-qualified are distinct; stop reports drain, not a kill.
Use context-free `/orbi help` for the loaded helper path, defaults and recovery table.

`start` requires an owner scheduling request. Existing explicit pauses, cutover
requirements and human-only gates must first be resolved for that operation. The
skill and offline checks do not release the paused/live-unqualified contract.

If no deployment exists and no explicit `--config` was supplied, start composes the
same non-activating new-deployment preparation as `setup`: installed Pi-Bolt by
default, or explicit `--harness pi`; complete provider inputs, or verified donor
metadata when omitted. A missing input is an exact prerequisite failure, never a
request to create a donor, install a harness, log in or invent model capabilities.
Preparation must return `prepared` after non-activating validation. Start then
rediscovers/re-reads the exact config and checks the prepared binding, file identities,
canonical repository, ownership, source, provider, harness and prerequisites again
under the activation lock. The setup lock is released before this lock is acquired.
Changed ownership/config/selection holds without activation or automatic repair.

An existing valid or active target skips preparation entirely, avoiding `setup_busy`
and preserving its provider/harness/pin. Omit all `--pi-*` and `--harness` selectors
on subsequent starts; even matching bootstrap selectors are refused. A missing
explicit config is an error, not permission to create a target. Malformed, ambiguous,
foreign or partial existing targets require deliberate recovery; start never performs
`--resume-setup` (setup-only). Config-absent interrupted preparation can reuse only
verified staged source and byte-equivalent intended files under normal setup rules.

Start re-reads unit ownership, the pinned source, provider metadata, Node/Pi
compatibility, GitHub and Pi authentication and the shared bootstrap. It runs upstream `setup` and
`install-units` with the scoped environment, enables only instances
`1..max_concurrency` of this deployment's timer, and starts the first service
instance only when no instance is active or activating. A repeated start never
restarts or duplicates a live worker.

A definite nonzero exit from a configured timer's `systemctl --user enable --now`
can still allow one normal `systemctl --user start` of the exact owned slot-1
service. This exception requires successful upstream setup/install and scheduler
readback. Still under the config lock, the helper revalidates repository/config/file
identity, reads fresh unit ownership and states, and enumerates loaded/installed
instances and pending jobs. Every relevant worker must be known idle, all configured
timers must have stable owned evidence (active, inactive or failed), and no target
job may remain. Partially enabled/active timers are observed, not rolled back.
An active/draining worker, unknown state/ownership, target drift, timer transition,
missing unit, timeout or unavailable scheduler blocks this request. Upstream
setup/install failures never enter this exception. No later timer is configured,
no failed timer is retried, and no Runner CLI is invoked directly. Public default
setup uses this same path; prepare-only and dry-run do not.

For an absent target, start dry-run runs only setup's nonmutating preflight/preview.
It reports preparation and activation as planned, with staged source, published-file
validation and activation preflight explicitly deferred/unrun. It does not run
`start_plan` on nonexistent files or imply those gates passed. Unknown prerequisites
fail honestly. It creates no deployment directory, lock, launcher, config, source
fetch, bootstrap or timer writes.

For an existing target, start dry-run plans the same configured `1..max_concurrency` timer range, skipping
already-active timers. Its separate `scheduler` snapshot retains the broader
observed inventory, including out-of-config units; those observations are not
planned activations. Preview performs no mutation.

Start activates only the bound deployment. It never issues issue
pauses or blocked work and never touches another deployment. Enforced
administrators, strict required CI, independent review and human-only
acceptance stay in place; a doctor warning about enforced admins never
authorizes a protection change.

## Stop, status and drain

`stop` enumerates this deployment's owned timer instances, including observed
out-of-config instances within the five-instance observation bound, and runs only
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

### Pending issues and read coverage

`queue.state` and `queue.ready` remain the ready-queue interface: ready is a list
of `#number title` strings, now verified against observed holds, ownership and
open native prerequisites. `queue.pending_count` counts all observed open issues,
not PRs; `queue.pending` groups them into `actionable_blocker`, `active_owned`,
`native_dependency`, `planning_paused`, `epic`, `ready` and `unknown`. Each row
includes number, title, URL, labels, observed owners, native prerequisites, reason
and next action. Ownership labels/assignees are not proof of a running worker.
Epics are coordination, not executable work. Planning/paused issues point to their
owner for the recorded decision/input; when not evidenced here, that input is
explicitly unknown. Dependencies come only from native `blockedBy`, never issue
ordering or similar titles. Status does not invent a repository-wide bottleneck
from one blocked issue.

GitHub reads are bounded: at most three cursor pages of 100 issues (creation
order), with up to 100 labels, 10 assignees and 20 native prerequisites per issue.
Non-Issue and closed records are excluded defensively. Native dependency evidence
is batched with the list, not fetched separately per issue. Only blockers and
owned/active issues request comment detail, prioritizing blockers. A shared budget
of ten additional reads covers comments (100 per page, up to three pages per
issue) and deduplicated same-repository PR links found in those comments. No LLM
call per issue is required. Unlinked PRs and remote worker ownership remain unknown.
PR rows report observed state and head; `OPEN` is not successful delivery, and
`MERGED` alone does not prove issue acceptance or live qualification.

`queue.coverage` reports listing completeness, page/read bounds, reads performed
and gaps, including truncated nested connections, repeated/missing cursors, detail
caps and failed/invalid API reads. `queue.state` is `ok` with complete evidence,
`partial` with retained observations and gaps, or `unavailable` when no reliable
listing was read. A successful complete empty list is genuinely zero pending;
an API failure is not. Partial counts/readiness are observed lower bounds, not an
exhaustive queue. Restore GitHub auth/read access or inspect the named limit, then
rerun read-only status. Raw API errors are not echoed. JSON exposes these fields;
text mode renders them as flattened `queue.pending.<group>=...` and coverage lines.

A blocked failure receipt's `retry_safe=false` forbids blind retry/requeue; no
receipt ever grants safe retry. For a reported branch change/conflict, the next
action is to compare the current remote head and retained work with the existing
owner before any retry, preserving both candidates. Follow
[`/unblock`](../../unblock/SKILL.md) deliberately for recovery; status does not
invoke it, write labels, launch workers, repair branches or settle planning
choices. Detail gaps mean the diagnosis may be incomplete, not permission to
retry. An idle service snapshot plus ready issues calls for inspecting scheduler
and ownership evidence and existing pauses; only separately authorized `start`
can activate scheduling. No status result releases a live gate.

`deployment.state=transitional` means activating/reloading services without an
observed active service. It is neither verified idle nor issue pickup. Existing
scheduler counts retain their observation semantics below: a transitional unit
may count in `running_services` for drain safety, not as delivery evidence.

### Interpreting Linux scheduler inventory

For a bound Linux target, `deployment.slots` and
`scheduler.inventory.configured_slots` come from native `max_concurrency`.
They describe configured capacity, not observed enablement or activity. Every
emitted timer/service record adds `configured` (index within that capacity) and
`fragment_kind`: `template` for a readable shared `@.timer`/`@.service` fragment,
`instance` for a readable instance-specific fragment, `absent` for a known empty
FragmentPath, or `unknown` when the filename/read cannot establish its kind.
Legacy `installed` means only nonempty FragmentPath, not enabled/deployed capacity;
`owned` remains bound to the service fragment's `ORBI_CONFIG`, never inferred
from template availability. Absent timer fragments retain the existing omission
from `timers`; service records cover every scanned index.

`scheduler.inventory` exposes `scope: local-target-prefix`, `scan_first: 1`,
`scan_last: 5` (the current `MAX_INSTANCES`) and `outside_scan: unobserved`.
`configured_slots_covered` is false when configured capacity exceeds this scan;
positive concurrency above five remains valid. Counts describe only owned
observed units within that bound, including out-of-config ones, not exhaustive
whole-deployment or remote activity:

- `counts.enabled_timers`: explicit enablement, including runtime-enabled timers.
- `counts.active_timers`: timer ActiveState is exactly `active`.
- `counts.running_services`: service ActiveState is `active`, `activating` or
  `reloading`. `deactivating` remains drain evidence, not a running-service count.

Each metric is `{state: ok, value: integer}` only with complete evidence for that
metric, including ownership; incomplete/failed reads or foreign/ambiguous ownership
produce `{state: unavailable, value: null}`, not zero. Known absent fragments
contribute zero. Exceptions may make all counts unavailable, while configured
capacity and scan bounds remain visible. Unknown timer activity invalidates its
active count even if legacy snapshot `state` is `ok`. JSON exposes these fields;
text mode flattens them, for example
`scheduler.inventory.counts.enabled_timers.value=3` (unavailable values render as
`None`, with `state=unavailable`). Absent deployments and macOS do not invent Linux
inventory counts.

For example, a config with three slots, templates visible for 1–5 and only 1–3
enabled means **3 configured slots, 3 enabled timers; observed instances 1–5**.
Rows 4/5 have `configured: false` and `fragment_kind: template`; template presence
alone is not enabled surplus. Genuine out-of-config enablement/activity is visible
in those rows' `enabled`, `active` or service `state` and in the observed counts.
Disabled does not mean impossible to activate manually; enabled does not mean
currently running. A service-unit state proves neither a working model nor a
completed delivery, and counts do not establish global deployment health.

One deployment/task pool can have several slot timers; that is not several
repositories or duplicate pools claiming the same queue. Compare native config,
explicit enablement and observed activity before naming a scheduling defect.
Never manually enable instances 4/5 just to match `MAX_INSTANCES`. Use read-only
status for observation: helper `setup --dry-run` (public `setup --prepare-only --dry-run`)
is preparation preflight, not a harmless
health substitute. `setup_busy` while scheduling/workers are active is an expected
refusal, not evidence of extra instances. Any repair still requires its own
scope/authority; this inventory authorizes no scheduler mutation.

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

Mutations report completed steps and the failed step with a precise `error=`
and `fix=` line. JSON uses `error.mutated`; text errors explicitly include
`mutated=True/False`. Nonzero exit alone does not mean unchanged state.
Setup errors include `target`, `original_error`,
completed/failed `steps`, `error.mutated`, `activated: false` and separately observed
`scheduler` evidence (or `unavailable`). Lock creation counts as mutation. An
attempt that may have written is marked `mutation: possible` on failure; completed
operations are distinguished from possible partial mutation. Filesystem errors
are structured with details withheld; raw stderr, metadata and credential/env
values are never receipts. `activated: false` means this setup invoked no
activation, **not** proof an existing scheduler is inactive.

Start results and errors include `preparation` with `state: skipped|planned|prepared|failed`
and target/steps/harness/prerequisite evidence when available. A preparation failure
preserves its original operation/code/steps and invokes no activation. If preparation
wrote files and later activation preflight fails, `error.mutated` remains true,
preparation remains `prepared` and activation is `none`. Inspect and repair the cause;
there is no automatic retry or rollback. Preparation, activation and live qualification
are separate outcomes.

Start/stop errors also retain `target`, deployment config/unit identity,
`original_error`, and completed/failed `steps` at the JSON top level (not under
`error.evidence`). A failed step names its `unit` when applicable and records
`mutation: possible` for an attempted write, `none` for an observation failure.
Lock acquisition/release failures count as possible writes even if no scheduler
command ran. Preflight and dry-run failures remain mutation-free.

Start reports `activation: possible` once upstream activation is attempted,
including later timer-enable, first-tick or scheduler-read failures. Lock-only
failure reports `activation: none`, not unchanged files. `activated_timers` lists
only direct enables that returned successfully; it is not an exhaustive list of
upstream activation. Stop retains `disabled_timers` only for confirmed completed
disables. Failed and unprocessed timers may still schedule work; a failed command
can have applied effects without completing successfully. A read-only `scheduler`
snapshot is separate evidence, or `unavailable` if inspection failed. Recovery
inspection never replaces the original error or completed steps.

Before recovery, inspect helper `status` read-only and the failed step/unit
privately, then deliberately repair the cause. Never automatically repeat a
start/stop, retry an unchanged timeout, roll back with enable/disable compensation,
or stop/kill/restart workers to undo partial application. The helper attempts no
later timer mutations after failure. Only the guarded definite timer-enable failure
exception above permits a first-tick request. Its receipt keeps the original timer
error, nonzero exit, failed step and confirmed timer list, with
`recurring_scheduling: incomplete`. Separate `first_tick` reports `requested`,
`blocked`, `failed`, `unverified` or `not-requested`. `first_tick_evidence` names the
service, decision scheduler snapshot, mutation (`none`, `possible` or `completed`)
and reason/error when applicable. A failed or timed-out first-tick request never
replaces the timer error and is not retried. The top-level scheduler is a later
read-only observation; it does not erase the decision evidence. `requested` means
systemd accepted one request, not that a worker completed or live delivery succeeded.
Inspect status and repair recurring scheduling deliberately even if the request
succeeded; do not repeat start blindly.

A process killed before rendering cannot emit a receipt. Infer safe retry from
actual files: complete matching provider/env with no config can be reused by new
setup; complete valid config uses normal setup without selectors; the bounded
legacy missing-provider case needs explicit resume. Other states need deliberate
repair preserving all recovery inputs. Never automatically delete, roll back or
retry an unchanged timeout. Typical repairs:

- `provider_unavailable` with no deployment: supply the complete explicit
  bootstrap selectors and published local Pi metadata; creating a donor first
  is not required. For an existing partial deployment, repair its native
  `pi_providers`/`pi_provider`/`pi_model` selection deliberately, then rerun public `setup --prepare-only` (helper
  setup) without bootstrap flags; only the bounded missing-local-provider case can
  use public `setup --prepare-only --resume-setup` with complete matching selectors. No credentials are copied.
- `invalid_provider_selection`, `credential_copy_refused` or a symlink refusal:
  correct the selectors or use regular credential-free metadata paths, then
  preview again. These failures occur before preparation writes.
- `provider_override_refused`: omit bootstrap flags to preserve the existing
  target's selection. They cannot replace an existing selection; the explicit
  bounded resume fills only a missing local provider file.
- `validation_failed` with `error.mutated: true`: files may already be prepared,
  but validation did not pass. Inspect the native config, provider metadata and
  check failure; repair the cause and rerun public `setup --prepare-only` (helper `setup`) without bootstrap
  inputs (or non-activating `orbi check --config PATH`). Never run upstream
  `orbi setup`/`install-units` as routine preparation recovery. Use helper
  `status` to observe scheduler state separately, not `start` to repair metadata.
- `resume_refused`, `publication_conflict` or `target_changed`: preserve the
  conflicting files/concurrent change and follow the specific repair; never
  overwrite evidence or silently change selection or pin.
- `transport_mismatch`: deliberately repair deployment-local transport after
  inspecting origin/config; never rewrite origin as a preparation repair.
- `harness_conflict` or `harness_migration_required`: omit the selector to reuse
  saved/legacy routing; changing harnesses requires deliberate migration.
- `harness_drift`, `harness_unavailable` or `extension_env_mismatch`: inspect the
  persisted fields, owned launcher, executable and final extension environment;
  preserve evidence and deliberately repair the reported mismatch before activation.
- `env_value_unsupported`: use supported literal values and absolute colon-free paths.
- `credential_reference_missing` or `auth_unverified`: provision the exact named
  service env reference or existing user catalog/auth input separately. Do not
  expose values or treat a schema/key-presence check as inference.
- `prerequisite_missing`: install the named command (including selected pi-bolt
  or pi) separately; no sudo, automatic harness install or fallback is used.
- `bootstrap_unverified`: repair readable `uv tool list` evidence before writes.
- `file_encoding_invalid`: inspect the failed step and repair UTF-8 encoding
  privately, preserving original bytes and recovery inputs. Invalid native config
  encoding is reported as `config_invalid`.
- `filesystem_error`: inspect local permissions/files privately and repair the
  cause; the failure step may have partially mutated even though publication is atomic.
- `setup_busy`: cite observed timer/worker state and inspect with `status`.
  Offer authorized stop/drain only when deliberately re-preparing or pausing.
  Verify inactivity before setup; do not kill workers or stop scheduling just
  to make a preview pass. An existing valid start skips setup.
- `update_busy`: plain update requires stop/drain first, or use explicit
  `update --stop` to authorize the pause while preserving workers. Verify no service is
  active and no owned timer is enabled, then rerun `update`; never kill workers
  or disable an unrelated deployment to pass the check.
- `source_dirty`: preserve the tracked checkout changes in a separate operation
  and decide deliberately; update never discards them or rewrites origin.
- `sync_engine_source_failed` or `command_timeout` during `update`: the pin or
  checkout may already have moved and units may already be refreshed. Read
  `previous`, `steps`, `disabled_timers`, `error.mutated` and the read-only
  scheduler snapshot before deliberate recovery; inspect the fetch/channel
  privately and do not retry an unchanged timeout.
- `bootstrap_incompatible` or `bootstrap_conflict`: repair or replace the
  user-local Orbi bootstrap deliberately; never force-reinstall a shared tool
  as part of another deployment's start.
- `unit_conflict` or `ambiguous_deployment`: keep one task pool per repository
  and remove or repoint the duplicate config or unit ownership.
- `source_drift` or `pin_mismatch`: check out the configured pin explicitly.
- `setup_failed`, `install_units_failed`, `command_failed` or `command_timeout`
  during start activation, timer enable/disable or the first tick:
  upstream may already have activated timers or started workers. The error marks
  start activation as `possible`; stop retains confirmed disables. The receipt
  includes a read-only scheduler snapshot (or `unavailable`) and completed/failed
  steps. Inspect that evidence and the cause
  before recovery; never repeat activation unchanged or stop workers to undo it.
  Observation failure does not replace the original activation error.
- `scheduler_unavailable`: verify the systemd user session; status reports the
  same condition as unavailable evidence.

Offline tests and `doctor` do not qualify a live loop. Real issue pickup, PR,
independent review, required CI and protected merge remain live acceptance.

## Host round trips and evidence

The common path in `SKILL.md` is shared by Hermes and portable hosts. The host
LLM interprets intent/authority once; the ACTIONS-backed helper performs checks
and returns the receipt. Additional reasoning needs a concrete ambiguity,
missing prerequisite, unresolved gate or failed operation. A failed receipt is
an answer, not an instruction to retry or silently stop/repair/start.

### Host-required continuations

- Pi's explicit callback still uses `sendUserMessage`, queued as `followUp` while
  busy. It supplies the portable host contract and canonical workflow with their
  absolute source directories; no adapter executes or routes lifecycle commands.
- Claude Code and Codex load the explicit portable adapter, then any missing host
  contract/workflow together. They use the same common path, not a second router.
- Hermes registration still requests `skill_view` for the canonical skill. That
  discovery/tool boundary is not removed by this change.
- A host that requires a model request after instruction/tool results still owns
  those continuations. Relay the safe receipt minimally; do not add another
  interpretation, validation or prose-polishing pass. Direct tool-result return
  is conditional on host support, not a new API or a claimed tested capability.

Real observed model-request counts and host-required continuation counts are
**unknown** for Pi, Claude Code, Codex and Hermes: no live host traces were
collected. One `sendUserMessage`, a fake response or one helper process is not
one measured model call. Worker inference and independent review are unchanged,
not exercised by these fixtures and must be counted separately in live traces.

### Comparable offline boundaries

The Pi fixture matrix in `tests/portable_pi.test.mjs` invokes the real registered
callback with a fake message sink in both idle and busy contexts. Compared with
base `ed432d13d9f53348b3a2e9bcc466faf46e7dc93d`, in the same worktree under Node
22.22.2, each request dispatches once before and after. UTF-8 bytes below count
only Kit's command message, not system/history/tool wrappers or a full provider
request. Absolute source-path lengths affect these numbers.

| Literal request | Dispatch bytes before → after | Bytes after required instruction loads before → after |
| --- | ---: | ---: |
| bare | 1,316 → 14,110 | 21,004 → 14,110 |
| `status` | 1,322 → 14,116 | 21,010 → 14,116 |
| `help` | 1,320 → 14,114 | 21,008 → 14,114 |
| `setup --dry-run` | 1,331 → 14,125 | 21,019 → 14,125 |
| `start --dry-run` | 1,331 → 14,125 | 21,019 → 14,125 |
| `stop --dry-run` | 1,330 → 14,124 | 21,018 → 14,124 |
| `update --dry-run` | 1,332 → 14,126 | 21,020 → 14,126 |
| `update --config "/missing literal $(file).toml"` | 1,363 → 14,157 | 21,051 → 14,157 |
| `start or stop?` | 1,330 → 14,124 | 21,018 → 14,124 |

Dispatch is larger because instructions are supplied up front. The canonical
workflow is 8,262 rather than 15,912 bytes; branch detail stays in this reference.
The required extra instruction files drop from two (COMMON and canonical) to
zero on Pi. That removes the need for model-assisted reads, not two proven model
requests: a host could batch or cache reads. Shared policy/reference reads needed
by a concrete case remain possible. Ambiguous input is forwarded literally;
these tests do not prove that a real model asks the right clarification.

The public CLI receipt fixture in `tests/test_orbi_control.py` uses disposable
homes, a prepared target, an unrelated deployment and fake external tools. The
same CLI requests against the base and current helper each use **one helper
invocation**. External tool subprocess counts before → after are: bare/status
32 → 32 each; help 0 → 0; setup/start previews 33 → 33 each; stop preview 32 → 32;
update preview 36 → 36; failed busy update 35 → 35. These are helper-internal
checks, not model calls or host tool invocations. No checks were removed. Routine
previews return `planned`; busy update exits nonzero with `update_busy`,
`mutated: false` and the repair action to request a separately authorized
stop/drain and verify inactivity. No implicit mutation or retry follows.

The workflow removes routine duplicate host discovery/status probes, help
lookups, separate setup before absent start, preview-then-apply sequences,
polling and validation/paraphrase passes. This is an instruction/dispatch
contract with synthetic boundary evidence, **not a measured live round-trip or
latency saving**. Live qualification must record actual provider requests,
host tools, prompt bytes, mandatory continuations and worker inference separately
for the same authorized success/failure fixtures, without releasing live gates.
