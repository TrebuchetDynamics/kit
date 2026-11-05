# Language strategy: keep the Python core, measure before changing

Status: Accepted (owner recommendation, 2026-11-05). The Go supervisor prototype
remains conditional on the measurement gate below.

## Decision

- Keep Autowork's coordinator, task store, authority, leases, dispatch, integration
  and verification in Python.
- Use Go only for a standalone operational component after measurements justify it.
- Keep TypeScript at the Pi and Paseo integration boundary. Do not introduce a
  TypeScript coordinator.
- Do not start a full Go rewrite. Reconsider it only after a bounded Go prototype
  shows a substantial measured benefit.

This is a direction for future work, not a rewrite order. The current Python engine
stays the canonical owner of task state and execution authority.

## Why

Autowork is a coordinator of Git operations, agent subprocesses, structured task
state and verification. Most wall-clock time is spent waiting on external work, so
Python is unlikely to be the main performance bottleneck. The delicate correctness
guarantees already implemented in Python — task-store revisions, bounded pushes,
structured authorization, reserved worker slots and attempt provenance — would need
revalidation in any rewrite.

Go's strongest case is operational: a single binary, process supervision,
cooperative cancellation and predictable deployment. That is a supervisor-sized
component, not the whole engine. TypeScript's strongest case is host integration,
which already exists in the Paseo plugin and the Pi adapter.

## Evidence

- [Current components](../project.md#current-components): the engine is Python; the
  Paseo plugin is TypeScript; the Pi adapter is JavaScript.
- [Dependencies](../dependencies.md#current-source-policy): pi-autowork stays
  standard-library Python; Textual and `uv` are optional presentation and tooling.
- [`scorecard.py`](../../Src/pi_autowork/scorecard.py) already reports observed
  phase diagnostics, including dispatch-to-integration latency (TOOLSET-394). It
  does not sample coordinator memory or CPU.
- [`parallel_dispatch.py`](../../Src/pi_autowork/engine/parallel_dispatch.py)
  measures host memory, disk and load for admission. It does not measure the
  coordinator's own footprint.
- [`test_parallel_adversarial.py`](../../pi-autowork/engine/test_parallel_adversarial.py),
  [`test_task_transactions.py`](../../pi-autowork/tests/test_task_transactions.py)
  and [`test_parallel_state.py`](../../pi-autowork/engine/test_parallel_state.py)
  already cover worker lifecycle races, concurrent task-store writes and lease
  expiry. No new test-only task is needed for that outcome.
- [`task_select.py`](../../Src/pi_autowork/engine/task_select.py) and
  [`planning_authority.py`](../../Src/pi_autowork/planning_authority.py) are the
  critical selection and authority seam. They carry partial annotations and the
  repository had no type-check configuration when this plan was written.

## Decision gate for a Go supervisor prototype

A bounded Go prototype that reproduces task selection and process supervision
without acquiring canonical write authority is justified only if the first
measurement shows at least one of:

- coordinator RSS is at least 25% of the RSS of the rest of its live process tree
  (workers, agents and checks, excluding the coordinator) or at least 1 GiB,
  measured as the median of at least three samples at least 60 seconds apart while
  the runner is cycling. The share is not evaluated when the tree has no live
  descendant;
- dispatch latency p95 exceeds 5 minutes while at least one worker slot is idle,
  from `autowork scorecard --json` and `autowork ls --json`;
- coordinator restarts, OOM kills or resource-gate pauses attributable to the
  coordinator occur more than once per 7 days per repository, from the service
  journal and runner state;
- installing or running the coordinator requires Python environment provisioning
  that blocks a target host, reported by the owner or a target-host attempt.

These thresholds are planner calls, revisable when the first measurement exists.
A threshold with no available evidence is recorded as `not measured`; it does not
justify a prototype. A prototype that meets none of the measured thresholds is not
started. A single sample is not a benchmark; the measurement task records its
source, time and limits.

## Rejected alternatives

- **Full Go rewrite now.** Revalidates every correctness guarantee for a benefit
  that is not yet measured.
- **TypeScript coordinator.** Limited operational benefit; the host boundary
  already uses TypeScript.
- **Immediate Go supervisor.** No measured need; an unbounded prototype could
  become a second task owner or scheduler.

## Ordered work

1. `LANG-001-8d4fe384` measures coordinator and fleet resource use in the existing
   status surface.
2. `LANG-002-72648a0e` type-checks the selection and authority seam strictly.
3. `LANG-003-40f1f5a5` is the closing planning task: it reads the measurements,
   applies the gate, and saves the next batch or records why no prototype starts.

The closing task records the first measurement under `## Measurement round 1` and
follows [rolling planning](../../skills/shared/TODO-WORKCENTER.md#rolling-planning).
It depends on both building tasks and carries `Plan round: 1 of 10`.

## Sources

- Owner recommendation, 2026-11-05 (the request that produced this plan).
- [Current components](../project.md#current-components).
- [Dependencies](../dependencies.md#current-source-policy).
- [`scorecard.py`](../../Src/pi_autowork/scorecard.py).
- [`parallel_dispatch.py`](../../Src/pi_autowork/engine/parallel_dispatch.py).
- [`test_parallel_adversarial.py`](../../pi-autowork/engine/test_parallel_adversarial.py).
- [`test_task_transactions.py`](../../pi-autowork/tests/test_task_transactions.py).
- [`test_parallel_state.py`](../../pi-autowork/engine/test_parallel_state.py).
