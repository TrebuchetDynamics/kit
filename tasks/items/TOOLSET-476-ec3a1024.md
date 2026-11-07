+++
schema = 1
id = "TOOLSET-476-ec3a1024"
title = "Preserve recovery checkpoints during automatic worktree closeout"
short = "Keep recovery checkpoints intact"
status = "open"
goal = "SKILL-ADHERENCE"
section = "Now"
rank = 2000
depends_on = []
touches = ["Src/pi_autowork/engine/worktree_closeout.py", "pi-autowork/engine/test_worktree_closeout.py", "skills/autowork/references/worktree-closeout.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Make worktree_closeout preserve the explicit recovery/ branch namespace in report, apply and archive modes, including explicitly named and prunable registrations. The repository policy requires recovery-bearing worktrees/branches to survive ordinary task cleanup. Use a small guard in existing judge(), no new database, override flag or destructive recovery behavior. Preserve ordinary merged-task cleanup, all current locked/live/dirty/evidence guards and source-bound archive checks. Document the reserved recovery namespace and manual explicit-owner removal boundary."
acceptance = ["Disposable real-Git fixtures show an unlocked clean merged recovery/checkpoint worktree and its exact branch/files survive report/apply/archive and explicitly targeted cleanup; the returned kept reason identifies recovery preservation.", "A missing-directory/prunable recovery registration and branch remain intact; ordinary autowork/recovery-task branches and existing merged-clean cleanup still work, with current locked/live/dirty/unmerged/evidence safeguards unchanged."]
checks = ["python3 scripts/check.py pi-autowork/engine/test_worktree_closeout.py tests/test_worktree_closeout.py", "git diff --check"]
exclusions = ["No real-repository cleanup tests, service controls, package install, model calls, publication or permission changes. Test removal/archive only in disposable test-owned repositories.", "No automatic deletion of recovery branches or worktrees, even if merged/clean/old; no branch-name substring heuristic beyond the explicit recovery/ namespace, no new deletion override or broad cleanup refactor."]
+++
- Sources: skills/autowork/references/worktree-closeout.md; repository instruction to preserve recovery-bearing candidates; current in-session Work maintenance authority.
- Work search: During supported owner_cycle task acquisition, automatic cleanup removed a clean integrated recovery/parked-display-edits checkpoint. Immediately restored its original branch/worktree at exact7e15be3b and locked it; no source content was lost. Existing judge checks merged/clean/quiet/process use but ignores recovery namespace. Rejected relying only on manual locks because future recovery checkpoints can be unmarked and cleanup claims run automatically.
- Decision: Reserve recovery/ branch prefix as an unconditional preservation reason in judge, including --archive and explicit --worktree requests. Owners may use ordinary explicit Git operations outside automatic helper when truly authorizing recovery disposal. Coding detail: a small early guard; no new runtime registry or features.
- Repo obligations triggered: engine closeout implementation, its real-Git fixture seam and skill worktree-closeout safety contract must agree; normal autowork/ merged cleanup and all other negative guards remain. No manifest/schema/lock/CI changes needed.
- Scheduling: Independent of pending portable Work delivery; shares the same private checkout only serially. Canonical Src-to-src migration is a separate active writer: preserve it and defer canonical integration until safely released. Kit remains deliberately stopped; do not restart it.
- Next action: Offline guard implementation is complete;22engine+3root disposableGit tests passed, fresh independent review68cda8ed found no blockers. Worktree-closeout policy documentation updated. Pending canonical integration after foreign Src-to-src migration completes/releases main; rerun invalidated checks on assembled tree before honest closure. Protected recovery checkpoints remain restored and locked; no real-repository cleanup test or service restart performed.
