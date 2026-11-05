+++
schema = 1
id = "TOOLSET-470-aaca1816"
title = "Share one presentation contract between the TUI and the Paseo plugin"
short = "Share the presentation contract"
status = "open"
goal = "PASEO-PLUGIN"
section = "Next"
rank = 7000
depends_on = []
touches = ["Src/pi_autowork/task_status.py", "Src/pi_autowork/task_snapshot.py", "Src/pi_autowork/fleet_view.py", "Src/pi_autowork/command.py", "Src/pi_autowork/task_commands.py", "pi-autowork/tests/", "integrations/paseo/shared/contracts.ts", "integrations/paseo/client/presentation.ts", "integrations/paseo/client/screens.tsx", "integrations/paseo/tests/", "integrations/paseo/docs/design.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "One Python presentation contract owns the display words for a task and a runner. task_status keeps the vocabulary; task_snapshot builds the task display; fleet_view builds the runner display. The CLI carries the display in tasks list --json, tasks show --json and ls --json. The TUI uses the same row data. The Paseo renders the display and keeps tone, icon, relative time and layout; it removes the closure, task-state and blocker mappers. The display is output-only: no admission, dispatch, integration or closure module reads it. The raw fields stay; both consumers are in the repository. Update the Paseo design decision and the tests. Do not change task authorization, the runner service, publication or live state."
acceptance = ["A task display carries state, bucket, why, question, pending, blocker and closure (label, detail, verified, provenance); a runner display carries state, needs, question summary, blockers, question IDs and the task map. The values come from task_status, task_snapshot and fleet_view; no second mapper.", "autowork tasks list --json, autowork tasks show --json and autowork ls --json include the display. The raw status, closure and blocked_by fields stay. The TUI renders the same row data without a behavior change.", "The Paseo task and runner schemas accept the display. The client renders the display; closureLabel, closureBadge, taskState and blockedReason are removed. stateTone, toneIcon, relativeTime and layout stay.", "The display is output-only. A structural test shows no admission, dispatch, integration or closure module imports the display functions.", "The Paseo design doc names the split: the CLI owns the domain labels; the client owns tone, icon, relative time and layout. Docs Sync passes.", "The focused Python tests and the Paseo npm run check pass; the task store validates."]
checks = ["python3 scripts/affected_tests.py --run", "cd integrations/paseo && npm run check", "./pi-autowork/bin/autowork tasks validate --worktree .", "python3 skills/docs-sync/scripts/docs.py check ."]
exclusions = ["No change to task authorization, admission, dispatch, integration or closure rules; the display is descriptive only.", "No runner service start, stop or restart, no publication, push, deployment or live qualification.", "No removal of raw CLI fields and no change to the TUI closed view beyond the shared display."]
+++
- Sources: integrations/paseo/docs/design.md#native-presentation; docs/project.md#task-status-vocabulary
