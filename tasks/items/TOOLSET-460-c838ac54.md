+++
schema = 1
id = "TOOLSET-460-c838ac54"
title = "Give a second empty hold one bounded recovery without an owner edit"
short = "Recover a second empty hold"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 3000
depends_on = []
touches = ["Src/pi_autowork/engine/parallel_integrate.py", "Src/pi_autowork/engine/parallel_state.py", "Src/pi_autowork/engine/parallel_dispatch.py", "pi-autowork/engine/test_parallel_integrate.py", "pi-autowork/engine/test_parallel_dispatch.py", "pi-autowork/engine/test_hold_causes.py", "pi-autowork/README.md", "CHANGELOG.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "A held slot with `cause = empty` or `no_change` at attempt 2 has no recovery path: `retry_held` retries only attempt 1, `--parallel-clear-held` requires a held commit that does not exist, and the task is then parked forever and reported as Agent repair although no agent can repair it. Three tasks (TOOLSET-442, 452, 453) reached this state after the red-main period. Add one explicit, bounded recovery that does not bypass the second-failure budget: an operator or maintainer request requeues the task from the current main as a fresh attempt with the actor, the reason and the previous attempt's evidence recorded, at most once per task contract. If that attempt also ends empty, the task becomes a visible engineering hold with its evidence and no further automatic retry. A changed contract still runs fresh as today, and a held commit still uses the existing clear-held path."
acceptance = ["An attempt-2 empty or no_change hold with no commit is requeued once from the current main by an explicit supported request, recording actor, reason and the previous attempt evidence.", "A second empty failure after that requeue is parked and becomes a visible engineering hold; no automatic loop and no third attempt.", "A held commit still goes through the existing clear-held path; no commit, branch or worktree is discarded by the new recovery.", "Deterministic tests cover requeue once, refusal of a second requeue, unchanged behaviour for an attempt-1 empty hold, and unchanged behaviour for a held commit."]
checks = ["python3 scripts/check.py pi-autowork/engine/test_parallel_integrate.py pi-autowork/engine/test_parallel_dispatch.py pi-autowork/engine/test_parallel_state.py pi-autowork/engine/test_hold_causes.py", "python3 skills/docs-sync/scripts/docs.py check ."]
exclusions = ["No increase of the automatic attempt budget and no silent re-run loop: the recovery is explicit and once per contract.", "No bypass of validation, scope, closure evidence or ownership, and no owner question for a technical hold.", "No live service change is required or claimed by the offline checks."]
+++
- Sources: docs/research/authorized-autonomy-audit-2026-11-04.md#2-durable-effects-and-crash-recovery
