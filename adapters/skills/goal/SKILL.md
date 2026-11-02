---
name: goal
description: "Keep one objective alive until evidence proves it done."
disable-model-invocation: true
---

# Goal

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host contract](../COMMON.md), then follow the
[goal skill](../../../skills/goal/SKILL.md) in this session. Keep the goal contract
and state visible in the conversation. Do not create a goal file, task record,
database, hook or background process.

Host commands:

- Pi: `/goal`
- Claude Code: `/kit:goal`
- Codex: `$kit:goal`
- Hermes: the native `/goal` loop owns the name. Use `kit:goal` only when that native
  loop is unavailable. Do not replace or reconfigure the native command.

A goal is thread-scoped. Use the host's native goal store or tools when present.
Otherwise restate the state after a resume or compression. This adapter adds no
state and no automatic continuation.

The goal skill keeps its own scope, evidence and completion rules. Planning,
execution, delivery and live operations keep their own commands and authority.
