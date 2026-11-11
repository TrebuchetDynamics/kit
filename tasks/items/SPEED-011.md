+++
schema = 1
id = "SPEED-011"
title = "Planner instructions keep resources for exclusive things and use touches for file overlap"
short = "Resources only for exclusive things"
status = "done"
section = "Next"
rank = 33000
depends_on = []
touches = ["skills/shared/TODO-WORKCENTER.md", "skills/docs-sync/SKILL.md", "pi-autowork/task-store.md", "pi-autowork/src/pi_autowork/task_commands.py", "pi-autowork/tests/runner/test_task_commands.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Tasks that name the same resource run one at a time. On 2026-11-10 the resource `autowork-python-layout` held three kit tasks behind another whose files were different. State one rule in the planner instructions (skills/shared/TODO-WORKCENTER.md, skills/docs-sync/SKILL.md) and in pi-autowork/task-store.md: `touches` is the only declaration of file overlap; `resources` names only something that cannot be shared, such as a port, an install, a device or a live service. `autowork tasks validate` reports, as a warning and not an error, a resource name that no task in the store uses together with `live`, a port, an install or a device word, so a planner sees a broad name before it serializes work. The owner already removed `autowork-python-layout` from the open kit tasks."
acceptance = ["The three documents state the rule with one example of a correct resource and one of a file overlap that belongs in touches.", "A fixture proves validate prints the warning for a broad resource name shared by two tasks and stays ok:true, and prints none for `live` or a named port, install or device.", "No scheduling behaviour changes: tasks that share a declared resource still run one at a time."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_task_commands.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/SPEED-011.toml"
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
