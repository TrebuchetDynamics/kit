+++
schema = 1
id = "TOOLSET-500"
title = "Restore recorded per-task review limits after coordinator reload"
short = "Retain review budget across reloads"
status = "done"
section = "Now"
rank = 11000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/runner/test_worker_tmp.py"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Repair the existing adaptive review-timeout continuation contract. Reuse a single reader for the already-recorded slot reverified suffix budget in both review_limit and reverify_after_timeout, so a fresh coordinator retains an earlier larger per-task limit. Keep the existing four-hour cap, configured/recent-review minimum behavior, bounded retry exhaustion, reviewer identity, exact attempt/candidate and check-slot accounting. Do not modify current slot files, service settings or the active review."
acceptance = ["A regression constructs a fresh coordinator with empty timeout_limits and a private slot carrying reviewer.t7200; review_limit(task) restores7200 rather than1800, and start_integration passes that same budget to the engine timeout and reviewer environment without launching a real process.", "A stale smaller memory value cannot reduce the recorded budget; oversized recorded limits stay capped, malformed/missing records fall back safely, and existing review-limit defaults, batch/review recovery and worker scratch tests pass. No new state format, unbounded timeout, extra rework budget, source re-pin or worker restart is introduced."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_worker_tmp.py", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No mutation of current slot/attempt/receipt/runtime files, settings, grants or pauses; no worker interruption, service restart, push, install or live-success claim in offline completion."]
closure = "manual"
closure_actor = "debug-coordinator"
closure_timestamp = "2026-11-10T10:49:45.703277+00:00"
closure_reason = "Offline implementation and independent read-only review passed; integrated on canonical main. No active attempt or runtime state changed. Existing live reviews and service activation remain separate."
closure_evidence = "commit:e2d718f1; focused checker:75 tests passed; independent reviewer:no blockers; /tmp/kit-review-budget-reload-{red,green}.log"
+++
- Sources: User-authorized recurring debugging; coordinator.review_limit and reverify_after_timeout; existing ReviewLimitTests; restart/timeout journal of TOOLSET-479.
- Evidence: The runner recorded a larger per-task timeout, re-executed at01:57, then a later review ran out of time after1800seconds. review_limit restores repository review history and process-local timeout_limits only, while reverify_after_timeout separately reads the durable slot reverified .tN suffix. start_integration uses review_limit for both engine and reviewer timeout.
- Planner call: Share the existing durable suffix reader, take the larger safe remembered/recorded limit, and keep the established cap; do not introduce a new setting or state migration. Record-only observation is not proof the live resumed review passed.
- First action: Add failing fresh-coordinator budget/launch regression with a mocked producer, implement, run the focused worker test module and independent review.
- Ownership: Isolated .worktrees/fix-review-budget-reload; retain this new task uncommitted on main until verified offline closure so the not-yet-updated runner cannot dispatch a duplicate. Existing active task contracts stay unchanged.