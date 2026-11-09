# Worker iteration and autonomous decisions

These operating priorities apply to every Autowork run.

3. **Fix your own environment.** Install missing non-privileged tooling in user
   space/project; record installs, PATH changes and fixtures. Only sudo/system
   packages, credentials and paid resources become owner questions (priority 9).
   For offline fixtures, populate an omitted, already-qualified dependency from
   genuine local source at a verified revision (source-only; copied binaries can
   defeat negative tests), and unset only a demonstrated contaminating selector for
   the test process (`env -u NAME …`). Never fabricate markers, spoof identity
   variables or relax containment. A wrapper refusal before execution is an unrun
   gate, not a product failure. Prefer existing supported gates over new bespoke
   prerequisites.
4. **Workers iterate.** In the current session, a failing check means fix → rerun until
   acceptance, or until 5 consecutive attempts produce no new evidence. Never block
   on a first failure, and never write "one execution/one rerun/no source edit"
   limits into contracts for work inside their scope. Give workers the scope
   they need; a harness or fixture correction needed to reach acceptance is in
   scope by default, subject to explicit exclusions and live ownership. Routine
   isolated patch reconstruction and local input recovery use existing authority:
   execute the saved next step, verify it and continue on the same task. Use
   [direct recovery](owner-cycle.md#limits-and-recovery)
   when evidence lookup or reconstruction is being mistaken for missing authority.
   If an approach fails, choose another reversible implementation on this task
   while preserving accepted behavior, exclusions and checks; record material
   deviations in existing evidence. Neither debugging nor a hard implementation
   is a reason to ask permission or repeat planning. Resolve only newly exposed
   consequential choices through the coordinator's bounded planning pass.
5. **Retry and backoff across runs.** Use no automatic failure retry after an
   unknown launch; reconcile actual process/workspace evidence first. Preserve
   recorded usage as evidence. Two unchanged holds
   require a different supported repair, independent authorized work or one exact
   external input. A failed task holds only its actual dependencies and resources.
   Finish pending required review, commit and local integration before selecting
   new work. Preserve paused jobs and useful candidates. No card transitions or
   native continuation API are required for current-session recovery.
6. **Vague acceptance.** If criteria are vague, the worker rewrites them in its
   first turn as 1–3 observable checks under `Interpreted acceptance:` and proceeds.
   Ask an owner question (priority 9) only when the possible readings lead to
   materially different product outcomes; continue only independent authorized work
   until that input arrives. Honor explicit task/caller scope. Stop at acceptance.
7. **Done means scoped done.** Finish after checks pass and owned changes are committed; never rerun an unchanged
   passing gate merely to refresh status metadata. NOT_CHECKED is not qualification.
   For checks likely to exceed the terminal window, use the host's tracked
   background/session execution from the start, with a finite command timeout
   appropriate to the gate; respect execution deadlines and cancellation.
   Save command, candidate identity, session/process
   identity and log/exit receipt; observe that same run through completion.
   A transport timeout is not a test verdict: reconcile the original process
   before retrying, never launch a duplicate live check. Missing final exit/results
   remains unchecked. Reuse source-bound passing receipts when policy allows; required checks still run.
   Separate implemented, exact-source/platform qualification and verified main delivery.
   Explain progress in user outcomes: overall goal, current slice, what is still unproved.
   Keep unrelated recovery work separate; IDs and test counts must not obscure that map.
   Follow the complete outcome standard in references/delivery-batches.md.
8. **Required review.** Use the project's ordinary independent review mechanism
   when required. Bind approval to the actual candidate and checks. Review-requested
   changes run in the current authorized session, followed by affected checks and
   fresh review for changed bytes. No Kanban reassignment or card becoming done is
   required. Review approval alone does not prove all task acceptance. When explicit
   authority requires review before commit, state that ordering consistently in the
   contract and keep the post-approval commit step; review entry never requires the
   deferred commit. Scoped commit helpers may leave HEAD unchanged: use the commit
   they return, not worktree HEAD, for review and integration.
9. **Ask, don't block independent work.** Decide routine engineering choices
   (approach, internal design, tests, ordering within focus) under existing authority
   without a questionnaire. Ask only for material missing USER_INPUT, SUDO or
   USER_DECISION, using `grill-me`/`clarify` when available. Record the exact held
   action and recommendation in BLOCKERS.md and the handoff. Silence never grants
   authority or required review acceptance. Prepare authorized work up to that
   boundary and continue independent work; if nothing can proceed, report the real
   dependency honestly. Do not relabel incomplete work as done to avoid a pause.
   Existing explicit authority carries forward. Apply an owner-adopted standing
   delegation to approved work before escalating owner-only labels or missing live
   records. The coordinator records covered authority through `autowork tasks` and
   verifies the committed handoff; it does not request a second approval or bypass
   admission. Distinguish missing bookkeeping from genuinely unavailable inputs.
   Failing tests, missing user-space
   tooling, routine debugging and agent-invented restrictions are not owner decisions.
   A real tool `pending_approval` holds its original operation and dependent work
   only. Preserve its resume step and supplied request ID; do not resubmit through another tool
   or invent approval. The coordinator may select independently authorized,
   dependency-ready, non-overlapping work; workers stay within their assigned scope.
   Read owner replies (chat / `session_search`) at each run and apply them; do not
   repeatedly return `[SILENT]` for an unanswered material question.

## Apply standing approval

Read the repository's owner-adopted standing decision policy before treating an
owner-only label or missing live grant as a new owner question. When that policy
delegates full execution of approved work, approval covers the actions necessary
for its accepted outcome; record and apply it without asking again. Queue placement
alone is not approval, and explicit exclusions, pauses and human-only requirements
still apply.

Make this reconciliation before selection/admission, including newly discovered
tasks inside the delegated scope. A complete task with a covered owner-only label
or missing live grant is bookkeeping to repair, not a fresh permission request.
Ordinary model usage is covered when the standing policy explicitly includes it;
only genuinely unavailable provider/target inputs remain an input question.
A self-stop verification runs in an authorized external coordinator, not inside
the service it must stop. Preserve that execution-context exclusion.

The coordinator, not a worker, reconciles stale ownership and live fields through
`autowork tasks`, citing the actual approval source, actor, date and scope. Preserve
live contracts, validate and commit attributable edits, then re-read admission.
Do not bypass typed runtime gates or fabricate missing approval evidence. A policy
edit alone does not update task records or prove runner execution. If a real input
is unavailable, retain that obligation and continue independent approved work.

## Decision handoff recovery

Before repeating an owner question or treating an answer as consumed, inspect
`autowork tasks handoff /absolute/repo` (capability `tasks: handoff`). This read-only
report shares the exact snapshot, `pending_revision`, diff and validation used by
`tasks commit --dry-run`; its per-task states distinguish an unanswered decision,
a saved answer awaiting commit, another pending edit, a committed answer and a
committed dated deferral. It does not acknowledge runner execution or grant authority.

- `pending_commit`: the answer exists. Do not ask the same question again or replay
  the save. Review the report's complete `tasks/` diff. Commit only with existing
  commit authority and the reviewed `--expect-pending REVISION`; otherwise report
  the exact review/commit step, not a missing owner answer. Never silently include
  unrelated task edits. Changed input needs a fresh review, not an automatic retry.
- `pending_edit`: inspect what changed; an edited title or section is not evidence
  that the owner answered. Do not infer consent from a generic edit.
- `committed`: inspect `tasks why ID` and the runner's source/health before further
  repair. A commit is not runner acknowledgement, selection, task completion or
  live permission. Do not reopen the question solely because no worker started.
- `deferred`: retain the documented wait and work on independent authorized tasks.
- `answer_required`: ask only for the genuinely missing material input, within the
  task's scope. A bare `yes` cannot supply missing participants, credentials,
  publication scope or structured live authorization. When an owner-adopted
  standing policy already supplies the grant, the coordinator records that existing
  authority rather than asking again; do not invent missing approval provenance.

If the installed backend lacks `handoff`, use `tasks commit --dry-run`,
`tasks show ID --worktree` and the committed record as separate, explicit evidence.
A failed/unavailable read is unknown, never a clean store or an unanswered owner.
Do not repair a specific repository by committing its owner's edits, changing its
live fields, clearing holds or restarting its service without the corresponding
authority. Improve the shared handoff/recovery path and verify it offline first.

## Mode precedence

Caller scope and saved stop/batch limits control continuation.
Default interactive execution completes one slice, including authorized recovery
and closeout. An explicit one-task limit stops new selection after that task;
standing authority cannot override the caller's narrower stop. Explicit continuation or whole-spec scope
permits further eligible batches only within its accepted bounds.
Recurrence authorizes the saved occurrence, not wider scope. Reconcile consumed
history first. Autowork has no token, cost or time budgets: usage is measured, never
a reason to stop or a grant to spend.

## Behavior-preserving refactor

A request to refactor code inside a seam is ordinary execution, not a new workflow:
one **check** already passes on unchanged behavior, one **step** per slice, and the
same check passes again. Rename a symbol, extract a function or class, split one file
into modules, or deduplicate logic in that shape. A behavior change belongs in its own
task with its own acceptance, never in the same slice as a rename or a move.

Moving files between folders is `/split-folder`; deciding whether a module is too
shallow is `/improve-codebase-architecture`. Removal of unreachable code is
`/unused-code`.

## Close verified completion

Close a task only after verified acceptance. The engine's verified close writes
`status = "done"` into `tasks/items/<ID>.md` and the receipt `tasks/evidence/<ID>.toml`
in one commit; a replay writes nothing. A manual close uses
`autowork tasks done ID --by WHO --reason TEXT [--evidence REF]`. It records Manual,
not Verified, and writes no verified receipt. Closed records stay in `tasks/items/`;
nothing is moved to an archive, and an existing `TODO.archive.md` is frozen history.
Do not wait for a Docs Sync job. Read-only runs skip this write.

## Resolve held or blocked tasks

A held or blocked task goes to [Plan For Me](../../plan-for-me/SKILL.md) in the same
run, before reporting, and Plan For Me must **fix or skip** it. Fix: choose a
reversible change within the delegated scope, record it as the planner's call and
implement it now. Skip: split the blocked acceptance into its own open task naming
the exact missing input (never waived), then continue with the next ready task in
scope. Report a blocker again only when it is a genuinely unavailable external input
or authority (credentials, money, deployment, legal or owner approval), and only
once; never repeat an unchanged held report. Ask only for
material missing decisions or authority; never repeat a permission question already
answered. Preserve actual pending-approval requests; do not bypass them through a
new tool, session or credential.

## Partial delivery and the critical path

Before another partial delivery, compare it with the exact acceptance criterion
still preventing closure: name the positive capability it delivers or the required
gate it removes. Do not keep selecting adjacent parser, cancellation or refusal
controls while the same missing trust input or runtime capability stays untouched;
growing commit/test counts can conceal an unchanged critical path. Repair genuine
security or data-loss defects, but do not use incidental hardening as a substitute
for finishing the selected outcome. If the remaining capability is unavailable,
make the existing fix-or-skip disposition and advance dependency-ready independent
work within scope; never imply that refusal-only tests supply the positive path.
Recover independently useful fixes from an idle candidate only after verifying
provenance and current writer inactivity; compare adopted bytes, rerun affected
checks and obtain required review. Prefer one coherent final candidate and the
union of mandatory affected checks over a full rebuild/review for each tiny guard.
Reuse a sanitized cache/target and check receipts only when their bound inputs
match; retain required mutations, independent review and integration checks.
Integrate a partial slice only when repository policy permits it; record its
commit and exact remaining gates under the original task ID. Never call focused
passes a full-suite pass, waive a gate, close the parent, or infer dependency,
publication or upstream authority from partial delivery.
