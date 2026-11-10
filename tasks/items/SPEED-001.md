+++
schema = 1
id = "SPEED-001"
title = "A coordinator-owned task returns to workers two hours after its record last changed"
short = "Coordinator claim expires"
status = "open"
section = "Now"
rank = 16000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/engine/parallel_plan.py", "pi-autowork/src/pi_autowork/task_snapshot.py", "pi-autowork/tests/engine/test_parallel_plan.py", "pi-autowork/tests/runner/test_task_snapshot.py", "pi-autowork/task-store.md", "pi-autowork/README.md", "skills/shared/TODO-WORKCENTER.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Six kit tasks and one task in another repository waited on 2026-11-10 because their record said ownership = \"coordinator\" and no coordinator session was running them. authorization_wait in pi-autowork/src/pi_autowork/engine/parallel_plan.py makes such a task wait forever with `awaiting coordinator action`. Make the claim end two hours after the commit time of the last commit that changed the task record: before that the task waits as today, after that admission treats it as a worker task and its waiting reason and the task snapshot say that the coordinator claim expired. The record is not rewritten. The rule applies to existing records. A planner or skill instruction that writes coordinator ownership states the two-hour rule."
acceptance = ["A regression with a committed coordinator-owned record whose last change is older than two hours proves parallel admission and the sequential fallback dispatch it as a worker task, and one changed less than two hours ago still waits with `awaiting coordinator action`.", "Owner-only tasks, live-authorization waits and typed owner gates are unchanged, and a body Ownership note still cannot override the typed value.", "The task snapshot and fleet rows show the expired claim as an ordinary ready worker task; pi-autowork/task-store.md, pi-autowork/README.md and skills/shared/TODO-WORKCENTER.md state the rule."]
checks = ["python3 scripts/check.py pi-autowork/tests/engine/test_parallel_plan.py pi-autowork/tests/runner/test_task_snapshot.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling rounds 1 and 2, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
