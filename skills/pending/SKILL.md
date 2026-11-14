---
name: pending
description: "Report open, done and next tasks."
license: MIT
metadata:
  hermes:
    tags: [tasks, pending, done, query, read-only]
---

# Pending

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../shared/COMMUNICATION.md) for user-facing text.

Follow the [shared contract](../shared/COMMON-CONTRACT.md) and
[GitHub issue contract](../shared/PLAN-HANDOFF.md).

1. Resolve the repository. Read open GitHub Issues and linked PRs, including labels,
   priority, native `blockedBy` relationships and epic membership. Paginate the full
   requested scope; do not confuse a client limit with the complete backlog.
2. Report ready work, dependent waiting work, proposals/explicit pauses and actual
   Orbi-owned delivery separately. `ai-ready` is the default, not proof of pickup.
   Use `orbi status --config /path/to/orbi.toml` and `orbi doctor` when available;
   distinguish diagnostics from successful model execution.
3. For completion, read closed issues, merged PRs, checks and independent reviews
   in the requested interval. Closed alone does not prove implementation. Preserve
   legacy IDs as provenance; inspect immutable legacy history only when relevant.
4. Report issue/PR URLs, next eligible work, exact blockers and coverage limits.
   If GitHub or the deployment is unavailable, say what was not assessed.

## Boundaries

- Read-only: no labels, issues, local records, services or repair writes.
- Use `/docs-sync` for supported document/issue reconciliation.
- Use `/plan-with-me` for missing intent and `/work` for explicit manual delivery.

**Done when:** open, next and completed work reflect inspected GitHub evidence and
the report states its interval, coverage and unassessed runtime state.
