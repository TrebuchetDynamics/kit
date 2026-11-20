# 0001 — Use lightweight behavior specs without requiring OpenSpec

**Status:** Accepted design; skill changes are not yet verified or delivered.

For a user-visible behavior change, describe what is added, modified, removed, or renamed. Contrast the proposed behavior with the current contract and give an observable WHEN/THEN example. Do not invent a requirement for a refactor that leaves behavior unchanged.

`/grill-with-docs` uses the example to resolve ambiguity before recording a durable decision. `/plan-with-me` and `/plan-for-me` put accepted scenarios in GitHub issue acceptance criteria. When a project already uses native OpenSpec, or explicitly opts in, link to its exact spec rather than copying it into a parallel document. `/docs-sync` checks merged code and tests before describing a proposed behavior as current.

Example of a proposed behavior, not an instruction to run it: WHEN an operator requests `/orbi update --dry-run` while a worker is active, THEN show which worker the update would interrupt and leave it running. Accepting that scenario does not authorize a live update.

We chose this over requiring OpenSpec initialization, its CLI, and a second task list in every project. Scenarios make disagreements observable without changing who owns execution: GitHub Issues remain the backlog and Orbi owns delivery. This requires no extra model call per artifact.

References: [OpenSpec’s spec-driven schema](https://github.com/Fission-AI/OpenSpec/blob/0c737dc1b543249b38b0f4716816fcf493d894dd/schemas/spec-driven/schema.yaml), [Kit planning contract](../../skills/shared/RESEARCH-PLAN.md), and [GitHub delivery contract](../github-native.md).
