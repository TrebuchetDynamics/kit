+++
schema = 1
id = "SPEED-005"
title = "Rolling planning stops at three rounds and each plan run yields a task or one owner question"
short = "Three planning rounds, one result"
status = "open"
section = "Next"
rank = 29000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/maintainer.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/runner/", "skills/shared/TODO-WORKCENTER.md", "skills/shared/RESEARCH-PLAN.md", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "A plan task may save a successor plan task up to round 10 (skills/shared/TODO-WORKCENTER.md, skills/shared/RESEARCH-PLAN.md, pi-autowork/src/pi_autowork/maintainer.py). Cut the limit to three rounds. A plan run is accepted only when it saves at least one runnable worker task or exactly one owner question; a run that saves neither is closed as `no result` with its reason and is not retried. An open plan task already past round three runs one final time under this rule and may save no successor. A proposal rejected by a format rule, such as `Needs decision items must name their question`, is retried once with the rejection text given to the planner; after a second rejection the task is a visible engineering hold, and the task views show the latest outcome, not the earlier rejection."
acceptance = ["Fixtures prove a round-three plan task cannot save a successor, a plan task recorded above round three runs once with no successor, and a run that saves neither a runnable task nor one owner question closes as `no result` without retry.", "A proposal rejected once for a format rule is replanned once with the rejection text; a second rejection leaves one engineering hold and no further planning run.", "The planning instructions in skills/shared and the README state three rounds and the task-or-question rule."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_maintainer.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling rounds 1 and 2, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
