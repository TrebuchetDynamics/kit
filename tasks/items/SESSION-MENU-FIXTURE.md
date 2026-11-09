+++
schema = 1
id = "SESSION-MENU-FIXTURE"
title = "Match the fleet pilot menu expectation to the Commands binding"
short = "Match the fleet pilot menu expectatio..."
status = "done"
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
closure = "manual"
closure_actor = "AnimatroniCode2"
closure_timestamp = "2026-11-09T19:48:07.347845+00:00"
closure_reason = "Fleet pilot menu matches the ctrl+p Commands binding; test_fleet_view passed."
closure_evidence = "commit 1ae726bd"
+++
- Sources: docs/plans/tui-responsiveness.md#operational-state-and-screen-boundaries
