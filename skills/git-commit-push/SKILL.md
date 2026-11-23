---
name: git-commit-push
description: "Commit current branch, sync and push its upstream."
version: 2.1.1
license: MIT
metadata:
  hermes:
    tags: [git, commit, push, pull, merge, sync, delivery, worktree, fleet]
    related_skills: [lgtm, ponytail-review, systematic-debugging]
---

# Git Commit Push

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Adapted from an earlier TrebuchetDynamics delivery workflow.
Merged with the fleet's shared-worktree rules and, since 2.0.0, with the former `git-pull-merge` skill: one skill delivers changes out
(commit, push) and brings them in (pull, merge).

Ship finished work without turning delivery into another project. Local changes are the
delivery queue, not a reason to stop and ask. Prefer direct execution for a bounded
stage/gate/commit sequence; delegate only when substantial ownership or dependency
analysis needs isolation. Do not add another reviewer or repeat a completed gate
merely because delivery moved from a worker to its parent. Verify the candidate
identity and existing receipts first; unchanged evidence can satisfy that handoff.

## When this applies

- The user asks to commit, push, or ship ("commit and push", "ship it", "push that").
- `/git-commit-push` (CLI) or `/git_commit_push` (Telegram) was invoked: that invocation **is** the ship request. Any text after the command narrows scope (paths, topic, "audit", "dry run", "no push", "no pull").
- **Every ship also syncs.** By default the branch is pulled and merged with its upstream
  before pushing (step 6), so a ship leaves local and remote equal. "no pull", "no sync" or
  "ff-only" narrows it. Fast-forward-only/no-merge routes permit fast-forward sync,
  not merge commits; audit permits no Git writes. The autonomous local-only
  agent-branch route still grants no sync or publication authority.
- LGTM accepts a checkpoint that recommended or explicitly offered commit/push (see the
  `lgtm` skill). A generic LGTM after an implementation report that did not offer shipping
  never implies shipping.
- Audit: the user asks for delivery status, a dry run, or "what would you commit". Do not
  stage, commit, or push.
- **Pull and merge only:** the user asks only to pull, sync, "update from origin/main" or
  merge a branch or PR into the current one, or the text after `/git-commit-push` starts with
  `pull`, `sync` or `merge` (for example `/git-commit-push merge agent/example/t_1234`). Follow
  [pull and merge](references/pull-merge.md) instead of the ship path below; it pushes only
  when the request also asks for a push.

## Pick the delivery target first

Resolve the repository's branch policy before choosing any helper, worktree or
remote route. A main-only policy overrides this skill's agent-branch and delivery-PR
recipes: curate owned changes in the canonical checkout and use complete immutable
filesystem exports for QA, without creating branches or branch-based worktrees.
Recheck that policy after a user correction or resumed handoff; an earlier candidate
branch is preserved evidence, not permission to keep developing there.

Compare the permitted route with effective remote protection before expensive gates.
If main-only delivery conflicts with a PR requirement, ask only about that policy
conflict; do not create a PR or weaken protection under generic shipping authority.
When the owner explicitly authorizes removal of the PR requirement, remove only that
rule, preserve every other protection and verify the ruleset plus effective branch
rules. Follow [GitHub protection changes](references/github-protection.md).
On GitHub read both `branches/<branch>/protection` and `rules/branches/<branch>`: a
legacy "Branch not protected" does not exclude rulesets, and an auth/access error is
not absence of protection.
A successful protection change resolves only the delivery-route question: retain the
original commit/push/main-delivery obligation and continue candidate verification.

| Situation | Target | Push? |
|---|---|---|
| User explicitly asked to commit only | the checked-out branch, subject to repository branch policy | **no** |
| User explicitly asked to push, commit and push, or ship | the checked-out branch, then its upstream | yes |
| Authorized local slice, no explicit or standing publication authority | owned task branch under repository policy | **never** |
| Audit request | nothing | no |

No push means no remote writes, including branch pushes, PR creation or remote merges.
This limit propagates through every reference and handoff.

