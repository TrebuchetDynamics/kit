---
name: docs-sync
description: "Maintain docs and GitHub issue handoffs."
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [documentation, governance, technical-writing, backlog]
---

# Docs Sync

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../shared/COMMUNICATION.md) and follow the
[shared contract](../shared/COMMON-CONTRACT.md).

Keep docs accurate and distinguish intent from implementation. Reuse owners.
GitHub Issues are the authoritative backlog; Orbi owns delivery. The
[legacy task store](../shared/TODO-WORKCENTER.md) is migration-only, not a new queue.

## 1. Choose mode and scope

- **Bootstrap/Maintain:** inspect the requested scope, build missing applicable
  document roles and correct affected owners from source evidence.
- **Audit/read-only/questions-only/dry-run:** read and report; no files, scratch,
  GitHub Issues, labels or service mutations.
- **docs:** document maintenance only; no issue publication.
- **tasks:** reconcile GitHub Issues, native dependencies and linked PR evidence.
  Explicit legacy pruning follows the migration guide's separate safe reconciliation;
  never delete recovery state or infer completion from an empty store.

A bare invocation maintains applicable docs and evidenced missing work; it does not
prune legacy records or start execution services. Newly published complete issues
default to `ai-ready` through [Plan Handoff](../shared/PLAN-HANDOFF.md), so an existing
Orbi deployment may pick them up. Explicit no-dispatch requests keep `ai-planning`.
Keep incomplete/proposed work undispatched. Do not invent requirements, acceptance
or completion to fill a queue. A document-only request does not change code, install
software or deploy production.

## 2. Discover and coordinate

Read repository instructions, accepted decisions, source/tests/CI, Git status and
the current GitHub issues/PRs within scope. Inspect staged, unstaged and untracked
inputs. Reuse the caller's verified findings instead of restarting research.
Check actual writers and preserve unrelated changes. Before updating an issue,
reread its current body, labels, dependencies and linked PR; do not replace a live
worker's contract or replay a stale snapshot. A refused update requires narrow
reconciliation, not a new blanket approval.

Resolve completed and partially delivered work against PR/check/review evidence.
Preserve remaining live qualification and exact next actions on the same issue.
Do not create completed-task reports or duplicate issue/PR history in local files.
Use the existing document owner and normal repository PR process for document edits;
there is no local-main task-store admission gate.

## 2a. Targeted relationship analysis

Routine link, wording and task-metadata repairs use direct source evidence;
no Graphify or other supporting skill is required merely to edit documentation.
For architecture, cross-component impact or uncertain task dependencies, use
`graphify` and [Graphify analysis](references/graphify-analysis.md) when its map
adds needed evidence. Corroborate graph findings in source and accepted intent.
An explicit Graphify requirement remains binding. If graph tooling is unavailable,
use bounded source inspection where sufficient and report material coverage gaps;
never claim that source-only work completed a requested graph analysis. Audit
reads existing artifacts only. Graph inference is not approval or executed validation.
Report `Graph evidence:` and Graphify coverage/limitations with the source checks.

## 3. Intent and evidence

Requirements/accepted decisions own intent; code/tests show implementation; release
records show delivery. Investigate mismatches rather than changing intent to match
code. Distinguish Proposed, Planned and Implemented. Ground claims in paths/symbols/
checks; never invent approval, owners, metrics, history or validation. Bind
historical receipts to their tested revision: old untested wording does not prove
current absence. Before retaining a “local-only” or “not on main” claim, check
`git merge-base --is-ancestor <reviewed-commit> <target>` and the relevant current
source blobs; integration can advance independently of an old receipt. Correct
CHANGELOG and test-plan together while keeping packaging, deployment and live
qualification separate.

