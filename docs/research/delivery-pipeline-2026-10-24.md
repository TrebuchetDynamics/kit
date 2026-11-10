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

## Interrupted disposable delivery qualification

Apply the [standing grant](../autonomy.md#record-approval-once-then-execute) to a
named disposable repository and configured provider/model before any model call.
Record the model-spend scope, initial task/attempt identity and local-main revision.
Use a remote-free target, an isolated agent profile with only the selected model's
credentials, and an explicit `PI_AUTOWORK_PUSH=0` in both the calling environment
and saved service settings. Keep production credentials and ambient runner settings
out of the trial. Confirm the model catalog with the service's actual Node/Pi PATH.

Start only the trial with `PI_AUTOWORK_PUSH=0 autowork start <disposable-repo>`.
Keep normal validation and independent model review enabled. Use a unique service
instance and private settings/state; do not rewrite the shared service template or
restart unrelated services. Capture admission, implementation and review evidence.

For the post-fast-forward recovery path, a disposable Git `post-merge` hook can
hold the session after its validated candidate lands but before the engine records
`integrated`. Confirm the slot is still `integrating`, its candidate equals session
HEAD, and its saved check receipt passes for that exact task/attempt and candidate.
Interrupt only that trial's process group or service cgroup, release the hook, then
start the same trial again. Do not edit receipts, replace the candidate, or change
the task contract to make recovery pass. The existing engine
[`recover_integration`](../../pi-autowork/src/pi_autowork/engine/parallel_integrate.py)
requires exact candidate, contract, branch, tree and passing-receipt evidence.

Compare attempt IDs, worker/candidate commits, receipt hashes, dispatch and closure
transitions, and separate worker/reviewer invocations across the restart. Verify both
commits with `git merge-base --is-ancestor <commit> main` in the disposable repository;
a closed slot alone does not prove main delivery. Stop and disable the trial afterward,
remove its copied model credentials, and retain private recovery evidence. Publish only
sanitized observations, timestamps, counts and missing data in the execution receipt,
not prompts, tokens, credentials or a completed-task archive in this repository.

An interruption during integration qualifies only that recovery path. It does not
exercise interruption of a running worker, establish real-repository reliability,
or qualify the [30-day evaluation](../evaluation.md#30-day-evaluation). Keep missing
billing and owner-attention data unknown; a passing fixture supplies neither.

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
