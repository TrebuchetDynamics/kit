# Worktree isolation

Apply the [mode-aware freshness contract](COMMON-CONTRACT.md#source-freshness-and-delivery-ownership) first. Read-only and planning modes do not create worktrees or fetch.

Before creating an authorized writing checkout, inspect repository instructions, Git status,
existing worktrees and active ownership. Pin the intended base to an immutable
commit from a verified intended upstream baseline and identify required prerequisites.
When stale or shared, isolate authorized edits there rather than updating another
writer's checkout. Preserve outstanding Orbi coordinator ownership even when its
checkout is clean; an open PR is not an integration candidate. A clean base does not include dirty
backlog edits or uncommitted dependencies; resolve attribution before assembling
an isolated candidate. Never copy foreign edits to manufacture a clean gate.

Use a private worktree when the workflow requires isolation, unless the user's
scope explicitly requires the current checkout. Keep the checkout and owned file
boundaries in the handoff. Verify its repository identity, base and required files
before editing. New task worktrees belong under the canonical repository's
`.worktrees/` directory. For Orbi delivery, preserve its actual ownership and
freshness checks; legacy manifests are not admission gates for new work.

Worktree creation is not commit, push, merge, cleanup or delivery authorization.
Preserve existing worktrees, branches, indexes and live writers. Remove only
scratch you created when it is no longer needed, without deleting receipts or
launch inputs required for recovery.

For authorized cleanup, apply [worktree closeout](../git-commit-push/references/worktree-closeout.md).
Keep active, dirty, locked, unmerged and recovery-bearing worktrees. Unknown
ownership means retain. Existing legacy worktrees are preserved during executor
removal; no bundled closeout helper remains and no cleanup is automatic.
