+++
schema = 1
id = "SPEED-010"
title = "The docs maintainer runs once when the queue is idle, for every task closed since its last run"
short = "Docs maintainer runs when idle"
status = "open"
section = "Next"
rank = 32000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/post_completion.py", "pi-autowork/src/pi_autowork/maintainer.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/tests/runner/test_post_completion.py", "pi-autowork/tests/runner/test_maintainer.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "The docs maintainer starts a model run after each closed task (`post-completion Docs Sync for ...`). On 2026-11-10 two runs were refused with `maintenance changed ownership, decisions or non-descriptive notes`, so the model time gave no result. Collect closed tasks and start one post-completion run when no worker, review or landing is in flight, covering every task closed since the last run. A refused run is not repeated for the same set of closed tasks; it runs again only when a further task closes. The refusal checks in pi-autowork/src/pi_autowork/post_completion.py are unchanged."
acceptance = ["A fixture proves three closes while work is in flight start no maintainer run, and one run covering all three starts when the runner is idle.", "A fixture proves a refused run is not started again for the same closed set and is started after one more task closes.", "Existing post-completion refusal and landing tests pass with assertions unchanged; README states when the maintainer runs."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_post_completion.py pi-autowork/tests/runner/test_maintainer.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
