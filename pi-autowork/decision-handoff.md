# Decision handoff and recovery

`autowork tasks handoff /absolute/repository` is a read-only recovery report for
answers that appear to have had no effect. It uses the same validated private-index
snapshot as `tasks commit --dry-run`. It changes no tracked files, real index, refs,
Git object database, task status, grants or service state.

The result includes the complete pending `tasks/` diff, `pending_revision`, existing
`lifecycle` feedback and a `handoff` object. Existing commit previews/results carry
the same handoff object, so hosts do not need their own decision-state inference.
Capabilities advertise `handoff` as a task verb. No new execution action is granted.

The TUI's **Save answer** uses `tasks decide --commit --save-if-detached` (quick-hold
resolution still uses scoped answer-note `field --commit`, with no detached opt-in).
On main/master it commits only the answer and requested section, not unrelated work.
On detached HEAD it saves locally and reports `pending_commit` with saved paths and
`commit: null`, without switching branches or changing refs/index. Reopening shows
the saved answer and pending feedback. If the answer/section matches committed bytes,
no new pending delta or commit is claimed; existing pending edits remain disclosed,
or `clean` is returned when none remain. Plain `--commit` and named non-main
branches still refuse detached/unsupported branch saves respectively.

Normal CLI writes without `--commit` remain local-only. Detached pending success is
not a fallback for hook failures or Git/ref/index uncertainty. A failed commit
retains the local answer and reports failure; use this report before retrying old
pending answers or uncertain commit outcomes. Neither successful saving nor a local
commit proves runner acceptance or grants live authority.

Scoped answer commits reserve the real Git index and HEAD, run the repository's
hooks with the original branch name and effective configuration in an isolated
Git snapshot, then publish using an expected-old-ref update. They refuse branch,
HEAD, target staging or unfinished-operation drift instead of committing an older
tree over another writer's work. Git's files-based ref storage is required; other
backends retain the answer pending with an explicit error. If publication is
uncertain or index installation fails, the prepared `index.lock` is retained and
its path is reported for explicit reconciliation. Do not delete it or retry a
commit blindly: establish process quiescence, the actual branch revision and the
prepared/original index contents before recovering. `tasks handoff` may report a
clean task snapshot even while this index reconciliation is outstanding; it does
not inspect or recover Git lockfiles and is not sufficient recovery evidence.

A committed answer can coexist with a real owner-action wait. In particular,
`ownership = "owner"` forbids unattended execution even after an approval note.
The questions producer labels that condition `owner_action`, repeats the saved
answer as context, and asks for the actual outside action/evidence or an explicit
deferral/cancellation—not another approval or a live grant that cannot transfer
ownership. Reopening the form restores saved direction; it never preaccepts a
runner suggestion or closes/qualifies the task.

## Per-task states

| State | Evidence | Next action |
| --- | --- | --- |
| `answer_required` | Committed Needs-decision task without an established dated deferral | Obtain the actual missing material decision |
| `pending_commit` | Owner-decision notes changed in the validated pending snapshot | Review the exact diff; explicitly commit with its pending revision |
| `pending_edit` | A relevant record changed, but no new answer is proven | Inspect the edit; do not call it consent |
| `committed` | Answer/transition exists in the captured committed store | Inspect normal selection and runner source; do not call it execution |
| `deferred` | Existing dated deferral in committed Needs decision | Preserve the wait; continue independent authorized work |

Rows carry committed and saved sections and record hashes. The handoff's
`workspace` and `committed_revision` identify its captured source. If the committed
store is absent or invalid, `committed_inventory_available` is false and
`baseline_error` explains the missing evidence. A validated pending store can still
repair it through the existing reviewed commit path; no new answer is inferred from
an unavailable baseline. A saved record hash is not a
committed revision. A commit result reports the exact committed snapshot, not any
new edits made by an editor afterwards. Read again for current working-tree state.

## Recovery protocol

1. Read the report before repeating an answer or a failed mutation.
2. If an answer is pending, retain it and review the complete diff. Do not ask the
   same question again merely because committed counts have not changed.
3. With explicit commit authority, use `tasks commit --expect-pending REVISION`.
   Never silently commit unrelated edits; if they are not accepted, leave the
   snapshot pending rather than treating the report as approval. A changed HEAD or
   snapshot refuses the commit and requires a fresh review.
4. Read the handoff again. A successful local commit is not a push or a runner
   acknowledgement. Use `tasks why ID` and source-bound runner observations to
   inspect remaining dependencies, holds, planning refusals or permissions.
5. Preserve live gates. A generic `yes`, or moving a record to Now, cannot grant
   recruitment access, consent, spending, publication or typed live permission.

Invalid pending records fail the read. An unavailable committed baseline with no
valid repair is reported as `lifecycle.state = "unknown"`, never a clean store.
An interrupted task transaction refuses `handoff` and `commit --dry-run` without
recovering tracked bytes or removing its journal; use explicit recovery separately.
No handoff state can admit a task, close it or clear a hold. Committed membership
and count buckets remain pinned to the committed store, even when an answer waits
in the working tree.

Offline regression tests exercise unanswered → saved → committed → deferred,
stale-review refusal, unrelated edits and preservation. They do not prove a
running service has read the new revision or completed the task.
