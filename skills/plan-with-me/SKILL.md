---
name: plan-with-me
description: "Plan together through questions and research."
license: MIT
metadata:
  version: 0.5.0
  hermes:
    tags: [interview, requirements, documentation, planning]
---

# Plan With Me

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

The interactive adapter over the [shared planning protocol](../shared/RESEARCH-PLAN.md#shared-planning-interface).
It researches the repository, finds out what the user wants through focused
questions, and saves the plan and tasks. Read the protocol first, then the
[planning craft](../shared/PLANNING-CRAFT.md), the pinned
[plan protocol](../autoresearch/upstream/plan.md) and the
[interactive adaptations](../shared/RESEARCH-PLAN.md#interactive-planning-plan-with-me).
Follow the [shared contract](../shared/COMMON-CONTRACT.md) and
[plan handoff](../shared/PLAN-HANDOFF.md). For cancelled tasks, blockers, pending-task
lists, validation performance, simpler test cleanup, companion frontends, onboarding
pages, teaching, investor briefs, jurisdiction changes, long interviews and live
gates, load the matching section of [special cases](references/special-cases.md).

`/plan_with_me` (`/plan-with-me` also works in CLI) starts an interview about the
current repository; arguments narrow the topic, including literal input beginning
with `blockers`. For held work, inspect saved decisions and current issue/PR evidence
before asking for missing intent
([special cases](references/special-cases.md#blockers-and-recovery)). Its default
scope includes saving answered decisions and maintaining affected docs. Only
`questions only`, `read-only`, `no changes` or `dry run` means no file changes; an
audit or an "is it ready?" question is planning like any other and ends with tasks
([audits and readiness](references/special-cases.md#audits-and-readiness-questions)).
It does not perform code changes or start a service. Standalone planning narrows
this occurrence despite earlier unrelated implementation permission; an
Orbi-owned planning substep returns to that same coordinator without execution
inside the substep.

For recovery, changed baselines or stale audits, apply the shared
[recovery, provenance and qualification rules](../shared/PLANNING-CRAFT.md#recovery-provenance-and-qualification).

## Challenge mode

For “grill me”, “challenge this plan” or the compatibility `/grill_me` command,
read [the questioning protocol](../grill-me/SKILL.md) on demand. This is a mode of
Plan With Me, not a second planning workflow. Its decision tree drives the order:
ask only frontier decisions whose prerequisites are settled, and work in rounds.
No exhaustive interrogation or repeat approval of settled answers.

## Learn enough to ask a useful question

First apply [conversation intake](../shared/PLAN-HANDOFF.md#conversation-findings-to-issues)
to earlier analyses, grill answers and UI findings; settled answers stay settled.
Read repository instructions, the user's current request, relevant existing docs,
glossary, accepted decisions and scoped source/tests. Reuse the actual
README/PRD/spec/ADR and backlog owners; do not perform a full docs-sync bootstrap
before asking. Distinguish implemented behavior from intended behavior. Facts are
yours to find; never ask for something the repository can answer, or reopen a
settled answer without new contradictory evidence.

Size the work and track its [consequential uncertainty](../shared/PLANNING-CRAFT.md#consequential-uncertainty).
A fully specified request needs no interview: briefly explain that no material
product choices remain, save the complete requested batch and stop planning.
Otherwise the first response has two parts, in this order:

1. A short playback: what they want and why, in their words; what already exists
   that it builds on; and the draft shape, the tasks you would save, one line each
   and marked as a draft. Mark guesses as guesses.
2. One question, the highest-impact decision still open. The request's own words
   are answers: never ask to confirm what it already says.

When intent is thin, ask an open question that gets them describing a real moment.
A choice between options gives your recommendation first, with its trade-off. Do not
habitually offer to skip before making a useful inquiry. If the user explicitly
switches to Plan For Me, continue with the evidence and answers already gathered;
record delegated choices as the planner's calls.

## Ask, listen, adapt

Use `clarify` when available or ordinary chat when it is not, in plain language that
matches the user's vocabulary, never process jargon. Get them describing before
offering options. Offer a short menu only when they are stuck, or when choosing
among concrete alternatives the evidence has already narrowed; then give two or
three options with a recommendation and its trade-off. When they say "just guess"
or "what do you think?", propose something concrete. Allow a free-form answer.

Work in rounds using the [uncertainty loop](../shared/PLANNING-CRAFT.md#consequential-uncertainty).
Ask the highest-impact ready question, then wait. If presenting a few independent
ready decisions together, number them and make each choice and its trade-off
explicit. Apply the linked loop's round-scoped acceptance rule to clear recommended
batches; clarify only unresolved choices. A question whose prerequisites are open
belongs to a later round.

After every answer, update only the uncertainty it resolves, investigate changed
repository facts, and ask the next consequential question. One answered question is
not a finish condition. Across a bulk batch, ask a shared constraint once and apply
its answer to all affected tasks; keep unrelated ready work independent. Cover the
ground in [planning craft](../shared/PLANNING-CRAFT.md#cover-the-ground-not-a-script)
only where it is unresolved and relevant.

For vague words such as "fast" or "easy", ask for a concrete user situation or
acceptable outcome. When an answer contradicts accepted intent or the code, explain
the conflict and ask which direction governs; preserve history rather than silently
replacing it. `You decide` delegates that choice: recommend and record a compatible
decision inside the stated constraints as the planner's call. It does not grant
unrelated execution or publication authority. `Skip` leaves the question open;
`stop` ends questioning and preserves answered progress. Silence is neither an
answer nor acceptance. In scheduled/noninteractive runs, report the single
highest-value question and leave it pending; do not fabricate replies or poll.

## Save answers and finish the plan

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

Use the shared [progress and final receipt](../shared/PLAN-HANDOFF.md#progress-and-final-receipt):
preview outcomes, acceptance and issue dependencies in chat before publication;
then replace proposed keys with read-back links and actual publication states.
Stop planning without implementing or starting a service. A delivery-owned substep returns to
its same coordinator. Runtime failure without new product uncertainty goes back
to that coordinator with the existing issue, failed operation and candidate evidence;
do not create replacement work or reopen the product interview.

## Execution handoff

Use the [execution handoff](../shared/PLAN-HANDOFF.md#execution-handoff): Orbi owns
Pi implementation, tests, PR creation, independent review and merge gates.
A published plan is not evidence those steps ran. No legacy runner starts here.

## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; a saved
plan is not execution.

| Rationalization | Reality |
| --- | --- |
| "Ask what the repository can answer." | Find repository facts yourself. Ask only for missing intent, authority or input. |
| "Batch acceptance also settles unanswered alternatives." | Accept the latest round's clear recommendations; clarify only genuinely unresolved choices under the uncertainty loop. |
| "A polished proposal is accepted scope." | Proposals stay proposed until the owner accepts them. |
| "I can write code while waiting for an answer." | Planning writes docs and task records. Implementation needs its own authorization. |
| "Silence means agreement." | Silence is neither an answer nor acceptance. Leave the question open. |

## Red Flags

- Asking for facts the repository already answers.
- Unanswered alternatives treated as settled, or clear batch approval questioned again.
- A proposal marked Accepted without an owner answer.
- Code, tests or fixtures edited during the interview.
- Settled questions asked again without new evidence.

## Boundaries

- Not unattended discovery; use `/plan-for-me`.
- Not implementation; Orbi delivers published issues through PR and review gates.
- Challenge mode loads `/grill-me`; the interview engine is `/grilling`.

**Done when:** the requested interview round ends at the next owner question, or settled work has a verified issue handoff. For a read-only request, return the question or plan inline. Identify any failed handoff as UNSAVED.
