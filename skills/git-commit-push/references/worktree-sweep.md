# Worktree sweep

The inbound twin of a ship: bring every finished worktree back into the base branch.
A worktree is cheap to create and easy to forget, and a forgotten one holds planning and
implementation that no later decision can see. The sweep finds them, merges the finished
ones, and leaves everything ambiguous exactly where it is.

## States

| State | Meaning | Sweep action |
| --- | --- | --- |
| `merged` | HEAD is already contained in the base branch | close it out if clean |
| `unmerged-clean` | commits are not on the base branch, tree is clean | merge it |
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
   run again when it is idle. A dirty worktree is the owner's call: report the paths, or
   archive it with `worktree_closeout.py --archive`, which keeps a commit of the whole
   tree under `refs/archive/worktrees/` before removing anything.
   **Pass when:** each non-candidate names its reason and its next step.
3. **Merge the candidates.** `--apply` merges the clean, unmerged ones one at a time,
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
5. **Close out.** For worktrees that are now merged and clean, run
   `pi-autowork/engine/worktree_closeout.py <canonical> --worktree <path> --apply`. It
   removes a worktree only after its own safety checks and never with `--force`.
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
- No rebase, no force, no history rewrite, no branch deletion. `worktree_closeout.py`
  deletes a branch only with `git branch -d` after the merge is proven.
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
Next: owner commits the 3 dirty worktrees, or archive them, then re-run --apply
```
