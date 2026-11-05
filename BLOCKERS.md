# External input blockers

Only confirmed USER_INPUT, SUDO or USER_DECISION blockers belong here. Internal
engineering and integration work remain in the [`tasks/`](tasks/) store. This file creates
no extra approval step or execution authority.

## Active

<!-- pi-autowork:questions:start -->

### Q-TOOLSET-463-8af43073 — USER_DECISION — effort decision — unblocks 1

- Task: TOOLSET-463-8af43073 — Verify a deliberate stop is terminal and a restart re-asserts configuration
- Needs: TOOLSET-463-8af43073 requires owner action or recorded live authorization; an unattended runner cannot run it.
- Since: 2026-11-05T02:13:30Z
- Answer: Run it yourself, set `live = "authorized"` in tasks/items/TOOLSET-463-8af43073.md with an `Owner decision:` note (who authorized which live scope and when), or move it to Needs decision. Only the owner grants it; a worker's edit to the record never does.
- Kind: outside

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

### Q-TOOLSET-468-d0554d9d — Planning stopped

- Goal: PLANNING-AUTHORITY — One planning authority and shared protocol.
- Task: TOOLSET-468-d0554d9d — Plan the remaining planning-authority proof after the policy audit
- Needs: The accepted decision is implemented and audited and all member tasks are done, but PLANNING-AUTHORITY stays partial because TOOLSET-432-d98e9678 and TOOLSET-433-3eba7cfe closed as manual agent closures without an executed goal Evidence note.
- Question: Should PLANNING-AUTHORITY be marked met on the recorded offline checks plus the coordinator-verified audit, or does it need a fresh coordinator-verified full pass?
- Kind: decision
- Continuation: TOOLSET-469-7ba77973 in Needs decision.
