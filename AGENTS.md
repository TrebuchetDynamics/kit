# Repository agent instructions

Kit ships planning skills for Pi, Claude Code and Codex, with optional Hermes
integration. **GitHub Issues** own the executable backlog; **Orbi** owns delivery
(Pi → tests → PR → independent review → merge gates).

## Scope and authority

- Before changing a public contract, read [README.md](README.md) and
  [product scope](docs/project.md).
- All issues default to `ai-ready`, regardless of author. Publish that label last,
  after complete content and native `blockedBy` dependencies exist. Epics and
  incomplete planning do not execute. There is no local task store or `tasks/` sync.
- `/plan-with-me` and `/plan-for-me` publish GitHub Issues and stop. Retained
  fix/apply modes keep their accepted scope and shared ownership/review/PR gates.
- Preserve existing tasks, worktrees, attempts and recovery evidence;
  never remove an active attempt or its recovery inputs. Reconcile still-required outcomes into
  GitHub Issues. Orbi stays paused and live-unqualified; do not enable it as part
  of other work. For publication and delivery, read [GitHub-native rules](docs/github-native.md).
- Accepted scope authorizes reversible implementation and scoped commits under
  [the standing decision policy](docs/autonomy.md). Explicit exclusions, pauses,
  access controls and human-only gates still apply.

## Source owners

- `skills/<name>/SKILL.md` is canonical; `adapters/skills/` serves portable hosts.
  Pi dispatch is `adapters/pi.mjs`; Claude Code and Codex use `.claude-plugin/`
  and `.codex-plugin/`; Hermes uses `plugin.yaml`.
- For a skill edit, read [contributing](docs/contributing.md) and the
  [skill standard](docs/skill-standard.md), plus its adapter, references and tests.
  Every public skill links the shared [Ponytail method](skills/shared/PONYTAIL.md)
  and [communication rules](skills/shared/COMMUNICATION.md).
- For package changes, `package.json` `files` owns the shipped inventory. Add paths
  only when not already covered, and test the actual portable package.
- For commands and configuration, use [reference](docs/reference.md) and
  [workflows](docs/workflows.md). For host limits, read [cross-host](docs/cross-host.md).
- When accepted work changes a documented command, source-of-truth path,
  architectural boundary or durable convention, follow
  [same-PR instruction maintenance](skills/shared/AGENT-INSTRUCTIONS.md).
- Documentation states current behavior. Git history is the record of past work;
  do not create completed-task tables, archives or `TODO.archive.md`.

## Workspace and changes

- Keep one writer per checkout. Interactive sessions use the main checkout one
  at a time; a second session uses a worktree. Delivery workers and parallel
  delegated agents may also use worktrees.
- Create task worktrees under `<canonical-repo>/.worktrees/<task>/`; resolve the
  canonical checkout with `git worktree list --porcelain`. Never use sibling
  `<repo>-<task>` or `.claude/worktrees/` directories. In Claude Code use
  `EnterWorktree` so the user hook enforces placement. Read
  [worktree placement](docs/worktree-placement.md) for hook and ownership mechanics.
- Start dispatched subagents in a fresh context window. State scope, completion
  criterion and write permission; a read-only review stays read-only.
- Preserve unrelated changes and other workers' files. Commit only your own
  attributable, verified work. Never force-push, reset, rewrite histories or discard
  recovery state. Keep credentials, private identities and runtime state out of Git.
  Do not edit or patch upstream Hermes Agent.
- Leave service configuration, schedules, profiles and other live state alone
  unless accepted scope explicitly covers them.

## Verification and receipt

Test only what the change can affect. CI runs the full offline suite on every push;
focused work does not need a local full run or whole-directory reruns "to be safe".
For test selection and environment details, read [testing](docs/testing.md).

```sh
python3 scripts/affected_tests.py --run   # affected checks
python3 scripts/check.py --list          # offline inventory
python3 scripts/check.py                 # full inventory; provisions CPython 3.12 + uv
python3 scripts/check.py tests/native --shard 1/3
node --test tests/portable_pi.test.mjs    # Node 22
```

The pre-push hook checks the pushed revision and core contracts; tests run in CI.
For hook installation, affected-test opt-in and bypass controls, read
[testing procedures](docs/testing.md).

Report changes, checks run and remaining live, device, production or human gates.
Separate commit, integration, push, installation and live acceptance. Offline,
registration and native checks prove boundaries, not model output, live messaging
or Orbi delivery. After a repeated blocker, repair the cause, do independent
accepted work, or name the exact missing external input.
