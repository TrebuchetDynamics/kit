+++
schema = 1
id = "TOOLSET-436-db0d0f40"
title = "Add Tier 3 skill-trace evals"
short = "Tier 3 trace evals"
status = "done"
goal = "SKILL-ADHERENCE"
section = "Now"
rank = 1000
depends_on = ["TOOLSET-434-99b8a226", "TOOLSET-435-85e3248e"]
touches = ["scripts/skill_trace_eval.py", "scripts/pi_trace_to_eval.py", "evals/README.md", "evals/tier3/", "tests/test_skill_trace_evals.py", "tests/test_pi_trace_to_eval.py", "docs/skill-standard.md", "docs/project.md", "docs/plans/skill-adherence-2026-11-01.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Add scripts/skill_trace_eval.py, evals/tier3 specs and synthetic pass/fail trace fixtures for the six high-risk skills, tests/test_skill_trace_evals.py, and evals/README.md. Grade trace shape and required/forbidden events. Do not call a model or execute trace content."
acceptance = ["Every Tier 3 spec has a passing synthetic trace fixture.", "A forbidden write fails the ponytail-review spec; a wrong-skill or malformed trace is refused.", "The documented CLI returns exit 0 for a pass and exit 1 for a forbidden action.", "The docs state that fixtures are synthetic and do not prove live model adherence."]
checks = ["python3 scripts/check.py tests/test_skill_trace_evals.py"]
exclusions = []
closure = "manual"
closure_actor = "agent"
closure_timestamp = "2026-11-02T05:21:51.097579+00:00"
closure_reason = "Added Tier 3 trace specs, synthetic fixtures, evaluator and tests for the six high-risk skills."
closure_evidence = "offline: tests/test_skill_trace_evals.py and documented CLI pass/fail examples"
+++
- Sources: [skill adherence plan](../plans/skill-adherence-2026-11-01.md#task-3-tier-3-trace-evals)
