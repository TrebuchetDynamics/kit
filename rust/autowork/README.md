# Native-Octet Autowork candidate

This Linux Rust component provides an owned-agent runtime, not the installed
Python runner. `version` and `capabilities` work without a model. The coordinator
`run` command remains unavailable. This component does not install a service,
import global authentication, or replace an existing runner.

See the [accepted design](../../docs/plans/rust-octet-autowork.md),
[dependency pin and build prerequisites](../../docs/dependencies.md#rust-autowork-candidate),
and [upstream license notice](THIRD_PARTY_NOTICES.md).

## Build and offline checks

From the repository root, use Rust/Cargo 1.95.0, Git, a C compiler and a linker.
The task store also uses the Linux `sha256sum` and `date` utilities:

```sh
RUSTUP_TOOLCHAIN=1.95.0 cargo build --locked --manifest-path rust/autowork/Cargo.toml
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path rust/autowork/Cargo.toml --test runtime_native
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path rust/autowork/Cargo.toml --test cli
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path rust/autowork/Cargo.toml --test task_store
```

The native tests use a local OpenAI Chat-compatible HTTP fixture through the real
Octet `Agent`. They need no live provider or credentials. They use ports within
`AUTOWORK_PORT_BASE` through `AUTOWORK_PORT_BASE+6` when that variable is set.
Otherwise, the operating system assigns local ports. Test files use `TMPDIR`.

| Native test | Offline evidence |
| --- | --- |
| `native_roles_enforce_task_authority` | Worker edits through CoreTools and Controlled broker confirmations. Planner/reviewer tool lists contain only `read`. No role can invoke a process tool. |
| `cancel_and_stale_run_are_not_success` | Reject mismatched and consumed generations. Revoke stale authority. Cancel, timeout, receiver drop and owner drop reap only the owned child. Retain session and uncertainty records. Late responses cannot settle another attempt. |
| `reject_scope_and_redact_secret` | Deny undeclared, protected, external, symlink and hard-link targets. Keep fixture credentials out of retained evidence and projected events, including provider-error diagnostics. |

These checks do not qualify a live provider, task completion, integration,
publication, deployment, devices or sustained service operation.

## Revision-bound task store

[`task_store.rs`](src/task_store.rs) implements the current
[schema-1 contract](../../pi-autowork/task-store.md), without a Python runtime or
another queue. `TaskStore::read_at(repo, revision)` resolves a commit once, disables
Git replacement refs and inherited `GIT_*` redirection, and eagerly reads its
records and evidence. `Snapshot::revision()`, `records()`, `tasks()` and `goals()`
expose immutable views. Record revisions hash exact bytes; contract hashes retain
the current canonical JSON rules. Free Markdown notes and historical IDs are not
rewritten. Missing task fields remain drafts; malformed records refuse the store.

`Snapshot::select(&Scope)` orders eligible IDs by focus, section, rank, goal
priority, goal status and ID. An empty scope includes all tasks, including planning
tasks. `Selection::blocked` names blocking rules. `select_on(scope, YYYY-MM-DD)`
accepts an explicit local date for repeatable expiring-hold decisions; `select`
uses today's local date. Needs-decision records, holds, unfinished dependencies
and unqualified verified dependencies stay blocked. A passing receipt must bind
the contract to a real two-parent integration ancestor and its candidate/tree;
legacy waiver prose alone qualifies nothing. Selection does not evaluate runtime
pauses, leases, resources or caller authority. The coordinator must retain those
admission gates and protect active contracts before applying a proposal.

`TaskService::new(repo_root)` binds writes to one checkout. `apply(base, proposal)`
requires the full HEAD commit in both base fields, plus each changed record's
SHA-256 revision (an empty string means a new path). It validates the whole proposed
store before writing, compares inputs again, and preserves the proposed bytes
without normalization. Planner changes cannot alter existing ownership, closure,
owner attestations, live gates or protected evidence/hold/owner notes. The result
is only `PendingEdit`; committed selection does not advance.

Writers and recovery hold `<git dir>/autowork-tasks.lock`. A flushed
`autowork-rust-tasks.transaction` undo journal precedes replacements. Removing and
syncing the journal commits the working-tree batch, not a Git revision. `recover()`
(and the next `apply`) rolls back an interrupted batch. Recovery preserves external
edits and retains the journal/original bytes on conflicts; reconcile the named
paths, journal and any `.autowork-rust.undo` file before retrying. Do not delete a
journal to bypass recovery. Python journals require recovery by their owning
runtime; never run Python and Rust writers concurrently. Direct editors that skip
the lock do not get an atomic multi-file view.

`capture_pending()` refuses an interrupted transaction without recovering it. It
returns frozen `base_head`, full branch ref, candidate `tree`, all candidate
record `captured_bytes` and a content-bound `token`. A temporary index starts at
HEAD and changes only task/goal record entries, using exact bytes without Git
clean filters. Unrelated staged content and pending evidence edits cannot enter
that tree; the real index, refs and HEAD stay unchanged. Candidate blobs/trees
remain in Git's object database for publication. A pending tree/token is not a
selectable committed revision. The coordinator owns drift checks, tasks-only
commit publication and publication crash recovery; this API never commits or pushes.

The Rust-owned fixtures retain the existing schema-1 sample and static SHA-256
expectations. `pinned_selection_preserves_contracts` covers selection, notes,
drafts, holds and dependency evidence. `transaction_refuses_stale_or_invalid_records`
covers revision/authority refusal, batch validation, interrupted recovery,
cooperative locking and index-isolated capture. These are offline checks, not
runtime admission or live task-completion evidence.

## Coordinator API and authority

[`runtime.rs`](src/runtime.rs) defines `Runtime::new(executable, evidence_root,
models, timeout)`. Supply the absolute path of the built `autowork-next` binary,
an existing private evidence directory outside the workspace, an explicit
`BTreeMap<String, ModelRoute>`, and a nonzero wall-time limit.

Each route has these fields:

- `provider`: `openai_chat`. No other protocol is implemented in this slice.
- `model`: the provider's explicit API model name.
- `base_url`: an HTTPS base URL with a trailing slash. Literal loopback HTTP is
  also supported for local providers and offline fixtures. User information,
  query strings and fragments are refused.
- `secret_file`: an optional private regular-file reference outside the
  workspace. The child reads the bearer token at the agent boundary. The file
  must have no group/other permissions or extra hard links and be at most
  4096 bytes. Do not put a token in the route, prompt, model reference or task.

`Runtime::run(AgentRequest)` returns a bounded `Receiver<RuntimeEvent>`. A request
selects a registered route through `model_ref`. The coordinator supplies the
frozen `ExecutionAdmission` separately from `prompt`. Repository/workspace
canonical paths and device/inode identities must match. Task, attempt,
generation, role and contract hash must agree with the admission.

Allowed writes are **exact normalized relative file paths**, not directory
prefixes or globs. Only workers receive `read`, `edit` and `write`. Planner and
reviewer receive `read` only. All roles deny protected task records,
`BLOCKERS.md`, `CHANGELOG.md`, `TODO.archive.md`, `.git`, resolved Git/common roots,
explicit denied paths and path aliases. The native workspace resolver and secure
file operations remain active. There is no shell, process tool, executable
extension discovery or `UnsafeHost` policy.

The child uses Octet's public `transform_tool_call` hook to validate typed tool
names and path arguments before broker admission. It answers only the matching
CoreTools edit/write confirmation after checking the host lease, generation,
workspace identity and path again. It never derives grants from confirmation
prose. Unknown input requests are canceled.

A task cannot have two active runs in one runtime. After reaping, a new attempt
must use a higher generation. `Runtime::cancel(RunIdentity)` rejects a different
identity, revokes the lease and waits for reaping. Receiver drop and runtime
owner drop also revoke the run. Cancellation uses the owned stdin control pipe
and native `RunControl::abort`, with a bounded grace period before killing the
owned `Child` handle. It never signals an unrelated PID or process group.

The coordinator remains responsible for repository scheduling, durable generation
admission across restarts, role instructions, checks, independent review and
closure. `CheckOperationSpec` entries remain coordinator data. They do not install
model-callable tools. This runtime executes no check strings or model-authored
argv. Fixed-argv check execution belongs to the coordinator's separate boundary.

## Events, evidence and recovery

The hidden `internal-agent` route consumes one bounded JSON request line. Its
configuration comes from the runtime-owned child environment, not the prompt.
The remaining stdin pipe is cancellation/liveness control. This is an internal
embedding route, not a public unattended-write CLI option.

Every run creates a fresh Octet session in a private operation directory.
`owned_process(identity)` exposes its PID, Linux birth ticks and evidence path.
The runtime retains `owner.json`, `uncertainty.json`, `session.jsonl`,
`diagnostics.json` and `outcome.json`. The coordinator must retain and reconcile
these records before retrying an uncertain mutation. Do not adopt a process from
its PID alone or treat a retained session as task acceptance.

Child output contains normalized schema-1 accepted/progress/usage/outcome JSONL.
Each record is at most 16 KiB. Progress is capped and may be coalesced or dropped
under backpressure. Usage events mark native turn boundaries; accounting details
remain in the native session. The parent validates identity and waits for child
exit before emitting the terminal outcome. A missing terminal event, stream
failure or nonzero child exit is not success.

Projected events contain no model/tool text, credentials, environment dumps or
provider error bodies. Diagnostics retain only status and the discarded stderr
byte count. Native sessions are separate private transcripts, not sanitized public
logs. Keep their file contents private. A `succeeded` runtime outcome means only
that Octet completed the run. It does not prove that the task or its checks passed.
