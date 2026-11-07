# Installed Pi RPC delivery pilot requirements

Status: proposed, no pilot authority. A future pilot requires a new owner task
with an explicit target, bounded model use and interruption window; live remains
denied until then. This is not an executed result or fleet qualification.
Coordinator steering remains gated on this pilot; source integration alone cannot
release it. Completed task reports and observed fleet snapshots live in Git history.

## Current evidence boundary

Read back actual selected release, resolved SDK/Pi executables and transport for the
owned target. Selected release and configured next-invocation transport are not
execution proof. Existing workers can retain older releases across coordinator
reload. Use the [qualification boundaries](pi-rpc-qualification-2026-10-24.md)
to distinguish fake-peer, native-offline, real-model and installed-engine evidence.

## Proposed target and authorization

Prefer **one new disposable standalone repository**, with no Git remotes,
production configuration or existing task state, using the installed release's
supported foreground `--until-empty --workers 1` runner. Its task worktrees belong
under that repository's own canonical `.worktrees/`. Use an isolated private state
root and explicitly select the existing pinned SDK interpreter; do not install,
modify or restart existing services. This qualifies the installed
CLI/engine path, not systemd rollout or fleet acceptance.

The owner decision must name the exact private target/state paths, executor,
window, maximum model-run/time budget and permission for the controlled
interruptions below. Proposed ceiling: four worker/reviewer case pairs (normal
RPC, recovery RPC and matched JSON controls), with no extra fallback/model runs
without a recorded budget decision. If the owner instead chooses an existing
service, obtain its actual writer handoff and preserve all work/attempts first;
the disposable-target proposal does not authorize interrupting that service.

## Preconditions and frozen manifest

1. The selected integrated runtime has genuine independent acceptance and its exact
   revision passes the required offline gate. Preserve the raw full-check result,
   command, exit code, revision/tree, skips and expected failures. An in-progress
   check or pass on an earlier revision is not a substitute. Reuse an already
   running matching check rather than launching a competing duplicate.
2. Pin the installed release selected for the pilot. Record resolved entrypoints,
   source tree, effective transport, Pi executable/version, SDK executable/version,
   model and relevant safe settings. Recheck readiness without a model call.
3. For this target only, require `PI_AUTOWORK_PUSH=0`,
   `PI_AUTOWORK_STEERING=0`, review/validation enabled, optimistic integration off,
   bounded runtime/retries and updates disabled through the supported
   `PI_AUTOWORK_UPDATE_INTERVAL=0` setting. Verify effective settings after saved
   repository configuration is applied. Do not change global/fleet settings.
4. Freeze a small deterministic engineering task, checks and exclusions, including
   observable work markers and an independent reviewer. Record baseline, contract
   hash and expected files before admission; a prompt-only echo is insufficient.
   Model transport is the only intended remote use; no deployment, data services,
   publication, protected corpus or credential modification.

## Required cases

### Normal installed-engine closure

Use the real installed launcher, engine, worker and independent reviewer. Capture
admission, slot/attempt ID, worker report/candidate, reviewer identity and session,
checks, integration commit and native closure receipt. Correlate the actual RPC
process/progress and completed run metadata to that attempt. Require SDK/Pi pins,
settlement and complete cleanup evidence; task/model prose is not a receipt.
The task must reach verified closure through the engine, not manual `tasks done`.

### Interrupted-attempt recovery

First establish exact ownership and process birth identities for this disposable
coordinator and its accepted worker. At an observable bounded checkpoint, record
the slot, session, task/contract hash, worker identity, partial work and descendant
ownership. Interrupt only the authorized pilot coordinator through the supported
lifecycle; a crash case requires separate explicit permission for the precise
owned process and failure window. Never kill an unrelated worker or guard.

Restart only the same pilot against the same state. Verify engine reconciliation
adopts the existing live worker where applicable, preserves the accepted attempt,
partial work and session, and creates no competing worker or duplicate task
execution. Correlate receipts rather than merely counting process starts. If the
worker was aborted, acceptance is uncertain or cleanup unproven, the correct
result is a retained technical hold—not forced retry or a switch to JSON.
Record that limit honestly; do not call a held run recovered completion.

### Matched JSON comparison

Only after RPC processes are settled and cleanup proven, use fresh equivalent
baseline/contract/session cases with explicit JSON selection. Never replay the
RPC accepted session in JSON. Keep model, task complexity, checks, reviewer and
budget comparable. If a safe matching recovery case cannot be run, mark that
comparison missing rather than altering the failure scenario to get a pass.

## Evidence, abort and exit criteria

Keep raw histories, prompts, process identities and private state outside Git.
Publish only sanitized revision-bound evidence: complete engine chain, independent
review, exact checks, recovery/duplicate-dispatch observations, cleanup, wall time,
startup/tool/recovery latency, retry/intervention counts and quality coverage.
Separate partial token subtotals from complete totals; unknown billed spend stays
unknown. Four small cases cannot establish fleet reliability or performance gains.

On contract drift, unexpected side effect, budget exhaustion, duplicate ownership,
uncertain acceptance or missing cleanup proof, stop new admissions, retain all
artifacts and report the exact failure. Do not erase attempts, clear holds, weaken
checks or enable JSON automatically. Explicit rollback is for a future invocation
only after reconciliation and proven cleanup.

Close any future installed-pilot task only when its acceptance is actually covered,
with missing measurements or live evidence explicitly remaining open. Then, and only
then, admit the separate control-channel implementation. Automatic steering remains
off until its separate bounded policy/channel qualification succeeds.
