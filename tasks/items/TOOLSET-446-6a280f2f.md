+++
schema = 1
id = "TOOLSET-446-6a280f2f"
title = "Expose every runner control, model choice, clear-held, attention, status and scorecard"
short = "Runner controls in plugin"
status = "done"
goal = "PASEO-PLUGIN"
section = "Now"
rank = 4000
depends_on = ["TOOLSET-443-41644eec"]
touches = ["Src/pi_autowork/scorecard.py", "integrations/paseo"]
resources = []
kind = "implementation"
ownership = "owner"
scope = "Add restart with stop-workers and now, remove, update, model with fallback (from autowork models), clear-held, attention, the runner status text and the scorecard JSON to the plugin. Each mutation keeps the exact-action confirmation and the operator grant. Make autowork scorecard report a missing repository as an error row instead of failing."
acceptance = ["Every autowork runner command except run, web, tui and blockers is reachable from the Runner view with its confirmation.", "autowork scorecard --json tolerates a runner whose repository is gone.", "Model choice offers the list from autowork models and sends the exact selection."]
checks = ["python3 scripts/affected_tests.py --run", "npm --prefix integrations/paseo run check"]
exclusions = []
closure = "manual"
closure_actor = "interactive Claude Code session"
closure_timestamp = "2026-11-03T05:11:30.950200+00:00"
closure_reason = "restart with stop-workers/now, remove, update, model with fallback from autowork models, clear-held, attention, status text and scorecard in the plugin (538c3459); scorecard tolerates a missing repository (e70cab6f), verified against the live fleet"
closure_evidence = "integrations/paseo/tests/client.test.tsx; Src/pi_autowork/scorecard.py"
+++
