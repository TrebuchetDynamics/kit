# Rust Autowork with Octet

Status: Accepted product direction, 2026-11-07. Technical choices below are planner calls under delegated decision authority. Offline first-batch source and the mechanical crate relocation have landed. This does not qualify the complete replacement, installed handoff or live execution.

## Accepted direction

The owner requests a redesigned Rust Autowork with Octet instead of Pi as its agent engine. It may improve the design from the start rather than reproduce the Python internals. The owner delegates ordinary decisions to the planning skill, which can run again whenever execution needs a new decision. Sudo or missing special credentials are the routine reasons to request owner help.

Autowork selects work, implements, checks, repairs, reviews and continues automatically. A failing test, design choice, blocked task or empty queue is not a reason to ask the owner to pick work. Preserve safety restrictions, explicit pauses, existing live authority and honest acceptance evidence. These are boundaries, not decisions the planner may waive. A genuinely impossible or unsafe action remains unmet; the system must not invent progress to satisfy the autonomy goal.

This direction supersedes the Python-retention and conditional Go choice in [the earlier language strategy](2026-11-05-language-strategy.md). Its measurements, completed tasks and receipts remain historical evidence. Do not reinterpret this request as authority to interrupt an old live claim, erase state, push, deploy, spend money or perform live device operations.

## Outcomes and non-goals

- One Rust application owns task selection, coordination, planning re-entry, verification, Git integration and durable recovery.
- Octet owns inference, the agent/tool loop, model sessions and run control. Pi and its Python RPC SDK are absent from the new executable's runtime dependency chain.
- Manual `run` and future background operation use the same coordinator. Manual work continues through eligible tasks, not one task followed by a menu.
- The normal owner-help channel has structured `sudo_required` and `credential_required` reasons with actionable, secret-free evidence. Routine implementation and design decisions go to planning.
- Preserve task IDs, accepted requirements, completed evidence, unrelated dirty files, user pauses and live writers. An Octet result is not task acceptance.
- Native terminal UI, service management, fleet/Paseo integration, installer cutover and retirement of Python are part of the final redesign, not delivered by the first batch.

No upstream Octet patches, new product strategy, implicit privilege escalation, credentials in Git, mandatory Pi bridge, blind state conversion, or claim of OS sandboxing. Portable skill documents and the TypeScript Paseo client do not become Rust merely because the execution application does.

## Decisions and evidence

