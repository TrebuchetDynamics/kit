# Repository agent instructions

Kit ships planning skills for Pi, Claude Code and Codex, with optional Hermes
integration. It researches, decides and decomposes; **GitHub Issues** own the
executable backlog and **Orbi** owns delivery (Pi → tests → PR → independent
review → merge gates). Read [README.md](README.md) and
[docs/project.md](docs/project.md) before changing a public contract.

## Authority

- GitHub Issues are the only executable backlog. All issues default to
  `ai-ready`, regardless of author; publish that label last, after complete
  content and native `blockedBy` dependencies exist. Epics and incomplete
  planning do not execute. There is no local task store and no `tasks/` sync.
- `/plan-with-me` and `/plan-for-me` publish GitHub Issues and stop. Retained
  fix/apply modes keep their own accepted scope and shared ownership/review/PR gates.
- `pi-autowork` (executor, CLI, Paseo plugin) is retired, unsupported and
  removed. Do not develop, repair, restore, install or restart it. Preserve
  existing tasks, worktrees, attempts and recovery evidence; never remove an active
  attempt or its recovery inputs. Reconcile still-required outcomes into
  GitHub Issues. Orbi stays paused and
  live-unqualified — do not enable it as part of other work.
- Accepted scope authorizes reversible implementation and scoped commits under
  [the standing decision policy](docs/autonomy.md). Explicit exclusions,
  pauses, access controls and human-only gates still apply.

## Checks

```sh
python3 scripts/check.py                  # full offline inventory (provisions CPython 3.12 + uv)
python3 scripts/check.py --list           # what the inventory covers
python3 scripts/check.py tests/native --shard 1/3
python3 scripts/affected_tests.py --run   # only tests your change can affect
```

- Test only what the change can affect. `scripts/check.py` runs the safe offline
  inventory; CI runs the full suite on every push, so a focused change does not
  need a local full run. Do not rerun whole test directories "to be safe".
- The pre-push hook (`python3 scripts/pre_push_check.py --install`, once per
  clone) runs core contracts plus targeted affected tests and defers whole-suite
  selections to CI. `KIT_PRE_PUSH=0` or `git push --no-verify` skips it.
- Pi adapter tests need Node 22: `node --test tests/portable_pi.test.mjs`.
- Offline, registration and native checks prove boundaries, not model output,
  live messaging or Orbi delivery. Keep unproven live gates visible instead of
  reporting them as passing.

## Where contracts live

| Concern | Source of truth |
| --- | --- |
| Product scope, host support | [docs/project.md](docs/project.md) |
| Issue publication, Orbi gates | [docs/github-native.md](docs/github-native.md) |
| Skill authoring and review | [docs/contributing.md](docs/contributing.md), [docs/skill-standard.md](docs/skill-standard.md) |
| Commands and configuration | [docs/reference.md](docs/reference.md), [docs/workflows.md](docs/workflows.md) |
| Testing and host limits | [docs/testing.md](docs/testing.md), [docs/cross-host.md](docs/cross-host.md) |

- `skills/<name>/SKILL.md` is canonical. Portable hosts use
  `adapters/skills/`; Pi command dispatch is `adapters/pi.mjs`; Claude Code and
  Codex use `.claude-plugin/` and `.codex-plugin/`; Hermes uses `plugin.yaml`.
- A skill edit usually needs its adapter, references and the tests that read
  them. Every public skill links the shared
  [Ponytail method](skills/shared/PONYTAIL.md) and
  [communication rules](skills/shared/COMMUNICATION.md).
- `package.json` `files` decides what the Pi package ships. Add new shipped
  paths there and cover them in the portable-package tests.
- Documentation states current behavior. Git history is the record of past work:
  do not create completed-task tables, archives or `TODO.archive.md`.

## Working rules

- Keep one writer per checkout. Interactive sessions use the main checkout one
  at a time; a second session uses a worktree. Delivery workers and parallel
  delegated agents may also use worktrees.
- Create task worktrees under `<canonical-repo>/.worktrees/<task>/` (resolve the
  canonical checkout from `git worktree list --porcelain`). Never create sibling
  `<repo>-<task>` directories or `.claude/worktrees/`. In Claude Code use
  `EnterWorktree` so the user hook enforces placement. See
  [docs/worktree-placement.md](docs/worktree-placement.md).
- Start dispatched subagents in a fresh context window and state scope,
  completion criterion and write permission; a read-only review stays read-only.
- Preserve unrelated changes and other workers' files; commit only your own
  attributable, verified work. Never force-push, reset, rewrite histories or
  discard recovery state. Keep credentials, private identities and runtime
  state out of Git. Do not edit or patch upstream Hermes Agent.
- Leave service configuration, schedules, profiles and other live state alone
  unless the accepted task explicitly covers them.

## Reporting

State what changed, which checks ran, and what remains unverified (live,
device, production or human gates). Separate commit, integration, push,
installation and live acceptance. After a repeated blocker, repair the cause,
do independent accepted work, or name the exact missing external input.
