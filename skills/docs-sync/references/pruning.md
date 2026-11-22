# Legacy record preservation

Docs Sync maintains GitHub issue handoffs,
not a local executable queue. Bare, tasks and audit modes do not delete preserved
legacy task records, receipts, attempts, worktrees or recovery state.

Any later pruning requires a separately scoped, reviewed reconciliation mechanism.
Do not hand-edit preserved records or reinstall the removed CLI as a substitute.
First establish actual ownership, integrated closure, surviving consumers, verified
dependency proof and immutable source evidence. Keep goal status and owner/live
gates unchanged. Unknown ownership or missing proof means retain, not empty.

The [prior retention criteria](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/skills/docs-sync/references/pruning.md)
remain evidence for reconciliation. They are not a completed-task archive or proof
that an obligation is satisfied. Follow [Plan Handoff](../../shared/PLAN-HANDOFF.md).