Interpret delivery verbs separately: a request to implement and commit authorizes a local commit, not publication. Do not infer push permission from the skill name, an upstream being configured, or a broad request to finish all plans. After a local-only commit, verify `git show --stat HEAD` and repository status; omit remote-write readback because no remote write occurred (freshness inspection uses existing refs and permitted remote metadata; fetch is a write and needs authorized sync).

A repeated commit-only request after you disclosed failing checks authorizes a local
checkpoint, not a repair project: record known failures and unrun checks in the message
and report, claim no readiness, and still apply scope, live-writer, secret, preservation
and hook rules (repository-mandated commit gates stay binding). A later ship request must
reconcile fresh upstream and pass the candidate-bound gates.

Before probes, apply the [shared freshness and ownership contract](../shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership).
It owns mode effects, verified remote selection and coordinator retention, including
open Orbi PRs whose checks pass. Use [/push](../push/SKILL.md) for repository-wide
remote discovery and landed Orbi synchronization. Refresh relevant PR/ownership
state and verify source/base/destination pins immediately before integration and
publication; rebuild changed upstream through normal merge and affected checks/review.

**Scope is authorization, not authorship.** An explicit repo-wide ship request covers
all eligible changes in requested scope, including completed work from other agents or
earlier sessions. Take delivery ownership after checking provenance, intended scope,
completion, dependencies, secrets and candidate-bound verification; authorship alone
never excludes changes or yields NO-OP. Do not ask again merely because the implementer
is someone else or no card exists. A path/topic allowlist stays narrow, and an
autonomous worker/card without explicit repo-wide authorization remains limited to its
owned slice. Local-only requests never authorize push; audit never authorizes Git
writes. Repo-wide authorization does not override a live writer/lease, unfinished work,
unapproved product scope, secrets or missing verification. A generic "commit all" does
not revoke a specific earlier KEEP/preservation decision: resolve it before staging bulk
deletions. For accumulated/concurrent changes or uncertain provenance, load
[shared-worktree safety](references/shared-worktree-safety.md) before staging;
it owns the detailed cross-agent and shared-index procedures.

The executor's card-branch helper is removed. Use the repository's ordinary
owned-branch commit workflow or the [temporary-index safety procedure](references/shared-worktree-safety.md)
when explicitly authorized. Never change another writer's HEAD, index or dirty work.

## Fast path

