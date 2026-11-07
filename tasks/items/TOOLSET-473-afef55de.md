+++
schema = 1
id = "TOOLSET-473-afef55de"
title = "Run owned native Octet agents with role-specific tools and cancellation"
short = "Own native Octet agent runs"
status = "done"
goal = "RUST-OCTET"
section = "Next"
rank = 9000
depends_on = ["TOOLSET-472-48c78e95"]
touches = ["rust/autowork/src/runtime.rs", "rust/autowork/tests/runtime_native.rs", "rust/autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Implement the Runtime and AgentRequest seam using public Agent/AgentConfig/Session/RunControl from pinned octet-agent and octet-ai. Each role runs in the binary's internal owned-agent child mode, with fresh context, PID/birth identity, contract hash and generation. Configure a fixture/local OpenAI-compatible provider through Octet for deterministic offline checks; production configuration uses explicit model/provider and secret references resolved only at the agent boundary, never raw credentials in journal/task/output. Keep the Controlled broker and workspace tools; planner/reviewer register only reads and no process/extensions. Worker edits require exact current-generation task authority via ephemeral broker confirmation. The only check execution seam in this round is coordinator-authored fixed argv; no model-authored general shell, UnsafeHost or automatic executable-extension loading. Drain events/stdout/stderr with bounded records and secret-safe diagnostics, propagate cancel/timeout, retain sessions and mark post-dispatch uncertainty honestly. No Octet-host write flag fiction and no global auth import. Consume only the coordinator-issued immutable ExecutionAdmission outside prompt text. Use public transform_tool_call typed name/argument checks before the Controlled broker, and recheck identity/generation before replying to eligible CoreTools edit/write confirmations; never parse presentation strings as grants. Deny coordinator task records, BLOCKERS/CHANGELOG/archive, .git/common runtime roots, undeclared in-workspace paths and aliases/symlinks. Consume native confirmation channels in the child and emit normalized RuntimeEvent JSON to the parent."
acceptance = ["Given a local fixture provider emitting a workspace edit, a worker admitted under its frozen task writes the expected file through the real Octet Agent while a planner/reviewer cannot mutate or spawn a process; runtime_native.rs::native_roles_enforce_task_authority proves both paths without a live provider.", "Given wrong generation or a canceled/dropped owned child, runtime_native.rs::cancel_and_stale_run_are_not_success asserts only that owned child is stopped/reaped, late output cannot settle another attempt, retained session/uncertainty evidence exists, and an unrelated process survives.", "Given fixture credentials and undeclared in-workspace paths including tasks/, BLOCKERS.md and .git plus external/aliased targets, runtime_native.rs::reject_scope_and_redact_secret proves typed admission refuses every unauthorized write and credentials remain absent from persisted events/diagnostics, without parsing confirmation prose or relaxing policy."]
checks = ["cargo test --locked --manifest-path rust/autowork/Cargo.toml --test runtime_native"]
exclusions = ["No live models, device operations, service changes, old-runtime cutover, push or deployment in offline acceptance.", "No changes to upstream Octet, unrelated work or existing user grants."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/TOOLSET-473-afef55de.toml"
+++
- Sources: docs/plans/rust-octet-autowork.md#accepted-direction; docs/plans/rust-octet-autowork.md#first-implementation-batch
- Planner calls: Consumes: AgentRequest and versioned role/result seams from foundation. Produces: native Octet Runtime event stream, cancel identity and role admission used by planner and coordinator. Existing SDK source proves APIs, not implementation compatibility; run these proposed tests when implementing.
- Verification: Proposed checks and test names are unrun until implementation; no model/live qualification is claimed.
- Queue disposition: Open in Next; no planning-only hold. Explicit user scope and existing ownership still govern execution.
- Builder resolution: Resolved from fresh read-only builder findings: Consume only the coordinator-issued immutable ExecutionAdmission outside prompt text. Use public transform_tool_call typed name/argument checks before the Controlled broker, and recheck identity/generation before replying to eligible CoreTools edit/write confirmations; never parse presentation strings as grants. Deny coordinator task records, BLOCKERS/CHANGELOG/archive, .git/common runtime roots, undeclared in-workspace paths and aliases/symlinks. Consume native confirmation channels in the child and emit normalized RuntimeEvent JSON to the parent.
- Pending live: Live-provider/model and production credential qualification remain unrun. This task authorizes only deterministic local fixtures, not live models, service changes, deployment or installed-runner cutover.
