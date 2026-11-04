# What the dsh-superagent prototype changes in Autowork — 2026-11-04

Read-only comparison of [`DeepSeek-ai/dsh-superagent-prototype`](https://github.com/DeepSeek-ai/dsh-superagent-prototype)
at `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` (2026-10-31) against the Autowork runner in
this repository. That project is a research prototype, not a product; its own README says
to review and adapt it. This note records what was adopted, what was deliberately left out,
and why, so a later session does not re-propose it. It is not qualification of any live
runner.

Source documents read: `docs/000-philosophy.md`, `001-domain.md`, `002-authorization.md`,
`003-execution.md`, `004-prompts.md`, and `src/core`, `src/executor`, `src/sources`.

## The one principle worth importing

> Take as little human attention as possible, and give as much value as possible.

Every message, notification, question, setting and panel element must give more than the
attention it costs, or it is removed. Everything below follows from that.

## Already present in Autowork

The comparison found far more overlap than gap. These rules are already enforced here, so a
port would add a second mechanism, not a new guarantee:

| dsh rule | Autowork's existing mechanism |
| --- | --- |
| Act only when asked or when a written rule allows it | `task_select.blocking`, the `Live authorization`/`Ownership` gate in `parallel_plan.authorization_wait`, and the store-only admission in `task_queue.selectable` |
| Proactive work starts in `observe` mode, recorded but not executed | the runner never invents work; the planning console stages proposals and requires explicit Apply (`planning_proposals.stage`) |
| A mandate is immutable and revalidated before it resumes | the pinned `contract_hash`/`record_revision`, `contract_changed` holds, and `closed_requeue` proving a verified close was actually reopened in Git |
| Never infer "waiting on a person" from free text | typed `cause` values and `failure_policy.classify`; display text never promotes a technical hold to an owner decision |
| Stored work: decide, then act; retries are idempotent | atomic slot writes, the append-only journal, `progress_runtime.route` (atomic publish, bound request IDs, evidence-bound replies) |
| Retry only passing failures; a failed launch is not retried on its own | `pi_runtime`'s provider cooldown/fallback and bounded retries, `retry_safe`, and the `launch`/`crash` split in `HOLD_CAUSES` |
| A policy change discards running judgement but does not cancel work | priority drift, Touches widening and `contract_changed` reruns; no hold is cancelled by an edit |
| The panel lists first what waits for a person | `questions.build` (owner-only causes), `fleet_view.needs`, `_question_verdict`, the fleet sort |
| A pause holds across restarts | paused slots keep their attempt and resume with the same worktree |

## Adopted now: one slot kept for the owner's continuation

`003-execution.md` gives the concurrency limit **one extra slot for a person's message or a
status request**, "so new work cannot prevent a person from continuing an existing Ticket".
Autowork planned resumed attempts first, but the limit still applied to them: with a full
pool of fresh autonomous work, an attempt the owner had answered, paused or restarted waited
for a worker to finish (up to the task timeout).

Now at most one paused (person-stopped or answered) attempt may resume beside a full pool,
N+1 workers. It takes a free normal slot first, fresh work never uses it, the host memory and
load gates still apply, and the reserve is capped below the hard slot limit. Status reports
the cycle's effective `max_workers` with `configured_max_workers` and `owner_slot`.
Source: `Src/pi_autowork/engine/parallel_dispatch.py`, `pi-autowork/engine/test_parallel_dispatch.py`.

## Deliberately not adopted

| dsh concept | Why it stays out |
| --- | --- |
| Source/Thread/Subscription/Channel domain, with fan-out to tickets | Autowork's unit is a task record plus its attempt history; answers already reach the retried attempt (`answers.md`), and there are no chat channels to route. Adding a thread model would duplicate the store and add a second authority for what is open |
| Mandate as a separate entity with a Policy version | The pinned contract hash and `record_revision` already bind an attempt to the record it was admitted under, and a merge cannot invent a value that is in neither parent (`task_queue.merge_record_error`) |
| An `auto`/`observe` accept mode for the runner | The runner does not create work; the planning console is the observe step, with explicit Apply. A second mode would be a setting where a default suffices |
| Editable, versioned prompt parts | Autowork has no per-deployment prompt configuration to version |
| Conversation-ordered outbound delivery with backoff | `BLOCKERS.md` is rewritten atomically per cycle; there is no queued conversation to order |
| A separate `person/answer` + `person/review` stage table | Health, questions, buckets and blockers already derive precedence separately; unifying them is a candidate refactor below, not a rule change made here |

## Bounded follow-ups (recorded, not executed)

1. **One derived stage per task.** `health.classify`, `task_status.phase_status`,
   `parallel_status.roots` and `questions.exhausted` each decide "what is this waiting for"
   with their own precedence. A single total-ordered `stage()` with the property that a
   person stage always dominates a working stage would remove the chance of disagreement.
   That is a display refactor across several consumers and needs its own tests.
2. **Question budget.** The owner's block can hold many questions; dsh asks one concrete
   question at a time. `/blockers` already walks them easiest first, so a budget would only
   help the raw `BLOCKERS.md` read. Measure first.

A runner stopped or answered by a person is a live path; the new reserve is covered offline
only. Live service restart and answer handoff still need operational qualification.
