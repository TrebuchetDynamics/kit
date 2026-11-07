# Pi harness integration requirements

Current architecture, pins, installation and explicit rollback are in
[the runtime guide](../pi-rpc.md); evidence boundaries are in
[RPC qualification](pi-rpc-qualification-2026-10-24.md).
Completed audits, implementation slices and test reports remain in Git history.
The default is RPC; this page does not restore the earlier JSON-baseline proposal.

## Ownership and lifecycle

Retain the existing engine attempt, task contract, model/retry policy and independent
review sessions. Transport events and model statements do not close tasks or supply
publication authority. One client/session has one run owner. ACK, agent-end and
settlement are different observations; observation timeout alone is not confirmed
cancellation or proof of cleanup.

Pin the SDK/Pi contract and requalify changes through actual public seams. Descendant
cleanup is a composed obligation, not a consequence of terminating only the direct
SDK child. Test ordinary and escaped descendants, PID reuse/parent identity, crash
recovery and no duplicate dispatch. Preserve uncertain-acceptance fences and partial
results. Automatic JSON fallback after uncertain RPC acceptance is forbidden.

Bound queues, callback work and progress persistence. Progress is a projection with
provenance, not a second execution journal or scheduler. Never publish raw thinking,
arguments, private session data or credentials as progress. Preserve settlement,
retry/compaction and partial-accounting distinctions. Assistant/catalog usage is not
complete invocation usage or billed spend; absent data stays unknown.

## Native contract and limits

The opt-in installed-Pi fixtures use the real launcher/runtime and deterministic
offline provider. Explicitly select the installed executable for direct native tests;
the ordinary checker strips `AUTOWORK_*` and optional skips do not qualify native
execution. Preserve settlement/partial-output, session separation, tool allowlist and
cleanup guards without inferring semantic recall, production ID generation or OS
containment from them.

Only separately authorized installed/live cases establish real engine closure,
interrupted-attempt reconciliation and matched engineering performance. Keep source,
model, contract, reviewer/check coverage and measurement windows comparable. Native
fixtures and instruction guards supply no measured stall reduction or model-adherence
claim. Steering/control and stronger process containment retain their separate gates.
No model use, installation, service operation, upstream Hermes modification or
publication is authorized by this document.
