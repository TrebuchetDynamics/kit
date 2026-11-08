# Planning authority and shared protocol

Status: Accepted

## Scope

One machine planning authority and one shared planning interface. Preserve the
accepted Task Store v2 boundary, the Plan For Me / Plan With Me mode split, and the
current CLI behavior.

## Task 1: one planning authority

Keep the machine-enforced planning rules in `src/pi_autowork/planning_authority.py`
(`pi-autowork/src/pi_autowork/planning_authority.py` after the accepted component relocation):
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

## Remaining offline qualification

Status: Accepted engineering qualification within the existing scope.

The `PLANNING-AUTHORITY` goal remains partial. Its current requirement retains
immutable proof-basis inputs at `310a5412fd439dee977792e282a6bb73ee7a0013` and
`5f2ac81841e1e62c37a6155793b1661795edde45`. Historical manual implementation
closures and a policy audit do not qualify the full current implementation.

Discovery at `5301209bfe4ecddef331754376fa21590cb19c57` found the shared machine
owner and existing authority/protocol tests, but no open qualification task.
This is an observed evidence gap, not proof that the implementation is defective.
The Rust state/planning/cycle work and Python/Paseo/Rust relocation already have
accepted tasks; this batch neither duplicates them nor changes their priority.

**Planner's call:** use one offline inspection task to trace both accepted
requirements through their current owners and existing tests. Reuse the tests
rather than add another policy layer, rewrite the skills or infer qualification
from manual closure. Keep goal status partial unless the supported coordinator
qualification checks actually permit a later transition. Never add an owner waiver
or prune retained proof inputs to make the goal appear met.

Acceptance for this remaining slice:

- `PlanningAuthorityTests` and the existing planning-console refusal tests prove
  ordinary edits remain possible while path, size, secret and record-authority
  restrictions agree between validator and generated prompt. Trace the console
  and validator imports to the same owner, including the store-owned schema and
  authority diff checks.
- Existing workflow, planning CLI, discovery, touches, blockers and skill-standard
  tests cover the shared protocol, both planning modes, literal argument handling
  and no-write/coordinator boundaries. Static instruction checks do not prove
  live model adherence.
- Check results and independent acceptance review bind to the same source revision
  and relevant inputs. Correct only current requirement paths and qualification
  claims in this document. Any failed criterion remains unmet with its exact
  failure; inspection is not permission to repair production code or weaken tests.

Proposed checks (UNRUN in this planning pass):

- Before relocation: `python3 scripts/check.py tests/test_planning_authority.py pi-autowork/tests/test_planning.py tests/test_workflow_commands.py tests/test_planning_cli_contract.py tests/test_plan_for_me_discovery.py tests/test_task_touches_contract.py tests/test_blockers.py tests/test_skill_standard.py`.
- After relocation: use the same command with the first two paths replaced by
  `pi-autowork/tests/runner/test_planning_authority.py` and
  `pi-autowork/tests/runner/test_planning.py`; all six shared test owners stay put.
- `git diff --check` for the document update. Reuse only matching source-bound
  check results; do not repeat an unaffected full suite.

The existing `autowork-python-layout` resource serializes this inspection with
source relocation. It is a stable-source requirement, not a new product dependency.
Use the prepared checker environment; if its required inputs are unavailable,
report the exact setup input without installing dependencies during planning.
A failing behavior check is a technical finding, not an owner decision or a reason
to relax acceptance. Source/test repairs require a separately scoped execution
contract. Preserve historical qualification inputs and all typed gates.

The worker updates this current requirement owner only, not a dedicated completion
report. The coordinator retains normal source-bound check/review receipts through
its supported closeout. Expected execution cost: one task integration and one
independent review, separate from the planning commit. No successor planning task
is needed: this slice has a known verification boundary.

## Out of scope

No new planning queue, no second task store, no execution or publication authority,
no live/model qualification, and no change to Task Store v2 selection semantics.
