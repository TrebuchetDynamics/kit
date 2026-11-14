# Delivery-pipeline measurement requirements

The current objective, accepted constraints and measurement definitions are in
[the evaluation contract](../evaluation.md#thirty-day-evaluation).
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

## Interrupted disposable delivery qualification

The executor-specific interruption recipe is removed. Its
[original scenarios and outstanding proof](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/research/delivery-pipeline-2026-10-24.md#interrupted-disposable-delivery-qualification)
remain immutable requirements evidence. Do not install or run the old executor.

For a separately authorized successor pilot, preserve original candidate and
attempt identity, exact checks/review evidence and the real integrated revision
across failure/recovery. A saved completion or successful restart alone proves no
delivery. Never edit receipts or acceptance to make recovery pass. Use disposable
targets, protect credentials, preserve recovery state and keep missing billing or
owner-attention data unknown. Orbi remains paused until [cutover gates](../github-native.md)
are satisfied; no measurement document authorizes activation.
