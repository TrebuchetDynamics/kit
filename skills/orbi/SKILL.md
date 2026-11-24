---
name: orbi
description: "Prepare, start, inspect or stop one Orbi deployment."
license: MIT
---

# Orbi

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[shared communication rules](../shared/COMMUNICATION.md) within this workflow's
scope. The [GitHub-native contract](../../docs/github-native.md) owns delivery
gates. This skill is a lifecycle client with read-only local host inventory, not an executor.

## Intent and state: fast path

| Owner intent / observed state | Meaning and next safe action |
| --- | --- |
| Setup (default) or start; genuinely absent deployment, no explicit config | Once scheduling authority and applicable gates are resolved, `start` prepares, validates non-activating, then activates in **one invocation**. No separate setup or repeated approval is needed. |
| Preview setup/default start | `setup --dry-run` maps to `start --dry-run`: write-free preview of preparation then activation. Staging-dependent validation and activation checks remain deferred; success is not authorization. |
| Setup (default) or start; valid existing target | Skip setup; retain saved provider/harness/pin and omit bootstrap selectors. A missing explicit config, partial or foreign target is **not absent**: inspect and repair deliberately. |
| Enabled/active owned timer; no observed running workers | Scheduling is active, but no worker was observed. Do not call it stopped or say setup is needed. Missing evidence or activity outside the scan is unknown, not zero. |
| `setup_busy` | Cite observed timer/worker state and use `status` to inspect. Offer authorized stop/drain only when deliberately re-preparing or pausing, not just to make a preview pass. |
| Setup (default) or start; gate evidence missing/unknown | Preserve the settled owner request. Name the exact missing check, applicable checklist or located record (or say no record was found), and the next safe read-only evidence check or owner action. Do not request a generic cutover record or invent approval. |

## Common path

Keep the host LLM: interpret the current request once, using the conversation's
scope, restrictions and authorization. No separate model routes, validates, polls
or paraphrases a routine command. Extra reasoning or clarification requires a
concrete unmet need, not a fixed sequence of model turns.

