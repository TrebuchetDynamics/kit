---
name: push
description: "Ship eligible local and landed Orbi changes."
license: MIT
---

# Push

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/push` is a repository-wide delivery request: commit all eligible changes, merge
eligible local worktree candidates, include already-merged upstream Orbi changes,
then publish to the repository's intended base (normally `main`). Include completed
work from other authors. Discover and report outstanding Orbi work on GitHub or in
other checkouts without taking it over. Arguments narrow this default. Creating or
editing this skill does not invoke it.

Read the [Git Commit Push delivery rules](../git-commit-push/SKILL.md) before Git
writes. Reuse its scope, preservation, staging, candidate checks and remote readback
rules. This workflow owns the broader default and sequence below; the sibling's
current-branch push default does not apply. Use the repository's supported landing
path, including PR protection. Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md)
to delivery evidence, without closing tasks merely because their commits shipped.
The [shared freshness contract](../shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership)
owns mode effects, unknown coverage and coordinator ownership; apply it first.

## Fast path

1. **Inventory local and remote evidence.** Resolve the actual repository and
   canonical checkout with Git identity and `git worktree list --porcelain`.
   Resolve the intended base, configured upstream and push destination from Git
   configuration and repository policy, including fetch/push URL and ref mappings;
   do not assume `origin` or a branch-name prefix. If destinations disagree, the
   base is absent or policy forbids the route, ask one precise question before writes.
   Inspect status, staged/unstaged diffs, untracked files, submodules, branch tips
   and actual worker/session activity across every registered worktree. Pin each
   candidate SHA and baseline. A clean current checkout is not a repository-wide NO-OP.

   Read GitHub issue/PR evidence for that verified repository with pagination to
   exhaustion, not a default first page or only locally registered branches. Use
   the host's supported read tools and verified API/CLI help for query fields and
   pagination. Include open PRs and relevant merged/closed PRs linked to discovered
   candidate issues/refs. Inspect issue/PR links, bodies/comments, run/coordinator
   metadata, current labels, check/review state and actual ownership evidence.
   Names containing `orbi` or bot authors are search hints only, not attribution.
   Include issue-only candidates without inventing a PR or head SHA. Record URLs,
   observed state/time, base/head/merge SHAs (absent or unavailable explicitly),
   current owner and the evidence tying each issue, PR and local ref together.
   Deduplicate by repository/issue/PR identity so the same work is classified once.

   | Classification | Action |
   | --- | --- |
   | merged upstream | Confirm merge inclusion in verified default-branch ancestry; integrate through upstream, not the stale PR head. A merged flag alone is insufficient, including merges to another base. |
   | open/owned | Leave with its coordinator, even if checks pass; report issue/PR URL, current owner/gate and pending next action. Do not cherry-pick or merge its head locally. |
   | failed/blocked | Preserve failed, blocked, paused or unfinished work and any recovery inputs; report the exact failure/pause and coordinator repair/resume action. |
   | closed-unmerged | Keep untouched; report closure and the owner decision needed before any renewed delivery. |
   | already included/equivalent | Prove ancestry or content/patch equivalence against the target; skip duplicate integration and cite the proof. |
   | unavailable/unknown | Preserve unverified candidates; report missing ownership/source/API evidence and the input needed to resolve it. |

   For overlapping states, delivered ancestry/equivalence settles code inclusion;
   otherwise closed-unmerged, explicit failure/block/pause, open/owned, then unknown
   determines the one classification. Keep coordinator lifecycle status separate
   from code inclusion. Classify eligible independent local work under the existing
   local rules; a remote candidate is not made eligible by a clean local checkout.
   API errors/rate limits leave a **partial inventory**, never an empty backlog.
   Retain discovered candidates and name which pages/states remain unverified.
   Continue verified Git sync and independent eligible work only under existing
   gates; unavailable required protection/review holds dependent publication. No
   retry loop or alternate credentials. Continue when coverage and exclusions are explicit.
2. **Verify upstream before curation.** In authorized delivery/sync mode only,
   fetch the verified configured upstream without pruning remote refs. Pin its
   observed base SHA and the destination SHA separately. Use these fresh inputs to
   compare local bytes and branch ancestry so stale copies cannot revert landed
   Orbi fixes or their tests. Read-only/audit/dry-run uses existing refs and permitted
   remote metadata only, reports freshness unknown, and stops before Git writes.
   Honor no-pull/no-sync limits. Continue when the allowed baseline is explicit.
3. **Commit all eligible local changes.** Include staged, unstaged and untracked
   changes in scope, including completed changes in idle dirty worktrees. Establish
   delivery ownership from provenance, completion and current activity, not file
   age alone. An open Orbi PR remains owned even in an idle checkout. Check each
   worktree's instructions and recheck HEAD, index and file baselines before staging
   explicit paths. Keep tests and docs with implementation. Use the sibling's commit
   and candidate-check rules in local-only mode here; do not push each worktree
   branch. Leave live, protected, unfinished or unverifiable changes untouched and
   list their paths. Continue when eligible changes have verified commit SHAs, or
   exact exclusion reasons.
4. **Assemble the base candidate.** Immediately before each integration, refresh
   relevant PR/ownership state and verify pinned local source, upstream base and
   destination inputs. A moved head or changed owner invalidates its eligibility;
   reclassify rather than using stale approval. If an open PR became merged, take
   it through upstream, never merge its former head a second time. If metadata is
   unavailable, retain that candidate as unknown and keep independent work separate.

   Serialize integration through the supported repository path. Follow the
   [pull and merge procedure](../git-commit-push/references/pull-merge.md) to include
   landed upstream first: fast-forward when possible, otherwise ordinary merge.
   Preserve local accepted changes and incoming tests. Merge only eligible pinned
   local tips in dependency order, oldest first when independent. The
   [worktree sweep reference](../git-commit-push/references/worktree-sweep.md)
   supplies inventory and clean-candidate merge mechanics, not proof of eligibility
   or release. Its cleanup phase is not part of `/push`. Preserve locked, detached,
   prunable and live worktrees, including Orbi workers. Use an isolated candidate
   when the canonical checkout is shared/dirty; never refresh another writer's tree.
   Verify already-integrated work by ancestry or equivalent content before skipping.
   Abort unresolved merges and report `Merge pending`; continue independent candidates
   whose dependencies still hold. An unresolved upstream conflict holds publication.
   Respect ff-only/no-sync/no-pull limits rather than falling back to a merge.
   Continue when each candidate is included or explicitly pending, with no merge in progress.
5. **Check the exact candidate.** Run required checks on the assembled tree for the
   affected union of local and incoming changes. Reuse passing receipts only when
   source, dependency and tool inputs still match. Parallelize independent read-only
   probes/checks; serialize shared Git writes. Required independent review remains
   required. Continue only after checks and review passed for the exact candidate.
6. **Refresh, publish and prove.** Immediately before publication, refresh relevant
   PR/ownership state again and verify source, base and destination pins. If upstream
   advanced, rebuild through the same normal merge path and rerun only affected
   candidate-bound checks and required review. Record selected and final SHAs. If
   ownership changed, hold/reclassify dependent work rather than publishing stale
   inputs. Never bypass an unavailable required gate. Push the candidate to the
   verified destination with an explicit refspec using the supported PR route when
   required; a task-branch push is not base delivery. Read back the remote ref and
   prove delivered commit inclusion in the intended base. Normal push rejects a
   race: reconcile once through the same path, never force or loop retries. A second
   advance is a precise moving-ref hold. Continue when inclusion is proven or the
   exact publication blocker is recorded.

## Restrictions

`dry run`, `audit`, `read-only` and `questions only` permit inspection, not Git
writes, including fetch. `no commit` leaves dirty changes untouched but permits
eligible existing commits unless further restricted; it does not authorize a merge
commit. `no push` permits local delivery only. A path/topic limit also limits
candidate ancestors; select only attributable commits when a branch carries
unrelated history. If inseparable, report it instead of widening scope.
No PR checkout, remote ref deletion or live-worker takeover is part of this skill.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| “All means stage everything blindly.” | Eligible work still needs scope, secret, completion and ownership checks. |
| “Clean means the worker finished.” | Verify actual activity and coordinator ownership, not file age. |
| “A passing Orbi PR can be merged here.” | Its coordinator still owns PR/review gates; take only landed code through upstream. |
| “API failure means no Orbi work.” | Discovery is partial/unknown; preserve candidates and state missing coverage. |
| “One conflict blocks every branch.” | Deliver verified independent work as a partial result. |

## Red Flags

- Committing in a live or unknown writer's worktree, or importing an owned PR head.
- Calling a partial inventory/delivery complete while candidates remain pending.
- Claiming publication from a local merge or check without remote inclusion proof.
- Reusing stale pins/reviews, or repeating gates against unchanged inputs.

## Boundaries

- Use `/git-commit-push` for current-branch delivery or pull-only work; `/push`
  defaults to repository-wide delivery into the verified intended base.
- Preserve files, worktrees, refs, scheduler state and task status. No cleanup,
  forced ignored-file staging, stash, reset, rebase, force-push, protection change,
  deployment or release is authorized. Observation does not activate paused Orbi.
- Stop dependent work on unresolved product decisions or required gate failures.
  Pending Orbi work stays with its coordinator; independent eligible work can ship.

**Done when:** eligible local work and incoming landed changes are accounted for,
checks/review and remote base inclusion are evidenced, and pending Orbi work and
inventory gaps are reported; otherwise report partial delivery or the exact hold.

**Receipt:** repository/base/upstream/destination; local commits versus incoming landed
changes; candidate issue/PR URLs, classification, owner and reason/next action;
observed source/base/head/merge and selected/final SHAs; checks/review and reused
receipts; remote inclusion proof; remaining paths and local checkout synchronization.
A successful partial shipment never means every Orbi change landed.
