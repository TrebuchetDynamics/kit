+++
schema = 1
id = "TOOLSET-443-41644eec"
title = "Move the Paseo plugin into integrations/paseo with its history"
short = "Import Paseo plugin into kit"
status = "done"
goal = "PASEO-PLUGIN"
section = "Now"
rank = 1000
depends_on = []
touches = ["integrations/paseo", ".gitignore", "package.json", "scripts/check.py", ".github/workflows/paseo.yml", "README.md", "docs/testing.md"]
resources = []
kind = "implementation"
ownership = "owner"
scope = "Import the private paseo-autowork repository's main branch into integrations/paseo/ with git subtree so its history is kept. Ignore node_modules, add the directory to the Pi package files, register the plugin check in scripts/check.py as an optional Node check, restore the paseo.yml workflow, cut the kit README and docs/testing.md over to the new path, drop the private-repository claim from the plugin README, remove the stale .worktrees/paseo-migration directory, and repoint the local Paseo daemon at the kit path."
acceptance = ["integrations/paseo holds the plugin with its commit history and npm run check passes there.", "python3 scripts/check.py --list reports the plugin check or its skip reason.", "The kit README names integrations/paseo as the install path and no document claims a private plugin repository.", "paseo plugin ls reports paseo-autowork running from the kit path."]
checks = ["npm --prefix integrations/paseo run check", "python3 scripts/check.py --list"]
exclusions = []
closure = "manual"
closure_actor = "interactive Claude Code session"
closure_timestamp = "2026-11-03T05:11:28.636085+00:00"
closure_reason = "git subtree import a452b909 and cutover 09fbb10a; npm run check passed in integrations/paseo; scripts/check.py --list reports the plugin check; paseo plugin ls reports paseo-autowork running from the kit checkout's integrations/paseo"
closure_evidence = "integrations/paseo/docs/qualification.md#management-surface-2026-11-02"
+++
