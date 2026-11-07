# Delivery-pipeline measurement requirements

The current objective, accepted constraints and measurement definitions are in
[the evaluation contract](../evaluation.md#delivery-pipeline-optimization).
Completed source audits, numeric baselines and task reconciliation reports belong
in Git history. This document supplies no fresh performance or live acceptance claim.

## Evidence boundaries

Measure verified deliveries per observed runner-hour, with regressions and human
intervention as counter-metrics. Integration, task closure and actual main delivery
are different endpoints. Attempt-hours are not runner uptime. Missing delivery,
uptime, billing or owner-time data stays unknown rather than becoming zero.

Publish observed sample counts, coverage, censoring and phase median/p95 beside the
conservative full-cohort metrics. Distinguish eligible review-tail time from total
wait time; current spare capacity cannot prove capacity at historical dispatch.
Comparable quality and check coverage are required for performance claims.

## Implementation constraints

Retain existing runtime, scorecard, maintainer and integration ownership; add no
second scheduler or evidence registry merely to optimize a metric. Unknown test
attribution is not an automatic culprit or permission to revert an entire cohort.
Serial eligible-prefix consumption must preserve integration/review authority.
Technical maintainer retries must remain bounded and fenced against uncertain
acceptance and duplicate effects; semantic-result deduplication remains separate.
Shared files alone are not logical prerequisites. Executable check handoffs must
run the selected checks; selection output alone does not prove validation.

Use current source and fresh actual ownership for future changes, not a dated audit's
worker snapshot. Preserve accepted contracts, stopped jobs, original recoveries,
owner-only live tasks and independent review. Read-only metrics and offline fixtures
do not qualify model execution, installation, delivery or automatic steering.

The unqualified 30-day real-repository run remains paused pending its actual inputs
and live authority. Any installed RPC pilot also requires the separate
[pilot authorization and acceptance](pi-rpc-installed-pilot-plan-2026-10-24.md).
No restart, dispatch, configuration change, model spend or publication follows from
these requirements. Raw runtime identities, secrets and session histories stay outside Git.
