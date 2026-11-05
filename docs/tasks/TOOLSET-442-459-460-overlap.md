# TOOLSET-442 / TOOLSET-459 / TOOLSET-460 overlap disposition

## Evidence

- [TOOLSET-442-6c1f2ab0](../../tasks/items/TOOLSET-442-6c1f2ab0.md),
  [TOOLSET-459-d9214062](../../tasks/items/TOOLSET-459-d9214062.md) and
  [TOOLSET-460-c838ac54](../../tasks/items/TOOLSET-460-c838ac54.md) each name
  `pi-autowork/README.md`; together with running
  [TOOLSET-453-525f9994](../../tasks/items/TOOLSET-453-525f9994.md) the file is a hot
  literal path (four unfinished tasks), so each waits with
  `waits for TOOLSET-453-525f9994 (shares hot file pi-autowork/README.md)`.
- `pi-autowork/README.md` is a real output for all three, not an over-declaration. The
  retained-attempt-files section documents the janitor's sweep that TOOLSET-442 extends
  (`pi-autowork/README.md#retained-attempt-files`); the session-merge-recovery section is
  the documented home for TOOLSET-459's integration-worktree recovery; the command/hold
  documentation is where TOOLSET-460's bounded requeue is described. `PLANNING-CRAFT.md`
  requires each task piece to own its docs, so removing README would narrow a genuine
  output rather than drop a scheduling over-declaration.
- TOOLSET-453 is currently running: its private slot exists with a live worker PID, so the
  file gate is a wait on unlanded work, not on a held or idle peer. TOOLSET-442, 459 and
  460 have no slot, no live worker and no retained candidate, so the gate clears itself
  when TOOLSET-453 lands and the three then serialize on README as the scheduler intends.
- TOOLSET-459 and TOOLSET-460 listed `CHANGELOG.md`, which
  [`skills/shared/PLANNING-CRAFT.md`](../../skills/shared/PLANNING-CRAFT.md) forbids: "Never
  list the coordinator's files: `tasks/`, `BLOCKERS.md`, `TODO.archive.md`, `CHANGELOG.md`."
  `parallel_dispatch.COORDINATOR_FILES` and the worker prompt repeat the prohibition, and
  `parallel_integrate.changelog_entry` composes the entry from the worker report's
  `changelog` field, not from `Touches`. This was a genuine over-declaration and was
  corrected.

## Disposition

Remove `CHANGELOG.md` from TOOLSET-459 and TOOLSET-460 `Touches`; leave every Scope,
Acceptance, Check, Dependency, section and authorization unchanged. Leave the README
waits intact: they are a source-backed shared output held by running TOOLSET-453, not a
product prerequisite, and the maintainer instruction forbids inventing a dependency or
narrowing a genuine Touches entry for overlap alone. No dependency was added, no task was
merged, split, superseded, closed or qualified, and no owner decision or missing proof was
invented.
