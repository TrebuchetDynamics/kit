+++
schema = 1
id = "SPEED-009"
title = "A runner updates its toolset only with no work in flight and at most once an hour"
short = "Toolset updates only when idle"
status = "open"
section = "Next"
rank = 31000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/supervision/maintenance.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/runner/test_async_maintenance.py", "pi-autowork/README.md", "pi-autowork/src/pi_autowork/cli.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "The kit runner restarted on a new toolset five times in three hours on 2026-11-10; each restart waited for reviews (`Reload pending`) and paused new dispatch. Automatic toolset update, in pi-autowork/src/pi_autowork/supervision/maintenance.py and the coordinator's update path, starts only when this runner has no worker, review, batch, resolver or landing in flight, and not sooner than one hour after its previous automatic update. The existing rule that defers for other runners' work stays. An explicit `autowork update` or `autowork restart` acts immediately as today. Status shows the pending release and why it waits."
acceptance = ["A fixture proves a newer release is not installed while a worker or review is in flight and is installed once the runner is idle.", "A fixture proves a second newer release within one hour of the last automatic update waits, and an explicit update or restart request is honoured immediately.", "Status and the log name the pending release and the reason it waits; README states the rule."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_async_maintenance.py", "python3 scripts/affected_tests.py --run --base 5898a391c74538754d5d09b72064eb8d1664e1f6", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
- Review remediation: The review requires an acceptance list, not merely passing checks: report exactly one entry for each of the three admitted Acceptance strings, with exact item text, honest result and concrete evidence. Reconcile the retained attempt-2/report.json against the actual candidate; it now contains all three entries, so do not invent a new product change to repair an older report. The same report names cli.py status_view as the status output owner and lists that changed file; Touches now includes it without expanding the accepted status requirement. The affected-check placeholder is resolved to the captured base 5898a391c74538754d5d09b72064eb8d1664e1f6 from that report. Its 1800-second admission timeout ran no tests and is not passing affected-check evidence: obtain admission and complete the declared command. Record literal Checks identities in report.checks.command, with admission wrappers/timings in summary. Preserve all acceptance, explicit update/restart behavior, fleet deferral and authorization. Sources: accepted owner decisions cited above; attempt-2/report.json; review-findings/SPEED-009.json; engine/parallel_integrate.py report_mismatch. No completion or scorecard improvement is asserted.
