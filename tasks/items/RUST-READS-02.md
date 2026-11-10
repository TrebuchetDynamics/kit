+++
schema = 1
id = "RUST-READS-02"
title = "Expose committed Rust task list and show queries"
short = "Expose committed Rust task list and s..."
status = "open"
goal = "RUST-OCTET"
section = "Next"
rank = 29000
depends_on = []
touches = ["pi-autowork/rust/autowork/src/main.rs", "pi-autowork/rust/autowork/tests/cli.rs", "pi-autowork/rust/autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Add tasks --repo PATH list and tasks --repo PATH show ID with optional --rev COMMIT (default HEAD). Route reads before mutation/capture through TaskStore::read_at, preserving committed-only semantics and versioned JSON with pinned revision, task identity, typed metadata and exact original record content. Unknown IDs and invalid revisions fail explicitly. Do not use StateStore::open, reconcile, apply or capture_pending for queries."
acceptance = ["Offline CLI fixtures prove list/show pin HEAD or an explicit older commit, preserve original record content and omit pending edits.", "Invalid IDs/revisions fail explicitly; poisoned Git environment cannot redirect reads. Repeated queries create no locks, task edits or runtime state; existing mutation/status CLI tests pass."]
checks = ["RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml --test cli --test task_store"]
exclusions = ["No live models, credentials, upstream changes, general shell, service operations, installation, migration or retirement; no authority expansion."]
+++
- Sources: docs/plans/rust-octet-autowork.md#round-three-batch-committed-task-queries
