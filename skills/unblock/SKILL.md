---
name: unblock
description: "Resolve blocked GitHub work without releasing pauses."
license: MIT
---

# Unblock

Apply the [shared Ponytail method](../shared/PONYTAIL.md),
[communication rules](../shared/COMMUNICATION.md) and
[GitHub handoff](../shared/PLAN-HANDOFF.md).

`/unblock [repo|all]` diagnoses the current repository by default. `all` must
name an explicit set of repositories; it is not permission to discover or operate
an entire host fleet. Editing this skill does not invoke recovery.

GitHub Issues and Orbi are the only executable backlog and delivery executor.
Preserve existing tasks, worktrees, attempts and
recovery evidence. Orbi remains paused and live-unqualified. This invocation
does not authorize enabling it, clearing a pause or starting another implementer.

## Act by default

Invoking `/unblock` authorizes routine recovery decisions, same-issue recovery comments
and scoped label changes using the caller’s existing GitHub access. Do the repair in
this run; do not ask “may I fix or requeue it?” Read-only restrictions still win.
Inventory all pages of open issues and PRs, not just `ai-blocked`: missing labels,
failed checks and unresolved prerequisites can hide stalled work. Fix an actionable
prerequisite first and keep moving on independent issues.

**Reconcile labels after fixing the cause.** Immediately re-read the issue, latest
attempt, linked PR/head, dependencies and current labels. If another worker claimed
it or the evidence changed, leave its state alone. Evaluate every open issue tagged
`ai-planning` or `ai-blocked`, including issues with both labels:

- `ai-planning` → `ai-ready`: resolve routine choices from accepted decisions and
  repository policy. Verify the issue's scope, acceptance, checks and native
  dependencies, and the complete batch if publication is in progress. Do not race
  the publishing planner. Unresolved intent or an explicit no-dispatch request holds publication.
- `ai-blocked` → `ai-ready`: verify the cause was fixed and the same-issue retry
  is safe. Use the deployment's supported requeue; preserve its recovery evidence.
- If both labels apply, require both conditions. For each eligible unowned issue,
  publish `ai-ready` last, after the eligibility checks. Confirm readiness before
  removing resolved state labels. Preserve unrelated labels; read back the result
  and check for pickup. If a gate remains,
  report its reason and next action, then continue with the other issues.

Do not blindly replace the full label set. Keep real blockers blocked; keep epics,
explicit pauses and human acceptance out of automatic dispatch. A ready
issue waiting on a native prerequisite need not be relabeled. If a PR already owns
the fix, route the repair there rather than requeueing a second implementation.

For example, when a push times out, compare the retained commit to the remote ref.
If it already landed, resume at the next missing step. If absent, an authorized
normal push of that exact candidate may repair publication; keep hooks enabled and
allow time for them. If the remote diverged, preserve both heads and reconcile with
the owner. A timeout alone neither proves the push failed nor authorizes force-push.

## Recover, verify, continue

1. **Bind and inventory.** Read GitHub Issues, native dependencies, linked PRs,
   CI/review results and actual ownership. Use read-only `orbi status` and
   `orbi doctor` with the target's configuration if installed. A failed read is
   unavailable evidence, not an empty queue. Include every unresolved decision,
   not only the dashboard's displayed questions.
2. **Diagnose.** Read repository policy, accepted scope, latest attempts and failed
   operation logs. Distinguish dependency, active ownership, failed check,
   missing external input and explicit pause. Inspect saved decisions, issue comments,
   dependency readbacks and candidate/attempt evidence before asking a question.
   Check same-issue recovery first: retain its candidate, findings, budgets and
   coordinator; do not create replacement work or a competing repair session.
   Reuse settled answers; distinguish real dependency/resource waits, active or
   uncertain ownership, failed validation and missing external input. A worker
   approval request or label alone does not prove a human decision is needed.
   Choose routine reversible repairs within accepted scope; record the reason as `Standing policy:` where useful.
   Never fabricate an owner answer, waiver, grant or live qualification.
3. **Repair.** Perform authorized local diagnosis and repair within the accepted
   scope, without an additional permission ceremony. Establish one writer per checkout,
   preserve existing candidates and coordinate with their actual owner. Re-read an issue
   before editing its contract; never replace an active worker's instructions.
   Reuse retained code and valid exact-source checks; rerun missing or invalidated
   checks. Never patch a report or clear ownership/attempt state to manufacture progress.
   Keep issue acceptance, affected checks, independent review and PR gates.
   Publish only under existing publication authority. Service operations are a
   separate scope: follow [service boundaries](references/services.md).
4. **Verify.** Run affected checks and required review, then inspect consumption
   of the repair. Observe the expected transition in the issue, PR, checks or
   actual execution evidence; do not claim success from an edited label or a
   saved plan. A known pending operation is unfinished recovery. Inspect its
   completion signal within a bounded wait; do not loop unchanged retries.
   Do not create backlog work merely to make an idle deployment busy.

For a genuine owner gate, ask the smallest concrete question, with a recommendation
and the effect on dependent work. Continue independent authorized repairs.
A planning closure or an evidenced wait is not recovery. Apply the
[Definition of Done](../shared/DEFINITION-OF-DONE.md) to actual delivery claims.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "Restarting fixes every stall." | Repair the cause and verify consumption; preserve pauses. |
| "I saved the answer, so it is unblocked." | An issue edit is not executed recovery. |
| "Orbi is paused, so use the old runner." | The executor is removed; there is no fallback. |

## Red Flags

- Clearing ownership, retry history or failed evidence to make status green.
- Releasing an explicit pause or weakening acceptance to remove a blocker.
- Starting a competing session for an owned issue.
- Claiming live qualification from an offline test.

## Boundaries

- Use the existing planners for missing intent; inspect GitHub issue/PR evidence
  and existing read-only `/orbi status` or CLI diagnostics for status.
- Not a replacement implementation coordinator; repair only the scoped cause.
- Planning-only requests perform no repairs. Read-only/audit/questions-only
  requests mutate no files, issues, labels or services.
- Preserve deliberately paused, disabled or stopped services and other writers.
  Do not kill competing sessions, delete runtime state or change credentials,
  approval policy, model/spend grants or security defaults.
- Production operations, fleet deployment and remote publication need their own
  applicable authority.

**Done when:** every scoped cause has an observed disposition.
Report **Recovered** only when work consumed the repair and continued;
**Idle** only for a confirmed queue with no outstanding work; otherwise
**Blocked**, naming the missing input, active owner or unfinished operation.
If no task resumed, say "No work resumed."

**Receipt:** outcomes per repository, actual transitions, repairs, checks and
commits, plus exact remaining gates. Distinguish local commit, integration,
publication, installed activation and live acceptance.
