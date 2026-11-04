# Authorized autonomy audit: dsh-superagent against Autowork — 2026-11-04

Status: **research only.** This commit adds no behaviour. Every recommendation below is a
proposal for review; none is implemented. One earlier commit on this branch
(`7c746892`, reserved owner slot) predates the report-first instruction and is evaluated in
§8 rather than extended.

Method: read `DeepSeek-ai/dsh-superagent-prototype` at `8c32a9dc` (`docs/000`–`007`,
`src/core`, `src/executor`, `src/sources`) and the Autowork engine at main `7c16829b`
(the canonical checkout also held another session's uncommitted `Src/pi_autowork/coordinator.py`
edits, so coordinator line numbers may shift). Paseo client citations are from the
committed tree at `862eefc8`, because that checkout was being edited at read time. No live
runner, service restart or model call was observed: this audit proves source behaviour and
test coverage only, never live qualification.

Success is not more activity. It is fewer unsafe actions, fewer unrecoverable failures,
less owner intervention and more verified deliveries. `autowork scorecard` already measures
those: verified closures, `held_share`, `questions`, `owner_minutes_per_verified_task`
and `cost_per_verified_task_usd` (`Src/pi_autowork/scorecard.py:228-288,466-530`).

## Verdict

| Concept | Verdict | Priority | Residual gap |
| --- | --- | --- | --- |
| 1. Immutable authorization | **Adapt** — enforcement is strong; attribution is missing | P1 | A grant or waiver names neither who, when, nor for which resource |
| 2. Durable effects | **Adapt** — two concrete defects | **P1 first** | Push has no bounded outcome; `BLOCKERS.md` is written non-atomically |
| 3. Attention-first supervision | **Sufficient** — defer new UI | — | Ranking by impact rather than effort is unmeasured |
| 4. Trigger admission / shadow mode | **Reject** for the runner; the analogue already exists in planning | — | None for the runner; GitHub intake is a new product surface |
| 5. Thread subscriptions | **Reject** now | — | No PR workflow exists to subscribe to |
| 6. Slot fairness | **Adopt** — on branch, needs one more test | P1 | A person's explicit new task still waits behind the pool |
| 7. Versioned provenance | **Adapt** — small additive manifest | P2 | Toolset revision and instruction hashes are not recorded per attempt |

The brief's order (authorization → effects → attention) changes on evidence: authorization
*enforcement* is already the strongest part of the engine, so its residual is a small
attribution rule; effects has the two clearest defects; attention is already the most
developed layer. Hence effects first, authorization attribution second, provenance third.

## 1. Immutable authorization and explicit scope

### What exists

- **Typed, store-validated grant.** `live = "authorized"` is a frontmatter enum, not prose
  (`Src/pi_autowork/engine/task_store.py:43,80`); unknown fields are refused, so no new
  authority field can be smuggled in (`task_store.py:256-258`). `Owner only` ownership plus
  a `live` resource requires that grant, and the check runs on **every** dispatch pass, not
  only at first admission: `parallel_plan.plan()` calls `authorization_wait` per candidate
  (`parallel_plan.py:403`, `:198-215`), and `plan()` is the only admission path for fresh,
  resumed and retried work (`parallel_dispatch.py:1134`, `:942`).
- **A worker cannot grant itself or another task anything.** Integration rejects a
  worker-authored change under `tasks/` (not a version the base already had) as
  `Hold('scope', ...)`, with the stated reason that "no branch can grant itself or another
  task resources, live authorization or checks"
  (`parallel_integrate.py:390-426`; test
  `test_a_worker_edit_to_the_task_store_is_held_never_merged_or_offered_again`,
  `pi-autowork/engine/test_parallel_integrate.py:1876`).
- **A merge cannot invent authority.** Every merged field must equal a value from one merge
  parent, and every step of a resolver's first-parent history is checked
  (`task_queue.py:62` `merge_record_error`, `:131` `merge_history_error`, used at
  `parallel_integrate.py:224,457,531` and `coordinator.py:1346`).
