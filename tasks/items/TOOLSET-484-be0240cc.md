+++
schema = 1
id = "TOOLSET-484-be0240cc"
title = "Task-writing skills produce distinct labels and usable instructions"
short = "Task-writing rules and examples"
status = "done"
goal = "PLANNING-AUTHORITY"
section = "Next"
rank = 18000
depends_on = []
touches = ["skills/shared/TODO-WORKCENTER.md", "skills/shared/RESEARCH-PLAN.md", "skills/shared/PLAN-HANDOFF.md", "tests/test_planning_cli_contract.py", "tests/fixtures/planning/scenarios.py", "tests/fixtures/planning/README.md", "tests/test_planning_specimens.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Make task-writing skills produce clear names and actionable, non-repetitive descriptions. Extend the work-center's existing naming policy with the accepted description standard in docs/plans/planning-skills-current-autowork.md#task-writing-quality. Use existing shared links for planning, Docs Sync, Autoresearch, Autowork discovery and other task-producing skills. Keep field roles distinct: scope explains the behavior change and boundaries; acceptance names observable results; checks gives exact commands; notes supply only additional decisions, inputs and the first action. Extend the existing instruction-contract tests and planning specimens with positive/negative output examples. Preserve authority, active contracts and all mandatory checks. Do not implement a new schema, evaluator service or subjective CLI quality gate."
acceptance = ["PlanningCliContractTests.test_planners_share_descriptive_task_name_policy and proposed test_task_writers_share_actionable_description_policy cover the shared standard and reachable links from the named task-writing routes. Titles/short labels distinguish outcomes; scope explains behavior and boundaries; a concrete first action, evidence and inputs accompany separate acceptance/checks without repeated boilerplate.", "The existing specimen builder covers vague/sibling names, path-only scope, repetitive prose and an unavailable external input. Proposed PlanningSpecimenTests.test_task_writing_cases_preserve_scope_and_evidence verifies valid seeds, complete case inventory and source provenance. README positive/negative examples have a human review rubric that preserves scope, constraints, checks and honest missing inputs.", "Existing planning CLI/specimen and docs checks pass. No repository backlog, task schema, authority, mode boundary or short-label limit changes. Results distinguish offline instruction/fixture checks from optional, unrun model-adherence evaluation."]
checks = ["python3 scripts/check.py tests/test_planning_cli_contract.py tests/test_planning_specimens.py", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No edits to tasks/ by the implementation worker, no bulk backlog cleanup and no rewrite of active contracts or completed naming-task evidence.", "No task schema, CLI, selector, runtime prompt implementation, approval policy, public command or pinned-upstream change. No fixed title/body word count or subjective language-quality rejection in runtime validation.", "No provider/model invocation, installation, service operation, dispatch, push or live qualification. Model-adherence evaluation remains separately authorized and cannot be claimed from static tests."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/TOOLSET-484-be0240cc.toml"
+++
- Sources: docs/plans/planning-skills-current-autowork.md#task-writing-quality; skills/shared/TODO-WORKCENTER.md#task-names; tests/test_planning_cli_contract.py; tests/fixtures/planning/README.md
- Evidence: At 5301209b, completed TOOLSET-479-fbb024b9 supplies naming rules and their phrase/example guard. This task adds description quality, coverage of other task-writing routes and output specimens; it does not reopen that completed task. Existing scenarios.py and PlanningSpecimenTests own fixture preparation, inventory and provenance.
- Decisions: One shared standard, existing fields and brief notes; no per-adapter copies or fixed prose length. Reuse the specimen builder and human example review, not a new service or a claim that static tests prove model quality. Exact wording and assertion structure remain reversible worker choices. No missing input blocks this offline task.
- Repo obligations triggered: The cited plan owns accepted behavior. WORKCENTER owns field semantics; RESEARCH-PLAN/PLAN-HANDOFF own save guidance; existing CLI/specimen tests and fixture README own verification. No generated output or runtime change.
- Next action: Extend the naming guard and add the focused description-policy guard. Observe its targeted failure, update shared guidance, then add bounded specimen cases and update their inventory assertion. Review positive/negative examples against the accepted rubric and run Checks. New tests and implementation checks are proposed and UNRUN.
- Scheduling: One shared policy/fixture outcome, no unmet producer or exclusive resource. Preserve active ownership and unrelated work. Expect one implementation review and integration. This standalone planning task starts no worker and adds no hold.
