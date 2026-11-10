+++
schema = 1
id = "SPEED-004"
title = "The default model-review setting is auto, and code and test changes keep their review"
short = "Model review default is auto"
status = "open"
section = "Next"
rank = 28000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/review_policy.py", "pi-autowork/src/pi_autowork/service.py", "pi-autowork/src/pi_autowork/worker.py", "pi-autowork/tests/runner/", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "pi-autowork/src/pi_autowork/review_policy.py reads PI_AUTOWORK_REVIEW with default `1`, a model review for every task. Change the default to `auto` wherever the default is defined or documented (review_policy.py, service.py, worker.py), so a small ordinary prose change whose exact tree passed its check with no failure or skip lands without a model review. Do not widen what `auto` may skip: every change to code, tests, configuration, instructions or sensitive documents keeps the model review. An explicit `1` or `0` keeps its present meaning."
acceptance = ["With PI_AUTOWORK_REVIEW unset, a prose-only fixture that meets the existing auto conditions skips the model review and a code or test fixture still requires it.", "Explicit `1` and `0` behave as before; existing review-policy tests pass with assertions unchanged except for the default.", "README and the service settings text name `auto` as the default."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_review_policy.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling rounds 1 and 2, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
