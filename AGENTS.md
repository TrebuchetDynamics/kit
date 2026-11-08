# Repository agent instructions

Autowork supplies repository workflows, command registration and profile
setup. Read README.md and the relevant docs before changing these contracts.
Preserve unrelated changes and keep credentials, private profile identities and
runtime state out of Git. Do not edit or patch upstream Hermes Agent.

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
  --install` once per clone) runs the core contracts and only the affected tests; a
  document edit costs seconds, not the suite. `KIT_PRE_PUSH=0` or `git push --no-verify`
  leaves a push to CI.
- Test only what your change can affect: `python3 scripts/affected_tests.py --run`
  selects and runs the test modules that import, run or read the files you changed
  (since origin/main; `--base REV` otherwise) and prints why each was chosen. Do not
  rerun whole test directories or the full check for a focused change: the runner
  checks main in full after landing. `python3 scripts/check.py` runs the safe offline
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

After real closure and integration, prune completed task records and their dedicated
receipts/reports through a separate safe reconciliation. Use `autowork tasks` for
record edits. Check fresh status and actual ownership first; never remove an active
attempt, alter a running contract, fabricate completion or discard an unresolved live
obligation. Remove only already-satisfied ordinary dependency edges from inactive
surviving tasks. Preserve verified-dependency proof and any still-required qualification
via immutable Git inputs or current open requirements before pruning. Keep goal status
and live/owner gates unchanged; an empty history is not proof that a goal is met.
Do not rewrite Git history, remove worktrees/runtime recovery state, or change generic
archive-import fixtures merely to clean this repository. Runtime closeout may create
transient done records; this policy does not bypass its checks or promise immediate
automatic deletion by an already-installed runner.

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
Otherwise worktrees are only for Autowork runners and for parallel delegated agents
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

<!-- autowork-local-authority:start -->
## Autowork: autonomous local progress

An Autowork invocation or recurring Autowork job authorizes routine local
repository improvement: plan, implement, test, document and make scoped local
commits. Choose reasonable reversible implementation details without waiting for
an owner, parent session or another profile to approve them. This section replaces
older owner-acknowledgement and blanket main-only development requirements for
that local work; it does not override product safety or explicit task exclusions.
For approved Autowork, follow [the standing decision policy](docs/autonomy.md):
approval delegates the actions necessary to complete the accepted scope, including
publication and live execution, without repeated owner approval. Reconcile stale
owner-only labels and missing grant records from that approval through the supported
task commands; do not bypass runtime guards or infer approval from queue placement.

- Read the current task and repository state. Repair attributable task metadata,
  links and missing backlog structure from source evidence; preserve existing
  decisions and never invent acceptance, ownership release or completed checks.
- If no task is runnable, inspect implementation, tests, docs and UI/accessibility
  for a concrete improvement. Record a bounded task with acceptance criteria and
  dependencies, then execute it. Keep a few independent ready tasks when evidence
  supports them; do not manufacture busywork or count planning as implementation.
- Separate offline implementation and tests from device, production and other
  live qualification. Complete the local task while retaining an explicit pending
  live task; never mark the combined feature qualified from offline evidence.
- Use supported isolated task branches/worktrees when needed. Keep one writer per
  workspace. A historical ACTIVE claim alone is not a permanent veto: check actual
  worker/session activity and candidate changes. Preserve prior work; adopt an
  idle candidate only after verifying it is no longer being written. If activity
  cannot be established, select non-overlapping work instead of guessing.
- The current Autowork coordinator may review and integrate its verified local
  changes into canonical main without a separate parent/owner acknowledgement.
  Serialize canonical writes, inspect fresh status, preserve unrelated dirty
  work, and use the supported integration path. Do not bypass runtime guards,
  repin evidence to hide drift, force-push, reset or discard another writer's work.
- After a repeated blocker, take a different concrete action in the same run:
  repair the local cause, execute independent work, or report one precise external
  input that is genuinely unavailable. Do not repeatedly audit the same hold.
- Run checks proportional to the change. Commit only attributable, verified work.
  Report task ID/title, actual changes, checks, commit, next task and exact remaining
  blocker. Distinguish local commit, integration, push and live acceptance.
- Approved scope, not a repeated permission ceremony, governs execution. Preserve
  explicit exclusions, paused jobs, access controls and human-only requirements.
  Missing credentials or external inputs remain real limitations; report them
  precisely and continue independent approved work. Never fabricate completion.
<!-- autowork-local-authority:end -->
