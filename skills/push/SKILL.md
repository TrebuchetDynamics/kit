---
name: push
description: "Commit all, merge worktrees, sync and push main."
license: MIT
---

# Push

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/push` is a repository-wide delivery request: commit all eligible changes, merge
worktree candidates into `main`, pull and merge its upstream changes, then push
`main`. Include completed work from other authors. Execute without another approval
round when the scope and delivery route are clear. Arguments narrow this default.
Creating or editing this skill does not invoke it.

Read the [Git Commit Push delivery rules](../git-commit-push/SKILL.md) before Git
writes. Reuse its scope, preservation, staging, candidate checks and remote readback
rules. This workflow owns the broader default and sequence below; the sibling's
current-branch push default does not apply. Use the repository's supported landing
path when it has one. Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md)
to delivery evidence, without closing tasks merely because their commits shipped.

## Fast path

1. **Inventory once.** Resolve the canonical checkout with
   `git worktree list --porcelain`. Inspect status, staged and unstaged diffs,
   untracked files, branch tips, repository policy and actual worker/session activity
   across every registered worktree. “Active worktrees” means registered working
   copies, not permission to interrupt live writers. Pin candidate SHAs and record
   each worktree as eligible, already integrated, live, unfinished, or unavailable.
   Check dirty submodules separately under the delivery rules. Continue when every
   worktree and changed path has a classification.
2. **Resolve the destination.** Use local `main` and its configured upstream and push
   destination. Verify that these identify the intended remote `main`; inspect Git's
   push configuration instead of assuming `origin`. Fetch the selected upstream
   before curating changes, so stale local files cannot replace newer remote work.
   If `main` is absent, destinations disagree, or branch policy forbids the route,
   ask one precise question. Continue when source, destination and route are explicit.
3. **Commit all eligible changes.** Include staged, unstaged and untracked changes
   in scope, including completed changes in idle dirty worktrees. Establish delivery
   ownership from provenance, completion and current activity, not file age alone.
   Check each worktree's instructions and recheck HEAD, index and file baselines
   before staging explicit paths. Keep tests and docs with their implementation.
   Use the sibling's commit and candidate-check rules in local-only mode here;
   do not push each worktree branch. Leave live, protected, unfinished or unverifiable
   changes untouched and list their paths. Continue when each eligible change has
   a verified commit SHA, or an exact exclusion reason.
4. **Assemble main.** Serialize integration through the supported repository path.
   Merge each eligible pinned tip in dependency order, oldest first when independent.
   Verify already-integrated work by ancestry or equivalent content before skipping it.
   The [worktree sweep reference](../git-commit-push/references/worktree-sweep.md)
   supplies inventory and clean-candidate merge mechanics. Its dirty-worktree skip
   applies to changes not committed in step 3; its cleanup phase is not part of
   `/push`. Preserve locked, detached, prunable and live worktrees. Resolve mechanical
   conflicts only when the accepted behavior is clear. Abort an unresolved merge,
   report `Merge pending`, and continue independent candidates whose dependencies
   still hold. Continue when every candidate is integrated or explicitly pending,
   with no merge in progress.
5. **Pull and merge upstream.** Follow the
   [pull and merge procedure](../git-commit-push/references/pull-merge.md) for `main`:
   fetch, fast-forward when possible, otherwise merge. Preserve both sides' accepted
   behavior and tests. An unresolved upstream conflict stops publication. Honor
   explicit `no pull`, `no sync` or `ff-only` restrictions and report their effect.
   Continue when the assembled candidate includes the fetched upstream, or the
   caller's narrower sync requirement is met.
6. **Check once per candidate.** Run the repository's required checks on the final
   assembled tree, including the affected union across local and incoming changes.
   Reuse passing receipts only when their source, dependency and tool inputs still
   match. Parallelize independent read-only probes and checks; serialize shared Git
   writes. A required independent review stays required. Continue only after all
   required checks and review passed for the exact candidate.
7. **Push and prove.** Push only `main` to the verified destination with an explicit
   refspec. Read back the remote ref and prove inclusion of the delivered commits.
   If a concurrent push rejects it, fetch, merge and rerun affected checks before a
   normal retry. Stop repeated retries and report the moving ref. Continue when
   remote inclusion is proven, or the precise publication blocker is recorded.

## Restrictions

`dry run`, `audit`, `read-only` and `questions only` permit inspection, not Git
writes. `no commit` leaves dirty changes untouched but permits delivery of eligible
existing commits unless further restricted. `no push` permits local delivery only.
A path or topic limit also limits worktree candidates and their ancestors; include
only attributable commits when a branch carries unrelated history. If a candidate
cannot be separated safely, report it instead of widening scope.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| “All means stage everything blindly.” | All eligible changes still require scope, secret and completion checks. |
| “Clean means the worker finished.” | Check actual activity and completion before taking delivery ownership. |
| “Faster means skip the final gate.” | Reuse matching evidence; check changed inputs on the assembled candidate. |
| “One conflict blocks every branch.” | Keep it pending and deliver verified independent work as a partial result. |

## Red Flags

- Committing in a worktree while its writer is live or its ownership is unknown.
- Calling a partial delivery complete while worktrees remain pending.
- Claiming a push from a local merge or a successful check.
- Repeatedly running the same gate against unchanged inputs without a reason.

## Boundaries

- Use `/git-commit-push` for current-branch delivery or pull-only work; `/push`
  defaults to repository-wide delivery into `main`.
- Preserve files, worktrees, branches, scheduler state and task status. This command
  does not authorize cleanup, forced staging of ignored files, stash, reset, rebase,
  force-push, protection changes, deployment or release.
- Stop on unresolved product decisions or required gate failures. Preserve remote
  protection and existing review requirements instead of bypassing them.

**Done when:** all eligible changes are committed, candidate worktrees are accounted
for, upstream sync and checks are evidenced, and remote main inclusion is verified;
otherwise report partial delivery or the exact blocker without claiming completion.

**Receipt:** committed SHAs; worktrees merged or kept with reasons; upstream sync;
checks and reused evidence; local main and remote SHAs; remaining paths and next action.
