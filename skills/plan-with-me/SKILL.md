---
name: plan-with-me
description: "Plan together through questions and research."
license: MIT
metadata:
  version: 0.4.0
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
current repository; arguments narrow the topic. `/plan_with_me blockers [repo|name]`
is [`/blockers`](../blockers/SKILL.md): routine planning repairs first, then genuine
owner questions, easiest first, planning each task that needs it with this skill
([special cases](references/special-cases.md#blockers-and-recovery)). Its default
scope includes saving answered decisions and maintaining affected docs. Only
`questions only`, `read-only`, `no changes` or `dry run` means no file changes; an
audit or an "is it ready?" question is planning like any other and ends with tasks
([audits and readiness](references/special-cases.md#audits-and-readiness-questions)).
It does not authorize code changes or start autowork. Standalone planning narrows
this occurrence despite earlier unrelated implementation permission; an
Autowork-owned planning substep returns to that same coordinator without execution
inside the substep.

## Challenge mode

For “grill me”, “challenge this plan” or the compatibility `/grill_me` command,
read [the questioning protocol](../grill-me/SKILL.md) on demand. This is a mode of
Plan With Me, not a second planning workflow. Its decision tree drives the order:
ask only frontier decisions whose prerequisites are settled, and work in rounds.
No exhaustive interrogation or repeat approval of settled answers.

## Learn enough to ask a useful question

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
explicit. A bare "yes" accepts one unambiguous proposal, never several separate
recommendations. A question whose prerequisites are open belongs to a later round.

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

Follow the shared protocol's save and validate steps. During an ongoing interview,
save material explicit answers in the existing owner when useful for continuity;
resolved terms go to the glossary owner as they settle. Keep unanswered issues and
inferred requirements clearly Open/Proposed. Never mark an entire plan Accepted
from one local answer. For a resumed interview, read saved answers and ask only what
remains unresolved. Apply the
[single-pass handoff](../shared/PLAN-HANDOFF.md#one-planning-pass-one-handoff);
save meaningful answers during the interview, then batch final documentation and
task-store checks once. Respect read-only scope and preserve concurrent edits, task
IDs and active leases. Keep a question scoped to the tasks it affects.

When no material intent/acceptance uncertainty remains, or the user asks to
finish/stop, end questioning and give a concise readback: outcome, users, success,
scope/non-goals/anti-goals, constraints, their decisions, the planner's calls and
remaining open questions. When the user has not asked to stop/finish, ask for
confirmation only if the synthesis introduces a material inference or unresolved
conflict. On stop/finish, leave such issues open without another question. Clear contextual
approval counts; do not demand a magic word. Approval covers what the user saw:
accepting a pitch does not approve an unseen mockup or added requirement.

In writable mode, run a narrow docs-sync Maintain pass for the affected document
owners. Accepted intent becomes bounded Now/Next tasks, saved with
`autowork tasks add` (and their goal with `autowork tasks goal`), with dependencies,
acceptance, verification and `touches` (plus `resources` where needed) per the
[work center](../shared/TODO-WORKCENTER.md). Cut and write them by the
[planning craft](../shared/PLANNING-CRAFT.md#size-each-task). For future work whose
content depends on implementation evidence, follow
[rolling planning](../shared/TODO-WORKCENTER.md#rolling-planning).

Run the [builder check](../shared/PLANNING-CRAFT.md#builder-check-before-handoff) on
the saved tasks and fold its answers in. Validate changed docs and run
`autowork tasks validate --worktree .`; fix every error and every draft you did not mean. Then commit
the batch once. Put the accepted-plan anchor in each affected task's `Sources:` note
and its goal's `source`. After the commit, `autowork tasks why ID` reports
committed-store selection eligibility and position only, not resource/ownership
admission, capacity or dispatch. Report the selection-ready first task separately
from a dependent successor: a successor waiting on its dependency is normal ordering,
not a blocker.

Finish with changed document paths, decisions captured, the planner's calls, open
questions and the actual selection result when `autowork tasks why` ran; otherwise
state that selection was not assessed. Distinguish a branch-local commit from
delivery to the actual canonical consumer: disclose whether that consumer includes
the commit and whether selection was checked there. Report runtime and ownership
unassessed unless observed. Questions-only/read-only mode finishes with a
conversational summary, no Maintain pass and no writes.

When existing execution fails without new product uncertainty, return the exact
task ID, attempt evidence and failed operation to the same coordinator for supported
recovery; do not reopen the product interview or create duplicate tasks. An
Autowork-owned planning substep returns the batch to its same coordinator without
another permission question; preserve its review and owned-commit requirements.

## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; a saved
plan is not execution.

| Rationalization | Reality |
| --- | --- |
| "Ask what the repository can answer." | Find repository facts yourself. Ask only for missing intent, authority or input. |
| "A bare yes accepts every recommendation." | A bare yes accepts one unambiguous proposal, never several separate recommendations. |
| "A polished proposal is accepted scope." | Proposals stay proposed until the owner accepts them. |
| "I can write code while waiting for an answer." | Planning writes docs and task records. Implementation needs its own authorization. |
| "Silence means agreement." | Silence is neither an answer nor acceptance. Leave the question open. |

## Red Flags

- Asking for facts the repository already answers.
- Several recommendations accepted by one bare yes.
- A proposal marked Accepted without an owner answer.
- Code, tests or fixtures edited during the interview.
- Settled questions asked again without new evidence.

## Boundaries

- Not unattended discovery; use `/plan-for-me`.
- Not implementation; use `/autowork` after the plan is accepted.
- Challenge mode loads `/grill-me`; the interview engine is `/grilling`.

**Done when:** open questions are answered, and the plan and its tasks are saved and validated.
