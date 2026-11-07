+++
schema = 1
id = "TOOLSET-475-66aacc5f"
title = "Add a durable Rust runtime journal with generation-fenced crash recovery"
short = "Persist and reconcile run state"
status = "open"
goal = "RUST-OCTET"
section = "Next"
rank = 11000
depends_on = ["TOOLSET-472-48c78e95"]
touches = ["rust/autowork/src/state.rs", "rust/autowork/tests/state_recovery.rs", "rust/autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Implement StateStore in private per-repository local SQLite using bundled rusqlite, immediate transactions, WAL, full sync, foreign keys and a cooperative repository writer lock. Bind state to Git common-dir identity, operation/task/attempt IDs, contract/source and generation. Append events and state projection in one transaction with unique operation keys; implement intent/completion records and observation-driven reconciliation around nontransactional child/Git effects. Refuse unsupported newer schemas and non-local WAL use rather than resetting state; retain a backup for schema migrations. Source/consumer paths and sessions stay distinct. Do not import or write the old Python runtime database/files, launch processes, adopt bare PIDs or change task acceptance."
acceptance = ["Given injected crash boundaries before/after journal commits and external-effect completion, state_recovery.rs::recover_without_duplicate_effects proves committed transitions/projections agree and unresolved operations require reconciliation instead of blind replay or success.", "Given competing owners, PID reuse or stale generations, state_recovery.rs::fence_foreign_owner_and_schema proves only the verified current owner can transition and a newer schema is refused without changing retained state."]
checks = ["cargo test --locked --manifest-path rust/autowork/Cargo.toml --test state_recovery"]
exclusions = ["No live models, device operations, service changes, old-runtime cutover, push or deployment in offline acceptance.", "No changes to upstream Octet, unrelated work or existing user grants."]
+++
- Sources: docs/plans/rust-octet-autowork.md#accepted-direction; docs/plans/rust-octet-autowork.md#first-implementation-batch
- Planner calls: Consumes: foundation event/identity seams. Produces: StateStore transition/reconcile APIs used by planner and coordinator. SQLite atomicity does not cover subprocesses or Git; no exactly-once external-effect claim.
- Verification: Proposed checks and test names are unrun until implementation; no model/live qualification is claimed.
- Queue disposition: Open in Next; no planning-only hold. Explicit user scope and existing ownership still govern execution.