# Native source layout and maintainability contract

## SDD maintainability refactor

The executor is removed. Native Hermes implementation remains under
`src/kit_runtime/`, with `src/kit_bootstrap.py` and thin public
`scripts/` entrypoints. Preserve selected-source identity, packaged resources,
native plugin registration and unrelated host functionality.

### Layout and source-loading contract

- Load the selected tree's bootstrap and source, never a foreign cwd, installation,
  site-package or cached module as a fallback.
- Preserve supported native command interfaces, profile settings and private state.
- Keep public entrypoints with their same-release payload; copying one entrypoint
  is not a standalone installation.
- Keep source checks distinct from installed host/model, gateway and live delivery
  qualification. A directory move or deletion proves none of those outcomes.
- Preserve existing task records, worktrees, attempts and recovery evidence.

The [original source-layout requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/structural-audit-2026-10.md)
retain remaining proof and historical executor-specific contracts. Reconcile any
still-required outcome into GitHub Issues; do not restore the removed source or
mark unmet qualification complete. Orbi remains paused and live-unqualified.
