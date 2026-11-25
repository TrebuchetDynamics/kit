# Standing decision policy

> GitHub Issues are the only executable backlog and Orbi owns delivery, with all
> issues defaulting to `ai-ready` regardless of author. The scope, exclusion,
> human-only and evidence limits below remain. Use
> [GitHub-native publication and delivery](github-native.md) and preserve explicit pauses.

Status: owner-approved. This policy applies to this repository and to workspaces
whose owner explicitly adopts it. Approval of implementation delegates execution
of the approved scope, not just preparation of a plan. Retained fix/apply modes
keep their accepted scope, ownership, review and PR gates. Planning still stops
after publication and grants no service activation. Use an [explicit Orbi lifecycle
command](github-native.md#kit-lifecycle-skill) for activation. The removed executor
must not be restored.

## Approved work has full delegated authority

Explicitly approved implementation in this repository is fully authorized for
its accepted scope. The owner's standing execution grant covers selected accepted
tasks and bounded engineering prerequisites within the accepted direction, not
unaccepted product strategies. No second execution approval is required.

The grant includes model execution and its ordinary usage cost, isolated test
targets and routine live qualification needed by the task, in addition to the
implementation and delivery actions below. The coordinator chooses available
configured providers and disposable targets within scope. Missing credentials,
real external inputs and explicit caller limits remain limitations, not reasons
to repeat an already-settled authorization question. Standalone planning, interviews
and read-only requests keep their own non-execution boundaries.

Approved implementation may take the actions needed to complete its accepted scope
without another owner approval. This includes implementation, environment repair,
testing, integration, publication and live operations when they are necessary to
the approved outcome. The coordinator chooses implementation details and resolves
in-scope decisions rather than sending them back to the owner.

An `ownership = "owner"` label or missing recorded live authorization is not, by
itself, a reason to ask again when this standing approval covers the action.
Reconcile those records from the approval and continue. Do not confuse a stale
label with an explicit instruction that a human must personally perform an action.

Full delegated authority is not unlimited capability or permission outside the
approved scope. Explicit exclusions, pauses, revocations, human-only requirements,
access controls and higher-priority instructions still apply. Do not invent
credentials, signatures, external participants or successful execution. A new goal,
changed acceptance or unrelated action needs its own authority. The presence of a
task in Now/Next is not itself evidence of owner approval or adoption of this policy.

## Record approval once, then execute

1. Read the approved task, its sources, the standing policy and any narrower
   instructions. Identify the actual operation and target covered by approval.
2. Inspect fresh task status and actual worker/session ownership. Do not change a
   running contract or overlap another writer.
3. Reconcile stale ownership/authority bookkeeping in the current GitHub issue
   from actual approval evidence. Preserve scope, acceptance, checks, native
   dependencies and explicit exclusions. Never edit a live worker's contract or
   use the removed task CLI to modify preserved legacy records.
4. For live work, record the actual approval's actor, date and exact target/scope.
   Cite this policy and its owner adoption; do not invent evidence or grant
   yourself authority. A note or readiness label is not a human-only acceptance.
5. Read back the issue, dependencies and actual ownership. Follow supported
   GitHub/Orbi gates; a prose policy bypasses no runtime checks or explicit pause.
6. Execute and verify the approved work. Report actual implementation, integration,
   publication and live qualification separately. Approval is never completion
   evidence and does not waive required checks or independent review.

## Resolve blockers without stopping independent work

Before asking the owner, distinguish missing authority from missing bookkeeping.
Apply existing approval instead of repeating a permission question. Fix an in-scope
technical blocker, choose another valid approach, or produce the missing input.

If an external input is genuinely unavailable, record exactly what is missing and
what was attempted. Keep the affected obligation open and continue independent
approved work. A human-only action may block its dependents, not the whole queue.
Do not repeatedly report an unchanged blocker or manufacture busywork when no
independent work remains.

A check that stops its own service needs execution outside the runner being stopped.
That is an executor/context requirement, not missing authorization. An authorized
external coordinator performs it; do not remove the exclusion, dispatch it inside
the service it must stop, or ask the owner to approve it again. A physical action
or credential that no authorized executor can supply remains a specific input gap.
Shared-resource waits, active writers, required review and source-freshness checks
are execution constraints; full authority does not make them completed or available.

## Evidence and change control

Only the owner changes the scope of this standing delegation. A coordinator may
record and apply it, but cannot override explicit exclusions or manufacture owner
attestations. Do not create an `owner_waiver` or `owner_qualification` from a planner
call. Preserve verified-dependency proof, real tool approval requests and actual
completion requirements. Never route around an access-control denial through a
new tool, session or credential.

This is an execution policy, not proof that a runner consumed it or that a task
completed. GitHub readiness, runtime pickup, checks, review, merge and live
acceptance remain distinct observed outcomes.
