---
name: push
description: "Save this checkout, pull main, then push main."
license: MIT
---

# Push

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/push` saves eligible changes in the invoking checkout only, pulls `main` from its
verified upstream, then delivers to `main`. Include ordinary in-scope changes from
other authors and already-merged upstream Orbi changes. Other local worktrees are
out of scope. Remote work is inspected and reported without taking it over
when another coordinator owns it. Do not wait for a second approval round: when the
destination and the landing route are explicit, commit, pull and push. Arguments
narrow this default; without them all three actions happen. Creating or editing this
skill does not invoke it.

Read the [Git Commit Push delivery rules](../git-commit-push/SKILL.md) before Git
writes. Reuse its scope, preservation, staging, candidate checks and remote readback
rules within this checkout's scope. This workflow owns the default and sequence
below; neither the sibling's current-branch push default nor its sweep applies.
Use the repository's supported landing path: push to `main` directly when branch
policy allows it, otherwise push the candidate branch, open the pull request and
merge it under the existing gates.
Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to delivery evidence,
without closing tasks merely because their commits shipped. The
[shared freshness contract](../shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership)
owns mode effects, unknown coverage and coordinator ownership; apply it first.

## Fast path

1. **Inventory once.** Identify the invoking checkout with `git rev-parse --show-toplevel`.
   A linked checkout is the source, not permission to inspect or modify the canonical
   checkout. Use only minimal Git metadata for landing/placement and registered-root
   boundaries (`git worktree list --porcelain -z`); do not discover/classify sibling
   contents, status, activity or unique tips. Do not call the sweep helper, directly
   or through another workflow. Resolve the intended base, configured upstream and
   push destination from Git configuration and repository policy, including
   fetch/push URL and ref mappings; do not assume `origin` or a branch-name prefix.
   Inspect status, staged/unstaged diffs, eligible untracked files, submodules and
   actual ownership only inside the invoking checkout, excluding nested registered
   worktree roots before file reads or recursive enumeration. Treat those roots as
   boundaries, never untracked content to stage. Pin the in-scope candidate SHA and
   HEAD/index/file baselines. A clean invoking checkout does not prove remote `main`
   is current; continue upstream and remote discovery.

   Read GitHub issue/PR evidence for that verified repository with pagination to
   exhaustion, not a default first page or only locally registered branches. Include
   open PRs and relevant merged/closed PRs linked to discovered candidate
   issues/refs. Inspect links, bodies/comments, run/coordinator metadata, labels,
   check/review state and ownership evidence. Names containing `orbi` or bot authors
   are search hints only, not attribution. Record URLs, observed state/time,
   base/head/merge SHAs, current owner and the evidence tying each issue, PR and
   in-scope local ref together, deduplicated by repository/issue/PR identity. Remote
   discovery does not authorize sibling checkout probes.

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
   decides the classification. These holds do not block saving independent eligible
   local changes. API errors/rate limits leave a partial
   inventory, never an empty backlog; name which pages/states remain unverified.
   Continue when coverage and exclusions are explicit.

2. **Save all eligible changes.** Include staged, unstaged, deleted and ordinary
   non-ignored untracked files in the invoking checkout only.
   No separate completion note or marker is required. Verify provenance, intended
   scope and actual worker/session inactivity under that checkout's instructions;
   file age or a quiet status alone does not prove released ownership. For this
   `/push` scope, ordinary changes need verification, not the sibling's completed-work
   requirement. Project ownership rules and narrower requests still win.

   Commit all eligible changes locally before deciding what can ship. If an edit
   can be saved but not published, commit it on a separate local checkpoint
   branch. Record the publication blocker. Do not include that checkpoint in
   the candidate for `main`. A pending review or merge gate alone is not a
   reason to leave eligible edits staged. This does not waive commit-time checks
   or the exclusions below.

   Recheck HEAD, index bytes and file contents against the inventory immediately
   before staging explicit paths. A changed baseline means `Save pending`: preserve
   the affected paths, report the drift, and re-inventory ownership and bytes before
   staging. Keep tests and docs with the implementation. Use the sibling's explicit
   staging, secret-scan, commit and candidate-check rules in local-only mode here.
   Verify the staged set matches the eligible paths, including deletions, and held
   paths remain unchanged by this operation.
   Keep these drift checks and explicit-path staging inside the invoking checkout;
   exclude nested registered roots and their descendants, even if not ignored.

   Exclude credentials, secrets, private runtime state, ignored untracked output,
   active or uncertain ownership, and any path under a pause or recovery hold.
   Preserve these paths without staging them, and report each path and reason
   without exposing contents. Do not alter pre-existing excluded index entries;
   isolate the eligible commit or hold it if they cannot be safely separated.
   An open Orbi PR remains owned by its coordinator, even in an idle worktree.
   Continue when every in-scope change has a verified commit SHA or an exact exclusion reason.

3. **Pull main.** Follow the
   [pull and merge procedure](../git-commit-push/references/pull-merge.md) for `main`:
   fetch the verified upstream, fast-forward when possible, otherwise merge. The
   commit in step 2 comes first, because uncommitted changes that also changed
   upstream block a safe pull. Preserve local accepted changes and incoming tests.
   Resolve mechanical conflicts only when the accepted behavior is clear. An
   unresolved conflict stops publication: abort it, report `Merge pending`, and keep
   the local commits. Integrate only the invoking checkout's attributable history
   and verified upstream, not sibling tips. Use the existing isolated candidate/PR
   route when in-place landing is unsafe or `main` is checked out elsewhere; do not
   probe or synchronize that other checkout. Minimal registration metadata is enough
   to choose isolation. If policy leaves no safe route, preserve the saved work and
   report the exact landing blocker and repair action. Honor explicit `no pull`,
   `no sync` or `ff-only` limits instead of falling back to a merge. Continue when
   the candidate includes the fetched upstream, with no merge in progress.

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
| “All means stage everything blindly.” | Stage only verified eligible paths; preserve and report exclusions. |
| “Other worktrees might have changes, so inspect them.” | Local scope is the invoking checkout only; use explicit `/git-commit-push all` for the existing sweep. |
| “Pull first, commit later.” | Uncommitted changes that also changed upstream block the pull; commit first. |
| “An open Orbi PR blocks my local commit.” | Its head stays with its coordinator; independent eligible local work still ships. |
| “The PR is open, so delivery is done.” | Delivery is proven inclusion in remote `main`. |
| “One conflict blocks every branch.” | Deliver verified independent work as a partial result. |

## Red Flags

- Probing sibling files/status/activity, staging a nested worktree, or importing a sibling tip.
- Reporting inventory instead of committing, pulling and pushing.
- Claiming delivery from a local commit, an open pull request or a green check.
- Force-push, protection bypass, or repeated pushes against a moving ref.
- Pulling over uncommitted changes that also changed upstream.

## Boundaries

- Use `/git-commit-push` for current-branch delivery or pull-only work, and explicit
  `/git-commit-push all` for its existing sweep. `/push` saves eligible invoking-checkout
  changes, pulls verified `main` and delivers to `main` without inspecting other worktrees.
- Preserve files, worktrees, refs, scheduler state and task status. No cleanup,
  forced ignored-file staging, stash, reset, rebase, force-push, protection change,
  deployment or release is authorized. Observation does not activate paused Orbi.
- Stop for missing credentials, an unresolved conflict, a failed required gate,
  unsafe landing route or unresolved product decision; report the exact blocker
  and the next action.

**Done when:** every in-scope change is committed or listed with an exact exclusion reason,
the candidate includes the pulled upstream `main`, required checks passed on that
tree, and remote `main` contains the delivered commits; otherwise report partial
delivery or the exact blocker without claiming completion.

**Receipt:** local scope (invoking checkout path); other worktrees were not inspected
(not claimed clean or shipped); committed SHAs; in-scope excluded paths and reasons;
pulled upstream and its SHAs; candidate issue/PR URLs with classification and owner;
checks and reused evidence; pull request URL when policy requires one; local `main`
ref (Git metadata only) and remote `main` SHAs; remaining in-scope paths and next action.
