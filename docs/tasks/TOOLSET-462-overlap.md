# TOOLSET-462 overlap disposition

## Evidence

- [TOOLSET-462-9f8caaab](../../tasks/items/TOOLSET-462-9f8caaab.md) names
  `pi-autowork/README.md`; together with unfinished
  [TOOLSET-442-6c1f2ab0](../../tasks/items/TOOLSET-442-6c1f2ab0.md),
  [TOOLSET-459-d9214062](../../tasks/items/TOOLSET-459-d9214062.md) and
  [TOOLSET-460-c838ac54](../../tasks/items/TOOLSET-460-c838ac54.md) the file is a hot
  literal path (four unfinished tasks), so the scheduler holds it with
  `waits for TOOLSET-442-6c1f2ab0 (shares hot file pi-autowork/README.md)`, 442 being
  the first README sharer in `Next` order.
- `pi-autowork/README.md` is a real output for TOOLSET-462, not an over-declaration: the
  task changes the deliberate-stop/restart authority and the effective `PI_AUTOWORK_PUSH`
  binding, which the README documents in the command table (`autowork stop`,
  `autowork restart`), the "Stopping and recovery" section and the publication opt-in
  section; `docs/cross-host.md` documents the same behaviour. Removing README would
  narrow a genuine output, which
  [`skills/shared/PLANNING-CRAFT.md`](../../skills/shared/PLANNING-CRAFT.md) forbids.
- There is no producer/consumer seam between TOOLSET-442 (bounded janitor state) and
  TOOLSET-462 (verified-release publication authority); their subjects and Touches are
  disjoint, so no `depends_on` edge is evidence-backed. The wait is file admission on
  unlanded work, exactly the serialization the scheduler intends, not a product
  prerequisite.
- TOOLSET-462 listed `CHANGELOG.md`, which
  [`skills/shared/PLANNING-CRAFT.md`](../../skills/shared/PLANNING-CRAFT.md) forbids: "Never
  list the coordinator's files: `tasks/`, `BLOCKERS.md`, `TODO.archive.md`, `CHANGELOG.md`."
  `parallel_dispatch.COORDINATOR_FILES` and the worker prompt repeat the prohibition, and
  `parallel_integrate.changelog_entry` composes the entry from the worker report's
  `changelog` field, not from `Touches`. This was a genuine over-declaration, corrected as
  the same defect already was for TOOLSET-459 and TOOLSET-460 in `3dc82d62`.

## Disposition

Remove `CHANGELOG.md` from TOOLSET-462 `Touches`; leave every Scope, Acceptance, Check,
Dependency, section and authorization unchanged. Leave the `pi-autowork/README.md` wait
intact: it is a source-backed shared output held by unlanded work, not a product
prerequisite, and the maintainer instruction forbids inventing a dependency or narrowing a
genuine `Touches` entry for overlap alone. No dependency was added, no task was merged,
split, superseded, closed or qualified, and no owner decision or missing proof was
invented.
