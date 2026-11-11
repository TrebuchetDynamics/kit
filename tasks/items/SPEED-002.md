+++
schema = 1
id = "SPEED-002"
title = "A task the owner deferred leaves the attention count and the health line"
short = "Deferred owner tasks stay quiet"
status = "done"
section = "Now"
rank = 17000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/task_snapshot.py", "pi-autowork/src/pi_autowork/questions.py", "pi-autowork/src/pi_autowork/health.py", "pi-autowork/src/pi_autowork/fleet_view.py", "pi-autowork/src/pi_autowork/scorecard.py", "pi-autowork/tests/runner/", "pi-autowork/README.md", "pi-autowork/src/pi_autowork/engine/task_queue.py", "pi-autowork/tests/engine/test_task_queue.py", "pi-autowork/src/pi_autowork/engine/parallel_status.py", "pi-autowork/tests/engine/test_parallel_status.py", "pi-autowork/src/pi_autowork/engine/task_select.py", "pi-autowork/tests/engine/test_task_select.py", "pi-autowork/src/pi_autowork/engine/parallel_plan.py", "pi-autowork/tests/engine/test_parallel_plan.py", "pi-autowork/src/pi_autowork/engine/parallel_dispatch.py", "pi-autowork/tests/engine/test_parallel_dispatch.py", "pi-autowork/src/pi_autowork/blockers_report.py", "pi-autowork/src/pi_autowork/task_handoff.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "TOOLSET-463-8af43073 is an owner-only task whose latest note is `Owner decision: 2026-11-10: deferred: ok`. The project still showed Needs attention, `blocked by Live authorization` and one open question. A task whose latest dated Owner decision note starts with `deferred` is shown with the state Deferred: it stays in the task list, it is not counted as a question, a blocker or a reason for Needs attention, and it does not appear in the health line or BLOCKERS.md questions block. It has no expiry: only a later dated Owner decision that does not start with `deferred`, or a record change that removes the note, reopens it. `autowork scorecard` lists deferred tasks with their age in days."
acceptance = ["A fixture with one owner-only task and a dated `deferred` Owner decision proves the runner health, the fleet row, the Tasks view counts and the generated questions block do not report it as attention, blocker or question, and the task list shows it as Deferred.", "A later dated Owner decision that is not a deferral restores the previous owner-action presentation, and a deferral never dispatches the task, grants live authorization or closes it.", "The scorecard lists each deferred task with its age; README text for the fleet inventory states the Deferred state."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_task_snapshot.py pi-autowork/tests/runner/test_fleet_view.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
closure = "manual"
closure_actor = "repository-maintainer"
closure_timestamp = "2026-11-11T02:22:34.791402+00:00"
closure_reason = "Implemented and integrated explicit deferrals, selection/restart guards, health/report/count consistency and scorecard ages; focused offline regressions and independent review passed. No live qualification claimed."
closure_evidence = "git:8c606f27ca55fc56f6700b52f88dc37c79eac2bf"
+++
- Sources: Owner decisions of 2026-11-10 (grilling rounds 1 and 2, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
