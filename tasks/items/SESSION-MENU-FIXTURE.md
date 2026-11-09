+++
schema = 1
id = "SESSION-MENU-FIXTURE"
title = "Match the fleet pilot menu expectation to the Commands binding"
short = "Match the fleet pilot menu expectatio..."
status = "open"
section = "Now"
rank = 12000
depends_on = []
touches = ["pi-autowork/tests/tui_pilot.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Repair only the stale exact menu suffix assertion after the landed ctrl+p Commands menu addition; preserve all old labels, shortcut highlighting assertions and refusal scenarios."
acceptance = ["The existing fleet pilot passes with the actual Commands suffix; every prior menu action and highlighted-key assertion remains checked."]
checks = ["python3 scripts/check.py pi-autowork/tests/test_fleet_view.py"]
exclusions = ["No product changes, removed assertions, service/model actions, task-contract changes or publication."]
+++
- Sources: docs/plans/tui-responsiveness.md#operational-state-and-screen-boundaries
