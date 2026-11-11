+++
schema = 1
id = "SPEED-007"
title = "A main check stops when main moves and starts on the new head"
short = "Main check follows the head"
status = "done"
section = "Now"
rank = 19000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/supervision/main_checks.py", "pi-autowork/src/pi_autowork/main_check.py", "pi-autowork/tests/runner/test_main_check.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "The runner keeps a main check running after main moves (`main check running on X; superseded by main at Y`). On 2026-11-10 one check ran 23 minutes on a commit main had already passed and the last green revision stayed two hours behind the head. In pi-autowork/src/pi_autowork/supervision/main_checks.py and main_check.py, stop the running check when main moves and start one on the new head. One limit keeps a busy main from never turning green: a check that has completed more than 80 percent of its test modules, by the checker's own module count, is allowed to finish. Stopping reaps the check's process group and its scratch worktree and temporary directory. A stopped check records no red or green result and no regression."
acceptance = ["A fixture proves a main check below 80 percent of its modules is stopped when main moves, its processes, scratch worktree and temporary directory are gone, and a check starts on the new head.", "A fixture proves a check above 80 percent finishes and records its result for its own revision, and the next check starts on the head.", "A stopped check changes neither the last green revision nor the red or regression state; status shows the check running on the head."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_main_check.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/SPEED-007.toml"
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
