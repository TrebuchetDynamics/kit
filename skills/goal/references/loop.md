# Goal loop, evidence and handoffs

Use this reference during an active goal. The main skill owns the contract, status
and completion audit. This file supplies the operating detail.

## Choose the next slice

Pick the smallest action that does one of these:

1. Runs the contract's verification surface.
2. Tests the riskiest assumption in the current plan.
3. Removes the blocker that stops the next verification.
4. Produces the next required artifact.

Prefer an action that gives a clear pass or fail. Avoid a broad rewrite, a second
audit of the same surface or a tool tour. Record why the slice is next when the
choice is not obvious.

## Evidence ledger

Keep one compact ledger entry per slice:

```text
- Slice: <what changed or what was run>
- Command: <exact command>
- Result: <pass/fail, number, error or output summary>
- Source: <path@revision or artifact path>
- Next: <one action or stop reason>
```

Use the current revision when a file path matters. Do not copy a result from an
earlier run when an input changed. Do not record an expected result as an observed
result.

## Progress and no-progress

A slice is progress when it adds evidence toward the contract or removes a blocker.
A changed file is not progress by itself. A passing unrelated check is not progress.

After three attempts with the same failure and no new evidence:

1. State the repeated failure and the evidence.
2. Change the hypothesis, the method or the input.
3. If no defensible alternative exists, stop blocked.

Do not repeat the same command, edit or review and call it a new attempt.

## Specialist handoffs

Load one specialist at the seam that needs it. Do not load every skill.

| Need | Command |
| --- | --- |
| Investigate and save a plan or tasks | `/plan-for-me` |
| Answer missing owner intent | `/plan-with-me` |
| Execute one ready task in the repository queue | `/autowork` |
| Run many independent improvement lanes with review | `/autonomous-codebase-improver` |
| Select one engineering method | [engineering](../../engineering/REFERENCE.md) (reference only) |
| Hunt an unreproduced defect | `/bug-harvest` |
| Reduce redundant tests | `/test-optimizer` |
| Remove proven dead code | `/unused-code` |
| Improve module depth or seams | `/improve-codebase-architecture` |
| Commit, merge or push authorized work | `/git-commit-push` |

A handoff names the current objective, the completed evidence and the exact next
criterion. The specialist keeps its own write, review and delivery rules. A
specialist result returns to the goal audit; it does not complete the goal by
itself unless its evidence proves the contract.

If the host supports subagents and the user's scope allows delegation, start a
dispatched run in a fresh context window. State its scope, completion criterion and
whether it may write. A read-only review stays read-only. Do not hand the parent
conversation to a child by forking when the point of the dispatch is independent
review.

## Budget and context

A soft budget is a checkpoint, not a meter. At the limit:

1. Stop substantive work.
2. Report what is proved, what is not and the next action.
3. Keep the goal active or paused. Do not mark complete.

When the context is compressed or the session resumes:

1. Restate the contract and state block.
2. Re-read the current files, checks and repository state.
3. Drop stale evidence.
4. Continue from the recorded next action, not from memory of the old turn.

## Paused, blocked and cleared

**Paused** means the user stopped the loop. Preserve the state and the next action.
Do not run a slice, review or check that the user did not ask for.

**Blocked** means a real input, authority, external condition, live access or
defensible path is missing. Report:

- the exact condition;
- the attempts and their evidence;
- the one input or decision that unlocks progress;
- what work, if any, can continue independently.

**Cleared** means the user dropped the goal. Stop the loop. Keep work already
produced. Do not delete commits, files or task records merely because the goal is
cleared.

## Durable work

A goal is not a second task queue. When the work must survive this conversation,
drive a runner or share ownership, use the repository's `tasks/` store through
`/plan-for-me` and `/autowork`. Do not create a private goal database or copy the
contract into a project instruction file.
