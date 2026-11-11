+++
schema = 1
id = "SPEED-008"
title = "The pre-push hook skips affected tests when the runner holds a passing receipt for the same tree"
short = "Pre-push reuses a passing receipt"
status = "open"
section = "Now"
rank = 20000
depends_on = []
touches = ["scripts/pre_push_check.py", "pi-autowork/src/pi_autowork/supervision/maintenance.py", "pi-autowork/src/pi_autowork/coordinator.py", "tests/test_pre_push_check.py", "pi-autowork/tests/runner/test_async_maintenance.py", "docs/testing.md", "AGENTS.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "A landed change is tested in the batch check, in the main check and again by scripts/pre_push_check.py, and then by CI. On 2026-11-10 the pre-push run failed only because of host load and publication stopped for an hour. When the runner publishes, it passes the hook the path of its check receipt. The hook skips the affected-test run only when that receipt is a passing full-suite result with no failure, timeout or skip and its Git tree equals the tree of the commit being pushed; it prints which receipt it reused. Any mismatch, a missing or unreadable receipt, or a push not started by the runner runs the affected tests as today. The docs check, task-store validation and private-terms scan run on every push."
acceptance = ["A fixture proves a runner push with a passing receipt for the exact tree runs the core contracts and the private-terms scan, skips the affected tests and names the receipt.", "Fixtures prove a receipt for another tree, a receipt with a failure, timeout or skip, a malformed receipt and a push without a receipt each run the affected tests.", "docs/testing.md and AGENTS.md describe the reuse rule beside the existing KIT_PRE_PUSH text."]
checks = ["python3 scripts/check.py tests/test_pre_push_check.py pi-autowork/tests/runner/test_async_maintenance.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
