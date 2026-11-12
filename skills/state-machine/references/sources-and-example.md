# Sources and worked example

This is a locally authored method, not a vendored skill or an attribution of the
viral prompt. These primary sources were read online on 2026-11-12.
They inform the method; application source and accepted requirements decide its
actual semantics. The workflow works offline without any of these libraries.

## Sources

- [W3C SCXML 1.0, Recommendation, 2015-09-01](https://www.w3.org/TR/2015/REC-scxml-20150901/):
  sections 3.1, 3.5, 3.11 and 3.13 describe states, guards, legal configurations
  and transition selection. This supports explicit predicates and transition
  tables. SCXML execution rules do not automatically apply to application code.
- [Stately: Transitions](https://stately.ai/docs/transitions):
  events, guards, parent-state selection and self-transitions show why status
  changes alone miss behavior. A transition can change data or cause effects
  without changing the finite state. XState is an example, not a dependency.
- [Hypothesis: Stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html):
  action sequences, model comparisons, preconditions and invariants support
  sequence-based verification. Its guidance also notes that simpler tests can
  suffice. A sequential stateful test does not model concurrent execution by itself.

These are design references, not a requirement to convert the app to SCXML,
XState or Hypothesis. No upstream source bytes are copied into this bundle.

## Example: timeout does not mean failure

Assume an accepted order contract says cancellation prevents shipment. Source
shows that dispatch checks the order, calls a carrier, then records shipment.

| Step | Actor | Observed action |
| --- | --- | --- |
| 1 | Dispatch worker | Reads `paid`; a local guard permits dispatch. |
| 2 | Carrier | Accepts shipment; its response is delayed. |
| 3 | Cancellation handler | Still reads `paid`; records `cancelled`. |
| 4 | Dispatch worker | Receives success; writes `shipped` without rechecking. |

The counterexample is not just `cancelled → shipped`. It includes a remote effect
that a database transaction cannot roll back. Verify the actual cancellation
contract, carrier semantics, conditional writes and compensation before reporting
a defect. A product may intentionally make cancellation unavailable after dispatch
starts.

A bounded test can pause the carrier response, invoke cancellation and resume the
worker. Assert the agreed outcome and effect count, not only the final status.
A second distinct risk is retrying the carrier call after a timeout: inspect the
idempotency key and its scope before claiming duplicate shipment is possible.
Use fakes for this experiment unless live execution has separate authorization.

If repair is authorized, compare a shared transition guard, an atomic dispatch
claim and the existing recovery mechanism. A new state-machine framework is not
automatically the smallest fix.
