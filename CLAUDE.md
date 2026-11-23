# Claude Code repository instructions

Read and follow [AGENTS.md](AGENTS.md). It owns shared repository policy, including
GitHub Issues/Orbi delivery, check selection, worktree placement, delegation and reporting.
Only Claude-specific hook mechanics belong below.

## Worktree entry

Use `EnterWorktree`, not manual `git worktree add`. The user `WorktreeCreate` hook
places checkouts under `<canonical-repo>/.worktrees/<task>/` and refuses sibling or
`.claude/worktrees/` locations; the Bash guard redirects manual creation.
For hook behavior, read [worktree placement](docs/worktree-placement.md).
The explicit user location overrides bundled skill examples.

## Interactive ownership

The `checkout-lock` hook denies edits in the canonical checkout while another
session holds it. Continue in your own worktree or wait. Release only a stale
holder, never a live one with uncommitted files. Preserve other sessions, dirty
files and unmerged branches.
