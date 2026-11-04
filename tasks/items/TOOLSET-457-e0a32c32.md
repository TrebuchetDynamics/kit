+++
schema = 1
id = "TOOLSET-457-e0a32c32"
title = "Qualify the reserved owner slot against exclusive, serial and live work"
short = "Qualify the reserved slot"
status = "done"
goal = "RELIABILITY-2026-10"
section = "Now"
rank = 6000
depends_on = []
touches = ["pi-autowork/engine/test_parallel_dispatch.py", "Src/pi_autowork/engine/parallel_dispatch.py", "CHANGELOG.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Commit 7c746892 on branch dsh-lessons lets one paused, restarted or answered attempt resume beside a full worker pool (N+1) so fresh autonomous work cannot displace a person's continuation. Review that commit independently in a fresh, read-only context and record its findings, then prove with deterministic tests that the reservation cannot violate the existing scheduling constraints: parallel_plan.plan applies exclusive, serial, dependency and shared-resource conflicts before dispatch, so a reserved attempt that conflicts stays waiting with the plan's typed reason, and an unconflicted paused attempt still resumes beside a full pool. Merge 7c746892 into main only when the review and both tests hold, without pushing."
acceptance = ["An independent read-only review of 7c746892 (fresh context, no repository writes) records findings with file and line references, or states that it found none; the result is cited in this task's evidence.", "A deterministic test proves that a paused, resumed attempt whose Touches or Resources conflict with a running exclusive task, a serial path or a shared live/exclusive resource does not start when the pool is full and the reserve is available; it stays waiting with parallel_plan's typed reason.", "A paused attempt with no conflict still resumes beside a full pool with N+1 workers and reports owner_slot = 1.", "The commit is merged into main only after the review and both tests hold, locally and without push; a defect found by the review is reported instead of merged."]
checks = ["python3 scripts/check.py pi-autowork/engine/test_parallel_dispatch.py pi-autowork/engine/test_parallel_plan.py", "python3 skills/docs-sync/scripts/docs.py check ."]
exclusions = ["No widening of the reserve: one attempt at most, after a free normal slot, below the hard slot limit.", "No change to exclusive, serial, dependency, lease or ownership rules, and no bypass of a live resource holder.", "No push, no service start or restart, and no change to another runner's state."]
closure = "manual"
closure_actor = "interactive-autowork-session"
closure_timestamp = "2026-11-04T18:45:38.186724+00:00"
closure_reason = "Implemented and offline-verified under the owner-approved audit follow-up; manual close, so no coordinator receipt (no runner service was installed or restarted)"
closure_evidence = "commits and checks in the Evidence note"
+++
- Sources: branch dsh-lessons docs/research/authorized-autonomy-audit-2026-11-04.md#6-worker-slot-fairness
- Evidence: Commits 36d47878 (cherry-pick of 7c746892) and eac1b709. An independent fresh-context read-only review of 7c746892 recorded findings: approve with required tests, no conflict bypass found; it found the reported limit could read below active workers, the owner_slot event outside the writer lock, and four untested branches. All were fixed and the six required tests added: exclusive holder, serial holder, free normal slot first, memory-gate refusal, launch failure, two paused attempts, hard-limit disable, and honest reporting while the reserved worker lives. 87 dispatch, 14 e2e and 7 status tests green. No service start, restart or live worker was exercised.