1. **Inspect once.**
   - If the dirty set disappears or changes before committing, re-read `HEAD`, status
     and the exact remote ref: attribute another writer's commit and verify its scope
     instead of making an empty or duplicate commit. New uncommitted edits do not
     invalidate a gate on an unchanged immutable commit, but stay excluded and
     reported, never called clean.
   - Read repo instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING`), then run
     `git status --short --branch`, `git diff --stat`, `git diff --cached --stat`, and
     `git status --porcelain --untracked-files=all`. `git diff --stat` does not list untracked files.
   - For authentication or browser-login blockers, follow [hosting authentication readiness](references/hosting-authentication.md) before repeating a login or diagnosing missing credentials. Check each required host separately; public fetch access does not prove authenticated push or CI/API access. Do not claim that a browser flow started until an authorization URL, device prompt or callback listener is actually observed.
   - Check upstream: `git rev-parse --abbrev-ref @{u}` and `git rev-list --left-right --count @{u}...HEAD`.
     The first number counts commits reachable from the first argument only, the second from the
     second only. Label them from the expression you typed, not from habit: `@{u}...HEAD` prints
     behind/ahead, `HEAD...origin/main` prints ahead/behind — reading the pair the other way round
     reports a branch you are behind as one you are ahead of.
   - For a changed submodule, compare `git -C <path> rev-parse HEAD` with its upstream, then
     compare that nested commit to the superproject's committed pointer (`git rev-parse HEAD:<path>`)
     and index pointer (`git ls-files -s -- <path>`). Do not use `git rev-parse <path>` as the
     submodule revision: a filesystem path is not a Git ref. Stage the gitlink explicitly and
     verify the staged SHA equals the intended nested `HEAD` before committing.
   - Bind every Git probe to its intended checkout (explicit `cwd`/`-C`) and assert
     `git rev-parse --show-toplevel` before recording HEAD/index/status baselines; record
     index bytes (`git rev-parse --git-path index`) before any mutation. Equal status does
     not prove equal bytes; a misrouted baseline makes that preservation claim unverified.
   - For large dirty sets capture NUL-delimited inventory and diffs privately and summarize
     programmatically; see step 1 of [shared-worktree-safety.md](references/shared-worktree-safety.md).
   - Inventory completed agent/task branches and their unpublished commits in the same first
     pass, so an unsafe checkpoint or live writer cannot hide independent reviewed work.
     A clean checkout level with its upstream is not a repo-wide NO-OP: list authorized
     refs with `git for-each-ref --no-merged <target>` and use `git cherry <target> <ref>`
     plus blob comparison, since cherry-picked work can be delivered under different
     commit IDs. Never restore an older branch snapshot over newer target code.
   - For a retained candidate, read its latest continuation and named gate/review
     receipts first: candidate, verdict, per-check exit codes, log paths and pending
     action. A stale `running` label cannot override a recorded failing check, nor an
     older "review pending" a later exact-source approval. Do not dump receipt trees or
     full process argv.
   - Apply an owner restoration decision only to the named subtree
     (`git restore --source=HEAD --staged --worktree -- <subtree>`, then verify its status);
     never extend it to siblings or untracked files, and re-baseline HEAD/index afterward.
   - Classify every path: **ship now**, **leave local** (with a concrete reason), **needs one
     owner decision**, or **red line**. What this conversation or card produced counts as evidence of ownership.
   - **A shared checkout that is behind its upstream is not automatically the delivery queue.**
     Several agents push from sibling checkouts, so a dirty path can hold an *older revision* of a
     file upstream has since changed — its worktree blob equal to an unmerged `agent/*` branch
     tip's blob and older than `<verified-upstream-ref>`'s. Committing or overlaying it reverts reviewed
     work. Resolve every path's bytes against `<verified-upstream-ref>` and the unmerged branch tips in
     one pass before shipping a behind tree; a superseded path is an owner decision, not a flush.
     Rehearse the landing in a scratch worktree (merge, `--abort` on conflict) so the question you
     ask is specific. Depth: [shared-worktree-safety.md](references/shared-worktree-safety.md).

2. **Separate eligible completed work from live or out-of-scope work.**
   - Preserve scheduler state during shipping: inspect the latest explicit pause/resume decision and current run activity, but do not pause a recurring job merely to obtain a staging window or reapply an older stop superseded by a later resume. Shipping authority is not scheduling authority. Exclude actively owned paths and qualify an independent slice, or report the precise remaining conflict.
   - For a partial research/document delivery, qualify the selected slice against a complete index export without relying on held narrative, review receipts or ledger transitions. Source-preserving tables can ship independently when their original inputs and coverage verify; leave review-status upgrades or completion claims local when their supporting evidence is still being written. Report a partial shipment, not a clean tree or completed parent task.
   - Check current ownership/continuation evidence and actual writer activity. Query
     Kanban only when this repository still uses it (`hermes kanban --board <board> list
     --status running --assignee <profile>`); an empty board or missing historical card
     does not prove writer release and is never a delivery prerequisite.
   - Path age: `now=$(date +%s); for f in <paths>; do echo "$(( (now - $(stat -c %Y "$f")) / 60 ))m $f"; done`.
     A path written in the last few minutes, while a card owning that area is running, is
     mid-write. Exclude it and name it; it stays dirty for its owner's commit.
   - A finished card's own files: `git diff --name-only $(git merge-base HEAD agent/<p>/<card>)..agent/<p>/<card>`.
     A path listed there establishes provenance, not an exclusion. Under explicit repo-wide
     authorization, compare its bytes with the target and include completed unshipped work
     after the same scope and verification checks; a card-branch commit is not proof it
     already reached the requested target.
   - A *running* card's own files: read its body (`hermes kanban show <id>`) and its latest run
     summary. A live ownership contract or lease means leave its actively-owned hunks
     to its branch commit; an "authored by" label alone does not — check
     `git log agent/<p>/<card>` for the commit that already carries them instead of shipping
     them yourself and calling them your held work. Compare the branch against the working tree
     (`git diff agent/<p>/<card> -- <paths>`): empty output means the tree's bytes are already
     committed there, which establishes provenance even while the file still reads as modified
     against HEAD. For a path untracked in the tree that same diff renders as pure deletions —
     untracked files are not in the comparison, so it is not evidence the file is missing.
   - Generated indexes and their classification ledgers: stage only eligible in-scope diffs.
     A regenerated index also carries rows for files you are not committing, and an
     index↔tree guard then fails on the pushed tree; read `git diff -- <index>` and hold the
     file when excluded rows ride along.
   - Eligibility is per hunk, not per file. Read the diff of every co-touched file; if excluded
     hunks cannot be split out safely (`git add -p` is unavailable; use `git apply --cached`
     on an edited patch), hold the whole file.
   - Ledgers (`tasks/` records, trackers) usually carry other passes' uncommitted
     edits. If you stage one, say so in the commit message and report; never present it as
     only your change. A task record also receives the engine's own verified close (`status =
     "done"` plus its `tasks/evidence/` receipt), so staging one can duplicate a change that
     close commits too — name it in the message and reconcile by task identity before staging;
     do not duplicate a close.
     - A ledger's working copy can also be **behind** the remote, and committing that deletes other
       people's work. Another pass may have pushed its entries from a different checkout, so the copy
       you hold is missing lines that exist on `<verified-upstream-ref>` and your commit removes them on push.
       Diff the ledger against the remote before staging (`git diff origin/<branch> -- <ledger>`) and
       inspect additions, removals and task identities against fresh upstream. Reconstruct only
       genuine authorized unshipped edits **on fresh upstream in an isolated candidate**;
       preserve newer remote entries via supported GitHub issue operations and anchored
       prose edits, then validate and inspect the resulting diff.
       Never delete remote lines merely to match a stale/forked copy. A stale-only ledger
       contains no new work: leave that copy untouched and do not create a restoration commit.
     - Re-measure `git status --porcelain` right before staging. A count that moved means a
       writer is live.
   - **Completed cross-agent implementation is eligible under explicit repo-wide authorization.**
     Inspect its diff, provenance and completion evidence; run or reuse candidate-bound gates
     and include its tests/docs. Missing review or verification requires evidence, not an
     authorship veto. Attribute contributors and verification receipts in the commit message
     and report; never call their implementation your own. Hold live writer/lease hunks,
     incomplete or unverifiable work, secrets and unapproved scope. Ask only when an actual
     intent or authority gap remains; do not revert or delete held work.

3. **Prepare the smallest delivery.**
   - Before staging into a shared or pre-populated index, load
     [shared-index commit safety](references/shared-worktree-safety.md#shared-index-commits).
     Preserve held staged entries, HEAD and dirty work. For main-only temporary-index
     landing, load the [landing recipe](references/shared-worktree-safety.md#temporary-index-landing-without-a-development-branch)
     before any writes.
   - Group in-scope work into the fewest coherent commits, one per component or topic. Keep
     each change with its tests and docs. Never commit code without the test that pins it.
   - Make only safe mechanical fixes (formatting, imports, ignored local output, stale paths).
     Do not expand product scope.
   - Before combining reviewed slices, load
     [combined-slice gates](references/candidate-gates.md#combining-reviewed-slices).
     Reconcile producer/consumer contracts and run formatting, analysis and the focused
     regression union on the assembled candidate before the broad gate. Preserve
     public-behavior, ownership and recovery regressions; isolate conflicts from live workers.
   - When a feature depends on uncommitted predecessors, trace required symbols and
     select only their necessary hunks with regression tests. Do not import a whole
     backend merely because one fixture gained a contract. If whole-file inclusion
     changes unrelated runtime outcomes, narrow the dependency or report the blocker.
   - Gate that curated index in a complete `git checkout-index --all --prefix=.../`
     snapshot, not the dirty root or a partial source mirror. Preserve tracked native
     hosts/docs/source-contract inputs, verify every snapshot blob against the index,
     and identify historical local-only receipt links rather than importing unrelated
     ledgers or generated evidence to make Markdown closure pass.

4. **Validate once, in the right order: stage → gate → push.**
   - Before gating an export that needs untracked dependencies or Git-bound validators,
     load [candidate gates](references/candidate-gates.md). Also load it before handling
     snapshot-only failures, HEAD drift, long/interrupted gates, asynchronous handoffs,
     CRLF CSV checks or an after-the-fact missed gate. Scope candidate `GIT_*` overrides
     to individual Git calls, never build-tool environments.
   - Identify the repository's canonical check command before running the gate
     (`make check`, `make test`, or the documented equivalent). Execute it from
     the complete candidate snapshot with the supported timeout control, retaining
     its exact command and result. Prefer that entry point over an equivalent
     ad-hoc wrapper: verification integrations may recognize the canonical command
     but miss a nested invocation, forcing an otherwise redundant full run.
   - Bind the gate to the curated index: record `git write-tree`, check the complete
     exported snapshot, and retain its commands, results and relevant dependency/environment
     inputs. Reuse those results only while those inputs match; unchanged source bytes alone
     do not prove unchanged tools or dependencies. Capture the fingerprint *before* launch in
     the same receipt as the exact command (tree, component trees, lockfile hashes, executable
     paths/versions, fixture config), then tree identity, exit, duration and log path on exit;
     a command-plus-duration receipt cannot show which candidate it exercised. Read the actual
     compiler/SDK version against the repository pin; on mismatch use an isolated matching
     toolchain, never another session's shared install. Run `git diff --cached --check`.
   - Report suite counts from that exact candidate, not a broader dirty-tree run: excluded
     foreign tests can legitimately change the totals. Never import unrelated work merely
     to reproduce an earlier count.
   - On failure, fix the smallest safe cause and rerun only failed or affected checks.
     Before repair or reporting HELD, load
     [gate failures and receipt repair](references/candidate-gates.md#gate-failures-and-receipt-repair).
     Preserve passing receipts only for unchanged source, tests, dependencies and tool inputs.
     No waived gate or unverified readiness claim is allowed.
   - A running gate is not a pass: never push while its required checks are still running.
5. **Commit.**
   - Stage explicit paths only (`git add -- <paths>`); never `git add -A` / `git add .` on a
     shared tree. Use `git --literal-pathspecs add` for collected filenames. Build the add list
     from paths present in the worktree or `git ls-files -z`: an already-staged deletion (common
     after `git apply --3way`) exists in neither and aborts the whole `git add`; keep it in the
     expected staged set. Deduplicate so a staged deletion plus untracked replacement stages the
     replacement. Verify with `git diff --cached --name-status` that the staged set is exactly
     what you meant, and that the files you held back are still unstaged.
   - Scan staged content for secrets with the repository scanner or an in-process matcher over
     `git diff --cached` (signals: `api[_-]?key|secret|token|passw|BEGIN [A-Z ]*PRIVATE KEY`).
     Assert the scan received the intended path set and, for a nonempty added-content diff,
     a nonzero added-line count before accepting zero findings. Use an actual newline when
     splitting diff text (`String.fromCharCode(10)` avoids nested shell/Python/JavaScript
     escaping ambiguity); a filter over literal backslash-n can silently scan nothing.
     Report the scanned count without printing content. For deletion-only changes, explicitly
     record that there is no added content rather than treating empty input as a scan pass.
     Output only file, line and category; printing matched literals can itself leak a credential.
     Classify every hit before acting on it. A real value blocks the commit, but these patterns also
     catch **names and prose**: a variable assignment whose right-hand side is another variable
     (`TEST_PASSWORD="$ADMIN_PASSWORD"`) and a sentence that says "rotate any secrets" are not
     secrets. Hold the commit for a value only; never rewrite a name or a quoted sentence to silence
     the matcher.
   - Follow the repo's commit-message convention (check `git log --oneline -10`). Read the
     message back before pushing; once it is on a shared branch, fixing it would need a force-push.
   - Before splitting one gated tree into topic commits, load
     [partitioned commit checks](references/shared-worktree-safety.md#shared-index-commits).
     Match each commit to its pinned path/blob partition and only the final tree to the combined gated tree.
   - Immediately before committing, re-read `git diff --cached --name-only` and compare
     it with the authorized path set. Exclude unrelated staged entries without changing
     another writer's index; if isolation is unsafe, hold. Compare `git write-tree` with
     the recorded gated tree and verify HEAD has not moved. For a single commit, require
     `git rev-parse HEAD^{tree}` to match the gated tree after committing. If hooks or another
     writer changed it, inspect the difference and rerun affected checks before claiming verification.

6. **Sync with upstream (default).**
   - With sync authorized, after the owned commits exist and before pushing:
     `git fetch <verified-upstream-remote>`, then
     `git rev-list --left-right --count HEAD...@{u}`. Nothing incoming: go to step 7.
     For no-pull/no-sync: use permitted remote metadata without fetch or integration;
     verify destination inclusion using already available objects, or hold publication
     with the missing SHA/evidence. A restriction never authorizes a fallback sync.
   - Integrate with the [pull and merge](references/pull-merge.md) procedure: verify
     checkout ownership before checking dirty-path collisions. Shared/live checkouts
     require isolation even when paths are disjoint. Fast-forward when there are no
     local commits; otherwise `git merge --no-ff @{u}` only when merge commits are
     authorized. Under ff-only/no-merge/no-commit, try only fast-forward and report
     divergence rather than creating a commit. Never rebase, stash, reset or
     `git pull --rebase`.
   - Resolve conflicts as that procedure says; never by dropping either side's tests.
   - Re-gate the merged tree: rerun the checks for the areas the incoming commits touched,
     and confirm your own paths' blobs are unchanged. A failure the merge caused is part of
     this delivery: fix it, or `git merge --abort` (before committing) or
     `git revert -m 1 <merge>` (after) and report HELD.
   - Having nothing to commit is not a reason to skip the sync: a pull with nothing to push
     is reported as SYNCED.
   - Never push a branch that is behind its push target. Before every push, including
     an explicit refspec, read the exact destination SHA (not only `@{u}`) and prove it
     is an ancestor of what you push. Fetch only within authorized sync; under caller
     restrictions use remote metadata and existing objects as above. If the verified
     destination cannot be proved included, report HELD instead of fetching anyway.

7. **Push (explicit ship target only).**
   - Push only the verified configured destination/ref; no upstream means resolve
     repository policy and push configuration first, not an automatic `origin` fallback.
     A new delivery branch cut from remote main can inherit main as upstream: push an explicit
     refspec (`git push --set-upstream <remote> HEAD:refs/heads/<branch>`) and verify that exact
     ref. A delivery-branch push is not a main merge.
   - Preserve already-qualified immutable source commits rather than cherry-picking
     duplicate bytes. If upstream advanced, incorporate them through the normal merge
     path on the verified base before publication; do not publish an older candidate
     merely because one component is unchanged. Reuse component-bound receipts only
     when source subtrees, owned-file allowlist/hashes and dependency/tool inputs
     still match; rerun affected checks/review. Read back remote ref, PR head and file list.
   - Never `--autostash`. Step 6 has already merged upstream; if the push is still rejected
     because upstream moved again, repeat step 6 once and push. Rebase needs explicit approval.
     On a no-pull/no-sync request, report the moving destination without fetching or
     rebuilding on new upstream. Under ff-only/no-merge/no-commit, reconcile only by
     allowed fast-forward or report divergence; never fall back to a reference's merge
     recipe or recreate existing commits to evade that limit. Never force-push. Measure the overlap against the merge base, not against
     HEAD: `git diff --name-only $(git merge-base HEAD origin/main)..origin/main` lists what they
     changed, while `HEAD..origin/main` also lists your own unpushed files and reads as an overlap
     that is not there.
   - **When a shared dirty checkout cannot safely integrate incoming work**, prepare a fresh
     isolated delivery branch at a pinned upstream revision without stashing, resetting or
     switching the shared checkout. Apply only attributed completed source deltas; reconstruct
     genuine current issue changes through supported GitHub tools instead of copying a stale file; preserve legacy records.
     Stage explicit paths, gate the coherent candidate and push its delivery branch. Reuse an
     existing suitable PR rather than creating a duplicate. When merge is authorized, satisfy
     repository protection, reviews and checks, then merge the exact inspected PR head and
     read back its merged state plus main inclusion. Merge authorization never permits direct
     main pushes or protection bypass where a PR is required. Preserve the original local
     branch/index/worktree and report any divergence; do not realign pointers or force-remove
     worktrees as incidental delivery cleanup.
   - Verify the exact pushed destination ref by permitted remote readback, matching
     its SHA/inclusion to the candidate; do not silently fetch a different default
     remote. The push output alone is not proof.
   - **Leave the canonical checkout current after pushing the default branch from elsewhere**
     only when local sync is authorized and ownership is released. Use its verified
     default branch/upstream, not a hard-coded remote. When it is on that branch,
     idle with known ownership, and no incoming path is dirty, fast-forward and read
     back both SHAs (for a verified `origin/main`, `git -C <canonical> merge --ff-only origin/main`).
     Never refresh a live writer's checkout, stash, reset or switch it to make this
     possible; otherwise report **local main stale** (or the actual base) with its reason.

8. **Close the loop.**
   - `git status --short --branch`; report hashes, the push result, and every remaining path with its reason.
   - If a tracker entry authorized the commit, mark it with the SHAs using an
     anchored patch (reread the file first). Don't rewrite the whole file.
   - If any safe topic shipped, the outcome is SHIPPED, even with other paths left local.

## Worktree sweep (`all`)

`/git-commit-push all`, "merge all worktrees" or "clean up worktrees" also merges the
finished worktrees into the base branch. A worktree that never merges holds planning and
implementation that nobody can see, and every later decision is made without it. The
[sweep procedure](references/worktree-sweep.md) owns the order, the safety rules and the
report; these three commands are the whole interface.

```sh
python3 "<skill-dir>/scripts/worktree_sweep.py" .                     # read-only inventory
python3 "<skill-dir>/scripts/worktree_sweep.py" . --apply             # merge finished, clean ones
python3 "<skill-dir>/scripts/worktree_sweep.py" . --apply --remove    # then close them out
```

A merge candidate needs released ownership, completed eligible scope, required gates,
commits not on the verified base branch **and** a clean tree. An open Orbi PR is
not eligible, even in a clean idle worktree; its coordinator retains delivery.
Read-only inventory is allowed; do not run `--apply` on an unfiltered inventory
that includes owned/unknown worktrees. The
sweep never commits, stashes, resets, rebases or discards another writer's work: a dirty
worktree is reported for its owner, or archived with `worktree_closeout.py --archive`.
Detached release checkouts and locked worktrees stay untouched. After the batch, re-run
the repository check on the merged tree, and report a conflict as `Merge pending` for
that branch while the rest continue.

## Red lines

- Never commit secrets, `.env*`, credentials, private keys, logs, caches, build output,
  databases or service data roots, `graphify-out/`, `.understand-anything/` or other
  generated artifacts, or machine state.
- **Project ledgers are not generated artifacts.** Legacy `tasks/` records remain
  preserved evidence, not an active backlog. Impeccable's `PRODUCT.md`,
  `DESIGN.md` (+ sidecar) and `.impeccable/` config/briefs are tracked project files.
  Ship authorized verified changes with their work; never mutate legacy task records
  through a removed CLI or a hand-edit workaround. Only
  `.impeccable/mocks/` and screenshot/evidence folders follow the repo's gitignore.
- Do not discard, stash, revert, or `git clean` other agents' or the owner's work to make a commit tidy.
- Committed is not deployed. Do not deploy, publish, release, rebuild images, restart live
  services, run migrations, force-push, rewrite history, rebase,
  change remotes, or delete branches without explicit approval for that exact action.
- Ask only when ownership, intended behavior, secret handling, destructive history,
  dependency policy, or remote integration changes what the safe action is. A long list of
  changed files is not a reason to ask; inspect and isolate it.

## Outcomes

- **COMMITTED**: the requested local commit exists and was read back; no push was requested or performed. Unrelated paths may remain.
- **SYNCED**: nothing eligible to commit, and upstream changes were merged into the branch
  (and pushed when the merge created a commit and a push was requested). Report what came in.
- **SHIPPED**: checked commits reached the authorized remote target and were read back. An
  agent-branch write is COMMITTED; a task-branch push is not main delivery when main was requested.
  Unrelated paths may remain.
- **NO-OP**: no actual unshipped delta in requested scope after checking all eligible
  completed changes against the requested target, regardless of author. Already-published
  bytes and stale-only ledgers are not new work. Report behind/diverged status separately;
  withheld work awaiting safety, authority or verification is HELD/ASKED, not NO-OP.
- **ASKED**: no safe topic can ship without one owner choice. Ask one yes/no question
  with `clarify` (reply `yes` to ship, `no` to leave local), or at most three numbered options.
- **HELD**: a red line, missing credentials, a conflict, a hard validation failure, or an
  unsafe remote state remains after one focused repair attempt. Record it in a GitHub
  Issue or the tracker only if it meets the `hard-blockers` criteria, and ask any owner
  question as a questionnaire.

ASKED and HELD describe this delivery only. The surrounding goal or card keeps going: they never mean the work is paused.

## Report (chat-sized: Telegram/Discord first)

At most three lines. Leave out empty fields and don't repeat a hash or path.

```text
COMMITTED|SYNCED|SHIPPED|NO-OP|ASKED|HELD — <local or agent-branch sha, not pushed | hashes + push result | exact reason>; synced: <n incoming, ff|merge|none>
Checks: <gate(s) and result>; inspected all modified and untracked paths
Left local: <path — reason, …> | Need: <one action>
```

Audit mode starts with `AUDIT — <what would be committed, grouped>` and never changes Git state.

Follow [the shared skill contract](../shared/COMMON-CONTRACT.md) for repo hygiene,
verification evidence, and safety defaults.

## Shared index safety and checkout isolation

A plain scoped delivery does not require these exceptional playbooks.
Load shared-index safety at step 3 for accumulated/concurrent or pre-populated indexes;
load candidate gates only for the branches named at steps 3–4.
For a new coding checkout, load [WORKTREE-ISOLATION.md](../shared/WORKTREE-ISOLATION.md).
These references do not grant commit, push, cleanup or execution authority.

## Skill policy regression checks

For changes to this delivery policy, run through `terminal` from the Kit
repository: `python3 skills/git-commit-push/scripts/test_delivery_scope.py -v`.
`python3 scripts/check.py` discovers this offline suite. These checks pin scope,
cross-agent eligibility, live-writer exclusions and stale-ledger reconciliation;
they are policy-contract tests, not proof of model behavior or live publication.

## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; delivery
does not replace it.

| Rationalization | Reality |
| --- | --- |
| "The change is ready, so I can commit everything." | Stage only owned paths. Preserve unrelated, dirty and live work. |
| "Commit implies push." | A local commit, push and deployment are separate outcomes. Push needs explicit authority. |
| "The gate is failing, but I can ship a checkpoint." | Report the failing gate. A local checkpoint may be allowed; it claims no readiness and waives nothing. |
| "I can force-push or rewrite history to clean this up." | Destructive history changes need explicit authority and their own safety checks. |
| "The push probably worked." | Read back the remote target. A local success is not remote delivery. |

## Red Flags

- Staged unrelated paths, secrets or generated scratch.
- Push, force-push or history rewrite without explicit authority.
- A waived gate, skipped check or readiness claim after a failure.
- Remote delivery claimed without a readback.
- Merge or cleanup that touches dirty, locked or live worktrees.

## Boundaries

- Not a code review; use `/ponytail-review`.
- Not a way past a failing gate: a red check is reported, never waived.

**Done when:** owned paths are committed, upstream is synced, and any push is read back; otherwise the exact hold is reported.
