+++
schema = 1
id = "TOOLSET-433-3eba7cfe"
title = "Collapse the planning manual"
short = "One shared planning protocol"
status = "done"
goal = "PLANNING-AUTHORITY"
section = "Now"
rank = 3000
depends_on = ["TOOLSET-432-d98e9678"]
touches = ["skills/shared/RESEARCH-PLAN.md", "skills/plan-with-me/SKILL.md", "skills/plan-for-me/SKILL.md", "tests/test_workflow_commands.py", "tests/test_task_touches_contract.py", "docs/project.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Add the shared planning interface to skills/shared/RESEARCH-PLAN.md. Make skills/plan-with-me/SKILL.md and skills/plan-for-me/SKILL.md thin mode adapters that link to it. Move shared rolling-plan and task-record rules to the protocol. Update the workflow contract test to read the protocol."
acceptance = ["Both entry skills link to the shared planning interface and keep only mode-specific behavior.", "Shared rolling-plan and task-record rules have one home in the protocol.", "The accepted Plan For Me / Plan With Me split and existing instruction guards remain.", "Focused planning and workflow tests pass."]
checks = ["python3 scripts/check.py tests/test_workflow_commands.py tests/test_planning_cli_contract.py tests/test_plan_for_me_discovery.py tests/test_task_touches_contract.py tests/test_blockers.py tests/test_skill_standard.py"]
exclusions = []
closure = "manual"
closure_actor = "agent"
closure_timestamp = "2026-11-02T04:08:10.021242+00:00"
closure_reason = "Moved the shared planning interface into RESEARCH-PLAN and reduced Plan With Me and Plan For Me to mode adapters."
closure_evidence = "offline: planning and workflow contract checks passed"
+++
- Sources: [planning authority plan](../plans/planning-authority-2026-11-01.md#task-2-collapse-the-planning-manual)
