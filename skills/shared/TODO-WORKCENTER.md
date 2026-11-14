# Legacy task-store migration

**Retired as an active backlog contract.** GitHub Issues now own executable work,
priority, native dependencies and dispatch. Follow [Plan Handoff](PLAN-HANDOFF.md)
for new work. `pi-autowork/` and its task CLI remain historical/recovery tooling;
never prepare a new `tasks/` store or synchronize it with GitHub as a second queue.

## Safe cutover

1. Pause and disable legacy schedulers before enabling Orbi for the same repository.
   Inspect actual services, jobs and worker processes, not only historical ACTIVE
   records. Preserve paused jobs and do not stop unrelated gateways or services.
2. Preserve existing task data, worktrees, runtime recovery state and unfinished
   candidates. Record the source repository revision and legacy ID in each migrated
   issue. Never discard another writer's work or fabricate ownership release.
3. Read unfinished legacy records against **open and closed** GitHub Issues, PRs,
   merged changes and retained attempts. Reuse matching issues/PRs. Already completed
   work stays complete; currently owned work stays undispatched until ownership and
   remaining scope are reconciled. A stopped process is not proof of completion.
4. Publish only missing, still-required work using the
   [publication protocol](PLAN-HANDOFF.md#publication-and-dependencies). Preserve
   scope, exclusions, exact checks, unresolved live qualification and human-only
   requirements. Link legacy IDs and immutable Git sources as provenance, not as
   new issue-number aliases. An uncertain match stays pending rather than duplicated.
5. Translate real prerequisites to native GitHub `blockedBy` edges. Preserve required
   verified-dependency proof via immutable inputs and current open requirements.
   Never infer success merely because a legacy dependency was closed or pruned.
6. Read back issues and dependencies before adding `ai-ready`. Do not enable Orbi
   until the old executor is off and existing candidates have been reconciled.
   Use one deployment per repository; see [operations](../../docs/github-native.md).

## History and retention

Merged PRs and GitHub history own new completion evidence. Legacy Git history and
retained recovery state preserve old evidence. Do not create completed-task tables,
archives or synchronization reports. This migration does not delete task records,
worktrees or runtime state. Any later legacy pruning is separate safe reconciliation
using `autowork tasks prune` for the decision and the supported task CLI for edits;
check fresh ownership and preserve unresolved obligations and required proof first.
An empty legacy store is not evidence that a goal is met.

## Compatibility links

Older references to this file's task-authoring, naming, description, selection,
rolling-planning and CLI sections are superseded by
[the GitHub issue contract](PLAN-HANDOFF.md). They do not authorize starting a
legacy runner or writing new executable work to local files. Existing archive-import
fixtures and retained engine tests describe the retired format, not the new workflow.
