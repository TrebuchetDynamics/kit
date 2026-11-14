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
| An Orbi-owned planning substep | Stay inside the named task and its authorized prerequisites; return findings and records to that same coordinator. |

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
accepted decisions, GitHub Issues and their linked PRs, and active task
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

When called by Orbi, investigate its named uncertainty and return to the current
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

Save meaningful decisions in their existing document owners; keep proposals and
remaining questions scoped to affected work. Run the
[builder check](../shared/PLANNING-CRAFT.md#builder-check-before-handoff) and resolve
material findings before publication. Reuse the answers and evidence already gathered.

Follow [Plan Handoff](../shared/PLAN-HANDOFF.md) for idempotent GitHub Issue
publication, native `blockedBy` dependencies and optional `ai-epic` coordination.
GitHub Issues, not `tasks/` or a local-main commit, are executable-work authority.
Each issue includes outcome, scope, exclusions, acceptance, verification commands
and governing sources. Read back the entire batch and publish `ai-ready` last.
All issue authors receive that default; incomplete planning retains `ai-planning`.
Explicit no-dispatch requests withhold readiness. Read-only/questions-only/no-write
or dry-run requests make no local or GitHub writes. Failed persistence is **UNSAVED**,
not a complete handoff or a reason to create a second queue.

Report issue URLs, decisions and planner calls, unresolved choices, native
dependencies and actual checks. Readiness is not pickup, PR delivery or merge.
An existing Orbi deployment can consume published work immediately. Stop planning
without implementing or starting a service. A delivery-owned substep returns to
its same coordinator. Runtime failure without new product uncertainty goes back
to that coordinator with the existing issue, failed operation and candidate evidence;
do not create replacement work or reopen the product interview.

## Execution handoff

Use the [execution handoff](../shared/PLAN-HANDOFF.md#execution-handoff): Orbi owns
Pi implementation, tests, PR creation, independent review and merge gates.
A published plan is not evidence those steps ran. No legacy runner starts here.

## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; a
saved plan is not execution.

| Rationalization | Reality |
| --- | --- |
| "The request is vague, so ask for a goal first." | Bare or vague Plan For Me runs discovery. Investigate the repository first. |
| "A well-written proposal is accepted scope." | New product directions stay proposals until the owner accepts them. |
| "A plan without tasks is enough." | The handoff needs complete GitHub Issues with acceptance, verification and bounded scope. |
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
- Not implementation; Orbi delivers published issues; `/work` is an explicit manual alternative.
- Not an Orbi-owned execution; return to that coordinator.

**Done when:** open questions are answered or kept on affected tasks, and the plan and its tasks are saved and validated.
