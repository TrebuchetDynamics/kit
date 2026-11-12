---
name: docs-sync
description: "Maintain docs and repository tasks."
disable-model-invocation: true
---

# Docs Sync

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host-neutral Docs Sync workflow](../../../skills/docs-sync/SKILL.md) first.

Read the [host contract](../COMMON.md) and use the shared
[document scaffold](../../../skills/docs-sync/references/document-scaffold.md).
Bare invocation bootstraps missing applicable roles and updates supported drift;
scoped requests change only affected owners. Audit/read-only changes no files.
Reuse paths and combine roles for small repos; never generate empty documentation.

Inspect source/tests for current behavior and accepted requirements for intent.
Separate current architecture from planned changes. Maintain README, requirements,
architecture/spec, test plan, runbook and changelog as applicable; add conditional
roles only when useful. Fix supported doc issues now.

Load the [task CLI policy](../../../skills/shared/TODO-WORKCENTER.md#task-cli-policy)
for the missing-PATH-wrapper fallback and complete inline **UNSAVED** proposals when
tooling is unavailable. A guard refusal is not tool absence; preserve the outcomes below.

Before task work, run `autowork capabilities`: it must succeed, list `tasks` with
`prepare`, and report `prepare_api` 4 or higher (consumer/content-safe conversion).
If a present CLI fails this gate, report `TOOLCHAIN_MISMATCH` (resolved executable, what is missing, fix:
`autowork update` when the owner allows installing, then reload the host), keep to
document work, and never fall back to editing TODO.md or goals.json.

Then run `autowork tasks prepare .` in the consumer repository (Audit: `--check`,
which writes nothing; without commit authority: `--no-commit`) and act on its
`outcome`: `READY`, `MIGRATED` (converted a TODO.md + goals.json repository now),
`NO_STORE`, `MIGRATION_DEFERRED` (work in flight: the request is recorded and the
repository's runner drains and converts it; report pending, not done),
`MIGRATION_BLOCKED` (report the named refusal), `INVALID_STORE` or
`ACTIVATION_PENDING` (the running runner's release cannot read `tasks/`; the owner
restarts it). When the owner's request says `force` (`/docs-sync force`), run
`autowork tasks prepare --force .` instead (needs `prepare_api` 4): it converts now,
stopping the service, live workers and other lease holders, setting every attempt aside
with its work kept, and committing the owner's planning edits; report what it stopped
and set aside. Force accepts tracked legacy consumers without rewriting or deleting their
code; report the `LEGACY_CONSUMER` diagnostics with path, line and legacy names, then
reconcile within scope. Plain prepare lists every refusal and, if `runner.running` is
false, names `autowork tasks prepare --force` as the route without a runner drain; the
suggestion alone grants no force authority. Force never discards work or data; report a `MIGRATION_BLOCKED` it still
returns rather than deleting anything. On `NO_STORE`, writable Bootstrap creates
`tasks/` even without accepted intent. Use a file-writing tool to create an empty
`tasks/.gitkeep` only when absent, so Git retains the folder. This marker is not a
task record; all task and goal records still require `autowork tasks`. Add tasks
only from accepted intent; group shared outcomes only when useful. With no accepted
intent, report the missing input and leave the store empty. Do not create placeholder
tasks or goals, restore removed records, or put markers under `items/` or `goals/`.
Audit/read-only, docs-only and explicit no-store scopes create nothing. Never use a
marker to bypass a toolchain mismatch, conversion refusal or invalid store. Preserve
existing store contents on repeat passes. Validate with `autowork tasks validate
--worktree .`; include the marker in the scoped commit when authorized, then rerun
prepare. An uncommitted marker alone can still report `NO_STORE`; without commit
authority, report bootstrap as local-only, not `READY`. An empty store proves no
goal met and starts no runner.
Its `diagnostics` name defects with the `autowork tasks` command that
repairs each: repair only from accepted evidence, never grant ownership, `live` or
resources, never close work to silence one, and leave `IN_FLIGHT` contracts alone.
Classify each with the [triage table](../../../skills/docs-sync/references/diagnostics.md):
actionable, advisory, intentional or frozen. Read `--summary` first, then one code
with `--code CODE --limit N`. Report counts, the first failure and a path; never
paste the full report.

Before conversion, inspect `consumers`, `documentation_drift` and `preserved`. Tracked
build/CI/hook/source/test references to TODO.md or goals.json block conversion;
documentation mentions are nonblocking drift. The inventory also checks the retained Git
snapshot, so commit authorized consumer repairs first; uncommitted repairs are not in the
conversion commit. Repair consumer code only within authorized repository scope. Run `autowork migrate --accept-consumers <consumer>` only with explicit
acceptance of the reported consumers on the plain route; routine Maintain does not imply
acceptance. Resuming that route also requires the flag while consumers remain. The owner's
`force` request accepts them through `prepare --force`. Otherwise report the files/lines
and continue independent docs work. Never recreate the
legacy inputs to silence checks. Extra TODO content is preserved in `CHECKLIST.md` with
source bytes and line numbers retained (generated coverage blanked); read back the
reported inclusive `line_ranges` and reconcile into existing document owners without
losing the snapshot. Destination collisions refuse rather than overwrite. After conversion,
`LEGACY_CONSUMER` and `LEGACY_DOCUMENTATION` diagnostics identify remaining references;
repair those files from evidence within scope, not through task-field edits.

Turn accepted gaps into tasks through
[ordinary authoring](../../../skills/shared/TODO-WORKCENTER.md#ordinary-authoring):
`autowork tasks add --title T` with `--scope`, `--acceptance` and `--checks`.
Resolve `--touches`, real dependencies and resources before dispatch. Goal and
custom short label are optional; use `goal ID --title --source path#anchor
--priority N` and `--goal G` for a meaningful shared outcome. Use `field ID
LABEL VALUE` for other typed fields or notes (such as `Sources`), `place` and `move`
for section and rank, `supersede --by OTHER --reason` to retire a task and `done ID
--by WHO --reason TEXT [--evidence REF]` to close any task kind manually. Manual
closure records actor, timestamp and reason, never a receipt or verification claim.
Meeting a goal or satisfying a `verified_depends_on` prerequisite needs coordinator
verification or an explicit owner `owner_waiver`/`owner_qualification` record (set
through `field`, naming authority, criterion and evidence); never invent one.
Ordinary dependencies are unaffected. CLI/fleet views and scorecard counts keep
Manual distinct from Verified. Give each executable task its
`touches` (widen when unsure, or set `resources` to `exclusive` with a
reason) so parallel Autowork can run tasks together. Keep Now/Next/Needs decision
distinct; priority is section, then rank. Only typed fields (`ownership`,
`resources`, `live`) grant authority; live authorization is the owner's to grant.
Preserve live IDs, completed implementation, required proof, holds and priorities;
never manufacture work. The
[pruning procedure](../../../skills/docs-sync/references/pruning.md) is mandatory
within scope on every Bootstrap/Maintain, for
[completed-task retention](../../../skills/shared/TODO-WORKCENTER.md#completed-task-retention).
A bare invocation prints the `autowork tasks prune` plan and stops; it deletes no
record. `/docs-sync tasks`, or a request that names pruning or task cleanup, runs
`autowork tasks prune --apply --expect-plan REV`. Do not derive the retention rules
by script. Keep only records with a concrete current need; Git history is the archive.
Audit/read-only deletes nothing. Report cleanup counts and one reason for each
retained record, not a replacement completed-task ledger.

For any prose containing quotes, backticks, `$` (including `$(...)` and `$VAR`)
or newlines, write one UTF-8 JSON object with a file-writing tool and use
`autowork tasks add --json task.json`, `autowork tasks field ID --json field.json`,
or `autowork tasks goal ID --json goal.json` from the consumer repository.
Use `--json - < task.json` for stdin, never interpolated shell arguments, `echo`
or an unquoted heredoc. Keys mirror options with underscores; lists take arrays.
Field input is `{"label": "scope", "value": "text"}` (an array for `acceptance`).
Add's `notes`, or field label `notes`, is the complete literal Markdown body:
read and retain Sources, holds and other notes before replacing it. Do not mix
JSON with value flags or label/value arguments. See the
[literal input reference](../../../pi-autowork/task-store.md#literal-prose-input---json)
for keys and types; all validation and `--expect REV` guards still apply.

Each `autowork tasks` write changes only the working tree, never commits, takes the
task lock, refuses a file changed since it was read (or since `--expect REV`, the
`record_revision` of `show ID --worktree`) and validates the whole store; `add`
refuses a duplicate title under the same goal. Finish with `autowork tasks validate
--worktree .` and `autowork tasks prepare .` again (an unchanged repository reports
the same result). `list`, `show` and `why` read the committed store unless
`--store worktree` is given; `prepare --check` reads the working tree when task
files are uncommitted and prints `read: HEAD` or `read: worktree`. Never write
TODO.md or goals.json. An existing `TODO.archive.md` is frozen, read-only
history ([frozen archive](../../../skills/docs-sync/references/todo-archive.md)).
Do not create a second tracker. Use source inspection for routine edits; graph tools
only when available and useful or explicitly required. Check links, commands and
statuses. With a [role manifest](../../../skills/docs-sync/references/document-scaffold.md#optional-role-manifest),
also run the bundled `docs.py stale <repo>` and `docs.py check <repo>` and keep it synchronized.
Its optional repository-type `profile` sets which roles are baseline.

The scaffold's parent-skill references describe document roles, not permission to
start Hermes coordination. Use this adapter for execution rules. Keep actual external
inputs in BLOCKERS.md; internal engineering work belongs in tasks. This skill neither
grants nor removes delivery authority: the repository's `AGENTS.md` governs commit,
integration and push. Saving docs does not authorize implementation, scheduling or
host configuration changes.

Use the [single-pass handoff](../../../skills/shared/PLAN-HANDOFF.md#one-planning-pass-one-handoff):
resume accepted decisions and existing task IDs, investigate only missing evidence,
persist one affected batch, and reuse input-bound checks. Unchanged findings need
no new docs pass. Follow this host adapter for execution authority; the shared
contract does not require Hermes-native tooling on this host.
