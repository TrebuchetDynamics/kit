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
When supporting implementation, contribute these criteria to its existing review lane.
A `Ship` verdict does not authorize delivery or replace required independent review.

## Finding routing and receipt

1. **Bind.** For each change-specific finding, verify the current PR URL and head SHA
   against the reviewed candidate, or identify the owning issue URL when no PR owns
   the change. Record the reviewed revision, severity, concrete regression evidence
   (source lines or reproducer), and required check with its expected result. Keep
   the existing live owner and review lane; do not take over their work.
2. **Reconcile.** Read the existing review/comments before any authorized post.
   Reuse the existing finding link for the same defect and evidence; unchanged
   evidence produces no duplicate post. A changed head requires rechecking affected
   evidence, not replaying an old finding against new code.
3. **Publish only within authority.** Post only to that existing PR or issue thread
   when review publication is already authorized. Read-only/no-write review never
   posts; all user restrictions still apply. If ownership is unknown, return the
   finding inline. If a required read fails, report the concrete error, missing
   input and safe resume action; hold publication rather than guess ownership or
   absence of a prior finding.
4. **Return.** The review receipt includes each finding and owner link (or explicit
   unknown ownership), reviewed head/revision, severity, evidence, required check,
   verdict and unverified areas. Distinguish posted, reused and inline-only findings;
   include the existing finding link when reused and the verified post link when
   published. A proposed check is not a passed check.

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
- Not implementation or backlog publication. Do not open a tracking issue or start
  repairs; return findings to the existing owner or inline when ownership is unknown.

**Done when:** the review receipt binds findings to their owner and reviewed revision,
with severity, evidence, required checks, publication disposition and a verdict;
unverified areas are named.
