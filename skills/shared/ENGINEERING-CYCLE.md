# Repository engineering cycle

Optional routing reference: consult when a method is needed and its selection is
unclear. GitHub Issues own executable work; retained fix/apply modes implement only
their explicitly accepted scope under ownership, PR and review gates.
Engineering protocols add techniques, never authority.

Caller scope and saved stop/batch limits control continuation. Default interactive
execution completes one slice including authorized recovery and closeout; an
explicit one-task limit stops new selection. Continuation or whole-spec mandates
permit only their named accepted scope. Preserve no-commit, no-push, no-deploy,
read-only and human-only boundaries. A skill default cannot expand permission.

Apply [Plan Handoff](PLAN-HANDOFF.md): reconcile accepted scope and current issues,
verify native dependencies, then publish readiness last. Autoresearch persists
supported findings there. Use bounded planning only for actual research or
consequential decomposition gaps, not routine debugging or a mandatory phase tour.
Legacy task records and recovery state stay preserved migration evidence.

## One coordinator, supporting skills on demand

Orbi owns issue-to-PR delivery. An explicitly requested specialist command stays
within its own scope and returns evidence to its existing execution owner.
Installation makes skills available, not mandatory to invoke. Every workflow
applies the [shared Ponytail method](PONYTAIL.md) as its baseline, not an extra
workflow or review loop; load detailed protocols only for the relevant choice.

