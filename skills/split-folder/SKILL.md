---
name: split-folder
description: "Split one folder without behavior change."
license: MIT
---

# Split Folder

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Split one named directory into responsibility-based subfolders. Three words carry the
work: a **move-only** slice changes paths and imports and nothing else; a **seam** is
the public entrypoint whose behavior must keep working; **topology** is the layout you
choose and can defend. Read the [host and authority adaptations](../shared/PI-TOOLSET.md)
and the pinned [folder-refactor protocol](upstream/PROTOCOL.md); these local rules win
where they differ.

## Gate: one check first

Find one command that already passes on the current tree and exercises the moved code.
Without it, add a focused behavior check at the nearest seam, run it green, and only
then move files. No check, no move: a refactor you cannot verify is a guess with better
file names. When no correct seam exists, stop the slice and report the gap.

## Copy the topology that is already there

Read the repository's own convention before naming a folder: bucket folders with an
index README, feature folders, a flat list, or a router command that maps paths. Follow
it. Inventing a second convention is the failure this skill exists to prevent, and a
project with an index, README table, router command or docs page that names the path
has one more file in the refactor: that map.

## Steps

1. **Map the move.** List files, exported symbols, package boundaries, external
   callers, tests, fixtures and generated files. List cross-folder callers from a local
   code graph when one exists, record its
   [declared graph state](../shared/COMMON-CONTRACT.md#graph-state), then confirm each
   caller in source. Name what must keep working: import paths, package exports,
   CLI/API routes and observable output.
   **Pass when:** you can list every caller outside the folder and the check that
   covers them.
2. **Choose the topology.** One responsibility per subfolder, named for the domain
   rather than the file type; the project's naming wins over yours; dependency
   direction stays sane with core logic free of transport and framework detail.
   **Pass when:** each new folder states what it owns, what it exposes and what it
   stays ignorant of.
3. **Move only.** Move files, fix paths and imports, and update the maps named above.
   Symbols, logic, helpers and compatibility facades stay as they are.
   **Pass when:** the same check passes, and the diff holds no rename, rewrite or
   extraction.
4. **Extract proven duplication.** Share a helper only when at least two call sites
   need identical semantics, the responsibility is clear and the check covers it.
   Keep similar-looking code apart until the evidence says otherwise.
   **Pass when:** each shared module has two named callers and the check still passes.
5. **Update the map.** Every index, README table, router entry, import path and docs
   link that names an old path points at the new one.
   **Pass when:** a search for the old path finds only history and release notes.
6. **Clean up last.** Remove a shim or dead file only after callers and the check prove
   it is safe, then verify again.
   **Pass when:** the check passes and nothing imports the removed path.

## Example

`src/parser/` holds 14 files and no subfolders. The check is
`pytest tests/test_parser.py`. One move-only slice creates `src/parser/lex/` and
`src/parser/ast/`, moves six files, updates eight imports and the `src/parser/README.md`
table; the check passes before and after. Extraction and the remaining root files are
later slices, reported as a checkpoint rather than a finished refactor.

## Limits

Use the user's slice limit, budget or pause as the stop line, and mark a verified slice
as a checkpoint, not a finished topology. Treat a repository-root split as high risk
and obtain explicit scope first. When no folder is named, ask for the boundary or run
read-only discovery when the request allows it. Use native tools: no `folder_refactor_*`
tool is required, and state belongs in the existing task receipt.

**Completion audit:** reread the tree from disk and classify every remaining root file
by exact basename: public facade or compatibility file, intentionally out of scope, or
next move or extraction candidate. An unclassified file or a remaining candidate means
the target is incomplete.

**Receipt:** target; planned and actual topology; moves; shared-code decision;
compatibility; checks and review; root-file classifications; completion state; next
slice or stop reason.

## Boundaries

- Not behavior changes, renames or deletions; use `/unused-code` for removal.
- Not an architecture review or a deep-module redesign; use
  `/improve-codebase-architecture`.
- Not multi-lane repository improvement; use `/autonomous-codebase-improver`.

**Done when:** the same check passes after a move-only diff that updates every map, and
each remaining root file is classified or named as the next slice.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).
