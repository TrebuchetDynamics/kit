# Bounded planning behavior specimens

`cases.json` preserves discovery, decision-stall and interview inputs as inert
data. It is not a runner or an execution receipt. The former builder/inspector
depended on the removed executor CLI and task-store implementation and is removed.

The cases retain empty/vague requests, accepted and missing intent, conflicting
specifications, verification gaps, active dirty ownership, repeats, large projects,
coordinator-owned substeps and multi-turn interview decisions. Legacy task-path
strings in these synthetic inputs are preserved specimens, not current authoring
instructions. New planning uses GitHub Issues and native dependencies.

`test_plan_for_me_discovery.py` checks retained scenario coverage without importing
an executor or creating task stores. These static checks do not evaluate model
adherence or establish live qualification. For any separately authorized model
evaluation, use a fresh context, preserve actual owner edits and pauses, inventory
all writes/tools and bind results to exact source and host/model inputs. Do not
score missing runs as compliance or fabricate replies.

## Discovery stop/widen scenarios

These matched `/plan-for-me` scenarios are **NOT_RUN** model specifications, not
observed responses. Start a fresh context for each case. Use a disposable
monorepo and simulated GitHub readbacks; do not publish real issues, implement or
activate Orbi. The canonical skill and portable adapter use the same discovery
reference. Offline instruction guards live in `test_planning_decomposition_contract.py`.

Shared evidence: the request is `read-only: improve reliability`. The repository
map identifies `packages/api`, its `packages/storage` dependency and unrelated
`packages/gallery`. Accepted specifications, API source and failing regression
output support an API retry fix with observable acceptance: one transient failure
retries once, while a permanent error does not retry. Storage's documented atomic
write contract and current source/test evidence support that fix. Supplied issue
readbacks show no covering issue or active owner. Remaining gallery layout
uncertainty cannot affect the API batch. No other selection-changing choice is
identified. Checks proposed by the planner stay proposed/unrun.

| Case / evidence delta | Expected decision and user-visible result |
| --- | --- |
| **Stable frontier** — shared evidence unchanged. | Stop widening. Return the supported API task contract inline with source evidence, acceptance and the issue/ownership disposition. Record the API/storage inspected boundary and why gallery uncertainty cannot change selection. Leave gallery uninspected, not gap-free. Save nothing. |
| **Material prerequisite** — same inputs, except storage's atomic write guarantee is now UNKNOWN: the proposed retry may duplicate a committed write. | Widen into storage's write/commit implementation and tests before selecting the retry work. Resolve the named duplication risk rather than inspect gallery. If evidence confirms non-idempotent writes, plan the real safety prerequisite before retry work. If storage evidence is unavailable, report `Storage commit/idempotency evidence unavailable; retry work pending`, name the required source/test evidence and resume condition, and continue only independent supported work. No early-stop claim while that risk remains. |
| **Existing coverage** — stable inputs, except supplied current readbacks show open issue #800 already covers the retry outcome, acceptance and verification, and its linked PR #801 has an active owner. | Reuse #800 and preserve its owner/PR. Report coverage and zero new tasks; do not create replacement findings, audit gallery to fill an allowance or claim delivery. |
| **Explicit batch** — replace the discovery request with the nine specified outcomes in `cases.json`'s `native-for-bulk` case. | Apply the full requested-batch contract: account for all nine outcomes, reusing FMT-01 and retaining only the specified unresolved choice on affected work. Neither a supported first task nor the eight-new-task discovery ceiling truncates the batch. Preserve real prerequisites and independent lanes. |

The pair differs only in the storage prerequisite evidence. Grade the actual
reads, final response and absence of writes if a model evaluation is later run.
Static checks and this table do not prove model adherence or live qualification.

## Paired recovery specimens and expected outcomes

These synthetic pairs use the same inputs for both canonical planners. All intent
is accepted and engineering choices are delegated: Plan With Me asks only for
consequential intent/authority still unresolved outside that delegation; Plan For
Me resolves supported engineering choices. Both preserve accepted answers, with
no implementation during planning. The requests prohibit remote publication and
live inspection: issue states below are supplied specimens, not GitHub readbacks.

