# Shared skill contract

Use the [ASD-STE100 and project language rules](COMMUNICATION.md) for user-facing text.
Read the target project's glossary map and glossary when available.

Apply the [shared Ponytail method](PONYTAIL.md) within each workflow's authority.
Reuse existing code and artifact owners; choose the smallest complete result,
without weakening accepted behavior, safety or verification.

## Operating behavior

Apply these with [Ponytail](PONYTAIL.md) and the [communication rules](COMMUNICATION.md).

- Check whether a bundled skill fits before a non-trivial response or action; use
  [`/ask-kit`](../ask-kit/SKILL.md), then read the named skill.
- For lifecycle rules, asynchronous effects or shared-state changes, apply the
  [state-machine analysis](../state-machine/PROTOCOL.md) to the affected paths.
  Reuse a current map; keep the caller's scope, mode and report format.
- Surface assumptions before non-trivial work; mark guesses.
- Name confusion and conflicting requirements; stop and resolve them.
- Disagree with evidence; propose the alternative.
- Preserve scope and unrelated work.
- Verify before claim; name unrun checks and missing coverage.

User instructions and repository rules define the authorized scope. Read the
relevant instructions, current source, tests and existing documentation before
changing their owners. Keep proposals distinct from accepted requirements and
implemented behavior. An explicit skill invocation authorizes its documented default
actions within the user's scope: planning commands save docs and publish complete
GitHub Issues with default readiness; Orbi owns automatic implementation and PR delivery. Loading a supporting skill adds no authority.
Installation, publication, third-party contact and destructive actions require their
own authorization; specific no-write/no-commit restrictions always take precedence.

For task operations, load the [GitHub issue contract](PLAN-HANDOFF.md).
All issues default to `ai-ready`, regardless of author. Preserve explicit pauses,
incomplete planning, native dependencies and actual ownership. GitHub Issues and
Orbi are the only executable backlog and delivery executor. Never create a second
queue or executor when GitHub or Orbi is unavailable.

Inspect status and preserve pre-existing edits, untracked files and live ownership.
Use [worktree isolation](WORKTREE-ISOLATION.md) when a separate writing checkout
is required. Do not reset, clean, stage or overwrite unrelated work. Keep secrets
and generated scratch out of deliverables.

Run the checks that discriminate the claimed change. Record actual commands,
results and the source they exercised; label missing coverage NOT_CHECKED.
Static policy checks and offline fixtures do not prove model adherence, native
worker execution, provider behavior or delivery. Review scoped diffs and links,
and reconcile affected documentation and task state without inventing evidence.
Report changed artifacts, verified behavior, limitations and remaining work.

## Source freshness and delivery ownership

Select the mode before repository probes or handoffs. This rule overrides conflicting
first-party delivery text and linked upstream methods. Only the narrow
standalone-planner exception below adds Git-write authority.
Scope, explicit no-pull/no-sync/no-commit/no-push limits, pauses, host permissions,
protection and required review gates propagate to supporting skills and delegates.