1. **Resolve intent.** `/orbi [status|version|setup|start|update|stop|help]` uses
   `python3 -B <this-skill>/scripts/orbi_control.py` with the mapping below on **every host**.
   These are public skill arguments, not direct Python helper syntax; all unlisted
   actions pass through unchanged.

   | Public skill arguments | Helper arguments |
   | --- | --- |
   | `status all [--json]` | `status all [--json]` |
   | `setup` | `start` |
   | `setup --dry-run` | `start --dry-run` |
   | `setup --prepare-only` | `setup` |
   | `setup --prepare-only --dry-run` | `setup --dry-run` |
   | `setup --prepare-only --resume-setup` | `setup --resume-setup` |

   Remove only `--prepare-only` for public setup; preserve all other supported
   arguments literally, regardless of flag order. `--prepare-only` is public
   setup-only: reject it on other actions, never forward it to the helper.
   Reject `setup --resume-setup` before invoking the helper unless `--prepare-only`
   is explicit; give the corrected `setup --prepare-only --resume-setup` command
   retaining the supplied config/provider arguments and dry-run. Direct Python
   helper `setup` remains non-activating for automation and recovery.

   Bare `/orbi` means `status`. **Help first.** For help requests, run only help.
   For lifecycle commands, go directly to the requested action.
   Return observed output from the helper's `help` for help or command inventory;
   it needs no repository, config, environment or scheduler reads.
   **Host inventory:** preserve literal
   `status all` in one helper invocation, from any working directory. Do not inject
   `--repo-dir` or `--config`, resolve a checkout or run GitHub probes. Only `--json`
   may accompany `all`; conflicting selectors are refused before probes. Relay
   partial manager/config coverage and observed totals, never an absolute host count.
   For host inventory interpretation, see [host inventory](references/lifecycle.md#host-inventory).
   For repository lifecycle actions, use the requested
   repo/config or known current checkout. The helper resolves the canonical
   worktree and verifies GitHub origin, deployment discovery and unit ownership;
   do not duplicate those reads in host tools. If target or intent is genuinely
   ambiguous, ask one focused question before mutation. Never run bare `orbi`
   (the Runner's one-tick entry), guess a typo alias or silently select an action.
2. **Authorize.** Preserve read-only/no-write restrictions and literal `--dry-run`.
   Preparation, activation and live delivery are distinct. Orbi remains paused
   and live-unqualified: default `setup` and `start` need an owner scheduling request
   and resolved explicit pauses, cutover requirements and human-only gates for that deployment.
   Public setup starts by default: explicit invocation expresses scheduling intent,
   not a waiver of deployment gates. `setup --prepare-only` prepares without activation.
   Once authorized activation gates are evidenced, do not ask for a second approval.
   Missing, unknown or failed start gates hold activation. Use the
   [activation evidence guidance](references/lifecycle.md#activation-evidence)
   and [offline examples](references/lifecycle.md#offline-guidance-examples) to name the
   precise blocker and repair/read-only next action. Evidence collection is read-only;
   a preview does not clear a pause. Do not silently fall back to preparation or
   report a prepared run as started.

   Branch protection is not a Kit setup/start prerequisite: known unprotected branches
   and protection/rules HTTP 403 are informational, not scheduling blockers.
   A protection-specific 403 leaves details unknown, not absent rules or failed
   repository access. Do not require PR-only mode, special opt-in, a protection change,
   paid GitHub plan, engine release/proof or second approval on that basis.
   Authentication, repository access, ownership and all other applicable gates still apply.
   `update` (also spelled `update --stop`) authorizes pausing owned timers
   without another confirmation; workers
   finish naturally and scheduling stays stopped. It never authorizes a start.
   Stop disables only owned timers; `draining` is not `stopped`. Never kill/restart workers.
   Other mutations likewise require accepted scope. Installation and offline checks grant none.
3. **Invoke once.** Preserve literal argument values, quoting, paths, provider/model
   IDs, `--config`, `--repo-dir` and all restrictions. Build argv, never interpolate
   user text as shell code; shell-only hosts must safely quote every argv element.
   After the public mapping, pass supported flags unchanged; add a known `--repo-dir`
   only when needed to bind the requested repository. Use `--json` for structured receipts unless the
   requested text/help output is preferable. Do not add/remove `--dry-run`, expand
   a literal path's shell substitutions, invent selectors or copy credentials.
   The existing ACTIONS-backed helper owns deterministic checks and action composition.

   No routine pre-status, help lookup, extra setup, preview-then-apply, polling or
   post-validation call. Helper ownership, safety, authentication and evidence
   checks still run. New setup/absent start accept installed `--harness {pi-bolt,pi}`
   (default Pi-Bolt) and complete `--pi-providers PATH --pi-provider ID --pi-model ID`
   with optional `--pi-thinking LEVEL`. Reuse existing selections without bootstrap
   flags. Missing prerequisites are repair inputs, not authority to install/login.
   Linux is the only mutation platform; macOS supports status/version/help.
4. **Relay receipt.** Return the helper's safe result directly wherever the host
   supports it. If a tool-result model turn is mandatory, relay only observed facts;
   no new plan or paraphrase pass. Lead with target and outcome, then a next action
   only when needed. Relay the helper's exact `resume_command` or `error.fix`;
   never guess selectors or shorten a bound recovery command.

   Distinguish partial, uncertain and failed results, even on exit 0. For example,
   given one draining worker and `engine_update: deferred`, say: “sdrhf: scheduling
   paused. The engine was not updated; one worker is still running.” Follow with
   the exact supplied resume command. Disabled timers are not an applied engine
   update, and `prepared`, `activated: false` does not prove scheduler inactivity.

   Keep structured evidence available: errors, `error.fix`, `error.mutated`,
   completed/failed `steps`, confirmed timer lists, `preparation`, `activation` and
   scheduler uncertainty. A short summary must not hide partial mutation. For partial
   mutation or activation, use [partial failure and recovery](references/lifecycle.md#partial-failure-and-recovery).
   Preserve the nonzero timer error, `recurring_scheduling: incomplete`, `first_tick`
   and `first_tick_evidence` from the helper's guarded first-tick recovery; requested
   is not worker completion or live delivery. Never retry the timer or configure later slots.
   Exit success is not live qualification; harness resolution is not running-worker evidence.
   Never expose credentials, auth files, environment values or raw child stderr.
   On failure, stop and return the safe error and repair action. No blind retry,
   implicit repair, compensating timer changes or worker stops. An unchanged
   timeout is not retryable; killed processes have no receipt.

## Deployed engine and current work

`version [--repo-dir PATH] [--config PATH] [--json]` reads only the selected
deployment identity and engine evidence on Linux/macOS. Pass `version` unchanged
in one helper invocation. It does not run full status, bootstrap, scheduler, worker,
queue, authentication or network probes, acquire a lock or write files. There is
no `version all`; mutation/bootstrap selectors (including `--dry-run`) are refused.
No deployment means unconfigured. An observed revision is not a verified release;
unverifiable pin, manifest or clean source means unknown with a reason.

Status leads with the repository, deployment-bound package version/revision and
provenance, scheduler state and each observed slot. Relay `deployment.engine`
separately from selected source/pin and `bootstrap_cli`: a matching CLI version
is unverified runtime evidence; a mismatch never replaces the deployed version.
Missing, modified or unpinned package/revision metadata leaves the version unknown.

`activity.slots` distinguishes running (issue number/title/link, run ID and observed
phase/last activity), verified idle, starting, draining and unknown identity.
Missing live bindings mean **active/issue unknown**, never idle or the newest retained
issue. A missing title stays unknown. For slot attribution or uncertain worker identity,
see [stop, status and drain](references/lifecycle.md#stop-status-and-drain).

Keep configured slots, enabled/active timers, running services and verified working
issues as separate observations. Preserve unavailable counts, scan limits,
health and last/next tick evidence. Unavailable counts are unknown, not zero.
For Linux inventory interpretation, see
[scheduler inventory](references/lifecycle.md#interpreting-linux-scheduler-inventory).
Ready issues are not claimed. Ready order, labels, progress and PR records never prove pickup or liveness.
Status reads once: no tick, fetch, poll, repair,
activation, session/env dump or implicit installed-helper update. Version/source,
harness and doctor evidence do not qualify live delivery.

## Pending queue evidence

Status reports the verified ready queue and grouped open pending issues: actionable
blocker, active/owned, native dependency, planning/paused, epic coordination, ready
and unknown. Zero ready is not zero pending. Relay each issue's number/link,
evidenced reason, next action and observed PR/native prerequisite. Planning input
stays explicitly unknown when not evidenced; never invent decisions or infer
dependencies from ordering. An open PR is not successful delivery.

Partial reads report observed lower bounds; failed reads do not prove an empty
repository. For incomplete queue coverage or `retry_safe=false` recovery, see
[pending issues and read coverage](references/lifecycle.md#pending-issues-and-read-coverage).
Status never invokes [`/unblock`](../unblock/SKILL.md), changes labels, requeues or repairs
branches. An activating service is transitional, not verified idle or issue pickup.
Idle services with ready work call for inspecting scheduler/ownership evidence and
existing pauses, not automatic activation.

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
| "Start needs setup first; update needs a separate stop command." | Absent start composes preparation internally. Update pauses owned timers by default and defers until drained; it never authorizes service interruption or restart. |
| "Passing checks releases the pause." | Owner scheduling authority and live gates remain separate. |
| "The command failed, so nothing changed and retry is safe." | Preserve mutation/activation evidence and repair deliberately; failure can be partially applied. |
| "The queue is empty because the status read failed." | Failed reads are unavailable; partial reads disclose gaps. Zero verified ready is not zero pending. |
| "Activating plus an open PR proves progress." | Activating is transitional, not pickup. An open PR is not successful delivery; preserve existing ownership and recovery inputs. |

## Red Flags

- Extra routing/validation/paraphrase models, routine polling or duplicate host probes.
- A guessed alias, shell interpolation, changed literal selectors or removed dry-run.
- Prepare-only/dry-run enables timers, status writes, or stop/update kills/restarts a service.
- Update invokes activating install-units, syncs before fresh idle/no-pending-start
  evidence, re-enables timers or reports stopped from missing scheduler evidence.
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
- Not `/update-kit`: update moves one deployment's engine, not Kit or this helper.
- Local visibility only: no cross-machine lock or global capacity guarantee.

The standing [Definition of Done](../shared/DEFINITION-OF-DONE.md) applies beyond
this task's acceptance.

**Done when:** the helper's observed state or precise refusal and evidence are
reported, with only authorized scoped mutations and active workers preserved.
