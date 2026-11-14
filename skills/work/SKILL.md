---
name: work
description: "Implement GitHub issues in this session."
license: MIT
---

# Work

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../shared/COMMUNICATION.md) for user-facing text.

Follow the [shared contract](../shared/COMMON-CONTRACT.md) and
[GitHub handoff](../shared/PLAN-HANDOFF.md). Orbi is the default executor.
`/work` explicitly requests manual in-session delivery through the same GitHub
issue → PR → independent review → merge gates, not the retired Autowork engine.

## Select, implement and deliver

1. Read repository instructions, current GitHub Issues, native `blockedBy`
   dependencies and linked PRs. Honor a supplied issue or scope. Without one, select
   eligible work by repository priority; do not ask the owner to choose routine work.
2. Coordinate ownership **before editing**. Check Orbi's actual delivery state and
   existing PR/worktree. Do not steal an active issue. For an idle manual target,
   remove `ai-ready`, add `ai-planning`, and confirm no concurrent claim occurred.
   Labels are not an atomic lock: serialize with the deployment operator if an Orbi
   tick can race. If ownership is uncertain, choose non-overlapping work or report it.
3. Read the complete issue contract and governing decisions. Resolve ordinary
   reversible engineering details locally. Missing consequential intent routes to
   `/plan-with-me`; a runtime failure is not a new product-planning task.
4. Implement in an owned workspace; all new task worktrees live under the canonical
   repository's `.worktrees/`. Start with the failing test where applicable, make
   the smallest cohesive change, and run the issue's verification and proportional
   repository checks. Preserve exclusions and separate offline from live acceptance.
5. Open/update the linked PR with exact results. Obtain independent review in a
   fresh context window: state scope, completion criterion and read-only permission.
   Fix findings and satisfy repository CI, branch protection and human-only gates.
   Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md); never claim a
   merge or live qualification from a local test pass.
6. Record results on the issue/PR. Close only when its acceptance and required merge
   are verified. Retain unfinished work and its precise next action; do not turn a
   session interruption into duplicate implementation or automatic requeue.
   Continue eligible work within the caller's scope; stop at a genuine gate or
   exhausted useful work. A session end starts no replacement service or worker.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "Removing readiness is a lock." | Check actual ownership and serialize against dispatch. |
| "Local tests passed, so close the issue." | Review, CI, merge and live gates remain distinct. |

## Red Flags

- Implementing an issue already owned by Orbi.
- Writing a new local task queue or legacy lease.
- Skipping review or reporting an unmerged PR as delivered.

## Boundaries

- Not service control; `/autowork` inspects the Orbi handoff.
- Not product discovery; use `/plan-for-me` or `/plan-with-me`.
- Not read-only status; use `/pending`.

**Done when:** the in-scope delivery loop reaches an evidenced stop, with issue/PR
URLs, actual checks/review/merge status and exact remaining blockers reported.
