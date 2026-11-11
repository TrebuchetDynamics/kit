+++
schema = 1
id = "SPEED-009"
title = "A runner updates its toolset only with no work in flight and at most once an hour"
short = "Toolset updates only when idle"
status = "open"
section = "Next"
rank = 31000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/supervision/maintenance.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/runner/test_async_maintenance.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "The kit runner restarted on a new toolset five times in three hours on 2026-11-10; each restart waited for reviews (`Reload pending`) and paused new dispatch. Automatic toolset update, in pi-autowork/src/pi_autowork/supervision/maintenance.py and the coordinator's update path, starts only when this runner has no worker, review, batch, resolver or landing in flight, and not sooner than one hour after its previous automatic update. The existing rule that defers for other runners' work stays. An explicit `autowork update` or `autowork restart` acts immediately as today. Status shows the pending release and why it waits."
acceptance = ["A fixture proves a newer release is not installed while a worker or review is in flight and is installed once the runner is idle.", "A fixture proves a second newer release within one hour of the last automatic update waits, and an explicit update or restart request is honoured immediately.", "Status and the log name the pending release and the reason it waits; README states the rule."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_async_maintenance.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
