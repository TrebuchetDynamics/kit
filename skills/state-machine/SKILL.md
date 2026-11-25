---
name: state-machine
description: "Map unsafe transitions and publish warranted issues."
license: MIT
---

# State Machine

Use the [single-invocation specialist handoff](../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
for the default route. It owns reconciliation, preview, issue publication and receipts.

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.
Follow the [shared skill contract](../shared/COMMON-CONTRACT.md).

## Process

1. **Scope and mode.** Map the named application or area. With no area supplied,
   inspect the current repository. An ordinary invocation analyzes and publishes
   through the default handoff above. Explicit `report only`, `read-only`, `no-write`
   or `dry-run` means return findings inline and write nothing. Existing tests may
   run only when their effects fit the caller's limits; a strict no-write request
   also excludes tests that write caches or fixtures.
2. **Map and verify.** Read and apply the [state-machine analysis](PROTOCOL.md).
   Each actionable finding needs the trigger, initial and resulting state, violated
   invariant, source location at the inspected revision and a regression sequence
   with an independently supported expected result. Distinguish reproduced defects,
   source-supported unexecuted counterexamples and hypotheses. Hold undecided product
   rules with their reason and missing input; do not invent expected behavior.
   For definitions, online sources or a worked counterexample, read
   [references](references/sources-and-example.md).
3. **Route and stop.** Use the default handoff above to reconcile and publish warranted
   outcomes, then report verified issue links and held/covered dispositions. Keep the
   inventory, transition maps, protected paths, coverage gaps and actual checks in
   the inline report, not a new report file. Default publication does not implement
   findings locally. In no-write mode, deliver the analysis inline and stop.
   In explicitly requested and authorized fix/apply mode, use
   [`/bug-harvest`](../bug-harvest/SKILL.md#findings-from-the-preceding-response)
   in this invocation: reuse the map and findings as its bounded repair scope,
   not a fresh hunt or automatic publication batch. Preserve caller limits and
   ownership, review, PR and human-only gates; report remaining findings as pending.

Other skills use the analysis method by reading `PROTOCOL.md` directly. They keep
their own scope, mode and output format and reuse a current map rather than start
another repository audit.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| A suspicious state must be a bug. | Show a reachable sequence and an invariant grounded in accepted requirements. |
| One product rule is undecided, so publication must wait. | Hold that finding with its missing input and continue independent qualifying work. |

## Red Flags

- An issue assumes a product rule or lacks a transition regression sequence.
- The default route asks the user to select finding numbers or run a planner.
- Publication is presented as a local repair or live safety proof.

## Boundaries

- Not a default repair campaign; use `/bug-harvest` only for explicitly authorized
  local fixes. Publication does not activate Orbi.
- Not a requirement decision; use `/plan-with-me` for an unresolved product rule.
- Not a framework migration or proof that all possible executions are safe.
  Use `/improve-codebase-architecture` for a broader structural review.

**Done when:** each in-scope finding has a verified issue link or a covered, held or
unsaved disposition (or no change is warranted), with the map, checks and unresolved
frontier reported; explicit no-write returns inline findings without writes;
authorized fixes have their own verified receipt under the shared
[Definition of Done](../shared/DEFINITION-OF-DONE.md). Offline contract checks do not
verify live model or Orbi behavior.
