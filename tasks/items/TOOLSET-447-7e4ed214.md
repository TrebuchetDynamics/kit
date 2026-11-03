+++
schema = 1
id = "TOOLSET-447-7e4ed214"
title = "Refresh the plugin from a daemon change watch, and report outcomes with toasts and a sidebar count"
short = "Live refresh, toasts, sidebar count"
status = "done"
goal = "PASEO-PLUGIN"
section = "Now"
rank = 5000
depends_on = ["TOOLSET-443-41644eec"]
touches = ["integrations/paseo"]
resources = []
kind = "implementation"
ownership = "owner"
scope = "Paseo 0.14 has no plugin subscriptions, so add a long-poll watch RPC that returns when the fleet, task store or journal digest changes, and drive query invalidation from it with a slow fallback. Show the pending-decision count in the sidebar row and toasts when an operation settles."
acceptance = ["A change to a runner's state or task store refreshes the open views within seconds without manual refresh.", "The sidebar row shows the pending-decision total.", "An operation that settles shows a toast with its status."]
checks = ["npm --prefix integrations/paseo run check"]
exclusions = []
closure = "manual"
closure_actor = "interactive Claude Code session"
closure_timestamp = "2026-11-03T05:11:31.735592+00:00"
closure_reason = "long-poll autowork.watch RPC over task records, Git heads and runner state files with a client loop that invalidates reads; sidebar decision count; toasts on settled operations (542a52c9). Paseo 0.14 has no plugin subscriptions, recorded as follow-up 7"
closure_evidence = "integrations/paseo/tests/server.test.ts; integrations/paseo/tests/client.test.tsx"
+++
