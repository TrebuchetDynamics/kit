---
name: plan-for-me
description: "Turn goals and findings into GitHub issues."
license: MIT
metadata:
  version: 0.6.0
  hermes:
    tags: [research, requirements, documentation, planning]
---

# Plan For Me

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

The autonomous adapter over the [shared planning protocol](../shared/RESEARCH-PLAN.md#shared-planning-interface).
It investigates the repository, decides an approach within the user's scope, and
turns goals and conversation findings into complete GitHub Issues for Orbi.
It previews the issue plan in chat before publication. With a concrete objective it
determines how to achieve it; otherwise it discovers evidence-backed objectives.
Read the protocol first, then the [planning craft](../shared/PLANNING-CRAFT.md), the
pinned [Autoresearch plan protocol](../autoresearch/upstream/plan.md) and the
[planning adaptations](../shared/RESEARCH-PLAN.md). Follow the
[shared contract](../shared/COMMON-CONTRACT.md) and
[plan handoff](../shared/PLAN-HANDOFF.md). For aspirational quality goals,
superseded limitations, state-transition changes, blocker or unblock requests,
security-remediation exceptions, requests to finish faster, game animation or level
expansion, and validation-performance planning, load the matching section of
[special cases](references/special-cases.md).

For recovery, changed baselines or stale audits, apply the shared
[recovery, provenance and qualification rules](../shared/PLANNING-CRAFT.md#recovery-provenance-and-qualification).

## Route the request

First apply [conversation intake](../shared/PLAN-HANDOFF.md#conversation-findings-to-issues)
to prior analyses, interviews and design reviews. An explicit target wins; concrete
findings in the current conversation supply the scope when no target is repeated.
Then route by meaning, not a short phrase list:

| Request | Route |
| --- | --- |
| "One failed write makes the whole batch unsaved." | Use the linked per-issue partial receipt and reconcile before retrying. |
| No concrete objective in the request or relevant conversation; "plan this project"; "make it better"; a broad direction such as "improve reliability" or "improve performance" | Autonomous discovery: read [autonomous project discovery](references/discovery.md), investigate the repository, derive accepted and engineering goals, then save one executable frontier. Do not ask for a goal before investigating. |
| A named outcome, feature, defect, spec slice or accepted plan | Focused planning for that outcome and its authorized prerequisites; do not expand into unrelated project work. |
| Read-only, chat-only, no-write or dry-run | Use the matching route above but save nothing, including queue metadata. |
| An Orbi-owned planning substep | Stay inside the named task and its authorized prerequisites; return findings and records to that same coordinator. |

A bare `/plan_for_me` after concrete findings plans those findings. Without that
context it is a discovery request, not an interview. A vague adjective
("better", "premium", "faster") is a direction for discovery, not an accepted
outcome. A supplied objective wins even when short. If the repository has no
accepted objective or meaningful source, report the missing product intent and the
one decision that would create it; do not manufacture a roadmap to fill the queue.
New product directions stay proposals and never become runnable tasks by being
well written.

## Investigate and decide

Size the work first and say the size in plain words: a clear task gets one complete
task contract without an interview; a project gets a written plan section and
tasks with real dependencies. In no-write mode, return the complete plan inline and
write nothing; otherwise preview and publish through Plan Handoff. When neither
request nor conversation supplies an objective, say that this is project discovery, then establish the project model and
evidence-backed goal classes before choosing the frontier. Plan all requested
projects in one coherent batch, retaining independent ready lanes.

Inspect project instructions, relevant implementation and tests, existing docs,
accepted decisions, GitHub Issues and their linked PRs, and active task
ownership. For focused and discovery requests, apply
[open-issue reconciliation](../shared/PLAN-HANDOFF.md#open-issue-reconciliation)
before proposing work and refresh before writes. Reuse existing answers and task IDs.
When a governing decision fixes
the approach, cite it and proceed to acceptance and verification. Compare practical
approaches when a material choice remains, recording the evidence and trade-off
for the selected one. Own the complex part: resolve design,
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
user can reject it. Record rejected alternatives only when the reason is non-obvious.
Surface any contradiction between the request and the code instead of planning around it. Name new domain terms precisely
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

Account for every actionable accepted outcome with a new or reused issue, or a
proposed contract inline in no-write mode. When missing intent, existing coverage
or no-write mode leaves no new issues to publish, report an explicit disposition
with evidence and any missing input/resume condition. Zero new tasks is not itself
failure; an unaccounted accepted outcome is.

In writable mode, save meaningful decisions in their existing document owners;
keep proposals and remaining questions scoped to affected work. Run the
[builder check](../shared/PLANNING-CRAFT.md#builder-check-before-handoff) and resolve
material findings before publication. Reuse the answers and evidence already gathered.

Follow Plan Handoff's [publication and dependencies](../shared/PLAN-HANDOFF.md#publication-and-dependencies),
[persistence rules](../shared/PLAN-HANDOFF.md#persistence-not-local-main-admission)
and [progress and final receipt](../shared/PLAN-HANDOFF.md#progress-and-final-receipt)
for the writable preview, validation and publication. For failed publication, use
its [per-issue partial receipt](../shared/PLAN-HANDOFF.md#publication-receipt).

Stop planning without implementing or starting a service. Return an Orbi-owned
substep to its same coordinator under the [execution handoff](../shared/PLAN-HANDOFF.md#execution-handoff).

## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; a
saved plan is not execution.

| Rationalization | Reality |
| --- | --- |
| "The request is vague, so ask for a goal first." | Reuse concrete conversation findings; otherwise investigate the repository through discovery. |
| "A well-written proposal is accepted scope." | New product directions stay proposals until the owner accepts them. |
| "No new tasks means planning failed." | Missing intent, existing coverage and no-write mode can justify an explicit disposition; account for every actionable accepted outcome. |
| "Every request needs competing approaches." | Cite a governing decision; compare approaches only for a material open choice. |
| "The queue is short, so invent useful work." | Save only the evidence-backed frontier. A short queue is not permission to invent work. |
| "I can write code or tests while planning." | Planning writes docs and task records; implementation needs its own authorization. |

## Red Flags

- Whole-batch UNSAVED claims after partial publication, or blind replay of unknown writes.
- A goal question before repository investigation.
- An actionable accepted outcome missing its issue or no-write proposed contract.
- A fresh audit instead of using the preceding findings, or issue links without outcomes.
- A proposal marked accepted without an owner answer.
- Code, tests or fixtures written during planning.
- Acceptance or evidence invented to make the queue look ready.
- New tasks invented to avoid reporting missing intent or existing coverage.
- A settled approach reopened without contradictory evidence.

## Boundaries

- Not an interactive interview; use `/plan-with-me`.
- Not implementation; Orbi delivers published issues through PR and review gates.
- Not an Orbi-owned execution; return to that coordinator.

**Done when:** every in-scope topic is mapped to a validated issue or explicit
disposition, every actionable accepted outcome is accounted for, and the chat
receipt shows outcomes, dependencies and observed publication state. No-write
requests return complete proposals inline. Failed publication uses the
[per-issue partial receipt](../shared/PLAN-HANDOFF.md#publication-receipt).
