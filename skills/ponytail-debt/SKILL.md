---
name: ponytail-debt
description: "Publish issues for triggered shortcut debt."
license: MIT
---

# Ponytail Debt

Use the [single-invocation specialist handoff](../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
for reconciliation, grouping, preview, publication, native dependencies and receipts.
A bare invocation analyzes and publishes eligible outcomes within the requested scope,
without selection, confirmation or a second command. Stop after publication.

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.
Follow the [shared skill contract](../shared/COMMON-CONTRACT.md); its authority
and this workflow take precedence over upstream report-only/persistence instructions.
Explicit report-only or read-only/dry-run/no-write requests return findings inline
without any writes, including scratch files. Preserve no-dispatch, pauses and live
ownership through the shared handoff. Publication does not authorize implementation
or service activation.

## Process

1. **Scan.** Read the [pinned debt protocol](../ponytail/upstream/skills/ponytail-debt/PROTOCOL.md)
   for marker discovery and ledger rows, not its report-only completion rule.
   Use the host's repository search or its documented Git scan in the requested
   repository. Git exit 1 means no matches, not a failed scan. Report other errors
   with the concrete error and safe resume action; incomplete scans are not empty ledgers.
   Treat custom markers as literal data (escape regex metacharacters and pass an
   argument, never interpolate shell code). Inspect hits before counting them.
   Include `shortcut:` and legacy `ponytail:` deferrals, not keyboard-shortcut prose.
   Keep the existing ledger as context; do not create a competing debt backlog or
   rewrite legacy records. Each row keeps marker location and text, ceiling, stated revisit trigger,
   upgrade path and owner when known. Blame is optional and requires tracked history.

   The default scan covers `#`, `//` and `/*` comments and respects ignore rules;
   it can miss other comment styles and tracked-but-ignored files. Disclose relevant
   limits. No-marker output is evidence only for the scanned scope.
2. **Check triggers.** Compare each marker's stated revisit trigger with current
   source, supported configuration or measured evidence. Record the evidence and
   revision, not just the comment's existence. A reached trigger with an unmet
   remedy must establish a breached assumption, bounded remedy and verification check
   before it can become an issue. Do not file markers simply because they exist.

   - Documented ceiling of 100 entries; supported configuration now permits 200:
     if the marker says to revisit above 100 and the remedy remains uncovered,
     publish one issue with the marker, breached assumption, bounded remedy and check.
   - Supported configuration still permits only 100 entries: trigger unreached, no issue.
   - Marker has no stated revisit trigger: tag `no-trigger`, no issue. Name the
     missing trigger rather than inventing a threshold or filing marker cleanup.
   - Missing or conflicting evidence: hold that finding with the exact missing input
     and resume condition; continue independent eligible findings.
3. **Reconcile and publish.** Use the shared handoff to check source, open and closed
   issues, linked PRs and actual ownership before choosing new work. Completed,
   covered or owned remedies need no duplicate issue. Group markers sharing one fix
   and acceptance check. Each complete issue carries its marker evidence, breached
   assumption, bounded remedy and check alongside the shared issue fields. Preview
   the batch without waiting, verify the full batch and native dependencies, then
   apply `ai-ready` last under that contract. Explicit no-dispatch keeps work held.
   Use its failure/partial receipts if publication fails; never replace GitHub with
   a local queue. Report verified issue links and covered, unreached, `no-trigger`,
   held or unsaved dispositions. Zero eligible outcomes means zero new issues.

## Boundaries

- Not a fix or service control; publication stops before implementation.
- Not a repository-wide audit; use `/ponytail-audit` for the repository view.

**Done when:** every scoped marker has an evidenced disposition and eligible work
has verified issue links, or the receipt names held/unsaved/unknown outcomes and
resume actions; explicit no-write returns inline findings with nothing saved or dispatched.
