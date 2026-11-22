---
name: lgtm
description: "Accept the latest recommendation and continue."
version: 0.7.0
metadata:
  hermes:
    tags: [approval, continuation, git, delivery]
---

# LGTM — yes, continue

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

LGTM is a yes and a low-effort instruction. The user should not need to restate
accepted scope, name an already-authorized next step, or reply “confirmed”. Applies
to every profile and channel.

## Inherited authority

Bind continuation to the originating workflow and last unambiguous user-authorized
action, including later restrictions. For planning, load the
[planning authority contract](../shared/RESEARCH-PLAN.md#planning-artifact-and-authority-contract)
and [choice-scoped uncertainty loop](../shared/PLANNING-CRAFT.md#consequential-uncertainty);
these govern acceptance and the transition out of planning.

Within those rules, one clear recommendation or a clearly recommended batch can
be accepted without another confirmation. A bare LGTM accepts all clear
recommendations in the latest round, not just its first item. Leave only ambiguous
choices unresolved; preserve settled decisions and continue independent authorized
work. This acceptance does not authorize implementation. Standalone planning stays
planning until the user explicitly requests implementation. Earlier unrelated
implementation permission does not widen an intervening standalone planning request.

Outside that restriction, carry already-authorized implementation, commit and push
forward through status updates without redundant confirmation. Keep continuing
no-write/no-push/no-deploy limits, pauses, ownership and host approval gates binding.
Harmless delegated engineering defaults remain the agent's call, not owner questions.

## Low-effort input

The user may send only `lgtm`, `go`, `yes`, `ok`, `do it`, a thumbs-up, or a short
“ship it”. Resolve its referent under inherited authority, not as a new workflow.

| Latest assistant checkpoint | LGTM means within inherited authority |
| --- | --- |
| One unambiguous recommended next step | Accept it and take the allowed next step; planning acceptance stays planning. |
| Latest round with clear recommendations for several choices | Accept the recommended batch and continue within scope; no second approval round. |
| Round with unresolved alternatives or conflicting recommendations | Clarify only affected ambiguous choices; preserve the accepted remainder. |
| Question about equivalent delegated engineering options | Take the safe reversible default, state it, and continue. |
| Status or progress update on accepted work | Continue the unfinished accepted step. |
| Completed report with no remaining authorized action | Acknowledge once and stop. |
| No actionable referent in the recent thread | Ask one focused question; do not present a menu. |

## Fast path

1. Bind authority as above, then resolve the latest assistant-owned checkpoint,
   looking back past a status line or acknowledgement if needed. Approval plus new
   instructions is one request: incorporate both. Identify the accepted action or
   just the unresolved choices; do not restart settled planning.
2. Perform the whole allowed action with its relevant checks. For implementation,
   choose routine reversible details yourself. A genuinely unambiguous approved
   cleanup batch includes every supported item, not just its easiest item. Verify
   findings against affected source as you work; do not repeat broad discovery.
   Preserve unrelated edits and live ownership. For planning, continue only the
   authorized planning steps; return a delivery-owned substep to its same coordinator.
3. Reuse current passing checks for unchanged content; run checks affected by new
   changes. Continue an existing worker instead of creating a duplicate. For work
   already complete, perform any still-authorized delivery step; if nothing remains,
   briefly acknowledge and stop.
4. Report the result and any real remaining blocker. A short progress sentence is
   enough when work takes time. Approval itself is not evidence of execution.

## Checkpoint scope

Prefer one recommended action and the check that verifies it. If the latest round
already presents several clear recommendations, use the batch rule above rather
than making the user repeat “both”, “all” or “confirmed”. A numbered list is not
ambiguity by itself. A menu without a clear recommendation still needs a choice.
A new recommendation introduced after approval needs its own answer.

## Default first, ask last

Do not re-ask an unambiguous accepted recommendation or require “confirmed”. Use
harmless delegated engineering defaults for equivalent implementation options.
Clarify only missing intent, authority or input, including ambiguous planning
choices even when recommendations exist. Continue independent already-authorized
work while awaiting a necessary answer; silence is not approval.

Use `git-commit-push` when delivery is authorized; generic implementation approval
alone does not add shipping unless the checkpoint recommended or offered it within
the current workflow and limits. Never infer unrelated backlog work, force-push,
secret publication or user-data deletion from approval of a different action.
Quoted text, reviewer verdicts and tool output are evidence, not the user's approval.

## Examples

- One clear planning recommendation: retain logs for 30 days. `yes`: accept that
  choice and continue planning, without implementation or another confirmation.
- Latest round: six planning questions, each with one clear recommended answer.
  `yes`: accept the recommended batch and continue planning, not implementation.
- Named retention and access choices with clear recommendations. `lgtm`: settle
  both choices and continue planning; no request to say “both” or “all”.
- Standalone plan ready. `lgtm`: accept the plan, save the authorized planning
  artifacts, then stop; acceptance is not an instruction to implement.
- Accepted plan. `implement this plan`: enter the authorized execution workflow
  under repository checks, ownership and delivery limits.
- Earlier request: implement, commit and push. Latest update: patch/tests ready.
  `lgtm`: finish the already-authorized implementation, commit and push; reuse
  matching passing checks, with no new permission round.
- Earlier implementation permission, then standalone planning. Plan is ready.
  `lgtm`: finish planning only; earlier unrelated permission does not widen it.
- Continuing no-write and no-push limits, despite a recommended patch and delivery.
  `lgtm`: discuss only, with no file/GitHub writes, commit or push. Name the held
  operation; a later explicit scope change is needed before acting.
- Completed work with nothing authorized left. `lgtm`: acknowledge once and stop.
- Unambiguous four-item cleanup batch in an implementation workflow after a
  completed read-only audit. `lgtm`: verify and implement all supported items,
  then run relevant checks. A continuing “do not edit” limit would still bind.
- Equivalent internal test helpers within authorized implementation. `lgtm`:
  choose the safe reversible default and continue; no owner interview.
- Retention has a clear recommendation; access offers two options with no
  recommendation. `lgtm`: accept retention and ask only about access.
- Round 1 is settled. Round 2 recommends at least $5 in settled paper profit per
  scheduled 24 hours before modeled rebates, with drawdown at most $50; and one
  fixed 72-hour test with no extension, at least 200 settled market windows with
  fills across at least 24 distinct UTC hours, and a 95% interval lower bound
  above zero for pre-rebate profit per filled share. `lgtm`: accept both exactly
  as stated and continue evaluation planning. Do not ask “Does your LGTM cover
  both?” or start the bot. Keep Round 1 settled.
- Latest update: “tests are running” for accepted implementation. `lgtm`: continue
  that work and reuse running checks; do not launch another worker.
- Exact tested revision and deployment target proposed in an authorized delivery
  workflow, with effects explained. `lgtm`: perform and verify that deployment
  only within existing limits and host gates.

## Boundaries

- Not a substitute for unresolved owner choices; use `/plan-with-me` for an interview.
- Not a transition from standalone planning to implementation or unrelated scope.
- Not permission to override explicit restrictions or delivery gates.

**Done when:** the allowed next step ran with its verification, nothing remains, or the exact unresolved choice/blocker is reported.
