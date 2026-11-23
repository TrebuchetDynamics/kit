---
name: bug-harvest
description: "Verify defects and publish warranted GitHub issues."
license: MIT
---

# Bug Harvest

Use the [single-invocation specialist handoff](../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
for the default route. An invocation without a publication directive analyzes the
requested scope and publishes warranted issues in the same invocation.

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Apply the [host and authority adaptations](../shared/PI-TOOLSET.md) before reading the pinned
[bug-harvest protocol](upstream/PROTOCOL.md). This workflow's modes take precedence over the upstream fix/campaign loop.
Default publication does not patch locally. Only an explicitly requested and authorized local fix/apply mode
uses [Authorized local fixes](#authorized-local-fixes). Explicit `report only`,
`read-only`, `no-write` or `dry-run` means report inline and write nothing,
including scratch repro files. Preserve explicit no-dispatch, pause, ownership,
live-action and human-only limits in every mode.

## Findings from the preceding response

When invoked without arguments after an analysis such as `/state-machine`, use
that response's findings as the bounded publication scope, not local repairs.
No extra prompt, report file or repeated analysis is required. Reuse the state map and evidence
instead of starting a fresh repository hunt. Recheck the findings against current source and ownership;
a polished report is not proof of a bug. Hypotheses remain leads until verified.
A prior skill's read-only default does not make this invocation read-only, but
explicit continuing user no-write and delivery limits remain binding.

## Workflow

1. **Bound the search.** Inspect current source, instructions, issues, linked PRs
   and actual ownership; quarantine unrelated dirty files. Use the requested area
   or preceding findings and explicit stop limits. Without either, bound discovery
   to the current repository. Use a bounded executable check to find evidence,
   not code smells or endless TODO searching. Keep at most three discovery leads
   and investigate one candidate at a time. This is a discovery frontier, not a cap on an explicit batch
   or on supported outcomes within scope. Continue through the requested findings
   within caller limits; do not expand into unrelated discovery.

   Before wide reading, rank leads with a local code graph when one exists, record
   its [declared graph state](../shared/COMMON-CONTRACT.md#graph-state), and confirm
   every graph lead in live source. For a lifecycle or event-ordering lead, apply
   the [state-machine analysis](../state-machine/PROTOCOL.md) before choosing the repro.
2. **Verify each defect.** Record source locations, a bounded reproducer with setup
   and current failure evidence, observed behavior, expected behavior and its governing
   contract, concrete impact and trigger, and a discriminating regression check
   with the expected post-fix signal. Identify the smallest compatible correction
   and likely files so the outcome is buildable. For a supplied known repro, use
   the debugging method directly, not a fresh campaign or an implicit local fix.
   Separate confirmed failures from hypotheses and pre-existing check failures.
   Use only checks permitted by the current mode; missing safe reproduction stays
   uncertain, not an invented passing or failing result.
3. **Reconcile and close.** Use the shared handoff to check existing open and closed
   issues, linked PRs, completed work and live owners. Already-fixed, covered, owned
   and unsupported findings create no new issue. Hold unresolved product rules or
   missing evidence with the exact reason, required input and resume condition;
   continue independent qualifying findings rather than asking the user to select
   finding numbers or starting another planner. Group findings that share one fix
   and acceptance check. Account for the whole in-scope batch, not just the top bug.
4. **Publish and stop.** Follow the shared handoff for all supported, buildable,
   uncovered outcomes: preview in chat without waiting, publish complete issues with
   native dependencies and `ai-ready` last, then report verified links and stop.
   Zero qualifying findings means zero new issues. Explicit no-dispatch keeps work
   held without readiness. In no-write mode, return findings inline without any writes.
   Use the shared publication receipt and failure recovery, including per-issue
   partial/unknown writes; do not create a substitute queue or activate Orbi.

**Receipt:** scope and search limits; source-bound evidence, reproducer,
observed/expected behavior, impact and regression check per defect; new, covered,
completed, owned, unsupported and held dispositions; shared publication receipt
or inline-only result; actual checks, unrun/live gates, stop reason and next action.
Never claim no bugs exist; report what was searched.

## Authorized local fixes

Use this branch only for explicitly requested and authorized local repairs, not
for a bare invocation or the default publication route. Keep the accepted scope
and shared ownership, review, PR and human-only gates. Recheck ownership before editing.
Confirm the failure, identify its root cause, make the smallest safe fix, add
discriminating regression protection, rerun the repro and affected checks, and
satisfy required review. Separate pre-existing failures from introduced regressions.
Record severity with its concrete impact and trigger.

Continue one candidate at a time only within the authorized campaign and remaining
limits. A named next candidate is not permission to exceed a one-bug/slice limit.
A bounded rescan finding no candidate, user stop, exhausted budget, unsafe ownership
or missing required capability ends or pauses the hunt. Record other findings as
pending, not automatically published work. No automatic commit or push.

**Fix receipt:** task/bug, severity and why, repro before → after, changed paths,
regression checks, review state, search after the last fix (or NOT_RUN because a
limit was reached), stop reason and resumable next action.

## Boundaries

- Not default local implementation; authorized fix/apply retains the shared
  [Definition of Done](../shared/DEFINITION-OF-DONE.md) and delivery gates.
- Not dead-code removal; use `/unused-code`.
- Not test reduction; use `/test-optimizer`.

**Done when:** every in-scope finding has verified issue links or an evidenced
covered, completed, owned, unsupported, held or unsaved disposition, or the bounded
search warrants no issues; no-write returns inline findings without writes;
authorized fixes have verified receipts with remaining work explicitly pending.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).
