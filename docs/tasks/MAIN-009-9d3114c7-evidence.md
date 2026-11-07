# MAIN-009: supplemental red-main evidence at 9d3114c7

## Disposition

[MAIN-009](../../tasks/items/MAIN-009.md) already covers all three failures in
this incident. It is open, first in Now, and already requires the full offline
check. Do not create a second repair task or reopen earlier MAIN repairs.

At this maintainer inspection, the Git common directory's
`autowork-execution/slots/MAIN-009.json` reports attempt 1 running in
`.worktrees/autowork-MAIN-009`. Its recorded worker process is alive, and a
PackageUpdateTests check is executing there. The attempt directory has no
`report.json` yet; no completed worker report or acceptance result is inferred.

The instruction prohibiting edits to a running task protects its entire entry,
including Evidence. Consequently this supplement preserves the new evidence
reference without changing the task record, its contract, rank, dependencies or
authority. The task's Evidence refresh is deferred while that protection applies;
this note is neither a closure nor a verification receipt. Reconcile against the
then-current task and worker outcome before any later ledger edit.

## Evidence (read in place, not copied)

Bundle directory:
`<git-common-dir>/autowork-execution/main-evidence/9d3114c7f1be82425868ef49f79c62a73c22f1b9`
(resolve `<git-common-dir>` with `git rev-parse --git-common-dir`).
All five files were inspected: `main_check.json`, `main-check.log`,
`main-check.exit`, `main-check-reruns.log`, and `flaky_history.json`.

- Checked revision: `9d3114c7f1be82425868ef49f79c62a73c22f1b9`.
  Last green: `5a28ed0a16497427a5fa5af7fcb19671c34e9c90`.
- Result: red, `TEST_FAILURE`, exit 1. The check reached its results:
  **4 test directories passed; 1 failed; 3 modules excluded**. This is not a
  checker crash.
- Failures, all in `test_release.PackageUpdateTests`:
  - `test_local_packages_never_fetch_or_update_even_with_an_old_installed_flag`
  - `test_managed_packages_use_the_exact_registered_source_including_ref`
  - `test_unknown_or_unreadable_package_declarations_do_not_update`
- Each isolated rerun exits 1: respectively two, three and one error subtests.
  Full-run and isolated tracebacks reach `Coordinator.update_toolset` ->
  `maintenance.update` -> `start` -> `write` -> `json.dumps(record)` and end
  `TypeError: Object of type PosixPath is not JSON serializable` under CPython
  3.12.14. These are reproducible failures, not a flaky-test classification.
- `main_check.json` has an empty current `flaky` list. None of these three
  tests appears in `flaky_history.json`; historical unrelated flakes do not
  reclassify this incident or widen MAIN-009.

The incident's named commits since green are:

- `9d3114c7` docs(tasks): close TOOLSET-474-5b3e3ea3 (pi-autowork)
- `4215e044` Merge commit '98733cb24623edf352b896988b2727aeb96f48da' into HEAD
- `bffde82c` docs(tasks): close TOOLSET-474-9404c8c9 (pi-autowork)
- `98733cb2` fix(autowork): retire uninstalled runners from fleet discovery
- `8af5bbc8` Merge commit '13e04becb8b306399db68bfdd13b778e77df8ad1' into HEAD
- `13e04bec` feat(installer): bootstrap official stable Octet binaries
- `773e5bf8` Merge commit '9bc09e6c294b4505bea977a62b1e123a0eefade3' into pi-autowork/20261104-141507
- `9bc09e6c` Merge branch 'main' into recovery/unblock-lang-003

The bundle's `commits` field retains the longer history; MAIN-009 already records
that earlier context. This list is investigation context, not causal attribution.

## Existing contract remains sufficient

The task's Sources were checked against the registered-source policy and off-loop
maintenance lifecycle in [the component README](../../pi-autowork/README.md),
[offline verification](../testing.md#verify), the package-update fixture and
`Src/pi_autowork/supervision/maintenance.py`. The fixture assigns Path-valued
package/toolset identities and patches the checkpoint in the parent process;
maintenance now persists identity before starting a child. Both boundary issues
are already explicit in MAIN-009's Scope and Acceptance.

Its Touches already cover the failing test, coordinator, maintenance, release and
async regression coverage. The newer uninstall and Octet commits change fleet,
service and installer paths, but the supplied traces provide no reason to add
those unrelated implementation paths. Preserve the existing bounded Touches and
Checks; no new product prerequisite or scheduler bypass is justified.

## Maintainer validation

`tasks validate --worktree .` passed: 263 tasks, 31 goals, no drafts.
`python3 scripts/affected_tests.py --base HEAD --run` selected zero test modules
for this documentation-only change. This confirms ledger structure and change
impact only, not repair completion. No product checks were rerun to compete with
the live worker; implementation, integration and main-green proof remain pending
under MAIN-009.
