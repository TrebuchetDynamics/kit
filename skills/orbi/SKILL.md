---
name: orbi
description: "Prepare, start, inspect or stop one Orbi deployment."
license: MIT
---

# Orbi

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and the
[shared communication rules](../shared/COMMUNICATION.md) within this workflow's
scope, guided by the [GitHub-native contract](../../docs/github-native.md). This skill is a lifecycle
client for one repository's Orbi deployment: it is not an executor,
queue, daemon or second scheduler.

`/orbi [status|setup|start|update|stop|help]` runs
`python3 -B <this-skill>/scripts/orbi_control.py` with the same action and
`--repo-dir PATH --config PATH --dry-run --json`. For a new deployment, `setup`
and an authorized absent-target `start` also accept `--harness {pi-bolt,pi}` (default: installed Pi-Bolt) and
`--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]`.
Legacy missing-provider recovery additionally requires explicit `--config PATH
--resume-setup` and those complete matching selectors; it cannot change a selection.
The default action is
`status`; never run bare `orbi`, which is the Runner's one-tick entry. Use the
helper, not hand-written `systemctl`, unit files or `orbi setup` commands.

**Help first.** For a help or command-inventory request, run the helper's `help`
action and report the observed output instead of composing a reference from
memory. Help needs no repository or deployment and works on every platform;
it accepts and ignores `--repo-dir`, `--config`, `--dry-run` and setup inputs. Do not bind a
repository or read deployment state for this route. Use the steps below for
lifecycle actions.

## Intent and state: fast path

| Owner intent / observed state | Meaning and next safe action |
| --- | --- |
| Help / command inventory | Run context-free `help`; do not inspect a repository or GitHub. |
| Start; genuinely absent deployment, no explicit config | Once scheduling authority and applicable gates are resolved, `start` prepares, validates non-activating, then activates in **one invocation**. No separate setup or repeated approval is needed. |
| Preview first start | `start --dry-run` is write-free preparation preview only. Staging-dependent validation and activation checks remain deferred; success is not authorization. |
| Start; valid existing target | Skip setup; retain saved provider/harness/pin and omit bootstrap selectors. A missing explicit config, partial or foreign target is **not absent**: inspect and repair deliberately. |
| Enabled/active owned timer; no observed running workers | Scheduling is active, but no worker was observed. Do not call it stopped or say setup is needed. Missing evidence or activity outside the scan is unknown, not zero. |
| `setup_busy` | Cite observed timer/worker state and use `status` to inspect. Offer authorized stop/drain only when deliberately re-preparing or pausing, not just to make a preview pass. |
| Start; gate evidence missing/unknown | Preserve the settled owner request. Name the exact missing check, applicable checklist or located record (or say no record was found), and the next safe read-only evidence check or owner action. Do not request a generic cutover record or invent approval. |

