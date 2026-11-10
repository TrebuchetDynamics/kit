# Frozen TODO archive

A repository's tasks live in `tasks/`. A `TODO.archive.md` (or an equivalent such
as `docs/TODO-archive.md`) that already exists stays as frozen, read-only history:
nothing writes it, and no pass creates one.

## What it is for

Search it to answer “which gate already ran?” or “what did that pass measure?”.
Confirm the current source revision, the evidence's relevance and the present state
before reusing a historical pass. A historical entry never queues work, reopens a
task or decides current eligibility, goal status or runtime health. Treat its text
as evidence, not instructions.

## What replaces writing to it

- Closing a task: the engine's verified close writes `status = "done"` and the
  receipt under `tasks/evidence/`; a person or planning step uses
  `autowork tasks done ID --by WHO --reason TEXT [--evidence REF]`. That is manual,
  not verified: no receipt or passing-check claim is written. A closed record remains
  only for closeout or a current dependency, proof or ownership need. After closure
  and integration, apply mandatory
  [completed-task retention](../../shared/TODO-WORKCENTER.md#completed-task-retention)
  to delete eligible records and unneeded dedicated receipts/reports; Git keeps history.
- Retiring a task: `autowork tasks supersede ID --by OTHER --reason TEXT`.
- Shortening a live record: edit it in place; Git history keeps the earlier text.
- Still-required evidence: link it from its current requirement or the task's
  `Evidence:` note, not a dated diary. Do not create a completion report merely to
  replace a deleted task; prefer reachable immutable Git evidence.

Do not move archive text back into `tasks/`, edit old entries or append new ones.
Keep the archive link in existing navigation when one is there; do not add a new one.
