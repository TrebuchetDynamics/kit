# Change history

Use Git history for past changes. This repository does not keep completed-task reports or a duplicate task archive.

Current behavior and requirements are documented in [the product specification](docs/project.md), [the reference](docs/reference.md) and [the runbooks](docs/installation.md). Unfinished work belongs in GitHub Issues, with Orbi as the delivery owner. Preserved local records are recovery evidence, not an executable backlog.

Source commits, installation and live qualification are distinct; removing historical records proves none of them.

## Unreleased

- **Hermes support removed.** Kit now installs into Claude Code, Codex and Pi (through
  Pi-Bolt), plus `tx` and the Orbi CLI. The Hermes plugin, its Telegram menu policy,
  fleet setup and update bundles, `install-plugins.sh`, `install-skills.sh`,
  `plugins/` and the `install.sh` Hermes item and flags (`--hermes-home`,
  `--bundle-only`, `--no-reload`, `--yes-deps`) are gone. `./install.sh --only hermes`
  fails with "Kit no longer supports Hermes". An earlier Hermes install is left
  unchanged; see [removal](docs/uninstall.md#earlier-hermes-installs).
- **Quieter installer output.** Step contracts and helper commands print only with
  `--verbose` or `--dry-run`; the default `services` summary hides routine notes.
