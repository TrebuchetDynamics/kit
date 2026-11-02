# tx architecture refactor

Status: Accepted

## Scope

Deepen `tx` without changing its commands, config format or tmux behavior. Keep one
installed `tx` file with explicit internal modules, a source-only execution guard, and
tests that can reach the modules without running `main`.

## Work

1. **Config module.** One owner for parsing, expanding, validating and atomically
   rewriting the line-preserving config. `add`, `remove`, `edit` and `doctor` become
   adapters. Commit `a6740448`.
2. **Command table.** One table owns command names, flags, handlers, summaries and
   completion policy. Dispatch, help, reserved aliases and completion read it. Commit
   `84ff8467`.
3. **Session module.** One owner for alias-to-session state and tmux calls. A fake
   tmux adapter covers list, kill, attach and status. Commit `86ee590e`.
4. **Install paths.** `install.sh --print-paths` is the one source for resolved install
   targets. `tx doctor --install` reads it instead of re-deriving defaults. Commit
   `a4c3648b`.

## Checks

```sh
python3 scripts/check.py tests/test_tx.py
```

The test file covers the source-only config seam, the command table, fake-tmux session
paths and read-only install-path output. It is offline and does not start a real tmux
session.

## Out of scope

No new commands, no sourced library files, no change to the config grammar or tmux
behavior, no push or installation. Live tmux qualification stays separate.
