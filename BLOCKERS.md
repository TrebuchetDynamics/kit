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

### Q-TOOLSET-467-69e39d8c — USER_INPUT — effort input — unblocks 1

- Task: TOOLSET-467-69e39d8c — Record the standing autonomy policy audit of open owner questions
- Needs: the worker edited the task store, which only the coordinator writes: tasks/items/TOOLSET-431-47a7152e.md, tasks/items/TOOLSET-450-e643cb7a.md, tasks/items/TOOLSET-451-ba324296.md
- Since: 2026-11-05T08:39:23Z
- Answer: Answer in tasks/items/TOOLSET-467-69e39d8c.md with the evidence or a dated `Owner decision:` deferral. Review the specific requested `touches` change against the worker report; approve only that file scope if appropriate, otherwise split or defer the task. Keep the task in Needs decision if the input is unavailable; preserve the acceptance criteria, live authorization and ownership gates. A record edit does not supply signatures or transfer live ownership, and does not by itself establish that the blocker is resolved.
- Kind: held

<!-- pi-autowork:questions:end -->

None.

## Engineering holds

Technical incidents remain visible in the runner status and fleet view; they are not owner
questions. A failed review, a dead worker, a merge conflict or exhausted reviewer rework
stays here as Agent repair until normal verification clears it. No such incident asks the
owner to decide whether incorrect work is acceptable.

## Resolved

None.
