---
name: pending
description: "Report open, done and next tasks."
license: MIT
metadata:
  version: 0.2.0
  hermes:
    tags: [tasks, pending, done, query, read-only]
---

# Pending

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Answer "what is left, what is next, what was done" without changing the repository.
Read current work from `tasks/` and completed work from
[Git history](../shared/TODO-WORKCENTER.md#read-completed-work-from-git).
Use the read-only `autowork tasks` queries, which read the store at a commit
(HEAD by default), and report the outcome in the user's language, leading with
what matters and keeping task IDs:

```sh
autowork tasks list [repo]                 # every task: status, section, rank, next-eligible position
autowork tasks show <TASK-ID> [repo]       # one task: its contract, notes and record revision
autowork tasks why <TASK-ID> [repo]        # why it is or is not the next eligible task
```

Compare `list --worktree` with the committed list when there are pending task edits;
label the two views rather than silently counting uncommitted work as queued.
For completed work, inspect closure records in history, not just commit subjects
or receipt presence. Report the revision/interval and coverage limits; pruning
does not mean nothing was completed. Follow the linked history procedure for
Manual versus Verified evidence and task-ID deduplication.

Open work is `status: open` in Now and Next, in `position` order; Needs decision items
wait for a person. A verified close has a receipt at its closure revision under
`tasks/evidence/<ID>.toml`; cleanup can remove the current copy. The queries write
nothing and run nothing; eligibility is recorded dependency and priority
evidence, not worker admission or liveness. A repository without `tasks/` is not
converted yet: say so and name `/docs_sync` (its `autowork tasks prepare` converts it,
or defers to the runner while work is in flight); do not read TODO.md instead.
## Boundaries

- Read-only: not a repair; use `/docs-sync` to change the store.
- Not a blocker resolution; use `/blockers`.

**Done when:** open and next reflect the stated queue revision and selection order;
completed work reflects inspected Git evidence for the stated interval, with coverage
limits and Manual versus Verified distinguished.
