---
name: impeccable
description: "Design, audit or polish frontend UI."
version: 4.8.0
license: Apache 2.0
---

# Impeccable

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.
Read the [upstream Impeccable protocol](PROTOCOL.md) for the selected playbook.
The local modes below take precedence over its menu and edit defaults. Its skill
base directory remains this directory. Preserve the requested visual quality,
accessibility and accepted behavior; simplicity does not mean generic design.

## Modes

- **Default findings.** A bare invocation, audit or critique uses the shared
  [UI findings handoff](../shared/UI-FINDINGS.md): analyze and publish eligible
  outcomes, then stop. Do not show the upstream no-argument command menu.
- **Requested work.** An explicit design/edit request or named build/refine command
  follows its playbook and existing ownership, review and delivery gates. Preserve
  the requested scope instead of substituting issue publication. Setup, hooks,
  doctor and pin tooling retain their explicit command behavior.
- **Restricted work.** Report-only/read-only/dry-run/no-write means inline findings
  with no writes. Scheduled, cron or unattended runs audit only unless their accepted
  task scope explicitly authorizes the requested writes. The shared handoff keeps
  no-dispatch and live-owner restrictions.
## Boundaries

- Not README art; use `/beautify-github-readme`.
- Not the UI Taste playbooks; use `/ui-taste`.

**Done when:** default findings have verified issue links or covered, held or
unsaved dispositions (or no warranted changes); no-write findings are inline with
nothing saved; explicit work has the chosen playbook's artifacts and checks.
