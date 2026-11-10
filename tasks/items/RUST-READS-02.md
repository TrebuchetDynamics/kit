+++
schema = 1
id = "RUST-READS-02"
title = "Expose committed Rust task list and show queries"
short = "Expose committed Rust task list and s..."
status = "done"
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
closure = "manual"
closure_actor = "interactive-codex"
closure_timestamp = "2026-11-10T18:34:32.865946+00:00"
closure_reason = "Implemented committed list/show with pinned revisions, typed metadata and exact content before mutation services. Twelve locked offline CLI/task-store tests pass, including historical revisions, pending-byte preservation, invalid inputs and poisoned Git routing. Independent read-only review approved; no runtime/live qualification."
closure_evidence = "/tmp/kit-rust-queries-check.log; pi-autowork/rust/autowork/tests/cli.rs"
+++
- Sources: docs/plans/rust-octet-autowork.md#round-three-batch-committed-task-queries
