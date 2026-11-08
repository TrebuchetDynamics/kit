# Fleet TUI responsiveness and task freshness

## Scope and boundaries

The accepted objective is responsive local input and accurate revision-bound task
counts. A blocked local reader, stale/mismatched store observation and missing
canonical delivery are separate conditions, not one SSH-latency diagnosis. Read
current source/ownership before implementation; do not restore old baselines or
change active contracts. Completed diagnosis and task timelines live in Git history.

Preserve bounded service/Git/filesystem/journal/model readers, source provenance,
failed-read timestamps, sanitized Git environments and explicit unknown/error states.
Local deterministic fixtures do not qualify SSH transport or an installed fleet.

## Chosen contracts

Planner calls: three cohesive slices: producer provenance → one committed task snapshot → nonblocking UI consumption. No schema migration, second queue, new permission gate, lower verification bar or unbounded polling/thread creation. Source-reading and fixture regressions are future task-owned inputs, not absent external prerequisites.

### Producer provenance

Status: Accepted

Add diagnostic observation metadata to engine status and health only; task/attempt/receipt schemas and authority are unchanged. At engine status entry capture one immutable TaskStore/revision and use it for all task membership/current-record reads in that answer, not a final HEAD lookup after rendering. Expose `task_source = {workspace, repository_identity, revision, observed_at}`; each task row carries its current source contract_hash and, where a live attempt exists, its admitted_contract_hash separately. Never substitute today's hash for the attempt's hash. Missing legacy metadata stays unknown, not inferred fresh.

Use the existing sanitized TaskStore Git path for revision discovery in task_queue.commit, preserving unborn/unknown revision handling while distinguishing real read failure. No process-global environment mutation. A hostile inherited GIT_DIR/WORK_TREE/INDEX_FILE or replace ref must not redirect the selected repository.

Coordinator status cache is keyed by resolved workspace and source revision as well as its existing lifetime; engine mutation invalidation remains. Cached data retains its original observed_at. Health carries that observation through successful/cached writes and retains its age on failed reads; write time is separate. Preserve existing failed-read escalation and status/lock lifecycle. No live process restart is required or implied by source qualification.

Produces: the additive task_source/row identity envelope and truthful observation time for the next slice. Planned checks: `python3 scripts/check.py pi-autowork/engine/test_parallel_status.py pi-autowork/engine/test_task_queue.py pi-autowork/tests/test_health.py pi-autowork/tests/test_status_provenance.py`. New test_status_provenance.py owns coordinator cache/revision and health propagation cases; existing runtime assertions remain.

### One committed task snapshot

Status: Accepted

Add `pi_autowork/task_snapshot.py` with `capture(repo, *, engine_observation, generation) -> TaskSnapshot`. Its immutable result includes selected repository identity/worktree, one resolved committed revision/TaskStore, generation and capture times, rows, counts, goals/questions, independently captured pending paths, engine source identity and explicit freshness/errors. Pending/working detail and runtime observations keep their own timestamps/provenance; a generation is not a claim that every source was observed at one physical instant.

Inventory membership is **exactly current committed open task IDs**, with each present once. Join execution evidence only for the same repository identity and compatible contract hash; different session/canonical revisions are disclosed, and hash-compatible observations may still describe the same task. Incompatible/legacy-unknown/orphan slot data remains visible as separate execution annotations, never extra inventory. Decisions come from current Needs-decision records; stopped dependency waits remain Blocker, overlap/transient waits remain Waiting, Mergeable still requires compatible evidence, and ordinary ready work is Waiting with explicit “ready; awaiting dispatch”, not omitted from Total. Preserve existing five-bucket sum and queue/goal order; questions without matching inventory are annotations.

Derive fleet counts, task rows, Waiting/Blocker detail parts and the visible task list from this same result. Reuse the revision-keyed TaskStore cache, not a whole live snapshot keyed only by HEAD. A newly committed task appears at the next completed capture even for stopped/no-health runners; closes/section changes remove/reclassify it. Staged/unstaged/untracked records remain pending, not committed membership. Do not scan or union arbitrary planning branches into counts.

Valid empty is six zeros. Unavailable/invalid/missing data is not empty: `task_counts` returns no valid vector when no verified snapshot/last-good exists, and consumers render unknown/unavailable; if last-good exists, show it with its original revision/age and stale/error state. Read failures never mean clean pending paths. Extend current synthetic count fixtures with explicit inventory inputs rather than deleting bucket/mergeability assertions. Preserve service lifecycle labels independently of task-data freshness.

