---
name: push
description: "Save all changes, pull main, then push main."
license: MIT
---

# Push

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/push` is the repository-wide delivery default: save every change in the checkout,
pull `main` from its verified upstream, then push `main`. Include completed work from
other authors and the already-merged upstream Orbi changes that the pull brings in.
Remote candidates are inspected and reported, without taking it over when another
coordinator owns the work. Do not wait for a second approval round: when the
destination and the landing route are explicit, commit, pull and push. Arguments
narrow this default; without them all three actions happen. Creating or editing this
skill does not invoke it.

Read the [Git Commit Push delivery rules](../git-commit-push/SKILL.md) before Git
writes. Reuse its scope, preservation, staging, candidate checks and remote readback
rules. This workflow owns the broader default and sequence below; the sibling's
current-branch push default does not apply. Use the repository's supported landing
path: push to `main` directly when branch policy allows it, otherwise push the
candidate branch, open the pull request and merge it under the existing gates.
Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to delivery evidence,
without closing tasks merely because their commits shipped. The
[shared freshness contract](../shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership)
owns mode effects, unknown coverage and coordinator ownership; apply it first.

## Fast path

1. **Inventory once.** Resolve the actual repository and canonical checkout with Git
   identity and `git worktree list --porcelain`. Resolve the intended base, configured
   upstream and push destination from Git configuration and repository policy,
   including fetch/push URL and ref mappings; do not assume `origin` or a branch-name
   prefix. Inspect status, staged/unstaged diffs, untracked files, submodules, branch
   tips and actual worker/session activity across every registered worktree. Pin each
   candidate SHA and baseline. A clean current checkout is not a repository-wide NO-OP.

   Read GitHub issue/PR evidence for that verified repository with pagination to
   exhaustion, not a default first page or only locally registered branches. Include
   open PRs and relevant merged/closed PRs linked to discovered candidate
   issues/refs. Inspect links, bodies/comments, run/coordinator metadata, labels,
   check/review state and ownership evidence. Names containing `orbi` or bot authors
   are search hints only, not attribution. Record URLs, observed state/time,
   base/head/merge SHAs, current owner and the evidence tying each issue, PR and local
   ref together, deduplicated by repository/issue/PR identity.

   | Classification | Action |
   | --- | --- |
   | merged upstream | Confirm merge inclusion in verified default-branch ancestry; take it through the pull, not the stale PR head. A merged flag alone is insufficient, including merges to another base. |
   | open/owned | Leave with its coordinator even if checks pass; report issue/PR URL, owner/gate and next action. Do not cherry-pick or merge its head locally. |
   | failed/blocked | Preserve the work and its recovery inputs; report the exact failure/pause and the coordinator repair action. |
   | closed-unmerged | Keep untouched; report closure and the owner decision needed before renewed delivery. |
   | already included/equivalent | Prove ancestry or content/patch equivalence against the target; skip duplicate integration and cite the proof. |
   | unavailable/unknown | Preserve unverified candidates; report the missing ownership/source evidence and the input needed to resolve it. |

   For overlapping states, delivered ancestry/equivalence settles code inclusion;
   otherwise closed-unmerged, explicit failure/block/pause, open/owned, then unknown
   decides the classification. Classification governs remote take-over only: it never
   decides whether local changes are saved. API errors/rate limits leave a partial
   inventory, never an empty backlog; name which pages/states remain unverified.
   Continue when coverage and exclusions are explicit.

2. **Save all changes.** Commit every staged, unstaged and untracked change in the
   checkout, and the completed changes in idle dirty worktrees. Establish ownership
   from provenance, completion and current activity, not file age alone. An open Orbi
   PR remains owned by its coordinator. Check each worktree's instructions and recheck
   HEAD, index and file baselines before staging explicit paths. Keep tests and docs
   with the implementation. Use the sibling's commit and candidate-check rules in
   local-only mode here; do not push each worktree branch. Leave credentials, secrets
   and files that a live writer is still editing uncommitted, and list their paths.
   Continue when every remaining change has a verified commit SHA, or an exact
   exclusion reason.

3. **Pull main.** Follow the
   [pull and merge procedure](../git-commit-push/references/pull-merge.md) for `main`:
   fetch the verified upstream, fast-forward when possible, otherwise merge. The
   commit in step 2 comes first, because uncommitted changes that also changed
   upstream block a safe pull. Preserve local accepted changes and incoming tests.
   Resolve mechanical conflicts only when the accepted behavior is clear. An
   unresolved conflict stops publication: abort it, report `Merge pending`, and keep
   the local commits. Use an isolated candidate when the canonical checkout is
   shared. An eligible local worktree tip merges through the same path in dependency
   order, oldest first, using the
   [worktree sweep mechanics](../git-commit-push/references/worktree-sweep.md);
   its cleanup phase is not part of `/push`. Honor explicit `no pull`, `no sync` or
   `ff-only` limits instead of falling back to a merge. Continue when the candidate
   includes the fetched upstream, with no merge in progress.

4. **Check the exact candidate.** Run the repository's required checks on the
   assembled tree for the affected union of local and incoming changes. Reuse passing
   receipts only when source, dependency and tool inputs still match. Parallelize
   independent read-only probes/checks; serialize shared Git writes. A required
   independent review stays required. Continue only after checks and review passed
   for the exact candidate.

5. **Push main and prove it.** Push the candidate to the verified destination with an
   explicit refspec, through the repository's supported route. Push `main` directly
   when policy allows it; otherwise push the candidate branch, open the pull request
   and merge it. Refresh the upstream pin immediately before publication; if it
   advanced, merge again through the same path and rerun only affected checks. Read
   back the remote ref and prove delivered commit inclusion in remote `main`. A
   normal push rejects a race: reconcile once through the same path, never force or
   loop retries. A second advance is a precise moving-ref hold. Continue when
   inclusion is proven, or the exact publication blocker is recorded.

## Restrictions

Only an explicit narrowing restricts this default: `dry run`, `audit`, `read-only`
and `questions only` permit inspection, not Git writes, including fetch; `no commit`
saves nothing and permits delivery of existing commits only; `no pull` and `no sync`
skip step 3; `no push` stops before remote writes; a path or topic limit narrows
steps 2 to 5 together. Without such a limit the command commits, pulls and pushes.
A path/topic limit also limits candidate ancestors; select only attributable commits
when a branch carries unrelated history, and report an inseparable candidate instead
of widening scope. No PR checkout, remote-ref deletion or live-worker takeover is
part of this skill.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| “Classification is the deliverable.” | Inventory classifies; the command saves, pulls and pushes in the same run. |
| “All means stage everything blindly.” | Every change is saved, but credentials and live-edited files stay out and are listed. |
| “Pull first, commit later.” | Uncommitted changes that also changed upstream block the pull; commit first. |
| “An open Orbi PR blocks my local commit.” | Its head stays with its coordinator; completed local work still ships. |
| “The PR is open, so delivery is done.” | Delivery is proven inclusion in remote `main`. |
| “One conflict blocks every branch.” | Deliver verified independent work as a partial result. |

## Red Flags

- Reporting inventory instead of committing, pulling and pushing.
- Claiming delivery from a local commit, an open pull request or a green check.
- Force-push, protection bypass, or repeated pushes against a moving ref.
- Pulling over uncommitted changes that also changed upstream.

## Boundaries

- Use `/git-commit-push` for current-branch delivery or pull-only work; `/push`
  saves every change, pulls `main` and pushes `main`.
- Preserve files, worktrees, refs, scheduler state and task status. No cleanup,
  forced ignored-file staging, stash, reset, rebase, force-push, protection change,
  deployment or release is authorized. Observation does not activate paused Orbi.
- Stop only for credentials, an unresolved conflict, a failed required gate or an
  unresolved product decision; report the exact blocker and the next action.

**Done when:** every change is committed or listed with an exact exclusion reason,
the candidate includes the pulled upstream `main`, required checks passed on that
tree, and remote `main` contains the delivered commits; otherwise report partial
delivery or the exact blocker without claiming completion.

**Receipt:** committed SHAs; excluded paths and reasons; pulled upstream and its SHAs;
candidate issue/PR URLs with classification and owner; checks and reused evidence;
pull request URL when policy requires one; local and remote `main` SHAs; remaining
paths and the next action.
