---
name: autowork
description: "Implement and verify ready repository tasks."
version: 0.28.2
author: Hermes Agent
platforms: [linux, macos]
metadata:
  hermes:
    tags: [autonomy, planning, backlog, verification]
---

# Autowork

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Execute a bounded useful slice in the current agent session. `tasks/` is the one
task store: `tasks/items/<ID>.md` owns each task's intent, scope, acceptance,
dependencies, section, rank and status; `tasks/goals/<ID>.md` owns goals; and
`tasks/evidence/<ID>.toml` holds the receipt of a verified close. Every edit goes
through `autowork tasks`. A repository needs no Hermes setup or extra public
tracking file. No Kanban lookup, card, board, assignee, native
continuation API or native review transition is a prerequisite, including recovery
of old work. Historical cards are not leases. Preserve their evidence without
querying, importing, releasing, resetting or deleting them.

Read repository instructions and accepted decisions first. A ready task needs no
planning prepass. Decide reversible details, implement, test, repair and close out
without reconfirmation. Delegate through host-native tools only when useful and
authorized; no mandatory worker launch. Select a supporting skill only for a
concrete method gap; use [engineering guidance](../shared/ENGINEERING-CYCLE.md)
only for that gap. Planning resolves consequential missing choices through
[Plan For Me](references/backlog-planning.md); it does not become a second approval
loop. Apply [Ponytail](references/ponytail.md) within the existing implementation and
review step. Keep Hermes Agent unchanged.

## Apply standing approval

Read the repository's owner-adopted standing decision policy before treating an
owner-only label or missing live grant as a new owner question. When that policy
delegates full execution of approved work, approval covers the actions necessary
for its accepted outcome; record and apply it without asking again. Queue placement
alone is not approval, and explicit exclusions, pauses and human-only requirements
still apply.

The coordinator, not a worker, reconciles stale ownership and live fields through
`autowork tasks`, citing the actual approval source, actor, date and scope. Preserve
live contracts, validate and commit attributable edits, then re-read admission.
Do not bypass typed runtime gates or fabricate missing approval evidence. A policy
edit alone does not update task records or prove runner execution. If a real input
is unavailable, retain that obligation and continue independent approved work.

## Select and execute

