# Git object retention safety

## Required safety boundary

Task-store validation uses disposable objects outside the repository object database.
That implementation does not establish that existing unreachable objects are safe
to delete. Git history retains earlier inspection results; this page is not an
object inventory, completed-task report or cleanup authorization.

Before GC, pruning, repacking, ref deletion or automatic-GC re-enablement, reconcile
all retained worker candidates and recovery artifacts against a fresh ref inventory.
Ref membership, reflog-only reachability, missing objects and unknown coverage are
different states. A clean checkout, old timestamp, commit subject or successful
`git fsck` does not prove a candidate is disposable. A reflog is not durable
ref-backed preservation; missing candidates require explicit reconciliation.

## Remaining qualification

Refresh actual worker/worktree activity and source/candidate ownership, including
private slots, previous attempts, reports, set-aside/checkpoint/archive refs and
non-JSON or external recovery artifacts. Do not assume every candidate is recorded
in one JSON inventory. Preserve concurrent writers, dirty and unmerged work,
locked worktrees and uncertain partial effects. Never rewrite runtime records to
hide missing evidence.

Read-only inspection may use `git count-objects`, `git fsck`, `git for-each-ref`,
`git rev-list --all`, reflog-inclusive reachability and `git cat-file`; it must not
silently run GC or mutate refs/settings. Object existence is not ref reachability.
Metadata/proof operations can leave objects after interrupted publication; no source
inspection alone proves their contents have no recovery value.

The [TaskStore reference](../../pi-autowork/task-store.md) owns validation isolation.
Use supported coordinator/closeout paths for any separately authorized retention
repair. Documentation cleanup authorizes no object deletion, history rewrite,
`gc.log` removal or automatic GC setting change. Required candidate-retention
qualification remains unresolved until actual source-bound proof is available.
