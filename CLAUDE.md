# Repository instructions for Claude

Read and follow [AGENTS.md](AGENTS.md) in this directory. It owns the repository
contracts: GitHub Issues and Orbi delivery,
check selection, worktree placement, delegation and reporting.

Claude Code adds two enforced mechanics on top of those rules:

- **Worktrees:** use `EnterWorktree`. The user `WorktreeCreate` hook creates the
  checkout under `<canonical-repo>/.worktrees/<task>/` and refuses sibling or
  `.claude/worktrees/` locations. Do not create task worktrees with manual
  `git worktree add`; the Bash guard redirects it. See
  [docs/worktree-placement.md](docs/worktree-placement.md).
- **One interactive writer:** the `checkout-lock` hook denies an edit in the
  canonical checkout while another session holds it. Continue in your own
  worktree or wait; release only a stale holder, never a live one with
  uncommitted files.

The explicit user location overrides bundled skill examples. Preserve other
sessions, dirty files and unmerged branches.
