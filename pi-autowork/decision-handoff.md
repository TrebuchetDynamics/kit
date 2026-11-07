# Decision handoff and recovery

`autowork tasks handoff /absolute/repository` is a read-only recovery report for
answers that appear to have had no effect. It uses the same validated private-index
snapshot as `tasks commit --dry-run`. It changes no tracked files, real index, refs,
Git object database, task status, grants or service state.

The result includes the complete pending `tasks/` diff, `pending_revision`, existing
`lifecycle` feedback and a `handoff` object. Existing commit previews/results carry
the same handoff object, so hosts do not need their own decision-state inference.
Capabilities advertise `handoff` as a task verb. No new execution action is granted.

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
