# Autowork uninstall removes the runner

## Accepted behavior

The owner reported that TUI **Uninstall** leaves the selected runner visible as
**not running** and answered: **“It should remove it.”** This accepts removing the
selected runner from the normal fleet after uninstall while retaining recovery
history, repository/task data, worktrees and unmerged branches. This is a
standalone planning batch, not implementation or authority to operate a service.
An existing authorized runner may execute its accepted offline task normally.

Success means the selected service is stopped and disabled, its saved instance
registration is removed, and subsequent successful fleet reads no longer offer it
as an installed runner. CLI `ls`, the TUI and Paseo use the same discovery result.
The shared `pi-autowork@.service` template and every other instance stay intact.

## Evidence and cause

Inspected canonical source at `9712648e` (read-only; no live mutations):

- `Src/pi_autowork/service.py::run(action='remove')` calls `disable --now`, removes
  the selected `.env` and handles the legacy escaped-path registration, but does
  not clear the selected instance's failed state.
- `Src/pi_autowork/fleet_view.py::_service_states` includes every loaded matching
  systemd instance, including disabled/failed entries without saved settings.
  `_health_runner` already ignores entirely orphaned history, but a failed loaded
  unit becomes a discovered service and can reacquire its repo from retained
  health data. Thus settings removal alone does not reliably retire the row.
- `command.py::cmd_remove` resolves saved settings without reopening a missing
  checkout. Preserve that behavior. `actions` exposes Uninstall for stopped
  services; confirmation says state/worktrees stay. Do not widen action authority.
- Read-only observation found the example instance disabled but still loaded and
  failed. This is evidence for the reported path, not proof of a completed
  uninstall or any service operation performed in this planning session.

Existing guards to retain: `tests/test_autowork_command.py` tests
`test_pause_resume_stop_restart_remove_go_through_systemctl` and
`test_remove_works_after_the_saved_repository_was_renamed_away`;
`tests/test_pi_autowork.py::ServiceTests.test_remove_and_refusals`;
`pi-autowork/tests/test_fleet_view.py` test
`test_a_stopped_disabled_service_is_listed_from_its_settings_and_paused_only_when_paused`
and its action/confirmation assertions. Do not remove disabled/paused installed
runners merely to make the uninstall case pass.

## Selected design

Planner calls, within the accepted outcome:

1. Use existing service registration and lifecycle, not a new retirement database
   or a permanent hide-only UI overlay. A valid saved `.env` continues to register
   an installed runner, even when stopped or paused. Retained health/history alone
   does not register it. An unregistered inactive/failed loaded-unit remnant does
   not register it either. Active/activating/deactivating instances remain visible
   as operational diagnostics rather than being hidden solely for missing settings.
   Unreadable/malformed discovery or settings remain explicit errors, not proof
   that an instance was uninstalled.
2. Successful removal stops/disables the selected instance and cleans its failed
   systemd state, then removes its registration and instance-only pause/stop state.
   Preserve legacy-instance cleanup and missing-checkout resolution. Confirm the
   lifecycle outcome through the existing systemctl seam; unexpected stop/cleanup
   failures must not claim full success or silently hide a still-live service.
   An already absent/inactive instance needs no destructive workaround. Repeat
   requests are safe (already-gone/missing-target refusal is acceptable); never
   guess another repository from a recycled name.
3. Do not delete the shared service template, repositories, tasks, logs, runtime
   evidence, grants belonging to other instances, worktrees or branches. Explicit
   later `start`/installation creates the usual saved registration and restores
   normal visibility; do not invent a separate restore command or erase history.

Rejected: deleting runtime history to make discovery empty (loses recovery);
hiding only in the TUI (CLI/Paseo and refreshes disagree); filtering every disabled
service (breaks pause/stop); deleting the shared template (breaks other runners).

## Saved implementation batch

Task: `TOOLSET-474-5b3e3ea3` (`Now`, worker-owned, live denied).
Goal: `RUNNER-REMOVAL`. One cohesive implementation outcome; no dependencies and no
exclusive/live resource. Its service/discovery/test/doc paths overlap possible
fleet work, so actual writer admission must be checked before execution. File
sharing alone is not a product dependency. No rolling expansion or closing plan
task is needed for this bounded fix.

The worker starts with a failing offline fixture that keeps a disabled/failed
unit listed after remove, retains stale health/history, and proves successful
uninstall no longer appears through the shared fleet/CLI result. Cover stop/error
handling, missing checkouts/legacy cleanup, preserved paused registrations,
unregistered live diagnostics, and explicit reinstallation in existing seams.
The existing TUI confirmation/view-only path remains unchanged.

Proposed implementation checks (not run during planning):

- `python3 scripts/check.py tests/test_autowork_command.py pi-autowork/tests/test_fleet_view.py`
- `python3 scripts/check.py tests/test_pi_autowork.py`
- `git diff --check`

Offline acceptance is distinct from live systemd qualification. After an explicit
operations request, qualify on a disposable user-service instance, checking the
actual unit/registration and CLI/TUI disappearance while preserving unrelated
services. Do not use an existing repository's service or restart the fleet as a
planning check.

## Handoff

A fresh read-only builder check found no product or architectural blocker. Its
one engineering finding (the no-install exclusion conflicting with the documented
checker's provisioning) is resolved: implementation may let `scripts/check.py`
provision its isolated CPython/`requirements-test.txt` environment through `uv`.
This never authorizes installing/updating Autowork or deployed software. The task's
exclusions and builder disposition record this narrow allowance. Reversible coding
details stay with the worker; no consequential owner question remains.

Planning checks passed on this saved batch: `autowork tasks validate --worktree .`
reported 260 tasks, 30 goals and no drafts; `python3
skills/docs-sync/scripts/docs.py check .` returned `ok`; `git diff --check` passed.
Task/goal readback confirms `TOOLSET-474-5b3e3ea3` is open in Now, worker-owned,
with live denied and no dependencies/resources. These are planning consistency
checks, not implementation or dispatch evidence. The final commit, consumer
inclusion and committed selection result are reported at handoff.

Implementation tests, real TUI interaction and live systemd removal are
proposed/unrun here. Standalone planning stops after saving the reviewed batch;
it does not implement, install, push or uninstall anything.
