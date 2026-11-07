+++
schema = 1
id = "COMMIT-SNAPSHOT"
title = "Bind task commits to reviewed pending content"
short = "Exact reviewed task commits"
status = "done"
goal = "TASK-STORE-HARDENING"
section = "Now"
rank = 4000
depends_on = []
touches = ["Src/pi_autowork/task_commands.py", "Src/pi_autowork/tui.py", "Src/pi_autowork/landing.py", "integrations/paseo/", "tests/test_task_commands.py", "pi-autowork/tests/test_tui_controls.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Add a pending-content revision enforced under the Python task lock; carry it through existing TUI and Paseo commit confirmations."
acceptance = ["Changes to task content, additions, deletions or HEAD after preview refuse protected commits without moving HEAD or changing the real index.", "Protected commits use the reviewed staged bytes and leave unrelated edits intact."]
checks = ["python3 scripts/check.py tests/test_task_commands.py", "npm --prefix integrations/paseo run typecheck"]
exclusions = ["No live runner operations, installation, push, other review candidates or policy-grant changes."]
closure = "manual"
closure_actor = "coordinator"
closure_timestamp = "2026-11-06T18:50:55.490630+00:00"
closure_reason = "Offline snapshot-commit acceptance met; independent follow-up review found no blockers. Manual closure, not coordinator-engine verification or live qualification."
closure_evidence = "Focused Python task/TUI/transaction/history/landing checks, Paseo typecheck and operations/client/contracts/server tests passed; independent read-only review approved the corrected candidate."
+++
- Sources: Accepted architecture review candidate 1; owner LGTM; Src/pi_autowork/task_commands.py; integrations/paseo/server/operations.ts
- Implementation evidence: Regression tests failed before implementation and pass after it. Python task commands (38), task transactions (5), history (4), TUI reads (4), TUI controls (4), planning UI (2), landing (9), README links (1) passed on their affected inputs. Paseo operations/client/contracts/server tests and typecheck passed; latest follow-up operations/client run passed 82 tests. Native/live qualification not checked.
- Next action: Publish the reviewed offline fix. Native/live UI qualification remains separate and NOT_CHECKED; no installation or runner operation is part of this delivery.
- Review evidence: Independent fresh-context reviewer inspected the candidate and reproduced the merge-state issue in a disposable fixture. After fixes, follow-up review confirmed both reported gaps closed and found no blockers. Review approval is not publication or installation authority.
- Documentation impact: Updated pi-autowork/README.md, integrations/paseo/README.md and integrations/paseo/docs/security.md for exact pending-snapshot acceptance, compatibility refusal and cooperative-lock limits.
