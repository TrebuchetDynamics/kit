+++
schema = 1
id = "TOOLSET-476-fb27960d"
title = "Resolve ordinary blockers through automatic revision-bound planning"
short = "Replan without owner menus"
status = "open"
goal = "RUST-OCTET"
section = "Next"
rank = 12000
depends_on = ["TOOLSET-473-afef55de", "TOOLSET-474-6b517117", "TOOLSET-475-66aacc5f"]
touches = ["rust/autowork/src/planning.rs", "rust/autowork/tests/planning_reentry.rs", "rust/autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Implement Planner::propose and coordinator-validated PlanProposal dispositions from the accepted plan. On design gaps, repeated repair failures, a gated queue or no accepted runnable task, run a read-only fresh-context Octet planner using the bundled Plan For Me/RESEARCH-PLAN instructions and current failure/source evidence. Apply complete record changes only through TaskService with expected revision, contract, failed-operation fingerprint and current generation. Preserve acceptance and in-flight contracts; split real prerequisites, repair routine inputs or discover useful offline work instead of asking the owner to choose a task. Only observed sudo_required/credential_required prerequisites enter routine owner-help; transient waits, explicit pauses and safety refusals retain their distinct state. Keep secrets out of proposals. Reuse evidence to avoid repeated planning on identical inputs; quiescence requires a bounded source-backed exhausted search, not a no-task response. The model never writes tasks or marks itself done. Return PendingEdit/token to the coordinator after validated application; do not select from an uncommitted proof tree. The coordinator's commit_proposal publishes it locally before committed selection. Never emit or expand ExecutionAdmission, executable identity or arbitrary check argv from model proposals."
acceptance = ["Given a design ambiguity, repeated failed repair or a queue consisting of live-gated tasks, planning_reentry.rs::replan_and_select_independent_offline_work proves a validated useful offline contract is applied and a pending publication token is handed to the coordinator without an owner-choice menu. No selection advances until the coordinator commits that snapshot; original live/acceptance gates and immutable execution grants remain.", "Given structured sudo/credential prerequisites, stale proposal revisions or identical failed-operation fingerprints, planning_reentry.rs::classify_owner_help_and_reject_stale_plan proves only the two routine help reasons request owner input, unsafe/stale proposals cannot mutate records, and unchanged evidence does not cause an infinite plan loop."]
checks = ["cargo test --locked --manifest-path rust/autowork/Cargo.toml --test planning_reentry"]
exclusions = ["No live models, device operations, service changes, old-runtime cutover, push or deployment in offline acceptance.", "No changes to upstream Octet, unrelated work or existing user grants."]
+++
- Sources: docs/plans/rust-octet-autowork.md#accepted-direction; docs/plans/rust-octet-autowork.md#first-implementation-batch
- Planner calls: Consumes: Runtime read-only planner role; TaskStore/TaskService; StateStore transition/reconcile. Produces: revision-bound PlanProposal and disposition behavior consumed by run_until_quiescent. Physical/live gates are preserved, not reclassified as authorization.
- Verification: Proposed checks and test names are unrun until implementation; no model/live qualification is claimed.
- Queue disposition: Open in Next; no planning-only hold. Explicit user scope and existing ownership still govern execution.
- Builder resolution: Resolved from fresh read-only builder findings: Return PendingEdit/token to the coordinator after validated application; do not select from an uncommitted proof tree. The coordinator's commit_proposal publishes it locally before committed selection. Never emit or expand ExecutionAdmission, executable identity or arbitrary check argv from model proposals.