+++
schema = 1
id = "TOOLSET-450-e643cb7a"
title = "Hermes approvals stay interactive unless autonomy is selected"
short = "Hermes opt-in autonomy"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Now"
rank = 5000
depends_on = []
touches = ["plugins/defaults.json", "src/autowork_runtime/runtime_defaults.py", "pi-autowork/src/autowork_runtime/runtime_defaults.py", "src/autowork_runtime/plugin.py", "pi-autowork/src/autowork_runtime/plugin.py", "src/autowork_runtime/install/setup_preflight.py", "pi-autowork/src/autowork_runtime/install/setup_preflight.py", "src/autowork_runtime/install/setup_runtime.py", "pi-autowork/src/autowork_runtime/install/setup_runtime.py", "tests/test_preflight.py", "tests/test_install_plugins.py", "tests/test_plugin.py", "tests/integration_plugin.py", "docs/installation.md", "docs/reference.md", "README.md"]
resources = ["autowork-python-layout"]
kind = "implementation"
ownership = "worker"
scope = "The native Hermes plugin currently applies approvals.mode=off, destructive_slash_confirm=false, mcp_reload_confirm=false and agent.max_turns=unlimited on every load unless the profile opts out. Replace that implicit widening with two explicit policies: interactive (the conservative default) and autonomous (the current fleet values). Keep apply_runtime_defaults=false as the no-write opt-out and keep the legacy autowork settings key readable. Setup and preflight must name the effective policy; an existing profile must not silently move to the autonomous policy or lose its current opt-out. This is a security-default decision, not a request to remove Hermes hard blocks, deny rules or the runner's own gates."
acceptance = ["A fresh profile with no policy setting receives manual approvals, destructive and MCP-reload confirmations enabled, and max_turns=90; it never receives approvals.mode=off or max_turns=unlimited implicitly.", "An explicit autonomous policy applies the current fleet values, while apply_runtime_defaults=false still writes no approval, turn, injection or skill-list policy; both the canonical kit key and legacy autowork key are covered.", "Setup and preflight show the selected policy and the values it will write, and do not silently change an existing profile's approval or turn policy.", "Focused fixtures cover a fresh interactive profile, an explicit autonomous profile, an opted-out profile, a legacy-key profile and a setup preview; no live profile is changed by the offline checks."]
checks = ["python3 scripts/check.py tests/test_preflight.py tests/test_install_plugins.py tests/test_plugin.py tests/test_complete_setup.py", "python3 -m pytest -q tests/integration_plugin.py"]
exclusions = ["No live Hermes profile, gateway, plugin install or approval setting is changed by this task's offline checks.", "No removal of Hermes hard blocks, deny rules, the runner's review/publication gates or the existing opt-out.", "No npm publication, deployment or remote service change."]
+++
- Sources: docs/evaluation.md#risks; docs/installation.md#install; docs/reference.md#plugin-settings
- Question: Resolved by the existing 2026-11-07 approval of this exact offline interactive/autonomous policy. No live profile action is requested or granted.
- Owner decision: 2026-11-07: approved
- Standing policy: Unblock reconciles the accepted worker contract, not a new security decision: creation f14f8c47, owner-only question 54b317c6, and owner answer 7e081dc18a41870c5e2b048c01f00aff552ae4ea (2026-11-07). Scope, acceptance, checks, exclusions and live denial are unchanged. Touches names the same four native modules at current and accepted relocated paths; use the existing selected-source owners, never recreate retired paths. The existing autowork-python-layout resource serializes these source writes with active relocation. CHANGELOG is coordinator-owned; update the existing in-scope product docs, not completed-task reports.
- Next action: Extend the existing profile-policy fixtures in tests/test_plugin.py and tests/test_preflight.py to fail on implicit autonomous defaults. Use the selected source owners named in Standing policy, including their relocated paths if that migration has landed.
- Execution: Implement the interactive/autonomous policy selection, then align setup, preflight and the in-scope installation/reference docs. Cover canonical and legacy settings keys, existing opt-outs and setup previews. Run every declared check in its required environment; tests/integration_plugin.py needs the optional Hermes loader and is not proved by an offline-suite exclusion. Do not change a live profile.
