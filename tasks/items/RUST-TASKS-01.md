+++
schema = 1
id = "RUST-TASKS-01"
title = "Add Rust pending task mutation command parity"
short = "Add Rust pending task mutation comman..."
status = "open"
goal = "RUST-OCTET"
section = "Next"
rank = 27000
depends_on = []
touches = ["pi-autowork/rust/autowork/src/main.rs", "pi-autowork/rust/autowork/src/task_store.rs", "pi-autowork/rust/autowork/tests/task_store.rs", "pi-autowork/rust/autowork/tests/cli.rs"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Expose tasks add, field, place and pending preview through the existing TaskService::apply and capture_pending seams. Match current Python typed field validation, dated decision notes and unknown-note preservation. Mutations require expected committed revision; preserve live/owner/verified-dependency guards. Return pending edit identity, never auto-select or imply publication. Existing Coordinator remains sole publication owner."
acceptance = ["Offline fixtures compare add/field/place and dated decisions against current Python contracts, including unknown fields, notes and schema validation.", "Stale revision, concurrent pending edits, protected grants and failed transactions preserve original bytes; output distinguishes pending from committed/selectable."]
checks = ["cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml --test cli --test task_store --test state_recovery"]
exclusions = ["No live models, service operations, installation, provider/auth changes, general shell, upstream edits, cutover or retirement. No widening authority."]
+++
- Sources: docs/plans/rust-octet-autowork.md#next-bounded-batch-read-surfaces-and-task-command-parity
- Scope: Expose tasks add, field, place and pending preview through existing TaskService::apply and capture_pending seams for planner-admissible ordinary records only. Preserve unknown notes and typed validation. Reject protected Owner decision writes, --decision, live/owner grants and verified-dependency mutations explicitly; trusted human decision parity is deferred. Require expected committed revision and return pending edit identity, never auto-select or imply publication. Existing Coordinator remains sole publication owner.
- Acceptance: ["Offline fixtures prove ordinary add/field/place and preview behavior with unknown-field/note preservation and schema validation. Protected --decision/Owner decision changes are explicitly refused without weakening planner_authority.", "Stale revision, concurrent pending edits, protected grants and failed transactions preserve original bytes; output distinguishes pending from committed/selectable."]