Reconcile retained checks by reading the receipt, result inventory and actual
runner liveness together. If the runner is gone but its receipt lacks a terminal
exit or full aggregate, record the attempt as incomplete/unqualified, not running
or passed; failed batches do not establish an invented whole-suite total. Before
promoting a retained full-gate receipt, verify its declared log and owned-source
hashes, then reconcile the selected inventory with unique recorded test/project
identities across every batch in code. Preserve retry, flaky and skip classifications;
summed batch counters can double-count attempts or conceal missing identities.
Record a completed focused check with its source/tools, selected-versus-recorded inventory,
setup-versus-product cases, skip reasons and cleanup evidence. Keep its duration
out of full-gate speedup claims. Put the detailed result in one existing evidence
owner and link it from the live task's `Evidence:` note and the plan; update the next
action without resetting ownership or acceptance. For paired visual evidence, retain baseline and
candidate observations separately: a defect present in both is an outstanding
acceptance gap, not proof that the candidate introduced it. State fixture limits
such as substituted fonts or a blank renderer alongside the claim, because painted
widget chrome does not establish production typography or device/GPU rendering.
Record an owner-permitted acceptance waiver with its exact
criterion, authority, residual risk and remaining checks; it is never an executed
pass and does not extend to other criteria or tasks. When scope changes, reconcile
the authority owner, active task records and operational guidance together.

Trace owner corrections through dependent contracts and tasks; distinguish policy
changes from implementation. Preserve security/user state, historical receipts,
exact commands, IDs and holds. Read/pin source reports; retain reusable scratch
findings in existing owners. Withdraw unsupported reference claims, not invent
replacement evidence. Notice-only edits must reproduce original bytes after removing
only this pass's notices; preserve pre-existing annotations. Label authorized redaction; no rewritten history or reactivated proposals.
Keep public skills profile-independent, operational receipts private and fixtures
neutral. Relocation does not purge Git history. Never copy secrets/production data.
When asked to save supplied operational notes, preserve the source under a short
provenance notice and link it from existing documentation navigation. Keep its
host/version qualifications and distinguish reported measurements from checks you
actually repeated. Saving a runbook does not authorize its install/configuration
commands or convert its checklist into executable tasks.

## 4. Core document owners

Bootstrap accounts for all applicable roles, reusing equivalent existing paths.
Use [document scaffolding](references/document-scaffold.md) for role ownership,
section templates and conditional documents. Roles need not be separate files.
README, PRD, architecture, spec, test-plan, runbook and CHANGELOG are product/service baselines;
other roles are conditional. Narrow Maintain updates only affected roles. Absence
of a default filename alone does not establish inapplicability.

| Role | Owns |
| --- | --- |
| README | Purpose, prerequisites, shortest supported setup/run/test and navigation. |
| PRD | Why/what: users, approved goals/scope, constraints, measurable acceptance. |
| architecture | Current system map, boundaries, data flow and source-backed relationships. |
| ADR | One durable architectural choice, alternatives and consequences. |
| spec | How: components/data/interfaces, failures, security, migration, rollout. |
| OpenAPI | Exact owned HTTP contract, following authoritative input/generator. |
| test-plan | Risk-based checks, observable outcomes, environments, coverage gaps. |
| runbook | Operations, health, diagnosis, recovery/rollback/backup limits. |
| CHANGELOG | Notable implemented/released changes under actual release conventions. |

