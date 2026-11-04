# External input blockers

Only confirmed USER_INPUT, SUDO or USER_DECISION blockers belong here. Internal
engineering and integration work remain in the [`tasks/`](tasks/) store. This file creates
no extra approval step or execution authority.

## Active

<!-- pi-autowork:questions:start -->

### Q-FULL-CHECK — USER_INPUT — effort input — unblocks 0

- Task: the repository's whole offline test suite
- Needs: no full-suite gate: a commit can land while breaking tests its own task never ran, and main is never checked
- Since: 2026-11-04T19:53:37Z
- Answer: Add one line to AGENTS.md, `Full check: <command>` (the command that runs the whole offline suite), or set PI_AUTOWORK_VALIDATE in the runner's settings.
- Kind: full_check

<!-- pi-autowork:questions:end -->

None.

## Engineering holds

Technical incidents remain visible in the runner status and fleet view; they are not owner
questions. A failed review, a dead worker, a merge conflict or exhausted reviewer rework
stays here as Agent repair until normal verification clears it. No such incident asks the
owner to decide whether incorrect work is acceptable.

## Resolved

None.
