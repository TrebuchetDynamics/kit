---
name: state-machine
description: "Map implicit state machines and unsafe transitions."
license: MIT
---

# State Machine

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.
Follow the [shared skill contract](../shared/COMMON-CONTRACT.md).

Map the named application or area. With no area supplied, inspect the current
repository. Default to a read-only analysis delivered inline, including no report
files or task edits. Existing tests may run only when their effects fit the caller's
limits; a strict no-write request also excludes tests that write caches or fixtures.

Read and apply the [state-machine analysis](PROTOCOL.md). It is also the shared
method for other skills: they read that file directly, keep their own scope and
output format, and reuse a current map rather than start another repository audit.
For definitions, online sources or a worked counterexample, read
[references](references/sources-and-example.md).

## Execute the findings

To request fixes, invoke `/bug-harvest` immediately after the analysis in the same
conversation, with no extra prompt. Its [contextual handoff](../bug-harvest/SKILL.md#findings-from-the-preceding-response)
uses the preceding findings as the repair scope and verifies candidates before fixing
them. This analysis itself remains read-only; it starts no repair workflow.

## Boundaries

- Not a repair campaign; use `/bug-harvest` for a verified defect or `/autowork`
  for an accepted implementation task. Carry existing authorization into that
  workflow without adding a permission round.
- Not a requirement decision; use `/plan-with-me` for an unresolved product rule.
- Not a framework migration or proof that all possible executions are safe.
  Use `/improve-codebase-architecture` for a broader structural review.

**Done when:** the scoped inventory, transition maps, evidence-ranked findings and
coverage gaps are delivered with actual checks and the next unresolved frontier.
