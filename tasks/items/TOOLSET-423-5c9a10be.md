+++
schema = 1
id = "TOOLSET-423-5c9a10be"
title = "Rename skill-folder-refactor to split-folder"
short = "Rename to split-folder"
status = "done"
goal = "SKILL-STYLE"
section = "Now"
rank = 1000
depends_on = []
touches = ["skills/split-folder", "adapters/skills/split-folder", "adapters/pi.mjs", "skills/ask-autowork/SKILL.md", "skills/unused-code/SKILL.md", "docs", "README.md", "tests"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Rename the skill and its adapter to split-folder because the old name read as refactoring a skill folder. Update every map that names the old command or path: the router, Pi commands, README, three docs, the unused-code boundary, packaging and doctor fixtures and the pin test. The vendored UPSTREAM.json keeps the upstream source path, so its hashes and revision stay unchanged."
acceptance = ["Both entries declare name split-folder and the adapter links the renamed host-neutral workflow; the pinned bytes, upstream source key, revision and hashes are unchanged and still verify.", "No map names the retired path outside closed task history: the router, Pi command list, README, docs/workflows, docs/cross-host, docs/dependencies and the unused-code Boundary all use split-folder.", "The pin test resolves the local name to the pinned upstream path through an explicit mapping, and the affected suites pass: skill standard, descriptions, portable package, doctor modes, pi-toolset bundle, plugin, bundle, workflow commands and node --test tests/portable_pi.test.mjs. Counts stay the same because this is a rename."]
checks = ["python3 scripts/check.py tests/test_skill_standard.py tests/test_skill_descriptions.py tests/test_portable_package.py tests/test_doctor_modes.py tests/test_pi_toolset_bundle.py tests/test_plugin.py tests/test_bundle.py tests/test_workflow_commands.py", "node --test tests/portable_pi.test.mjs"]
exclusions = ["No content redesign beyond the name and title, no upstream edit, no behavior or authority change, no change to closed task history, no publication."]
closure = "manual"
closure_actor = "interactive session (/lgtm on the rename recommendation)"
closure_timestamp = "2026-11-01T02:30:05.157438+00:00"
closure_reason = "Renamed skills/skill-folder-refactor and its adapter to split-folder. Both entries declare the new name, the adapter links the renamed workflow, and every map that named the old command or path now names split-folder: router row, Pi command, README example, workflows, cross-host, dependencies and the unused-code Boundary. The vendored pin keeps its upstream source key, revision 5e9aa83 and both hashes, which re-verified after the move, and the pin test maps the local name to that upstream path explicitly. Counts are unchanged because this is a rename. Checks passed: skill standard, descriptions, portable package, doctor modes, pi-toolset bundle, plugin, bundle, workflow commands and node --test tests/portable_pi.test.mjs (4/4). Closed task history was left untouched as history."
closure_evidence = "python3 scripts/check.py tests/test_skill_standard.py tests/test_skill_descriptions.py tests/test_portable_package.py tests/test_doctor_modes.py tests/test_pi_toolset_bundle.py tests/test_plugin.py tests/test_bundle.py tests/test_workflow_commands.py; node --test tests/portable_pi.test.mjs; sha256 recheck of skills/split-folder/UPSTREAM.json"
+++
