+++
schema = 1
id = "TOOLSET-496"
title = "Let verified publication finish repository pre-push checks before its deadline"
short = "Allow pre-push checks to finish"
status = "open"
section = "Now"
rank = 14000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/supervision/maintenance.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/runner/test_async_maintenance.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Repair the evidenced five-minute publication deadline in both background and synchronous publication. Use one shared finite 3600-second whole-push budget, including local pre-push hooks, rather than disabling checks or creating an alternate publisher. Preserve the asynchronous scheduler, exact verified source, grant and destination guards, bounded attempts/backoff, remote readback, process-identity cleanup and all existing fetch/probe/update deadlines. Add one focused regression at the existing async-maintenance seam and update the publication runbook. Execute in an isolated checkout because live workers own other runner paths; integrate only attributable verified work on main."
acceptance = ["A regression in test_async_maintenance.py proves background publication passes a 3600-second tracked job limit and synchronous publication uses the same budget; an existing local-repository push still publishes the exact verified SHA with hooks enabled.", "Existing slow-pre-push/nonblocking scheduler, timeout descendant cleanup, authority refusal, bounded retry, endpoint and unknown-outcome/readback tests remain unchanged and pass. Fetch remains 120 seconds, remote probes 60 seconds and package update 600 seconds.", "The publication README states the one-hour whole-push bound and explains that pre-push verification is included. No hook bypass, runtime-state edits, forced restart, task acceptance change or live-success claim is introduced."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_async_maintenance.py", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No changes to running worker contracts, service settings, pauses, live grants, credentials, hooks, remote protections, retry accounting, readback semantics or production/device state.", "Local offline fix does not prove installed or live publication. Activation must wait for supported safe reload and actual delivery."]
+++
- Sources: User-authorized recurring Autowork debugging; pi-autowork/README.md publication; pi-autowork/src/pi_autowork/supervision/maintenance.py publish; coordinator.py push.
- Evidence: Journal recorded repeated push exit124 with remote unchanged. Background maintenance.publish launches the whole git push with limit300; synchronous Coordinator.push also sets timeout300. This includes repository pre-push hooks. Exact immutable candidate bc3c2bfb published successfully through the same normal hooks only when given a long enough external deadline; /tmp/kit-final-push.log and .exit0 record191offline modules. No network/credential defect is inferred.
- Planner call: Share a fixed3600-second bounded whole-push limit across both existing paths; preserve shorter non-push operation budgets. This permits observed 20-plus-minute full verification without allowing an unbounded stuck push. No new environment setting, separate verifier or bypass is needed.
- First action: Add the failing budget regression in the existing async maintenance module, then change the shared budget and documentation. Completion requires focused checks and independent review.
- Ownership: Current interactive debug coordinator owns implementation in .worktrees/fix-publication-hook-budget; coordinator-owned record prevents duplicate runner dispatch. No task hold or live authority added.
- Skill application: repeated timed-out publication; skills/engineering/upstream/skills/debugging-and-error-recovery/PROTOCOL.md@1be8e34187e34647bb83adc3a1323b26ae6f6abe; traced timeout to whole-push launch including hooks; future focused regression initially unrun.