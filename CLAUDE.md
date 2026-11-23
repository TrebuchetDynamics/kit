# Claude Code in Kit

Read and follow [AGENTS.md](AGENTS.md) for shared repository policy.

- **Creating a worktree:** Use `EnterWorktree`. The user’s `WorktreeCreate` hook places the checkout under `<canonical-repo>/.worktrees/<task>/`. This location overrides bundled skill examples. Do not bypass the Bash guard with manual `git worktree add`.
- **If `checkout-lock` denies an edit:** Wait for the holder or use `EnterWorktree` for your own checkout. Never release a live holder’s lock to proceed. Release a lock manually only if you confirm the holder is stale. Preserve live sessions, uncommitted files and unmerged branches.

For hook behavior and ownership checks, see [worktree placement](docs/worktree-placement.md).
