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
Use its research and persistence method, with the user participating in
consequential decisions. Read that authority contract first, then the
[planning craft](../shared/PLANNING-CRAFT.md) and pinned
[plan protocol](../autoresearch/upstream/plan.md); adapt its phases with the interview
steps below. Already-loaded sources need no reread, including a contract supplied
inline by the host. Do not invoke Plan For Me as another coordinator or repeat its
discovery pass.
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
audit or an "is it ready?" question is planning like any other and accounts for
its findings
([audits and readiness](references/special-cases.md#audits-and-readiness-questions)).
It does not perform code changes or start a service. Standalone planning narrows
this occurrence despite earlier unrelated implementation permission; an
Orbi-owned planning substep returns to that same coordinator without execution
inside the substep.

For recovery, changed baselines or stale audits, apply the shared
[recovery, provenance and qualification rules](../shared/PLANNING-CRAFT.md#recovery-provenance-and-qualification).

## Challenge mode

For “grill me”, “challenge this plan”, the compatibility `/grill_me` command or
`Selected mode: challenge`, read [the questioning protocol](../grill-me/SKILL.md).
Otherwise load it only when that depth is useful or requested. Think wide privately
to expose alternatives; its decision tree challenges important assumptions, failure
cases and costly choices. This is a mode of Plan With Me, not a second planning
workflow. Ask only frontier decisions whose prerequisites are settled, in rounds.
This interview's round size, scope and stop rules override grill's exhaustive
questioning. Use its planning synthesis when choices are settled. Do not ask every
possible question or repeat approval of settled answers.

## Learn enough to ask a useful question

First apply [conversation intake](../shared/PLAN-HANDOFF.md#conversation-findings-to-issues)
to earlier analyses, grill answers and UI findings; settled answers stay settled.
For focused and discovery requests, apply
[open-issue reconciliation](../shared/PLAN-HANDOFF.md#open-issue-reconciliation)
before proposing work; reuse that inventory through the interview and refresh
before writes, including when no interview is needed.
Read repository instructions, the user's current request, relevant existing docs,
glossary, accepted decisions and scoped source/tests. Reuse the actual
README/PRD/spec/ADR and backlog owners; do not perform a full docs-sync bootstrap
before asking. Distinguish implemented behavior from intended behavior. Facts are
yours to find; never ask for something the repository can answer, or reopen a
settled answer without new contradictory evidence.

Turn the initial prompt into a concise working brief: intended users, problem,
desired outcome, scope/non-goals, constraints and observable success. Separate
explicit requirements from assumptions and unresolved choices; improve clarity
without expanding the user's goal. Reuse this brief in the existing plan owner.

When a governing decision fixes the approach, cite it and proceed to acceptance
and verification. Compare practical approaches when a material choice remains;
bring consequential intent choices to the user and resolve delegated engineering
choices within scope.

Size the work and track its [consequential uncertainty](../shared/PLANNING-CRAFT.md#consequential-uncertainty).
A fully specified request needs no interview: briefly explain that no material
product choices remain. In no-write mode, return the complete plan inline and write
nothing. In writable mode, preview the batch, then follow Plan Handoff.
Otherwise the first response has two parts, in this order:

1. A short playback: what they want and why, in their words, and what already
   exists that it builds on. Include draft tasks only when supported by known intent
   and evidence, one line each and marked as a draft. With thin intent, use zero
   invented tasks; omit the draft task list until an outcome is supported.
   Mark guesses as guesses.
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
explicit. Apply the linked loop's round-scoped acceptance rule to a bare “yes” or
LGTM, including clear recommended batches; clarify only genuinely ambiguous choices.
A question whose prerequisites are open
belongs to a later round.

After every answer, update only the uncertainty it resolves, investigate changed
repository facts, and ask the next consequential question. One answered question is
not a finish condition; do not complete a speculative plan before learning intent.
Across a bulk batch, ask a shared constraint once and apply
its answer to all affected tasks; keep unrelated ready work independent. Cover the
ground in [planning craft](../shared/PLANNING-CRAFT.md#cover-the-ground-not-a-script)
only where it is unresolved and relevant.

For vague words such as "fast" or "easy", ask for a concrete user situation or
acceptable outcome. When an answer contradicts accepted intent or the code, explain
the conflict and ask which direction governs; preserve history rather than silently
replacing it. `You decide` delegates that choice: recommend and record a compatible
decision inside the stated constraints as the planner's call. It does not grant
unrelated execution or publication authority. A skipped choice stays open; a
delegated choice becomes a planner call. Silence is neither an answer nor
acceptance. In scheduled/noninteractive runs, report the single highest-value
question and leave it pending; do not fabricate replies or poll.

Stop questioning once relevant intent and concrete acceptance are actionable,
with no fixed question count or filler for fully specified requests, or when the
user says finish/stop (including confirmation questions). Preserve corrections
and reuse accepted decisions on resume; keep remaining questions only on affected
work.

## Save answers and finish the plan

Save answers, evidence, decisions and task records in one coherent affected batch
in their existing owners; meaningful interim answers may be saved for continuity.
Do not require another interview or a complete documentation pass per answer.
Distinguish the user's choices from delegated engineering choices, proposals and
unverified assumptions. A refined prompt alone is not the writable-mode deliverable;
in no-write mode return it in chat instead. Run the
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

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; a saved
plan is not execution.

| Rationalization | Reality |
| --- | --- |
| "One failed write makes the whole batch unsaved." | Use the linked per-issue partial receipt and reconcile before retrying. |
| "Every request needs an interview and a draft task list." | Skip questions for settled intent; show only evidence-supported drafts. |
| "A settled approach needs another comparison." | Cite its governing decision; compare only material open choices. |
| "Ask what the repository can answer." | Find repository facts yourself. Ask only for missing intent, authority or input. |
| "Batch acceptance also settles unanswered alternatives." | Accept the latest round's clear recommendations; clarify only genuinely unresolved choices under the uncertainty loop. |
| "A polished proposal is accepted scope." | Proposals stay proposed until the owner accepts them. |
| "I can write code while waiting for an answer." | Planning writes docs and task records. Implementation needs its own authorization. |
| "Silence means agreement." | Silence is neither an answer nor acceptance. Leave the question open. |

## Red Flags

- Whole-batch UNSAVED claims after partial publication, or blind replay of unknown writes.
- An interview for fully specified intent, or invented tasks in a thin-intent playback.
- Alternative approaches generated only to reopen a settled decision.
- Asking for facts the repository already answers.
- Unanswered alternatives treated as settled, or clear batch approval questioned again.
- A proposal marked Accepted without an owner answer.
- Code, tests or fixtures edited during the interview.
- Settled questions asked again without new evidence.

## Boundaries

- Not unattended discovery; use `/plan-for-me`.
- Not implementation; Orbi delivers published issues through PR and review gates.
- Challenge mode loads `/grill-me`; the interview engine is `/grilling`.

**Done when:** the requested interview round ends at the next consequential owner
question, or settled work has a verified handoff or explicit disposition. No-write
requests return the question or complete plan inline. Failed publication uses the
[per-issue partial receipt](../shared/PLAN-HANDOFF.md#publication-receipt).
