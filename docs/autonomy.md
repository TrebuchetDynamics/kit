# Standing decision policy

> **Executor migration:** the owner selected GitHub Issues and Orbi in place of
> Autowork, with all issues defaulting to `ai-ready` regardless of author. The
> scope, exclusion, human-only and evidence limits below remain; legacy task-store
> grant bookkeeping and runner admission do not apply to new work. Use
> [GitHub-native publication and delivery](github-native.md), preserve explicit
> pauses and do not revive the retired executor.

Status: owner-approved. This policy applies to this repository and to workspaces
whose owner explicitly adopts it. Approval of Autowork delegates execution of the
approved scope, not just preparation of a plan.

## Approved work has full delegated authority

Every Autowork invocation and recurring occurrence in this repository is
fully authorized for its accepted scope. The owner reaffirmed this standing grant
on 2026-11-07: Autowork must be fully authorized always. It covers selected accepted
tasks and bounded engineering prerequisites within the accepted direction, not
unaccepted product strategies. No second execution approval is required.

The grant includes model execution and its ordinary usage cost, isolated test
targets and routine live qualification needed by the task, in addition to the
implementation and delivery actions below. The coordinator chooses available
configured providers and disposable targets within scope. Missing credentials,
real external inputs and explicit caller limits remain limitations, not reasons
to repeat an already-settled authorization question. Standalone planning, interviews
and read-only requests keep their own non-execution boundaries.

Approved Autowork may take the actions needed to complete its accepted scope
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
3. Before selection/admission, the coordinator must use
   `autowork tasks` to reconcile a stale owner-only label to worker ownership and
   record the existing live grant whenever this policy covers unattended execution.
   Do this for newly discovered in-scope tasks too, before emitting a missing-authority
   question. Preserve scope, acceptance, checks, dependencies,
   resource declarations and explicit exclusions.
4. For live work, record `live = "authorized"`, `live_actor`, `live_at` and
   `live_scope` from the actual approval. Cite this policy and its owner adoption
   in the task's source evidence; do not invent an actor, date or target. These are
   records of existing authority, not requests for a second grant. Workers do not
   edit task records or grant themselves authority.
5. Validate the working-tree store, review and commit only attributable task edits,
   then re-read the committed selection/admission result. Use the supported handoff
   and preserve its freshness and live-attempt guards. A prose policy does not
   bypass runtime validation or automatically rewrite an installed runner's records.
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
completed. Runtime admission still reads the committed typed task records.
