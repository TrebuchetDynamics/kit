# Removal and configuration recovery

Removing a host package stops future use; it does **not** undo earlier work. The
installer has no complete transaction journal or automatic rollback command. This
page describes manual removal, not a guarantee of reversal.

Source: [suite installer](../scripts/install_menu.py).

## Portable marketplace removal and migration

Fresh Claude Code installs use `kit@kit`; Codex uses `kit@kit-marketplace`.
For intentional removal, use the original Claude scope:

```sh
claude plugin uninstall kit@kit --scope SCOPE --keep-data
claude plugin marketplace remove kit --scope SCOPE
codex plugin remove kit@kit-marketplace
codex plugin marketplace remove kit-marketplace
```

Replace `SCOPE` with the original `user`, `project` or `local` scope; managed
registrations need the administrator. Review other plugins before marketplace
removal, which can remove more than Kit. Preserve private configuration/source/data
backups and recovery evidence first. Claude `--keep-data` preserves its data
directory, not all options/secrets or transfer to another ID. No Codex keep-data or
automatic rollback guarantee is made. These commands do not undo repository work.

## Pi

Use Pi's package controls with the source Kit installed:

```sh
pi-bolt remove git:github.com/TrebuchetDynamics/kit
```

A stock Pi that shares `~/.pi/agent` sees the same removal. Removing the package
does not remove Pi-Bolt itself.

## Earlier Hermes installs

Kit no longer installs, updates or removes its former Hermes plugin. An earlier
Hermes install is left as it was. To remove it, use Hermes' own plugin commands
for each profile, after stopping work that depends on it, and keep private backups
of each profile's configuration first. Kit's former setup may have changed approval,
turn, skill-list and menu settings; restore only the values you backed up.

## Skills, integrations and memories remain separate

- Graphify and external skills are separate installations. A previously
  installed external Ponytail plugin also remains separate; the current pinned
  Ponytail skill suite is bundled with Kit.
  Do not remove one merely because Kit is gone; other workflows may use it.
- Select your intended memory provider before removing an active provider plugin.
  Removing a plugin is not erasure of its memory store, a migration, or deletion
  from backups. See [memory](memory.md) for inspection and retention limitations.
- Removing Kit does not stop or remove Orbi deployments; use the
  [Orbi lifecycle](github-native.md) for those.
