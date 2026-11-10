+++
schema = 1
id = "RUST-STATUS-01"
title = "Expose versioned read-only Rust task and journal status"
short = "Expose versioned read-only Rust task..."
status = "open"
goal = "RUST-OCTET"
section = "Next"
rank = 26000
depends_on = []
touches = ["pi-autowork/rust/autowork/src/main.rs", "pi-autowork/rust/autowork/src/task_store.rs", "pi-autowork/rust/autowork/src/state.rs", "pi-autowork/rust/autowork/tests/cli.rs"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Add status --repo PATH --json to autowork-next using TaskStore::read_at committed snapshots and existing StateStore projection semantics. Read persisted state without create/reconcile/open side effects; absent/corrupt state is unavailable, never healthy. Output versioned task counts, dependency/readiness and observed journal uncertainty; no service/Paseo integration."
acceptance = ["CLI fixtures prove versioned JSON for committed ready/blocked tasks and absent/corrupt/uncertain journal state.", "Read probes preserve repository, pending task edits and state bytes; no DB creation, reconciliation, model calls or process lifecycle effects."]
checks = ["cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml --test cli --test task_store --test state_recovery"]
exclusions = ["No live models, service operations, installation, provider/auth changes, general shell, upstream edits, cutover or retirement. No widening authority."]
+++
- Sources: docs/plans/rust-octet-autowork.md#next-bounded-batch-read-surfaces-and-task-command-parity