- **Scope is explicit and pinned.** `Touches`, `Resources`, `Exclusions`, `Scope`,
  `Acceptance`, `Checks` are typed; the worker's commit is checked against them
  (`verify_scope`, `parallel_integrate.py:349-390`), and an attempt pins
  `contract_hash`/`record_revision`/`rev`; a later contract edit sets the attempt aside
  instead of silently widening it (`parallel_dispatch.py:1174-1179`,
  `contract_changed` in `parallel_state.HOLD_CAUSES`).
- **Publication is a separate, explicit grant**, not a task permission: the saved
  `PI_AUTOWORK_PUSH=1` per repository, workers have pushes blocked by a Git
  `pushInsteadOf` guard (`common.py:122-127`), and only the coordinator's `push()` runs
  without it (`coordinator.py:1561-1615`).
- **Closure is attributed.** `closure_actor`, `closure_timestamp`, `closure_reason`,
  `closure_evidence` (`task_store.py:87-93`), and manual closure requires `--by`, `--reason`
  and optional `--evidence` (documented in `pi-autowork/README.md`, `autowork tasks done`).

### Sufficient?

For *what authorizes work and how far it goes*, yes: the engine, not the model, enforces it,
and neither a worker commit nor a merge can add authority. This is the property the brief
asks for, already present.

### Concrete missing invariant

**A `live` grant and an owner waiver carry no actor, date or bound.** The typed grant is a
permanent bit on the record (`task_store.py:80`), the body note keeps the original wording
but is never parsed back, and `owner_waiver`/`owner_qualification` are free text whose mere
presence satisfies `record.qualified` (`task_store.py:101-102`), which is exactly what the
`verified_depends_on` gate reads (`task_select.blocking`,
`Src/pi_autowork/engine/task_select.py:56-62`). Closure is attributed; these two are not.

User-visible consequence: a record that was authorized for a one-off live action keeps that
authority for any later edit that does not change the contract, and a free-text waiver
permanently satisfies a verification dependency with no record of who waived it or when.
The intended convention is already visible in tests — `Live authorization: owner approved
this run on 2026-10-17` (`pi-autowork/engine/test_parallel_plan.py:52`) — but nothing enforces
it; only placeholder values are refused, and only at migration
(`task_migrate.py:483-485`).

### Cost and risk

Low, and cheap today: **0 of 227 task records use `live = "authorized"` and 0 use an owner
waiver** (counted over `tasks/items/`), so a stricter rule needs no data migration. Two
routes:

- No schema change (recommended first): require the date in the existing note text where the
  runner reads it, and require a date and actor before `qualified` accepts a waiver. Reuse
  `task_queue._dated` (`task_queue.py:281-287`). Existing tests that write a dated grant keep
  passing; an undated one starts waiting with a named reason.
- Schema change (only if attribution must be queryable): add `live_actor`/`live_timestamp`,
  which also needs `validate()`'s allowed set, `merge_record_error`'s field tuple and the
  migration reader. Higher cost, no extra safety yet.

### Minimal change and acceptance

1. Require a record with the typed `live = "authorized"` grant to carry the dated, attributed
   body note the migration already preserves, and validate the date and actor at read; an
   owner-only or `live` task without them is `WAITING` with
   `Live authorization: <ID> (undated)`.
2. Require `_dated()` and an actor for `owner_waiver`/`owner_qualification` in `qualified`.

Deterministic tests: `ParallelPlanTests` gains "an undated live grant waits" and "a waiver
without a date does not satisfy `verified_depends_on`"; both assert the typed
`failure_policy`/`Reason` code, not display text. Offline only.

## 2. Durable effects and crash recovery

### What exists

- **The canonical state is atomic.** Slot and metadata writes are `mkstemp` + `fsync` +
  `os.replace` (`task_execution.py:53-67`); accounting appends are `O_APPEND` + `fsync`
  (`accounting.py:46-62`); health status is tmp+`os.replace` (`health.py:162`).
- **Durable integration intent before the irreversible step.** The candidate merge, baseline,
  contract hash and canonical branch are written to the slot before validation and before
  the fast-forward, and recovery may only recover that exact candidate:
  "Durable intent precedes validation and FF. An abandoned helper can only recover this exact
  candidate, never infer a landing" (`parallel_integrate.py:866-874`, `recover_integration`
  at `:961`).
