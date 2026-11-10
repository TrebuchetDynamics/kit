+++
schema = 1
id = "SPEED-006"
title = "Status warns when another runner session publishes to the same upstream"
short = "Warn on a second publisher"
status = "open"
section = "Next"
rank = 30000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/supervision/maintenance.py", "pi-autowork/src/pi_autowork/health.py", "pi-autowork/tests/runner/test_async_maintenance.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "On 2026-11-10 two kit runners on two machines pushed to origin/main; each main diverged by about 50 commits and publication stopped until a manual merge. One publisher per repository is the rule, enforced by setting: PI_AUTOWORK_PUSH=1 on one machine only. Add one status line, also shown in the fleet view, when the fetched upstream branch contains merge commits whose subject names a `pi-autowork/` session branch other than this runner's own sessions. The line names the other session and says that only one runner may push for a repository. It is a warning: it does not stop dispatch, merging or the push. README states the one-publisher rule."
acceptance = ["A local-remote fixture with an upstream merge commit from a foreign `pi-autowork/` session produces the warning line once per foreign session, and an upstream with only this runner's sessions or ordinary commits produces none.", "Dispatch, upstream merge and publication behave exactly as before with the warning present.", "README states that only one runner pushes for each repository and what the warning means."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_async_maintenance.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling rounds 1 and 2, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
