---
name: orbi
description: "Set up, inspect, update, stop or prune Orbi deployments."
license: MIT
---

# Orbi

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[shared communication rules](../shared/COMMUNICATION.md) within this workflow's
scope. The [GitHub-native contract](../../docs/github-native.md) owns delivery
gates. This skill is a lifecycle client, not an executor.

## Intent and state: fast path

| Owner intent / observed state | Meaning and next safe action |
| --- | --- |
| Setup (default) or start; genuinely absent deployment, no explicit config | `start` prepares, validates non-activating, then activates in **one invocation** if technical checks pass. No separate setup or repeated approval is needed. |
| Preview setup/default start | `setup --dry-run` maps to `start --dry-run`: write-free preview of preparation then activation. Staging-dependent validation and activation checks remain deferred; success is not authorization. |
| Setup (default) or start; valid existing target | Retain the saved provider/harness and omit bootstrap selectors. If current with all configured timers enabled and active, report `already-running` without changes. Otherwise stop owned work as needed, sync/pin/check, repair units and start scheduling. A missing explicit config, partial or foreign target is **not absent**: inspect and repair deliberately. |
| Enabled/active owned timer; no observed running workers | Report scheduling active with no worker observed. Activity outside the scan is *unknown*. |
| `setup_busy` | Cite observed timer/worker state and use `status` to inspect. Offer authorized stop only when deliberately re-preparing or pausing, not just to make a preview pass. |
| Activation check fails or cannot be verified | Name the failed technical check and give the next read-only check or exact repair. Report the deployment as prepared, not started. |

## Common path

Keep the host LLM: interpret the current request once, using the conversation's
scope, restrictions and authorization. No separate model routes, validates, polls
or paraphrases a routine command. Extra reasoning or clarification requires a
concrete unmet need, not a fixed sequence of model turns. Each action's authority,
call and completion live in its own section below; these steps apply to all of them.

