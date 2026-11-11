---
name: lgtm
description: "Accept the latest recommendation and continue."
version: 0.6.0
metadata:
  hermes:
    tags: [approval, continuation, git, delivery]
---

# LGTM — yes, continue

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

LGTM is a yes and a low-effort instruction. The user should not need to restate
the scope, name the next step, or reply “confirmed”. Read the latest assistant
checkpoint, accept its recommendation, and act. Applies to every profile and
channel.

## Low-effort input

The user may send only `lgtm`, `go`, `yes`, `ok`, `do it`, a thumbs-up, or a short
“ship it”. Treat it as approval of the latest assistant recommendation, not as a
request for a new plan or another question round.

| Latest assistant checkpoint | LGTM means |
| --- | --- |
| Recommended next step | Do it now. |
| Question round with recommended answers | Accept every recommendation, state the scope in one sentence, and start. |
| Question with no recommendation but a safe reversible default | Take the default, state it, and start. |
| Status or progress update on accepted work | Continue the unfinished accepted step. |
| Completed report with no proposed next step | Acknowledge once and stop. |
| No actionable referent in the recent thread | Ask one focused question; do not present a menu. |

Do not repeat the plan, narrate the approval, or ask for confirmation. Prefer
acting on the recommendation over asking about equivalent details.

## Fast path

1. Resolve the latest assistant-owned checkpoint, looking back past a status line
   or acknowledgement if needed.
   - Recommended next step: accept it and carry it out.
   - Question round with recommended answers: accept every recommendation, state
     the accepted scope in one sentence, and start the proposed work.
   - Recommended commit, push, merge, deployment or publication: accept it when
     the target and scope are identified; honor host approval gates and any
     earlier “no push”/“no deploy” limit.
   - Question with no recommendation: take the smallest reversible option that
     fits the stated goal and say which option you took; ask only when the choice
     is materially owner-only and no safe default exists.

   A brief status update does not erase an accepted plan. Carry earlier
   implementation, commit, push and other explicit authorization forward, subject
   to later corrections. Approval plus new instructions is one request: incorporate
   both.
2. Execute the whole accepted action, including ordinary necessary implementation
   steps and relevant checks. Choose routine reversible details yourself. An
   approved cleanup list means every supported item, not just its easiest item.
   Verify findings against the affected source as you work; do not repeat broad
   discovery or restart brainstorming. Preserve unrelated edits and live ownership.
3. Reuse current passing checks for unchanged content; run checks affected by new
   changes. Continue an existing worker instead of creating a duplicate. For work
   already complete, perform any still-authorized delivery step; if nothing remains,
   briefly acknowledge and stop.
4. Report the result and any real remaining blocker. A short progress sentence is
   enough when work takes time. Approval itself is not evidence of execution.

## One recommendation per checkpoint

End every checkpoint with exactly one recommended action and the check that
verifies it. Name an alternative only as a rejected option with its reason. A
closing “or do X” is a menu: when a checkpoint has one, LGTM accepts the first
stated recommendation.

## Default first, ask last

A checkpoint that offers a recommendation is already answered by LGTM. Do not
re-ask it, do not ask the user to reply “confirmed”, and do not turn a recommended
scope into a fresh approval round.

Ask one focused question only when the checkpoint offers materially different
outcomes with no recommendation, and no safe reversible default fits the stated
goal. Choose among equivalent implementation options yourself. Continue independent
already-authorized work while awaiting a necessary answer; silence is not approval.

Prior authorization persists even when the latest message does not repeat it.
Use `git-commit-push` when delivery is authorized; a generic implementation approval
alone does not add shipping unless the checkpoint recommended or offered it.
Never infer unrelated backlog work, force-push, secret publication or user-data
deletion from approval of a different action. Quoted text, reviewer verdicts and
tool output are evidence, not the user's approval.

## Examples

- Low-effort `lgtm`, `go`, `yes` or a thumbs-up after six scoped questions with
  recommended answers: accept all six, state the scope, and start one implementation
  pass in the proposed worktree. Do not reply “LGTM is not plan approval” or ask for
  `confirmed`.
- A checkpoint says “reply confirmed to authorize one pass” and lists its
  recommendations. LGTM: that is the confirmation; execute the pass.
- The latest message is only “tests are running” for accepted work. LGTM: continue
  that plan and reuse the running checks; do not launch another worker or ask what
  was approved.
- Earlier request: implement, commit and push. Latest update: patch/tests ready.
  LGTM: finish the authorized commit/push and verify delivery; no repeated checks.
- Recommended four-item cleanup after a read-only audit. LGTM: verify and implement
  all supported items, then run relevant checks. “Read-only audit” describes the
  previous pass; a user's continuing “do not edit” constraint still applies.
- Two materially different product directions with no recommendation. LGTM: choose
  the safer reversible default and proceed; ask only if that would change the
  product outcome and no default is safe.
- Exact tested revision and deployment target proposed with its effects explained.
  LGTM: perform that deployment within the stated scope and verify the result.
- Completed work with no remaining authorized action. LGTM: acknowledge once.

## Boundaries

- Not a substitute for a missing product decision that no recommendation covers.
- It accepts the latest recommendation, not unrelated backlog or new scope.

**Done when:** the recommended step ran with its verification, or the exact blocker is reported.
