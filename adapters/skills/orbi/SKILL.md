---
name: orbi
description: "Prepare, start, inspect or stop one Orbi deployment."
disable-model-invocation: true
---

# Orbi

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host contract](../COMMON.md), then follow the
[host-neutral workflow](../../../skills/orbi/SKILL.md).
Resolve its helper and references from that workflow's directory, not this adapter.

## Boundaries

Explicit invocation only. This adapter grants no deployment authority and does not
release pauses or live gates. Use the existing planners for GitHub issue publication and
`/unblock` for recovery rather than lifecycle control.

**Done when:** the loaded workflow's completion condition is met and only observed
results are reported.