| Current need | Smallest workflow |
| --- | --- |
| Ready task with clear checks | Orbi delivery or an already-authorized fix/apply mode; no research or documentation prepass. |
| Known small repair, empty queue | Record one bounded task and execute; no research ceremony. |
| Unresolved hypothesis, tradeoff or measured optimization | Bounded Autoresearch, then return findings to the same issue and execution owner. |
| Affected docs, accepted decisions or task metadata | Narrow docs-sync Maintain; no repository bootstrap. |
| User requirements that evidence cannot answer | plan-with-me; Grill Me only for requested/advisable adversarial questioning. |
| Specific engineering method gap | Engineering reference adapter and the relevant protocol only. |
| Slow, redundant or low-signal tests, or a suite past the [test budget](#test-budget) | Engineering `--protocol test-suite-optimization`: audit by default; authorized apply verifies one bounded batch. |
| Material implementation or simplification choice | [Ponytail](PONYTAIL.md): smallest complete change, with concrete reuse and verification evidence. |
| Review of that implementation | Pinned Ponytail review criteria in the existing required review lane; no external plugin or extra reviewer. |
| UI/design work | Impeccable when relevant; no design pass for unrelated changes. |

Zero supporting skills is valid when the task and repository checks suffice. Load
one relevant method at a time and stop when the gap is resolved; the table below
is a menu, not a checklist. Do not reread unchanged supporting instructions within
the same task or add a second review/planning loop merely because a skill exists.
Explicit user-required methods and actual acceptance/review gates still apply.
A helper called by the execution owner returns findings, changed paths, checks and task IDs to
that coordinator; it never starts another picker, backlog or scheduler. Reuse the
same task record and receipt. Record a skill's application only when it materially
changes a decision or artifact; never manufacture receipts for unused skills.

## Test budget

Tests are evidence, not a count target. Aim for **minimum sufficient regression
protection**: the smallest set of reliable oracles covering the change's distinct
behavior and risks. Use the canonical
[test-suite optimization method](../engineering/local/test-suite-optimization/PROTOCOL.md)
for its matrix, evidence, retained-risk mapping and review rules.

- Start a bug fix with one discriminating regression that fails without the fix at
  the right public seam; extend an existing case/table when sufficient. This is a
  default, not a blanket one-test cap. Extra cases/layers need a distinct risk and
  review rationale (for example a real boundary a unit mock cannot establish).
  Do not generate a test per function/line or repeat an implementation-mirroring
  TDD loop. Each case should identify its behavior/risk by useful name or matrix.
- Prose-only documentation and pure renames usually need no new runtime test;
  validate their relevant references/contracts. Config, parser or migration
  **behavior** can need regression coverage. Equal coverage or a never-failed CI
  history does not make a case redundant. An assertless no-exception smoke or a
  contractual interaction can be a valid oracle; internal mock calls with no owned
  contract, tautologies and duplicated cases are not protection by themselves.
- Use the smallest fixture and one coherent behavior per case. Share immutable
  setup; preserve mutable-state isolation. Prefer events or bounded polls to sleeps.
  Consolidation must preserve named bug traceability, unique risks and identifiable
  failures, not merely reduce methods or test lines.
- Record repository-specific per-suite CI wall-time limits and a justified new-case
  budget per change/PR, environment/baseline and the review rule for unique-risk
  exceptions. Unknown costs/history stay unknown. Budget exceptions never waive
  safety, security, authorization, data-loss or required qualification obligations.
- Run focused tests and the task's `checks` while working, not a full suite after
  each edit. Run the required normal gate once for final acceptance under the
  repository's execution contract; if the coordinator owns that gate, retain its
  pending result rather than claim it passed. Optional impact selection needs sound
  dependency mapping, unknown-impact fallback and the existing full gate or an
  explicitly agreed periodic full run; it must not weaken CI.
- Repository thresholds govern audit triggers; absent those, over 10 minutes for
  the normal offline check, roughly 1,000 lines in a test module, or a near-duplicate
  addition are signals to reuse/record one `test-suite-optimization` audit task
  (at most one open per repository), not reasons to delete tests. Review the slowest/
  noisiest suites quarterly in existing maintenance, without creating a scheduled job.
  Default to audit; explicit apply or existing implementation authority permits
  bounded verified edits. Quarantine requires owner, reason, expiry, issue and lost
  protection/risk, visible reporting and repair/justified retirement/escalation at
  expiry; never silently hide a critical regression.

## Autoresearch evidence enters the same cycle

Use [autoresearch](../autoresearch/SKILL.md) for bounded measured experiments,
diagnosis, adversarial analysis and research-driven planning. Its original command
protocols are vendored with a pinned revision. `plan`/`learn`/`improve` and all
research checkpoints route findings through docs-sync narrow Maintain: update
existing document owners and deduplicate accepted GitHub Issues. Follow
[Plan Handoff](PLAN-HANDOFF.md): native dependencies first, readiness last.
TSV/handoff files are evidence, never a competing task queue. Preserve actual
execution ownership, review and commit gates. Planning does not dispatch workers or create timers;
already-authorized implementation can continue from a verified eligible handoff.

## Autonomous decisions are the default

Within the user's authorized outcome, decide routine reversible choices yourself:
implementation approach, internal naming, test seams, document structure, supported
metadata repair and dependency-ready ordering within the accepted focus. Inspect
existing conventions and constraints first, choose the smallest sufficient option,
record the reason and verifying check, then act. Do not ask the user to choose
between equivalent engineering options or approve each phase again. An agent's
own plan is not a new approval gate. Missing certainty calls for a bounded source
inspection or discriminating test, not an automatic owner question.

Use this decision order: explicit user/repository constraints → accepted contracts
and existing conventions → evidence from a cheap reversible probe → simplest
compatible implementation. For a consequential choice, compare viable alternatives
and record why the selected one wins. For trivial choices, proceed without creating
an ADR or decision task. Stop investigating once evidence distinguishes the options;
revisit only when a check fails or new evidence changes the choice.

Ask only for a missing fact or decision that materially changes the user's outcome,
conflicts with accepted requirements, crosses ownership/scope, or needs authority
not already granted. Explain the exact missing input, recommend an option and keep
independent work moving. Silence is never permission, review acceptance or evidence.
Routine decisions are made under existing authority, not "approved by default".
Existing explicit authority carries forward; do not request it again. Docs-only
scope stays docs-only, and required independent review and commit gates remain.

Record `Decision: <choice>; Evidence: <source>; Reason: <tradeoff>; Check: <proof>`
in the existing task/plan owner when material. Carry that decision into the worker
contract so it is not re-interviewed. Label inferred product intent as proposed;
never relabel it Accepted merely because the engineering choice is reversible.

## Load the skill needed at the current step

Resolve bundled skills through qualified names such as `kit:docs-sync`, or their
actual loaded SKILL.md paths. The engineering pack is a [reference](../engineering/REFERENCE.md),
not a registered skill: read it or the selected protocol directly when a method is
needed. Its pinned Addy snapshot is the default; select one technique with
`scripts/route.py --protocol NAME`.
Phase bundles are optional; load selected support only. This works without
external imports and avoids ambiguous bare names. Preserve recorded vendored
adaptations and apply the reference's task-store, authorization and host-tool translations.

An explicit user request to use a separate installed Addy version wins: verify its
source/revision through the profile catalog and `skills/.hub/lock.json`, disclose
missing references, and record that alternative. Do not invent an `addyosmani:`
namespace or assume another profile's home. Existing imports are left intact.

| Need | Targeted addyosmani skill | Apply to the existing owner |
| --- | --- | --- |
| Missing owner intent that evidence cannot resolve | `interview-me` | Ask only the material owner question; routine engineering decisions use the autonomy rule above. |
| Missing specification | `spec-driven-development` | Reuse the accepted spec/PRD; do not restart accepted design. |
| Changed behavior or architectural decision | `documentation-and-adrs` | Amend affected docs/ADR with observed facts; docs-sync owns backlog reconciliation. |
| Accepted work needs bounded tasks | `planning-and-task-breakdown` | Publish complete GitHub issue batches with scope, checks and native dependencies through Plan Handoff. |
| A consequential planning assumption needs scrutiny | `doubt-driven-development` | Test the artifact/contract; record corrections and unresolved risks. |
| Implement an eligible slice | `incremental-implementation` | Keep one observable result, owned files and task ID. |
| Changed logic or a bug | `test-driven-development` | Minimum sufficient red/green protection at the right seams within the [test budget](#test-budget). |
| Review an implemented slice | `code-review-and-quality` | Use its review criteria within the required project review workflow. |
| Ambiguous new product direction | `idea-refine` | Refine the existing outcome and alternatives; do not reopen accepted scope. |
| Missing or overloaded task context | `context-engineering` | Give the worker only relevant constraints, source, decisions and checks. |
| Quality requirements or a weakened check | `constraint-driven-development` | Bind existing quality requirements to observable checks; no invented owner-approved thresholds. |
| APIs, schemas or module boundaries | `api-and-interface-design` | Specify callers, compatibility, error behavior and contract checks. |
| UI or interaction work | `frontend-ui-engineering` | Plan/build states, accessibility, responsive behavior and relevant interaction checks. |
| Replacing/removing behavior or data formats | `deprecation-and-migration` | Identify consumers, compatibility, transition steps, rollback and migration checks. |
| Build, test automation or packaging boundaries | `ci-cd-and-automation` | Bind the changed boundary to runnable pipeline/build checks. |
| Services, jobs, retries or integration operations | `observability-and-instrumentation` | Define operational questions, useful signals and a verification path; preserve sensitive data. |
| Proven unnecessary complexity | `code-simplification` | Simplify owned code while preserving observable behavior; avoid unrelated cleanup. |
| Owned changes ready to commit | `git-workflow-and-versioning` | Group validated changes; use ordinary Git and the repository's scoped commit conventions. |
| Release or rollout planning in accepted scope | `shipping-and-launch` | Capture readiness and rollback criteria; planning does not itself authorize deployment. |
| Reproduction or failing checks | `debugging-and-error-recovery` | Diagnose before changing code; use the verified fallback below when unavailable. |
| Measured performance requirement | `performance-optimization` | Establish a baseline, target the measured cause and compare the same workload. |
| Trust boundaries or sensitive input | `security-and-hardening` | Trace threats to mitigations and abuse-case checks within the task. |
| Browser behavior needs qualification | `browser-testing-with-devtools` | Exercise the actual journey on the required environment; static checks are not browser proof. |
| External implementation/API behavior is uncertain | `source-driven-development` | Verify authoritative source/contracts before relying on remembered behavior. |

Consult this menu only for an unresolved method gap or explicit protocol request.
A phase change alone is not a trigger. Reuse accepted specs, plans, quality bars
and repository procedures; do not replay planning, review or delivery workflows.
For a protocol actually applied, record material decision/artifact/check evidence
in the existing task receipt. Do not create an application record for every skill
that could conceivably be relevant. Missing optional guidance is not a gate;
missing required acceptance or execution capability must still be reported.

Load only relevant skills, not this whole table. Adapt upstream examples such as
`tasks/todo.md`, new spec files and automatic commits to existing owners (task
issues in GitHub) and permissions; never create a competing backlog or duplicate accepted tasks.

For docs-sync, apply these skills through
[decisive planning](../docs-sync/references/decisive-planning.md): evidence-backed
Now/Next ordering, bounded records and repaired task contracts are the outputs.
Record selected skill → changed owner/decision/check; a list of loaded skills does
not establish application. A usable accepted backlog does not need repeated planning.

TDD identity collision: use the engineering reference's pinned
`upstream/skills/test-driven-development/PROTOCOL.md` by default. Neither a bare
`test-driven-development` name nor Hermes's bundled
`software-development/test-driven-development` establishes Addy provenance.
If the vendored protocol is unavailable, identify the actual fallback and gap.

If a domain skill is scanner-blocked or unavailable, use verified repository
procedures/checklists for its same obligations and report any missing capability;
do not bypass the scanner or silently omit the risk.
If `debugging-and-error-recovery` is scanner-blocked or unavailable, report that
fact and use an available, verified `systematic-debugging` skill for diagnosis.
If that fallback is also absent, use the repository's documented reproduction and
debugging procedure and report the limitation. Do not install, bypass the scanner,
or waive the same acceptance checks to obtain a supporting skill. Missing required
execution/review capability remains an explicit unresolved gate.

Check referenced support files before claiming to have read them. Per-skill installs
may omit upstream root `references/definition-of-done.md`,
`references/security-checklist.md` or `references/performance-checklist.md` even
when SKILL.md loads. Disclose missing support; use the accepted task's repository
criteria and available project checklists, retaining required security/performance
coverage. Mark unavailable required checks NOT_CHECKED, never pretend they passed.

## One canonical backlog, one executor, one closure owner

1. Planning reconciles accepted requirements into existing GitHub Issues and
   complete batches. Use [plan handoff](PLAN-HANDOFF.md); drafts and missing
   acceptance remain undispatched; native dependencies preserve prerequisite waits.
   A usable backlog skips another bootstrap or broad audit.
2. For explicitly authorized whole-spec execution, restrict selection to accepted
   issues and dependency-ready work. Read issues, PRs and native dependencies,
   inspect actual process/workspace ownership and source freshness, then implement
   only within the invoking workflow's already-authorized scope. No native card admission,
   board lookup or mandatory worker is required. Optional delegation uses the
   current host's tools only when useful and authorized.
3. Implement, run discriminating checks and update scoped documentation. Retain
   task IDs, source/candidate identity, changed paths, actual commands/results and
   remaining gaps. Honor explicit task/caller scope; spending money stays an
   authority only the owner grants.
   Delegated workers stay within their assigned scope and return evidence to the
   integration owner rather than modifying unrelated canonical task state.
4. Verify implementation evidence and required independent review acceptance at
   the tested source before closure. Pending/rejected review holds completion and
   dependent work; it is not a test pass. Address review changes in the current
   authorized session, with affected checks and fresh review. No native card
   reassignment, continuation API or done transition is required. Inspect exact
   integration evidence whenever the accepted task requires integration.
5. **Assess documentation impact** from the verified diff, task Acceptance/checks
   and actual affected docs (commands/configuration, interfaces, architecture,
   operations and verification requirements). Record `doc_impact` as `not_needed`
   with a source-backed reason, `updated` with paths and passing readback/checks,
   or `pending` with the concrete gap and resume action. Workers update in-scope
   component docs and route shared docs to the coordinator/DOCS-MAINTAINER. Apply the
   [shared completion contract](DEFINITION-OF-DONE.md).
   In sequential native/portable execution, resolve bundled Docs Sync in the actual
   host and run scoped Maintain only for a concrete delta, before final closure.
   No full bootstrap or global manifest is required. Do not change unrelated policy or Acceptance. Read back affected docs
   and run their checks. Preserve foreign dirty docs and reconcile moved source,
   rather than overwrite or repin old evidence. Required doc failure/interruption
   retains implementation and pending resume evidence, not a false documentation
   pass or implementation replay. Needed closeout stays within once/until-empty
   scope; stops and pauses launch no new work.
   Close only after the required checks, independent review and integration proof.
   Record evidence on the existing issue/PR. Never mark a goal met from an empty
   queue, a label or removal of its former executor. Preserve legacy records.
   These checks do not prove model adherence or live task completion.
6. After integration, reconcile current GitHub Issues and actual ownership.
   Select another batch only when caller scope and saved stop/batch limits permit.
   Default interactive, planning-only and explicit one-task requests report the next
   slice and stop; explicit continuation/whole-spec mandates use their named scope.
   Unresolved review/capability or ownership is recorded honestly;
   it never grants broader scope. Report implementation, checks, review, integration
   and delivery separately. Offline fixtures are not native/model execution proof.