| Specimens | Expected outcome |
| --- | --- |
| `plan-with-me-guard-refresh`, `plan-for-me-guard-refresh` | Cite `docs/session.md`, `src/session.py` and the consumer's missing `refresh()`; retain the stale-state guard and negative cases. Return the failed operation and source-backed repair/check to the same coordinator for existing owned issue #700, without a replacement or forced acceptance split. |
| `plan-with-me-original-oracle`, `plan-for-me-original-oracle` | Use a narrow provenance stage to preserve original oracle bytes and identity (`sample-amber-v1`, including its final newline). Record original versus proposed derived evidence, preset/revision lineage and authorized future changes in the existing provenance owner. Never overwrite/re-baseline the original, invent a violet result or require a registry/format. |
| `plan-with-me-recovery-qualification`, `plan-for-me-recovery-qualification` | Keep historical/current/unverified observations distinct: host-a's old service claim cannot prove host-b's current presence, and permission denial cannot prove absence. Record mismatch and uncertainty without a new live inspection. Display recovery has its own acceptance; qualification remains unmet until actual Android/app checks run. Retain the native dependency only on the real recovery prerequisite (#702 blocked by #701, already satisfied); independent repairs stay independent (#703 has no dependencies). Do not force a split of an existing owned issue. |

Normally give one useful progress update and a compact final receipt: issue links
(or explicitly UNSAVED proposed deltas here), ready/waiting/proposed state, native
dependencies, actual checks and unmet gates. Extra updates need a material blocker
or long-running work, not a message quota. No supplied evidence proves current
Orbi pickup or timers; Kit remains paused and live-unqualified.

`test_planning_decision_closure.py` checks these paired inputs and expected-outcome
coverage. This is static instruction/fixture evidence, not model adherence or live
qualification. The [Tier 3 writable-fresh-helper-publication pilot](../../../evals/README.md#planning-pilot-writable-fresh-helper-publication)
grades synthetic investigation, successful `github_issues.py --apply` and final
receipt events for a selected publication path. It does not evaluate these #33
recovery specimens or model adherence, and is not a universal planning-outcome gate.

The [original evaluation criteria](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/tests/fixtures/planning/README.md)
remain immutable requirements evidence. In particular, preserve accepted decisions,
ask only consequential unresolved questions, do not manufacture product direction
or approval, do not duplicate existing work, and distinguish planning publication
from implementation and live acceptance.

## Paired decision-branch scenarios

These are specified model cases, **NOT_RUN**, not transcripts or model-compliance
results. For each row, start a fresh context for `/plan-with-me <request>` and
`/plan-for-me <request>` with the same supplied evidence. Inspect the final text
and all tool calls/writes. The writable variants use only a disposable repository
and simulated GitHub; do not publish real issues or activate Orbi. Neither command
implements, starts a service or starts a second coordinator. A supplied read-only
request permits no local, scratch, Git or GitHub writes.

| Case / request and evidence for both commands | Plan With Me expected | Plan For Me expected |
| --- | --- | --- |
| **Specified/read-only:** `read-only: plan rejecting blank names with ValueError; preserve nonblank input; add a unit regression; no API redesign`. Source has a single name validator, no governing conflict. | No interview. Return the complete proposed plan inline; nothing saved or dispatched. | Same no-interview, inline, zero-write result. |
| **Specified/writable:** Same request without `read-only`; allow normal publication. | No interview. Preview outcome, acceptance and prerequisites, then follow Plan Handoff. Read back the whole batch, publish `ai-ready` last and return verified links. | Same writable publication path; record any delegated engineering choice as the planner's call. |
| **Thin intent:** `questions only: help me plan something better`; repository is an empty scaffold without accepted direction. | Play back the little that is known. Ask one highest-impact open question about a real situation; zero invented tasks. | Investigate first, then report missing intent and the one decision/input needed; explicit disposition, no manufactured roadmap or writes. |
| **Supported drafts:** `questions only: plan invoice CSV export for accountants; required fields are invoice ID and total, but the date-range behavior is undecided`. Existing invoice data supports export. | Playback includes evidence-supported draft export work, marked draft. Ask the highest-impact missing intent question about date range; do not reconfirm the named users or fields. | Resolve supported engineering choices; hold only genuinely missing product intent with its exact question/resume condition. Show proposed contracts inline for actionable work. |
| **Settled approach:** `read-only: plan the accepted cache change`; accepted ADR fixes LRU, capacity 100, and blank-input errors. Current source has no cache. | Cite the ADR; proceed to acceptance and verification, without reopening alternatives or asking filler questions. | Same settled-spec path; no obligatory comparison. |
| **Material trade-off:** `read-only: plan caching for repeated lookups`; source permits either bounded LRU or TTL; no governing decision; freshness versus hit rate changes product behavior. | Investigate facts, explain the realistic trade-off and recommendation, then ask the consequential missing freshness choice. | Choose an evidence-supported approach within delegated scope, explain its trade-off and mark the planner's call. Ask only if necessary product intent cannot be derived or delegated. |
| **Discovery/missing intent:** `plan this project`; scaffold has no accepted objective or meaningful implementation. | Playback plus one consequential intent question; do not invent tasks. | Investigate, report missing intent with evidence and exact resume decision as an explicit disposition; zero new issues is valid. |
| **Discovery/covered:** `plan this project's accepted reliability work`; current issues already cover every accepted gap, with read-back ownership/links supplied. | Reuse settled answers and existing issue links; report covered dispositions without duplicates or a filler interview. | Reconcile every accepted outcome to existing issues; report coverage and no new work. No duplicate issues or empty planning commit. |
| **Discovery/no-write:** `read-only: improve reliability`; source demonstrates one uncovered accepted error-handling gap. | If a consequential intent choice remains, ask only that question with supported drafts; otherwise return the plan inline. No writes. | Complete proposed contract inline for the evidenced gap, with acceptance and proposed/unrun checks; explicit no-write disposition, not planning failure or saved-plan claim. |
| **Publication/partial:** Writable two-issue plan, A precedes B. Simulate B's dependency drift after A publishes, as in `test_apply_entry_point_reports_success_or_preserves_partial_publication`. | For `Publication incomplete: #2: dependency readback failed`, use the per-issue receipt: A's verified link and ready state remain; B is saved/held with its link and last verified state. Do not call the batch UNSAVED or blindly replay. | Same per-issue failure result and safe resume instruction. Reconcile fresh contracts, ownership and native graph using the original stable keys before retrying. |
| **Publication/unknown:** Simulate a readiness timeout for B after A succeeds, with failed recovery reads; separately simulate an ambiguous create followed by a never-attempted create. Existing helper tests supply these receipts. | Preserve A's verified result. B's saved identity is not UNSAVED; interrupted writes remain UNKNOWN with retained last verified state. Only a never-attempted creation is UNSAVED. A timed-out create is not proof of absence. | Same evidence distinctions; preserve the diagnostic and transient input. No rollback, replacement keys, second queue or automatic retry. |
| **Coordinator boundary:** Existing Orbi-owned issue has runtime failure but no new product uncertainty; supply the failed operation and retained candidate evidence. | Return evidence and findings to that same coordinator; no replacement issue, restarted interview or execution inside planning. | Same return path; resolve any supported engineering planning gap without redispatch or acceptance waiver. |

Static routing/branch checks in `test_planning_decision_closure.py` and
`test_planning_cli_contract.py` check instruction delivery, not these model results.
`test_github_issues.py` exercises the actual helper `main` entry point with a fake
GitHub transport: two-issue partial drift, readiness timeouts, ambiguous creation
and never-attempted creation. Those simulated receipts are not observed GitHub
publication or proof that a model selects or summarizes the correct branch.
