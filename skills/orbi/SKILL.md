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

`/orbi [status|setup|start|stop|help]` runs
`python3 -B <this-skill>/scripts/orbi_control.py` with the same action and
`--repo-dir PATH --config PATH --dry-run --json`. For a new deployment, setup
also accepts `--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]`.
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

## Steps

1. **Bind the repository.** Resolve the canonical checkout (the main worktree,
   not a delivery worktree) and its GitHub origin. Read the native deployment
   config and installed unit ownership. A repository with no deployment is
   `absent`, not an empty queue.
2. **Status.** Run `status` (or `status --json`) for the deployment state,
   pinned source, shared bootstrap, provider metadata, target timers, service
   states and ready queue. Distinguish configured slots, enabled timers, active
   timers and running service units: shared template availability is not instance
   enablement. Report, for example, “3 configured slots, 3 enabled timers; observed
   instances 1–5,” not “5 installed slots.” Counts are local scan evidence, not
   deployment health or model/delivery proof. Status is read-only; missing evidence
   is `unavailable`.
3. **Prepare.** Run `setup` (preview with `--dry-run`). It stages the verified
   pinned source, atomically publishes provider metadata and `.orbi/env` before
   publishing the native config last, and validates with a non-activating `orbi check`.
   Before locks or deployment writes it checks transport, ownership, inactive/no-worker
   evidence and available prerequisites. A missing bootstrap also requires readable
   `uv tool list` conflict evidence and records interpreter selection; absent/older
   system Python selects uv provisioning of `3.14`, not a prerequisite blocker.
   Provisioning/network success and staged validation cannot be promised by preflight. For the first deployment, supply
   `--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]`
   using published metadata from Pi's local catalog, not authentication files.
   Without these flags, setup reuses verified metadata from a visible deployment.
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
   checks does not release them. It re-reads ownership, source, provider and
   prerequisite evidence, runs the supported
   upstream `setup`/`install-units` with the scoped environment, enables only
   this deployment's timers and requests one first tick when no worker runs.
5. **Stop.** Run `stop` to disable only this deployment's owned timer instances,
   including observed out-of-config instances. Active services finish: report
   `draining` with the pending units until they stop. Missing service evidence
   is `unavailable`, never `stopped`. Never kill, stop or restart a service to
   make the state look clean.
6. **Report evidence.** Name the repository, deployment, unit, pin, source and
   scheduler states you actually read, and the commands you ran. Keep provider
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
- An existing pin is upgraded, a credential is copied, or a literal
  credential is written into provider metadata.
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
- Not an implementation coordinator or a fallback to the retired runner.
- Not a cross-machine lock or capacity guarantee: visibility covers local
  deployments; report remote ownership as unavailable.

Load [lifecycle reference](references/lifecycle.md) for the interface,
discovery rules, isolation variables, pinned source, ownership bounds and
partial-failure recovery. The standing [Definition of Done](../shared/DEFINITION-OF-DONE.md)
applies beyond this task's acceptance.

**Done when:** the named deployment's state and the evidence behind it are
reported, and every mutation was limited to that repository with its active
workers preserved.