| Choice | Planner decision and reason | Rejected alternative |
| --- | --- | --- |
| Engine | Link public `octet-agent` and `octet-ai` from the immutable Octet v0.10.0 source revision `4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee`. Use `Agent`, `AgentConfig`, `Session`, native tools, events and `RunControl`; preserve the license. | A new inference/tool loop, Pi RPC emulation, or importing private product modules. |
| Process boundary | One `autowork-next` binary initially; its internal owned-agent mode runs each worker/reviewer/planner in a dedicated child process with fresh context. The coordinator owns its PID/birth identity, generation and cleanup. | Embedding all agents in the coordinator's address space, or adopting arbitrary existing processes. |
| Why not octet-host | Native-host protocol 1 is always Controlled, denies headless mutation approvals and has no in-band abort. It cannot implement the coding-worker contract as shipped. | Treating `allow_file_mutation=true` as approval, inventing an unsafe protocol flag, or silently downgrading policy. |
| Safety | Keep Octet's Controlled effect broker. The application answers an exact tool confirmation only under the already accepted task's authority and current generation. Review/planning roles lack mutation and process tools. Workspace checks and Git checks remain independent. | Turning on UnsafeHost to avoid decisions, approving every confirmation, or claiming a shell is confined by a worktree. |
| Credentials | Use explicit configured provider/model and credential references; resolve secrets at the owned agent boundary, never in task records or event logs. First delivery supports an explicitly configured OpenAI-compatible route through Octet; other provider/auth flows are later adapters, not claimed parity. | Copying Pi auth/session homes, automatic credential imports, or a new OAuth implementation. |
| Canonical intent | Retain current schema-1 TOML-frontmatter task and goal files under `tasks/`. Port their behavior, not Python implementation. Read at a pinned Git revision; compare record revisions on writes. | A second queue in SQLite or an unreviewed on-disk task migration. |
| Runtime state | A separate private per-repository SQLite journal plus transactional state projection, using rusqlite with bundled SQLite. State is not a task store. Bind repository common-dir identity, revision, contract hash, role and generation. | A collection of independently written status JSON files or treating cache projections as authority. |
| Git | Use literal Git argv with sanitized Git environment. Check/integrate captured candidate trees, preserve unrelated staged/dirty files, and retain interrupted candidates. No automatic push/deploy without a scoped existing grant. | Parsing shell-composed Git output or committing mutable task bytes after review. |
| Platform and rollout | Linux first, matching existing supervision/service scope. Build as `autowork-next` beside the running Python system. Explicit validated handoff at idle, with the old source/state retained. | In-place replacement of a live runner, promised cross-platform qualification, or a permanent second owner of one repository. |
| Source layout | One crate, internal modules `task_store`, `state`, `runtime`, `planning`, `execution`, and one CLI. The completed crate lives in `pi-autowork/rust/autowork/` under the accepted [one-product-root contract](pi-autowork-component-layout.md#one-product-root-contract). Keep its Cargo.lock bytes and immutable upstream pin unchanged during relocation; the original first-batch contracts and receipts remain bound to their original `rust/autowork/` sources. | A framework, microservices, a crate per state, or copying the Octet repository into Kit. |

Dependency families: Rust toolchain 1.95 initially (available on this host), Tokio, serde/serde_json, clap, toml/toml_edit, fs2 and rusqlite. Reuse versions compatible with the pinned Octet workspace, including rusqlite 0.40.2; the foundation task resolves and records the lock with locked build checks. Upstream declares Rust 1.88, but this application does not promise that floor until qualified. Toolchain/dependency setup is an implementation prerequisite, not something run by this planning pass.

## Coordinator and planning contract

The Rust coordinator is the only task/state writer. Agents propose results; they cannot mark themselves done or mutate the queue directly. Planning is a role in the same execution cycle, not a second competing coordinator.

1. Reconcile owned attempts and partial Git effects before selecting from the pinned task snapshot. Preserve task-specific pauses, live claims and unsafe uncertainty.
2. Select a dependency-ready accepted task. Apply resource, ownership and authority admission separately from selection. A planning decision never supplies live authorization or changes another active contract.
3. Run the owned Octet worker with a frozen contract and a dedicated workspace. Read progress from its native event stream. A dropped stream, timeout or crash is not success.
4. Run declared checks on the actual candidate and independent review under the repository's policy. A failed check routes to repair or planning; it does not reduce acceptance or disable the check.
5. Integrate serially with fresh target checks and evidence-bound closure. Keep local commit, integration, push, installation and live qualification separate.
6. On missing design detail, repeated ineffective repair, changed requirements evidence, or no eligible task, invoke the planning role. It reads current evidence and produces a proposal bound to the task revision and failed-operation fingerprint.
7. Validate and apply the proposal through the coordinator's task service. Application produces pending edits, not a selectable durable revision. Under existing local-commit authority, capture and validate their exact tree in a private index, journal the publication intent, and make a tasks-only local commit against the captured HEAD/branch. Reconcile interruptions against the retained tree/parent before retry. Only then select from that committed revision. Preserve unrelated staged/dirty content and ordinary hooks. If an explicit no-commit limit applies, retain pending edits and report that limit rather than select an ephemeral tree or invent success. This is local durability, never remote publication. Classify `repair_current`, `split_dependency`, `choose_independent`, `discover_offline`, `wait_external`, `need_sudo`, `need_credential`, or `refused_scope`. Stale proposals are discarded and refreshed, never applied to a different attempt.
8. Continue useful authorized work automatically. Transient provider/network failures use bounded per-operation backoff and configured alternate providers without new credentials or new billing authority. Preserve uncertain effects and reconcile before retry; no automatic replay of an unresolved mutation.

`need_sudo` and `need_credential` require observed prerequisite evidence, not merely model prose. The owner channel gives the exact action or credential reference needed and how to resume; it never requests passwords/tokens in chat or invokes sudo automatically.

A task with an unavailable rig or ungranted live scope stays pending while planning finds independent offline work. A transient external wait does not become an owner decision. If no safe useful action remains after a bounded source-backed search, report a quiescent/external-wait state and resume on new evidence or an eligible task; do not relabel unmet work done, repeatedly ask the same question, or spin on unchanged inputs. A user stop, pause or hard safety refusal always wins. Scope-wide inability remains visible even when it is not one of the routine owner-help categories.

### Role and effect admission

Foundation defines a frozen `ExecutionAdmission` envelope issued by the coordinator: repository/workspace canonical identity and device/inode, task/attempt/generation/contract hash, role, allowed normalized write paths, denied coordinator/Git paths, and admitted check-operation IDs. It travels on the owned child input separately from the model prompt; proposals cannot supply or widen its grants. Worker mutations always deny `tasks/`, `BLOCKERS.md`, `TODO.archive.md`, `CHANGELOG.md`, `.git` files/directories and the resolved common Git/runtime state roots, including aliases/symlinks. Task-scoped ordinary source paths require membership in the envelope's allowed write set and native workspace path checks.

Use Octet's public `ToolCallHook::transform_tool_call` for typed name/argument validation before effect admission, and recheck current generation before granting a broker confirmation. Only the verified CoreTools edit/write path in that owned agent may receive a grant; deny unknown confirmation/input requests. Do not derive authority by parsing `ToolConfirmation.prompt` or other model-facing text. Keep confirmations process-local. For worker runs, use the existing broker's ephemeral confirmations and host-owned task identity, not approval inferred from model output. Approve eligible workspace edits only for the current accepted task. Bash confirmation is an execution decision with OS-user authority, not proof of workspace confinement; arbitrary shell text must not be declared read-only or safe from a regex. The first worker seam exposes only coordinator-authored fixed argv check operations and workspace edit tools; general model-authored shell commands and executable extensions stay disabled until a separately qualified execution boundary exists. That boundary is a later goal outcome, not a reason to use UnsafeHost now. Missing build dependencies can be proposed by planning and installed only under existing host authority, without sudo or secret changes.

The first-slice check registry is coordinator-authored, frozen before dispatch and separate from string-valued `checks` notes. Each `CheckOperationSpec` contains operation ID, absolute executable identity/hash, accepted implementation/source revision, argv vector, cwd, sanitized environment allowlist, timeout/output limits and receipt identity. The initial executable operations are fixed Git checks and the same built binary's fixture-check mode for disposable test repositories. The model/planner may name an existing operation ID but cannot submit executable paths, shell text or new argv. Changed executable/source identities require new trusted admission; unsupported task checks remain unmet and route to planning. Do not silently parse a task check string into execution authority. The later general-check boundary must explicitly authorize running candidate-controlled scripts with the user's OS authority; fixed argv alone is not containment.

For planner/reviewer runs, register read-only tools and no executable extensions or shell/process tools. The coordinator runs allowed inspection checks itself and supplies their receipts. Load the relevant existing portable planning/review instructions explicitly; no imported user-global extensions or a second autonomous scheduler.

## Durable state and recovery

Proposed durable states: `ready`, `planning`, `executing`, `checking`, `reviewing`, `integrating`, `complete`, `waiting_external`, `waiting_sudo`, `waiting_credential`, `paused`, `uncertain`, `refused`.

Store transitions and projections in the same SQLite transaction. Use immediate write transactions, a per-repository writer lock, local-filesystem WAL, foreign keys and full sync. Keep monotonic event IDs and unique operation/generation keys. On restart, inspect owned process identity and actual Git effects before replaying a transition. SQLite cannot make Git or a subprocess atomic: retain intent and completion receipts around each external effect and reconcile the crash window.

Use versioned schemas and transactional migrations that retain a backup. A newer incompatible database is read-only/refused, never reset. Do not share a WAL database over network filesystems. Original Python state is an import source only after its owner has stopped at a verified checkpoint. Never run Python and Rust writers against the same task/workspace concurrently.

Runtime event schema 1 carries `repo_id`, `operation_id`, `task_id`, `attempt_id`, `generation`, `contract_hash`, `source_revision`, `role`, `event`, `status`, `evidence_ref` and timestamp. No credential values or raw environment dumps. Native Octet sessions remain separate from the coordinator journal. Human status derives from this one state owner; clients cannot independently invent blockers or closure.

## First implementation batch

This is the original first-batch contract map, not a completion ledger. Its checks were proposed and UNRUN at planning handoff. Next-round planning must reconcile the landed source with retained records and immutable source-bound evidence below. The batch targets one offline end-to-end autonomous path before fleet/UI/cutover features, not the complete replacement.

<!-- task-map:start -->
| Task | Outcome | Depends on |
| --- | --- | --- |
| TOOLSET-472-48c78e95 | Rust foundation and immutable native-Octet dependency seam | None |
| TOOLSET-473-afef55de | Owned native agents, role controls and cancellation | TOOLSET-472-48c78e95 |
| TOOLSET-474-6b517117 | Pinned task-store reads and safe revision-bound writes | TOOLSET-472-48c78e95 |
| TOOLSET-475-66aacc5f | Durable runtime journal and crash reconciliation | TOOLSET-472-48c78e95 |
| TOOLSET-476-fb27960d | Automatic planning re-entry and useful offline selection | TOOLSET-473-afef55de, TOOLSET-474-6b517117, TOOLSET-475-66aacc5f |
| TOOLSET-477-e5de6356 | Multi-task local cycle with checks/review/Git/recovery | TOOLSET-473-afef55de, TOOLSET-474-6b517117, TOOLSET-475-66aacc5f, TOOLSET-476-fb27960d |
| TOOLSET-478-9a8d7ece | Evidence-driven next batch; Plan round 1 of 10 | All six building tasks |
<!-- task-map:end -->

Public Rust seams selected for this batch:

- `TaskStore::read_at(repo, revision) -> Snapshot`; `Snapshot::select(scope) -> Selection`; `TaskService::apply(expected_revision, proposal) -> PendingEdit`; `TaskService::capture_pending() -> PendingSnapshot { base_head, branch, tree, captured_bytes, token }`. Applying records alone never advances committed selection. The coordinator task implements `commit_proposal(PendingSnapshot) -> CommittedRevision` with journaled recovery. Preserve the current schema and evidence rules.
- `StateStore::transition(expected_generation, transition) -> EventId`; `StateStore::reconcile(observations) -> RecoveryActions`. Do not let observations close a task.
- `AgentRequest { repo_id, task_id, attempt_id, generation, role, workspace, model_ref, contract_hash, prompt, admission: ExecutionAdmission }`; `Runtime::run(request) -> stream<RuntimeEvent>` and `Runtime::cancel(run_identity)`. Foundation wires `internal-agent` to a runtime stub with a defined `serve_owned_agent(request)` signature; runtime replaces that implementation. A child consumes native Octet `AgentEvent` and confirmation channels locally and projects versioned bounded JSON `RuntimeEvent` records (accepted/progress/usage/outcome) to the parent. Do not try to serialize native reply channels across processes. Production uses Octet; deterministic tests use a local fixture route, not fabricated production success.
- `Planner::propose(snapshot, failure_evidence) -> PlanProposal { expected_revision, failed_operation, disposition, record_changes, reason, sources }`. The coordinator validates scope, identity and authority before applying it.
- `Coordinator::run_until_quiescent(scope) -> RunSummary`. It consumes the same task/state/runtime services as future daemon mode. Completion needs check and review receipts bound to the integrated source.

Shared registry ownership: foundation declares module seams and bootstrap CLI routing; the coordinator task alone wires the new `run` command into the working loop. Later module tasks may implement existing module files but do not create independent dispatch registries. True dependencies are recorded in tasks; no fictitious dependencies from tests/docs overlap.

## Remaining goal outcomes and next rounds

These outcomes remain part of the goal; later rounds turn them into concrete implementation batches from measured first-batch evidence:

1. General-purpose build/test shell execution with a qualified authority boundary, native provider/auth adapters, steering/continuation and real cancellation/resource limits. The restricted first seam is not full coding capability.
2. Remaining task/goal mutations, user-facing pending-commit command parity, history/evidence presentation, Git recovery and closure compatibility. The minimum exact-snapshot local commit needed to publish planner edits is already required in the first coordinator task. Preserve the protections demonstrated by current task transaction, history, snapshot and landing tests.
3. Background service management and multi-repository scheduling using the same core, with an explicit graceful handoff from Python and no PID-only adoption. Migration must preserve the unresolved language-measurement goal and its missing-input boundaries without treating the Rust direction as qualification; reconcile current ownership before live handoff.
4. A Rust terminal interface driven by the shared status projection; responsive reads, preserved input drafts, useful task titles and clear actionable credential/sudo states. Do not port current UI defects for parity.
5. A versioned JSON CLI/status adapter for Paseo and installer support for the Rust binary. Keep the TypeScript client; gate incompatible API generations rather than silently reading stale schemas.
6. Versioned migration/import previews for task repositories, configuration and old runtime receipts. Preserve original bytes, paused jobs, active/unmerged worktrees and secrets. Source-backed offline fixtures precede separately authorized disposable live qualification.
7. Release/install rollback and Python/Pi runtime retirement only after the accepted outcomes and migration checks pass. No promise of native model execution, live delivery or speed gain from source checks alone.

The closing planning task carries `Plan round: 1 of 10` and must read the six building tasks' actual reports, the accepted crate-relocation proof from the [one-product-root batch](pi-autowork-component-layout.md#one-product-root-contract), and remaining goal proof. Retained records and the immutable Git inputs below preserve those requirements when satisfied ordinary dependency edges are pruned. Manual closure is not verified qualification. Preserve the original six building contracts, native acceptance and live-denied gates. Round two uses the landed `pi-autowork/rust/autowork/` owner. Save at most eight tasks per round and no speculative code tasks. Existing rolling-planning defaults cap one automatic planning chain at ten rounds; reaching that bound is not goal completion. The general runtime's future replanning follows the accepted authority and real evidence rather than turning the bound into a safety bypass.

## Verification and builder handoff

First selection-ready outcome: the Rust foundation. Subsequent runtime, store and journal implementations can proceed independently after foundation. Planning depends on their real APIs; the coordinator depends on all of them. Run only focused task checks plus repository-required landing/main gates. Include exact manifest/lock paths in the foundation's protected `touches`.

Pre-mortem: (1) a stale planner changes a different attempt: bind revision, contract and generation; (2) an agent or Git crash is mistaken for success: reconcile retained intent/effects and source-bound checks; (3) rewrite cutover discards old state or dual-starts a writer: require preview, preserved backup and exclusive handoff. Tests must prove each affected seam.

Builder review found three fixable gaps: durable task-proposal publication, trusted native edit authority, and fixed-argv check admission. Their resolutions are specified above and assigned to foundation/runtime/store/planning/coordinator contracts; they are not deferred owner questions. Native source/build compatibility and new behavior checks were unrun at that planning handoff; current qualification must come from source-bound results, not this historical builder review. A fresh read-only builder inspected the saved task contracts and this document before handoff; its first run timed out, then resumed to return the concrete findings. A separate fresh read-only follow-up confirmed all three gaps closed at contract level; no remaining blocker was found within that follow-up scope. This is not implementation or runtime qualification. Missing external live evidence remains explicit, not an offline test substitute. This plan does not start the current runner or the Rust candidate. Branch-local saved records do not change the canonical consumer until integrated through its existing policy.

## Sources

- Owner conversation, 2026-11-06/07: Rust project, Octet engine, better design from the start, delegated planning decisions, routine sudo/credential owner help.
- [Current Autowork components](../project.md#current-components), [task store](../../pi-autowork/task-store.md), and [old language strategy](2026-11-05-language-strategy.md).
- Current Python source: `pi-autowork/src/pi_autowork/` owns `coordinator.py`, `pi_runtime.py`, `pi_rpc.py`, `pi_process.py`, `planning.py`, `planning_authority.py`, `landing.py`, `task_commands.py`, and `engine/task_store.py`.
- Required next-round historical inputs remain reachable at `d521a3ff5d1100526a4a590e6a34d9d62afef1c2`: use `git show d521a3ff5d1100526a4a590e6a34d9d62afef1c2:tasks/items/TOOLSET-477-e5de6356.md` and `git show d521a3ff5d1100526a4a590e6a34d9d62afef1c2:tasks/evidence/TOOLSET-477-e5de6356.toml` for the offline cycle contract and receipt. Use `git show d521a3ff5d1100526a4a590e6a34d9d62afef1c2:tasks/items/TOOLSET-481-33040cb9.md` and `git show d521a3ff5d1100526a4a590e6a34d9d62afef1c2:tasks/evidence/TOOLSET-481-33040cb9.toml` for the mechanical relocation contract and receipt. These inputs retain their original source bindings, not fresh checks or live qualification.
- [Octet Rust agent API at the pinned source](https://github.com/skaft-software/octet/blob/4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee/crates/octet-agent/src/lib.rs): public embedding, native sessions and cancellation.
- [Octet native-host limits](https://github.com/skaft-software/octet/blob/4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee/docs/sdk.md#headless-safety-and-cancellation): no unattended writable native host and no in-band abort.
- [Octet effect broker](https://github.com/skaft-software/octet/blob/4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee/crates/octet-agent/src/effect.rs) and [ephemeral confirmation API](https://github.com/skaft-software/octet/blob/4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee/crates/octet-agent/src/tool.rs).
- [rusqlite transaction behavior](https://docs.rs/rusqlite/0.40.2/rusqlite/enum.TransactionBehavior.html); upstream Octet's 0.10.0 Cargo.lock also uses rusqlite 0.40.2. No database or Rust compilation was performed during planning.

## Next bounded batch: read surfaces and task-command parity

Plan round 2 of 10. The first batch supplies the pinned crate/API and CLI
(`TOOLSET-472`), controlled native roles (`473`), committed task snapshots and
pending publication (`474`), journal recovery (`475`), planner re-entry (`476`)
and serialized offline cycles (`477`). Source owners are now
`pi-autowork/rust/autowork/src/{runtime,task_store,state,planning,execution}.rs`.
The retained receipts for 472–475 and immutable 477/481 inputs in Sources record
passing reviewed candidates. The 476 closure is manual at `8db90299`; its
`planning_reentry.rs` cases are implementation evidence, not independently
verified or live qualification. These historical inputs are not fresh checks.

Choose read-only versioned status and bounded offline task-command parity next.
Both have concrete existing TaskStore/TaskService and StateStore interfaces;
neither needs a new shell confinement design or production provider credentials.
Status consumes committed snapshots and persisted journal observations, reports
schema/application versions and uncertainty, and performs no reconciliation
writes. Task mutations use the existing pending-edit/publication transaction,
preserve unknown notes and gates, and reject stale revisions. Protected Owner
decision writes and `place --decision` remain explicitly refused by the planner
authority seam; trusted human decision-command parity remains deferred. Keep command output
explicit about pending edits versus committed/selectable state. A closing planner
compares their actual results before selecting another batch.

General model-authored shell execution remains disabled. Native production
provider/auth, steering, cancellation/resource qualification, service management,
Rust TUI, Paseo wiring, installation, legacy migration/import and Python/Pi
retirement remain open goal outcomes. JSON status is an offline seam, not Paseo
compatibility or installed-service acceptance. No old LANG-003 task is present in
the current committed queue; preserve its historical contract and resolve actual
ownership before any migration/cutover work. This round changes no old owner,
service, source pin, model grants or runtime state.

The saved follow-up task records own exact write scopes, proposed offline checks
and dependencies. New behavior checks remain proposed until implementation;
planning never qualifies native execution, migration or live delivery.
