# Rename the toolset to Kit

## Decision

The owner chose **kit** as the toolset name. Spanish treats *kit* as native
("kit de herramientas"), it is one syllable on a command line, and it stops the
repository from being named after one of its own tools.

`autowork` keeps its name. It is the runner and its skill, not the suite: **Kit** is
the toolset, and **autowork** is the tool inside it.

## Target identity

| Surface | Before | After |
| --- | --- | --- |
| Repository | `TrebuchetDynamics/autowork` | `TrebuchetDynamics/kit` |
| Hermes plugin name (`plugin.yaml`) | `autowork` | `kit` |
| Plugin namespace, all hosts | `autowork:plan-with-me` | `kit:plan-with-me` |
| Claude Code commands | `/autowork:plan-with-me` | `/kit:plan-with-me` |
| Codex commands | `$autowork:plan-with-me` | `$kit:plan-with-me` |
| npm package | `autowork` | `@trebuchet/kit` (plain `kit` is taken) |
| Hermes settings key | `plugins.entries.autowork` | `plugins.entries.kit` |
| Runner CLI | `autowork start` | unchanged |
| Runner skill | `/autowork` | unchanged |
| Internal paths | `pi-autowork/`, `~/.local/state/pi-autowork/` | unchanged |
| Pi commands | `/plan-with-me` (unprefixed) | unchanged |

Verified before choosing the name: npm `kit` is v2.0.31 (a TypeScript utility library)
and PyPI `kit` is v0.2.15 (a Flask integration framework), so publishing needs a scope.
GitHub is org-scoped and needs none.

## Why the stages exist

`plugin.yaml` name, the `autowork:` namespace and `plugins.entries.autowork` are read
in three different ways:

- `update_bundle.py` validates the manifest name with a regex and refuses an
  unexpected one, so the manifest rename and the updater change must land together.
- Every host adapter and most tests spell the namespace `autowork:<skill>` in
  `skill_view`, `/autowork:...` and `$autowork:...` strings.
- The settings key is per-profile live state. Renaming the key without a compatible
  read makes every existing profile silently lose approvals mode, menu priority and
  its external-plugin policy, which is exactly the wound the 0.3.0
  `hermes-toolset → autowork` rename left open.

So the order is: compatibility first, identity second, prose last.

## Stage 1: dual-read settings key

- Add one constant pair (`PLUGIN`, `LEGACY_PLUGIN`) in the runtime module that already
  owns defaults, and read the new key with a fallback to the old one everywhere
  `plugins.entries.autowork` is consulted: `plugin.py` gateway-injection check,
  `setup_preflight.py` policy comparison, `runtime_defaults.py` opt-out, and the
  load-time policy application.
- Writes go to the new key only; reads accept either; a profile that has both keeps
  its existing value and reports the drift once.
- Tests: a profile configured under `plugins.entries.autowork` keeps its approvals,
  menu priority and opt-out after the rename; a profile with the new key wins when
  both exist; a profile with neither gets today's defaults.
- **Pass when:** the three fixtures pass and no code path reads only the old key.
- **Landed:** `runtime_defaults.PLUGIN` is `kit` and `LEGACY_PLUGIN` keeps
  `autowork`; the runtime, setup preflight, installer defaults and gateway-injection
  report read either entry per key (canonical values win, legacy values fill keys the
  canonical entry lacks). Settings are written under `plugins.entries.kit`; while the
  plugin is still named `autowork`, `allow_gateway_injection` is mirrored to the legacy
  entry Hermes actually reads, and the diagnostic names that entry.

## Stage 2: plugin identity and namespace

- `plugin.yaml` name, `package.json` name `@trebuchet/kit`,
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `.agents/plugins/marketplace.json`, and the `update_bundle.py` manifest regex.
- Namespace spelling across `adapters/`, the plugin command registration and every
  `skill_view(name="autowork:…")` string; Claude Code and Codex prefixes follow.
- Keep `pi-autowork/`, `Src/pi_autowork/`, the runner CLI and the state directory as
  they are.
- **Pass when:** the plugin loads under `kit`, all four hosts expose the same skill
  set, and `test_plugin`, `test_bundle`, `test_preflight`, `test_src_native`,
  `test_portable_package` and `node --test tests/portable_pi.test.mjs` pass with the
  new namespace.

## Stage 3: documentation and installers

- `README.md` first screen, `docs/installation.md`, `docs/cross-host.md`,
  `docs/workflows.md`, `docs/onboarding.md`, `docs/reference.md`, `docs/uninstall.md`,
  `docs/troubleshooting.md`, `plugins/PLUGINS.md`, `install.sh` item labels and
  `install-plugins.sh` paths.
- Add a migration note that names the old settings key and the release that drops it.
- **Pass when:** a documented install command from a clean machine resolves, and the
  repo has no prose that tells a reader to use `/autowork:` for a skill.

## Stage 4: rename and live proof

- GitHub repository rename (owner action, redirects keep old clones working). **Done:**
  the repository is `TrebuchetDynamics/kit` and the old URLs redirect.
- **No npm publication is required.** Installs come from the Git source (`install.sh`,
  `pi install git:github.com/TrebuchetDynamics/kit`, the Claude Code and Codex
  marketplaces). `package.json` keeps the scoped name `@trebuchet/kit` as local
  metadata only: no scope, deprecation notice or registry release is part of this
  rename.
- The one remaining evidence step is the pre-rename profile proof, and it is a live
  check: install the renamed plugin into a profile configured under
  `plugins.entries.autowork` and show approvals mode, menu priority and opt-out are
  unchanged. The stage 1 fixtures prove the read logic; they do not qualify a live
  profile.

## Verification that closes the rename

Not "tests pass". A pre-rename profile must be shown to keep its state. The offline
fixtures prove the read logic; only a live Hermes profile proves the migration:

1. Snapshot `plugins.entries.autowork` (approvals mode, menu priority, opt-out) in a
   fixture profile.
2. Run the renamed plugin against it.
3. Assert the effective settings are unchanged, the writes landed under
   `plugins.entries.kit`, and the old key is reported as migrated rather than ignored.

## Rollback

Stages 1 and 2 are revertible by commit: the dual read makes the old key authoritative
again if the new one is removed. Stage 3 is prose. Stage 4 is the only irreversible
step, which is why it comes last and after the verification above.

## What this plan does not cover

- Renaming the runner, its CLI, its state directory or `pi-autowork/`.
- Changing any skill's behaviour or the task store.
- Any live profile write, publish or deploy before stage 4 has its own authorization.
