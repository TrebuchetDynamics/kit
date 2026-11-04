---
name: plan-for-me
description: "Research and save a plan without an interview."
license: MIT
metadata:
  version: 0.5.0
  hermes:
    tags: [research, requirements, documentation, planning]
---

# Plan For Me

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

The autonomous adapter over the [shared planning protocol](../shared/RESEARCH-PLAN.md#shared-planning-interface).
It investigates the repository, decides an approach within the user's scope, and
saves the plan and tasks. With a concrete objective it determines how to achieve
it; with little or none it discovers which evidence-backed objectives matter most.
Read the protocol first, then the [planning craft](../shared/PLANNING-CRAFT.md), the
pinned [Autoresearch plan protocol](../autoresearch/upstream/plan.md) and the
[planning adaptations](../shared/RESEARCH-PLAN.md). Follow the
[shared contract](../shared/COMMON-CONTRACT.md) and
[plan handoff](../shared/PLAN-HANDOFF.md). For aspirational quality goals,
superseded limitations, state-transition changes, blocker or unblock requests,
security-remediation exceptions, requests to finish faster, game animation or level
expansion, and validation-performance planning, load the matching section of
[special cases](references/special-cases.md).

## Route the request

Decide from the request's meaning, not from a short phrase list:

| Request | Route |
| --- | --- |
| No concrete objective; "plan this project"; "make it better"; a broad direction such as "improve reliability" or "improve performance" | Autonomous discovery: read [autonomous project discovery](references/discovery.md), investigate the repository, derive accepted and engineering goals, then save one executable frontier. Do not ask for a goal before investigating. |
| A named outcome, feature, defect, spec slice or accepted plan | Focused planning for that outcome and its authorized prerequisites; do not expand into unrelated project work. |
| Read-only, chat-only, no-write or dry-run | Use the matching route above but save nothing, including queue metadata. |
| An Autowork-owned planning substep | Stay inside the named task and its authorized prerequisites; return findings and records to that same coordinator. |

A bare `/plan_for_me` is a discovery request, not an interview. A vague adjective
("better", "premium", "faster") is a direction for discovery, not an accepted
outcome. A supplied objective wins even when short. If the repository has no
accepted objective or meaningful source, report the missing product intent and the
one decision that would create it; do not manufacture a roadmap to fill the queue.
New product directions stay proposals and never become runnable tasks by being
well written.

## Investigate and decide

Size the work first and say the size in plain words: a clear task gets one complete
saved task record without an interview; a project gets a written plan section and
tasks with real dependencies. A bare or vague request is project discovery: say so,
then establish the project model and the evidence-backed goal classes before choosing
the frontier. Plan all requested projects in one coherent batch, retaining
independent ready lanes.

Inspect project instructions, relevant implementation and tests, existing docs,
accepted decisions, `autowork tasks list` and the records it names, and active task
ownership. Reuse existing answers and task IDs. Compare practical approaches and
record the evidence for the selected one. Own the complex part: resolve design,
decomposition, interfaces and acceptance within delegated scope, and choose
reversible engineering details yourself rather than leaving them as worker
permission questions. Hand off the smallest clear outcome, decided approach, exact
checks and stop conditions. Record a delegated planner decision as such, never as a
user selection. Ask only after investigating for genuinely missing product intent or
external authority, and continue independent work. Never invent acceptance or reopen
settled choices without new evidence.

Write down what the user asked for as theirs and everything else as yours: goals,
non-goals and anti-goals (what would make the result a failure even if it works),
constraints, and every default you chose, each marked as the planner's call so the
user can reject it. Generate several approaches before choosing; record the rejected
ones only when the reason is non-obvious. Surface any contradiction between the
request and the code instead of planning around it. Name new domain terms precisely
and record them, and give a decision its own ADR only when it is hard to reverse,
surprising without context and a real trade-off.

When called by Autowork, investigate its named uncertainty and return to the current
task. For held or blocked work, read the existing task, latest runs and retained
candidate evidence; classify the observed source and phase. Use
[decision closure](../shared/PLANNING-CRAFT.md#decision-closure) to resolve focused
tasks and discovered frontiers, record planner calls, and keep only genuinely
owner/external-blocked affected tasks pending.

- Resolve engineering planning choices within delegated scope, recording the
  supported approach and checks as the planner's call, not an owner question.
- If an existing task or candidate has a runtime, transport, gate or continuation
  failure without new product uncertainty, return the exact failed operation, task
  ID, attempt evidence and source-bound candidate evidence to the same coordinator
  for supported recovery. Report missing evidence as unassessed, never invented.
  Reuse the existing task and candidate: no new interview, replacement task or
  acceptance split just to get moving. Save new findings in the existing task; do
  not implement recovery or redispatch inside planning.
- Keep genuinely unavailable external, owner or physical-access inputs pending only
  on affected tasks, with the exact missing input and resume condition; continue
  independent authorized planning.
- Split only when authorized scope and evidence justify decomposition, not merely
  because runtime failed; preserve existing task IDs, contracts, acceptance and
  history, and never silently waive acceptance.

## Save the plan and hand off

Follow the shared protocol's save and validate steps. Use
[Docs Sync](../docs-sync/SKILL.md) to persist findings and decisions in the existing
document owners. Reuse Docs Sync's capability/prepare flow against the actual
consumer: require `prepare_api` 4 or higher, inspect the reported outcome, and never
call a deferred conversion or activation-pending consumer ready. Reuse that result
while its inputs are unchanged; do not duplicate its conversion matrix, force
conversion, install updates or interrupt workers to complete planning.

Apply the [single-pass handoff](../shared/PLAN-HANDOFF.md#one-planning-pass-one-handoff).
Save the batch as task records with `autowork tasks add
--goal G --title T --short S --scope ... --acceptance ... --checks ... --touches ...
--depends-on ...`, adding or updating its goal first with `autowork tasks goal`.
Include acceptance criteria, dependencies, verification and Now/Next placement;
distinguish proposed decisions from accepted scope. Save observable criteria in
`acceptance` and exact verification commands in `checks`. Give each executable task
`touches` from the paths your investigation found, and `resources` where needed, per
the [work center](../shared/TODO-WORKCENTER.md). Set further fields and notes such as
`Sources:` with `autowork tasks field`. For literal prose, write JSON with a
file-writing tool and use `--json`; after an earlier material read, carry `show ID
--worktree`'s `record_revision` to the update's `--expect REV`. On refusal reread,
reconcile and reapply only the authorized delta, never a stale snapshot or blind
retry.

For future work whose content depends on implementation evidence, follow
[rolling planning](../shared/TODO-WORKCENTER.md#rolling-planning). Run the
[builder check](../shared/PLANNING-CRAFT.md#builder-check-before-handoff) and fold
its answers in. Validate changed docs and run `autowork tasks validate --worktree .`;
fix every error and every draft you did not mean. Commit the batch once. Put the
accepted-plan anchor in each affected task's `Sources:` note and its goal's
`source`. Close a finished planning task with `autowork tasks done ID --by WHO
--reason TEXT [--evidence REF]`; it writes no verification receipt.

After the commit, `autowork tasks why ID` reports committed-store selection
eligibility and position only, not resource/ownership admission, capacity or
dispatch. Report the selection-ready first task separately from a dependent
successor: a successor waiting on its dependency is normal ordering, not a blocker.
Distinguish a branch-local commit from delivery to the actual canonical consumer:
disclose whether that consumer includes the commit and whether selection was checked
there. Report runtime and ownership unassessed unless observed.

For a rolling plan, the final report says the chain will continue on its own, gives
its round limit, and explains how to stop it: move the planning task to `Needs
decision`. Save the chain without starting a runner or granting execution authority.
Docs-only scope leaves the full requested batch undispatched. A later explicit
instruction to implement enters the execution workflow. An Autowork-owned planning
substep returns the batch to its same coordinator without another permission
question; preserve its review and owned-commit requirements.

When existing execution fails without new product uncertainty, return the exact task
ID, attempt evidence and failed operation to the same coordinator for supported
recovery; do not reopen the product interview or create duplicate tasks.

## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; a
saved plan is not execution.

| Rationalization | Reality |
| --- | --- |
| "The request is vague, so ask for a goal first." | Bare or vague Plan For Me runs discovery. Investigate the repository first. |
| "A well-written proposal is accepted scope." | New product directions stay proposals until the owner accepts them. |
| "A plan without tasks is enough." | The handoff needs complete task records with acceptance, checks and `touches`. |
| "The queue is short, so invent useful work." | Save only the evidence-backed frontier. A short queue is not permission to invent work. |
| "I can write code or tests while planning." | Planning writes docs and task records; implementation needs its own authorization. |

## Red Flags

- A goal question before repository investigation.
- A roadmap or prose plan with no task records.
- A proposal marked accepted without an owner answer.
- Code, tests or fixtures written during planning.
- Acceptance or evidence invented to make the queue look ready.

## Boundaries

- Not an interactive interview; use `/plan-with-me`.
- Not implementation; use `/autowork` after the plan is accepted.
- Not an Autowork-owned execution; return to that coordinator.

**Done when:** open questions are answered or kept on affected tasks, and the plan and its tasks are saved and validated.
