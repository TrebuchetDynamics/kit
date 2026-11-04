+++
schema = 1
id = "TOOLSET-437-bc962ae3"
title = "Extract the tx config module"
short = "One tx config module"
status = "done"
goal = "TX-ARCHITECTURE"
section = "Now"
rank = 1000
depends_on = []
touches = ["tmux/tx", "tests/test_tx.py"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Replace the four config grammar copies with one line-preserving config module inside tmux/tx. Add a source-only execution guard and unit tests for load, append, rewrite and comment/variable preservation."
acceptance = ["tmux/tx has one config load/append/rewrite owner; add, remove and edit call it.", "Comments, blank lines, variable lines and row order survive add/edit/remove.", "Sourcing tmux/tx does not run main; config tests pass."]
checks = ["python3 scripts/check.py tests/test_tx.py"]
exclusions = []
closure = "manual"
closure_actor = "agent"
closure_timestamp = "2026-11-02T05:44:28.964800+00:00"
closure_reason = "Extracted the config module and source-only guard."
closure_evidence = "commit a6740448; tests/test_tx.py config cases"
+++
- Sources: [tx plan](../plans/tx-architecture-2026-11-01.md#work)
