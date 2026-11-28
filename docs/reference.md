# Command and configuration reference

Exact entry points, flags, settings and environment variables Kit reads.
Each entry names its source of truth; when they disagree, the source wins and this
page has drifted. Conversational workflow commands (`/docs-sync`,
`/plan-with-me` and the rest) are listed in [workflows](workflows.md#commands);
procedures and their side effects are in [installation](installation.md).

[`/git-commit-push`](../skills/git-commit-push/SKILL.md) commits the current branch,
syncs and pushes its verified upstream by default; `pull`/`sync`/`merge` only integrates.
[`/push`](../skills/push/SKILL.md) saves eligible changes in the Git-identified
invoking checkout only, pulls verified `main` and delivers through the allowed main
route. Other worktrees are not inspected, saved or integrated; the receipt states
that local scope. Remote issue/PR coverage, ownership and delivery gates remain.
Explicit `/git-commit-push all` retains the [worktree sweep](../skills/git-commit-push/references/worktree-sweep.md).

Kit maintenance uses `./install.sh` and `/update-kit`. Planning saves GitHub Issues;
Orbi owns delivery. See the [support boundary](github-native.md#support-boundary).

## Inventory and delivery status

Use `./install.sh --list` to see which components are available, and
`./install.sh --dry-run` to preview a refresh. GitHub issue/PR evidence and read-only Orbi diagnostics own delivery status;
these reads do not activate Orbi or qualify live delivery.

## Source-checkout scripts

Run from a clone of this repository.

| Script | Flags | Effect |
| --- | --- | --- |
| `./install.sh` | `--all`/`--full`, `--only a,b`, `--skip a,b`, `--list`, `--menu`, `--no-pull`, `--dry-run`, `--verbose`/`--quiet`, `--color auto\|always\|never` | The suite installer ([`scripts/install_menu.py`](../scripts/install_menu.py)): Pi package, Pi-Bolt, [Orbi host refresh or CLI install](installation.md#orbi-cli), `tx`, Claude Code, Codex. Selecting Orbi authorizes a verified Linux fleet stop/update/restart (including paused deployments); pass `--skip orbi` to opt out. Defaults to all available components with live progress; `--verbose` adds step contracts, helper commands, every service decision and completed Orbi deployment steps; the explicit interactive menu requires a terminal. |
| `python3 scripts/check.py` | `--list`, `--timeout SECONDS` (default 1800 per test process) | Runs the offline test inventory; see [testing](testing.md). |

During the [Orbi refresh](installation.md#orbi-cli), the installer lists an
account as `not checked` without failing the refresh only when it cannot list the
account's user unit folders due to permissions, finds no readable Orbi evidence,
and verifies that the account has neither a running manager nor a linger marker.
Unverifiable linger state still holds the refresh for an unreadable account.

## Repository helpers used by workflows

These ship inside Kit and are run by skills against your project. Paths are
relative to this repository.

| Helper | Commands | Reference |
| --- | --- | --- |
| [`skills/update-kit/scripts/update_kit.py`](../skills/update-kit/scripts/update_kit.py) | No argument: refresh fixed upstream `main` and run `install.sh update --no-pull`; `--only`, `--skip`, `--all`/`--full` and verbosity/color; `--dry-run`/`--read-only`/`--questions-only`/`--list`: no-write/no-probe preview | Python 3.11+, Git/bash/lsof, Linux/macOS; resolve from loaded skill resources, not cwd; [persistent source, restrictions and receipts](installation.md#update-kit) |
| [`skills/docs-sync/scripts/docs.py`](../skills/docs-sync/scripts/docs.py) | `validate`, `check`, `stale`, `profiles` | `docs.py --help`; [role manifest](../skills/docs-sync/references/document-scaffold.md#optional-role-manifest) |
| [`skills/orbi/scripts/orbi_control.py`](../skills/orbi/scripts/orbi_control.py) | `status all [--work] [--verbose\|--json]` (read-only local deployment inventory and GitHub API budget; opt-in per-repo issue counts; no repo/config selectors or checkout; partial coverage retained), `status` (default; includes deployment worktree disk use), `version` (read-only selected deployment release/revision and verification evidence on Linux/macOS; no bootstrap, scheduler or network probes), `setup`, `start` (prepare if absent, then activate), `update [--wait]` (newest official release after verified inactivity, then unit refresh; `--wait` lets workers finish without interruption), [`update all [--wait-minutes MINUTES]`](../skills/orbi/references/lifecycle.md#fleet-update) (discover local deployments, wait without stopping workers, preserve scheduling), `stop`, `prune [--apply]` (preview/remove verified finished task worktrees and stale unloaded Linux user unit templates; no repo/config selectors), `help` (read-only, needs no repository); `--repo-dir`, `--config`, `--dry-run`, `--json`; new preparation: `--harness {pi-bolt,pi}`, complete `--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]`; `--resume-setup` is helper setup-only. This is direct helper syntax: public `/orbi setup` maps to `start`; public `setup --prepare-only` maps to helper `setup` and consumes `--prepare-only`; public resume requires `setup --prepare-only --resume-setup` before any mutation | Python 3.11+; [lifecycle and safety boundaries](../skills/orbi/references/lifecycle.md) |

## Removed executor helpers

Use [GitHub issue publication](github-native.md#publish-a-planning-batch)
and the repository's focused test commands directly. Preserve existing task and runtime state.

## Files and state

| Path | Owner | Contents |
| --- | --- | --- |
| `tasks/items/`, `tasks/goals/`, `tasks/evidence/` (project) | Preserved legacy evidence | Read-only migration inputs, not a second queue; do not delete during removal. |
| `docs/roles.json` (project, optional) | Docs Sync | Document role manifest. |
