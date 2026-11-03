+++
schema = 1
id = "TOOLSET-449-3da2ac43"
title = "Record the plugin's new surface and its qualification state"
short = "Plugin docs and qualification"
status = "open"
goal = "PASEO-PLUGIN"
section = "Now"
rank = 7000
depends_on = ["TOOLSET-443-41644eec"]
touches = ["integrations/paseo/README.md", "integrations/paseo/OVERVIEW.md", "integrations/paseo/docs"]
resources = []
kind = "implementation"
ownership = "owner"
scope = "Update the plugin README, OVERVIEW, follow-ups and qualification record for the new grants, actions, reads and live refresh. State what offline checks prove and what remains pending live qualification on the desktop app."
acceptance = ["The plugin README documents every action and grant.", "The qualification record separates offline evidence from pending live acceptance."]
checks = ["npm --prefix integrations/paseo run check"]
exclusions = []
+++
