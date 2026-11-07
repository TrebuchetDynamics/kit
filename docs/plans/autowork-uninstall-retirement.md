# Autowork uninstall removes the runner

## Accepted behavior

The owner reported that TUI **Uninstall** leaves the selected runner visible as
**not running** and answered: **“It should remove it.”** This accepts removing the
selected runner from the normal fleet after uninstall while retaining recovery
history, repository/task data, worktrees and unmerged branches. This requirement
is not authority to operate a service; actual removal needs its normal confirmation
and current ownership.

Success means the selected service is stopped and disabled, its saved instance
registration is removed, and subsequent successful fleet reads no longer offer it
as an installed runner. CLI `ls`, the TUI and Paseo use the same discovery result.
The shared `pi-autowork@.service` template and every other instance stay intact.

## Compatibility and qualification

Preserve missing-checkout and legacy-registration removal, normal action/confirmation
restrictions and disabled/paused installed runners. Loaded failed units and retained
health/history must not resurrect a successfully uninstalled registration. Unreadable
state is not an empty fleet or proof of removal. Existing command, lifecycle, fleet
and action fixtures own these regression seams; past audit results remain in Git.

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

## Required checks and live boundary

Offline fixtures must cover stale disabled/failed units after removal, stale health,
stop/cleanup errors, missing checkouts, legacy registration, preserved paused runners,
unregistered live diagnostics and explicit reinstallation. The TUI confirmation and
view-only path remains unchanged. Use existing command/fleet/service test seams.

Offline acceptance does not qualify live systemd behavior. A disposable user-service
qualification needs a separate explicit operations request and actual unit/registration
and CLI/TUI readback while preserving unrelated instances. Do not use an existing
repository's service or restart the fleet as a documentation check. Checker provisioning
of its isolated Python/test environment is not permission to install deployed Autowork.
