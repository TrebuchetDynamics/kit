---
name: blockers
description: "Resolve held tasks and owner questions."
license: MIT
metadata:
  version: 0.3.0
  hermes:
    tags: [blockers, interview, planning, autowork]
---

# Blockers

For issue operations, load [Plan Handoff](../shared/PLAN-HANDOFF.md).
The executor and task CLI are removed. Preserve existing task/attempt evidence;
Orbi remains paused and live-unqualified. Never release that pause here.

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/blockers [repo]` resolves held tasks and owner questions together.
Apply established answers, repair authorized technical causes and verify progress,
then ask only for unresolved owner
decisions or unavailable inputs, easiest first. Save each resolution before moving
on. `/autowork blockers` and `/plan_with_me blockers` are the same command.
It runs only when the owner starts it; no runner or schedule invokes it.

It never starts, stops, restarts or reconfigures a runner or service, never launches
a competing execution or repair session, never kills a session, and never pushes.
Execute authorized local recovery through the existing task's supported execution
workflow when exclusive ownership is established; do not edit a live worker or
duplicate its checks. An invocation authorizes bounded local blocker repair, not
unrelated implementation, live operations, credentials or publication. Explicit
questions-only, planning-only and read-only requests execute nothing; read-only also
writes nothing. Updating an already authorized plan needs no new owner decision.

Central rule: before asking the owner anything, look for an authorized technical
recovery that lets independent work run. After applying it, verify its effect on the
runner's selection and execution. If the block persists, explain the exact cause;
do not repeat the same advice or count an edited plan as progress.

## 1. Gather and filter

Do not announce a plan or ask whether to begin: gather and filter, then put the
first genuine question in the same turn if one remains. Otherwise report the
planning repairs and remaining execution work without inventing a question.

**Profile-bound invocations never ask which runner.** Telegram, CLI and cron
invocations carry the active Hermes profile and its configured repository, and a
local invocation starts in its checkout. Resolve that repository first and begin
there. Do not present the fleet as a multiple-choice question or ask the owner to
pick a runner when their profile already owns one; that is friction, not a blocker.
Only an explicitly fleet-wide request, or a genuinely unresolvable target after
checking the profile and checkout, may name candidates, and then in prose rather
than a runner-selection question.

Resolve the target from the active profile's configured repository or current
checkout; ask only when it cannot be established. Read GitHub Issues, native
blockedBy dependencies, linked PRs and checks, and actual Orbi ownership where
available. Inspect retained attempts read-only as migration evidence, not a second
queue. Include every unresolved issue decision, even when absent from a
dashboard. A failed read is unavailable evidence,
not an empty queue. Never use the removed executor CLI or edit its runtime state.

### Filter before asking

Merge duplicates by literal task ID and read the current task, decisions, repository
policy and candidate evidence. A generated `USER_DECISION` label or a worker's request
for approval is evidence to examine, not proof that a human decision is needed. A
question can outlive its cause: compare it with the current task state and the latest
attempt's report (a newer scope-validation failure supersedes an older missing-input
report). Exclude retired tasks, released claims and settled deferrals: a cached
worker reason can describe an older checkout. When live status cannot be read, use
retained reports with current queue evidence and say how fresh they are. Count and
sort what remains programmatically, and treat an `unblocks` count as the notice's
figure, not measured impact.

Classify each hold by cause before handling it, and never report them all as
"dependencies": functional dependency (needs another task's result), resource
reservation (`resources` such as `exclusive`, `live` or a port), live owner,
failed validation (a broken main or task check), and external input. Measure each
root's real reach: count the waiting tasks that are otherwise admissible and would
start if it cleared. Handle the widest first. One held or long-running task with
the `exclusive` resource can stop hundreds of independent tasks; inspect that
reservation before asking about receipts or access that stop no local work.

- **Established answer or routine recovery:** use existing authorization; repair the
  cause and verify the supported continuation, not merely another Next action.
- **Idle candidate awaiting delivery:** when no live writer owns it and local
  integration is already authorized, perform the integration-only continuation with
  the existing execution owner.
- **Over-broad resource reservation:** the `exclusive` resource, or another shared
  resource, that serializes unrelated work is a planning repair. Narrow it from
  evidence; never strip exclusivity in bulk.
- **Live or uncertain ownership:** retain the hold unless fresh activity checks prove
  abandonment or the owner releases it.
- **Real owner decision/input:** ask only for the specific missing intent, external
  input or authority, and preserve explicit pauses and restrictions.

Load [hold dispositions](references/hold-dispositions.md) for the evidence test,
recovery limit and excluded action of each branch.

Reuse the owner's latest answers, from this conversation and the queue. An item
the owner deferred is still open work but not an unanswered question; do not ask to
reconfirm it because it remains under `Needs decision`. A brief approval accepts the
recommended option only, never every alternative or permission to deploy. A task
that only waits on unfinished dependencies is not a question: a release task waiting
for features is not a request to approve publication. Waiting for overlapping files
or a running dependency is scheduling, never an owner question; a reservation wider
than the task's evidence is still a repair to make.

Record each decision in its current GitHub issue, preserving native dependencies,
explicit pauses and actual ownership. A saved answer does not prove the owning
worker consumed it. Keep deferred work visible without repeatedly asking for the
same answer, and never drop a dependency to make a question disappear.

A questions-only/read-only invocation records proposed repairs in chat rather than
editing files. With no genuine questions left, report what was reconciled and what
still awaits execution. Do not turn “reuse, verify, preserve privacy, no push” into
separate approvals: those are constraints to carry into the plan.

## 2. Order: easiest first

Order only the questions that survive filtering. A generated effort/kind label
does not override that filter:

| Effort | Kinds | Typical answer |
|---|---|---|
| quick | a narrow unresolved choice after inspecting dependencies | choose between two valid dependency plans |
| decision | an outside condition, a dependency not in Now/Next, an unanswered `Needs decision`, a contract mismatch | decide placement or disposition; reconcile the plan without starting work |
| input | a worker's blocker asking for files, inputs or authorization | supply the input, grant the authorization, or narrow the acceptance |
| investigate | evidence shows recovery needs a new scope or acceptance decision | choose the supported scope change |

Within an effort, a larger `unblocks` count comes first, then the oldest. Open with
one line of totals (for example `7 questions: 2 quick, 2 decision, 3 input`).

## 3. One picked question per unresolved decision

Ask one question at a time with the host's option picker: Hermes `clarify`
(`questions=[{question, choices}]`), Claude Code `AskUserQuestion`, Codex
`request_user_input` when available in the current mode, or
`request_user_input_async` during active work. Use only tools exposed by the host.
Without an available picker, number the options in chat and accept a number.

- The question names the task and how many tasks wait on it, quotes the worker's or
  engine's words whole when short, and gives the one piece of evidence that matters.
- Two to four choices, each a concrete plan change in a few words (for example
  `Add fixture: tests/data/feed.json`, `Split: offline part now, device check later`,
  `Supersede T-12`). The recommended choice comes first. Typed answers, `skip`
  (leave it open) and `stop` (end now) are always accepted; the picker's free-text
  row carries them.
- One shared decision can cover several named tasks; apply its answer to each
  within that scope instead of asking again. Preserve earlier answers across turns.
  Do not batch unrelated questions, and do not ask what the repository already answers; the
  [grill-me](../grill-me/SKILL.md) rules apply: verify before asking, decide only
  what the owner must.

When the pick means replanning (split or rescope the task, add a task or dependency,
change acceptance), plan that one task with
[Plan With Me](../plan-with-me/SKILL.md)'s planning craft: a short round of further
picked questions about that task only, then save it. Then go to the next blocker.

When the owner defers a physical or live check, keep its criteria and access limits.
If that check still stops independent offline work, ask separately whether offline
development may go ahead before the final human acceptance. The answer can change
admission dependencies; it never supplies a test result, product acceptance or
publication authority, and never turns an unobserved check into a pass.

## 4. Resolve and verify each item

For each technical hold, keep the same task and candidate.
Inspect its latest attempt, actual writer/session activity and exact qualification
inputs; fix the smallest in-scope local cause using `/work` with established
exclusive ownership. Reuse retained code and valid checks, repair local metadata/scope omissions
within accepted intent, and rerun only missing or invalidated required checks. Keep
required full-gate/review evidence, source bindings and negative safety assertions.
Never patch a report or directly clear a slot/lease to manufacture progress.

Read back the exact task state and question after the repair. A saved answer is not
a removed hold; missing terminal evidence stays unqualified. If a live owner must
consume the change, observe its acknowledgement or name the precise pending
operation and owner. Do not repeatedly append the same advice or edit metadata just
to trigger fresh implementation. An unavailable owner, real resource wait or external
prerequisite can remain held: retain its evidence and continue independent repairs.
Escalate only unavailable input, consequential intent or ungranted authority—not
routine implementation choices. Do not promise every hold can be removed safely.

Never repeat a recovery that already failed. If a requeue or retry returns the same
failure, investigate before trying again: read the log and report to tell an aborted
process (killed, timed out, out of memory, crashed before any result) from a suite
that completed with failing tests, and name the failing tests or the abort signal.
A generic "crashed" message is not a diagnosis.

Protect agreed priority, native dependencies and pauses. Before editing, re-read
the issue and its actual ownership; never rewrite a running worker's contract.
Use [issue edits](references/record-edits.md) for decisions, scope corrections and
supersession. A note never grants live authority. Preserve prior candidates and
failed evidence; retirement is not completion.

A recovery counts only when delivered: validate it, commit only attributable
files, and observe consumption or report the precise pending operation. A local
edit, new label or saved answer is not execution. Never enable a paused deployment
to consume an answer. Keep existing local task records and recovery state intact.

## 5. Close out

Commit only attributable, verified repair/document files and affected tests.
Preserve unrelated dirty changes. Issue-only decisions need no local-main commit.
This workflow never pushes; separately requested publication uses Git Commit Push
under its existing authority. Read back issue state and report separately: plan
corrected, repair delivered, consumed, executing and accepted. A successor may
still wait on the original unfinished prerequisite.

## 6. Report to the owner

The owner reads this on a phone. Start with how many questions genuinely need
them, then group work as needs you, authorized technical recovery, and waits on
other work. Name each remaining cause and its next action. Use fresh GitHub/PR
and deployment evidence with its time; stale status is not a new owner question.
Do not claim an issue edit resumed work. Keep internal receipt details out of the
summary unless requested, while retaining them in their existing evidence owner.

## Boundaries

- Not plan review; use `/grilling`.
- Not broad implementation; use `/work` for accepted implementation scope.

**Done when:** each held task or owner question is answered, released within authority, or reported with the precise missing input.
