+++
schema = 1
id = "TOOLSET-490-a67e5eb2"
title = "Separate command-result interpretation from the TUI"
short = "Interpret command results without TUI"
status = "open"
section = "Now"
rank = 12000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/command_results.py", "pi-autowork/src/pi_autowork/tui.py", "pi-autowork/tests/runner/test_command_results.py", "pi-autowork/tests/runner/test_tui_architecture.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Extract FleetApp command-result interpretation into a headless module. Preserve command execution, terminal suspension, UI callbacks, refresh ordering and existing CLI mutation and commit authority. This is the bounded extraction accepted in the interactive architecture review."
acceptance = ["Headless tests cover generic output, warning-success, failed commands, execution exceptions, pending answers, committed answers and invalid receipts with unchanged meanings.", "The TUI delegates interpretation while preserving notification truncation, callback ordering and refresh behavior; existing rendered control and deletion tests pass."]
checks = ["python3 scripts/affected_tests.py --base 65cb36913d7f68bb4293e8ee91a142542f4ba679 --run"]
exclusions = ["No runner policy changes, live service actions, additional architecture candidates, push or deployment."]
+++
- Owner decision: Accepted the bounded extraction and regression tests in the interactive LGTM request.
- Next action: Merge the reviewed extraction with current main, rerun affected checks on the merged candidate, then push and reinstall under the owner's explicit delivery request. Preserve existing runner and task authority; a verified engine close has not been recorded.