- **Launch ambiguity is resolved by process identity**, not by a flag: a slot is created
  before the worker starts (`parallel_dispatch.py:1162-1174`), and reconciliation adopts a
  live worker by PID/start-tick identity or classifies a dead one
  (`parallel_state.reconcile`, `worker_live`, `processes.py`).
- **Publication reconciles from Git refs, not from a local boolean.** `sync_upstream` computes
  `upstream..base` and pushes only when main is ahead (`coordinator.py:1539-1559`), so a
  repeated push after a crash is a no-op or a fast-forward, never a duplicate action.
- **The journal is explicitly best-effort telemetry**, and must never turn a successful
  operation into a hold (`execution_journal.py:119-141`, `parallel_state.event`).

### Sufficient?

At the landing and launch boundaries, yes; the pattern the brief recommends is already the
implementation. Two boundaries do not follow it.

### Concrete defects

**(a) `push()` has no bounded outcome.** It runs `subprocess.run(..., timeout=300)` with no
`TimeoutExpired`/`OSError` handling (`coordinator.py:1596-1599`), and the runner loop catches
only `Finish` (`coordinator.py:3859-3873`). A hung remote therefore ends the service process
with a traceback. The *effect* stays safe — the next cycle recomputes from refs — but the
runner crash is an avoidable unrecoverable failure and hides whether the push landed.

**(b) The owner's outbox is not written atomically.** `BLOCKERS.md` is rewritten with
`path.write_text(new)` and then committed (`coordinator.py:3258-3261`), unlike every other
runtime write. A crash during that plain write can leave a torn block; the next pass
then cannot find `END`, appends a second block, and commits the damaged text.

Everything else in the brief's effect list is either implemented or does not apply: the
journal is deliberately not authoritative, and there is no notification transport to queue.

### Cost and risk

Both are small, local edits with no state migration and no new abstraction.

### Minimal change and acceptance

1. Wrap the push invocation in `(OSError, subprocess.TimeoutExpired)`; log exactly one
   "outcome unknown; refs reconcile on the next cycle" line and return. Do not mark the push
   failed, do not retry inside the same call.
2. Write `BLOCKERS.md` through an atomic helper (tmp + `os.replace`), then commit only the
   bytes written; on failure leave the previous file and log.

Deterministic tests: patch `subprocess.run` to raise `TimeoutExpired` → `push()` returns,
one message, nothing propagates out of `cycle()`; a second `sync_upstream()` with
`upstream == base` pushes nothing. Patch `os.replace`/fsync to fail mid-write → `BLOCKERS.md`
is byte-identical to before, no commit is made, one line is logged; a torn file (START, no
END) still yields one repaired block.

## 3. Attention-first supervision

### What exists

- Task-level: only owner-owned causes become questions, with a typed gate
  (`failure_policy.classify` → `resolution_owner`, applied in `questions.add`,
  `Src/pi_autowork/questions.py:88-99`); technical holds stay engineering incidents.
- Fleet-level: `fleet_view.needs` prefers owner questions, else the first blocker
  (`Src/pi_autowork/fleet_view.py:938-955`), runners sort with questions first
  (`fleet_view.py:1275`), and a working headline appends "; N for you"
  (`fleet_view.py:521-542`).
- Paseo: one banner for the whole fleet, decisions first, then failure, then running
  (`integrations/paseo/client/screens.tsx:163-171` at `862eefc8`); urgency orders an error or
  any decision at 0, danger 1, live 2, warning 3, not running 4
  (`integrations/paseo/client/presentation.ts:150-163`); a shared blocker is said once
  (`presentation.ts:164-170`).
- Health announces a stall once per episode and again only when its roots change
  (`Src/pi_autowork/health.py:273-283`).

### Sufficient?

Yes for "what needs a person". The healthy state is compressed, decisions come first in both
surfaces, and duplicates are collapsed.

### Residual gap

Ordering *inside* the owner queue is by effort
(`questions.EFFORT_ORDER = quick, decision, input, investigate`), not by impact (how many
tasks the answer unblocks). Impact is recorded (`unblocks`) but only displayed. This is a
prioritisation nuance, not a defect, and changing it without measurement would trade one kind
of noise for another.

### Recommendation

