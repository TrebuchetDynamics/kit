# Assessment and delivery evaluation

Sustained live reliability remains unproven. The earlier
[Autowork assessment and evaluation requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/evaluation.md)
are immutable evidence, not a supported executor runbook. The executor, task CLI,
TUI and Paseo plugin are removed. Existing task data, attempts, worktrees and
recovery evidence remain intact; removal does not satisfy their unresolved proof.

## Current qualification

Orbi remains paused and live-unqualified. Complete the single-repository
[cutover pilot](github-native.md#cutover) before any fleet expansion. Establish
actual issue pickup, implementation, PR creation, independent review, required CI,
merge and failed-run recovery without duplicate work or lost candidates.
Preserve explicit pauses, sensitive-change controls and human-only acceptance.
Review the [safety requirements](../README.md#safety-before-installing) before any
live evaluation; keep production credentials away from unattended agents.

## Thirty-day evaluation

After a separately authorized, successful pilot, measure real repository outcomes:

- Work completed without intervention and regressions per accepted change.
- Owner attention and cost per verified outcome, not per generated task.
- Time from issue readiness to merged, reviewed delivery.
- Recovery after failure/interruption without lost work or duplicate execution.
- Scope/acceptance adherence, documentation correctness and remaining live proof.
- Aggregate resource budgets across deployments, not per-worker throughput alone.

Use GitHub issue/PR history, checks, review and actual Orbi diagnostics. Keep
private operational inputs outside Git; report missing data rather than inventing
metrics. Historical executor results cannot qualify a new delivery implementation.
Offline fixtures and registration checks prove neither model behavior nor live
messaging or device acceptance. Do not create completed-task archives or run
legacy services to fill evaluation gaps.
