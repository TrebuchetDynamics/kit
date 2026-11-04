+++
schema = 1
id = "TOOLSET-454-33fa923c"
title = "Bound push execution and reconcile an ambiguous remote outcome"
short = "Bound the push outcome"
status = "done"
goal = "RELIABILITY-2026-10"
section = "Now"
rank = 3000
depends_on = []
touches = ["Src/pi_autowork/coordinator.py", "tests/test_pi_autowork.py", "CHANGELOG.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "coordinator.py's push() runs git push with subprocess.run(timeout=300) and no handler, and the runner loop catches only Finish: a hung or failed remote ends the service process with a traceback, and the caller cannot tell a failed push from one that landed. Return a typed outcome instead (published, rejected, unknown), catch OSError and subprocess.TimeoutExpired, log once, and on an unknown outcome reconcile against the remote ref (git ls-remote, read-only) before any further push: treat the revision as published when the remote already names it, otherwise leave the next cycle to push the same fast-forward. Keep the PI_AUTOWORK_PUSH=1 grant check first, keep the worker push guard, keep fast-forward-only and the single existing non-fast-forward retry."
acceptance = ["A push that raises OSError or subprocess.TimeoutExpired neither propagates out of push() nor ends the runner cycle, and exactly one log line states that the remote outcome is unknown.", "An unknown outcome is reconciled from the remote refs before any retry: when the remote already has the published revision nothing else is pushed, and when it does not, the next cycle may push that same revision once.", "Without PI_AUTOWORK_PUSH=1 no push and no remote probe happens, and a worker still cannot push; a rejected or non-fast-forward push keeps the existing single fetch-and-push-once behaviour.", "Deterministic tests inject a timeout, an OSError, a remote that already has the revision, a remote that lacks it, and no grant; they assert the outcome value and the calls made, not log prose."]
checks = ["python3 scripts/check.py tests/test_pi_autowork.py", "python3 skills/docs-sync/scripts/docs.py check ."]
exclusions = ["No change to when publication is allowed: the PI_AUTOWORK_PUSH=1 grant, upstream selection and fast-forward-only rule stay as they are.", "No forced push, no remote write other than the existing fast-forward push of the main branch, and no live service, remote repository or deployment is touched by the offline checks.", "No new queue, database, scheduler or retry framework."]
closure = "manual"
closure_actor = "interactive-autowork-session"
closure_timestamp = "2026-11-04T18:45:36.175458+00:00"
closure_reason = "Implemented and offline-verified under the owner-approved audit follow-up; manual close, so no coordinator receipt (no runner service was installed or restarted)"
closure_evidence = "commits and checks in the Evidence note"
+++
- Sources: branch dsh-lessons docs/research/authorized-autonomy-audit-2026-11-04.md#2-durable-effects-and-crash-recovery
- Evidence: Fix 374deceb. Five deterministic cases in tests/test_pi_autowork.py PushOutcomeTests: a timeout records one unknown outcome, reconciles with a read-only ls-remote and does not retry; a push that landed before its timeout reads as published; a client refusal is a known failure with no probe; an unexplained failure is reconciled; no grant performs no push or probe. Existing push and upstream runner tests green. A live remote push was not performed.
