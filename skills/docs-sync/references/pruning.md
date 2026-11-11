# Pruning finished task records

One deterministic procedure for
[completed-task retention](../../shared/TODO-WORKCENTER.md#completed-task-retention).
Run the command; do not re-derive the rules by script.

```sh
autowork tasks prune .                              # the plan; writes nothing
autowork tasks prune --apply --expect-plan REV .    # REV: the plan_revision the plan printed
autowork tasks validate --worktree .
```

`--apply` deletes the eligible records and removes their satisfied `depends_on`
edges from inactive open tasks, in one validated transaction in the working tree.
It never commits. An older release without `prune` (`autowork capabilities` does not
list it): report the plan as unavailable and delete nothing.

## When a pass may apply

| Request | Pruning |
| --- | --- |
| Bare `/docs-sync` | Print the plan summary and stop. Delete nothing. |
| `/docs-sync tasks`, or a request that names pruning or task cleanup | Plan, then apply. |
| Audit or read-only | Plan only when asked. Delete nothing. |

## Decision table

Only `done` and `superseded` records are candidates. An open record is never
deleted, whatever its section. The first matching row decides.

| Code | The finished record stays while | What ends the retention |
| --- | --- | --- |
| `OWNERSHIP_UNKNOWN` | Worker slots or a lease cannot be read. Nothing is pruned. | Readable runtime state. |
| `RUNTIME_SLOT` | A slot with unfinished work (`dispatched`, `running`, `reported`, `integrating`, `integrated`, `held`, `interrupted`) or a live lease holds it. | The attempt closes. A `closed` slot does not retain. |
| `UNCOMMITTED` | Its record differs from HEAD, so closure is not integrated. | `autowork tasks commit`. |
| `NEEDS_DECISION` | It sits in `Needs decision`, even when `done`. | The owner's answer and `place`. |
| `UNVERIFIED_CLOSURE` | It claims a verified close and its receipt is missing or invalid. | A valid receipt. |
| `GOAL_PROOF` | A goal record cites its ID. | The goal no longer needs that proof. |
| `CITED_BY_OPEN_TASK` | The notes of an open task cite its ID. | That task closes or stops citing it. |
| `CURRENT_DOC` | A tracked Markdown document that is not frozen history cites its ID. | The document cites immutable Git evidence instead. |
| `VERIFIED_DEPENDENCY` | A surviving task names it in `verified_depends_on`. | That task is finished and pruned. Never drop the typed gate. |
| `SUPERSEDED_DEPENDENCY` | An open task depends on it and it is superseded. | Repoint that task to the successor. |
| `DEPENDENT_IN_FLIGHT` | An open task depends on it and an attempt holds that task's contract. | The attempt ends. |
| `RETAINED_DEPENDENT` | A retained finished record depends on it. | The dependent is pruned. |

A citation in a frozen archive (`TODO.archive.md`, `docs/TODO-archive.md`, or a
document that declares `doc-ref-guard: record`) never retains a record. A `done`
record that an inactive open task names only in `depends_on` is deleted, and that
satisfied edge is removed in the same transaction.

## What the command does not do

- It does not remove receipts. `receipts_left` lists each `tasks/evidence/ID.toml`
  of a deleted record. Remove one only after its consumers are reconciled and its
  Git copy is reachable.
- It does not change goal status, focus, owner or live gates, worktrees or runtime state.
- It does not prove completion. A `done` label retained no evidence of its own.

## Required report

Counts (`delete`, `retain`, `edges_removed`, `receipts_left`), then one line for
each retained record: ID, code and detail. Use `--summary` for counts by reason when
the list is long. Do not write a completed-task list. A second pass on unchanged
evidence reports the same plan and changes nothing.

## A single record

`autowork tasks delete ID` refuses while a surviving task depends on the record.
`--closure` prints those dependents and writes nothing. `--ids-file FILE` deletes a
set under one lock and one validation. `--force` leaves dangling references; use it
only when the owner asks for that result.
