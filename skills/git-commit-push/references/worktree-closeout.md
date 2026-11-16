# Worktree closeout

Task worktrees are temporary implementation spaces, not the final delivery
location. There is no hard limit on useful active worktrees: 20 or 50 may be valid
while workers need them. Minimize abandoned finished worktrees instead of limiting
concurrency or deleting active work.

## Integrate first

Record the canonical checkout, its actual default branch (`main` or `master`, not
both), the task worktree/branch and ownership when creating a worktree. Reuse a
suitable existing task worktree before creating another. Never rename a repository's
branch or switch another session's checkout to manufacture the desired target.
An explicitly different repository integration policy still applies.

Before ending a worktree-backed task, complete required checks/review, integrate
through the repository's supported path and verify the delivered commit on the
canonical default branch. Serialize canonical writes and preserve unrelated edits.
First `git fetch` the default branch's upstream, if one exists, and bring the canonical
`main` up to date (`git merge --ff-only origin/main`, or the pull and merge procedure
when local commits exist); integrating onto a stale local `main` diverges from the
remote. A local task-branch commit is not integration. No push or remote merge authority
is granted by cleanup. If integration is blocked, report **integration pending**,
retain the candidate and continue only independently authorized work.

## Preserve ownership and recovery evidence

The bundled executor closeout helper is removed. `worktree_sweep.py --remove`
requires an explicit existing `--closeout` helper; it fails before merging when
one is unavailable. There is no automatic deletion or unsafe Git fallback.
Review the supplied helper's ownership checks before using it.

Any removal must independently verify: integrated HEAD, clean tracked/untracked
and ignored non-cache files, unlocked registration, no active process or attempt,
no recovery branch or retained receipts, and unchanged inputs immediately before
removal. Keep unmerged work and report **cleanup pending** with its reason.
These instructions are not a runtime guarantee that a host performed the checks.
Unknown ownership means keep. Age or a clean tree alone is not proof
that a worktree is unused. Preserve legacy worktrees and attempts during executor
removal; later cleanup needs separate scope.

Use ordinary Git removal only under that verified authority, never force deletion,
blanket pruning or history rewriting. Do not archive another writer's dirty work
to evade a safety check. Report integration and cleanup separately, including
each kept path and its exact preservation reason.

The [shared ownership contract](../../shared/WORKTREE-ISOLATION.md) governs
current closeout; retired executor commands are not available in this package.
