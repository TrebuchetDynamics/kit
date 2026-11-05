+++
schema = 1
id = "TOOLSET-452-3dcf8df2"
title = "Sweep stale plugin names from installation and removal docs"
short = "Fix stale plugin commands"
status = "done"
goal = "RELIABILITY-2026-10"
section = "Now"
rank = 1000
depends_on = []
touches = ["docs/onboarding.md", "docs/cross-host.md", "docs/uninstall.md", "docs/contributing.md", "docs/workflows.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Rename stage 3 left current instructions for the old Hermes plugin name and old Claude Code/Codex plugin names. Update only the reader-facing install, update, removal and namespace instructions: Hermes enables, updates and removes plugin `kit`; Claude Code installs, updates and uninstalls `kit@autowork`; Codex adds, upgrades and removes `kit@autowork-marketplace`; examples use `/kit:` and `$kit:`. Preserve marketplace names (`autowork` and `autowork-marketplace`), the legacy `plugins.entries.autowork` migration note, the runner command `/autowork`, closed task/plan history, and all safety and policy text. Do not edit manifests, code or tests. Restated 2026-11-04: the previous worker died without a commit or changes (attempt 2, cause empty); no candidate exists to retry, so this contract is restated and runs fresh from the current main."
acceptance = ["docs/onboarding.md, docs/uninstall.md and docs/contributing.md name the Hermes plugin `kit` for enable, update, disable and remove; no current instruction still uses `autowork` as the plugin name.", "docs/cross-host.md installs and manages `kit@autowork` in Claude Code and `kit@autowork-marketplace` in Codex while leaving the marketplace names unchanged; docs/workflows.md shows `/kit:` and `$kit:` prefixes.", "The focused documentation and packaging checks pass, and the current-doc guard finds no `plugins ... autowork`, plugin `autowork@...`, `/autowork:` or `$autowork:` instruction outside the migration note and historical plans."]
checks = ["python3 skills/docs-sync/scripts/docs.py check .", "python3 scripts/check.py tests/test_portable_package.py tests/test_install_menu.py tests/test_repo_docs_graphify.py", "! rg -n 'plugins (enable|disable|remove|update) autowork|plugin (install|update|uninstall|add|remove) autowork@|/autowork:|\\$autowork:' README.md docs/onboarding.md docs/cross-host.md docs/uninstall.md docs/contributing.md docs/workflows.md docs/installation.md"]
exclusions = ["No code, manifest, marketplace-name, test or installation-state change.", "No live plugin install, removal, gateway restart or profile write.", "No deletion or rewriting of historical plans, legacy settings-key migration notes or the `/autowork` runner command."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/TOOLSET-452-3dcf8df2.toml"
+++
- Sources: docs/plans/2026-11-01-rename-to-kit.md#stage-3-documentation-and-installers; README.md#claude-code; plugin.yaml
- Repo obligations triggered: docs owners are docs/onboarding.md, docs/cross-host.md, docs/uninstall.md, docs/contributing.md and docs/workflows.md; no code, manifest or generated-output obligation; docs check and packaging tests validate the current reader-facing commands.
