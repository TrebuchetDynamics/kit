---
name: autowork
description: "Inspect GitHub delivery through Orbi."
disable-model-invocation: true
---

# Autowork (deprecated runner entrypoint)

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host contract](../COMMON.md), then follow the
[host-neutral workflow](../../../skills/autowork/SKILL.md).
Use the same GitHub issue and Orbi contract on every host; host availability does
not permit a fallback to the retired local task queue or runner.

Explicit invocation only. Keep read-only and no-write requests nonmutating.
If a required GitHub or Orbi tool is unavailable, report the exact failure and
next action rather than claiming remote publication or execution.

## Boundaries

Use `/plan-for-me` or `/plan-with-me` for planning, `/pending` for read-only status,
and `/work` for explicit manual implementation with coordinated ownership.
This adapter adds no execution or publication authority beyond its loaded workflow.

**Done when:** the loaded workflow's completion condition is met and only observed
results are reported.