**Defer.** Measure first: `scorecard` already reports question count and owner minutes; if
owners answer low-impact questions first, revisit ordering. Do not add another panel.

## 4. Trigger admission and shadow mode

### What exists

- The runner selects only from the committed `tasks/` store; it never infers work
  (`task_queue.selectable`, `pi-autowork/README.md` runner section).
- The shadow-mode analogue exists for planning: proposals are staged and require an explicit
  Apply (`planning_proposals.stage`, and the console's Review → Apply;
  `Src/pi_autowork/planning_proposals.py:81,152`).
- Read-only discovery already exists for local sources: `discover_sources.discover` and
  `engineering_signals.scan` produce bounded leads that are explicitly "leads only"
  (`Src/pi_autowork/engine/engineering_signals.py`, `discover_sources.py`).

### Sufficient?

For "no unrequested work", yes. There is no GitHub intake at all in the runner: the only
`github` strings are package sources and documentation URLs
(`cli.py:125,288,332-339`, `service.py:37`). Adding issue/comment intake would need an
authentication model, a deduplication store, a permission table and a new always-listening
service — a second product, not an extension.

### Recommendation

**Reject for the runner; keep the planner's propose→Apply as the shadow mode.** If GitHub
intake is ever wanted, the insertion point is a *local producer of staged task proposals*
fed by a small poller that commits nothing, not a new scheduler. Defer until a concrete user
needs it; no user-visible problem exists today.

## 5. Thread subscriptions

### What exists

A task is a record plus attempt history; later context reaches a retried attempt through
`answers.md` (`parallel_integrate.answer`, `parallel_integrate.py:1499-1528`), the pinned
contract and the attempt's own `prompt.md`/`report.json` under
`slot-data/<task>/attempt-N/`. There is no conversation object and no PR workflow: workers
commit in a worktree, integration merges locally, and publication pushes `main`
(`coordinator.py:1561-1615`). The task record schema has no issue/PR/thread field
(`task_store.py:69-99`).

### Recommendation

**Reject.** There is nothing to subscribe to; the concept would import dsh's ticket/thread
domain for a workflow this runner does not have. If publication later moves to pull requests,
add one `thread` reference to the record and reuse `answers.md`, not the domain model.

## 6. Worker-slot fairness

### What exists

- Interrupted/paused work is planned before fresh work explicitly, so it owns its files and
  does not deadlock against new work (`parallel_dispatch.admit`, `:1048-1080`).
- Priority, goal focus, dependency and exclusive/serial conflicts are enforced in
  `parallel_plan.plan` for every candidate (`:396-430`), including owner-only gates.
- A person's stop/answer pauses the attempt; a runner restart keeps the same attempt and
  worktree.

### Gap

The concurrency limit still applied to a paused continuation: with a full pool of fresh
autonomous work, an answered or restarted attempt waited for a worker to finish. On branch
`dsh-lessons` commit `7c746892` adds one reserved slot (N+1, at most one attempt, free normal
slot first, host gates unchanged, effective `max_workers` + `owner_slot` reported). See §8.

Residual: an explicit person request for a **new** task (`--tasks`, a CLI filter at
`task_execution.py:835`) still competes for a normal slot. The brief's ranking
"human-directed > recovery > continuation > speculative" is therefore only partly met.

### Recommendation

Keep and review the branch change, then decide explicitly whether a person's *new* request
also gets the reserve. The invariant to protect is unchanged: a reserved slot must still pass
the same conflict checks, so it can never sit beside an exclusive, serial or `live` resource
holder. `plan()` already enforces this before dispatch, but no test proves it for the reserve.

## 7. Versioned provenance

### What exists

- Per attempt: `slot-data/<task>/attempt-N/{prompt.md,contract.txt,contract.json,meta.json,report.json,worker.log}`
  written before launch (`parallel_dispatch.py:1162-1200`); `contract.json` pins
  `contract_hash`, `record_revision` and `rev`; `meta.json` holds the argv, host and slot index.
- Per event: `execution_journal.context` records repository hash, task, `attempt_id`, host and
  **model** on every event (`execution_journal.py:165-171`), and journal appends are
  `O_APPEND`+`fsync`.
