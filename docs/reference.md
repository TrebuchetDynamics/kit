# Command and configuration reference

Exact entry points, flags, settings and environment variables this bundle reads.
Each entry names its source of truth; when they disagree, the source wins and this
page has drifted. Conversational workflow commands (`/docs_sync`,
`/plan_with_me` and the rest) are listed in [workflows](workflows.md#commands);
procedures and their side effects are in [installation](installation.md).

[`/git-commit-push`](../skills/git-commit-push/SKILL.md) commits the current branch,
syncs and pushes its verified upstream by default; `pull`/`sync`/`merge` only integrates.
[`/push`](../skills/push/SKILL.md) saves eligible changes in the Git-identified
invoking checkout only, pulls verified `main` and delivers through the allowed main
route. Other worktrees are not inspected, saved or integrated; the receipt states
that local scope. Remote issue/PR coverage, ownership and delivery gates remain.
Explicit `/git-commit-push all` retains the [worktree sweep](../skills/git-commit-push/references/worktree-sweep.md).

Kit maintenance uses `hermes kit`. Planning saves GitHub Issues; Orbi owns delivery.
See the [support boundary](github-native.md#support-boundary).

## Terminal: `hermes kit`

Source: [`scripts/bundle.py`](../scripts/bundle.py) `setup_parser` and `handle_cli`. Add `-p PROFILE`
after `hermes` to run from a named profile; `setup` and `update` still target every
live profile under the same Hermes root. If another plugin owns the `kit` CLI
command, Kit logs `Skipping hermes kit: CLI command already exists (owner: NAME).`
and leaves that owner unchanged. Resolve the collision with that plugin's owner;
do not force a takeover or use the retired command.

| Command | Flags | Effect |
| --- | --- | --- |
| `hermes kit doctor` | `--json`; `--core` (alias `--bundle-only`) | Reports plugin load and command/skill registration, and lists profiles linked to a working checkout (`linked_profiles`; never a failure). Exit 1 unless `status` is `ready`. `--core` ignores external integration gaps. |
| `hermes kit setup` | `--dry-run`, `--yes-deps`, `--bundle-only`, `--no-reload`, `--hermes-home ROOT` | Runs [`scripts/setup_bundle.py`](../scripts/setup_bundle.py): installs sources in [`plugins/PLUGINS.md`](../plugins/PLUGINS.md), applies [defaults](../plugins/defaults.json), finalizes every live profile. |
| `hermes kit update` | `--check`, `--hermes-home ROOT` | Runs [`scripts/update_bundle.py`](../scripts/update_bundle.py) and waits: fast-forward-only update of every live profile. `--check` fetches and previews only. |
| `hermes kit pin NAME` | `--dry-run`, `--unpin`, `--hermes-home ROOT` | Replaces one profile's plugin link with a clone at the same revision, saving the link; `--unpin` restores it. See [linked profiles](installation.md#linked-profiles-and-pinned-clones). |
| `hermes kit finalize` | `--hermes-home ROOT` (required), `--bundle-only`, `--no-reload` | Verifies one profile's registrations and runtime settings and refreshes gateway commands; setup calls it per profile. |

`setup` flags:

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Preview target profiles and actions without writing. CLI startup can still apply runtime defaults; see [installation](installation.md#preflight-before-fleet-writes). |
| `--yes-deps` | Consent to declared Python dependencies during native installs. |
| `--bundle-only` | Link, enable and configure only this bundle; skip external sources. |
| `--no-reload` | Defer live gateway wiring explicitly. |
| `--hermes-home ROOT` | Hermes root containing `profiles/` (default: `HERMES_HOME`, else `~/.hermes`). |

## Inventory and delivery status

Use terminal `hermes kit doctor --json` for registration and plugin diagnostics.
Use `hermes kit update` or `hermes kit update --check` for synchronous
maintenance and its printed receipt. These are not chat-output equivalents.
GitHub issue/PR evidence and read-only Orbi diagnostics own delivery status;
these reads do not activate Orbi or qualify live delivery.

## Source-checkout scripts

Run from a clone of this repository. The shell installers are thin wrappers.

| Script | Flags | Effect |
| --- | --- | --- |
| `./install.sh` | `--all`/`--full`, `--only a,b`, `--skip a,b`, `--list`, `--menu`, `--no-pull`, `--dry-run`, `--verbose`/`--quiet`, `--color auto\|always\|never`; Hermes options for the Hermes item | The suite installer ([`scripts/install_menu.py`](../scripts/install_menu.py)): Pi package, Pi-Bolt, [Orbi host refresh or CLI bootstrap](installation.md#orbi-cli), `tx`, Hermes, Claude Code, Codex. Selecting Orbi authorizes a verified Linux fleet stop/update/restart (including paused deployments); pass `--skip orbi` to opt out. Defaults to all available components with verbose output; the explicit interactive menu requires a terminal. |
| `bash install-plugins.sh` | Same as `hermes kit setup`; `--help` | Public calls, including `--help`, execute `scripts/setup_bundle.py`. The source-installer usage appears only with the internal `--sources-only --help`. |
| `bash install-skills.sh` | `--dry-run`, `--hermes-home ROOT`, `--profile-home HOME` | Runs [`scripts/install_skills.py`](../scripts/install_skills.py): copies `skills/` (except retired `repo-docs` and `repo-interview`, and support folders that document themselves with a `README.md` and have no `SKILL.md`) into the default and every existing profile, or only `--profile-home`; `--hermes-home` and `--profile-home` are mutually exclusive. Does not overwrite existing skill contents; a reference-only source container retires a legacy installed `SKILL.md` while keeping the other files. Never changes configuration. |
| `python3 scripts/update_bundle.py` | `--hermes-home ROOT` (required), `--check`, `--dry-run`, `--profile NAME` (repeatable with `--source`), `--source CHECKOUT`, `--revision SHA`, `--native-python PATH`, `--cancel-scoped SHA256` | Cancel an exact unpublished scoped receipt (with `--check` to preview), or all-profile update, or with `--profile`, `--source`, `--revision` and `--native-python` (all four required) a scoped deployment of a reviewed local commit; see [installation](installation.md#deploy-an-exact-local-revision-to-selected-profiles). |
| `python3 scripts/install-graphify.py` | `--hermes-home ROOT`, `--profile NAME` (both required), `--dry-run` | Installs Graphify's Hermes skill into selected existing profiles; installs the `graphifyy` tool with `uv tool install` when missing. |
| `python3 scripts/check.py` | `--list`, `--timeout SECONDS` (default 1800 per test process) | Runs the offline test inventory; see [testing](testing.md). |

During the [Orbi refresh](installation.md#orbi-cli), the installer lists an
account as `not checked` without failing the refresh only when it cannot list the
account's user unit folders due to permissions, finds no readable Orbi evidence,
and verifies that the account has neither a running manager nor a linger marker.
Unverifiable linger state still holds the refresh for an unreadable account.

## Repository helpers used by workflows

These ship inside the bundle and are run by skills against your project. Paths are
relative to this repository.

| Helper | Commands | Reference |
| --- | --- | --- |
| [`skills/update-kit/scripts/update_kit.py`](../skills/update-kit/scripts/update_kit.py) | No argument: refresh fixed upstream `main` and run `install.sh update --no-pull`; `--only`, `--skip`, `--all`/`--full`, verbosity/color and explicit Hermes options; `--dry-run`/`--read-only`/`--questions-only`/`--list`: no-write/no-probe preview | Python 3.11+, Git/bash/lsof, Linux/macOS; resolve from loaded skill resources, not cwd; [persistent source, restrictions and receipts](installation.md#update-kit) |
| [`skills/docs-sync/scripts/docs.py`](../skills/docs-sync/scripts/docs.py) | `validate`, `check`, `stale`, `profiles` | `docs.py --help`; [role manifest](../skills/docs-sync/references/document-scaffold.md#optional-role-manifest) |
| [`skills/orbi/scripts/orbi_control.py`](../skills/orbi/scripts/orbi_control.py) | `status all [--json]` (read-only observable local host inventory; no repo/config selectors, checkout or GitHub auth; partial coverage retained), `status` (default), `version` (read-only selected deployment release/revision and verification evidence on Linux/macOS; no bootstrap, scheduler or network probes), `setup`, `start` (prepare if absent, then activate), `update` (newest official release for one inactive deployment, then unit refresh), `stop`, `prune [--apply]` (preview/remove stale unloaded Linux user unit templates; no repo/config selectors), `help` (read-only, needs no repository); `--repo-dir`, `--config`, `--dry-run`, `--json`; new preparation: `--harness {pi-bolt,pi}`, complete `--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]`; `--resume-setup` is helper setup-only. This is direct helper syntax: public `/orbi setup` maps to `start`; public `setup --prepare-only` maps to helper `setup` and consumes `--prepare-only`; public resume requires `setup --prepare-only --resume-setup` before any mutation | Python 3.11+; [lifecycle and safety boundaries](../skills/orbi/references/lifecycle.md) |

## Removed executor helpers

Use [GitHub issue publication](github-native.md#publish-a-planning-batch)
and the repository's focused test commands directly. Preserve existing task and runtime state.

## Hermes install identity

Fresh setup and native registration probes use `plugins/kit` and enable `kit`.
Setup adopts only Kit from the selected source. Duplicate slots (even aliases),
foreign sources and uncertain manifests refuse mutation with path diagnostics.
No runtime state relocation, credential copy or permission reset is required; source
delivery is not installed adoption or live activation. See [setup/recovery](installation.md#install).

## Plugin settings

Source: [`scripts/runtime_defaults.py`](../scripts/runtime_defaults.py),
[`plugins/defaults.json`](../plugins/defaults.json). Set them per profile with
`hermes -p PROFILE config set KEY VALUE`.

| Key | Default | Meaning |
| --- | --- | --- |
| `plugins.entries.kit.settings.apply_runtime_defaults` | `true` | Boolean `false` skips approval, turn, injection and skill-list policy in plugin loading and setup, regardless of `runtime_policy`. Telegram menu maintenance still applies. It does not undo prior changes; set it before restoring your own values. |
| `plugins.entries.kit.settings.runtime_policy` | `interactive` | `interactive` or `autonomous`; other values are rejected. Explicit selection reapplies the policy on every load. When absent, existing approval/turn values are preserved and only missing values get interactive defaults. Setup/preflight show the selected policy and effective values without selecting autonomy. |

While `apply_runtime_defaults` is not `false`, approval/turn values are:

| Key | Interactive | Explicit autonomous |
| --- | --- | --- |
| `approvals.mode` | `manual` | `off` |
| `approvals.destructive_slash_confirm` | `true` | `false` |
| `approvals.mcp_reload_confirm` | `true` | `false` |
| `agent.max_turns` | `90` | `unlimited` (no per-turn iteration cap) |

Without explicit selection, existing values in these four keys are left unchanged.
Other settings are preserved, including deny rules. Hermes hard blocks and runner
gates remain in effect under either policy. Both policies also apply:

| Key | Value written |
| --- | --- |
| `plugins.entries.kit.allow_gateway_injection` | `true` |
| `skills.disabled` | Your entries preserved; bundled toolset skills removed |
| `platforms.telegram.extra.command_menu.priority` | Your entries first, then the workflow commands and the `ui_taste`, `beautify_github_readme`, `impeccable`, `lgtm` and `git_commit_push` skill commands appended; retired bundle names and `autoresearch_*` entries removed. Other menu settings such as the mode and cap are not changed ([`scripts/telegram_menu_policy.py`](../scripts/telegram_menu_policy.py)). |

Every setup, including `--bundle-only`, also clears the per-platform skill disable
lists, except in opted-out profiles. Existing memory providers and their settings
are preserved. See [installation](installation.md#install) for the policy and
[removal](uninstall.md) to restore values.

## Environment variables

| Variable | Read by | Meaning |
| --- | --- | --- |
| `HERMES_HOME` | Setup, skill installer, `install-plugins.sh` | Default Hermes root when `--hermes-home` is absent. A named-profile home (`ROOT/profiles/NAME`) resolves to `ROOT`. Defaults to `~/.hermes`. `hermes kit update` resolves the profile's Hermes root the same way. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_HOME_CHANNEL` | Update menu healing, from each profile's `.env` (not the process environment) | For each distinct bot token, the chats whose leftover command lists the updater checks; see [installation](installation.md#update-all-profiles). |

## Files and state

| Path | Owner | Contents |
| --- | --- | --- |
| `ROOT/maintenance/toolset-update/latest.json` | Updater | Latest update receipt: status, revisions, profiles, local edits, backup location, and the gateway restart's state or recorded outcome (`gateway_restart`, `gateway_restart_result`). |
| `ROOT/maintenance/toolset-update/restart.json` | Updater | The last gateway restart the updater requested (process ID), or its deferred-restart waiter (process ID, latest chat-turn count), plus `covers`, the updates that restart will load; used to report progress, avoid overlapping restarts and record the outcome on each covered update. Once finished, also `finished` and the recorded `outcome`, which status shows when a later receipt replaced the covered one. |
| `ROOT/maintenance/toolset-update/pinned/NAME-*/` | `hermes kit pin` | One pin: `record.json` (profile, link, target, revision), the saved `link`, and after unpinning the kept clone (`unpinned-*`). |
| `ROOT/maintenance/toolset-update/run.log` | Updater | Gateway restarts requested by the updater; `hermes kit update` prints update output and its receipt to the terminal. |
| `tasks/items/`, `tasks/goals/`, `tasks/evidence/` (project) | Preserved legacy evidence | Read-only migration inputs, not a second queue; do not delete during removal. |
| `docs/roles.json` (project, optional) | Docs Sync | Document role manifest. |
