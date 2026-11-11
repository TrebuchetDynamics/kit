+++
schema = 1
id = "SPEED-013"
title = "Known load-sensitive tests run in one serial lane at the end of the check"
short = "Serial lane for load-sensitive tests"
status = "open"
section = "Next"
rank = 35000
depends_on = []
touches = ["scripts/check.py", "tests/test_check.py", "docs/testing.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Three runner tests failed at a host load of 65 and passed at 31 on 2026-11-10: test_pi_autowork.EngineTests.test_interrupt_and_resume, test_pi_autowork.EngineTests.test_a_crash_with_nothing_to_install_is_reviewed_again_and_lands_once_it_runs and test_parallel_dispatch.DispatchTests.test_a_worker_whose_task_closes_on_the_base_is_stopped_and_set_aside. FLAKE-002 and FLAKE-003 each repaired one such test. In scripts/check.py keep one explicit list of load-sensitive test ids; the parallel shards leave them out and one serial lane runs them after the shards finish. The list starts with the three tests above and the tests named by FLAKE-002, FLAKE-003 and FLAKE-004. Every listed test still runs in every full check and counts toward the result. A listed id that matches no test fails the check."
acceptance = ["tests/test_check.py proves each listed test runs exactly once, in the serial lane after the parallel shards, and that the total test count of a full check is unchanged.", "A listed id that matches no existing test fails the check with the id named; a focused run of one module still runs its listed tests.", "docs/testing.md names the lane, the list and the rule for adding a test to it: it failed under load and passed alone, with both runs recorded."]
checks = ["python3 scripts/check.py tests/test_check.py", "python3 scripts/check.py", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
