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

LGTM is a yes. Resolve the latest assistant-owned checkpoint and accept its
recommendation. A question round with recommended answers is a go: accept every
recommendation, state the accepted scope, and perform the proposed work once with
normal verification. If the checkpoint reports completed work, acknowledge without
repeating it. Preserve exclusions and any earlier "no push"/"no deploy" limit; do
not infer commit/push/deployment from a generic approval that did not recommend or
offer it. Ask only when the checkpoint offers materially different outcomes with no
recommendation and no safe default exists.