1. **Resolve intent.** `/orbi [status|version|setup|start|update|stop|prune|help]`
   and `/orbi set DEPLOYMENT ...` use
   `python3 -B <this-skill>/scripts/orbi_control.py` with the mapping below on **every host**.
   These are public skill arguments, not direct Python helper syntax; all unlisted
   actions pass through unchanged.

   | Public skill arguments | Helper arguments |
   | --- | --- |
   | `status all [--work] [--verbose\|--json]` | `status all [--work] [--verbose\|--json]` |
   | `update all [--wait-minutes MINUTES] [--dry-run] [--json]` | Pass through unchanged |
   | `set DEPLOYMENT slots N` | Pass through unchanged |
   | `set DEPLOYMENT model PROVIDER/MODEL [THINKING] [--allow-metered]` | Pass through unchanged |
   | `setup` | `start` |
   | `setup --dry-run` | `start --dry-run` |
   | `setup --prepare-only` | `setup` |
   | `setup --prepare-only --dry-run` | `setup --dry-run` |
   | `setup --prepare-only --resume-setup` | `setup --resume-setup` |

   Remove only `--prepare-only` for public setup; preserve all other supported
   arguments literally, regardless of flag order. Never add `--allow-metered` on the
   operator's behalf. `--prepare-only` is public
   setup-only: reject it on other actions, never forward it to the helper.
   Reject `setup --resume-setup` before invoking the helper unless `--prepare-only`
   is explicit; give the corrected `setup --prepare-only --resume-setup` command
   retaining the supplied config/provider arguments and dry-run. Direct Python
   helper `setup` remains non-activating for automation and recovery.

   Bare `/orbi` means `status`. **Help first.** For help requests, run only help.
   For lifecycle commands, go directly to the requested action.
   Return observed output from the helper's `help` for help or command inventory;
   it needs no repository, config, environment or scheduler reads.
   `all`, `prune` and `set` forms run from any directory with no injected
   `--repo-dir` or `--config`. For other repository lifecycle actions, use the
   requested repo/config or known current checkout; `update --config PATH` without
   `--repo-dir` lets the config select its checkout.
   The helper resolves the canonical worktree and verifies GitHub origin,
   deployment discovery and unit ownership; leave those reads to it.
   If target or intent is genuinely ambiguous, ask one focused question before
   mutation. Never run bare `orbi` (the Runner's one-tick entry), guess a typo
   alias or silently select an action.
2. **Authorize.** Preserve read-only/no-write restrictions and literal `--dry-run`.
   Explicit `/orbi start`, plain `/orbi update`, and `install.sh` with Orbi selected
   authorize activation; `update all` only restores previously running scheduling.
   Require verified unit and file ownership, a validated
   release pin and a passing `orbi check`; do not ask for a cutover record or
   separate approval. Public `setup` has the same authority as `start` because it
   maps to it. `setup --prepare-only` and dry-run never activate.
   The helper runs the [deployment-scoped check](references/lifecycle.md#activation-evidence)
   before activation; no separate check or dry-run validation call is needed.
   See [offline examples](references/lifecycle.md#offline-guidance-examples)
   for precise refusals. Do not silently fall back to preparation.
   Explicit `stop`, `set` and `prune --apply` authorize only their own section's
   effects. Other mutations require their own accepted scope. Offline checks grant none.

   Branch protection is not a Kit setup/start prerequisite: known unprotected branches
   and protection/rules HTTP 403 are informational, not scheduling blockers. Skip any
   PR-only, opt-in, protection-change, paid-plan or second-approval demand on that
   basis; authentication, repository access, ownership and other technical checks still apply.
3. **Invoke once.** Preserve literal argument values, quoting, paths, provider/model
   IDs, `--config`, `--repo-dir` and all restrictions. Build argv, never interpolate
   user text as shell code; shell-only hosts must safely quote every argv element.
   After the public mapping, pass supported flags unchanged; add a known `--repo-dir`
   only when needed to bind the requested repository. Use text output for `status`
   and `help`, and `--json` for mutating receipts, unless the request names a format.
   Keep `--dry-run` exactly as requested, keep path shell substitutions literal,
   and copy no credentials. The existing ACTIONS-backed helper owns deterministic
   checks and action composition.

   No routine pre-status, help lookup, extra setup, preview-then-apply, polling or
   post-validation call. Helper ownership, safety, authentication and evidence
   checks still run. Missing prerequisites are repair inputs, not authority to
   install/login. Linux is the only mutation platform; macOS supports status/version/help.
4. **Relay receipt.** Return the helper's safe result directly wherever the host
   supports it. If a tool-result model turn is mandatory, relay only observed facts;
   no new plan or paraphrase pass. Lead with target and outcome, then a next action
   only when needed. Relay `error.fix` and any exact `repair_command`; never guess
   selectors or shorten bound recovery commands. Failed quiesce blocks engine sync;
   disabled timers alone do not prove workers stopped or the engine updated. A
   `prepared` receipt with `activated: false` does not prove scheduler inactivity.

   Two evidence words govern every receipt. *Unknown*: missing, failed or
   out-of-scan evidence stays unknown with its reason; it is never zero, idle,
   empty, stopped or absent. *Live delivery*: exit success, activation,
   version/source, harness and doctor evidence, first-tick requests, ready order,
   labels and open PRs are evidence of their own step only;
   none qualifies live delivery or worker completion.

   Keep structured evidence available: errors, `error.fix`, `error.mutated`,
   completed/failed `steps`, disabled timers, stopped workers, `preparation`, `activation` and
   scheduler uncertainty. A short summary must still show partial mutation. For partial
   mutation or activation, use [partial failure and recovery](references/lifecycle.md#partial-failure-and-recovery).
   Preserve the nonzero timer error, `recurring_scheduling: incomplete`, `first_tick`
   and `first_tick_evidence` from the helper's guarded first-tick recovery. Never
   retry the timer or configure later slots.
   Never expose credentials, auth files, environment values or raw child stderr.
   On failure, relay the helper's safe error and repair action. No blind retry,
   implicit repair, timer changes or worker stops outside the helper. An unchanged
   timeout is not retryable; killed processes have no receipt.

## Status

`status` (also bare `/orbi`) reads once: no tick, fetch, poll, repair,
activation, session/env dump or implicit installed-helper update. Status never
invokes [`/unblock`](../unblock/SKILL.md), changes labels, requeues or repairs branches.

**Done when** the receipt leads with the repository, deployment-bound package
version/revision and provenance, scheduler state, each observed slot and the queue.
Relay `.worktrees/` disk use per deployment, or the reason it could not be measured.
Relay `last_lifecycle` as the last recorded Kit helper action, not proof of the
current scheduler state. Relay `deployment.engine` separately from selected
source/pin and `bootstrap_cli`: a matching CLI version is unverified runtime
evidence; a mismatch never replaces the deployed version. Missing, modified or
unpinned package/revision metadata leaves the version unknown.

`activity.slots` distinguishes running (issue number/title/link, run ID and observed
phase/last activity), verified idle, starting, draining and unknown identity.
Missing live bindings mean **active/issue unknown**, never idle or the newest retained
issue. A missing title stays unknown. For slot attribution or uncertain worker identity,
see [stop, status and drain](references/lifecycle.md#stop-status-and-drain).
An activating service is transitional: report it as neither idle nor issue pickup.

Keep configured slots, enabled/active timers, running services and verified working
issues as separate observations. Preserve unavailable counts, scan limits,
health and last/next tick evidence. Unavailable counts are unknown, not zero.
For Linux inventory interpretation, see
[scheduler inventory](references/lifecycle.md#interpreting-linux-scheduler-inventory).

### Pending queue evidence

Status reports the verified ready queue and grouped open pending issues: actionable
blocker, active/owned, native dependency, planning/paused, epic coordination, ready
and unknown. Zero ready is not zero pending. Relay each issue's number/link,
evidenced reason, next action and observed PR/native prerequisite. Ready issues are
not claimed. Ready order, labels, progress and PR records never prove pickup or
liveness. Planning input stays explicitly unknown when not evidenced; report only
evidenced decisions and dependencies, never ones inferred from ordering.

Partial reads report observed lower bounds. For incomplete queue coverage or
`retry_safe=false` recovery, see
[pending issues and read coverage](references/lifecycle.md#pending-issues-and-read-coverage).
Idle services with ready work call for inspecting scheduler/ownership evidence and
existing pauses; activation needs its own explicit command.

### Host inventory

`status all [--work] [--verbose|--json]` runs as one helper invocation from any
working directory. The helper reads the GitHub API budget; pass `--work` only when
requested for per-repo issue counts. Relay the helper's rows as-is: compact
deployment rows by default, per-unit text with `--verbose`, or structured inventory
with `--json`. Run no separate GitHub probes and leave its no-work suggestions
unactioned. Reject
conflicting selectors before probes. Relay partial coverage, unavailable GitHub data
and observed totals as a lower bound for the host.
For interpretation, see [host inventory](references/lifecycle.md#host-inventory).

## Start and setup

`start` and public `setup` share one activation path (see the fast path above).
New setup or an absent start accepts installed `--harness {pi-bolt,pi}` (default
Pi-Bolt) and complete `--pi-providers PATH --pi-provider ID --pi-model ID` with
optional `--pi-thinking LEVEL`. Reuse existing selections without bootstrap flags.

**Done when** the receipt shows `already-running`, or `activation: started` with
configured timers enabled and active. A held or failed activation names its
blocker and repair; report it as prepared, not started.

## Update

Plain `update` stops owned work, syncs and validates the engine, then requests
scheduling, even after an earlier `stop`. Choose the variant from the request:

| Request | Workers | Done when |
| --- | --- | --- |
| `update` | Stopped through systemd after timers are disabled | `engine_update` is `updated` or `up_to_date` and `activation: started` |
| `update --stop` | Stopped as above | Engine validated and `activation: held` with reason `explicit --stop` |
| `update --wait` | Finish naturally for up to 30 minutes | As plain `update`; on `update_busy`, scheduling stays paused with no engine change, so relay the bound command to rerun after work finishes |

A `sync_unverified` engine result means source may have changed without
validation; relay it with the bound recovery command.
For lock, ownership and sync detail, see [release update](references/lifecycle.md#release-update).

### Fleet update

Forward literal `update all` from any directory with only its listed flags.
The helper discovers the same local configs as `status all` and uses each config's
own checkout. It lets workers finish without stopping them and restores verified
running or stopped scheduling after a successful update or a drain timeout. The
shared drain budget is 120 minutes unless `--wait-minutes MINUTES` is supplied.
Relay each deployment's version, scheduling and drift, including pending rows and
their bound repair commands. See [fleet update recovery](references/lifecycle.md#fleet-update).

## Stop

Explicit `stop` disables owned timers, cancels verified queued starts and stops
owned workers through systemd. It preserves attempts, worktrees and recovery
inputs; there is no direct kill or restart.

**Done when** the receipt reports `stopped` with its `disabled_timers` and
`stopped_services`. Any other result is partial: relay it through step 4.
Scheduling resumes only through explicit `start`, plain `update` or an installer
refresh that selects Orbi. For quiesce detail, see
[stop, status and drain](references/lifecycle.md#stop-status-and-drain).

## Prune

Forward `prune [--apply] [--json]`. On Linux, preview is the default. Both modes
fetch the configured base for worktree checks; only explicit `--apply` removes
verified finished task worktrees and stale unloaded user templates. Relay why
worktrees stayed and the estimated bytes freed. See
[prune safety checks](references/lifecycle.md#prune).

## Change slots or model

```text
/orbi set sdrhf slots 1
/orbi set sdrhf model PROVIDER/MODEL [THINKING] [--allow-metered]
```

Select a prepared local deployment by a unique unit name prefix, repository
name, or path to its `orbi.toml`. Use the exact config path if a name is
ambiguous. Slots must be a positive integer from 1 to 5, the supported Orbi
scheduler range. Use a provider and model already listed in that deployment's
Pi metadata; an unknown model is refused before any writes. Omit `THINKING` to
keep the saved value, or pass `off`, `minimal`, `low`, `medium`, `high`, `xhigh`,
or `max`.

A move from a subscription provider to a metered provider (such as OpenRouter)
requires explicit `--allow-metered`. It also applies to an explicit metered
provider on first setup/start. A deployment's optional `allowed_providers`
list in `orbi.toml` still applies, even with the flag. Status marks metered models.
See [provider selection policy](references/lifecycle.md#provider-selection-policy).

Like `update --wait`, `set` pauses owned timers and gives workers up to 30 minutes
to finish without stopping them. If they don't finish, scheduling stays paused and
the config is unchanged. Under the same lifecycle lock, the helper saves the old
config as `orbi.toml.bak-<UTC timestamp>` beside the config before replacing it
atomically. It validates the new config and starts only its configured timers,
without syncing or changing the engine pin. The receipt shows old and new values
and the backup path. If applying fails after the write, preserve the backup and
inspect the failed step before retrying; there is no automatic rollback.

## Deployed engine version

`version [--repo-dir PATH] [--config PATH] [--json]` reads only the selected
deployment identity and engine evidence on Linux/macOS. Pass `version` unchanged
in one helper invocation. It does not run full status, bootstrap, scheduler, worker,
queue, authentication or network probes, acquire a lock or write files. There is
no `version all`; mutation/bootstrap selectors (including `--dry-run`) are refused.
No deployment means unconfigured. An observed revision is not a verified release;
unverifiable pin, manifest or clean source means unknown with a reason.

## Exceptional paths

The [lifecycle reference](references/lifecycle.md) owns detailed discovery, isolation
and action semantics. Do not preload it for routine commands. Load only the relevant branch:

- For missing provider inputs, use [provider bootstrap](references/lifecycle.md#first-deployment-provider-bootstrap).
- For missing or conflicting harness evidence, use [harness selection](references/lifecycle.md#harness-selection-and-evidence).
- For explicit legacy `--resume-setup` or an installed-helper flag mismatch, use
  [bounded resume](references/lifecycle.md#explicit-bounded-legacy-resume). For a stale
  helper, report its absolute loaded path and available Kit revision; recommend a
  separately authorized Kit update/reload, never an origin rewrite or activating upstream setup.
- For ownership ambiguity, use [discovery limits](references/lifecycle.md#ownership-and-discovery-limits).
- For partial mutation or deliberate repair, use [recovery](references/lifecycle.md#partial-failure-and-recovery).

For host/fixture measurement limits, use the reference's
[round-trip evidence](references/lifecycle.md#host-round-trips-and-evidence).

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "One more model should route or rephrase this." | Interpret once; the helper owns checks, and its safe receipt is the answer. Host-mandated continuations only relay it. |
| "I remember help, so I can compose the table." | Run the helper's `help`; report observed output. |
| "Release maintenance needs a separate stop command." | Release maintenance verifies inactivity before syncing. Explicit `--wait` drains without interrupting workers. |
| "A passing preview authorizes activation." | Only an explicit activating command authorizes it; previews perform no activation. |
| "The command failed, so nothing changed and retry is safe." | Preserve mutation/activation evidence and repair deliberately; failure can be partially applied. |
| "The queue is empty because the status read failed." | Failed reads are unavailable; partial reads disclose gaps. Zero verified ready is not zero pending. |
| "Activating plus an open PR proves progress." | Activating is transitional, not pickup. An open PR is not successful delivery; preserve existing ownership and recovery inputs. |

## Red Flags

- Extra routing/validation/paraphrase models, routine polling or duplicate host probes.
- A guessed alias, shell interpolation, changed literal selectors or removed dry-run.
- Prepare-only/dry-run enables timers, status writes, or stop/update kills/restarts a service.
- Update syncs before fresh idle/no-pending-start evidence, activates before engine
  validation or with unverified ownership, or reports stopped from missing evidence.
- Missing ownership/authorization, silently changed pin/provider/harness/origin,
  or an automatic install/login/repair/retry after a refusal.
- An empty queue or stopped state inferred from unavailable evidence, or secrets
  and raw child stderr exposed in a receipt.

## Boundaries

- Not an executor/scheduler: no tick, claim, review or merge. No worker-inference
  or independent-review reduction.
- Not `/unblock`: recovery follows [service boundaries](../unblock/references/services.md).
- Not `/git-commit-push`: no commit, push or PR for the managed repository.
- Not `/plan-with-me` or `/plan-for-me`: planning grants no live service authority.
- Not `/update-kit`: update moves deployment engines, not Kit or this helper.
- Local visibility only: no cross-machine lock or global capacity guarantee.

The standing [Definition of Done](../shared/DEFINITION-OF-DONE.md) applies beyond
this task's acceptance.

**Done when:** the helper's observed state or precise refusal and evidence are
reported, with only authorized scoped mutations and recovery inputs preserved.