Record path and maintained, created, unchanged_verified, created_with_open_questions,
conditional_not_applicable, or not_applicable with boundary reason. "Blocked" is not
an applicable-role outcome. Build substantive supported content despite unknowns;
label questions/defaults and book real question tasks, not fabricated intent/history.
README links detailed owners; reuse requirement IDs without duplicated schemas.
When the repository has a [role manifest](references/document-scaffold.md#optional-role-manifest),
keep it synchronized with these outcomes, run `scripts/docs.py stale <repo>` to scope
Maintain and `scripts/docs.py check <repo>` before reporting; fix or report every
finding. A pass does not prove content accuracy.
Its optional [profile](references/document-scaffold.md#repository-type-profiles) sets
the baseline roles for the repository type; choose it from what the repository ships.

ADRs cover significant hard-to-reverse choices, not routine edits/interview answers.
Check current numbering; otherwise use unique zero-padded IDs and Proposed/Accepted/
Rejected/Superseded statuses. Accepted requires approval. Preserve history; accepted
replacement gets a new ADR and reciprocal supersession links. Do not backdate.
OpenAPI applies to owned HTTP APIs, not CLI/library/third-party placeholders. Identify
schema/code/generated authority; change input only within scope. When handlers or a
service are retired, keep the task's original criteria, cite immutable history and
defer it absent an accepted surviving contract; deletion is not met. Preserve supported
versions/layouts/authentication/compatibility; report source changes outside scope.

For client API delivery load [client contract handoff](references/client-contract-handoff.md).
Bind service/revision/freshness and source versus deployed qualification. WebSocket
contracts need post-upgrade messages, not only OpenAPI routes. Preserve actual wire
semantics; label examples/gaps and omit secrets. Storage plans must reuse existing
gates, bind metrics/units, preserve decoding dependencies, and separate plans/offline
checks from authorized remote recovery/activation/relief. Whole-service checks need
per-supported-cell evidence bound to target/interval, not receipt-only fixtures,
sparse silence or readiness probes. Tests name observable outcomes and distinguish
run/existing/planned automation. Runbooks give prerequisites/action/signal/recovery
limits and destructive boundaries. Do not invent production or supported recovery.
CHANGELOG records implemented/released changes, not proposals or routine doc churn.
On repeat passes, check newly landed scoped commits and update CHANGELOG and the
affected test-plan together without rewriting earlier entries. Reconcile partial
delivery explicitly: record implemented behavior under the actual Unreleased/version
section, replace blanket “all checks planned” wording with existing versus remaining
coverage, and give the same live task one concrete next action. Keep its original
acceptance and open status when qualification remains; documentation reconciliation
is not a rerun of historical tests. Anchor changelog edits to the enclosing release
section and a unique neighboring entry, because headings such as `### Fixed` recur
across versions. Stop the edit/check chain on a failed replacement so a later
successful validator cannot mask an unapplied correction.
Treat a failed preservation assertion the same way: chain shell checks with `&&`
or use checked subprocess calls, not `;`, so a later successful validator cannot
mask a failed conservation check. After a failure, inspect the affected bytes
before resuming only the unapplied work.


## 5. Goal gaps and publication

Fix in-scope supported docs now. Route behavior to requirements/spec/tests, decisions
to ADR/spec, setup to README/runbook and verification to test-plan. Investigate
intent/code mismatches rather than silently changing acceptance to match code.
Use `/plan-for-me` for consequential engineering decomposition and `/plan-with-me`
only for genuinely missing intent; reuse settled answers.

For each evidenced unmet requirement, find an existing open or closed issue and its
PRs before creating anything. Reconcile in place where safe. New executable issues
follow [Plan Handoff](../shared/PLAN-HANDOFF.md): observable outcome, bounded scope,
exclusions, acceptance, exact verification commands and governing source links.
Use an `ai-epic` for a large coordinated outcome and native `blockedBy` relationships,
never local task-store edges or free-text substitutes. Preserve legacy IDs as
provenance during migration and do not re-execute completed or currently owned work.

Create the whole batch under `ai-planning`, validate/read back content and edges,
then add `ai-ready` as the final publication phase. All issue authors receive the
same default. Epics remain non-executable. Report GitHub/auth/network failure as
**UNSAVED** with complete proposed changes and an exact retry, not as saved work.

## 6. Validate and report

Run proportional document, reference and contract checks once on the affected
batch. Read back remote changes and name issue/PR URLs, decisions, checks and exact
remaining inputs. A saved issue, label or document check is not evidence of Orbi
pickup, model execution, independent review, merge or live qualification.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "The issue is closed, so its feature is verified." | Read the linked PR and actual checks; closure can mean superseded. |
| "GitHub is unavailable, so save a local queue." | Keep proposals UNSAVED and report the retry. |
| "A doc pass should restart the runner." | Service control is outside document maintenance. |

## Red Flags

- Preparing a new `tasks/` store or restarting legacy execution.
- Replacing active contracts or weakening acceptance to mark work complete.
- Publishing readiness before the batch and dependencies exist.
- Claiming live delivery from instruction changes.

## Boundaries

- Not product invention; use `/plan-with-me` for missing intent.
- Not implementation; Orbi delivers issues, or use explicit manual `/work`.
- Not a read-only queue query; use `/pending`.
- No legacy scheduler, archive migration or pruning unless explicitly scoped.

Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to verification claims.

**Done when:** affected documents match inspected evidence, missing executable work
is reconciled in GitHub or explicitly UNSAVED, and checks and remaining obligations
are reported without claiming unobserved execution.
