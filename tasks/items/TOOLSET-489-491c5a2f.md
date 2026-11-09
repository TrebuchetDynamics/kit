+++
schema = 1
id = "TOOLSET-489-491c5a2f"
title = "Harden stalled-service fixture timing under suite load"
short = "Stalled service fixture hardening"
status = "done"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 23000
depends_on = []
touches = ["tests/test_pi_autowork.py"]
resources = ["autowork-python-layout"]
kind = "implementation"
ownership = "worker"
scope = "Harden test_pi_autowork.EngineTests.test_a_stalled_service_says_so_once_and_the_fleet_view_shows_why and its test-owned check_blocked_service setup, observation, diagnostics and cleanup in tests/test_pi_autowork.py. Investigate fixture isolation and inherited environment, resource contention and timing across held A, released B, dependent C and repeated status observations. Use evidence to implement a test-only synchronization or isolation improvement, preserving the real disposable Git/fake-worker scenario and the owner-only sibling test. Main is not red for this flaky test; this is not a product-code repair."
acceptance = ["Characterize suite-only failure versus isolated success from the named evidence and current fixture, including isolation, resource load and timing. Explain how the test-only change addresses the observed failure; do not infer a product defect from the flake.", "Preserve all behavioral assertions: B finishes despite A holding C; the engineering hold is attributed correctly; the service remains alive and becomes stalled only after the threshold; three later interval-spaced snapshots retain state and attribution; STALLED is logged exactly once; A and C remain unfinished/unstarted as appropriate; fleet text, structured roots/groups and status agree. Preserve owner-only waiting behavior without STALLED and guarded process-tree cleanup on assertion failure. No skip, retry-to-green wrapper, removed assertion or arbitrary sleep/deadline inflation.", "Repeated isolated runs and the affected module pass with source-bound results. Exercise representative contention or deterministic test-owned ordering, retain actionable diagnostics and cleanup, and run the full offline check with actual results/skips reported separately from live qualification."]
checks = ["Repeat the named isolated unittest at least three times in the repository checker environment; record commands, interpreter, timings and results.", "python3 scripts/check.py tests/test_pi_autowork.py", "python3 scripts/check.py"]
exclusions = ["No product-code repair, runtime dependency, task/goal or runtime-state edits, upstream Hermes edits, live/model calls, service operations, install, publication, deployment or acceptance weakening."]
closure = "manual"
closure_actor = "AnimatroniCode2"
closure_timestamp = "2026-11-09T19:48:10.893951+00:00"
closure_reason = "Stalled-service fixture isolates its git identity; named test passed three isolated runs. The module still has unrelated host git-identity failures in other tests."
closure_evidence = "commit 145e7313"
+++

- Sources: DOCS-MAINTAINER MAIN (flaky test) instruction; docs/testing.md#verify; docs/project.md#reliability-bug-harvest-2026-10-15; tests/test_pi_autowork.py
- Evidence: Read <git-common-dir>/autowork-execution/main-evidence/93f98ee62425e8f29469ddb96a59341c16529dce in place (canonical repository .git/autowork-execution/main-evidence/93f98ee62425e8f29469ddb96a59341c16529dce; resolve git rev-parse --git-common-dir from linked worktrees): main_check.json, main-check.log, main-check.exit, main-check-reruns.log and flaky_history.json. Both JSON histories retain test_pi_autowork.EngineTests.test_a_stalled_service_says_so_once_and_the_fleet_view_shows_why for revisions 5f2ac81841e1e62c37a6155793b1661795edde45, e057d1aa73643aa3931ee3d9b013a749aa804aa9 and 792cdbd7ed0ecbf9669b765a9b6becf93026e30f. The supplied instruction reports full-run failure followed by isolated success on each. The current bundle is red for two other tests, not this flake, and contains no new stalled-service rerun. Do not copy runtime evidence into Git.
- Additional evidence: Retained sibling bundle <git-common-dir>/autowork-execution/main-evidence/792cdbd7ed0ecbf9669b765a9b6becf93026e30f/main-check.log shows failure in check_blocked_service at the third-stage observe loop (tests/test_pi_autowork.py:2712/2687): its shared 60-second deadline expires while waiting for later interval-spaced snapshots; the diagnostic already shows state=stalled and A's reviewed_twice hold. Its main-check-reruns.log records isolated exit 0, one test in 45.888s. The earlier two revision bundles are no longer retained at those paths; the supplied bundle preserves their three-revision history. Treat timing/load as an investigation lead, not a proven root cause or a license to increase waits arbitrarily.
- Queue disposition: Append to Next after existing tasks; no producer/consumer prerequisite is established by shared test paths. Keep resource admission for autowork-python-layout and preserve all prior fixture changes. If accepted relocation lands first, use the same module at pi-autowork/tests/runner/test_pi_autowork.py and repair this contract's paths/checks through the supported CLI before dispatch; do not recreate the root test file. MAIN-011 repairs different tests; do not conflate hardening with restoring red main.
- Checks status: Proposed, not executed by this maintainer; no hardening or live qualification is claimed.
- Commit inspection: The flaky revisions' own changes are 5f2ac818 (Rust foundation closure records and changelog), e057d1aa (planning-authority plan and task), and 792cdbd7 (standing-authority policy/skill/task records and tests/test_workflow_cycle.py). None changes the stalled-service fixture or proves a runtime defect. Touches therefore stays on the failing test module and its test-owned helper, not unrelated production owners. The current shared 60-second observation deadline is a concrete test timing lead; investigate before choosing the synchronization/isolation repair.