`fleet_view.collect` attaches/uses these snapshots. Define `collect_for_tui(..., generation, cached_preparation=None) -> FleetSnapshot` carrying runners, per-repository TaskSnapshots, capture time and explicit acquisition errors; existing CLI collection keeps its contract. Service/env/store/pending errors must survive the adapter instead of being swallowed as empty values. The TUI read path separates current cheap state/inventory capture from expensive preparation audit. Bound the formerly unbounded service-enabled query with the existing ten-second discovery bound in this reader-owning slice. CLI/full readiness retains existing semantics. TUI preparation diagnostics may reuse a labelled result for at most 30 seconds (planner default), invalidated by relevant observed repo/environment changes, action/preparation return or explicit refresh; mark diagnostics age separately. They never supply inventory counts or authorize Start. Confirmed Start always forces a fresh readiness read. No cache of pending/status/environment/readiness solely by HEAD.

This slice owns synchronous TUI rendering adapters for the new snapshot/unknown/freshness fields; the next slice moves their readers off-loop. Legacy health metadata remains displayable as unknown/stale with canonical inventory available. Planned checks: `python3 scripts/check.py pi-autowork/tests/test_task_snapshot.py pi-autowork/tests/test_fleet_view.py pi-autowork/tests/test_health.py`; existing rendered pilot and selected affected tests must run, with skips disclosed.

### Nonblocking read coordination

Status: Accepted

Add `pi_autowork/tui_reads.py` with a read-only coordinator: `request(kind, identity, epoch, loader) -> token`, subscribing only active app/screen resources. Token contains owner lifetime, kind/resource identity, request generation and invalidation epoch. Workers receive plain immutable inputs; the UI thread alone publishes results/queries widgets. Use a bounded executor (four concurrent reads, planner default), at most one physically active read plus one replaceable pending request per resource, and retire queued subscriptions when the owner/selection changes. No recurring thread per timer.

Fleet/discovery/task snapshots, journal/log/action detail, goals, readiness/directory labels, model catalog and code-stamp reads use this boundary. Separate log/catalog/readiness keys so one blocked reader does not serialize the entire UI. Resize/filter/wrap/selection renders cached snapshots immediately and schedules only missing reads; it must not recollect the fleet synchronously. File discovery stays on DirectoryTree's existing loader where applicable; no I/O from render_label. Consume the preceding slice's bounded service readers and preserve other established timeout/error semantics.

Publish each repo snapshot atomically for the current owner/identity/epoch, applying only completion sequences newer than the last applied result. Repeated timer polls of the same identity/epoch coalesce without invalidating the active read merely because another request is pending: otherwise a collector slower than the timer would never publish. Semantic invalidation/selection changes reject the old result; a newer already-published completion cannot be overwritten. Resolve runner/repository/task by identity, never a stale table index. Keep current selection, filter, scroll/follow state; a failed read releases busy state and retains visibly stale last-good data. An empty successful discovery differs from a failed discovery. Model results stay service/provider-context-specific; preserve default fresh discovery per opening and Portal invalidation, not a fleet-global catalog.

Unmount cancels queued work/subscriptions. Cancelling an async wrapper does not stop a running thread: keep its resource slot occupied until physical completion, discard its late result, and do not admit an overlapping replacement. Invalidate epochs after action/preparation/planning return and interactive resume; completion callbacks request new reads instead of doing synchronous recollection. Preserve fresh pre-Start readiness in a worker, duplicate-start prevention, confirmation/view-only/authorization and existing interactive suspension. Mutation commands are not cancellable disposable reads. Do not restore removed fleet shortcuts.

Proposed `test_tui_reads.py` and existing tui_pilot use threading.Event entered/released/completed handshakes: while each provider is blocked, acknowledge navigation/filter/key/close before release; prove coalescing, no overlapping cancelled-thread replacement, stale-generation rejection, close/reopen and action invalidation, error recovery and selection stability. Use a watchdog only to terminate deadlocks, not invented millisecond SSH performance claims. Planned checks: `python3 scripts/check.py pi-autowork/tests/test_tui_reads.py pi-autowork/tests/test_fleet_view.py pi-autowork/tests/test_tui_mouse.py`.

## Verification and qualification

