---
name: unblock
description: "Resolve Autowork blockers and resume authorized work."
license: MIT
---

# Unblock

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/unblock [runner|repo|all]` resolves blockers and delegated decisions so Autowork
can continue without an interview. A bare invocation targets the current repository's
runner, not the skill directory. `all` targets registered runners with faults or
blocked work; healthy runners are read-only. Named targets narrow this scope.
Creating or editing this skill does not invoke recovery.

Invocation authorizes routine local repairs and supported service recovery for
those targets, including reloading an active runner or restarting a failed runner
that was previously enabled. Make all reversible recovery decisions within accepted
task scope and the target repository's policy. Choose the smallest complete repair
instead of offering a menu. Existing user restrictions and explicit pauses win.
`read-only`, `audit` and `questions only` permit diagnosis, not mutation.

## Recover, verify, continue

1. **Bind and inventory.** Filter `autowork ls --json` to the targets. Read their
   fresh status, recent logs, service state, running and installed revisions, and
   pending service jobs. Reconcile `autowork tasks list REPO` with execution status
   and questions in the runner's session. Include every open `Needs decision` task,
   held task and ready task that did not start, even when absent from the dashboard's
   roots or questions. Finish with task IDs and causes or exact missing reads;
   a failed read is unavailable evidence, not zero workers.
2. **Diagnose.** Apply the [Blockers discovery and filtering rules](../blockers/SKILL.md#1-gather-and-filter),
   not their interview or no-service workflow. Read the target's instructions,
   decisions and standing policy. Rank causes by independent work blocked. For each,
   inspect its latest attempt or planner result and the failed operation's log.
   A `ready for planning` label can hide a refused planner result; `waiting on you`
   does not establish owner-only authority. Stop discovery when the evidence selects
   a repair or a specific gate. Keep output bounded and task-scoped; use the host's
   session controls for ownership checks, not a search through unrelated transcripts.
3. **Resolve decisions.** Reuse an existing answer within its exact scope. For a
   routine reversible choice covered by the target's policy, choose and record it
   now as `Standing policy:` or a planner call, with the choice, reason and evidence.
   Use `autowork tasks` and its installed verb help for record edits. Return a resolved
   `Needs decision` task to `Now` or `Next` when its placement is authorized; preserve
   explicit deferrals, acceptance, exclusions, ownership and functional dependencies.
   A technical failure needs a repair, not another approval. For an owner-only choice,
   retain the exact question and missing authority or input. Never invent an
   `Owner decision:`, waiver or qualification; notes do not grant typed authority.
   Finish with a disposition for every inventoried decision, not only the displayed
   questions. In read-only mode, give the proposed dispositions without saving them.
4. **Repair and deliver.** For implementation or test fixes, run
   [/autowork](../autowork/SKILL.md) in this session on the existing task and candidate;
   its no-service boundary governs that lane. For runner/process faults or activation
   of a verified repair, use the [service recovery procedure](references/services.md).
   Establish one writer per checkout. If another session owns the same repair, confirm
   its scope and fresh activity, then send the finding and required continuation through
   its available control channel. Retain a specific ownership wait if contact fails;
   a dirty file or old claim alone does not prove an active repair. Continue independent
   causes. Validate changed records and run affected checks and required review.
   Commit only attributable changes through the repository's supported local path and
   integrate when authorized. Finish with the repair delivered to the runner's input,
   or the exact delivery restriction, not an unsaved answer or a Next action note.
5. **Verify and continue.** Read back service state, running release, task selection
   and latest attempt. Observe the expected transition: decision consumed, admission,
   resumed planning, review or integration, or an evidenced idle queue. Selection from
   `autowork tasks why ID REPO` alone does not prove runtime admission. Follow a consumed
   answer through to execution or its next evidenced wait. Separate saved, committed,
   consumed and executing changes; do not claim success from a reload or a vanished
   question. On failure, inspect the new evidence and change approach; do not loop unchanged retries,
   erase attempt history or reset retry limits. Reconcile all inventoried causes before
   stopping, including independent work behind an owner-only gate. Do not create backlog work
   merely to make an idle runner busy.

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
| “Another session is fixing it.” | Confirm its activity and repair scope, then coordinate the continuation. |
| “I saved the answer, so it is unblocked.” | Verify consumption and execution, or name the next evidenced wait. |

## Red Flags

- Clearing leases, retry history or failed evidence to make a dashboard green.
- Restarting again while a previous service job is still running.
- Releasing an explicit pause or changing acceptance to remove a blocker.
- Reporting only displayed questions while `Needs decision` tasks remain unexamined.
- Repeating status reads after the failed operation and repair are known.

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

**Done when:** every inventoried blocker and decision is resolved with observed
continuation, or has an evidenced wait, external gate or ownership limit, and each
target's remaining queue is accounted for.

**Receipt:** targets; decisions resolved and blockers repaired; checks and commits;
before/after service, release and task states; installed changes; unresolved task IDs
with exact gates, responsible actors and next actions. Label unobserved transitions
as pending. Attribute progress by another session or the runner to that actor.
