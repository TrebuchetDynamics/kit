+++
schema = 1
id = "TOOLSET-425-eaea1e56"
title = "Make git-commit-push sweep finished worktrees into the base branch"
short = "Sweep worktrees on all"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Now"
rank = 1000
depends_on = []
touches = ["skills/git-commit-push/SKILL.md", "skills/git-commit-push/scripts/worktree_sweep.py", "skills/git-commit-push/references/worktree-sweep.md", "adapters/skills/git-commit-push/SKILL.md", "skills/ask-autowork/SKILL.md", "docs/workflows.md", "CHANGELOG.md", "tests/test_worktree_sweep.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Add a worktree sweep to /git-commit-push so an all request also merges the finished worktrees into the base branch. Ship a bundled script that classifies every registered worktree, merges only the clean unmerged ones with --no-ff oldest-first, aborts only the merge that conflicts, and refuses a canonical checkout that is on another branch, dirty or mid-merge. Never commit, stash, reset, rebase or discard another writer's work; dirty worktrees are reported or archived through the existing worktree_closeout.py. Add a reference for the order, rules and report, a router row, a workflow table row and a real-Git fixture test."
acceptance = ["worktree_sweep.py classifies merged, unmerged-clean, unmerged-dirty, detached and locked worktrees with ahead counts, dirty counts and activity age, and a read-only run changes no file.", "With --apply it merges only unmerged-clean worktrees, oldest commit first, using a merge commit of the exact classified commit; a conflict aborts that merge, leaves no MERGE_HEAD, and the remaining worktrees still merge. It refuses a dirty canonical checkout, a different checked-out branch and an existing merge in progress.", "A worktree whose Git metadata changed inside --idle-minutes is skipped and reported as active, --remove delegates merged worktrees to worktree_closeout.py, and a real-Git fixture covers classification, the apply path, a conflict, the idle guard and both refusals. The skill text, reference, router row, workflow row and CHANGELOG describe the behaviour; affected suites and node --test tests/portable_pi.test.mjs pass."]
checks = ["python3 scripts/check.py tests/test_worktree_sweep.py tests/test_skill_standard.py tests/test_portable_package.py tests/test_bundle.py", "python3 skills/git-commit-push/scripts/worktree_sweep.py .", "node --test tests/portable_pi.test.mjs"]
exclusions = ["No merge of the live repository's worktrees in this task, no branch deletion, no force, no rebase, no auto-commit of dirty work, no change to the runner's own merge or closeout logic, no publication."]
+++
