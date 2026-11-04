# Production-readiness audit: publication, recovery, and qualification

Date: 2026-11-04 (repo state at `862eefc8`); reviewer report dated 2026-11-04.
Status: local source and offline checks only. No live model, production repository,
remote push, service restart or profile write was performed for this audit.

## Scope and evidence

The review asked for four things: audit the open reliability issues against current
main, verify publication is opt-in through persisted service settings, audit the
Hermes policy defaults, and distinguish reproduced defects from unverified claims.
This pass inspected the source, reproducer tests and the TUI pilot. It also added one
mid-session repository-identity stop and two bounded follow-up tasks.

Run evidence:

```sh
TMPDIR=/tmp python3 scripts/check.py tests/test_repository_identity.py tests/test_autowork_push_setting.py
# 1 test directory passed; 0 failed; 3 optional integration modules excluded

TMPDIR=/tmp python3 -m pytest -q tests/test_autowork_push_setting.py \
  tests/test_autowork_command.py -k 'push or conflicting_service_settings or start_installs'
# 6 passed, 25 subtests passed

TMPDIR=/tmp python3 -m pytest -q tests/test_pi_autowork.py \
  -k 'setup_errors or inherited_git or push'
# 8 passed, 14 subtests passed

TMPDIR=/tmp uv run --offline --quiet --no-project --with textual==8.2.8 \
  python3 pi-autowork/tests/tui_pilot.py
# exited 0; TUI pilot passed, including Prepare/Prepare-and-start and readiness refresh
```

A full affected-test run also passed with `TMPDIR=/tmp` (5 test directories, 173
modules, 3 optional integration modules excluded). An earlier run without `TMPDIR`
hit an existing test assumption (`tests/test_supervision_main_checks.py` reads
`os.environ['TMPDIR']`); that is test-harness portability, not a runner behavior
claim. CI supplies a temporary directory.

## Open-issue audit

| Issue | Current state | Evidence | Remaining gap |
| --- | --- | --- | --- |
| #4 push default and `start` override | Regression evidence exists on current main. `coordinator.push()` and `sync_upstream()` require `PI_AUTOWORK_PUSH=1`; `service` no longer defaults to enabled; `start` refuses a conflicting saved setting and names the apply command. | `tests/test_autowork_push_setting.py`; `tests/test_autowork_command.py::test_start_refuses_conflicting_service_settings_without_starting`; saved-vs-shell status coverage. | The issue can be closed after this change is pushed and CI records the same regression. It should not be closed from a local-only commit. |
| #6 restart loop on an unusable repository | Startup failures already exit 4 and the unit has `RestartPreventExitStatus=1 2 3 4`. This pass adds a mid-session identity check before every cycle, merge and push, so a checkout replaced or marked `core.bare=true` stops deliberately with exit 4 instead of continuing or looping. | `tests/test_pi_autowork.py::test_setup_errors`; new `tests/test_repository_identity.py`. | A real systemd stop/restart on a disposable service is still live evidence, not covered by the fixture. |
| #9 prepare from Play and `ready` consistency | The Prepare / Prepare-and-start flow, shared `fleet_view.readiness` cache and post-prepare refresh are present. The headless pilot re-runs them against fixture repositories. | `uv ... tui_pilot.py` exited 0; source paths `tui.BrowseScreen.ready_to_start`, `PrepareRepository`, `RepoTree.update_readiness`, `fleet_view.readiness`. | The pilot is offline UI evidence; a live desktop/terminal TUI session and a real repository are not qualified. |
| #2 close/archive, dependencies, question separation | Several named fixes and regression fixtures are present (`dependency_ids` prose handling, close/reopen recovery, question freshness). The issue is a multi-part tracker, not one reproduced remaining defect. | `pi-autowork/engine/test_parallel_plan.py::test_dependencies_name_task_ids_not_the_prose_around_them`; existing close/recovery and question suites. | No single unresolved behavior was reproduced in this pass. Do not close #2 until each acceptance bullet has its own evidence. |

## Hermes approval policy

The review's P0 concern is still valid: with no `apply_runtime_defaults: false`
opt-out, loading the plugin writes `approvals.mode: off`,
`destructive_slash_confirm: false`, `mcp_reload_confirm: false` and
`agent.max_turns: unlimited`. That is wider authority than a general interactive
profile needs, even though it is documented and can be opted out.

This audit does **not** change the default. That is a security-policy decision for
the owner, and changing it silently for existing profiles would be the same class of
mistake. Task `TOOLSET-450-e643cb7a` records the bounded two-policy proposal:
interactive (conservative default) and autonomous (current fleet values), with
`apply_runtime_defaults: false` preserved as the no-write opt-out.

## Repository and publication hardening

* `cli.run` rejects inherited `GIT_DIR`/`GIT_WORK_TREE` routing before any service or
  repository write and removes every `GIT_*` variable before descendants run.
* Candidate checks and task-store reads have their own scrubbed Git environments;
  worker dispatch also removes `GIT_*`.
* Publication is refused unless the effective environment contains
  `PI_AUTOWORK_PUSH=1`. A saved grant is reusable, an explicit negative setting
  conflicts rather than being ignored, and `autowork status` states the launch
  setting. The remaining live evidence is an actual systemd restart with a saved
  grant and a no-grant service, not another unit test.
* The new `Coordinator.repository_problem()` re-probes the repository with a clean
  environment and compares both the work-tree root and common directory. It stops
  before merge or push with exit 4 when the checkout is unusable or replaced.

## Bounded follow-up tasks

| Priority | Task | Deterministic acceptance |
| --- | --- | --- |
| P0 | `TOOLSET-450-e643cb7a` — conservative Hermes policy with explicit autonomous opt-in | Fresh profile gets manual approvals and `max_turns=90`; explicit autonomous policy applies current values; opt-out writes no policy; preview names the policy. Offline fixtures only. |
| P1 | `TOOLSET-451-ba324296` — one disposable-repository delivery under interruption | Real-model run authorized by the owner; task admitted, reviewed, integrated and closed; local main ancestry recorded; one interrupt/restart resumes without duplicate dispatch or closure; measured/missing data separated. |
| P1 | Existing `TOOLSET-442-6c1f2ab0` — bound runner evidence | Keep open-slot receipts and unfinished-review evidence; trim closed-task evidence by age/size; report reclaimed bytes. |
| P2 | Onboarding: one successful change first | New developer completes describe → acceptance → implement → verify → deliver on a disposable repository without learning the full command surface. No new skill. |

The scorecard remains unqualified for a 30-day productivity claim: no real
multi-project run was performed here. Any later result must keep measured,
estimated and missing values separate, and must not treat these offline tests as
live reliability evidence.

## Local scorecard reading (kit only)

`bash pi-autowork/bin/autowork scorecard --days 30 --json .` was run read-only
against this repository's private runner state. It is **kit's own development
history**, not the two-product 30-day trial the evaluation plan requires:

- measured: 176 closed tasks, 82 verified closes, 94 manual closes, 0 unverified
  closes, 285 integrations, 47 questions, 2.73 verified tasks/day, 89 minutes
  start-to-merge, 8 explicit receipt-linked regressions in the retained data;
- missing: unattended completion percentage, accepted-to-delivered and
  dispatch-to-integrated medians/p95, cost per verified task, owner minutes per
  verified task;
- cost data is missing for all 837 observed runs; the report labels it `missing`,
  not zero.

This is a useful self-measurement, not evidence that Autowork improves delivery on
other products. It does not close `TOOLSET-311-d7` or qualify the 30-day plan.
