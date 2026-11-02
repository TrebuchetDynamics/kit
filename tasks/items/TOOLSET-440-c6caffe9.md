+++
schema = 1
id = "TOOLSET-440-c6caffe9"
title = "Share tx install paths with doctor"
short = "One tx install path source"
status = "done"
goal = "TX-ARCHITECTURE"
section = "Now"
rank = 4000
depends_on = ["TOOLSET-439-fe771cf4"]
touches = ["tmux/tx", "tmux/install.sh", "tmux/README.md", "tests/test_tx.py"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Add install.sh --print-paths for the resolved targets. Make tx doctor --install read those paths instead of re-deriving defaults. Document the read-only preview."
acceptance = ["install.sh --print-paths prints resolved targets and writes nothing.", "tx doctor --install reports the same paths the installer used.", "The install-path test passes and the README states the preview behavior."]
checks = ["python3 scripts/check.py tests/test_tx.py"]
exclusions = []
closure = "manual"
closure_actor = "agent"
closure_timestamp = "2026-11-02T05:44:31.257080+00:00"
closure_reason = "Added read-only install path preview and doctor consumption."
closure_evidence = "commit a4c3648b; tests/test_tx.py install-path case"
+++
- Sources: [tx plan](../plans/tx-architecture-2026-11-01.md#work)
