# External input blockers

Only confirmed USER_INPUT, SUDO or USER_DECISION blockers belong here. Internal
engineering and integration work remain in the [`tasks/`](tasks/) store. This file creates
no extra approval step or execution authority.

## Active

<!-- pi-autowork:questions:start -->

### Q-TOOLSET-463-8af43073 — USER_INPUT — effort input — unblocks 1

- Task: TOOLSET-463-8af43073 — Stopped runners stay stopped; restart cannot enable push
- Needs: TOOLSET-463-8af43073 requires owner-performed action, not unattended execution. Saved owner answer: 2026-11-10: continua y resuelvete. Another approval is not requested.
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

### LANGUAGE-STRATEGY — Missing measurement input

- Goal: LANGUAGE-STRATEGY remains unmet; the accepted Rust/Octet direction does not qualify the independent measurement gate.
- Needs: [Complete measurement evidence](docs/plans/2026-11-05-language-strategy.md#measurement-round-1), not another approval. Historical slot projection without completeness proof/status corroboration is not observed idle capacity.
- Question: Supply contemporaneous task-aligned capacity/status evidence or independently corroborated complete historical projection; alternatively, two coordinator-attributable incidents within seven days or a concrete blocked Python target-host attempt with source/time window.
- Kind: input
- Boundary: No Go prototype, new sampler, restart or planning round is authorized by retaining this stop. Completed inspection records remain in Git history.

### PLANNING-AUTHORITY — Verification pending

- Goal: PLANNING-AUTHORITY remains partial. The saved proof-basis decision is settled; no repeated approval is requested.
- Needs: The [current goal requirement](tasks/goals/PLANNING-AUTHORITY.md) names the missing source-bound authority/protocol verification, exact check seams and independent acceptance review.
- Boundary: Manual inspection and implementation closures remain unqualified for a met-goal transition. Preserve typed qualification gates and pinned proof; no waiver, new implementation pass or live qualification is implied.
