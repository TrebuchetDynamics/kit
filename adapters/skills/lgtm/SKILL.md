---
name: lgtm
description: "Accept the latest recommendation and continue."
disable-model-invocation: true
---

# Lgtm

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host-neutral LGTM — yes, continue workflow](../../../skills/lgtm/SKILL.md) first.

Read the [host contract](../COMMON.md).

LGTM is a yes and a low-effort instruction. Resolve the latest assistant-owned
checkpoint and accept its recommendation. A question round with recommended answers
is a go: accept every recommendation, state the accepted scope, and perform the
proposed work once with normal verification. Use the safe reversible default when a
question has no recommendation; ask only when materially different outcomes have no
recommendation and no safe default exists. Do not require the user to restate the
scope or reply “confirmed”, and do not repeat the plan. If the checkpoint reports
completed work, acknowledge without repeating it. Preserve exclusions and any
earlier “no push”/“no deploy” limit; do not infer commit/push/deployment from a
generic approval that did not recommend or offer it. End every checkpoint you write
with exactly one recommended action and the check that verifies it; a closing
“or do X” is a menu, and LGTM accepts the first stated recommendation.
