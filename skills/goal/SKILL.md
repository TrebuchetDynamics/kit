---
name: goal
description: "Keep one objective alive until evidence proves it done."
license: MIT
metadata:
  version: 0.1.0
  hermes:
    tags: [goal, continuation, verification, evidence]
---

# Goal

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/goal <objective>` keeps one objective in view, turns it into a completion
contract, works in verified slices, and completes only when the contract's evidence
proves the outcome. This is the Codex and Hermes goal pattern without a hook,
database or project file.

## Host and state

Goal state is thread-scoped. Do not write `GOAL.md`, a hidden state file, a
database, a hook or project instructions for it. If the host exposes a native goal
store or goal tools, use that store and those tools. Otherwise keep the state block
in the conversation and restate it after a resume, compression or handoff.

This skill cannot force a new turn after the host stops. On a host with native goal
continuation, use the native command. Do not install a hook from this skill.

On Hermes, the native `/goal` command owns this name and already provides
contracts, quality gates and a judge. Do not replace or reconfigure it. Use
`kit:goal` only when that native loop is unavailable. On Claude Code use
`/kit:goal`, on Codex `$kit:goal`, and on Pi `/goal`.

## 1. Read the command

| Input | Action |
| --- | --- |
| `/goal <objective>` | Set the objective and start. If an active goal has the same objective, continue it. If the objective differs, state the replacement and start the new goal. |
| `/goal draft <objective>` | Expand the objective into a contract, show the contract, and start. Do not wait for a second approval unless the user said `draft only`. |
| `/goal` or `/goal status` | Show the contract, status, evidence and next action. With no goal, say so and name the next step. |
| `/goal pause` | Pause continuation. Keep the state. Do no substantive work in this turn after the pause. |
| `/goal resume` | Resume from the last state. Recheck the evidence before the next slice. |
| `/goal clear` | Clear the goal. Keep files, commits, tasks and other work already produced. |
| `/goal complete` | Run the completion audit. Complete only when it passes. Otherwise stay active and report the gaps. |
| `/goal -- <objective>` | Set a literal objective that starts with a control word, such as `pause the nightly job`. |

Accept `--turns N` or `--tokens N` as a soft budget. Report the budget as an
estimate. Never claim exact token metering. A bare `/goal` with no goal does not
invent work: name `/plan-for-me` for discovery or ask for one objective.

## 2. Write the completion contract

A direction is not a goal. Name six fields before the first slice:

```text
Goal contract
- Outcome: <one end state that must be true>
- Verification: <exact command, test, artifact or source that proves it>
- Constraints: <what must not regress or change>
- Boundaries: <allowed files, data, tools, systems and resources>
- Iteration: <how to choose the next action after each attempt>
- Stop if: <blocked condition and what would unlock progress>
```

Use the user's words for the outcome. Draft the other fields from the request and
the repository evidence. Mark every default you choose as the agent's call. Ask one
question only when a missing field changes the outcome, scope or authority.

A strong goal names the end state, its proof, the constraints and the stop. A weak
goal names only a direction. Load [contract examples](references/contract.md) for
strong and weak rewrites, field tests and the audit worksheet.

When the user adds a criterion after activation, append it to the contract and
continue. Do not restart the goal or discard evidence.

## 3. Run the loop

Keep this state visible:

```text
Goal state
- Status: active|paused|blocked|complete|cleared
- Budget: none|turns|tokens (soft)
- Evidence: <command -> result; path@revision; artifact path>
- Next action: <one concrete action>
```

For each slice:

1. Restate the next concrete action in one line.
2. Take the smallest action that advances the verification surface or tests the
   riskiest assumption.
3. Run the verification and record the exact command, result and source. A claim
   without its source is not evidence.
4. Compare the result with the contract. If the outcome is met, run the audit.
5. If the outcome is not met, choose the next action from the new evidence and
   continue. Do not stop after one slice to ask "continue?" when the user already
   asked for the outcome and authority covers the work.
6. Stop only for a verified completion, an explicit pause or clear, a real blocker,
   a budget limit or a safety limit.

A slice counts as progress when it adds evidence toward the contract or removes a
blocker. After three attempts with the same failure and no new evidence, change the
hypothesis or stop blocked. Do not repeat the same attempt.

Load [loop and handoffs](references/loop.md) for slice selection, the evidence
ledger, specialist handoffs, budget handling and resumed sessions.

## 4. Stop and report

- **Paused:** the user stopped the loop. Report the exact resume action. Do not
  start new substantive work.
- **Blocked:** name the missing owner input, authority, external input, live access
  or defensible path. Report the attempts, their evidence and the one input that
  unlocks progress. Do not hide the blocker or spin.
- **Budget reached:** stop substantive work. Report progress and the next action.
  Reaching the budget is not completion.
- **Cleared:** drop the goal. Work already produced remains.
- **Complete:** only after the audit in section 5.

Lead the report with the status and outcome. Then give the evidence, any residual
risk, and the next action or exact blocker.

## 5. Run the completion audit

1. Restate the outcome and every contract criterion.
2. Map each criterion to fresh evidence. Name the command and result, the file and
   revision, or the artifact path.
3. Inspect the current files, command output, tests and repository state. Do not
   rely on memory or an older result when the inputs changed.
4. Check the constraints and boundaries. List every violation.
5. Name weak or missing proof, unrun checks and residual risk.
6. If any criterion lacks evidence, keep the goal active and continue or block.
   Never complete from prose, a plan or a claim that something "looks done".
7. Only then set the status to complete and report the evidence map.

A local or offline pass does not prove live, device, production, delivery or
publication qualification. Keep those states separate. A disclosed residual risk
does not replace a missing criterion unless the contract explicitly allows it.

## Boundaries

- Not planning or discovery; use `/plan-for-me` or `/plan-with-me`.
- Not one queued task; use `/autowork`.
- Not a multi-lane campaign or a second worker pool; use
  `/autonomous-codebase-improver`.
- Not a task status report; use `/pending`.
- Not delivery or publication; use `/git-commit-push` with its existing authority.
- Not the Hermes native goal loop; use the native `/goal` there and `kit:goal` only
  when the native loop is unavailable.
- No hidden goal state. Durable repository work belongs in `tasks/` through
  `/plan-for-me`, not in a private goal file.

**Done when:** every contract criterion maps to fresh evidence and the audit passes,
or the goal is paused, blocked or cleared with its exact next action and missing
input.

## References

- [Contract examples and audit worksheet](references/contract.md)
- [Loop, evidence and handoffs](references/loop.md)
- [Research notes and source links](references/sources.md)
- [Shared contract](../shared/COMMON-CONTRACT.md)
