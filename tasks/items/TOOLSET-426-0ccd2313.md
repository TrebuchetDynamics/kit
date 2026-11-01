+++
schema = 1
id = "TOOLSET-426-0ccd2313"
title = "Split the install and setup bodies out of Src/autowork_runtime"
short = "Split runtime install bodies"
status = "open"
goal = "CODE-HEALTH-2026-10"
section = "Now"
rank = 1000
depends_on = []
touches = ["Src/autowork_runtime/install/", "Src/autowork_runtime/", "install_skills.py", "setup_bundle.py", "setup_preflight.py", "setup_runtime.py", "install_omh.py", "install-graphify.py", "tests/test_complete_setup.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "One move-only slice of the high-ROI folder split: move the six install/setup implementation bodies into Src/autowork_runtime/install/ and update their root shims' execute paths plus the one test that enumerates those paths. The bootstrap keeps __file__ pointing at the root shim, so repo-relative paths inside the moved bodies do not change. No behavior, no shim surface, no preflight rules."
acceptance = ["The six bodies live under Src/autowork_runtime/install/, the six root shims execute the new paths, and the preflight payload list in tests/test_complete_setup.py names them. No other file references the old paths.", "The move-only slice keeps behavior: the install, setup, provisioning, vendor, bundle, src-native and check suites pass unchanged, including the preflight and complete-setup fixtures that delete each payload path.", "The checkpoint is reported as one verified slice with the remaining candidates named by exact basename: the update pair, the command pair and the core bundle/plugin/runtime_defaults modules."]
checks = ["python3 scripts/check.py tests/test_install_skills.py tests/test_install_omh.py tests/test_install_graphify.py tests/test_setup_runtime.py tests/test_complete_setup.py tests/test_preflight.py tests/test_native_provisioning.py", "python3 scripts/check.py tests/test_engineering_vendor.py tests/test_impeccable_bundle.py tests/test_ponytail_bundle.py tests/test_ui_taste_bundle.py tests/test_pi_toolset_bundle.py tests/test_src_native.py tests/test_check.py"]
exclusions = ["No behavior change, no rename, no shim removal, no new tool, no preflight or profile writes, no remaining slice in this task, no publication."]
+++
