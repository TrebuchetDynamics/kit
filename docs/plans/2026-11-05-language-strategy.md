# Language strategy and measurement boundaries

GitHub Issues own executable work; Orbi is the paused, live-unqualified delivery owner.
See the [current support boundary](../github-native.md#support-boundary).
Completed sampling results and task timelines remain in Git history.

## Decision

Do not keep or restore execution authority with a retired runtime. Preserve legacy
records and reconcile any still-required outcome into GitHub Issues, without
starting a Go/Rust prototype or enabling Orbi. The independent language-measurement
goal remains unmet; removal, a replacement choice or deleted measurement reports
are not evidence that the earlier measurement gate passed.

## Decision gate for a Go supervisor prototype

The earlier gate is preserved for any expressly authorized reconsideration. At
least one complete, source-bound condition is required:

- Median coordinator RSS is at least 25% of its live descendants' RSS or at least
  1 GiB, over at least three samples at least 60 seconds apart while cycling.
  Exclude the coordinator from descendant RSS; evaluate no share with zero live
  descendants.
- Dispatch p95 exceeds five minutes while at least one worker slot is idle.
  Capacity and latency must refer to the same task/time cohort.
- More than one coordinator-attributable restart, OOM kill or resource-gate pause
  occurs within seven days per repository. Log lines are not distinct incidents;
  host load, requested reloads and shutdown failures require causal attribution.
- An actual target host is blocked by Python provisioning, supported by an owner
  report or failed target-host attempt, not a hypothetical packaging preference.

Missing evidence is not measured, not zero and not a met threshold. A single sample
is not a benchmark. Passing a gate would justify only bounded operational prototyping
under its own authority, never canonical write ownership or a full Go rewrite.
The Rust executor redesign is superseded; these thresholds authorize no new work.

## Measurement round 1

This stable anchor now names the unresolved evidence requirement, not an archived
sampling report. No complete threshold was established; do not infer a met gate
from a historical p95 combined with present spare capacity or from an owner approval.

Required next input is contemporaneous task-aligned capacity/status evidence,
independent proof of complete historical slot projection with status corroboration,
coordinator-attributable incidents, or a concrete blocked target-host attempt.
A slot write precedes best-effort journal emission: parseable journal records alone
cannot prove complete transition coverage. Missing PID samples are not by themselves
a proof that a complete upper-bound projection is invalid; completeness must first
be established. A hot-file wait does not prove language overhead.

## Evidence continuation: LANG-004

This compatibility anchor retains the outstanding requirement for existing links.
It stores no completed inspection report. The missing-evidence stop remains open;
keep `LANGUAGE-STRATEGY` unmet. Another approval does not provide the missing inputs.
Reconsider only with concrete complete evidence and current ownership. No sampler,
benchmark service, restart, worker launch or prototype is authorized by this page.

## Sources

Current authority is documented in [GitHub-native delivery](../github-native.md)
and the [component map](../project.md#current-components). No historical result
is a new execution receipt or proof of replacement qualification.