Producer metadata, committed snapshots and nonblocking readers have real interface
dependencies. Shared paths alone create no product prerequisite. Use actual owners
and current source; preserve independent review, affected checks and main's gate.
The pinned Textual pilot must actually run for rendered evidence: a skipped dependency
is NOT_CHECKED, not a visual pass.

Completion requires deterministic responsiveness under stalled readers and accurate
revision-bound counts/errors. It does not establish universal low SSH latency.
Actual SSH terminal/transport qualification remains separate and unrun here. Source
integration, selection, admission and live acceptance remain different observations;
no installation, service change or dispatch follows from this document.

## Immediate task deletion feedback

Status: Accepted

Owner request: “deleting task must refresh tui inmediately”, through standalone Plan For Me. Save this bounded correction under RELIABILITY-2026-10; do not implement it, delete a real task, dispatch workers, install anything or change schedules in this occurrence.

### Diagnosis and chosen approach

Task deletion changes the working-tree record while canonical task snapshots remain committed-HEAD observations. Successful TUI mutation feedback must bridge that distinction without inventing a new committed revision or execution authority.

**Planner's calls:** handle TUI-initiated deletions as explicit, app-owned pending display mutations. “Immediately” means the next UI-loop update after the successful command result is posted, without a timer tick, completed fleet read or runner commit. Preserve the immutable committed snapshot and admission/eligibility authority. Show the display adjustment as “deletion pending commit”, not as a new committed revision. This is not a working-tree replacement for TaskStore.

- Carry explicit delete identity/result through the action completion path: captured runner, resolved workspace/repository identity and task ID, never the currently selected row, a mutable runner name lookup or parsed notification text. Invoke the existing delete CLI against the captured repository path, not a runner-name binding that could be retargeted between confirmation and execution. A zero return code with warnings is still success under the existing CLI contract. Failure, exception, denied access and cancellation of confirmation do not remove anything.
- Apply an idempotent success-only display overlay before starting expensive refresh. Derive visible task rows, per-view counts and fleet inventory counters from the same effective projection; remove a deleted closed-history record without decrementing open totals. Keep filters/scroll and choose the nearest surviving row, or an explicit empty state. Refresh the selected detail and menus; a deleted detail must become unavailable or return safely rather than retain actionable stale data. Repaint cached parent/task screens on resume, not unmounted widgets.
- Keep the overlay scoped to the captured repository/workspace and record identity so another runner/repository with the same task ID is untouched. Old reads and stale/last-good snapshots cannot resurrect the deleted record. Request a fresh off-loop observation through existing epochs/physical-slot scheduling; do not cancel a thread and pretend its slot is free. Slow or failed recollection must not undo acknowledged feedback or freeze input.
- Reconcile using off-loop working-tree/pending observation as well as committed membership. A fresh successful observation that the record is absent in committed inventory retires the overlay; a fresh observation that the record has been recreated/restored also retires it and restores any row that belongs to the current committed snapshot. A recreated record absent from HEAD is disclosed as a pending record, not inserted into committed inventory. HEAD absence alone must not conceal that pending recreation indefinitely. Unknown/read-error state retains the pending overlay with visible provenance rather than claiming a clean or committed deletion. Reject pre-action observations for reconciliation. Repeated success notifications are idempotent.
- Independent worker/slot/question observations remain diagnostics, not resurrected inventory; deleting a record does not erase actual worker activity or owner questions. Genuine independent questions can remain in Questions with that provenance. Dependent records remain present and blocked/warned under the existing semantics; the display overlay must not grant admission, satisfy dependencies or close anything.

Rejected alternatives: another timer/manual refresh does not address uncommitted deletion; silently filtering every pending path confuses edits/additions with deletions; committing from the TUI changes ownership/transaction authority; removing rows before command success falsely acknowledges failure. No filesystem watcher or new background service is needed. Planner's default scope is completion feedback for deletion initiated in this TUI; external CLI edits retain normal observation cadence.

### Single implementation slice and verification

Use the current canonical TUI/fleet implementation and existing fleet/read/pilot seams, not compatibility-shim copies. Shared writes require actual ownership reconciliation and serialized integration, not fabricated prerequisites or changed active contracts.

Planned checks: `python3 scripts/check.py pi-autowork/tests/test_fleet_view.py pi-autowork/tests/test_tui_reads.py pi-autowork/tests/test_task_history.py tests/test_task_commands.py`; the existing fleet test wrapper must actually execute its pinned Textual pilot, not count a skipped dependency as rendered coverage. Also run `python3 scripts/affected_tests.py --run` against the actual implementation base (`--base` when required). Proposed regressions are task-owned to add to existing seams, not written or run during this planning occurrence.

