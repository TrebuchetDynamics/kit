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

## Measurement round 1

Measured on 2026-11-07 for `LANG-003-40f1f5a5`. This is a planning result, not
qualification of a new supervisor or a language change.

### Sources and sampling

The prerequisites are coordinator-verified: `LANG-001-8d4fe384` has integration
`6d1c61f96ffc400ca6a946177f8610d2fdfe8df4`, and `LANG-002-72648a0e` has
integration `3e27bfec40f2a9e1ffbbaa05ba28003a9be434ca`. Their records and receipts
under `tasks/items/` and `tasks/evidence/` were read before measurement.

Commands ran from an isolated worktree at
`9712648ee966935d8e38db75418d52488abfbf1e`. `git worktree list --porcelain`
identified the canonical repository (`REPO` below). Canonical HEAD stayed at that
revision for all three samples. The `kit` runner executed release `fbd1f2fe`, not
the worktree build. Its PID and process birth identity stayed unchanged.

- Three reads of `pi-autowork/bin/autowork ls --json`, selecting the `kit` record.
  The sampler used the worktree CLI, not the installed shell command.
- `pi-autowork/bin/autowork scorecard --json REPO`: seven-day window ending
  2026-11-07T04:38:05Z, beginning 2026-10-31T04:38:05Z.
- `autowork status kit`, `pi-autowork/bin/autowork logs -n 180 kit`, and
  `journalctl --user -u pi-autowork@kit --since '7 days ago' --no-pager -o short-iso`.
  Journal inspection on 2026-11-07 also read the individual failure intervals below.

RSS fields ending in `_mb` use MiB (`processes.rss_mb` divides KiB by 1024).
Descendant RSS excludes the coordinator. CPU seconds are cumulative user plus
system CPU time, not a utilization percentage.

| Sample time (UTC) | Coordinator RSS (MiB) | Descendant RSS (MiB) | Live descendants | Coordinator / descendants | CPU seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-11-07T04:38:55.187Z | 57.15625 | 595.05859375 | 20 | 9.60515% | 41.54 |
| 2026-11-07T04:40:00.785Z | 70.109375 | 1478.125 | 51 | 4.74313% | 41.93 |
| 2026-11-07T04:41:06.210Z | 68.81640625 | 2196.0546875 | 45 | 3.13364% | 42.18 |

Sample gaps were 65.598 and 65.425 seconds. The runner was cycling: `MAIN-008`
changed from running to verifying. Its worker count was 1, then 0, then 0, with a
configured maximum of 8. Review and check processes remained live. These counts
show spare worker capacity at sampling time, not at historical dispatch times.

### Gate results

| Threshold | Result | Evidence and limit |
| --- | --- | --- |
| Median coordinator RSS at least 25% of descendant RSS, or at least 1 GiB | **Not met** | Median per-sample share was 4.74313%; median coordinator RSS was 68.81640625 MiB, below 1024 MiB. All three samples had live descendants. |
| Dispatch p95 above 5 minutes while a worker slot is idle | **Not measured** for the combined condition | `evaluation.phase_diagnostics.task_accepted_to_dispatched.metrics.p95_minutes.value` was 279.5569578607877 minutes over 23 observed pairs. The cohort contains tasks with receipt-valid verified closure in the window; their starts can precede it. Current spare capacity does not establish idle slots during those historical waits. |
| More than one coordinator-attributable restart, OOM kill or resource-gate pause per seven days | **Not measured** for attribution and complete coverage | Retained unit journal starts on November 4, not October 31. It contains five main-process exits, 68 resource-gate log lines, 21 toolset-update messages and nine reload messages. Log-line counts are not distinct coordinator-caused incidents. No OOM message was observed in that retained unit journal. |
| Python provisioning blocks a target host | **Not measured** | No owner report or failed Python-provisioning target-host attempt was supplied. This host ran the Python CLI successfully; that does not qualify other hosts. |

The five main-process exits were inspected rather than counted as language evidence:
November 4 at 13:06:57 (UTC-06:00) rejected an incompatible Pi executable;
13:51:12 could not restore an integration worktree. November 4 at 19:04:14 and
19:28:30, and November 6 at 21:45:56, ended in stop timeouts and SIGKILL after
service-stop requests. The first two timeout intervals explicitly show the
coordinator pausing workers and merging finished work before the stop deadline.
These are recovery failures worth retaining, but the available logs do not isolate
coordinator overhead from worker/check shutdown or identify the initiating caller.
A requested stop does not excuse a shutdown failure. Two coordinator-attributable
incidents within seven days would meet the gate even without full-window retention.
Toolset updates and requested reloads are not evidence of spontaneous faults.
Resource-gate lines report host load; they do not attribute it to the coordinator.

### Planner decision and continuation

**Standing policy:** Apply the accepted measurement gate without changing its
thresholds. No complete threshold is established as met, so create no Go prototype
or round-2 implementation batch. Keep `LANGUAGE-STRATEGY` unmet. Do not combine a
historical latency percentile with present spare capacity to claim the joint gate.
This completes the bounded measurement decision, not the language-strategy goal.

The next evidence is task-aligned idle-slot history for the dispatch cohort, a
complete seven-day incident record with coordinator attribution, or an actual
Python-provisioning failure on a target host. `LANG-004-244e109a` keeps that input
question in `Needs decision`, with the planning stop in `BLOCKERS.md`; it is not a
new executable planning round or a new policy approval. Reconsider the gate when
that evidence exists. This round authorizes no new sampler, benchmark service,
prototype, restart or worker dispatch. Existing accepted work continues independently.

## Sources

- Owner recommendation, 2026-11-05 (the request that produced this plan).
- [Current components](../project.md#current-components).
- [Dependencies](../dependencies.md#current-source-policy).
- [`scorecard.py`](../../Src/pi_autowork/scorecard.py).
- [`parallel_dispatch.py`](../../Src/pi_autowork/engine/parallel_dispatch.py).
- [`test_parallel_adversarial.py`](../../pi-autowork/engine/test_parallel_adversarial.py).
- [`test_task_transactions.py`](../../pi-autowork/tests/test_task_transactions.py).
- [`test_parallel_state.py`](../../pi-autowork/engine/test_parallel_state.py).
