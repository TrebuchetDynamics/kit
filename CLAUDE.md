# Repository instructions for Claude

Read and follow `AGENTS.md` in this directory.

`pi-autowork` is retired and unsupported: do not develop, repair, restore, install
or restart its executor, CLI or Paseo plugin. If an older assignment targets it,
stop that work and preserve uncommitted changes and recovery evidence. Reconcile
still-required outcomes into GitHub Issues; old plans do not override retirement.
Kit's `/plan-with-me` and `/plan-for-me` publish GitHub Issues. Orbi owns delivery;
`/work` is the explicit manual alternative and `/autowork` only a compatibility
redirect. Orbi remains paused and live-unqualified; this policy does not enable it.
See `docs/github-native.md` for the current contract.

Interactive sessions work directly in the main checkout, one at a time. The first
session to edit a file there holds the checkout until its edits are committed or
reverted; a second session works in its own worktree (`EnterWorktree`) meanwhile.
The checkout-lock hook enforces this (docs/worktree-placement.md). Otherwise,
worktrees are for delivery workers and parallel delegated agents only.

Those worktrees belong in `<canonical-repo>/.worktrees/<task>/` (plural),
including delegated Claude work. Never create sibling repository directories or
use `.claude/worktrees/`. Use `EnterWorktree`; the user WorktreeCreate hook enforces
the destination. Reuse existing task checkouts. Preserve other workers and
uncommitted work. The explicit user location overrides bundled skill examples.
