+++
schema = 1
id = "AUTH-CHECKS-001"
title = "Qualify hosted-auth imports and preserve test inventory"
short = "Reconcile hosted-auth test inputs"
status = "open"
section = "Now"
rank = 13000
depends_on = []
touches = ["pi-autowork/tests/runner/test_task_prepare.py", "tests/fixtures/python-layout.json", "tests/test_check.py"]
resources = ["hosted-auth-qualification"]
kind = "implementation"
ownership = "worker"
scope = "Repair the two deterministic qualification mismatches exposed by the normal frozen632bec62 hook against published57a1992b. Preserve the isolated-import DAG check and every required current test. Classify the new pi_autowork.tui_auth renderer with the existing pinned Textual execution environment instead of importing it without its UI dependency or skipping it. Reconcile the old terminal-login test identity with its deliberate hosted-auth replacement using immutable89877429 before/after Git blobs, not a candidate-generated expectation."
acceptance = ["The complete package import/cycle test executes tui_auth with the same offline textual==8.2.8 setup as other renderer modules; it is not excluded, mocked away or made an unconditional skip. Non-TUI modules remain independently importable without adding Textual as a production CLI dependency.", "Historical layout fixture gains only an explicit immutable hosted-auth rename transition, with full commit, before/after blob/mode/path provenance and a method-inventory fingerprint derived from the previous preserved baseline plus the verified historical delta. Preserve original snapshots, all baseline/current test coverage, three exclusions and disjoint/exhaustive shard checks. Verify the replacement retains selected-profile and authentication/cancellation safety coverage; do not restore obsolete external-terminal behavior or regenerate expected inventory from the migrated candidate.", "Focused package-import, inventory/checker and hosted-auth UI fixtures pass on the exact candidate with dependencies present, followed by fresh independent review. Normal full pre-push remains enabled. This test-input repair does not qualify live authentication, fix AUTH-001, or reconcile the separate Rust interfaces."]
checks = ["Scoped check.py executions for package import/cycle isolation and historical inventory/checker contracts", "Existing hosted-auth/model fixture checks as affected by immutable mapping proof", "Fresh independent read-only review of exact fixture/provenance changes", "docs/task validation, tree/type guard and diff check"]
exclusions = ["No edits to live FLAKE/Rust workers, no weakening/deleting tests or changing production authentication behavior, no credential/profile/browser/model calls, no live-success claim, no installer/restart, no remote write until normal candidate gates qualify."]
+++
- Sources: /tmp/kit-ci-only-632bec62-push.log, actual normal-hook exit1 with four directories passed and two failed. Exact failures: lost TuiModelsTests.test_login_uses_pi_terminal_and_selected_agent_directory; plain isolated import of pi_autowork.tui_auth raises ModuleNotFoundError:textual. Historical idle-fixture contract and receipt: git show 4e6b66caf869a798122d8ee8b70b2f120bf33346:tasks/items/FLAKE-001.md; git show 4e6b66caf869a798122d8ee8b70b2f120bf33346:tasks/evidence/FLAKE-001.toml
- Immutable evidence:89877429 deliberately replaces the terminal-login method with test_authentication_inside_tui_uses_selected_profile_masks_and_refreshes; the new fixture retains selected profile, explicit Connect/Browser, masked input and stale-profile cancellation assertions. Existing renderer import classification omits the new module.
- Ownership: Fresh FLAKE-001 is live but touches only test_pi_autowork.py; these paths are disjoint. Work only in the existing isolated CI delivery checkout after its producer has exited, preserving frozen past Git commits and main Rust divergence.
- First action: Pin the before/after Auth blobs and current fixture baseline, preserve a failing reproduction, then make the smallest metadata/environment correction. The CI setup repair0576 remains separately reviewed; do not rewrite its completion or infer all tests passed from CI setup alone.
- Description: The Ownership note's FLAKE-001 observation is historical: its test-only repair is closed and integrated at 2595f38a7f42dcc94b10105897ac72bd49848df4. The existing isolated-checkout and producer-exit requirements still apply; recheck actual ownership before repair. This supplies no hosted-auth qualification.
