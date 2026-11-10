+++
schema = 1
id = "TOOLSET-497"
title = "Keep typed coordinator-owned tasks out of automatic worker admission"
short = "Respect coordinator task ownership"
status = "done"
section = "Now"
rank = 15000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/engine/task_queue.py", "pi-autowork/src/pi_autowork/engine/parallel_plan.py", "pi-autowork/tests/engine/test_parallel_plan.py"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Carry typed coordinator ownership through the existing task-queue admission view and refuse future automatic worker admission with the current 'awaiting coordinator action' meaning, without an owner/live authorization question. Cover parallel planning and sequential fallback through the same admission helper. Preserve pure committed-store selection order, legacy imported worker tasks, typed owner/live gates, and existing running attempts. Do not use body notes as authority or alter a live contract. Implement locally in an isolated checkout; retain this new record uncommitted on canonical main until offline closure so the known-unfixed runner cannot dispatch a competing attempt."
acceptance = ["A regression using committed typed ownership=coordinator proves its admission view retains the ownership, both ordinary parallel admission and sequential fallback wait instead of launching it, and an independent worker task stays eligible. A body Ownership note cannot override the typed value.", "Coordinator ownership stays coordinator-only even with a structured live grant; its waiting reason is awaiting coordinator action, without a fabricated human-only grant question. Existing owner-only/live authorization, ordinary worker scheduling and task snapshot presentation tests pass.", "No existing slot, lease, task contract, live grant, service, runtime state or selection rank is changed. The fix is future admission only; offline evidence does not claim installed/live qualification."]
checks = ["python3 scripts/check.py pi-autowork/tests/engine/test_parallel_plan.py pi-autowork/tests/runner/test_task_snapshot.py", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No retroactive interruption, set-aside, manual closure or ownership edit of a running task. No service operations, grant changes, permission bypass or implementation of another backlog task."]
closure = "manual"
closure_actor = "current-debug-coordinator"
closure_timestamp = "2026-11-10T08:20:18.795236+00:00"
closure_reason = "Offline typed-coordinator admission defect repaired and independently reviewed. Reproduced dropped Ownership, then 60 planning/snapshot/migration tests, tree guard, strict mypy, docs and whitespace passed. Existing attempts were not altered; no installed or live acceptance is claimed."
closure_evidence = "commit 97533de0ffb85c298561f5111f905b51d50feb83; /tmp/kit-coordinator-admission-final.log"
+++
- Sources: User-authorized recurring debugging; skills/shared/TODO-WORKCENTER.md record ownership; task_store.Task.runnable; task_queue.fields; parallel_plan.authorization_wait; current TOOLSET-496 admission evidence.
- Evidence: TOOLSET-496 was actually dispatched from e2d11033 despite typed coordinator ownership. task_queue.fields clears note authority labels correctly but only emits typed Ownership for OWNER, losing COORDINATOR. Downstream authorization_wait therefore sees an ordinary worker. Task.runnable and task_snapshot already distinguish coordinator work; pure selection intentionally does not enforce admission.
- Planner call: Add Coordinator only to the existing admission field bridge and a coordinator-specific wait in the existing shared admission helper, with no synthetic outside dependency or owner question. Preserve legacy Toolset coordinator prose fixture behavior because its imported typed value remains worker.
- First action: Add the typed committed-record regression, observe the missing Ownership field failure, then implement and run the two focused test modules and independent review.
- Ownership: This debug session owns .worktrees/fix-coordinator-task-admission. Current live TOOLSET-496 and other worker checkouts remain untouched.
- Skill application: concrete admission boundary violation; skills/engineering/upstream/skills/debugging-and-error-recovery/PROTOCOL.md@1be8e34187e34647bb83adc3a1323b26ae6f6abe; traced typed-field loss before admission; tests initially unrun.