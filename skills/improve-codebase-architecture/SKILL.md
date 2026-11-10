---
name: improve-codebase-architecture
description: "Expose architectural waste and drive verified fixes."
license: MIT
---

# Improve Codebase Architecture

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Read the pinned [architecture review reference](upstream/PROTOCOL.md) and its
[HTML report format](upstream/HTML-REPORT.md). They own the scan questions, the report
cards and the visual guidance. This adapter owns scope, evidence and fix-mode rules
where they differ from the upstream report-and-interview sequence.

## Vocabulary

Use these terms and no substitutes: **module**, **interface**, **depth**, **seam**,
**adapter**, **leverage**, **locality**. A shallow module's interface is nearly as
complex as its implementation; a deep one hides that complexity behind a small
interface. Test a suspected shallow module with the **deletion test**: would deleting it
concentrate complexity, or only move it? One adapter is a hypothetical seam, two make it
real. The interface is the test surface. Read the repository's domain glossary and ADRs
before naming anything; a decision an ADR records is not yours to re-open silently.

## Process

1. **Scope first.** Take the area the owner named. Otherwise follow recent history to
   the hot spots. Read the glossary and the ADRs for those areas. Default to review;
   `report only` or `read-only` rules out fixes. An explicit request to fix, patch or
   optimize authorizes the bounded fix branch in step 4, not a repository-wide rewrite.
2. **Map, then challenge.** Load `/graphify` before wide reading. Reuse a valid local
   graph to inspect hubs, cycles, callers and cross-module seams; follow that skill's
   build, freshness and fallback rules. The source scan is read-only: build no graph
   in review mode. Record the [declared graph
   state](../shared/COMMON-CONTRACT.md#graph-state), queries and coverage gaps. Missing
   Graphify means native search, not a blocked review or an invented graph result.
   Verify every graph lead in current source, including dynamic entrypoints and tests;
   hub size is not defect severity and missing edges do not prove dead code.

   Load the pinned [Ponytail protocol](../ponytail/upstream/skills/ponytail/PROTOCOL.md)
   for material choices under the shared scope/level rules. Challenge every shallow
   module: can it disappear, reuse an existing module or hide more complexity behind
   a smaller interface? Inspect duplicated rules, speculative adapters, leaking state,
   swallowed failures, repeated I/O, unbounded work and bad scaling at expected load.
   Trace callers and failure paths, not just file shape. Demand the deletion test and
   a concrete failing case or measurable cost for each actionable finding. Keep style
   preferences and unverified hypotheses separate; fewer lines alone prove nothing.

   For a large codebase, delegate one bounded read-only exploration in a fresh context
   window. State its scope, no-write limit and completion criterion: source-backed
   findings with callers, failing cases and proposed checks. Otherwise inspect directly.
3. **Report.** Write one self-contained HTML file into the OS temp directory, never into
   the repository: `<tmpdir>/architecture-review-<timestamp>.html`. Give each candidate
   files, problem, solution, benefits stated as locality and leverage, a before/after
   visual, and a `Strong`, `Worth exploring` or `Speculative` badge, then one top
   recommendation. Rank correctness, security and data-loss defects before measured
   performance costs, then structural waste. Keep severity separate from the confidence
   badge. Each actionable candidate also names source locations, affected callers,
   failure or cost evidence, smallest complete fix, compatibility risk and verification
   command. An unmeasured speed claim stays a hypothesis. Report the absolute path.
   Open it only when a display and opener exist; otherwise leave it for the owner.
4. **Choose the branch.** In review mode, propose no interfaces yet and ask which
   candidate to explore. In authorized fix mode, load [verified fixes](references/fixes.md)
   and continue with `/autowork` for one bounded candidate; do not ask again for scope
   already granted. Record other findings as pending, not silently expanded scope.
5. **Interview unresolved design choices only.** For a review candidate or a fix whose
   compatibility or ADR decision is not authorized, pause that candidate and ask the
   smallest blocking question. Otherwise skip the interview.  Use [Grilling](../grilling/SKILL.md) for
   constraints, dependencies, the deepened shape, what sits behind the seam and which
   tests survive. Record settled decisions per
   [Grill With Docs](../grill-with-docs/SKILL.md) when the owner wants them durable.

A review is advice, not authorization. Fixes use the caller's accepted scope through
[Autowork](../autowork/SKILL.md); commit, push and deployment authority stay separate.
Report CDN use in the report file, since the visuals load from the network when opened.
An explicit no-write request also rules out the HTML file: report inline instead.

**Receipt:** scope and why; files and areas inspected; candidates with badge and
deletion-test evidence; severity and confidence; graph state and source confirmations;
report path or inline-only reason; ADR conflicts; chosen candidate; Ponytail reuse and
omission decisions; actual changes and checks; remaining findings and unverified claims.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| The graph proves this module is unused. | Verify runtime discovery and callers through `/unused-code`. |
| A smaller diff must be faster. | Measure the named workload and preserve behavior. |
| Existing tests pass, so the bug is fixed. | Show a regression check fail before and pass after. |
| Harsh optimization means rewriting everything. | Remove evidenced waste within the accepted scope. |

## Red Flags

- Findings lack a failing case, cost evidence or source location.
- A fix drops validation, error handling or compatibility to shrink the code.
- Speed claims have no baseline, or unrelated dirty work enters the diff.
- A report or lean diff is presented as verified implementation.

## Boundaries

- Not a separate implementation engine; fix mode uses `/autowork` and the shared
  [Definition of Done](../shared/DEFINITION-OF-DONE.md).
- Not a general bug hunt or dead-code sweep; use `/bug-harvest` or `/unused-code`.
- Not multi-lane improvement; use `/autonomous-codebase-improver`.

**Done when:** the review report is delivered (inline for no-write requests), and either
review stops with a next choice or one authorized fix has a verified Autowork receipt;
blocked fixes and all remaining candidates are explicitly pending.
[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).