Acceptance/oracles: extend `tui_pilot.py` with a deterministic post-delete case with timer refresh disabled and a blocked fleet reader. After releasing command success, assert row/detail/menu removal and matching displayed counts before releasing the reader, including last-row/closed-history deletion. Then release a pre-delete snapshot and assert no resurrection. Use the real native CLI in a private Git fixture to demonstrate successful working-tree deletion while HEAD still contains the record, plus warning-success, failed/cancelled deletion, duplicate completion, another repository with the same ID, close/reopen or selection change, and later commit or restore/recreation. Existing fleet/snapshot/reader/history/command guards remain intact; tests must not delete a real repository task or invoke live services/models.

Pre-mortem guards: (1) a stale reader restores a deleted row — barrier-controlled old-result and unchanged-HEAD tests; (2) optimistic feedback hides a failed delete or another repository's row — failure/cancel/warning and captured-identity cases; (3) counters/detail disagree or a restored task stays hidden — shared projection, last-row/history and fresh restore/recreation tests. Keep no-write/view-only guards, confirmation, worker warnings, task-store format, receipts, locks and live authority unchanged. No arbitrary millisecond latency or SSH-delivery claim.

## Operational state and screen boundaries

Status: Accepted scope from the owner's request to improve TUI architecture and UI.
The design choices below are planner calls, not claims that implementation or live
qualification has passed. This is a standalone planning batch, not a runner restart.

### Outcome and evidence

The operator must see one consistent answer to what the selected runner is doing,
what it waits for, and which action is useful. Keep the current terminal workflow,
keyboard/mouse controls, read-only web mode and committed task inventory.

At source `6d636540`, `fleet_view.runner_rows` renders raw `Runner.state`, while
`verdict` uses captured task counts, jobs and questions. This permits the supplied
fleet row to say working while its selected overview says Waiting on you.
`FleetApp.show_overview` adds all snapshot annotations to its warning count, although
`fleet_view.freshness` already distinguishes some historical annotations from errors.
The screenshot's 176 warnings are not a measured count of 176 current failures.
Current `task_snapshot.capture` already ignores observations belonging to known
closed/superseded records; preserve that fix instead of recreating its task.

The read-only runtime observation during planning showed zero active workers, a
background main check for `d2cdc71`, and existing reported/integrating attempts for
450, 475, 479 and 484. Those are execution/check/recovery states, not evidence that
the UI is frozen or that a new implementation of their tasks is needed. This plan
neither retries their candidates nor changes their contracts, checks or ownership.
Main-check duration and superseded revision are evidence to display, not a UI timer
to reset. Runtime files and private process identities remain outside Git.

`tui.py` currently owns fleet rendering, read lifetimes, task/decision screens,
forms, actions and planning navigation. Task screens reach app-owned execution and
planning callbacks through `self.app`. `tui_reads.ReadCoordinator` already supplies
four physical reads, identity/epoch rejection and suspension-safe publication.
`tui_dialogs.Confirm` is already a shared leaf. Reuse these boundaries.

### Selected design and alternatives

1. **One captured presentation.** Add a pure `fleet_view.presentation(runner)`
   value for label, explanation, style, observed activity and grouped diagnostics.
   Reuse `verdict`, `task_counts`, existing lane phases and snapshot provenance;
   do not create another scheduler, truth store or filesystem reader. Preserve raw
   `Runner.state` as service/health data. Fleet State, selected overview and Details
   use the same semantic label. Real live work may coexist with recorded questions;
   those questions remain a separate actionable indicator, not a claim of idleness.
   A main check is separate observed background work, not an invented active worker.
   Unknown/stale/unmatched observations stay explicit and cannot inflate active counts.
2. **Separate task screens from the app.** Move ReadScreen and shared widget/text
   helpers needed by both owners to flat `tui_common.py`. Move TasksScreen,
   TaskScreen, DecisionScreen, NewTask, PickSection, CommitEdits and TextPrompt to
   `tui_tasks.py`. FleetApp retains application lifetime, selection, read coordinator,
   command execution, deletion overlays, planning hub and navigation. Task screens
   call that host through the existing callbacks, not an import of FleetApp.
   Retain same-object exports from `pi_autowork.tui` for existing imports and tests.
   Keep Confirm and tui_reads as their existing owners. No framework, service locator,
   new dependency, nested package migration or duplicate class implementation.
