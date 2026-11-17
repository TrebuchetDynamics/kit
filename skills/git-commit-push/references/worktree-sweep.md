# Worktree sweep

The inbound twin of a ship: bring every finished worktree back into the base branch.
A worktree is cheap to create and easy to forget, and a forgotten one holds planning and
implementation that no later decision can see. The sweep finds them, merges the finished
ones, and leaves everything ambiguous exactly where it is.

Apply the [shared freshness/ownership contract](../../shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership)
before inventory. Read-only/audit never fetches or runs `--apply`. Resolve the
verified repository/base/upstream/destination under repository policy, not remote
or branch naming. A clean tree is a mechanical condition, not delivery eligibility.
Orbi-owned PRs/checkouts, live or unknown owners, failed/blocked/paused and
closed-unmerged work stay with their coordinator. Report their URL, reason and next
action; a passing check does not release ownership. Use [/push](../../push/SKILL.md)
for remote issue/PR discovery and already-landed upstream changes.

## States

| State | Meaning | Sweep action |
| --- | --- | --- |
| `merged` | HEAD is already contained in the base branch | close it out if clean |
| `unmerged-clean` | commits are not on the base branch, tree is clean | verify scope/completion/ownership/gates before merge |
| `unmerged-dirty` | commits are not on the base branch, and the tree has changes | report it to its owner; never commit it |
| `detached` | release or review checkout with no branch | leave it |
| `locked` | Git holds a worktree lock | leave it |
| `prunable` | the directory is gone but the registration remains | report the exact `git worktree prune` command |

## Procedure

1. **Inventory read-only.** Run `worktree_sweep.py <repo>` and read the table. It lists
   every registered worktree, its branch, how far ahead of the base it is, how many dirty
   paths it holds and how long its Git metadata has been quiet.
   **Pass when:** every worktree has a state and no file has changed.
2. **Triage.** Count the states. Recent activity (default 5 minutes) means another
   session may still be writing, so the sweep reports it as `skipped` instead of merging;
   verify actual ownership before applying; age alone proves no release. A dirty
   worktree is the owner's call: report its paths and preserve it.
   **Pass when:** each non-candidate names its reason and its next step.
3. **Merge the eligible candidates.** Refresh relevant PR/ownership evidence and
   verify pinned source/base/destination immediately before integration. Include
   landed changes via verified upstream using [normal sync](pull-merge.md), then
   reconcile affected checks/review if inputs moved. Never use an open PR head.
   `--apply` is only usable when its entire selected inventory is eligible: the
   helper's clean/age checks do not establish coordinator release. Otherwise use
   the existing manual clean-candidate merge path on eligible pins only, leaving
   worker checkouts untouched. It merges clean, unmerged ones one at a time,
   oldest commit first, with `git merge --no-ff <sha>` of the exact commit it classified.
   A conflict aborts that merge (`git merge --abort`) and the sweep continues, so one
   overlapping branch cannot block twenty independent ones.
   **Pass when:** each candidate is `merged` or `conflict`, and the canonical checkout has
   no merge in progress.
4. **Re-gate.** Run the repository's own check on the merged tree. Integrate only what
   passes; a regression caused by the batch is repaired or reverted with `git revert`
   against the merge commit that carried it, never by rewriting the base branch.
   **Pass when:** the check result names the merged revision, and every failure is
   attributed to a worktree.
5. **Close out.** The bundled executor helper is removed. `--remove` requires an
   explicit existing `--closeout` safety helper; otherwise it fails before merging.
   Apply [ownership and recovery checks](worktree-closeout.md) independently.
   Preserve existing legacy worktrees during removal; never use a force fallback.
   **Pass when:** each removed worktree is reported, and each kept one names its reason.
6. **Report.** Counts per state, merged branches, conflicts as `Merge pending`, kept dirty
   worktrees with paths, and the remaining next action.
   **Pass when:** a reader can tell which work is on the base branch and which is not.

## Rules

- Merge into the base branch only. The sweep refuses when the canonical checkout is on
  another branch, has uncommitted changes, or already has a merge in progress; it never
  moves your HEAD to make a merge possible.
- Never commit, stash, reset or discard another writer's uncommitted work. A dirty
  worktree is a message to its owner, not an obstacle to remove.
- No rebase, no force, no history rewrite, no automatic branch deletion. A supplied
  closeout helper must verify ownership and recovery evidence independently.
- Merge only worktrees classified as clean. A worktree you cannot classify is reported,
  not guessed.
- One conflict does not stop the sweep, and one sweep does not end the obligation: a
  branch left `Merge pending` stays in the report until it lands or its owner retires it.

## Report

```text
Worktree sweep: 77 worktrees; 30 unmerged-clean, 28 merged, 3 unmerged-dirty, 16 detached
Merged: 12 into main (oldest first); 1 conflict (autowork/TOOLSET-410) -> Merge pending
Kept: 3 dirty (paths listed); 16 detached release checkouts left alone
Checks: <command> on the merged tree, <result>
Next: coordinate the 3 dirty worktrees with their owners; preserve them until resolved
```
