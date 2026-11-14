# Repository agent instructions

## GitHub-native execution

GitHub Issues are the authoritative executable backlog. Kit plans; Orbi delivers
issues through Pi, tests, PRs, independent review and merge gates. All issues default
to `ai-ready`, regardless of author. Planning creates complete batches under
`ai-planning`, verifies native `blockedBy` dependencies, then publishes readiness
last; `ai-epic` coordination issues do not execute. Preserve explicit pauses,
actual ownership, CI, sensitive-change controls and human-only requirements.
Both `/plan-with-me` and `/plan-for-me` save executable plans as GitHub Issues,
not local task records. Keep their current names; `/autowork` is compatibility-only
and retained Hermes maintenance names are not executor support.
See `docs/github-native.md` and `skills/shared/PLAN-HANDOFF.md`.

The pi-autowork executor, CLI and Paseo plugin are retired, unsupported and removed.
Do not develop or repair the retired executor, restore it from older branches,
install or restart it, prepare local task stores or acquire legacy leases.
If an existing assignment targets pi-autowork, stop that executor work, preserve
its changes and evidence, and reconcile still-required outcomes into GitHub Issues
for Orbi. An old task, plan or research recommendation does not authorize revival.
Existing tasks, worktrees and attempts/recovery state are preserved migration evidence, not a
second queue. Orbi remains paused and live-unqualified; do not enable it as part
of removal. No local-main planning commit is required for issue publication.

Kit supplies repository workflows, command registration and profile setup. Read
README.md and relevant docs before changing these contracts. Preserve unrelated
changes and keep credentials, private profile identities and runtime state out
of Git. Do not edit or patch upstream Hermes Agent.

- Read `~/.agents/skills/using-superpowers/SKILL.md` when available and apply the
  relevant workflow; existing user authorization takes precedence over repeated
  planning or approval ceremonies.
- Prefer codebase-memory MCP tools for code discovery; index the repository if
  needed. Fall back to `rg` when tools are unavailable or results insufficient.
- Use Context7 (resolve library ID, then query docs) for current external library
  or CLI contracts. Local business logic and instruction edits need no lookup.
- Full check: `python3 scripts/check.py`
  The checker provisions its own CPython 3.12 and `requirements-test.txt` environment with
  `uv`, so a bare `python3 scripts/check.py` runs the documented check on a host whose
  `python3` is not that interpreter.
  CI runs it on every push (two jobs), so a push does not wait for it. The pre-push hook (`python3 scripts/pre_push_check.py
  --install` once per clone) runs the core contracts and targeted affected tests;
  whole-suite selections print the reason and defer execution to CI, not a local pass.
  Direct `scripts/affected_tests.py --run` retains its conservative full-suite fallback.
  A document edit costs seconds, not the suite. `KIT_PRE_PUSH=0` or `git push --no-verify`
  leaves a push to CI.
- Test only what your change can affect: `python3 scripts/affected_tests.py --run`
  selects and runs the test modules that import, run or read the files you changed
  (since origin/main; `--base REV` otherwise) and prints why each was chosen. Do not
  rerun whole test directories or the full check for a focused change: CI
  checks the integrated changes. `python3 scripts/check.py` runs the safe offline
  check inventory; inspect native/live tests before running them. Registration
  checks do not prove model execution or Telegram delivery.
- Keep public examples generic and preserve existing per-profile job state.
  Instruction changes alone do not prove that a cron job completed a task.

## Completed work and documentation

This repository keeps current requirements and unfinished work, not a completed-task
archive. Git history is the record of past work. Do not create or append task-history
reports, completed-task tables, or `TODO.archive.md`; update current behavior and
operating instructions instead. Routine completion replies summarize the change and
checks without listing closed task IDs or task-document paths unless requested.

Keep done-task retention to the minimum required by current consumers and safety.
GitHub history owns new completion evidence. Preserve existing legacy tasks,
attempts, worktrees and recovery state during removal/migration. `/docs-sync` does
not prune them; the removed task CLI is not a cleanup mechanism. Any later pruning
requires separately scoped safe reconciliation, fresh ownership checks and retained
immutable evidence; never remove an active attempt or its recovery inputs.
Never alter a running contract, fabricate completion, drop a
verified dependency or discard an unresolved live obligation. Keep goal status and
live/owner gates unchanged; an empty history is not proof that a goal is met.
Do not rewrite Git history or change archive-import fixtures merely for cleanup.

## Delegation

Start every dispatched subagent or worker in a **fresh context window**. Some harnesses
fork the parent conversation by default, and a fork inherits the context the dispatch
was meant to leave behind. A dispatched run also states its scope, its completion
criterion and whether it may write; a read-only review stays read-only. The rule in
[docs/skill-standard.md](docs/skill-standard.md) applies to every skill that dispatches.

## Worktree location

Interactive sessions (an agent working with the owner, a repository bot, the
owner) work directly in the main checkout, one at a time. The first session to edit
a file there holds the checkout until every file it edited is committed or reverted,
or it ends; a second interactive session works in its own worktree meanwhile.
Otherwise worktrees are only for delivery workers and for parallel delegated agents
that would otherwise write the same checkout at once. Keep one writer per checkout:
do not edit files a live runner worker owns, and commit only your own changes.

The user requires all new task worktrees under the **canonical repository's
`.worktrees/` directory** (plural). This overrides skill defaults and examples.
Never create sibling `<repo>-<task>` directories or new
`.claude/worktrees/` checkouts. Resolve the canonical checkout from `git worktree
list --porcelain`, including when already in a linked worktree. Reuse an existing
task checkout when appropriate and ensure `/.worktrees/` is ignored.

Claude must use `EnterWorktree` with the configured user `WorktreeCreate` hook;
manual Bash creation bypasses that hook. Preserve live sessions, dirty files and
unmerged branches when relocating or closing worktrees. See
`docs/worktree-placement.md` for the hook configuration.

## Authorized local progress

Accepted scope authorizes routine reversible implementation, focused tests,
documentation and scoped commits without repeated planning ceremonies. Follow
[the standing decision policy](docs/autonomy.md), while preserving explicit
exclusions, pauses, actual ownership, access controls and human-only gates.

- Read current issues and repository state; never invent acceptance or ownership release.
- Use `/work` for explicitly requested manual implementation; `/autowork` is only
  a GitHub/Orbi compatibility redirect, not an autonomous loop or service control.
- Separate offline implementation from device, production and live qualification.
  Keep unresolved live proof visible in current requirements and GitHub Issues.
- Keep one writer per checkout. Verify actual activity before adopting an idle
  candidate; when activity is unknown, choose non-overlapping work.
- Serialize authorized integration and preserve unrelated dirty changes. No
  force-push, reset, discarded recovery state or repinned evidence to hide drift.
- After a repeated blocker, repair the cause, do independent accepted work or
  report the precise missing external input. Do not manufacture backlog work.
- Commit only attributable verified changes. Report changes, checks and remaining
  blockers; distinguish commit, integration, push, installation and live acceptance.