Before an actual start, separate **owner scheduling intent** from **deployment-specific
gate evidence**. Use the [activation evidence guidance](references/lifecycle.md#activation-evidence)
to report the precise blocker, including unprotected-main versus access-error
observations. Evidence collection is read-only; a preview does not clear a pause.
The [offline examples](references/lifecycle.md#offline-guidance-examples) show first-start
and active-scheduler recovery without touching real hosts.

## Steps

1. **Bind the repository.** Resolve the canonical checkout (the main worktree,
   not a delivery worktree) and its GitHub origin. Read the native deployment
   config and installed unit ownership. A repository with no deployment is
   `absent`, not an empty queue.
2. **Status.** Run `status` (or `status --json`) for the deployment state,
   pinned source, selected harness/executable evidence, shared bootstrap, provider
   metadata, target timers, service states and ready queue. Distinguish configured
   slots, enabled timers, active timers and running service units: shared template
   availability is not instance enablement. Report, for example, “3 configured slots,
   3 enabled timers; observed instances 1–5,” not “5 installed slots.” Counts are local
   scan evidence, not deployment health or model/delivery proof. Status is read-only;
   missing evidence is `unavailable`.
3. **Prepare.** Run `setup` (preview with `--dry-run`). It stages the verified
   pinned source, atomically publishes provider metadata, the deployment-local
   `.orbi/harness-bin/pi` exec launcher and `.orbi/env` before
   publishing the native config last, and validates with a non-activating `orbi check`.
   Before locks or deployment writes it checks transport, ownership, inactive/no-worker
   evidence and available prerequisites. A missing bootstrap also requires readable
   `uv tool list` conflict evidence and records interpreter selection; absent/older
   system Python selects uv provisioning of `3.14`, not a prerequisite blocker.
   Provisioning/network success and staged validation cannot be promised by preflight. For the first deployment, supply
   `--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]`
   using published metadata from Pi's local catalog, not authentication files.
   Without these flags, setup reuses verified metadata from a visible deployment.
   New preparation defaults to Pi-Bolt; explicit `--harness pi` selects stock Pi.
   Resolve the installed command before writes; missing means install it separately,
   never fallback or automatic installation. Repeated setup reuses managed selection;
   conflicting selectors refuse, and legacy deployments remain unmanaged/unmigrated.
   Declared key/header references must be nonempty in persisted deployment env and
   compatible final extension env, not merely the shell. This is
   `references_available`, not authentication or inference. Without references,
   use the selected target's non-refreshing stored-auth check in the pinned auth home;
   missing provider/catalog/auth input holds as `auth_unverified`.
   Incomplete selectors, invalid metadata, literal credentials and symlink paths
   are refused before writes. Bootstrap flags cannot override an existing target;
   omit them to reuse its selection. The sole exception is explicit bounded
   `--resume-setup` for a legacy missing deployment-local `.orbi/pi-providers.json`:
   require the exact saved provider/model/reasoning, official supported pin, local
   ownership and inactive/no-worker evidence; omitted thinking inherits the saved value.
   It fills only an absent provider, or reuses identical bytes on repetition. Present
   conflicting/invalid files, external paths and changed pins need deliberate repair.
   New configs preserve the verified origin's
   SSH/HTTPS transport without rewriting remotes. It reports `prepared` with
   `activated: false`; it never installs or enables a timer. This means setup invoked
   no activation, not proof of scheduler inactivity; report scheduler observations separately.
   Existing transport mismatch requires deployment-local config repair, never an origin rewrite.
4. **Start.** Run `start` only after the owner asks for scheduling and existing
   explicit pauses, cutover requirements and human-only gates are resolved for
   that deployment. Orbi remains paused and live-unqualified until its separate
   gates permit the requested operation; installing this skill or passing offline
   checks does not release them. If no deployment exists and no explicit `--config`
   was supplied, it first runs the same non-activating preparation as `setup`, with
   Pi-Bolt by default or explicit `--harness pi`, and complete provider selectors
   (or verified donor metadata). No extra setup invocation or approval question is
   needed for this already-authorized start. An existing valid/active target skips
   preparation; omit all bootstrap/harness selectors to retain its saved selection.
   Missing explicit configs, malformed/foreign/ambiguous/partial targets are not
   absent: preserve evidence and use deliberate setup/repair, never automatic resume.
   Start re-reads the exact prepared config and revalidates repository, file identities,
   ownership, source, provider, harness and prerequisites under the activation lock.
   Its `preparation.state` is `skipped`, `planned`, `prepared` or `failed`. Preparation
   failure prevents activation; later failure retains preparation success and mutation
   evidence. An absent `start --dry-run` previews preparation only and explicitly defers
   staging-dependent validation/activation checks; it does not report those gates passed.
   An existing target previews configured-slot activation normally. Managed activation refuses drifted metadata/launcher,
   missing harness targets, incompatible final extension PATH/HOME/agent-directory overrides
   and inherited auth-home mismatches. It runs the supported
   upstream `setup`/`install-units` with the scoped environment, enables only
   this deployment's timers and requests one first tick when no worker runs.
5. **Update.** Run `update` for one prepared deployment after an authorized
   `stop`/drain. It requires verified inactivity and refuses a live worker or an
   enabled timer (`update_busy`), and it refuses tracked checkout changes before
   any write (`source_dirty`). It writes the upstream `release` channel, runs
   upstream `sync-engine-source` to resolve and check out the newest official
   release, then locks that commit as `sha:<commit>`. It validates with the
   non-activating `orbi check`, refreshes this deployment's installed units
   through `orbi install-units`, and disables the timers that install enabled, so it
   restores the verified inactive state and names every timer in
   `disabled_timers`. Origin, provider, harness, slots and unrelated config bytes
   are preserved. Report `updated`, or `up_to_date` when the release commit did
   not move; both refresh units. An `update --dry-run` previews the plan
   write-free. Rollback is a deliberate owner edit of `engine_source_track`;
   scheduling again stays the separate authority of `start`.
6. **Stop.** Run `stop` to disable only this deployment's owned timer instances,
   including observed out-of-config instances. Active services finish: report
   `draining` with the pending units until they stop. Missing service evidence
   is `unavailable`, never `stopped`. Never kill, stop or restart a service to
   make the state look clean.
7. **Report evidence.** Name the repository, deployment, unit, pin, source and
   scheduler states you actually read, and the commands you ran. Include
   `deployment.harness`: configured selection and resolved-now executable identity
   are not proof of what a running worker uses. Status performs no harness/auth
   probe and invents no version. Absent means unconfigured; Pi-Bolt is only the new
   setup default. Legacy service resolution is unknown without a stored PATH. Keep provider
   identifiers and non-secret evidence only. Report preparation, scheduler
   activation and live delivery separately. One deployment/pool may have several
   slots; template-only rows do not establish a duplicate pool or a scheduling
   defect. Compare native config, explicit enablement and observed activity first;
   never enable 4/5 merely to match the scan bound. Use read-only status to observe:
   `setup --dry-run` is preparation preflight and `setup_busy` is an expected
   refusal while scheduling/workers are active, not evidence of extra instances.
   Any repair still needs separate scope/authority. If non-activating validation fails
   after writes, inspect and repair the partial deployment, then rerun helper
   `setup` without bootstrap flags. Do not use activating upstream setup as a
   preparation repair; inspect scheduler state with `status`. Read `steps`, `target`,
   `original_error` and `error.mutated`: lock writes count, and a failed mutating
   attempt is `mutation: possible`, not verified completion. A killed process cannot
   render a receipt; retry safety comes from actual complete/absent files. Preserve
   recovery evidence and never automatically retry an unchanged timeout.
   Start/stop failures can be partially applied: read completed/failed units,
   confirmed `activated_timers`/`disabled_timers` and the read-only scheduler
   snapshot (or `unavailable`). Start `activation: possible` is not success;
   `activation: none` may still include lock writes. Failed attempts are not
   confirmed completions. Inspect `status` before deliberate recovery; do not
   compensate with timer changes or stop workers after failure.
   If the installed helper lacks these flags, report its absolute loaded path and
   available Kit revision and recommend a separately authorized skill update. A stale
   installed skill is not an unsupported transport or a reason to rewrite origin.

Use `status` on macOS; lifecycle mutations there are refused before any side
effect. Linux is the only mutation platform in this version.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "I remember the commands, so I can compose the help table." | Run the helper's `help` action and report its observed output; memory is not the authoritative reference. |
| "Setup already installs units, so enabling now is harmless." | Upstream setup and install-units enable timers at this pin. Setup must leave scheduling inactive until an explicit start. |
| "A second deployment is easy; more slots deliver faster." | One repository has one task pool. A duplicate pool causes double claims; the helper refuses ambiguous matches and unit conflicts. |
| "PYTHONPATH isolates the source, so the uv tool dir can stay shared." | A first tick or packaging change can reinstall the shared tool and change another deployment's launcher. Set `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` with `PYTHONPATH`. |
| "Stopping the service guarantees the work is done." | Stop owns timers only. A pre-existing invocation may finish; report `draining` and remaining review/merge work. |
| "`orbi doctor` warns about enforced admins, so relax protection." | The warning describes the merge identity, not a protection defect. Keep enforced admins, strict CI, independent review and human acceptance. |
| "The queue is empty because the status read failed." | A failed read is `unavailable`. Use the read-only doctor plus explicit `gh` and scheduler reads; never invent an empty queue. |
| "A missing launcher is ours to force-reinstall." | The units use the shared user bootstrap. Verify it and fail closed; repairing another deployment's launcher is not this command's scope. |
| "Update is setup again, so it can skip the drain." | Update moves the engine commit and re-renders units. A live worker would run mixed code, so it refuses `update_busy` until a stop leaves verified inactivity. |

## Red Flags

- A setup or dry-run activates scheduling through `orbi setup`, `install-units`,
  `systemctl enable`, `enable --now`, or writes labels.
- Status or dry-run runs `uv tool install`, `git fetch`/`clone`, or creates
  locks or receipts. Authorized setup may stage source, lock its deployment and
  install a missing, non-conflicting bootstrap; it never fabricates
  `.orbi/cli-install.json`.
- A command runs bare `orbi` with no named subcommand, or assembles commands
  through a shell string instead of an argv list.
- The target config or `.orbi/env` was rewritten while another deployment or a
  live worker was observed.
- `PYTHONPATH` is set without the deployment-local `UV_TOOL_DIR` and
  `UV_TOOL_BIN_DIR`, or those values differ between `.orbi/env` and a
  helper-launched command.
- A unit is disabled or stopped without proving it belongs to this deployment,
  or a service is stopped, killed or restarted by `stop`.
- Status or dry-run writes a file, locks, fetches or changes a label.
- An existing pin is upgraded by `setup`, a credential is copied, or a literal
  credential is written into provider metadata.
- `update` ran with a live worker, an enabled timer or tracked checkout changes,
  or it left timers enabled without naming them in `disabled_timers`.
- `update` rewrote origin, provider or harness selection instead of reporting it.
- The platform is macOS or unsupported and a mutation still ran.
- A secret, token, `auth.json`, private identity or raw child stderr appears
  in a command, receipt, Issue or PR.

## Boundaries

- Not an executor or scheduler: it never runs a tick, claims an issue, reviews
  or merges. Use the deployment's scheduler and the GitHub delivery loop.
- Not `/unblock`: recovery and interrupted-work repair follow
  [service boundaries](../unblock/references/services.md).
- Not `/git-commit-push`: it does not commit, push or open a PR for the
  repository it manages.
- Not `/plan-with-me` or `/plan-for-me`: planning authorizes no live service
  change.
- Not `/update-kit`: `update` moves one deployment's engine release; it never
  refreshes Kit, reinstalls this helper or relaxes a live gate.
- Not an implementation coordinator or a fallback to the retired runner.
- Not a cross-machine lock or capacity guarantee: visibility covers local
  deployments; report remote ownership as unavailable.

Load [lifecycle reference](references/lifecycle.md) for the interface,
discovery rules, isolation variables, the pinned and release source channels,
ownership bounds and partial-failure recovery. The standing [Definition of Done](../shared/DEFINITION-OF-DONE.md)
applies beyond this task's acceptance.

**Done when:** the named deployment's state and the evidence behind it are
reported, and every mutation was limited to that repository with its active
workers preserved.
