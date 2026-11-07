# TOOLSET-479 / TOOLSET-474 / TOOLSET-475 overlap disposition

Reviewed at repository revision `5f2ac81841e1e62c37a6155793b1661795edde45`.
This is an admission diagnosis, not execution, closure or live qualification.

## Evidence

- Read the current records for [TOOLSET-479-7f124d5c](../../tasks/items/TOOLSET-479-7f124d5c.md),
  [TOOLSET-474-6b517117](../../tasks/items/TOOLSET-474-6b517117.md) and
  [TOOLSET-475-66aacc5f](../../tasks/items/TOOLSET-475-66aacc5f.md), their accepted
  plans, and the records and plans for their running peers
  [PLAY-001-1c9535c5](../../tasks/items/PLAY-001-1c9535c5.md) and
  [TOOLSET-473-afef55de](../../tasks/items/TOOLSET-473-afef55de.md).
- The private `.git/autowork-execution/slots/` records show both peers running;
  their worker PID/start-tick identities matched live processes during inspection.
  PLAY already has uncommitted changes to its declared component README and
  implementation/tests. Neither peer has a completed worker report in its
  `slot-data/<task>/attempt-1/` directory; both worker logs were empty at inspection.
  The three waiting tasks have no corresponding slot-data directory. Do not edit
  either running peer's task contract or infer acceptance from unfinished work.
- The committed unfinished contracts name `pi-autowork/README.md` five times:
  PLAY-001 and TOOLSET-479, 480, 481 and 482. They name
  `rust/autowork/README.md` five times: TOOLSET-473 through 477. These are literal
  non-test paths, exceeding `HOT_TASKS = 3` in
  [parallel_plan.py](../../src/pi_autowork/engine/parallel_plan.py).
  Its `plan` counts unfinished noncandidate contracts and unlanded slots too;
  held peers alone reserve no files. Cold paths, directories, globs and test
  modules do not establish the same file gate. Resources and protected paths
  retain their independent admission rules.
- Replaying `plan` with the current task declarations, all committed contracts
  and each named running peer reproduced all three exact reported hot-file waits.
  This checks the supplied wait explanations, not whole-runner admission.

## Contract decisions

**TOOLSET-479:** retain the wait for PLAY-001. The accepted
[one-product-root contract](../plans/pi-autowork-component-layout.md#one-product-root-contract)
requires component navigation/current path documentation in the atomic Python
source/test cut. The existing component README documents precisely those source
owners and entrypoints. The [Play plan](../plans/play-main-checkout.md#accepted-outcome)
requires command/Play documentation, and PLAY's scope explicitly assigns it to
this README. Removing either declaration would conceal a genuine output.
The layout plan explicitly gives A no logical prerequisite and explains why its
loader/fixture relocation must remain atomic. Overlap alone justifies neither
adding PLAY as a dependency nor splitting that cut.

**TOOLSET-474 and TOOLSET-475:** retain both waits for TOOLSET-473. Each contract
owns its module, focused tests and the crate README; the documentation path is
an intended output, not a claim that it already exists. The accepted
[Rust batch](../plans/rust-octet-autowork.md#first-implementation-batch) defines
separate foundation-provided task-store, journal and runtime seams. Its builder
handoff explicitly says these three implementations can proceed independently
after foundation. Preserve both existing dependencies on TOOLSET-472-48c78e95,
whose record is coordinator-verified done. There is no source-backed runtime
producer prerequisite for either task, and no evidence supporting a narrower
documentation scope, merge, split or changed order.

## Outcome and verification

Leave all task records, priorities, acceptance, checks, dependencies, resources
and authorization unchanged. The reported waits are legitimate waits on unlanded
work, not missing owner input or malformed contracts. Re-evaluate admission as
work lands; this record neither promises immediate dispatch nor bypasses any
remaining resource/protected-path gate. No runtime state was changed.

The prescribed `tasks validate --worktree .` passed with 278 tasks, 33 goals,
no drafts and no pending diagnostics. The three pure scheduler replay assertions
passed. `python3 scripts/affected_tests.py --run --base HEAD` selected zero
modules for this disposition-only document. No product check, model execution or
live acceptance is claimed.
