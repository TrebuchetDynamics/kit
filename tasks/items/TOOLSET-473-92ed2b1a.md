+++
schema = 1
id = "TOOLSET-473-92ed2b1a"
title = "Land safely around recent owner edits without an idle timer"
short = "Remove landing idle timer"
status = "done"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 7000
depends_on = []
touches = ["Src/pi_autowork/coordinator.py", "pi-autowork/tests/test_landing.py", "docs/reference.md", "docs/cross-host.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "User-approved: allow landing during active sessions when the guarded three-way merge preserves edits. Remove the non-planning quiet-time landing veto, retain conflict and concurrent-write guards, and suppress unchanged landing warnings. Preserve owner-planning auto-commit settling."
acceptance = ["Recent non-planning edits merge immediately when conflict-free and remain uncommitted; unsafe edits preserve refs, index and owner content.", "Unchanged landing warnings print once, changed reasons print again, and successful landing clears suppression."]
checks = ["python3 scripts/check.py pi-autowork/tests/test_landing.py", "git diff --check"]
exclusions = ["No service control, deployment, publication, conflict overwrite, or owner-planning auto-commit policy change."]
closure = "manual"
closure_actor = "interactive Pi session"
closure_timestamp = "2026-11-07T03:27:50.711681+00:00"
closure_reason = "User-authorized integration on main; reviewed guarded landing change and warning deduplication. 13 landing regressions pass after merging the concurrent quiet-clock/retry fix; 78 related tests passed before that merge. Manual source closure, not live qualification."
closure_evidence = "45229b97; 1d70516b"
+++
- Sources: Src/pi_autowork/coordinator.py; Src/pi_autowork/landing.py
- Evidence: Local implementation checked: 10 landing tests plus 78 worker/barrier/common Git tests passed with CPython 3.12 checker; docs check, task validation and diff check passed. Two new regressions failed before the fix. Fresh read-only independent review found no blockers; its documentation wording note was corrected. Existing external-editor race window remains documented. Full suite and live runner qualification NOT_CHECKED.
- Next action: Integrate fix/less-blocked-landing through the current coordinator after ownership permits. Branch contains code, docs and checks; no service control or installed activation performed. Keep open until integration, and assess installed activation separately.
