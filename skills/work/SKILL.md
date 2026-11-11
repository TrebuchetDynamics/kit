---
name: work
description: "Auto-select and complete tasks in this session."
license: MIT
---

# Work

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/work` is manual, in-session Autowork. It selects tasks automatically and completes
as many eligible tasks as it can in the current session. No task argument is required.
A bare invocation authorizes ordinary local repository development, including useful
offline maintenance when the queue cannot run. Existing scope and safety limits win.

## Select, execute, repeat

1. **Reconcile.** Read repository instructions, caller restrictions and current work.
   Reconcile saved work and live writers through
   [Autowork's ownership rules](../autowork/SKILL.md#ownership-limits-and-continuation).
   Keep read-only requests read-only. Proceed with a known scope and workspace.
2. **Select automatically.** Read `autowork tasks list` and use
   `autowork tasks why ID` to check eligibility. Select the first eligible accepted
   task in the [canonical selection order](../autowork/references/owner-cycle.md#current-session).
   A supplied task ID or scope narrows selection. Preserve dependencies, explicit
   holds, live authorization and active ownership. State the selected ID, title
   and reason, then execute without asking the user to pick a task.
3. **Recover or discover.** When the queue is empty or all open tasks are gated,
   use [repository maintenance](../autowork/references/repository-maintenance.md)
   within the authorized scope. Inspect source, tests, docs and existing user flows
   for a concrete useful offline task. Reuse an existing record or create a bounded
   task through `autowork tasks`, following
   [ordinary authoring](../shared/TODO-WORKCENTER.md#ordinary-authoring).
   Use `/docs-sync` for a missing store and `/plan-for-me` only for consequential
   missing choices. Finish the selected offline work in this session.
   Preserve live and owner-only tasks as pending. Their gates do not block unrelated
   offline work. Named-task-only requests stay on that task and stop at a genuine
   unresolved gate. A repository-wide pause still stops execution.
4. **Execute here.** Follow the
   [host-neutral Autowork workflow](../autowork/SKILL.md) for preparation,
   implementation, checks and closeout. Load that source directly, not the portable
   `/autowork` command's runner-first route. Apply this skill's continuation default
   instead of Autowork's one-slice default. A selection or `EXECUTE` result is a
   contract to implement, not completed work.
   Keep implementation in this session. If independent review is required, start
   the reviewer in a fresh context window. State its scope, completion criterion
   and read-only permission.
5. **Close and continue.** Apply the shared
   [Definition of Done](../shared/DEFINITION-OF-DONE.md) and Autowork's closure rules.
   Make task-store edits through `autowork tasks`. Retain incomplete work with its
   exact next action instead of claiming acceptance. After integrated closeout,
   perform [working-set reconciliation](../shared/TODO-WORKCENTER.md#reconcile-the-working-set)
   before selecting the next task automatically. One completed task
   is not a stop condition. An explicit one-task or named-task limit wins.
6. **Stop with evidence.** Stop for a user stop, session interruption, a genuine
   scope-wide authority or ownership blocker, or a bounded search with no useful
   eligible work. Report the inspected areas, rejected candidates and exact missing
   input under the maintenance reference. An unchanged queue alone is not exhaustion.
   Do not invent busywork or repeat an unchanged search to keep the loop alive.
   A stop or session end launches no replacement worker or background job.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "I need a task ID before I can act." | Select automatically within scope. |
| "The open tasks are live-only, so all work is blocked." | Preserve those gates and inspect independent offline work. |
| "I finished one task, so I should stop." | Continue selection unless a caller limit or evidenced stop applies. |
| "A runner is available, so I should start it." | This invocation selects current-session execution. |

## Red Flags

- Asking the user to choose among routine eligible tasks.
- Ending after one task without a caller limit or evidenced stop.
- Starting a service, cron job or detached implementation worker.
- Bypassing live gates, ownership, required review or acceptance to claim progress.

## Boundaries

- Not a runner control. On portable hosts, `/autowork` is the service-first route.
- Not a new product mandate; use `/plan-with-me` for unresolved product intent.
- Not a read-only queue report; use `/pending`.
- Not publication or deployment authority; use `/git-commit-push` for authorized delivery.

**Done when:** the in-scope execution loop reaches an evidenced stop and the receipt
separates completed tasks, pending acceptance and remaining blockers.

**Receipt:** selected tasks and reasons; changes; checks and review; task states;
commit/integration status; inspected scope; next action; exact blocker and unverified acceptance.
