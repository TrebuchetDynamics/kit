# External input blockers

Only confirmed USER_INPUT, SUDO or USER_DECISION blockers belong here. Internal
engineering and integration work remain in the [`tasks/`](tasks/) store. This file creates
no extra approval step or execution authority.

## Active

<!-- pi-autowork:questions:start -->

### Q-TOOLSET-431-47a7152e — USER_INPUT — effort input — unblocks 1

- Task: TOOLSET-431-47a7152e — Kit rename stage 4: prove a pre-rename profile keeps its settings (no npm release)
- Needs: TOOLSET-431-47a7152e requires owner-performed action, not unattended execution. Saved owner answer: 2026-11-07: approved. Another approval is not requested.
- Since: 2026-11-07T21:55:00Z
- Answer: Perform the task outside this runner and record the actual completion evidence, or explicitly defer or cancel it. Saved direction is not completion evidence; another approval or live grant does not transfer an owner-owned task to the runner.
- Kind: owner_action

### Q-TOOLSET-463-8af43073 — USER_INPUT — effort input — unblocks 1

- Task: TOOLSET-463-8af43073 — Verify a deliberate stop is terminal and a restart re-asserts configuration
- Needs: TOOLSET-463-8af43073 requires owner-performed action, not unattended execution. Saved owner answer: 2026-11-07: approved. Another approval is not requested.
- Since: 2026-11-05T02:13:30Z
- Answer: Perform the task outside this runner and record the actual completion evidence, or explicitly defer or cancel it. Saved direction is not completion evidence; another approval or live grant does not transfer an owner-owned task to the runner.
- Kind: owner_action

<!-- pi-autowork:questions:end -->

None.

## Engineering holds

Technical incidents remain visible in the runner status and fleet view; they are not owner
questions. A failed review, a dead worker, a merge conflict or exhausted reviewer rework
stays here as Agent repair until normal verification clears it. No such incident asks the
owner to decide whether incorrect work is acceptable.

## Resolved

None.

## Planning stops

### Q-LANG-003-40f1f5a5 — Planning stopped

- Goal: LANGUAGE-STRATEGY — Keep the Python core and adopt another language only from measured need.
- Task: LANG-003-40f1f5a5 — Decide the Go supervisor prototype from measured coordinator resources.
- Needs: Round 1 completed with median coordinator RSS 68.82 MiB and share 4.74%, below the accepted memory gate. The historical dispatch p95 lacks same-time idle-slot evidence, incident logs do not establish coordinator attribution, and no blocked Python target-host attempt was supplied. No prototype starts; the goal stays unmet.
- Question: Is there task-aligned idle-slot history, a record of at least two coordinator-attributable incidents within seven days, or a blocked Python target-host provisioning attempt to evaluate? Provide the concrete evidence source; current data does not establish a complete gate.
- Kind: input
- Continuation: LANG-004-244e109a in Needs decision; evaluate supplied evidence under the unchanged gate, not a request for new policy approval.

### Q-TOOLSET-468-d0554d9d — Planning stopped

- Goal: PLANNING-AUTHORITY — One planning authority and shared protocol.
- Task: TOOLSET-468-d0554d9d — Plan the remaining planning-authority proof after the policy audit
- Needs: The accepted decision is implemented and audited and all member tasks are done, but PLANNING-AUTHORITY stays partial because TOOLSET-432-d98e9678 and TOOLSET-433-3eba7cfe closed as manual agent closures without an executed goal Evidence note.
- Question: Should PLANNING-AUTHORITY be marked met on the recorded offline checks plus the coordinator-verified audit, or does it need a fresh coordinator-verified full pass?
- Kind: decision
- Continuation: TOOLSET-469-7ba77973 in Needs decision.
