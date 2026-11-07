# Test-suite optimization contract

Current testing requirements are in [testing](testing.md); the reusable
[optimization protocol](../skills/engineering/local/test-suite-optimization/PROTOCOL.md)
owns the inspection method. Completed audits, task dispositions, coverage tables,
fixture timings and execution reports live in Git history, not this document.

## Suite thinning plan (2026-10-16)

The accepted objective is fewer unnecessary executions, lighter fixtures and less
wording-coupled maintenance without reducing defect detection. There is no target
test count, reduction percentage or invented latency SLA. Current Python inventory
comes from [the checker](../scripts/check.py); JavaScript gates come from [CI](../.github/workflows/test.yml).
Native/model/integration exclusions stay explicit and must not be silently removed.

### Acceptance and safety

Every removal must map to retained behavior or an explicit non-executable obligation.
Preserve unique branches, named regressions, authorization, privacy, data preservation,
composed handoffs, process/Git boundaries and refusal/recovery checks. Equal line
coverage, shared fixture setup or a large file proves no behavioral duplication.
Prose-only assertions may be replaced only after identifying the real consumed
metadata, routing, link, package, authorization or security obligation.

Keep distinct case labels and fresh mutable repositories, environment and process
state when parametrizing. Share immutable inputs only when justified. Do not add a
test-only production hook, weaken assertions, hide failures behind skips, raise a
timeout to manufacture success or replace all subprocesses/clocks with mocks.
A shorter sleep is not proof of a later-cycle or escaped-child cleanup oracle.

### Method and limits

Read current bodies/helpers before acting; historical equivalence cannot authorize
a present deletion. Select small behavior-owned batches with a concrete public
seam and a negative change the retained assertion detects. Repeated collection,
fixture orchestration and phrase matching are leads, not removal verdicts.

For focused before/after coverage, measure lines and branches, propagate unittest
caller contexts to child processes, verify nested sources and keep coverage data
off `sys.path`. Text/shell checks, copied source, isolated environments, alternate
interpreters, killed descendants and non-Python processes remain blind spots.
Instrumentation can change behavior: a later uninstrumented pass does not turn a
failed instrumented run green. No mandatory coverage or mutation dependency is added.
Instruction tests do not prove agent compliance or live delivery.

### Execution and verification

Preserve existing owners and unfinished work. Apply one bounded authorized change,
inspect it and run its affected checks; retain normal Python/Node acceptance gates.
Reuse a passing receipt only with matching source and execution inputs. Do not rerun
whole suites for each prose edit, or treat an advisory selector as an executed gate.

Failures, timeouts, optional skips and expected failures stay visible. Performance
percentages require comparable repeated passing measurements, not a shared-host
failure or fewer source lines. One pass does not establish a zero-flake rate.
Report actual checks and uncertainty without creating another completed-task audit.
No live profile, model, service, paid tool, install or publication is authorized here.
