---
name: orbi
description: "Inspect and manage local Orbi deployments."
disable-model-invocation: true
---

# Orbi

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Use the [host contract](../COMMON.md) and
[host-neutral workflow](../../../skills/orbi/SKILL.md). Pi supplies both in the
command message; use that supplied text without reloading it. On other portable
hosts, load missing instructions together before interpreting the request.
Resolve the helper and references from the canonical workflow's directory, not
this adapter. The canonical workflow owns the invocation contract; its helper
owns runtime semantics. Keep any host-required tool-result continuation to the
workflow's receipt relay; it is not another routing or planning pass.

## Boundaries

Explicit invocation only. Activation follows the canonical workflow above.
Use the existing planners for GitHub issue publication and
`/unblock` for recovery rather than lifecycle control. `/update-kit` owns Kit updates.

**Done when:** the loaded workflow's completion condition is met and only observed
results are reported.
