# tasks/: the repository work center

A repository's `tasks/` directory is the one place to plan, order and track its work.
`tasks/items/<ID>.md` holds one task, `tasks/goals/<ID>.md` one goal, and
`tasks/evidence/<ID>.toml` the receipt the engine writes when it verifies a close.
Plans and research receipts support these records; they must not become separate
invisible backlogs. `BLOCKERS.md` holds owner questions and `CHANGELOG.md` the
release notes. A `TODO.archive.md` that exists is frozen, read-only history.

Every task/goal record edit goes through `autowork tasks` (see [Edit records](#edit-records)). It
writes only the working tree, never commits, and validates the whole store before
keeping a write. Its operation-local conflict check protects the CLI's own read;
carry `record_revision` to `--expect REV` to protect an earlier planning read across
calls (see [Edit records](#edit-records)).

Autowork executes in the current agent session with optional authorized host-native
delegation. Old cards are not leases: inspect real process/workspace activity,
preserve useful candidates and source-bound checks, and keep required independent
review, explicit allocations and publication limits. Native task-state transitions
are not prerequisites for selection, recovery, review or integration.

## Task CLI policy

For task operations only, use `autowork tasks` within the current workflow's
existing authority. This grants no new task-producing role: read-only,
questions-only and audit stay nonmutating; worker/coordinator boundaries, active
contracts, holds, live gates and commit/publication limits remain unchanged.
Unrelated file edits do not need the task CLI. Keep shared plan decisions and
permitted reasoning in their existing document owners, not a runnable alternate queue.

1. **Available CLI.** Run `autowork capabilities` before task operations. Require a
   successful handshake with `tasks` in `commands`, `prepare` and the required verbs
   for the intended operations in `tasks`, and `prepare_api >= 4`. Check its
   `executable`, `toolset` and `release` against the loaded skill/toolchain. Use the
   [Docs Sync prepare flow](../docs-sync/SKILL.md#prepare-the-store-first) on the
   actual consumer, retaining every outcome and authority limit (read-only uses
   `--check`). Reuse verified capability/prepare results only while inputs are unchanged.
2. **Missing wrapper only.** If only the PATH wrapper is unavailable, resolve the
   trusted loaded Kit root from the actual loaded skill path or explicit host
   installation metadata. Verify its existing `pi-autowork/pi_autowork/command.py`
   and use an available compatible Python interpreter to run that same CLI.
   Use absolute quoted paths and an explicit consumer repository, never the skill
   directory or an implicit current directory. For example, replace these paths
   with the verified interpreter, loaded Kit root and intended repository:

   ```sh
   "/absolute/python3" "/trusted/kit/pi-autowork/pi_autowork/command.py" capabilities
   "/absolute/python3" "/trusted/kit/pi-autowork/pi_autowork/command.py" tasks show ID "/absolute/consumer" --worktree
   cd "/absolute/consumer" && "/absolute/python3" "/trusted/kit/pi-autowork/pi_autowork/command.py" tasks field ID --json "/absolute/field.json" --expect REV
   ```

   Require the same capability handshake before any task operation. Supply the
   repository argument explicitly for add, prepare, show and validate. For
   `field --json`, explicitly change to the consumer directory with `cd` as above:
   its optional label/value positionals cannot carry a repository with JSON.
   Use the existing [literal JSON and revision guards](#edit-records).
   This replaces invocation only, not the tool or its guards. Never search arbitrary
   checkouts, download or automatically install tools, silently substitute a
   foreign release, or use PATH mutation to make this work. An incompatible wrapper
   is not a missing wrapper: do not switch toolchains to evade a failed handshake.
3. **Unavailable toolchain.** If the CLI entrypoint or runtime is absent or incompatible,
   or required capabilities are missing, report `TOOLCHAIN_MISMATCH`, the exact missing
   input and retry command for the intended consumer. Continue permitted discussion
   and document work. Show complete proposed task changes inline, marked **UNSAVED**:
   include proposed new records (IDs provisional until allocated), field deltas,
   ordering, goal changes and deletions as applicable, with literal JSON/CLI inputs
   sufficient to retry after a fresh read. Do not hand-edit task Markdown/TOML,
   TODO.md or goals.json, create a second queue or fallback tracker, or claim these
   changes were saved, committed, delivered or executed. Existing document owners
   may retain allowed reasoning, never an alternate executable backlog.
4. **Refusal is not absence.** A stale revision is not tool absence: reread and
   reconcile the latest record through the normal CLI, then reapply only the
   still-authorized delta with its `record_revision`. An unresolved guard refusal
   (lock, validation, ownership or conversion) must be reported, not bypassed with
   another invocation, direct files, force or a fallback queue. Preserve existing
   prepare outcomes and report unsaved changes honestly; the fallback grants no
   installation, conversion-force, execution or delivery authority.

Use [Edit records](#edit-records) for add, field, place/move and goal operations.
For delete, follow [completed-task retention](#completed-task-retention), including
fresh ownership and dependency checks before deletion: delete diagnostics are
warnings, not safety refusals. A successful command alone does not establish safety.

## The records

A task file starts with TOML frontmatter between `+++` lines, followed by free body
notes, one per line as `- Label: value`.

| Field | Meaning |
| --- | --- |
| `id`, `title`, `short` | The ID, its outcome, and one line of at most 40 characters for task lists such as the autowork TUI's Tasks window (`Retained commits resume their worker`). |
| `status` | `open`, `done` or `superseded`. There is no in-progress status. |
| `goal` | Optional goal ID for a meaningful multi-task outcome. |
| `section`, `rank` | `Now`, `Next` or `Needs decision`, and an integer; lower runs first within its section. |
| `depends_on`, `verified_depends_on` | Task IDs that must be done first; the verified subset additionally requires verification or an explicit owner exception. |
| `touches`, `resources` | The write set and the shared resources (see [Bound the write set](#bound-the-write-set)). |
| `kind` | `implementation`, `plan` or `inspection`. |
| `ownership` | `worker`, `coordinator` or `owner`. Only `worker` tasks run in the runner. |
| `live` | `denied` (default) or `authorized`; a task with the `live` resource runs only when authorized. |
| `scope`, `acceptance`, `checks`, `exclusions` | The bounded outcome, its observable criteria, the commands that prove them, and what it must not do. |

Body notes carry what is not contract: `Sources`, `Owner decision`, `Held by`,
`Blocker resolution`, `Evidence`, `Question`, `Plan round`, `Superseded by` and the
like. A note never grants authority; only the typed fields `live`, `resources` and
`ownership` do. A record missing contract fields is a visible draft and is never
selected.

For an explicitly attributed regression, put `- Regression of: <ID>; commit <sha>; severity low|medium|high; found by owner|check` in the later task's body, naming the original task and its receipt's full integration SHA; discovery is the note's first commit, not a later edit to the same files.

A goal file carries `id`, `title`, `priority` (1 first), `source` (the accepted plan
or spec, `path#anchor`), `status` (`unmet`, `partial`, `unverified` or `met`),
`focus` (at most one goal has it) and `depends_on` (goal IDs).

Priority is the section (Now before Next), then rank, gated by goal focus, goal
priority and dependencies. Moving a task is editing its rank; there is no other
recorded order.

### Ordinary authoring

Supply title, scope, acceptance and checks. `autowork tasks add` derives the ID,
short label and scheduling defaults; goal and custom short label are optional.
Do not invent a goal, duplicate specification, separate plan, completion report or
TODO.md for an ordinary task. Link shared intent instead of copying it. Existing
BLOCKERS.md managed questions are a projection of task/runtime state, not a second
backlog; preserve still-needed external inputs outside that projection.

The four authoring inputs save intent, not dispatch permission. A record without
bounded `touches` stays draft. The coordinator resolves write scope and real shared
resources from source before dispatch, retaining all live and verification gates.
Defaults never authorize a repository-wide write or fabricate completion.
For the saved text, apply [task names](#task-names) and
[task descriptions](#task-descriptions).

### Task names

Use this policy when creating or materially refining an in-scope task in both
planning modes. Choose wording from the accepted scope; no extra interview is
needed just for naming.

- **`title`:** Name a concrete action or observable outcome and the affected
  component or user-visible object. Include enough distinguishing context to
  understand the change without opening the task. Add a condition or failure case only when
  it distinguishes similar work. Prefer direct action-led titles; clear outcome-led
  titles are also valid. This is guidance, not a mandatory grammar.
- **`short`:** Optional authoring override; the CLI derives a bounded label from
  the title. When supplying an override, write a meaningful standalone summary of at most 40 characters for
  task lists. Preserve the distinguishing object and outcome. Do not merely truncate
  `title` or repeat the ID.
- Reject padding, unexplained acronyms, and generic Improve/Fix/Update titles that
  do not identify the object and intended change or outcome.

| Kind | Weak title | Strong title | Standalone short |
| --- | --- | --- | --- |
| Feature | Improve downloads | Add invoice downloads for offline review | Download invoices for offline review |
| Defect | Fix retries | Stop invoice retries after payment succeeds | Stop retries after invoice payment |
| Planning | Update plan | Plan offline invoice checks before rollout | Plan offline invoice checks |

Before saving, read `title` and `short` independently and beside sibling tasks
as separate task-list entries: can a reader
identify what changes, which object it affects, and what distinguishes it from
nearby work? Check the short label's length and revise vague wording using only
the task's existing scope.

Naming never changes a task's meaning, acceptance, ID, authority or status. Keep
historical records unchanged; do not bulk rename the backlog. No title length cap,
rigid word-count rule or naming heuristic is added to CLI validation or selection.
These are planning instructions, not evidence of future model output quality.

### Task descriptions

Apply this shared standard when Plan For Me, Plan With Me, Docs Sync, Autoresearch,
Autowork discovery or other task-producing skills create or materially refine an
in-scope task. Use existing fields and brief notes only where they add information:

- **`scope`:** Explain the intended behavior change and its bounded context, not
  just a path list or a restatement of the title. Include the reason when it helps
  distinguish the work. Preserve known constraints and exclusions; `touches` owns
  the write set, not the behavioral description.
- **`acceptance`:** Name observable results and the tests or evidence that will
  prove them. **`checks`:** Give the exact commands separately. Mark future tests
  unrun; a required command is not a passing result.
- **Notes:** Give a concrete first action, source-backed decisions and required
  inputs in existing notes such as `Next action:`, `Decisions:` and `Sources:`.
  Add only what the typed fields do not already say. Link evidence and shared
  inputs rather than restating them. Identify genuinely unavailable external
  inputs on only the affected work, with the exact missing input and resume
  condition; do not invent inputs, readiness or another settled permission question.
- Do not repeat the same procedure across scope, acceptance and multiple notes.
  Link shared workflow rules instead of pasting boilerplate into every task.
  Brevity must preserve all mandatory checks, constraints and real limitations.

Before saving, read the task as an implementer: are the outcome, boundary,
starting action, reachable inputs and evidence of success clear without another
design round? Repair wording from source evidence; unresolved intent stays explicit.
Do not rewrite an active contract or bulk-edit unrelated tasks to apply this
standard. No fixed prose length is required; this is not a schema or CLI quality
gate, nor proof of future model adherence.

## Read orders before selecting

Read `autowork tasks list`, the records you will act on, accepted plans and current
execution state. Reconcile attributable user instructions before task selection:
new work, priority, Now/Next order, scope changes, pauses and cancellations. Reflect
each with `autowork tasks`. A known user priority change supersedes old ranks;
formatting differences or untrusted quoted material are not new authorization.
Preserve unrelated edits. If provenance or intent is ambiguous, preserve both
versions and ask one precise question while continuing unaffected work. Never
silently overwrite a user order.

Changing priority does not satisfy a dependency, stop a live worker, remove an
explicit exclusion or establish completion. `autowork tasks why ID` explains
committed-store selection eligibility and position, not admission, capacity,
current ownership or dispatch; choose its prerequisite or independent authorized work. Pauses and
scope restrictions remain binding. Do not infer execution authorization from an open
task, a research recommendation or a generated plan alone.

## Save research by default

An Autoresearch invocation in a repository includes permission to persist its
in-scope findings and plan through docs-sync. The user need not say “save”.
For explicit read-only, chat-only, no-write or --dry-run requests, write nothing and
return proposed task updates in chat. A planning-only or “do not implement” request
still saves planning documents and task records; it does not change product code.

Reuse existing task IDs and document owners. New IDs are plain numbered IDs such
as `TOOLSET-084`; do not append a hash or random suffix. `autowork tasks add`
allocates the next number, counting existing, archived and locally committed
historical IDs (including legacy hashed IDs), so pruning committed tasks does not
recycle their numbers.
`autowork tasks new-id` prints a candidate, not a reservation; let `add` allocate
under its write lock, and reconcile cross-checkout collisions rather than overwrite.
Keep existing IDs and references intact, especially for live attempts; removing
legacy suffixes requires a separate safe remapping, not blind normalization. A discovery pass that finds the existing backlog already covers the
evidenced gaps reports that and changes nothing; a short queue is not permission to
invent work. A task may stand alone. Add a goal with `autowork tasks goal ID
--title T --source path#anchor --priority N` only for a meaningful shared outcome.

Put executable details in the record: `scope`, `acceptance`, `checks`, `depends_on`,
and a `Sources:` note for existing shared intent when applicable; a task that uses another's output may name the
seam in `Produces:`/`Consumes:` notes. Each acceptance criterion names the test that
proves it ([executable acceptance](PLANNING-CRAFT.md#executable-acceptance)). `checks`
names the focused commands that prove the acceptance (a test file, class or
selector); preserve all task-required commands and mandatory checks. Acceptance
asks for behavior, never for a number of tests (see the
[test budget](ENGINEERING-CYCLE.md#test-budget)). Workers run focused/task checks.
For this repository's standard check runner, landing runs affected checks on the
merged candidate; main separately runs the full check after landing. An affected
pass is not a full-main pass. A task's full-check entry is satisfied by the runner's
full merged-tree gate, not repeated by a worker; custom required checks remain binding. Link a substantial plan from its tasks; do not create a
separate plan file merely to satisfy a ritual.

Keep unsupported ideas visibly in `Needs decision` with their `Question:` note
instead of fabricating acceptance. If research finds no new work, retain existing
bytes and report why. Missing Graphify or a failed readiness gate must be reported
honestly; saving a plan and qualifying its execution are distinct outcomes.

### Bound the write set

Every executable task you create or rewrite gets `touches`: the repository-relative
paths or globs it is expected to change (a trailing `/` covers a directory). Name the
exact files from the scope, sources and the code you inspected, including its tests
and docs; when a file is not known yet, widen to the owning directories rather than
omit the field. Parallel Autowork uses `touches` to rank likely-independent work
first. Ordinary file, directory and glob overlap is a scheduling hint, not a
dispatch gate, regardless of how many unfinished tasks name a file. Report possible merge conflicts honestly; do not invent product
`depends_on` edges for file overlap. Keep real prerequisites and
[bounded write sets](PLANNING-CRAFT.md#disjoint-write-sets). Add `resources` where
needed (`exclusive` to run alone, `live` for authorized live work, or shared names
such as `test-db`);
resource and protected manifest/lock/schema/migration/CI gates still apply. Only
when no path can be bounded, set `resources` to `exclusive` with the reason in a
note and `touches` to the widest owning directory. Do not list `tasks/`,
`BLOCKERS.md`, `TODO.archive.md` or `CHANGELOG.md`: the coordinator owns them.
`Needs decision` tasks may stay drafts until they become executable.

### Task holds require an explicit user request

Leave accepted tasks open in `Now` or `Next`, available to the authorized runner.
A skill may add or renew `Held by:` or run `autowork tasks hold` only when the user
explicitly asks to hold or pause the affected task. Record that request and its
scope; a skill name such as `PLAN-FOR-ME` is not authorization to hold work.
This rule applies to planning, Docs Sync, manual execution and delivery alike.

“Plan only”, “no code this pass” and “do not implement in this session” limit the
current session. They do not pause an existing authorized runner or require a later
implementation order in the saved task's exclusions. Do not substitute a goal pause,
`Needs decision`, a fake dependency or an incomplete contract to reserve accepted
work. Keep genuine unresolved decisions, prerequisites and approval limits explicit;
open does not mean dependency-ready, admitted or authorized for live operations.

Use supported execution leases, workspace locks and current worker checks to prevent
duplicate execution, not an unrequested task hold. Preserve existing user pauses,
live claims, runtime failure holds and safety gates; this rule does not clear them.
If this pass added a planning-only hold without a user request, remove only that
attributable hold before handoff with `autowork tasks release`, after verifying no
live owner or explicit pause relies on it. Preserve other notes and exclusions, and
use `--expect REV` after an earlier read. Unknown ownership needs investigation,
not blanket release. Report remaining real blockers separately from skill-created
reservations.

### Edit records

| Command | Effect |
| --- | --- |
| `autowork tasks list`, `validate`, `show ID`, `why ID` | Read the committed store; `list`, `validate` and `show` also accept `--worktree` for uncommitted edits. `why` is selection evidence only. |
| `autowork tasks add --title T [--goal G] [--short S] [--section] [--scope] [--acceptance] [--checks] [--touches] [--depends-on]` | A new open task at the bottom of its section; repeat a list flag per item. |
| `autowork tasks field ID LABEL VALUE` | A typed field (`rank`, `touches`, `checks`, `kind`, ...) or any note label. |
| `autowork tasks place ID Now\|Next\|"Needs decision" [--decision TEXT]` | Move to the bottom of a section; `--decision` also records an `Owner decision:` note. |
| `autowork tasks move ID up\|down` | One place up or down within its section. |
| `autowork tasks hold ID --by WHO [--until YYYY-MM-DD]`, `release ID` | Apply an explicitly user-requested task pause, or release a reconciled hold under the policy above. |
| `autowork tasks done ID --by WHO --reason TEXT [--evidence REF]` | Manual close of any task kind; optional evidence is a reference, not verified acceptance. |
| `autowork tasks supersede ID --by OTHER --reason TEXT` | Replace a task. |
| `autowork tasks delete ID` | Delete a task record only after the [ownership/dependency and retention checks](#completed-task-retention); warnings are not safety refusals. Receipts and dependents are unchanged. |
| `autowork tasks goal ID [--title --source --priority --status --focus/--no-focus --depends-on --evidence]` | Add or change a goal; `--status met` needs evidence and all non-superseded owned tasks done and qualified. |
| `autowork tasks goals [--worktree]` | Read every goal record, in priority order. |
| `autowork tasks commit [--message TEXT] [--dry-run]` | Commit the working tree's `tasks/` edits and nothing else; `--dry-run` shows the paths and their diff. |

**Pass prose as literal JSON.** For quotes, backticks, `$` (including `$(...)`
and `$VAR`) or newlines, write a UTF-8 JSON object with a file-writing tool; from
the consumer repository run `autowork tasks add --json task.json`,
`autowork tasks field ID --json field.json`, or
`autowork tasks goal ID --json goal.json`. Stdin uses `--json - < task.json`.
Never interpolate prose into shell arguments, `echo` or an unquoted heredoc.
Keys mirror options with underscores, list options take arrays, and field uses
`{"label": "scope", "value": "text"}` (arrays for list fields). Add's `notes`
and field label `notes` preserve the entire raw multiline Markdown body; read it
first and retain Sources, holds and other notes. Do not mix JSON with value flags
or label/value arguments. See [literal input](../../pi-autowork/task-store.md#literal-prose-input---json)
for all keys/types. Validation, authority checks and `--expect REV` still apply.

**Protect an earlier read across calls.** Read the current working-tree record,
retain its `record_revision`, decide the attributable delta, then supply that digest
as `REV` (not HEAD, `rev` or `contract_hash`):

```sh
autowork tasks show ID --worktree
autowork tasks field ID --json field.json --expect REV
```

Write `field.json` with a file-writing tool as described above. JSON protects literal
prose, not freshness. On refusal, reread the latest record, compare changes and
reapply only the still-authorized delta using its new `record_revision`. Preserve
other edits, notes, ranks, holds and transitions; withdraw obsolete changes. Never
replay a stale full snapshot or blind retry with a freshly substituted digest. The
operation-local check alone cannot protect decisions from an earlier call.

Finish a planning batch with `autowork tasks validate --worktree .`, then commit the
`tasks/` changes. A worker never edits `tasks/`: its commit that does is held and
never merged. Live authorization is the owner's to grant.

### Manual is not verified

A manual close records `closure = "manual"`, actor, timestamp, reason and optional
reference. It writes no receipt, check result or verification claim. Ordinary
`depends_on` accepts a manual done task; `verified_depends_on` additionally requires
verification or an explicit owner exception. A manually closed owned task cannot
qualify `goal --status met` without an owner-recorded `owner_waiver` (exact criterion,
reason and risk) or `owner_qualification` (qualification and evidence). Never invent
these attestations from a planner decision or passing report, or manually close
implementation acceptance just to make the queue green. Honor explicit owner stops
without relabelling unmet acceptance as verified. Only the engine's verified close
writes `closure = "coordinator_verified"` and its receipt with `status = "done"`
in one commit; planning never fabricates or edits that receipt.

## Completed-task retention

Keep `tasks/` focused on unfinished work. Delete eligible completed task records
and their dedicated receipts/reports after real closure and integration; Git history
is the archive. The target is no unnecessary done records, with no arbitrary keep-last-N
quota, grace period or replacement completion ledger. This applies to Docs Sync and
other authorized task-maintenance workflows. Audit/read-only never deletes anything;
a narrow request cleans only completed work within scope.

Pruning is a separate reconciliation after closeout, not a replacement for it:

1. Read fresh Git/store status and actual worker/session activity for the records
   and their consumers. Verify closure and integration from source-bound evidence.
   Never delete an active attempt, rewrite a running contract, discard an unresolved
   live obligation or treat a done label, task age or empty queue as completion proof.
   Unknown ownership or missing evidence means retain the affected record, not a
   blanket halt to unrelated safe cleanup.
2. Inspect dependencies, goal qualification, source links and receipt consumers.
   Remove only already-satisfied ordinary dependency edges from inactive surviving tasks,
   using `autowork tasks field` with a fresh record revision. Do not drop
   `verified_depends_on` or erase a manual closure that still enforces a qualification
   or owner-waiver gate. Preserve required proof through immutable Git references or
   current open requirements before pruning; a prose link cannot replace a typed
   verification gate. If the current consumer still needs the record/receipt to enforce
   that gate, retain it until that need ends. Never fabricate qualification or a waiver.
3. Once safe, use `autowork tasks delete ID` for each eligible record. This command
   can delete live or referenced tasks: its warnings are warnings, not safety refusals.
   Perform the checks above before invoking it; do not use successful deletion as
   evidence of safety. It leaves receipts and dependents untouched.
4. Remove only dedicated receipts/reports whose consumers and remaining obligations
   have been reconciled, using scoped file removal after confirming their immutable
   Git copies are reachable. Never fabricate or rewrite receipts, replace them with
   a completed-task summary, rewrite Git history, delete worktrees/runtime recovery state,
   or alter generic archive-import fixtures. Shared specifications, ADRs, release notes
   and a pre-existing frozen archive are not disposable task reports.
5. Keep goal status, focus, owner/live gates and unresolved acceptance unchanged;
   an empty history is not proof that a goal is met. Run
   `autowork tasks validate --worktree .`, check surviving references and confirm that
   selection changed only by removing satisfied prerequisites. Re-read status before
   landing; commit only within existing authority and preserve concurrent changes.
6. Report cleanup counts and the concrete current reason for each retained record
   (for example, active consumer, required verification proof or pending qualification).
   Do not create a completed-task list or archive. Repeat passes with unchanged
   evidence leave the store unchanged. Runtime closeout may create transient done
   records; this policy does not bypass runtime checks or make an older installed
   runner perform automatic garbage collection.

## Rolling planning

When accepted work is too large for one batch, save the first batch whose content
is known now, not speculative implementation tasks for the whole project. End it
with exactly one planning task under the same goal, depending on every building
task in that batch. Its `scope` names the goal, what the next round must find out,
and the evidence to read: finished task reports, current code and remaining goal
proof. Keep normal task fields, source links and acceptance/checks; planning is an
explicit task, not an invitation for code workers to edit the queue.

| Field | Meaning |
| --- | --- |
| `kind = "plan"` | The runner routes this task to its docs maintainer for planning-only writes, never to a code worker. Set it with `autowork tasks field ID kind plan`; building tasks keep `implementation`. |
| `Plan round: N of M` | A note: planning round and limit, with `1 <= N <= M`. Start at `Plan round: 1 of 10` by default (`autowork tasks field ID "Plan round" "1 of 10"`); a successor carries `N+1 of M`. Preserve an existing chain's limit; a smaller M may be chosen. |

Each round saves at most 8 new tasks total, including its closing planning task
and any `Needs decision` items, all under the same goal. Revise an oversized batch;
do not silently drop tasks. Put owner-only gaps in `Needs decision` with their one
`Question:`; they are not dependencies of the closing planning task, so independent
building work can continue.

After the batch finishes, the authorized runner runs the planning task through
Plan For Me, saves the next known batch, and closes the current planning task with
`autowork tasks done ID --by WHO --reason TEXT [--evidence REF]` in the same planning
commit. This closes the planning activity manually, not the implementation's
acceptance or remaining goal proof. If the goal is still
unmet, N < M and new building work was added, end that batch with one successor
depending on every new building task. At round M, or when a round adds no building
task, save no successor. If the goal is still unmet, record what remains and one
continuation question in `BLOCKERS.md`; keep an open `Needs decision` task for the
remaining goal proof/continuation. Never mark a goal met merely because its queue is
empty. Planning tasks run one at a time per repository because they share queue
ownership.

The report says the chain will continue on its own with an already running,
authorized runner, states its round limit (10 by default), and explains how to stop
it: move the planning task to `Needs decision` (`autowork tasks place ID "Needs
decision"`). Saving a chain does not dispatch workers, start a runner or schedule,
or widen execution/publication authority. Read-only modes save nothing. Small tasks
and plans that fit one batch add no planning task; their existing saving flow is
unchanged.

### Example: port this project to Flutter

Illustrative first batch after repository research and platform/screen scope are
settled. These abbreviated records show the chain; real tasks also carry `touches`,
`acceptance`, `checks` and a `Sources:` note derived from that repository, as
required above.

```toml
+++
id = "PORT-001-a1"
title = "Build the Flutter app shell"
goal = "PORT"
section = "Now"
rank = 1000
depends_on = []
kind = "implementation"
scope = "Add the agreed Flutter target with navigation and the existing design tokens."
+++
+++
id = "PORT-002-b2"
title = "Port the agreed first screen"
goal = "PORT"
section = "Now"
rank = 2000
depends_on = ["PORT-001-a1"]
kind = "implementation"
scope = "Connect that screen to the existing API and prove its agreed parity checks."
+++
+++
id = "PORT-003-c3"
title = "Plan the next Flutter port batch"
goal = "PORT"
section = "Now"
rank = 3000
depends_on = ["PORT-001-a1", "PORT-002-b2"]
kind = "plan"
scope = "For PORT, read the shell/screen reports and code; find out which remaining screens can reuse them and what API parity gaps the next batch must close."
+++
- Plan round: 1 of 10
```

### Example: fix a README typo

A clear task is saved normally, without a closing planning task:

```toml
+++
id = "DOC-001-d4"
title = "Fix the README typo"
goal = "DOCS"
section = "Now"
rank = 1000
depends_on = []
kind = "implementation"
scope = "Correct the identified typo without changing the documented behavior."
+++
```

## Make the queue easy to operate

`autowork tasks list` is the overview; report it in these terms:

| Area | Content |
| --- | --- |
| Now | Selected task ID, outcome and next action |
| Next | Ordered ready tasks or their explicit prerequisites |
| Needs decision | Specific unresolved questions and the task they affect |
| Waiting | Held tasks and external qualification/input, plus local work that can continue |
| Done | Transient closeout or still-required proof only; prune under [completed-task retention](#completed-task-retention) |

Waiting and Done are presentation categories, not statuses or a second task list.
Keep goal statuses and dependencies valid. Update only affected records; unchanged
findings must not churn files, rerank unrelated tasks or create duplicates.

## Close the loop

Autoresearch reports saved paths, added/updated task IDs, Now/Next and what can run.
Use plain language: “Plan saved; task X can start, after prerequisite Y” rather than
presenting a helper exit code as the whole outcome. Include technical readiness
results when useful. A saved plan is not an implemented feature.

Autowork reads this queue first. Execute a clear runnable task directly. If a task
has an unresolved research or decomposition question, invoke bounded Autoresearch
in the current conversation. If the queue is empty, inspect for useful work first;
a clear bounded repair needs only a task record, not a research pass. Add the
record, validate and retry selection in the same occurrence. Under broad
repo-development authority, inspect a fresh relevant code/docs/UI/test seam and plan
up to three evidence-backed slices. With task-limited authority, stay inside that
scope. Do not invent work, loop on identical research, start a timer or require a
separate owner reply.
