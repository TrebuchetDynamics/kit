---
name: orbi
description: "Prepare, update, start, inspect or stop one Orbi deployment."
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
this adapter. Keep any host-required tool-result continuation to the workflow's
receipt relay; it is not another routing or planning pass.

Forward `version [--repo-dir PATH] [--config PATH] [--json]` unchanged to the
canonical helper in one read-only invocation on Linux/macOS, without pre-status
or bootstrap probes. It identifies the selected deployment, not the global CLI.

## Boundaries

Explicit invocation only. This adapter grants no deployment authority and does not
release pauses or live gates. Use the existing planners for GitHub issue publication and
`/unblock` for recovery rather than lifecycle control. `update` advances one stopped
deployment's engine release; explicit `update --stop` authorizes pausing owned timers,
not interrupting workers or restarting scheduling. Draining returns an exact resume
command; unit refresh waits for the next authorized start. It never refreshes Kit,
which stays `/update-kit`.

**Done when:** the loaded workflow's completion condition is met and only observed
results are reported.
