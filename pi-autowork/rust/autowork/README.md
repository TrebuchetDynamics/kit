# Native-Octet Autowork candidate

This Linux Rust candidate provides an owned-agent runtime, durable journal and
serialized local delivery coordinator, not the installed Python runner.
`version`, `capabilities`, `tasks` inspection/publication and `status` work without a model.
`run` requires explicit model
routes and an isolated repository. It does not install a service, import global
authentication, push, deploy or replace an existing runner.

See the [accepted design](../../../docs/plans/rust-octet-autowork.md),
[dependency pin and build prerequisites](../../../docs/dependencies.md#rust-autowork-candidate),
and [upstream license notice](THIRD_PARTY_NOTICES.md).

## Build and offline checks

From the repository root, use Rust/Cargo 1.95.0, Git, a C compiler and a linker.
The task store also uses the Linux `sha256sum` and `date` utilities:

```sh
RUSTUP_TOOLCHAIN=1.95.0 cargo build --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml --test runtime_native
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml --test cli
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml --test task_store
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml --test state_recovery
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml --test autonomous_cycle
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --manifest-path pi-autowork/rust/autowork/Cargo.toml --tests
```

The native tests use a local OpenAI Chat-compatible HTTP fixture through the real
Octet `Agent`. They need no live provider or credentials. Runtime tests use
`AUTOWORK_PORT_BASE` through `AUTOWORK_PORT_BASE+7`, and planning tests use `+8`,
when that variable is set. Otherwise, the operating system assigns local ports.
Test files use `TMPDIR`.

| Native test | Offline evidence |
| --- | --- |
| `native_roles_enforce_task_authority` | Worker edits through CoreTools and Controlled broker confirmations. Planner/reviewer tool lists contain only `read`. No role can invoke a process tool. |
| `cancel_and_stale_run_are_not_success` | Reject mismatched and consumed generations. Revoke stale authority. Cancel, timeout, receiver drop and owner drop reap only the owned child. Retain session and uncertainty records. Late responses cannot settle another attempt. |
| `reject_scope_and_redact_secret` | Deny undeclared, protected, external, symlink and hard-link targets. Keep fixture credentials out of retained evidence and projected events, including provider-error diagnostics. |

These runtime checks do not qualify task delivery. The coordinator checks below
exercise local integration and task-proposal publication in disposable repositories.
Neither set qualifies a live provider, deployment, devices, migration or sustained
service operation.

## Wire formats

One global `--format` option selects the wire contract of `status`, `tasks`, `goals`
and `capabilities`. It may appear before or after the subcommand.

| Format | Selected by | `status` | `tasks` | `goals` |
| --- | --- | --- | --- | --- |
| `public-v1` | default | committed tasks plus persisted runs of every generation, from a quiescent journal | `list`, `show`, `add`, `field`, `place`, `preview` | `list`, `show`, `add`, `field` |
| `inspection-v1` | `--format inspection-v1` | typed latest-generation journal projection, read beside a writer | `list`, `goals`, `show`, `why`, `commit` | unsupported |

A command outside the selected format is refused, never answered in the other
format's shape. `capabilities` lists both under `formats`. `--repo` and `--rev` are
accepted before or after the `tasks` or `goals` subcommand; `--rev` given twice is
refused, and a pending edit accepts only `--rev HEAD`. `status --json` is a
compatibility marker: output is always JSON and the flag selects nothing.

Pending commands require explicit `--offline` exclusion, including preview and
publication dry runs. Before task locks, scratch objects or journal construction,
they acquire Python dispatch/integration/writer locks and the native writer lease.
Any retained Python execution entry beyond those three lock files is refused,
even when it appears idle: its owning runtime must reconcile it. Unsafe paths or
busy locks also refuse. This conservative boundary supports repositories without
Python execution history; it is not an active-runner handoff or owner release.
Publication transfers the native lease into StateStore, retaining writer epochs,
CAS and recovery checks. Queries and status require no exclusion.

## Read-only status and pending task/goal commands (`public-v1`)

`autowork-next status --repo /path/to/repo --json` returns schema version 1,
committed task counts, dependency readiness and persisted journal observations.
Absent, corrupt, foreign or unsafe journals report unavailable. Both status formats
use the same validated SQLite read transaction, including private local paths and
sidecars, repository identity, and run-to-event linkage for every generation.
Public status preserves all generations; inspection status projects the latest
runs and the transaction's event high-water mark. Concurrent WAL readers may
create SQLite coordination sidecars. Reads never claim a writer epoch, migrate,
recover or change logical journal data. These are observed snapshots, not model
or service qualification.

`tasks --repo /path/to/repo list` and `tasks --repo /path/to/repo show ID`
return schema-versioned JSON from committed records only. Add `--rev COMMIT`
after `list` or `show ID` to pin an older snapshot. Responses include the full
resolved commit, typed task metadata and exact original record content. Unknown
IDs and invalid revisions fail explicitly. These reads ignore pending edits and
create no task locks or runtime state; Git environment overrides cannot redirect
them to another repository.

`--offline tasks --repo /path/to/repo --expected-revision COMMIT` accepts:

- `add ID --record /path/to/record.md`: validate a complete task record through the
  existing task service. A new ID needs an absent destination.
- `field ID --record-revision SHA256 title '"New title"'`: JSON values and an exact
  working-record revision prevent stale edits. Existing unknown notes survive.
- `place ID --record-revision SHA256 Next`: change the scheduling section.

`--offline tasks --repo /path/to/repo preview` captures the pending-edit identity. Mutation
results include their base revision and resulting record hashes. Follow-up edits
use those hashes and preserve earlier pending edits. They remain uncommitted and
unselectable until the existing coordinator publishes the validated snapshot.
Protected fields, Owner decision changes and `--decision` are refused by this
ordinary planning seam; no command grants live execution or publication.

### Goal commands

`goals --repo /path/to/repo list` and `goals --repo /path/to/repo show ID` use
committed snapshots only, with `--rev COMMIT` (default `HEAD`). The schema-versioned
response contains `goals` or `goal`, the resolved `revision` and `source: "committed"`.
Each row preserves all typed goal frontmatter, including its own `source`, integer
`priority`, boolean `focus` and optional `depends_on`, plus exact `content`, `path`,
`record_revision` and `contract_hash`. Pending bytes and Git environment redirection
cannot affect these reads. Unknown IDs/revisions fail without creating state.

`--offline goals --repo /path/to/repo --expected-revision COMMIT` accepts:

- `add ID --record /path/to/goal.md`: validate a schema-1 goal with a new ID and
  `status = "unmet"`. Existing destinations and invented authority notes are refused.
- `field ID --record-revision SHA256 priority '2'`: edit only `title`, `source`,
  `priority`, `focus` or `depends_on`, using JSON values of the schema's types.

These writes reuse the task service's full-HEAD base check, exact working-record
SHA-256 check and apply-time compare-and-swap. They preserve current notes and
other pending task/goal edits. Use the returned `base_revision` and
`record_revisions` for sequential edits; `tasks preview` captures their shared
pending identity. Nothing commits automatically or becomes selectable. Goal
status/progress, closure, qualification and owner/live authority are not writable;
existing protected notes remain unchanged. The pending-edit offline exclusion
above also applies to goals.

Offline CLI and task-store fixtures cover committed goal reads, historical pins,
typed edits, pending identity, note preservation, stale base/record refusal and
protected goal progress/authority. They do not qualify concurrent runtimes or live
execution.

## Revision-bound task store

[`task_store.rs`](src/task_store.rs) implements the current
[schema-1 contract](../../task-store.md), without a Python runtime or
another queue. `TaskStore::read_at(repo, revision)` resolves a commit once, disables
Git replacement refs and inherited `GIT_*` redirection, and eagerly reads its
records and evidence. `Snapshot::revision()`, `records()`, `tasks()` and `goals()`
expose immutable views. Record revisions hash exact bytes; contract hashes retain
the current canonical JSON rules. Free Markdown notes and historical IDs are not
rewritten. Missing task fields remain drafts; malformed records refuse the store.

### Committed inspection CLI (generation 1, `inspection-v1`)

```sh
autowork-next --format inspection-v1 tasks list --repo /path/to/repo
autowork-next --format inspection-v1 tasks goals --repo /path/to/repo --rev HEAD
autowork-next --format inspection-v1 tasks show TASK-ID --repo /path/to/repo --rev COMMIT
autowork-next --format inspection-v1 tasks why TASK-ID --repo /path/to/repo --rev COMMIT
```

`capabilities` advertises `contracts.task_inspection = 1` for these four inspection
verbs, plus the separate `commit` subset described below. Task-authoring verbs
(such as `field`) and `--worktree` are unsupported. Each inspection command resolves
`--rev` once (default `HEAD`); dirty and staged records cannot affect the result.
No task lock, proof commit, index update or ref write occurs. List/goals return
arrays; show/why return objects. Record rows expose exact typed frontmatter,
`body`, `record_revision`, `contract_hash`, `missing_fields`, `receipt_valid`,
`path` and a separate `snapshot` object with committed `source`, `ref`, `revision`
and `revision_ephemeral: false`. A goal's frontmatter `source` remains unchanged.
An unknown show ID fails; unknown why IDs return an `UNKNOWN_TASK` reason.

List rows and why objects add `position`, `blocked_by`, `eligible`, `first`,
`reasons` and the [selection-only source metadata](../../task-store.md#selection).
`POSITION` and `AFTER_*` reasons describe the existing selector's order; blocked
rows retain its hold, draft and dependency reasons. These outputs do not evaluate
admission or runtime availability. An owner-only or unauthorized live task may be
selectable without permission to dispatch it. No Python command parity, task
closure, goal qualification or live ownership is implied.

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

`TaskService::new(repo_root)` binds writes to one checkout. `record_for_edit` and
`goal_record_for_edit` read exact current working-record bytes under the task lock
with an expected digest; `apply` rechecks that digest before writing.
`apply(base, proposal)` requires the full HEAD commit in both base fields, plus each changed record's
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

## Durable runtime journal

[`state.rs`](src/state.rs) provides `StateStore::open(common_dir)`. The coordinator
supplies the consumer repository's resolved Git common directory, not its checkout,
the Kit source directory or an Octet session directory. The journal launches no
processes. It uses only `<common_dir>/autowork-rust/journal.sqlite3` and its own lock,
SQLite sidecars and migration backup. It does not read, import or write Python
runtime state. The pending CLI's separate `OfflineAdmission` boundary creates and
holds Python exclusion lock files; `open_offline` transfers those locks and the
native lease into the store for its lifetime. It never imports Python attempts or
receipts. Native sessions and source revisions remain separate inputs.

The directory must be owned by the current user with no group/other permissions.
Journal and lock files must also be private, regular and single-linked. The store
holds `writer.lock` exclusively until it is dropped. All cooperating Rust journal
writers for linked worktrees use that same common-directory lock. This does not
lock the Python runner, direct editors or external Git commands. Do not run the
Python and Rust coordinators against the same live work concurrently.

SQLite uses immediate write transactions, WAL, `synchronous=FULL` and foreign keys.
Linux mount information must identify a supported local filesystem: ext2/3/4,
XFS, Btrfs, ZFS, tmpfs or overlay. Network, FUSE and unknown mounts are refused.
Tmpfs supports restart recovery, not persistence across a host reboot. Unsupported
newer schemas and nonempty unversioned databases are refused without resetting
state. Schema 1 is the first version. Upgrading an existing empty schema-0 database
retains `journal.schema-0.backup.sqlite3`; reopening after an interrupted upgrade
validates and reuses that backup rather than overwriting it. Future nonempty schema
migrations need their own supported, backed-up migration.

Use `repo_id()` in each `RunIdentity`. It binds the journal to the canonical common
directory, device and inode. `claim(previous_generation, identity, source_revision)`
admits exactly the next per-task generation and records its `Ready` projection.
The writer lease binds Linux PID, process birth ticks, boot ID and a durable owner
epoch. Every write verifies that lease. A restart requires a new generation claim;
it never adopts a retained PID or grants the old attempt new authority.

`transition(expected_generation, Transition)` requires the current claimed task,
attempt, role, contract and source revision. `Transition.key` is a repository-wide
record key: retrying its exact payload returns the original `EventId`; different
content is refused. Use distinct keys for individual runtime stream records.
Events, per-generation projections and effect records commit in one transaction.
`events()` returns ordered journal records; `projection(task, generation)` returns
the corresponding last event and durable status.

### Journal inspection CLI (generation 1, `inspection-v1`)

```sh
autowork-next --format inspection-v1 status --repo /path/to/repo
```

`capabilities` advertises `contracts.status = 1`. `read_status(common_dir)` uses a
separate SQLite read-only connection, never `StateStore::open`. It validates the
same private-path, local-filesystem and common-directory identity boundaries,
and reads schema 1, metadata, latest per-task generations and the event high-water
mark in one short transaction. The transaction ends before JSON rendering. It
never takes `writer.lock`, advances the owner epoch, claims work, reconciles,
checkpoints, migrates or creates an application directory/database.

The JSON allowlist is `schema_version: 1`, `source: "runtime-journal"`,
`repository` (common-directory device/inode, without its private path),
`journal_state`, `journal_schema`, `event_high_water_mark` and `projections`.
Each projection contains only `task_id`, `attempt_id`, `generation`, `role`,
`contract_hash`, `source_revision`, durable `status` and `event_id`. Raw events,
owner/process records, sessions, evidence references, environment, model text,
credential values and resolved secret paths are not returned.

A missing journal returns `journal_state: "absent"`, null journal schema/high-water
mark and an empty projection array without creating state. It does not mean idle,
stopped or complete. Unsafe paths, incompatible schemas, foreign identity,
corruption and SQLite lock contention fail with nonzero exit and a bounded JSON
stderr object: `status: "unavailable"`, a fixed `code` (`unsafe_source`,
`unsupported_schema`, `foreign_journal`, `corrupt_journal` or `busy`) and a
secret-free `error`. SQLite busy handling waits at most 200 ms per contended
operation; no fallback turns failure into an empty success. Retained state is not
reset or repaired.

Ordinary SQLite read-only WAL coordination can create/change WAL shared-memory
sidecars. Status allows that coordination; it does not use `immutable=1` or claim
byte-identical sidecars. It makes no application-authored or logical journal
writes. Runtime projections do not establish current PID liveness, a live lease,
idle-service state, verified task acceptance or task closure. Git inspection and
journal inspection have independent source identities, not a cross-store atomic
snapshot. Clients must check the advertised API generations.

`cli::task_inspection_is_pinned_and_selection_only`,
`cli::status_reads_without_writer_claim` and
`cli::inspection_refuses_unsafe_sources` exercise these public seams with committed
disposable repositories, a coordinated writer, private payload markers and
SQLite-managed locks. They require no model, service or installed-runner handoff.

Before a child or Git mutation, commit `RecordKind::Intent(Child | Git)` with its
stable `RuntimeEvent.operation_id`. Only then perform the external effect. Record
`Completion` with the same identity, operation and source, plus an evidence
reference. Completion records describe an effect, not canonical task acceptance.
An unresolved effect blocks further intents and the `Complete` status for that
task. An applied operation cannot be replayed under a fresh generation or record key.

After interruption, call `reconcile(Observations)`. The coordinator must inspect
actual Git effects or runtime-owned child receipts, then supply identity- and
source-bound `EffectObservation` evidence. Missing or `Unknown` observations stay
in `reconcile_operation_ids`. `Applied` or `Absent` observations produce resolved
receipts and an `Uncertain` projection for the original generation. They never
mark a task complete or overwrite a newer generation's projection. Verified
absence permits an explicitly requested new intent; the store never retries it.
SQLite cannot make child processes or Git atomic, and this API makes no
exactly-once external-effect claim.

`state_recovery` uses disposable local repositories and an external-effect file
fixture. `recover_without_duplicate_effects` exercises abrupt exits before/after
journal commits and effect completion, transaction rollback, idempotence and
observation-driven recovery. `fence_foreign_owner_and_schema` covers competing
writers, reused-PID birth identities, stale generations, contract/source binding,
common-directory identity, retained backups and newer-schema refusal. These tests
do not qualify a live runner, model, Git integration or task acceptance.

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

The coordinator owns repository scheduling, durable generation admission across
restarts, role instructions, checks, independent review and closure. `CheckOperationSpec` entries remain coordinator data. They do not install
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


Repository IDs preserve `StateStore::repo_id()` exactly across owned requests
and native events. They are opaque strings, bounded to 4096 bytes with no control
characters; runtime admission must carry the same value. They never become file
paths. Task, attempt, model, contract and source identifiers retain their strict
safe-token rules. `runtime_native::native_state_repository_identity` exercises a
real state-store identity through native Octet and rejects mismatched, control,
oversized and empty IDs without dispatch. No journal identity migration occurs.

## Planning re-entry

`Planner::new(runtime, task_service, state_store)` uses an owned fresh-context
native planner with the bundled Plan For Me and RESEARCH-PLAN instructions. The
coordinator first claims its generation in `StateStore`, then supplies a
`PlanningContext` with a read-only `AgentRequest`, current in-flight task IDs,
observed prerequisites and secret values that must be rejected from output.
The request binds the actual snapshot task contract. No model response can
supply admission, an executable identity or check argv.

`propose(snapshot, failure, context)` journals the child intent, consumes its
bounded events, requires a successful reaped native outcome, and reads the final
structured response through Octet's read-only private Session API. The private
transcript is not public evidence. Failure and response diagnostics expose no
model prose. A durable input marker prevents another model call on the same
revision, failed operation, fingerprint and evidence references, including after
restart. New evidence is required to revisit that input; unresolved child effects
still require coordinator reconciliation.

`validate_and_apply` checks the current journal generation, source revision,
contract and exact failure evidence before calling `TaskService`. Existing
acceptance, required checks, exclusions, write scope, resources and verified
prerequisites cannot be weakened. Existing dependencies cannot be removed and
in-flight records cannot change. TaskService separately preserves owner/live
and closure authority and validates the complete schema-1 store. Sources must
refer to the coordinator-supplied evidence. New source discoveries therefore
need new inspected-source evidence before application.

Useful proposals return `PlanOutcome::Pending { edit, snapshot }`. That token is
publication input for `Coordinator::commit_proposal`; it is never converted to
a selectable uncommitted snapshot. Pending edits have not been committed or
integrated. Only an observed matching `SudoRequired` or `CredentialRequired`
prerequisite returns owner help. External waits and scope refusals remain
separate. An exhausted search needs a bounded list of alternatives and inspected
source references; an empty model answer cannot establish quiescence.

```sh
RUSTUP_TOOLCHAIN=1.95.0 cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml --test planning_reentry
```

The two tests use disposable repositories and a loopback response through the
real Octet runtime, plus direct coordinator validation. They prove pending
publication, immutable gates, stale and unsafe response refusal, observed-only
help classification and unchanged-evidence suppression. They do not prove
coordinator publication or integrated task completion; those have separate cycle
checks below. No test here proves live-provider behavior.

## Serialized offline delivery cycle

[`execution.rs`](src/execution.rs) supplies `Coordinator::run_until_quiescent` and
`commit_proposal`. The CLI uses those same services:

```text
autowork-next run --repo /absolute/disposable-repository --models /private/routes.json \
  --worker-model worker --reviewer-model reviewer --planner-model planner --one-task
```

The routes file is a JSON object mapping those explicit references to the
`ModelRoute` fields above. Configure the intended provider before running; the
command does not discover credentials or silently choose a model. Offline tests
use loopback fixtures, not a live provider. Do not run this candidate alongside an
existing writer or against a production repository.

- `--task ID` restricts scope and is repeatable. `--one-task` admits at most one
  task attempt, including a failed attempt, rather than counting only successes.
- `--no-commit` leaves pending edits unselected and dispatches no agents. An empty
  routes object is sufficient for this non-executing mode.
- The caller's `Control::pause/stop`, or a `pause`/`stop` marker in the private
  `autowork-rust` state directory, prevents further dispatch/publication. Native
  worker/reviewer/planner cancellation revokes only the owned child. Planning
  checks the control again before applying edits. Per-task paused/refused journal
  states remain admission gates.
- Selection does not grant authority. Only complete worker-owned runnable tasks
  enter execution; live resources are unsupported in this slice, even when
  authorized elsewhere. `touches` must name exact normalized relative files, not
  directories or globs. Candidate and fresh read-only reviewer worktrees live
  under the canonical checkout's `.worktrees/` and are retained for inspection.

### Checks, review and local publication

#### Preview and publish pending records (generation 1)

Use only a disposable offline repository with no other Python or Rust writer.
The caller must establish exclusive ownership. This command does not import legacy
ownership, establish service liveness or qualify an installed-runner handoff.

```sh
autowork-next --offline --format inspection-v1 tasks commit --dry-run --repo /absolute/disposable-repository
autowork-next --offline --format inspection-v1 tasks commit --repo /absolute/disposable-repository --expect-token TOKEN
```

`capabilities` advertises `contracts.task_publication = 1`. Preview validates one
stable set of working task/goal records against HEAD's existing receipt evidence.
It includes added, changed and deleted records under `tasks/items/` and
`tasks/goals/`, not pending receipt edits or unrelated staged/dirty files.
It holds the task lock and refuses interrupted Python or Rust task transactions
without recovery. A temporary index and object database use repository objects as
read-only alternates. Cleanup leaves repository objects, index and refs unchanged.
Preview does not open `StateStore`, claim a writer epoch, run hooks or call agents.
The task lock file can be created as part of ordinary lock coordination.

Preview JSON contains `state` (`clean` or `pending_commit`), `base_head`, full
`branch` ref, `tree`, `token`, sorted `files` and the exact binary-capable `diff`.
External diff and text conversion are disabled. Diffs over 256 KiB are refused,
not truncated. A clean preview has empty files/diff and a null token. A pending
token binds the original HEAD, branch, tree and all captured record bytes, just
like `PendingSnapshot`. Its temporary tree is not a durable or selectable revision.
Invalid/linked records, detached HEAD, unstable inputs and `--rev` other than
literal `HEAD` refuse without changing record bytes. No working-tree selection
interface is supplied.

Explicit publication needs the matching 64-character lowercase SHA-256 token for
nonempty edits. It re-captures records and uses `Coordinator::commit_proposal`, the
private state writer lock, pause/stop gates, source/branch/record/index checks,
ordinary owned Git hooks and compare-and-swap branch publication. Commit messages
remain fixed. Unrelated staged blobs and working bytes are preserved. No model
routes, credentials, task selection or agent execution are involved. An empty edit
set without a matching retained operation returns `state: clean`, `commit: null`.
A successful result returns `state: committed`, the local `commit`, the reviewed
`token`, `publication: local_only`, and false execution/closure evaluation flags.
It does not supply task acceptance, receipts, goal proof, integration or live authority.

After interruption, supply the **original** token again. Recovery locates only its
retained publication and original snapshot, including when HEAD already advanced.
A verified settled operation returns the same commit without another hook call.
Other unresolved effects, task journals, active writer ownership and conflicting
external bytes refuse safely. Failed or uncertain started hooks are never replayed.
Retain the private journal, owned publication workspace and effect evidence for
reconciliation. This command never invokes general coordinator recovery to clear
an unrelated operation. Do not delete evidence or journals to force a retry.

The three `cli.rs` cases `pending_publication_preview_is_exact`,
`pending_publication_commits_only_reviewed_records` and
`pending_publication_recovers_without_dispatch` exercise this subset with disposable
repositories, staged/dirty sentinels and hooks. Existing task-store/cycle guards
cover shared validation and Git effects. These offline checks do not qualify live
providers, service operation, Python-writer takeover or installed consumption.
The [Python task-store contract](../../task-store.md#writing-and-autowork-tasks)
is unchanged. Native task authoring and broader command parity remain unsupported.

#### Delivery checks and review

The frozen `CheckRegistry` admits only `git-diff-check` and, with explicit
`--fixture-checks`/`enable_fixture_checks`, the same built binary's `fixture-pass`
and `fixture-fail` operations for disposable repositories. A spec binds the
absolute executable/hash, implementation ID, accepted base revision, fixed argv,
workspace, complete sanitized environment, timeout, output cap and receipt ID.
Task/planner strings name operation IDs only. Unknown operations, shell text and
executable/source/specification drift are refused. Git content filters are not
admitted in this slice; attribute inspection rejects them before checkout/staging
or check execution, and Git fsmonitor execution is disabled. Ordinary publication
hooks remain explicit owned Git effects, not model-callable check operations.
Unsupported mandatory checks remain unmet; fixture success is never substituted
for an arbitrary build/test
command or live qualification.

The coordinator captures an exact candidate tree, runs every required operation,
and supplies the independent reviewer with bound receipts and a bounded exact
base/candidate diff, including deletions. A native successful outcome alone is
not approval: the review response must explicitly approve the same candidate,
tree and contract. Integration is serialized, has that exact tree and a two-parent
commit, and refuses target drift or overlapping user changes. Only then can a
coordinator-authored task closure and receipt be locally committed. Candidate and
integration commits use literal Git plumbing; task publication/closure retains
ordinary commit hooks in a detached workspace with a private index. A hook-changed
tree/parent/message is rejected **before** canonical branch publication. Canonical
publication uses compare-and-swap; unrelated staged blobs and working bytes stay.
Nothing is pushed or deployed.

### Restart and quiescence

Private state retains planner publication input before apply, exact pending
snapshots, Git intent/completion records, check/review receipts, native request
identities and owned Git invocation state. Restart reconciles task undo journals,
matching reaped native outcomes and actual Git effects before selection. A known
successful worker can resume its retained candidate without another worker call;
its original frozen registry must still match. A started hook invocation is never
automatically replayed after a failure or uncertain interruption. Keep the owned
workspaces, journal and evidence; do not delete intent files to force a retry.
Unmatched/live/uncertain effects stay open rather than becoming acceptance.
Settled delivery records no longer require completed task records to survive
later pruning or reopening.

Planner application is not selection. Only the exact validated pending tree can
become a tasks-only local commit bound to its captured HEAD/branch. Recovery
compares original and proposed bytes, refusing intervening task edits; unrelated
pending task edits report `pending_edits`, not a selectable ephemeral tree.
Failed checks/review retain required acceptance and send bounded coordinator
failure data to planning. Unchanged planning evidence suppresses another call.

The JSON summary separates completed IDs, pending IDs, evidence references and
`completed`, `pending`, `pending_edits`, `task_limit`, `paused`, `stopped`,
`no_commit`, `uncertain`, `waiting_external`, `waiting_sudo`,
`waiting_credential` or `refused_scope`. Only coordinator-observed matching sudo
or credential prerequisites can produce owner help. The CLI supplies no such
observations; model prose alone cannot request credentials or sudo.

`autonomous_cycle.rs` contains three composite offline acceptance cases:
`finish_multiple_tasks_and_replan`, `recover_git_effects_without_false_closure`
and `respect_limits_and_explain_quiescence`. They use native Octet fixtures,
fixed authored checks and disposable repositories to cover multi-task delivery,
exact planner publication, recovery boundaries, hook failures, evidence binding,
authority/limits and unrelated staged/dirty preservation. Their ports use
`AUTOWORK_PORT_BASE+20` through `+99` when configured, preferring `+20` through
`+32` and skipping occupied/TIME_WAIT ports without touching other processes.
These are not general shell,
live-model, device, service, migration or replacement qualification.
