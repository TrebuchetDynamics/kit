+++
schema = 1
id = "TOOLSET-492-5239ccc5"
title = "Distinguish owner-action tasks from worker dispatch waits"
short = "Show owner action instead of dispatch"
status = "open"
section = "Now"
rank = 14000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/task_snapshot.py", "pi-autowork/tests/runner/test_task_snapshot.py", "pi-autowork/tests/runner/test_tui_layout.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Repair committed task-row presentation for owner-only tasks such as the two reported landing records. Show Blocker with an explicit owner-action reason rather than ready; awaiting dispatch, including with absent/stale runtime data or a compatible idle waiting observation. Give coordinator-owned idle work an explicit coordinator wait, never a worker-dispatch promise. Reuse task_snapshot.task_row/task_display across Tasks, details and CLI display. Keep task selection, admission, ownership and live authorization unchanged; a saved yes is direction, not completion or permission."
acceptance = ["A new test_owner_action_is_not_awaiting_dispatch in test_task_snapshot uses generic owner-only records matching the reported cases, including live denied and a dated yes. Without engine data and with compatible waiting observations, rows show Blocker and owner-action reason, counts include each open ID once, and task_display agrees; typed gates/closure stay unchanged.", "Extend that snapshot seam for coordinator ownership, ordinary worker waits and Needs decision precedence. Coordinator-owned idle work names its coordinator wait; ordinary ready workers retain ready; awaiting dispatch. Existing dependency-stop, stale/mismatched evidence and Active/Mergeable tests retain their meaning. Existing test_task_commands selection-only metadata test still proves owner tasks can be selection-eligible without worker admission.", "Extend the existing test_tui_layout pilot fixture with owner rows. Open/Blocker/Waiting views, counts, selected reason and Info/Help agree at existing fixture sizes; task identity, Decide and question navigation remain intact. A saved yes does not remove a still-required owner action."]
checks = ["PYTHONPATH=pi-autowork/tests:pi-autowork/tests/runner:pi-autowork/src:pi-autowork/src/pi_autowork/engine python3 -m unittest test_task_snapshot test_task_commands.TaskCommandTests.test_selection_metadata_pins_explicit_revision_and_does_not_imply_admission", "PYTHONPATH=pi-autowork/tests:pi-autowork/tests/runner:pi-autowork/src:pi-autowork/src/pi_autowork/engine python3 -m unittest test_tui_layout", "git diff --check"]
exclusions = ["No selector/admission-policy changes, new grants, task completion, blanket task renaming, service actions, live research or writes to the landing repository. Do not treat every question as another permission request."]
+++

- Sources: User screenshot and request to repair Autowork itself; pi-autowork/README.md#fleet-task-inventory-and-freshness; pi-autowork/src/pi_autowork/engine/task_select.py.
- Evidence: At e0635a9e, task_snapshot.py::_canonical_reason defaults to ready; awaiting dispatch after dependencies; task_row ignores typed ownership and idle observation text can overwrite why. Reported LND-009-6f5d5311 and LND-010-3f37aa56 are open Now with ownership owner. test_task_commands.py::test_selection_metadata_pins_explicit_revision_and_does_not_imply_admission pins the selection/admission boundary.
- Decisions: Owner-action is a descriptive Blocker, not Needs decision or a new approval request. A matching existing question may add context but is not required. Needs decision retains Decision precedence; compatible real in-flight evidence retains provenance-based display. Idle waiting text cannot erase committed ownership. Coordinator-owned idle work stays Waiting with coordinator reason. No new bucket or raw-record schema field.
- Next action: Add the named failing owner snapshot test in disposable generic repositories; extend the existing compact TUI seam, not a second status model. All new assertions and implementation checks are proposed/unrun. Missing pinned Textual cache is an unmet check, not a pass.
- Repo obligations triggered: Update pi-autowork/README.md Fleet task inventory and freshness to distinguish worker dispatch waits from owner/coordinator work. Preserve five-bucket sum, committed membership, pending edits, question context and runtime identity guards. No schema, generated-output, manifest or fixture-file changes.
- Scheduling: No product dependency on detached-answer saving or TOOLSET-487. Shared README and potential TOOLSET-487 test_tui_layout edits may conflict; inspect live ownership before implementation and preserve the other lane. Expect one integration and one independent review; physical TUI/install/service use remains unqualified.
