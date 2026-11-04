+++
schema = 1
id = "TOOLSET-444-766cb4ce"
title = "Grant plugin authority from a default policy file and show it in a Settings screen"
short = "Default policy file and Settings"
status = "done"
goal = "PASEO-PLUGIN"
section = "Now"
rank = 2000
depends_on = ["TOOLSET-443-41644eec"]
touches = ["integrations/paseo/server/config.ts", "integrations/paseo/shared/contracts.ts", "integrations/paseo/client", "integrations/paseo/index.client.tsx"]
resources = []
kind = "implementation"
ownership = "owner"
scope = "Load the operator policy from ~/.config/paseo-autowork/policy.json (XDG_CONFIG_HOME honored, mode 0600) when PASEO_AUTOWORK_CONFIG is unset. Extend the policy with grants for task verbs, task-store commits, runner maintenance and planning. Add a Paseo Settings screen that shows the effective grants, the policy path and the executable. No client toggle grants authority."
acceptance = ["A 0600 policy file at the default path is loaded without an environment variable; a world-writable or symlinked file is refused.", "The fleet RPC reports every grant kind and the Settings screen renders them read-only.", "Tests cover the default path, the refusals and the settings registration."]
checks = ["npm --prefix integrations/paseo run check"]
exclusions = []
closure = "manual"
closure_actor = "interactive Claude Code session"
closure_timestamp = "2026-11-03T05:11:29.407046+00:00"
closure_reason = "default policy path with private-file rule, all/selective grants, Settings screen; server tests for the default path and refusals, client test for the read-only settings screen (commit 538c3459)"
closure_evidence = "integrations/paseo/tests/server.test.ts"
+++
