---
name: ponytail-audit
description: "Audit code and publish actionable GitHub issues."
license: MIT
---

# Ponytail Audit

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.
Follow the [shared skill contract](../shared/COMMON-CONTRACT.md); its authority
and the Ponytail scope rules take precedence over upstream instructions.

Use the [single-invocation specialist handoff](../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
for the default route. An ordinary `/ponytail-audit` invocation analyzes the requested
scope and publishes warranted GitHub issues without selection, confirmation or a planner invocation.

## Process

1. **Select scope and mode.** Audit the named area; with no area, use the current
   repository. Preserve the requested level and boundaries. Explicit report-only,
   read-only, no-write or dry-run means no writes. Return findings inline without
   GitHub, label, document or scratch writes. Keep an explicitly requested and
   authorized local fix/apply mode separate from default publication, under the
   accepted scope and existing ownership, review, PR and human-only gates.
2. **Map and verify.** Read the [pinned audit protocol](../ponytail/upstream/skills/ponytail-audit/PROTOCOL.md)
   for audit questions and ranking. Trace relevant entry points, callers, tests and
   failure paths. State expected load, unread areas and checks not performed. For
   each finding, translate severity, source/reproducer evidence, expected load where
   relevant and next action into an observable check with its expected result.
   Name the smallest compatible fix and bounded implementation scope. A badge,
   unread area or preference alone is not actionable. Do not apply the upstream
   report-only route or 20-finding cap to publication.
3. **Reconcile and qualify.** Check current source, open and closed issues, linked
   PRs and actual ownership through the handoff: covered, completed, owned and
   unsupported findings create no duplicate issue. Publish all supported, buildable,
   uncovered outcomes within the requested scope. Group findings that share a fix
   and acceptance check. Hold only uncertain findings with the reason and resume
   condition; continue independent qualifying work. Zero qualifying findings means
   zero new issues: explain what is covered, held or healthy.
4. **Route and stop.** For default publication, preview in chat without waiting,
   then follow Plan Handoff with native `blockedBy` dependencies and `ai-ready` last;
   report verified issue links and stop. Preserve explicit no-dispatch, pauses and
   live ownership. Default publication does not implement findings locally or
   activate services. In no-write mode, return the ranked findings inline and stop.
   In authorized fix/apply mode, implement only the accepted bounded repairs and
   report actual changes, checks and remaining findings, not automatic issue publication.

If a required read fails, report the concrete error, missing input and safe resume
action. Failed reads mean unknown coverage, not an empty backlog; hold dependent
publication rather than invent absence or ownership. On publication failure, use
Plan Handoff's UNSAVED/UNKNOWN and partial receipts with stable-key reconciliation,
not a substitute queue or blind write retry.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| The report has numbered findings, so the user must choose. | Publish every qualifying outcome in scope through the default handoff. |
| An unread area warrants a test issue. | Establish concrete risk and an observable check first. |

## Red Flags

- A badge or preference replaces failure evidence and a check.
- One uncertain finding stops independent supported work.
- Issue readiness is described as implementation or live qualification; keep the [Definition of Done](../shared/DEFINITION-OF-DONE.md) distinct.

## Boundaries

- Not a change review; use `/ponytail-review`.
- Not a marker list; use `/ponytail-debt`.
- Not a publisher, scheduler or service activation mechanism; reuse Plan Handoff.

**Done when:** every in-scope finding has a verified issue link or a covered, held,
unsupported or unsaved disposition, or no change is warranted; explicit no-write
returns inline findings without writes; authorized fix/apply has a scoped verification receipt.
