+++
schema = 1
id = "TOOLSET-474-5b3e3ea3"
title = "Retire uninstalled service instances from shared fleet discovery"
short = "Uninstall removes the runner"
status = "done"
goal = "RUNNER-REMOVAL"
section = "Now"
rank = 4000
depends_on = []
touches = ["Src/pi_autowork/service.py", "Src/pi_autowork/fleet_view.py", "tests/test_autowork_command.py", "pi-autowork/tests/test_fleet_view.py", "tests/test_pi_autowork.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Implement the accepted uninstall lifecycle in docs/plans/autowork-uninstall-retirement.md. Stop/disable and clean only the selected service instance, preserve missing-checkout and legacy removal, and prevent unregistered inactive/failed unit remnants plus retained health state from reappearing in shared CLI/TUI/Paseo fleet discovery. Keep installed stopped/paused runners, live unregistered diagnostics and read errors visible. Preserve history, repositories, task data, worktrees, branches and the shared template. Extend existing fake-systemctl/fleet seams and document the distinction."
acceptance = ["Given a registered runner whose fake systemctl keeps a disabled/failed unit and stale health visible after removal, successful CLI remove stops/disables and cleans the selected instance, removes its registration, and the next successful ls --json/shared fleet result omits it; extend AutoworkCommandTests.test_pause_resume_stop_restart_remove_go_through_systemctl and FleetViewTests with the retained-failed-unit fixture.", "Given installed stopped/paused registrations, unregistered live units, malformed/unreadable settings or a failed stop/cleanup, discovery preserves their truthful visible state/error and uninstall never claims full success for a still-live service; extend the existing fleet stopped-disabled test and removal/refusal fixtures without weakening their guards.", "Given missing checkouts, legacy instances, preserved recovery data and later explicit installation, existing removal behavior remains safe, all unrelated instance/template/data bytes remain unchanged, and the new registration is visible again; extend the missing-checkout and ServiceTests.test_remove_and_refusals seams and update pi-autowork/README.md."]
checks = ["python3 scripts/check.py tests/test_autowork_command.py pi-autowork/tests/test_fleet_view.py", "python3 scripts/check.py tests/test_pi_autowork.py", "git diff --check"]
exclusions = ["No live systemd/service/repository operations, model execution, deployment or installation/update of Autowork or other deployed software, publication, credentials or permission changes. The documented checker may provision only its isolated CPython/requirements-test environment through uv; this does not authorize a runtime/package rollout.", "No purge of runtime history, repositories, task/goal data, worktrees or branches; no shared template deletion, blanket hiding of disabled services, separate retirement database or TUI-only workaround."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/TOOLSET-474-5b3e3ea3.toml"
+++
- Sources: docs/plans/autowork-uninstall-retirement.md#accepted-behavior
- Owner decision: In standalone Plan With Me, the owner answered 'It should remove it' to removing an uninstalled runner from the normal list while preserving recovery data. This accepts the behavior, not live uninstall or implementation within planning.
- Decisions: Saved settings identify installed instances; retained history and unregistered inactive/failed loaded-unit remnants do not. Keep active lifecycle diagnostics visible and errors explicit. Successful removal cleans the selected instance only; explicit start/installation restores normal registration. Routine coding details remain reversible within this design.
- Evidence: Source at 9712648e: service.run remove omits failed-state cleanup; fleet_view._service_states admits all loaded instances; _health_runner can attach retained history to that unit. Read-only example inspection found a disabled, loaded, failed instance. No live action was run.
- Repo obligations triggered: pi-autowork/README.md Commands remove and TUI uninstall/retention copy must match the lifecycle; existing CLI missing-checkout, service legacy/refusal, fleet pause/stop and action confirmation assertions are guards to retain. No manifest/schema/generated-output changes are needed. The six touches are one cohesive service/discovery contract, not independent layers.
- Verification status: All listed implementation checks and new/extended fixtures are proposed/unrun during planning. Start with the retained-failed-unit regression in the existing command/fleet seams. Live qualification is separate and needs explicit operations authority; offline completion does not prove real uninstall.
- Scheduling: No prerequisite task or exclusive/live resource. Preserve other active writers; overlapping service/fleet files constrain admission, not product dependencies.
- Builder disposition: Fresh read-only builder review found no product/architecture blocker; its P2 checker-versus-install exclusion conflict is planner-resolved by permitting only scripts/check.py isolated CPython/requirements-test provisioning through uv, never an Autowork/runtime rollout. Existing guard tests and proposed paths are reachable. Implementation checks remain proposed/unrun.
- Pending live: Separately authorize qualification on a disposable systemd user-service instance: confirm real stop/disable/failed-state cleanup and the next CLI/TUI/Paseo discovery result, preserving unrelated services and recovery data. No live service operations were performed.