3. **Action-first UI.** On the fleet screen show runner identity, consistent state,
   compact count/provenance and the primary useful action. Put secondary controls
   behind a labelled More menu while retaining every direct binding and confirmation.
   Selection must not move on refresh. Task/lane cells show committed task names,
   then phase and concrete wait reason; IDs stay available in Details and remain row
   keys/action identity. Duplicate titles cannot redirect actions. Missing names fall
   back to IDs. Long last-agent prose belongs in worker/log views, not the primary
   status column. Waiting for a check slot, review, integration or a dependency must
   remain distinguishable. Unmatched runtime lanes remain annotations, not inventory.
4. **Explain diagnostics.** Separate actual acquisition errors from source/provenance
   notes. Deduplicate identical messages for the overview, summarize their categories
   and retain every original message and affected ID in Details/Blockers. Never hide
   stale source, contract mismatch or unavailable inventory to make a green screen.
   Keep main-check running/red/green/broken state and checked/current revisions with
   their original age. Superseded work does not mean the current main passed.

Rejected: cosmetic label changes in each widget (keeps contradictory authorities),
a replacement TUI/web stack (unnecessary dependencies and lost guards), a fresh task
ledger or forced recovery/restart (outside this UI request), and splitting every
screen now (unbounded refactoring with no user benefit). Preserve the existing
immediate post-delete feedback contract above, including pending-commit overlays.

### Executable batch

- `TOOLSET-485-93544fa5`: consistent runner presentation and grouped observations.
- `TOOLSET-486-e49cf8cb`: extract task-screen/read helper ownership with unchanged behavior.
- `TOOLSET-487-2938d3f0`: consume both seams for the action-first fleet/task UI.

The first two have no product dependency on each other. The third consumes their
actual presentation and screen interfaces. All name the existing
`autowork-python-layout` resource because migration 479 is actively moving these
source/test owners. This serializes actual admission, including the first two;
independent selection-ready does not mean simultaneous execution. Do not alter
479 or invent completion of its retained candidate. Preserve goal priority/focus.

Path rule: edit the actual selected source owner only. The accepted component map
moves `src/pi_autowork/X.py` to `pi-autowork/src/pi_autowork/X.py`, product test files
to `pi-autowork/tests/runner/`, and `src/README.md` to
`pi-autowork/docs/source-layout.md`. Task touches explicitly permit both alternatives;
never recreate a retired path or edit a public compatibility adapter as a second owner.
The records contain conditional focused check commands for these exact alternatives.

### Verification and boundaries

Use synthetic captured Runner/TaskSnapshot inputs for contradictory state, live
review plus questions, valid empty, invalid/stale inputs, unmatched contract rows,
repeated source notes and superseded main checks. No live service/model is needed.
Extend only changed assertions in existing suites and add bounded behavior-owned
fixtures, not another giant all-purpose pilot. Preserve the existing rendered tests.

The UI slice owns a new focused Textual pilot/wrapper at 80x24, 120x32 and 160x48
(planner-selected terminal cell sizes). Keep text and actionable controls inside the
viewport or an explicitly scrollable region; keyboard and mouse must reach the same
routes. At 80x24 prioritize primary state/actions, task identity and evidence access,
not every secondary column. A blocked reader must not prevent input acknowledgement,
selection, menu open/close or pending-delete feedback; use event barriers, not an
invented millisecond benchmark. Missing pinned Textual setup is a disclosed unmet
check, never rendered acceptance via skip. Existing offline setup may provision its
isolated pinned dependencies during later implementation; planning installs nothing.

Pre-mortem: contradictory status returns through a second renderer (shared projection
fixture); extraction breaks suspended screen/action identity (existing lifetime,
view-only, duplicate callback and same-object export guards); compact layout hides
truth or targets the wrong task (named viewport pilot with duplicate titles, long
names, stale reads, mismatched source, failure/cancel and restored deletion cases).

Expected delivery: three implementation integrations and three independent reviews,
plus this one planning commit. Worker checks are focused; the runner owns affected
landing checks and its separate full-main check. All proposed implementation/pilot
checks are UNRUN in this planning pass. Physical terminal/SSH/browser appearance and
installed-release behavior remain unqualified; no live acceptance or deployment is
inferred from offline fixtures. No speculative rolling successor is needed: this
request has a fully defined three-task frontier. Stop after saving and validating it.
