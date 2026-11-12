# State-machine analysis

This method supplies analysis, not authority. The caller owns scope, write limits,
task state, review gates and delivery. Direct invocation uses the read-only
[State Machine skill](SKILL.md). Other workflows read this file as reference,
without invoking a second command or inheriting another workflow's default actions.

## 1. Bound the search

Record the repository revision, relevant dirty paths, requested area and available
budget. For "all", inventory every first-party subsystem before choosing deep dives.
List excluded dependencies, generated code, inaccessible services and unexamined
areas. Prioritize money, authorization, data loss and concurrent writes.

Use repository search or an existing index, then verify leads in current source.
Search status enums, boolean combinations, nullable fields, timestamps, ownership,
leases, counters, UI flags, queues, persistence and resource acquisition/release.
Follow callers and writers, not just names containing "state".
Include APIs, workers, callbacks, timers, admin paths, migrations and startup recovery.

Keep a frontier in the response or existing authorized artifact: each area is
mapped, ruled out with evidence, or unresolved with a reason. Search ends when the
frontier is exhausted within scope or the budget is reached. A sampled scan cannot
claim to have found all machines.

## 2. Recover the state

For each candidate, identify the entity, authoritative storage, all writers and
readers that decide what happens next. Express states as predicates over real
fields, including absence, defaults, deletion and partially initialized values.
Separate stored state from derived, cached and externally observed state.

List initial, terminal, error and recovery states. State is not always one enum:
model independent dimensions separately and record constraints between them.
Include coupled entities and parent/child lifecycles without expanding every
possible combination. Mark omitted combinations and reachability assumptions.

Define invariants: conditions that must stay true. Cite accepted requirements,
tests or caller contracts. Keep observed behavior, intended behavior and unknown
intent separate. For liveness claims, state what must eventually happen and the
scheduler, time or delivery assumptions it needs. A suspicious combination alone
is not a defect.

## 3. Recover the transitions

Trace each event through its actual entrypoint to writes and effects. Record:

| From predicate | Event / actor | Guard and where enforced | Writes / effects in order | To predicate | Failure / recovery | Source |
| --- | --- | --- | --- | --- | --- | --- |

Cite file, symbol and line range from the inspected revision. Include automatic
transitions, no-ops, rejection paths, self-transitions and actions that change data
without changing the status label. A diagram may summarize this table, not replace
its guards and evidence.

For each transition, locate the atomic boundary: transaction, conditional update,
lock, actor serialization, or none found. Identify when the guard is checked and
whether it remains valid at the write. An application-level check or a local lock
does not prove exclusion across processes. Record persistence and external effects
separately, including the crash window between them.
Finish this step with each discovered writer mapped or explicitly unresolved.

## 4. Challenge the model

For each relevant risk below, trace a concrete path or explain why it is excluded.
Start from reachable states, not arbitrary corrupt fixtures.

- Missing or inconsistent guards across API, background and administrative paths.
- Duplicate, delayed, reordered or stale events; retry after timeout when the first
  attempt may already have succeeded; reused identity or expired ownership.
- Two writers reading the same state, then racing through check-and-write.
  Give the interleaving, not merely "a race may exist".
- Cancellation, deletion, unmount or terminal completion followed by late success.
- Crash after an external effect but before persistence, and the reverse ordering;
  partial updates, restart, replay and failed compensation.
- Invalid combinations of independent flags or coupled entities.
- Unreachable states, unintended cycles, dead ends and stuck work with no recovery.
  Separate legitimate terminal states from liveness failures.

Inspect existing guards, database constraints, idempotency keys and recovery code
before calling an edge unsafe. Record protection with its enforcement point and
limits. Do not assume that drawing an edge creates an executable path.

## 5. Verify counterexamples

For each finding, give the shortest known reachable event sequence or interleaving,
initial data, entrypoints, expected invariant, actual consequence and source evidence.
Distinguish reproduced defects, source-supported unexecuted counterexamples and
hypotheses that need more evidence. Rank impact separately from confidence.

Use existing safe tests when authorized. Prefer one discriminating sequence check,
with an independent expected result, over many isolated function checks. For broad
sequence coverage, propose model-based or property-based testing with invariants
checked after each action. Also test rejected actions: restricting the generator
to legal transitions can hide missing guards in the implementation.

Concurrency needs a controlled schedule or equivalent evidence; random sequential
actions do not prove race safety. Fault injection and live side effects need their
own authority. Report commands, results and NOT_RUN reasons. Reuse current tooling;
suggest a new library or formal model only when a concrete gap warrants it.

## 6. Report and hand back

Return the inventory/frontier, state predicates and invariants, transition tables,
ranked findings, protected paths, test gaps and inspected source locations.
For each finding, propose the smallest guard, atomicity, recovery or test change
that addresses its cause. A missing explicit state-machine library is not a bug.
Keep fixes as proposals unless the caller already owns an implementation workflow.

Use the caller's existing report rather than create another ledger. Name checks
actually run, assumptions, excluded areas, stop reason and the next unresolved
frontier. Passing unit tests, an empty findings list or this map alone is not proof
of exhaustive discovery, model adherence or live safety.
