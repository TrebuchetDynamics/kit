+++
schema = 1
id = "CLOSE-EVIDENCE-002"
title = "An acceptance hold resumes the same worker once before it becomes a blocker"
short = "Acceptance hold resumes its worker once"
status = "open"
section = "Now"
rank = 21000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/engine/parallel_state.py", "pi-autowork/src/pi_autowork/engine/parallel_integrate.py", "pi-autowork/src/pi_autowork/engine/failure_policy.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/engine/", "pi-autowork/tests/runner/", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "CLOSE-EVIDENCE-001 holds a finished commit when its report lacks one met result with evidence for every acceptance item (`acceptance hold: ...`). pi-autowork/src/pi_autowork/engine/parallel_state.py maps the cause `acceptance` to `engineering_stuck`, and nothing acts on it: on 2026-11-11 eleven kit tasks stayed held for nine hours until the owner set each aside by hand. failure_policy.py already names the intended recovery (`record_acceptance_results`, agent repair). Give the hold one automatic recovery: the runner resumes the same worker on the same attempt and commit, once, with the exact unmet or missing acceptance items in its prompt; the worker finishes those items if work is missing and rewrites report.json with a result and evidence for every item. Reuse the existing same-attempt report resume path (recover_reports, resume_report) where it fits instead of a second mechanism. A second acceptance hold on the same attempt is final: it is shown as an engineering hold with the unmet items, and no further resume or fresh attempt starts by itself. The acceptance check itself is unchanged: a result is never inferred, and a report the runner did not receive from the worker is never written."
acceptance = ["A fixture with a held commit whose report has no acceptance list proves the runner resumes the same attempt once with the missing items named, and the task integrates after the worker reports every item as met with evidence.", "A fixture whose resumed worker still reports an item as not_met or not_checked proves the task is held with those items named, no second resume and no fresh attempt starts, and the retained commit is kept.", "Existing acceptance-mismatch and report-resume tests pass with assertions unchanged, and pi-autowork/README.md states the one-resume rule."]
checks = ["python3 scripts/check.py pi-autowork/tests/engine/test_parallel_integrate.py pi-autowork/tests/engine/test_parallel_state.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No weakened or deleted test; no change to what the acceptance check accepts; no runner-written or inferred acceptance result.", "No model calls in tests, service start/stop/restart, installs, pushes or edits to another task's record."]
+++
- Sources: Owner request of 2026-11-11 (unblock all): eleven acceptance holds had no automatic recovery.
