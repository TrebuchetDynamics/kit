# Verified architecture fixes

Load this branch only when the caller explicitly authorizes fixes, patches or
optimization. `/autowork` owns implementation, task records, review and closure;
this reference supplies architecture-specific acceptance, not another executor.

1. **Bound the candidate.** Select the highest-severity source-confirmed finding
   within the granted scope. State the affected interface, callers, intended behavior,
   exclusions and acceptance check in the existing task contract. Preserve unrelated
   dirty work. A cross-scope migration or unresolved ADR conflict stays pending.
2. **Establish the baseline.** For a bug, run a focused regression check against the
   original code and confirm it fails for the claimed reason. If execution is blocked,
   report the blocker; do not claim a verified repair. For performance, record the
   command, workload, environment and repeated baseline measurements. Set the target
   metric and tolerated regressions before editing. Keep synthetic and live load
   claims separate. Structural changes need interface-level behavior checks and a
   concrete deletion-test result, not an invented speed target.
3. **Fix the root cause.** Inspect every caller, reuse the existing owner and choose
   the smallest complete change. Remove unnecessary indirection when the evidence
   supports it; update callers, exports, fixtures and docs together. Verify dynamic
   usage through `/unused-code` before deleting apparently unreachable code. Preserve
   validation, error handling, security, accessibility and public compatibility.
4. **Prove the result.** Run the regression check again and the affected tests. For
   speed changes, repeat the same workload under comparable conditions and report
   before/after values and variability; retain no optimization justified only by noise.
   Check edge cases and expected-load failures along the changed seam. A behavior
   regression blocks completion even if the speed target passes.
5. **Review and close.** Load `/ponytail-review` in Autowork's existing review lane:
   correctness, safety, expected load, tests, speed, then unnecessary complexity.
   Fix in-scope must-fix findings and rerun affected checks. This read-only review
   does not itself apply patches or grant delivery authority. Reuse the required
   reviewer rather than spawning an extra one; any dispatched reviewer starts fresh
   with an explicit read-only scope and completion criterion. Close only under the
   shared Definition of Done. Report exact checks, measured results, residual risks,
   pending candidates, and local commit/integration/push states separately.
