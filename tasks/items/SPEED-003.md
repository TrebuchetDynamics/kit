+++
schema = 1
id = "SPEED-003"
title = "Two fleet-wide full-check slots replace the per-runner load gate for workers"
short = "Fleet check slots replace load gate"
status = "open"
section = "Now"
rank = 18000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/engine/parallel_dispatch.py", "pi-autowork/src/pi_autowork/supervision/main_checks.py", "pi-autowork/src/pi_autowork/main_check.py", "pi-autowork/src/pi_autowork/worker.py", "pi-autowork/src/pi_autowork/health.py", "pi-autowork/tests/engine/test_parallel_dispatch.py", "pi-autowork/tests/runner/", "pi-autowork/README.md"]
resources = ["autowork-python-layout"]
kind = "implementation"
ownership = "worker"
scope = "Eight runners share one 24-CPU machine. On 2026-11-10 the load average stayed near 31, the worker gate in pi-autowork/src/pi_autowork/engine/parallel_dispatch.py (`resource gate: load average X >= N CPUs`) held ready kit tasks, and a full check took 15 to 20 minutes. Workers mostly wait on a model; full-suite runs use the CPUs. Add one fleet-wide limit of two concurrent full-suite runs, held as lock files under the shared state root so every runner of this user sees it, default 2 and set by one documented environment value. The main check, the batch or landing check and a worker's full-suite verification each take a slot; a focused test run takes none. A run that finds no free slot waits in a queue and states which runner holds the slots; it does not fail, time out its task or ask the owner. A slot whose holder process is dead is reclaimed. Remove the load-average gate for worker dispatch. The existing per-repository main-check slot stays."
acceptance = ["A fixture with three competing full-suite requests from different state directories proves at most two run at once, the third waits and then runs, and a slot left by a dead process is reclaimed.", "A regression proves a ready worker task is dispatched when the load average is above the CPU count, and the `resource gate: load average` reason is no longer produced for worker dispatch.", "Status and the fleet view show a waiting full check as queued for a fleet slot with the holder named; README documents the limit and its setting."]
checks = ["python3 scripts/check.py pi-autowork/tests/engine/test_parallel_dispatch.py pi-autowork/tests/runner/test_main_check.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No model calls, service start/stop/restart, installs, pushes or edits to another task's record.", "No weakened or deleted test; no change to owner-only gates, live authorization or receipt checks."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling rounds 1 and 2, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
