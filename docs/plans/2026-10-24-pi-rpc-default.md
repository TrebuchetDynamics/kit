# Pi RPC default runtime implementation

## Accepted intent

The owner explicitly requests RPC now and by default, using pi-agent-python-sdk,
not another design-only experiment. Preserve task/attempt/contract authority,
independent review, checks, Git integration, receipts and publication policy.
Automatic steering remains off until qualified; do not restart other runners.
The full mission includes live-model qualification and measurement, which must not
be inferred from deterministic fixture execution.

## Current source and ownership

Use the [runtime guide](../pi-rpc.md) for current pins and source ownership.
Refresh actual worker/session activity before modifying runtime contracts. Preserve
recovery classification and complete accounting requirements; selected source or
configuration alone is not execution evidence. Historical implementation stages
and qualification reports live in Git history, not this plan.

## Architecture decision

Keep `pi_runtime.job` as the sole model-selection/retry/accounting policy seam.
All worker, reviewer and auxiliary invocations pass through it. `run_pi` defaults
to RPC; `PI_AUTOWORK_TRANSPORT=json` is explicit rollback only, never automatic
replay after uncertain acceptance. Read-only CLI imports remain stdlib-only.

A synchronous engine caller invokes a bounded SDK-host subprocess using the pinned
Python environment. The host runs AsyncPiClient with one process/session for that
attempt invocation. This avoids introducing an event loop into the synchronous
coordinator or depending on its interpreter having the SDK. The OS guard wraps the
SDK host and owns/reaps Pi and tool descendants; it uses Linux process identities,
subreaping and parent-death handling. No SDK private fields or custom JSONL protocol.

`RunSpec` pins session, role, working directory, prompt contents/digest, model,
timeout and allowed arguments/environment. Startup @file prompts are explicitly
expanded before RPC submission, with bounded file sizes. Worker sessions retain
existing engine-derived IDs; reviewers retain separate IDs and exclude MCP.
A per-session file lock prevents simultaneous owners. Compact progress files in
private runtime state are projections, not a new execution journal or scheduler.

`EventProjection` consumes events as they arrive with bounded memory, preserving
settlement, tool lifecycle, retries/compaction, final assistant text and known usage.
No raw text/thinking/tool arguments enter progress. Unknown metadata is not authority.
Slow progress persistence is coalesced outside SDK delivery; critical event overflow
fails closed. The SDK retains its native queue bounds and run ownership rules.

Uncertain acceptance, protocol/overflow failures and missing cleanup evidence are
terminal technical outcomes for this invocation, not automatic job retries.
Confirmed settled provider failures may use existing bounded fallback only after
the process guard proves cleanup. No runtime event closes an engineering task.
Control methods query state, clear/abort and accept only engine-pinned, bounded
technical steering; no arbitrary LLM-generated authorization. Reviewer steering
is forbidden. Intervention records belong to the attempt and require freshness.

## Required verification and remaining qualification

Preserve process-guard, event-projection, immutable-spec, per-session ownership,
cleanup, version-pin and independent-review regression coverage. Native offline
fixtures remain separate from real-model and installed-engine acceptance.

Installed-runner/interrupted-attempt qualification and matched real-task measurement
remain outstanding; no blanket fleet restart is authorized. A future pilot requires
a new explicitly owner-approved task and bounded target/model/interruption authority.
Production coordinator control-channel/policy qualification remains gated on that
pilot. Automatic steering remains off until separately qualified.

Tests precede behavioral changes. Run proportional affected checks and preserve
required final acceptance gates. No production savings, model quality or fleet
activation claim follows from offline passes or selection-only output.
