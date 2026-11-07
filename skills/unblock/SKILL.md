---
name: unblock
description: "Diagnose and repair stalled Autowork services."
license: MIT
---

# Unblock

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/unblock [runner|repo|all]` diagnoses and repairs stalled Autowork services
without an interview. A bare invocation targets the current repository's runner, not the
directory that stores this skill. `all` targets registered runners with a fault or
blocked work; healthy runners are read-only. Named targets narrow this scope.
Creating or editing this skill does not invoke recovery.

Invocation authorizes routine local repairs and supported service recovery for
those targets, including reloading an active runner or restarting a failed runner
that was previously enabled. Make all reversible recovery decisions within accepted
task scope and the target repository's policy. Choose the smallest complete repair
instead of offering a menu. Existing user restrictions and explicit pauses win.
`read-only`, `audit` and `questions only` permit diagnosis, not mutation.

## Recover, verify, continue

1. **Inventory.** Read `autowork ls --json`, each target's fresh status, service
   state and logs. Inspect runner and installed revisions, pending service jobs,
   queue eligibility and actual worker/session activity. Read target instructions
   and existing decisions. Treat failed reads as unavailable evidence, not zero
   workers. Finish when every target has a cause or a precise diagnostic gap.
2. **Find the cause.** Load the [Blockers discovery and filtering rules](../blockers/SKILL.md#1-gather-and-filter)
   for held tasks, reports and owner questions. Reuse their evidence tests, not
   their interview or no-service workflow. Rank causes by independent work blocked.
   A dashboard timer, `waiting on you` label or live PID is a lead, not a diagnosis.
   Distinguish an intentionally idle queue from a failed service, stale projection,
   technical hold, live writer, dependency wait or genuine external gate.
   Finish when each proposed repair names the failed operation and its evidence.
3. **Decide and repair.** Apply existing answers and delegated choices immediately.
   Record agent decisions as `Standing policy:` or planner calls through
   `autowork tasks`, never as fabricated `Owner decision:`, waivers or qualification.
   Preserve acceptance and functional dependencies. For implementation or test fixes,
   use [Autowork](../autowork/SKILL.md) in the current session with the existing task
   and candidate; its no-service boundary still governs that implementation lane.
   For runner/process faults, use the [service recovery procedure](references/services.md).
   Establish one writer per checkout and preserve live leases. Finish each repair
   with checks and its supported continuation, not just a changed note.
4. **Prove progress.** Read back the target's service state, running release, task
   selection and latest attempt after repair. Observe the expected transition:
   admission, resumed attempt, review, integration, or an evidenced idle queue.
   An active service or disappearing question alone is not recovered execution.
   Separate saved, committed, consumed and executing changes. If observation remains
   pending, state exactly what has not been seen; do not claim success.
5. **Continue independently.** Keep repairing other in-scope causes while one waits.
   After a repeated failure, inspect the new failure evidence and change approach;
   do not loop unchanged retries, erase attempt history or reset retry limits.
   Preserve an unavailable authority/input as an exact external gate, without a
   second approval round for choices already delegated. Stop only when targets
   recover or every remaining cause has an evidenced wait, external gate or
   ownership limit. Do not create backlog work merely to make an idle runner busy.

Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to local repairs.
Required checks and independent review remain required; local integration,
publication, installation and live acceptance are separate outcomes.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| “Waiting on you means I must ask.” | Inspect the actual choice and existing authority; decide routine recovery yourself. |
| “Restarting fixes every stall.” | Repair the cause, then observe the expected task transition. |
| “All decisions means every permission.” | Recovery authority preserves explicit stops, security and live boundaries. |
| “One blocked task stops the fleet.” | Continue independent eligible repairs and preserve the exact gate. |

## Red Flags

- Clearing leases, retry history or failed evidence to make a dashboard green.
- Restarting again while a previous service job is still running.
- Releasing an explicit pause or changing acceptance to remove a blocker.
- Claiming recovery from a metadata edit, successful signal or old status snapshot.

## Boundaries

- Use `/blockers` for an owner-question interview without service controls,
  `/pending` for a read-only queue report, and `/autowork` for normal task execution.
- Preserve deliberately paused, disabled or stopped services and other writers.
  Do not kill competing sessions, delete runtime state or change host permissions,
  approval policy, credentials, model/spend grants or security defaults.
- This invocation grants no production/product live operations, remote publication,
  fleet-wide package deployment, destructive recovery or new product scope.
  Retain real external gates and continue independent repairs.
- Use `/push` only under separate publication authority. A recovery skill cannot
  promise perpetual operation or task completion after the current session ends.

**Done when:** every target has observed recovery or an evidenced remaining wait,
external gate or ownership limit, with actual actions and verification reported.

**Receipt:** targets and causes; autonomous decisions; repairs and checks; before
and after service/release/task states; commits and installed changes; remaining
gates, unobserved transitions and exact next action.