1. **Step 0 — reconcile, never fingerprint-exit.** Reconcile once: inspect current
   workspace/Git changes, actual process identity and activity, existing candidates,
   checks and required reviews. Resume the saved continuation before discovery;
   finish authorized integration and review rework first. Historical cards cannot
   veto execution. Do not overlap a live writer or assume a stale PID proves release.
   Disable change-only fingerprint monitors. CONTINUE selection after closeout when
   caller limits permit. A completed slice is not itself a stop condition under continuation authority;
   default and explicit caller stops still apply.
   When an owner says an answer had no effect, apply
   [decision handoff recovery](references/iteration-and-decisions.md#decision-handoff-recovery)
   before asking again or replaying a mutation: distinguish saved, committed and
   actually observed work. Improve a broken shared handoff instead of bypassing a
   particular repository's commit or permission gates.
2. **Use runnable backlog first; otherwise run the docs-sync fallback.** Selection
   reads `tasks/` at the base commit: section (Now before Next), then rank, gated by
   goal focus, priority and dependencies. `autowork tasks list` shows the order and
   `autowork tasks why ID` explains a pick or a skip. A record missing contract fields
   is a visible draft, never selected. Reconcile inconsistent source evidence
   without inventing acceptance or ownership.
   Do not run a docs-sync prepass for a usable backlog task.
   Named --tasks/--plan scope stays exact. A task Autowork records or
   repairs carries `touches` from the inspected seam
   ([task rules](../shared/TODO-WORKCENTER.md)), so parallel workers can run it beside
   others. Do not create a second board. A repository without `tasks/` selects nothing;
   `autowork tasks prepare` (Docs Sync) converts it, or records the request so the
   runner drains in-flight work and converts it itself.
3. **Prepare only missing inputs, then implement.** Derive a short contract from
   the task's objective, scope/exclusions, acceptance/checks, dependencies and sources.
   Keep source/candidate identity, actual owner/session and explicit limits in
   private evidence. One coherent delivery batch may include
   connected code, tests and docs; do not split it merely by file.
   The engine is not part of this skill: it ships with pi-autowork, in
   `<toolset>/pi-autowork/engine/`, where `<toolset>` is the installed Autowork toolset
   (the Pi package `~/.pi/agent/git/github.com/TrebuchetDynamics/kit`, or a clone).
   The default is one composed command for selection and coordination:

   ```sh
   python3 <toolset>/pi-autowork/engine/owner_cycle.py /absolute/repo \
     --apply --owner-pid ACTUAL_SESSION_PID
   ```

   Resolve ACTUAL_SESSION_PID from the real persistent current coordinator process;
   never use a guessed PID or a transient shell that exits before work starts.
   The process must be task-scoped: verify its role and birth identity before
   invoking `--apply`. A shared gateway/server ancestor is not the owner; a common
   parent does not identify the current conversation. Keep inspection and mutation in
   separate calls or a conditional branch that refuses an invalid owner; printing
   an invalid role before an unconditional mutation is not a guard.
   `EXECUTE` returns a contract for this session to implement; it is not proof of
   implementation or a background launch. Moving a task is editing its rank
   (`autowork tasks move ID up|down` or `autowork tasks field ID rank N`); there is
   no separate recorded order. See [the exact interface](references/owner-cycle.md)
   for claims, bounded argv execution, release and source-bound receipts.
4. **Implement and verify.** Repair routine non-privileged environment failures,
   iterate on failing tests, and retain failure evidence. Required acceptance tests,
   independent review where required and source freshness still apply. Reuse checks
   only for matching inputs when policy allows; rerun changed-input and mandatory
   gates. A missing required review holds completion, not unrelated authorized work.
   Follow
   [partial delivery and the critical path](references/iteration-and-decisions.md#partial-delivery-and-the-critical-path).
5. **Close out.** Assess doc impact from the verified diff, Acceptance and actual docs:
   record `not_needed` with reason, `updated` with paths/readback/checks, or `pending`
   with the gap and resume action. Follow the shared [scoped documentation closeout](../shared/ENGINEERING-CYCLE.md#one-canonical-backlog-one-executor-one-closure-owner):
   resolve bundled Docs Sync in this host and run Maintain only for a concrete delta.
   Workers update in-scope component docs and report shared-doc gaps for the
   coordinator/DOCS-MAINTAINER. Preserve
   implementation and pending evidence on interruption; never replay implementation
   or launch work after a stop or pause to finish docs.
   Commit attributable verified paths locally unless forbidden.
   Use ordinary Git, repository review and integration policy. Inspect fresh target
   state and serialize canonical writes; preserve unrelated dirty work. Never push,
   deploy, publish, spend money, place trades or broaden live authority without its
   explicit scoped authorization, which may already be supplied by an owner-adopted
   standing policy for approved work. Do not request that authorization twice.
   Report actual commit/review/integration separately.
   For worktree-backed work, finish [worktree closeout](references/worktree-closeout.md):
   verify integration on the canonical `main` or `master`, then remove the task's
   worktree with `<toolset>/pi-autowork/engine/worktree_closeout.py CANONICAL --worktree PATH --apply`.
   Every `--apply` task claim also removes earlier integrated, clean, unused
   worktrees and reports the rest under `worktree_cleanup`. Preserve active, dirty,
   unmerged or recovery-bearing worktrees; report integration/cleanup pending.
   Close a task only after verified acceptance: the engine's verified close writes
   `status = "done"` plus the receipt in `tasks/evidence/<ID>.toml` in one commit, and
   replay is a no-op. A manual close uses `autowork tasks done ID --by WHO
   --reason TEXT [--evidence REF]`. It records Manual, not Verified, and writes no
   verified receipt. An existing `TODO.archive.md` is frozen history, never written.
   Read-only runs do not write.

## Ownership, limits and continuation

Use local repository locks and isolated worktrees where concurrent writers need
isolation; one writer per workspace. Before adopting idle work, inspect actual
process liveness, workspace changes, source/candidate provenance and check receipts.
Advisory locks cannot exclude manual writers who ignore them or coordinate different
hosts; an enabled same-repository cron run may also be writing. Preserve useful
candidates; do not kill workers or delete worktrees. A `Held by:` note prevents
selection. Under the [task-hold policy](../shared/TODO-WORKCENTER.md#task-holds-require-an-explicit-user-request),
only an explicit user request permits adding or renewing that note with
`autowork tasks hold`. Use supported execution leases and workspace locks for
ordinary ownership instead. Preserve existing holds; `autowork tasks release ID`
lifts only a reconciled hold. An open session or a bare PID is not
live ownership: verify the executor's identity and recent activity before releasing
an abandoned claim, keeping its work and any explicit pause. Only typed fields
(`live`, `resources`, `ownership`) grant authority; a note never does. Workers never
edit `tasks/`: a worker commit that does is held and never merged. Before requeueing, check the executor can work where the task's
files live. Never end a turn on a bare claim: leave the task open with its Next
action, a current `Held by:` note, or the explicit pause, so no claim outlives the
session that made it. A live writer does not freeze priority: an owner's rank or
section edit applies to the next selection without interrupting current work or
faking a dependency; report it only after `autowork tasks list` agrees.

Work in the canonical checkout by default; for live sessions, `BUSY`/`isolate`, integration
and execution leases follow [canonical checkout and leases](references/owner-cycle.md#canonical-checkout-sessions-and-leases).

Caller scope and saved stop/batch limits control continuation. Default: one useful
slice including recovery and closeout. Explicit stops win. Apply
[mode precedence](references/iteration-and-decisions.md#mode-precedence).
Autowork has no token, cost or time budgets: model usage and cost are measured
(`runs.jsonl`), never a reason to stop, and timeouts only bound single runs. A task
that still declares a budget, allowance or ceiling is not held for it: record its
usage as evidence and keep working to its acceptance. Spending money (paid services,
purchases) remains an authority only the owner grants.

A held or blocked task goes to [Plan For Me](../plan-for-me/SKILL.md) in the same
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

Run discovery only when no usable task remains. Under broad repository authority,
[repository maintenance](references/repository-maintenance.md) inspects a bounded
seam, records a justified task with `autowork tasks add` and executes it in the same occurrence.
Named-only jobs cannot widen scope. Empty queues, green tests or unchanged HEAD
are not proof of exhaustion; record `work_search` evidence and rejected candidates.
This policy is not a runtime guarantee of progress. No fabricated busywork.

## Parallel workers (opt-in)

Only when the user asks: [parallel workers](references/parallel-workers.md#admission-at-a-glance)
run independent tasks in separate worktrees and integrate them one at a time.

## Owner blockers

`/autowork blockers [repo|name]` is [`/blockers`](../blockers/SKILL.md): routine planning
repairs and genuine owner answers become planning, never execution.
Tasks may read runners (`autowork ls|status`), never start, stop or reconfigure them.

## Scheduled work and reporting

Autowork creates no schedules. Existing jobs follow
[scheduled policy](references/scheduled-policy.md#scheduled-runs-and-their-reports);
a paused job cannot resume itself, and occurrence scope never widens.

## Behavior-preserving refactor

A refactor inside a seam is ordinary execution: one **check** passes on unchanged
behavior, one **step** per slice, and the same check passes again; a behavior change
stays in its own task. Detail:
[iteration and decisions](references/iteration-and-decisions.md#behavior-preserving-refactor).

Folder moves are `/split-folder`; module depth is `/improve-codebase-architecture`;
unreachable code is `/unused-code`.

## Reference map

Active guidance: references/repository-stages.md, references/iteration-and-decisions.md,
references/owner-cycle.md, references/scheduled-policy.md, references/cron-autoheal.md,
references/repository-maintenance.md, references/dispatch-and-reporting.md,
references/delivery-batches.md, references/accepted-plan-execution.md,
references/whole-spec-execution.md, references/backlog-planning.md,
references/parallel-workers.md, references/ponytail.md, references/discovery.md,
references/profile-feedback.md,
references/adherence.md.

Historical native-card evidence, not instructions or prerequisites:
references/blocker-recovery.md
references/blockers-and-history.md
references/budget-controller-proof.md
references/controller-bridge-proof.md
references/handoff.md
references/maintenance.md
references/native-containment-proof.md
references/state-and-recovery.md
references/upstream-goal-selection.md
references/historical-owner-cycle.md
## Common Rationalizations

The [Definition of Done](../shared/DEFINITION-OF-DONE.md) is the standing bar; this
task's acceptance is narrower.

| Rationalization | Reality |
| --- | --- |
| "The task is obvious, so I can skip the record." | The record owns acceptance, checks and closeout. A ready task needs no new plan, but an unrecorded task has no contract. |
| "Tests are probably fine." | Close only after the required checks ran on the changed candidate. A manual close is not a verified receipt. |
| "I can fix unrelated files while I am here." | Preserve unrelated work and edit only the accepted task's paths. |
| "I can bypass a slow worker or reviewer." | Live ownership is real. Report the blocker; do not start a competing writer. |
| "The change is verified, so I can push." | Local commit, integration, push and deployment are separate outcomes. Push needs explicit authority. |

## Red Flags

- A task closed without an executed check or receipt.
- Edits outside the task's scope or `touches`.
- A second writer, a killed worker or a bypassed review.
- "Done" reported from memory, a plan or a diff.
- Push, deploy or live qualification claimed without its own evidence.

## Boundaries

- For automatic task selection and continued work in this session, use `/work`.
- Not planning; use `/plan-with-me` or `/plan-for-me`.
- Not open-ended improvement; use `/autonomous-codebase-improver`.
- Not an architecture review; use `/improve-codebase-architecture`.
- Not publication by default; use `/git-commit-push` when the request includes push.

**Done when:** one ready task's acceptance is met, its checks ran, and it is closed or reported with the exact blocker.
