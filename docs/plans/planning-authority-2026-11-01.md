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

The current source at `4fa8f95e9f9ab290a831bf79142951722d8c6c04` has one
machine owner: `planning.py` generates its console policy with
`planning_authority.policy_text()`, and `planning_proposals.py` delegates path and
file checks to that same module. Proposal preview delegates record validation and
authority transitions to `engine/task_store.py::planner_authority`, whose
`_Document` parser owns record schema validation. Task closure/status, live grants
and resources, existing ownership, goal progress and protected owner/evidence/hold
notes remain protected there.

Both planning entry skills link to
`skills/shared/RESEARCH-PLAN.md#shared-planning-interface`. The interactive adapter
retains its interview mode; the autonomous adapter retains repository discovery.
Both preserve read-only/no-write requests and return an Autowork-owned substep to
its original coordinator. Static instruction checks establish these links and
boundaries, not model adherence.

The eight focused modules below pass against that source with CPython 3.12 in the
prepared checker environment, including the console refusal scenarios. The
inherited display-only `GIT_PAGER` variable must be unset for this fixture run:
plan application deliberately refuses inherited `GIT_*` overrides. This changes no
product guard. Independent acceptance review and a supported coordinator
qualification receipt remain required; this source trace and passing checks do not
make the partial goal met. Preserve the immutable proof-basis inputs above.

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

Current qualification checks:

- Before relocation: `env -u GIT_PAGER python3 scripts/check.py tests/test_planning_authority.py pi-autowork/tests/test_planning.py tests/test_workflow_commands.py tests/test_planning_cli_contract.py tests/test_plan_for_me_discovery.py tests/test_task_touches_contract.py tests/test_blockers.py tests/test_skill_standard.py`.
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
