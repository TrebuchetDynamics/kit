+++
schema = 1
id = "SESSION-RUST-IDENTITY"
title = "Accept journal repository identities at the Rust runtime boundary"
short = "Accept journal repository identities..."
status = "open"
section = "Now"
rank = 11000
depends_on = []
touches = ["rust/autowork/src/runtime.rs", "rust/autowork/tests/runtime_native.rs", "rust/autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Repair the reproduced mismatch between StateStore canonical repository identity and Runtime AgentRequest validation. Treat repository identity as opaque host-issued bounded nonempty text with no control characters and exact admission equality; retain strict safe tokens for all filesystem/execution identifiers. Preserve journal metadata and existing state identity without migration or a second mapping."
acceptance = ["A native runtime regression using the actual StateStore repo_id succeeds with matching admission, rejects mismatched/control/oversized identities, and all prior runtime and state safety tests pass."]
checks = ["cargo test --locked --manifest-path rust/autowork/Cargo.toml --test runtime_native --test state_recovery"]
exclusions = ["No dependency changes, journal migration, weakened task/attempt/path token guards, live model/service calls, upstream changes or publication."]
+++
- Sources: docs/plans/rust-octet-autowork.md#first-implementation-batch
