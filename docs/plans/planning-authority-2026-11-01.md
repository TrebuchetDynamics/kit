# Planning authority and shared protocol

Status: Accepted

## Scope

One machine planning authority and one shared planning interface. Preserve the
accepted Task Store v2 boundary, the Plan For Me / Plan With Me mode split, and the
current CLI behavior.

## Task 1: one planning authority

Move the machine-enforced planning rules into `Src/pi_autowork/planning_authority.py`:
allowed paths, proposal size, secret refusal and the prompt block. Delegate record
schema and authority diffs to `task_store.planner_authority`. The console policy and
the proposal validator call those owners.

Acceptance: an ordinary task edit passes; closure, owner attestation, hold, live
authorization, ownership, task status and goal status changes are refused; the
console prompt contains the generated machine block; focused authority and planning
tests pass.

Checks:

```sh
python3 scripts/check.py tests/test_planning_authority.py pi-autowork/tests/test_planning.py
```

## Task 2: collapse the planning manual

Add the shared planning interface to `skills/shared/RESEARCH-PLAN.md`. Make
`skills/plan-with-me/SKILL.md` and `skills/plan-for-me/SKILL.md` thin mode adapters
that link to it. Shared rolling-plan and task-record rules have one home. Update the
workflow contract test to read the protocol.

Acceptance: both entry skills link to the shared interface; shared rules are not
restated as parallel manuals; focused planning and workflow tests pass; the accepted
mode split and instruction guards remain.

Checks:

```sh
python3 scripts/check.py tests/test_workflow_commands.py tests/test_planning_cli_contract.py \
  tests/test_plan_for_me_discovery.py tests/test_task_touches_contract.py \
  tests/test_blockers.py tests/test_skill_standard.py
```

## Out of scope

No new planning queue, no second task store, no execution or publication authority,
no live/model qualification, and no change to Task Store v2 selection semantics.
