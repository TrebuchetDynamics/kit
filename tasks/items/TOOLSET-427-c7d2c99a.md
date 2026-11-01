+++
schema = 1
id = "TOOLSET-427-c7d2c99a"
title = "Finish the runtime folder split: update and command subfolders"
short = "Finish runtime subfolders"
status = "open"
goal = "CODE-HEALTH-2026-10"
section = "Now"
rank = 1000
depends_on = []
touches = ["Src/autowork_runtime/update", "Src/autowork_runtime/commands", "update_bundle.py", "update_bundle_native.py", "autoresearch_commands.py", "workflow_commands.py", "tests/test_update_bundle.py", "tests/test_src_native.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Complete the remaining move-only slices of Src/autowork_runtime: move the update pair into update/ and the command pair into commands/, updating their root shims and the two test expectations that name those source paths. Keep the core peer set flat by decision, and classify every remaining root file in the completion audit."
acceptance = ["update_bundle and update_bundle_native live under Src/autowork_runtime/update/, autoresearch_commands and workflow_commands under commands/, and the four root shims execute the new paths with no stale reference outside history.", "test_update_bundle names the new payload paths, and test_src_native maps a remote command owner to its subfolder in both the exec probe and the missing-payload check, so the move-only slice keeps behavior.", "The completion audit classifies every remaining root file: __init__.py as the package marker, and bundle.py, plugin.py, runtime_defaults.py and telegram_menu_policy.py as the intentionally flat core peer set. Affected suites pass and the checkpoint is reported as a finished topology for this slice."]
checks = ["python3 scripts/check.py tests/test_update_bundle.py tests/test_src_native.py tests/test_plugin.py tests/test_bundle.py tests/test_workflow_commands.py tests/test_preflight.py tests/test_complete_setup.py", "python3 scripts/check.py tests/test_check.py tests/test_native_provisioning.py"]
exclusions = ["No extraction or logic change, no core split, no shim removal, no rename, no preflight or profile writes, no publication."]
+++