- Per run: the CLI resolves one immutable toolset release and child processes keep it
  (`pi-autowork/README.md` module table; `cli.py` release resolution); accounting records
  role, usage and attribution (`accounting.py`).

### Gap

A report cannot answer "which instructions and which toolset shaped this attempt?" The
attempt records its own prompt and contract, but not the toolset release it ran from, nor
hashes of the host instructions it read (repository `AGENTS.md`, loaded skills). Two runs of
one task can differ through instruction drift with no recorded difference.

### Cost and risk

Additive and low: two fields in `meta.json` and the journal context. No schema version bump
(the task store is untouched). Deterministic.

### Minimal change and acceptance

Record `toolset_revision` (the resolved release's commit, when it is a Git checkout),
`prompt_sha256` and `instructions` (paths + content hashes of the instruction files the
worker host actually loaded, or an explicit "not recorded" when unavailable). Test: two
dispatches with different prompt bytes produce different hashes; a fixture release makes
`meta.json` name its revision; the journal context carries both.

## 8. The branch change already made

Commit `7c746892` on `dsh-lessons` (unmerged, unpushed) implements the reserved slot from §6
with offline coverage: `test_one_paused_attempt_resumes_beside_a_full_pool_without_a_second_reserve`
(`pi-autowork/engine/test_parallel_dispatch.py:1418`) fails with `[] != ['A']` when the
dispatch change is reverted, and passes with it; the full dispatch, status, e2e, state, plan
and integrate modules were run green (80/7/14/18/25/167 tests), plus
`tests/test_pi_autowork.py -k status`.

Disposition under this brief: **hold for review.** It is evidence-backed and inside the
engine's existing priority order, but it did not follow report-first, it covers only paused
continuations, and the exclusive-resource invariant it must not break is untested. If the
owner prefers a clean slate, reverting the branch commit is a single command and changes
nothing on main.

## Explicitly rejected

| Rejected | Reason |
| --- | --- |
| SQLite (or any second) authoritative task database | The task store is the queue and the audit trail; a second authority would duplicate revisions, leases and closure evidence |
| DSH session management, Feishu, orchestrator/executor domain | Another harness's runtime and a chat product this runner does not integrate |
| A separate always-active supervisory model | New cost and a second authority; the engine's typed policy already owns dispositions |
| Porting prototype code | Research code, not production; no dependency or scan would be reviewed here. Ideas only |
| GitHub event intake for the runner | New auth, dedup, permission and service surface; rejected until a concrete need (§4) |
| Unifying the display vocabularies into a new stage model now | Real drift risk across health, status, questions and Paseo for no current user-visible defect; recorded as a candidate only |

## Prioritized proposals

| # | Proposal | Priority | Cost | Risk | Depends on |
| --- | --- | --- | --- | --- | --- |
| A | Bounded push outcome (`TimeoutExpired`/`OSError` → one "unknown" line) | P1 | ~10 lines + 1 test | Very low | — |
| B | Atomic `BLOCKERS.md` write + commit exact bytes | P1 | ~15 lines + 2 tests | Low | — |
| C | Attributed, dated live grant and owner waiver | P1 | ~40 lines + 3 tests | Low (0 records use either) | A/B independent |
| D | Review reserved slot + exclusive-resource test | P1 | 1 test | Low | branch `7c746892` |
| E | Attempt manifest: toolset revision + instruction/prompt hashes | P2 | ~30 lines + 2 tests | Very low | — |
| F | Owner-queue ordering by impact (only after scorecard evidence) | P3 | measure first | Medium if unordered | `scorecard` window |
| G | Direct unit tests for `merge_record_error`/`merge_history_error` | P3 | tests only | None | — |

Each proposal above states its deterministic acceptance test. None requires a new service, a
new configuration key, a schema migration or a second scheduler.

## What this audit does not prove

- No live runner, service restart, remote push or model call was exercised; every claim is
  about source and offline tests.
- The canonical checkout's `coordinator.py` was mid-edit in another session, so those line
  numbers may move.
- Cost estimates are code-surface estimates, not measured effort.
- `merge_record_error`/`merge_history_error` are exercised only indirectly through
  integration; the "a merge cannot invent authority" property is implemented but lacks a
  direct regression test (proposal G).
