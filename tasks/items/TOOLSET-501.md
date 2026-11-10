+++
schema = 1
id = "TOOLSET-501"
title = "Exclude extensionless build binaries from affected-test source scanning"
short = "Exclude binaries from test scanning"
status = "open"
section = "Now"
rank = 11000
depends_on = []
touches = ["scripts/affected_tests.py", "tests/test_affected_tests.py"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Repair affected-test input classification so untracked extensionless build binaries cannot be decoded wholesale as source. Preserve legitimate extensionless scripts and conservative dependency coverage for real source. First reproduce with a small private synthetic binary and script fixture; use bounded binary detection before full text decoding, not a file-size-only exclusion of legitimate source. Do not edit the active Rust/layout candidates, their .gitignore files, cached build artifacts or runtime state. Integrate only source-bound tested and independently reviewed changes when no conflicting writer or test gate is active."
acceptance = ["A private-fixture regression proves an untracked extensionless binary is not admitted to source text decoding or dependency edges while a legitimate extensionless script still selects its dependent test.", "Binary detection reads only a bounded prefix before deciding whether full text decoding is appropriate; no dependency upgrades, Cargo builds, large binary fixtures or scans of real retained build outputs are needed for the regression.", "Existing affected-test selection, conservative unmapped-code behavior, duplicate module stems and document/planning-record rules remain intact. Focused checks and independent review bind the same immutable candidate. Preserve existing attempts, retry limits, pauses, acceptance and live gates."]
checks = ["python3 scripts/check.py tests/test_affected_tests.py (only when the existing gate is clear)", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate .", "git diff --check"]
exclusions = ["No edits to live worker/review checkouts or contracts; no deletion/cleanup of target directories; no service actions, competing tests, push, install, state migration, lowered gates or live-success claim."]
+++
- Sources: /tmp/kit-debug-rust-selector-artifact-evidence.json (private observation input); retained integration 69b0178c49c63b7d7c39a1373025c8f33fb11b25 against base 9ae914e0178ec942cb8d89ef588ad3302e56e47d (not a landed-qualification claim); scripts/affected_tests.py: repository_files and dependency_graph; tests/test_affected_tests.py.
- Evidence: The Rust candidate replaces the legacy target ignore with the relocated one while retaining3.5GB at the legacy target. Git exposes3676 artifact entries. The selector admits extensionless untracked files and dependency_graph decodes them with read_text(errors=replace). Repeated real-repository select calls in test_affected_tests consumed sustained CPU; candidate full-check log reports root-test TIMEOUT after1800seconds, five other directories passed. The outer integration then timed out after5346seconds at06:32; this does not qualify the candidate or prove every slowdown is binary decoding.
- Planner call: Fix source classification independently in a synthetic fixture; do not hide artifacts in a running checkout or weaken source selection. Retaining both legacy/current build ignore coverage during relocation remains a separate owning-worker concern, not permission to edit that live candidate.
- First action: Recheck actual ownership and gate activity. Execute in canonical .worktrees isolation only when the conflicting gate/writer is clear; do not count this saved plan as implementation.
- Qualification: Offline source repair only; hourly publication/reinstall and active layout/Rust reviews remain separately pending.