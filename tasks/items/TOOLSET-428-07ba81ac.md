+++
schema = 1
id = "TOOLSET-428-07ba81ac"
title = "Kit rename stage 1: dual-read the plugin settings key"
short = "Dual-read the settings key"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 1000
depends_on = []
touches = ["Src/autowork_runtime/plugin.py", "Src/autowork_runtime/install/setup_preflight.py", "Src/autowork_runtime/runtime_defaults.py", "tests/test_preflight.py", "tests/test_complete_setup.py", "docs/plans/2026-11-01-rename-to-kit.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "First stage of docs/plans/2026-11-01-rename-to-kit.md. Add one canonical plugin-name constant with its legacy value, write settings under plugins.entries.kit, and read either key at every point that consults plugins.entries.autowork today: the gateway-injection check in plugin.py, the policy comparison in setup_preflight.py, the runtime-defaults opt-out and the load-time policy application. Writes use the new key only; a profile that carries both reports the drift once and keeps its existing value. Do not rename the plugin, the namespace, the runner or any path in this stage."
acceptance = ["A profile configured only under plugins.entries.autowork keeps its approvals mode, menu priority and opt-out after the change; a profile with the new key wins when both exist; a profile with neither gets today's defaults; each case has a test through the real settings reader.", "No code path reads only the legacy key, and every write targets plugins.entries.kit. The stage is revertible by one commit: removing the new key restores the legacy read as authoritative.", "Affected suites pass: preflight, complete_setup, plugin, bundle, runtime-defaults behaviour and the setup fixtures. No plugin, namespace, runner, state-directory or documentation rename happens here."]
checks = ["python3 scripts/check.py tests/test_preflight.py tests/test_complete_setup.py tests/test_plugin.py tests/test_bundle.py"]
exclusions = ["No plugin.yaml, package.json, marketplace, adapter-namespace or documentation rename; no runner, CLI or state-path rename; no live profile write; no publication."]
+++