| Mode | Source evidence and permitted effects |
| --- | --- |
| Read-only / audit / questions / dry-run | Read existing local refs/source and permitted remote metadata/source only. Never fetch (it writes `.git`), update refs, pull, create worktrees or otherwise mutate Git. Report the observed revision and freshness gaps. |
| Writable planning | Save authorized planning artifacts/publish issues and consult fresh issue/PR evidence. Standalone Plan With Me / Plan For Me apply [planner freshness](#standalone-planner-freshness) before code analysis. Other planning routes use permitted remote reads without Git sync. Never commit the checkout. |
| Authorized implementation | Inspect the baseline, repository identity and actual ownership before edits. If stale or shared, use the existing isolation procedure from a verified base; do not refresh another writer's checkout. If the base cannot be verified within scope, hold dependent edits and name the missing evidence. |
| Delivery/sync | Follow [/push](../push/SKILL.md) for invoking-checkout delivery to `main` or [/git-commit-push](../git-commit-push/SKILL.md) for its explicit scope (`all` retains the sweep). Only authorized sync may fetch a verified configured upstream. Narrower caller limits win. |
| Non-repository | Report this rule not applicable; do not require Git or GitHub for a non-repository task. |

### Standalone planner freshness

**Scope.** This prospective exception is for standalone writable Plan With Me and
Plan For Me only. It is not delivery permission. Read-only, audit, questions-only,
dry-run, no-write and explicit no-pull/no-sync invocations never fetch or alter
refs. Honor historical/pinned source requests without this exception. An Orbi-owned
substep preserves its coordinator's pinned candidate. Supporting methods and other
planning routes do not inherit this authority.

1. **Bind before reading code.** Do this once before scoped code analysis, including
   discovery and interview preparation. Read the request and repository instructions
   needed to establish identity, restrictions and ownership first. Resolve the
   canonical repository with `git worktree list --porcelain`, the invoking checkout,
   intended analysis branch from request/policy, attached current branch, and its
   configured `branch.<branch>.remote` and `branch.<branch>.merge`. Verify the fetch
   URL (not the push URL), upstream ref and tracking mapping against that repository.
   Do not infer `origin/main`, switch branches or set missing upstream configuration.
   A missing or ambiguous target holds local sync.
2. **Prove safe ownership and ancestry.** Require an exclusively held checkout on
   that verified branch, with a clean index and worktree including untracked files
   and submodules, no in-progress Git operation, and no active/foreign-worker or
   uncertain ownership. A clean status or a worktree name alone proves no release.
   Use current issue/PR/run and local writer evidence without modifying other trees.
   Use nonmutating probes, including `GIT_OPTIONAL_LOCKS=0` to prevent status from
   refreshing the index. Read upstream metadata without fetching, for example
   `timeout 60 git -C "$checkout" ls-remote --exit-code "$fetch_remote" "$upstream_ref"`.
   Require one exact ref/SHA. Establish that local HEAD has no local-only commits
   relative to that SHA, using available Git objects/ancestry or permitted remote
   comparison reads. Cached tracking refs alone do not prove current ancestry.
   If ancestry cannot be verified without fetching, use remote-source analysis.
   Never pull an ahead, diverged, detached, dirty, wrong-branch or owned checkout.
3. **Fast-forward once.** Recheck branch, HEAD, clean status and ownership immediately
   before the write. Only after all gates pass, use the verified values below:

   ```sh
   timeout 60 git -C "$checkout" pull --ff-only --no-rebase --no-autostash --no-recurse-submodules "$fetch_remote" "$upstream_ref"
   ```

   This is the only added Git-write operation, including its fetch. Do not run a
   separate fetch or substitute a generic delivery recipe. Record pre-pull HEAD,
   the observed remote SHA, exit status, resulting HEAD and fetched upstream commit
   (`git rev-parse FETCH_HEAD`). Require resulting HEAD = fetched upstream SHA,
   even for an already-current no-op. If the fetched SHA differs from the earlier
   observation, verify identity/ancestry and use the fetched revision only after
   assessing affected evidence. A rejection, timeout, postcondition failure or
   ownership drift is not success. Preserve the actual error and observed state,
   including any changed fetch metadata/refs. No retry or repair: no commit, push,
   rebase, merge commit, stash, reset, forced checkout, service changes or repair of
   another tree.
4. **Choose and attribute source.** If sync is unsafe, forbidden or fails, use
   permitted read-only source at a verified remote SHA for the intended ref. Read
   source/tests at that SHA, not a moving branch URL. A metadata-only SHA is not
   evidence that its code was read. Keep local-only changes distinctly attributed
   to their local revision or dirty paths, never silently combine them with upstream.
   For pinned/coordinator requests, use the requested source rather than replacing
   it with latest. If remote source is unavailable too, disclose actual local/pinned
   source and the freshness gap. Hold freshness-dependent decisions, not independent
   planning. Name the repair/resume condition, such as verifying the intended
   upstream or obtaining read access; do not repair or release another worker.
5. **Reuse and report.** Coordinate existing planning reads with this check, then
   investigate source/tests at the chosen revision. Reuse still-valid evidence,
   not a second discovery pass or a pull per question. Recheck permitted upstream
   metadata before publication, not on every interview turn. Revisit only material
   drift affecting decisions or acceptance; hold affected publication if unresolved.
   The source receipt names repository/checkout, branch, fetch remote/ref, pre-pull
   HEAD, observed/fetched upstream SHA, resulting HEAD, chosen analysis revision,
   sync outcome (fast-forward, already-current, skipped or failed), local-only
   evidence and gaps. Use not-applicable/unknown rather than inventing a fetched
   revision for a no-sync path. Report what was and was not verified.

**Verify identity, not names.** Resolve the actual repository, intended base,
configured upstream and push destination from Git configuration and repository
policy. Distinguish fetch and push URLs/refs; do not assume `origin`, `main`, a
branch prefix or a bot author establishes identity or ownership. Existing examples
with those names apply only after verification. Resolve ambiguous destinations
before writes. Check current issue/PR links, coordinator/run evidence and actual
writer activity within the invoking command's local scope; a quiet or clean worker
checkout does not establish release. `/push` excludes other worktrees from local
inspection, saving and tip integration, including the canonical checkout when
invoked from a linked checkout. Minimal Git metadata for boundaries, placement and
safe landing is allowed; remote issue/PR discovery and freshness remain complete.

**Keep Orbi delivery with its coordinator.** Orbi owns its issue-to-PR/review/merge
route, including an open PR whose checks pass. Take already-landed code through
verified upstream, not a worker head. Report open, failed, blocked, paused,
closed-unmerged and unknown work with its URL, exact reason and next action; leave
its files, refs and checkouts untouched. No PR checkout, remote ref deletion or
implicit takeover. A later explicit takeover must name the task and reconcile
ownership and required gates; these workflows do not provide that takeover.
Completed independent local work remains eligible under existing delivery scope,
regardless of author, but that cannot override an outstanding coordinator's route.

**Refresh affected evidence.** New upstream source triggers re-evaluation of affected
decisions, candidate checks and required review, not a second worker or scope
expansion. Delivery pins source/base/head/merge and destination SHAs, refreshes
relevant ownership/PR evidence immediately before integration/publication, and
rebuilds changed candidates through the normal merge path. API failure/rate limit
means unknown coverage, never an empty backlog. Preserve unverified candidates and
report partial inventory; no retry loop or alternate-credential workaround. Verified
upstream Git sync and independent local delivery may continue under existing gates,
but missing required protection/review evidence holds dependent publication. Report
partial delivery separately from complete discovery. The Orbi lifecycle skill still
does not commit or push; no observation enables paused/live-unqualified Orbi.

## Graph state

A code graph never describes its input perfectly. When a workflow uses one, report
exactly one state: `graphify_fresh` (version keys readable, nonzero nodes and links,
queried inputs unchanged, tool version recorded), `graphify_stale` or
`graphify_partial` (a changed or unknown input, an uncommitted or excluded file, or an
integrity warning), or `graphify_unavailable` (the tool, the skill or the extraction
failed; name the failure). Under any state except `graphify_fresh`, a graph result is
orientation: verify it in live source before a conclusion, and claim no unreachability,
runtime behavior, severity or effort saved. The Graphify workflow in
`adapters/skills/graphify/SKILL.md` owns how this tool reaches each state.

Resolve helper paths from the actual loaded skill directory, not an assumed
Hermes home. Sibling bundled skills and this support directory retain their
relative layout. Quote absolute paths and repository arguments in shell commands.
Before creating or refining repository work, read
[Plan Handoff](PLAN-HANDOFF.md) for issue content, publication and dependency rules.
No local-main persistence or task-store synchronization is required.
