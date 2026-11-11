+++
schema = 1
id = "RUST-GOALS-01"
title = "Expose committed goal reads and pending ordinary metadata edits"
short = "Expose committed goal reads and pendi..."
status = "done"
goal = "RUST-OCTET"
section = "Now"
rank = 2000
depends_on = []
touches = ["pi-autowork/rust/autowork/src/main.rs", "pi-autowork/rust/autowork/src/task_store.rs", "pi-autowork/rust/autowork/tests/cli.rs", "pi-autowork/rust/autowork/tests/task_store.rs", "pi-autowork/rust/autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Add goals --repo PATH list/show ID with --rev COMMIT default HEAD, routing through TaskStore::read_at and Snapshot::goals before mutation services. Add pending goals add ID --record FILE and field ID KEY JSON using expected base commit and exact working-record digest. Extend TaskService record_for_edit with a bounded goal-record seam and apply-time CAS; reuse pending base/hash output. Permit only title/source/priority/focus/depends_on ordinary metadata. Refuse progress/status, closure, qualification and owner/live authority changes. Preserve current goal bytes/notes and other pending edits; no auto-commit or selectable pending state."
acceptance = ["Offline list/show fixtures preserve exact committed goal content, pinned historical revisions and typed metadata while ignoring pending bytes and Git redirection. Unknown IDs/revisions fail without creating runtime/task state.", "Offline add/field fixtures prove typed validation, sequential pending-edit preservation, stale base/record refusal, unknown-note preservation and correct pending identity. Protected goal progress/authority cannot be changed or created as met; rejected edits preserve bytes and existing task/status commands still pass."]
checks = ["RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml --test cli --test task_store"]
exclusions = ["No live models, credentials, upstream edits, general shell, service operations, installation, migration, runtime retirement or authority expansion."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/RUST-GOALS-01.toml"
+++
- Sources: docs/plans/rust-octet-autowork.md#round-four-batch-goal-command-parity
- Owner decision: 2026-11-10: pruebas
