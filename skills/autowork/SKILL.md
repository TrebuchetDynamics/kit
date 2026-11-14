---
name: autowork
description: "Inspect GitHub delivery through Orbi."
license: MIT
---

# Autowork (deprecated execution entrypoint)

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../shared/COMMUNICATION.md) for user-facing text.

Follow the [shared contract](../shared/COMMON-CONTRACT.md) and
[GitHub handoff](../shared/PLAN-HANDOFF.md).

The legacy Autowork execution system is retired. This compatibility command now
routes to GitHub and Orbi; it never starts, resumes, installs or schedules
`pi-autowork`. Existing code is retained for migration and recovery only.

## Inspect and hand off

1. Resolve the target repository and read its GitHub Issues, PRs, native dependencies
   and deployment configuration. Preserve explicit pauses and existing ownership.
2. For status, run `orbi status --config /path/to/orbi.toml` and read linked GitHub
   evidence. Run `orbi doctor --config /path/to/orbi.toml` for read-only diagnostics.
   If no deployment exists, report that fact and use the
   [cutover guide](../../docs/github-native.md); do not invent successful pickup.
3. For new work, use `/plan-for-me` or `/plan-with-me` and publish the complete issue
   batch. All issues default to `ai-ready`; planning publishes that label last.
   Native dependencies and Orbi's review/merge gates still apply.
4. A request to implement here routes explicitly to `/work`. Never start a parallel
   implementer for an Orbi-owned issue. Deployment changes require execution scope
   and verified legacy shutdown; an informational invocation changes no services.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "Orbi is absent, so start the old runner." | Report the missing deployment; no fallback executor. |
| "ai-ready proves it ran." | Labels are dispatch input, not implementation evidence. |

## Red Flags

- Starting a legacy service, task lease or cron loop.
- Claiming delivery without the PR, checks and review evidence.
- Requeueing owned or paused work to force progress.

## Boundaries

- Not planning; use `/plan-for-me` or `/plan-with-me`.
- Not manual implementation; use `/work`.
- Not a broad improvement campaign; use `/autonomous-codebase-improver`.
- Not architecture analysis; use `/improve-codebase-architecture`.
- Not a second queue. The [legacy store](../shared/TODO-WORKCENTER.md) is migration-only.

Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to delivery claims.

**Done when:** the requested GitHub/Orbi status or handoff is reported with observed
evidence and any exact missing deployment input, without reviving legacy execution.
