# Kit repository instructions

## Decide who owns the work

- Before changing a public contract, read the [README](README.md) and [product scope](docs/project.md).
- GitHub Issues are the only executable backlog. Do not sync a local task store or `tasks/`.
  Ordinary issues default to `ai-ready`, regardless of author. Publish the label last, after the issue content and native `blockedBy` dependencies are complete. Owner tasks, epics and incomplete plans do not execute.
- `/plan-with-me` and `/plan-for-me` stop after issue publication. Orbi owns automatic delivery: Pi implementation, tests, PR, independent review and merge gates. Only [explicit Orbi lifecycle commands](docs/github-native.md#kit-lifecycle-skill) authorize activation after technical checks; they do not qualify live delivery. Do not activate it as part of other work.
- For issue publication or delivery, follow the [GitHub-native rules](docs/github-native.md). Preserve existing tasks, worktrees, attempts and recovery evidence; never remove an active attempt or its recovery inputs. Reconcile still-required outcomes into GitHub Issues.
- For accepted implementation, the [standing decision policy](docs/autonomy.md) permits reversible changes and scoped commits. Retained fix/apply modes keep their ownership, review and PR gates. Respect exclusions, pauses, access controls and human-only gates. Leave service configuration, schedules, profiles and other live state alone unless explicitly in scope.

## Choose the checkout

- Keep one writer per checkout. Interactive sessions use the main checkout one at a time. A second writer uses a worktree. Delivery workers and parallel delegated agents may use worktrees.
- Resolve the canonical checkout with `git worktree list --porcelain`. Create task worktrees under `<canonical-repo>/.worktrees/<task>/`, never in sibling `<repo>-<task>` or `.claude/worktrees/` directories. Follow [worktree placement](docs/worktree-placement.md) for hook and ownership rules.
- Give each dispatched subagent a fresh context window, scope, completion criterion and explicit write permission or read-only limit.
- Preserve unrelated changes and other workers’ files. Commit only your own verified work. Never force-push, reset, rewrite history or discard recovery state. Keep credentials, private identities and runtime state out of Git.

## Edit the owning source

- **Skills:** Start with `skills/<name>/SKILL.md`. Read the [contributing guide](docs/contributing.md), [skill standard](docs/skill-standard.md), adapter, references and tests. Every public skill links the shared [Ponytail method](skills/shared/PONYTAIL.md) and [communication rules](skills/shared/COMMUNICATION.md).
- **Hosts:** `adapters/skills/` serves portable hosts. `adapters/pi.mjs` dispatches Pi commands. Claude Code and Codex use `.claude-plugin/` and `.codex-plugin/`, respectively. Check [host limits](docs/cross-host.md) before claiming parity.
- **Packaging:** `files` in `package.json` defines the shipped inventory. Add a path only if existing entries do not cover it. Test the actual portable package.
- **Documentation:** Use the [reference](docs/reference.md) and [workflows](docs/workflows.md) for commands and configuration.
- **Instruction maintenance:** When accepted work changes a documented command, source-of-truth path, architectural boundary or durable convention, update only the affected guidance in the same PR. If no guidance is affected, make no instruction edit. Follow the [maintenance procedure](skills/shared/AGENT-INSTRUCTIONS.md).
- Document current behavior. Git history is the record of past work. Do not create completed-task tables, archives or `TODO.archive.md`.

## Verify and report

Run `python3 scripts/affected_tests.py --run` for affected checks. Test only what the change can affect. CI runs the full offline suite on pull requests and pushes to `main` or tags; do not repeat whole suites or directories locally for a focused change. The default pre-push hook checks the pushed revision and core contracts. For test selection, environments, hook setup, opt-in checks and bypass controls, read [testing](docs/testing.md).

Report what changed, what ran and which live, device, production or human gates remain. Distinguish commit, integration, push, installation and live acceptance. Offline, registration and native checks do not prove model output, live messaging or Orbi delivery. If a blocker repeats, repair its cause, continue independent accepted work or name the exact missing external input.
