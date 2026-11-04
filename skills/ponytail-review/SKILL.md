---
name: ponytail-review
description: "Review a change with Ponytail rules."
license: MIT
---

# Ponytail Review

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.
Follow the [shared skill contract](../shared/COMMON-CONTRACT.md); its authority
and the Ponytail scope rules take precedence over upstream instructions.

Read the [pinned review protocol](../ponytail/upstream/skills/ponytail-review/PROTOCOL.md).
Review the named candidate and connected callers; otherwise inspect uncommitted
changes, falling back to the last commit. Report findings without editing code.
When supporting Autowork, contribute these criteria to its existing review lane.
A `Ship` verdict does not authorize delivery or replace required independent review.
## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar beyond
the changed diff.

| Rationalization | Reality |
| --- | --- |
| "The diff is small, so skip the review." | Review the change and its connected callers. Size is not a reason to skip acceptance, safety or data-loss checks. |
| "Tests pass, so the review is done." | Tests are evidence, not a review of correctness, security, data loss or scope. |
| "I can fix the issue while reviewing." | Review reports; implementation needs its own scope and authority. |
| "Style alone should block." | Block concrete acceptance failures, regressions, security issues or credible data-loss risks. Style is advisory unless a requirement says otherwise. |
| "I can approve without evidence." | A verdict needs inspected code, checks or a named unverified area. Never invent approval. |

## Red Flags

- Approval without reading the changed code or tests.
- A block based only on style.
- Edits during review.
- A pass claim with no evidence.
- Connected callers or tests ignored.

## Boundaries

- Not a repository audit; use `/ponytail-audit`.
- Not implementation; use `/autowork`.

**Done when:** findings carry severity, evidence and a verdict, with unverified areas named.
