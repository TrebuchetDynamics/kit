+++
schema = 1
id = "TOOLSET-450-e643cb7a"
title = "Make Hermes approvals conservative unless autonomous policy is explicit"
short = "Require explicit autonomous policy"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Needs decision"
rank = 2000
depends_on = []
touches = ["plugins/defaults.json", "Src/autowork_runtime/runtime_defaults.py", "Src/autowork_runtime/plugin.py", "Src/autowork_runtime/install/setup_preflight.py", "Src/autowork_runtime/install/setup_runtime.py", "tests/test_preflight.py", "tests/test_install_plugins.py", "tests/test_plugin.py", "tests/integration_plugin.py", "docs/installation.md", "docs/reference.md", "README.md", "CHANGELOG.md"]
resources = []
kind = "plan"
ownership = "owner"
scope = "The native Hermes plugin currently applies approvals.mode=off, destructive_slash_confirm=false, mcp_reload_confirm=false and agent.max_turns=unlimited on every load unless the profile opts out. Replace that implicit widening with two explicit policies: interactive (the conservative default) and autonomous (the current fleet values). Keep apply_runtime_defaults=false as the no-write opt-out and keep the legacy autowork settings key readable. Setup and preflight must name the effective policy; an existing profile must not silently move to the autonomous policy or lose its current opt-out. This is a security-default decision, not a request to remove Hermes hard blocks, deny rules or the runner's own gates."
acceptance = ["A fresh profile with no policy setting receives manual approvals, destructive and MCP-reload confirmations enabled, and max_turns=90; it never receives approvals.mode=off or max_turns=unlimited implicitly.", "An explicit autonomous policy applies the current fleet values, while apply_runtime_defaults=false still writes no approval, turn, injection or skill-list policy; both the canonical kit key and legacy autowork key are covered.", "Setup and preflight show the selected policy and the values it will write, and do not silently change an existing profile's approval or turn policy.", "Focused fixtures cover a fresh interactive profile, an explicit autonomous profile, an opted-out profile, a legacy-key profile and a setup preview; no live profile is changed by the offline checks."]
checks = ["python3 scripts/check.py tests/test_preflight.py tests/test_install_plugins.py tests/test_plugin.py tests/test_complete_setup.py", "python3 -m pytest -q tests/integration_plugin.py"]
exclusions = ["No live Hermes profile, gateway, plugin install or approval setting is changed by this task's offline checks.", "No removal of Hermes hard blocks, deny rules, the runner's review/publication gates or the existing opt-out.", "No npm publication, deployment or remote service change."]
+++
- Sources: docs/evaluation.md#risks; docs/installation.md#install; docs/reference.md#plugin-settings
- Question: The owner must decide whether the default Hermes approvals stance changes from implicit widening to an explicit interactive/autonomous policy. Resume condition: the owner records the security-default decision.
