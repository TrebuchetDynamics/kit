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
recovery evidence. This invocation does not authorize enabling Orbi, clearing a
pause or starting another implementer.

## Act by default

Invoking `/unblock` authorizes routine recovery decisions, same-issue recovery comments
and scoped label changes using the caller’s existing GitHub access. Do the repair in
this run; do not ask “may I fix or requeue it?” Read-only restrictions still win.
Inventory all pages of open issues and PRs, not just `ai-blocked`: missing labels,
failed checks and unresolved prerequisites can hide stalled work. Check
[stale issue state](#stale-issue-state) before the general requeue below. Fix an
actionable prerequisite first and keep moving on independent issues.

**Reconcile labels after fixing the cause.** Immediately re-read the issue, latest
attempt, linked PR/head, dependencies and current labels. If another worker claimed
it or the evidence changed, leave its state alone. Route base-red blocks only to
[base-red recovery](#base-red-blocks), even when `ai-planning` also applies.
Evaluate all other open issues tagged `ai-planning` or `ai-blocked`:

- `ai-planning` → `ai-ready`: resolve routine choices from accepted decisions and
  repository policy. Verify the issue's scope, acceptance, checks and native
  dependencies, and the complete batch if publication is in progress. Do not race
  the publishing planner. Unresolved intent or an explicit no-dispatch request holds publication.
- `ai-blocked` → `ai-ready`: verify the cause was fixed and the same-issue retry
  is safe. Use the deployment's supported requeue; preserve its recovery evidence.
  If the fix is an owner's local-only commit, use the [candidate handoff](#hand-off-a-local-candidate)
  instead of changing the labels by hand.
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

## Stale issue state

### Closed issues

Include all pages of closed issues carrying **any** of the four labels below.
Re-read each candidate's state and labels immediately before editing. Proceed only
if the issue is still `CLOSED`. Remove only the labels present from this set:
`ai-blocked`, `ai-fix-needed`, `ai-in-progress` and `ai-pr-opened`. Keep `ai-merged`
and unrelated labels. Read back `CLOSED` and the remaining labels; confirm the four
stale labels are absent. If the issue reopened or readback fails, report the
observed state or read error instead of making further label changes.

### Base-red blocks

1. **Compare.** For an open `ai-blocked` issue, read the latest trusted failure.
   When it records that a check also fails on the base (Orbi: `base_ci_red`), bind
   the base branch, SHA, named checks and retained PR from that failure. If it
   carries Orbi's `orbi:base-ci-red:v1` record, use that record; a malformed
   record is unavailable evidence, not a reason to fall back to an older block.
   Compare the recorded SHA with current `origin/<base>` after verifying the
   remote repository and live branch tip, not just a cached tracking ref. If the
   SHA is unchanged or evidence is missing, leave the issue blocked and report
   the matching SHA or the evidence needed to retry.
2. **Recheck.** Rerun the named checks with a timeout using their documented
   invocation on the new base SHA in isolation, not on the PR head. For a hosted
   check, verify the rerun's check identity and head SHA; a rerun of the old
   failing run is not a check of the new SHA. If any check still fails or has no
   confirmed pass on the new SHA, leave the PR and labels unchanged. Report the
   check, SHA, exact error or missing result, and what must change before retrying.
3. **Update the retained PR.** Refresh the open issue, current block, retained
   open PR head/base, ownership and dispatch gates (planning, prerequisites,
   pauses and human gates) before writing. If the evidence changed, reconcile it
   first. Bring the exact tested base SHA into the same PR branch by normal
   merge through the existing owner's authorized path; never force-push or rebase.
   Do not take over an active or uncertain owner. Read back the remote PR head
   and verify it includes both the retained head and the tested base, and that
   the live base still matches the tested SHA. If the update conflicts or cannot
   be verified, report the exact blocker and do not requeue.
4. **Resume the same delivery.** Refresh the same gates before each write. Post
   a deduplicated evidence comment on the issue with the original and tested
   base SHAs, check result and log or run link, PR and verified updated head.
   Confirm the comment is present and the verified base and PR head still match
   before replacing `ai-blocked` with `ai-fix-needed`. Keep all other labels.
   Read back the issue and labels and verify the transition. Check for resumed
   work separately. A held or failed base-red recheck does not fall through to
   `ai-ready` or another repair record for the same blocker.

**Worked example:** Issue #42's block names `python3 scripts/check.py` on
`main` at `17a2b3c`. `origin/main` now points to `89d4e5f`; the same check exits
0 on that commit. The normal merge into PR #43 produces head `cd321ab`; readback
confirms it contains the tested base and the old PR head. The issue comment records
both base SHAs, the passing check evidence and PR #43 at `cd321ab`. Issue #42 is
still open and readback shows `ai-fix-needed` instead of `ai-blocked`. If the check
had exited 1, report its failing output and leave the PR and issue labels untouched
until the base failure is repaired.

## Changed requirements: hand back on the same issue

When accepted requirements change after a delivery attempt, compare the retained
commit with the current acceptance criteria before treating the original failure
as a retry. Old passing tests prove only the cases they covered. Record on the
original issue the retained commit SHA, the missing behavior, and the test or
observation that would prove it. Cite the accepted change. For example, if the
new rule distinguishes a documented answer from conflicting authority, name
both expected results: follow the documented answer; ask one scoped question
only when binding decisions conflict.

Give that evidence to the existing delivery owner on the same issue or linked PR.
If the only blocker was missing intent and the accepted change resolves it,
use the same-issue requeue rules above for eligible unowned work. A passing
new test is required for delivery, not for handoff. Do not implement
the missing change in a competing session or publish the old candidate as complete.
Before writing, refresh ownership, pauses, dependencies and prior comments. Reuse
an unchanged handoff without reposting. If ownership is unknown or a pause applies,
leave dispatch alone. If binding decisions conflict, hold only the affected work;
do not requeue an entire issue past that hold.

After readback confirms the owner has the handoff, report **Handed back**. That
is not **Recovered**: report resumed only after observed pickup or continued work
on the revised requirement. A comment or label alone is not evidence of resumption.

## Hand off a local candidate

1. Verify the exact commit meets the current issue and checks. Confirm publication
   authority, no pause, human gate or open dependency, and no other owner or linked
   PR delivery line. Use the owning deployment's diagnostics and serialize manual
   publishers. If ownership is unknown, hold the handoff.
2. From the candidate checkout with `origin` bound to the source repository, run the
   [candidate helper](scripts/adopt_candidate.py) with the deployment's effective
   `base_branch` and `dispatch_label` (normally `ai-ready`), including repository overrides:

   ```sh
   timeout 15m python3 /path/to/adopt_candidate.py OWNER/REPO NUMBER COMMIT \
     --config /path/to/orbi.toml --base BASE --dispatch-label LABEL
   ```

   The helper merges `origin/BASE` into the commit in a separate worktree, then
   publishes on `orbi/<OWNER>-<REPO>-issue-<N>`. It refuses another remote head
   or an owned issue, and requires an idle slot snapshot from the owning deployment.
   For a merge conflict, inspect the retained worktree; resolve and recheck the
   candidate before publication. After an interrupted write, inspect the remote
   branch, PR and labels first. If the branch already has the prepared commit,
   supply that exact SHA on retry. If the base advanced after publication, update
   and recheck the same PR through the owner-first repair path before requeuing.
3. Keep the **same PR URL** through resume. The new PR body starts with a run marker
   (`<!-- orbi:run=... -->`) from the issue's trusted delivery-line comments, then
   `Fixes #N` (`Closes #N` does not pass Orbi's check). The helper trusts authors
   with repository write access. For a marker posted by the owning runner without
   write access, add `--runner-login LOGIN` only after confirming the GitHub
   account used by that deployment, not the publishing account or a name inferred
   from issue comments. The helper does not rewrite an existing PR body,
   replace the branch, or swap the PR for another one. Route an incompatible PR
   through [owner-first repair](#blocked-prs-owner-first-repair-records).
4. Use the helper's verified PR URL and queue label as the handoff receipt. It
   replaces `ai-blocked` with the dispatch label only after PR readback; Orbi's
   ready-queue takeover records that URL for review without starting another
   implementer. Check for actual pickup before reporting **Recovered**.

## Recover, verify, continue

1. **Bind and inventory.** Read GitHub Issues, native dependencies, linked PRs,
   CI/review results and actual ownership. Use read-only `orbi status` and
   `orbi doctor` with the target's configuration if installed. A failed read is
   unavailable evidence, not an empty queue. Include every unresolved decision,
   not only the dashboard's displayed questions. For open PRs, follow
   [owner-first repair records](#blocked-prs-owner-first-repair-records) below.
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

## Blocked PRs: owner-first repair records

Apply this phase during inventory and before repair/publication. Existing invocation
limits still govern: a read-only scan reports proposed dispositions without writes.

1. **Snapshot.** Inspect every scoped open PR, including PRs with no linked issue.
   Record repository/PR URL, head SHA, base ref/SHA, review decision, required checks
   and their current statuses, mergeability, linked issues/native dependencies and
   live owner (issue, worker/run and branch). Bind check/run URLs, review/conflict
   evidence and observation time to the evaluated head/base. Read ownership from
   current issue comments and configured read-only Orbi diagnostics, not assignee
   or labels alone. Failed/incomplete reads or uncertain ownership mean **Unknown**:
   report the exact read error or missing evidence, next read/action and resume
   condition, with no speculative writes. Account for every PR even if unblocked.
2. **Classify.** Distinguish failed checks, missing required checks, changes requested,
   conflicts/stale heads, native dependencies, external service/transport problems,
   explicit pause, human gate and unknown causes. Pending is a wait, not failure.
   Ignore failed checks on superseded heads as current failure evidence; inspect
   the latest applicable check attempt and any required merge-result checks.
   For a missing check, confirm repository requirements, expected trigger and
   elapsed/queued state before diagnosing failure. Unknown mergeability is not a
   proven conflict. For an external outage, do not assume a code repair: identify
   the service owner and restoration signal. Mark human/paused gates **Held** with
   a named next input, responsible owner and resume condition; do not fabricate
   approval or create meaningless executable work. Keep independent repairs separate.
3. **Reconcile owner first.** Search open and closed issues, PR links, comments and
   prior repair records for this PR/blocker and any shared prerequisite. If an
   existing issue owns the exact PR repair, reuse it. Give relevant new evidence as
   a comment for a live worker; keep its owner and PR branch, and never edit the
   live worker's instructions. An unowned existing issue may receive a scoped
   evidence/contract update after fresh readback. This path creates no second
   tracking issue or worker. Closed repair records require evidence reconciliation,
   not automatic reopening or replacement. Ambiguous ownership stays Unknown.
4. **Cover gaps.** For an uncovered actionable repair, create one linked repair issue
   under the [existing publication contract](../shared/PLAN-HANDOFF.md#publication-and-dependencies).
   Include Outcome, Scope, Exclusions, Acceptance, Verification and Sources, the
   first executable action, head-bound evidence and owner/branch handoff. Name the
   PR URL and existing PR delivery line: fix there, not on a competing repair PR.
   State who coordinates/resumes that line before readiness; an issue is not
   permission to start a second implementer. Only a truly independent prerequisite
   that must land first warrants a separate delivery line. Prefer to reuse a shared
   prerequisite; link affected repair/original issues with native blockedBy edges
   where the prerequisite really blocks them, never for priority or file overlap.
   Use the existing publisher's stable keys and ai-planning construction, verify
   contracts/edges, then publish ai-ready last only for eligible unowned work.
   Keep explicit pauses and human gates held, and preserve a live issue's contract.
5. **Recheck and deduplicate.** Use a repository-scoped stable PR/blocker key across
   invocations; head SHA belongs in evidence, not the issue identity. Match semantic
   repair scope as well as keys so pre-existing unmarked work is reused. Identify
   evidence by PR/blocker/head and evidence URLs/conclusions; unchanged evidence is
   a no-op, including comments. Immediately before each write (including comments),
   refresh PR head/base, blocker state, issue content/comments, dependencies and
   ownership. Drop resolved or superseded findings; reconcile changed evidence first.
   If the owner acquired the repair, use step 3 instead of creating work. Serialize
   publishers of the same PR/blocker; if serialization or deduplication is ambiguous,
   hold the write. GitHub creation/comment writes are not atomic deduplication.
   After a timed-out write, read back before retrying; unavailable readback leaves
   the write Unknown, not failed or permission to create a replacement.
6. **Verify and receipt.** After publication, read back issue content, PR links, native
   edges and readiness under the shared handoff contract. Verify subsequent
   PR/check/run movement separately against the current head: issue creation is not
   recovery. Observe pending movement within a bounded wait, then report its exact
   unfinished gate. Report one disposition per PR (unblocked, owned repair, newly
   covered repair, prerequisite wait, pending, Held or Unknown), with every blocker,
   repair issue or owner, head-bound evidence, actual writes or no-op, and next input.
   Publication is discoverability, not pickup; retain the recovery claim limits below.

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
