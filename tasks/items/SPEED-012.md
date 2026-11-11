+++
schema = 1
id = "SPEED-012"
title = "Each runner uses a private Pi directory that a change to the interactive Pi home cannot break"
short = "Runners keep a private Pi directory"
status = "open"
section = "Next"
rank = 34000
depends_on = []
touches = ["scripts/install_menu.py", "pi-autowork/src/pi_autowork/service.py", "pi-autowork/src/pi_autowork/command.py", "pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/src/pi_autowork/pi_runtime.py", "pi-autowork/src/autowork_runtime/", "pi-autowork/tests/runner/", "tests/test_install_menu.py", "docs/installation.md", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "On 2026-11-10 the interactive Pi home was removed and all eight runners stopped: they read the owner's Pi settings, model login and package clone from it (`Provider is not configured`, `PI_AUTOWORK_TOOLSET is missing`). Give the fleet one private Pi directory under the shared runner state root, owner-only (0700, files 0600). `install.sh` and `autowork update` fill it once from the interactive Pi home: settings needed to run, the model login and nothing else. The owner approved this local copy of the login on 2026-11-10; it is never written to a repository, a log, a report or a worktree. Runners start Pi with that directory and run from the installed release, not from the interactive package clone. When the private directory is missing or its login is refused, status says so and names the one command that refills it; the runner does not fall back silently to the interactive home. The `autowork` command link points at the installed release, so removing the interactive clone does not break it."
acceptance = ["A fixture with a disposable interactive Pi home and state root proves install fills the private directory with owner-only permissions, and a runner job environment points Pi at it.", "A fixture proves that deleting the interactive Pi home afterwards leaves the runner's Pi environment, toolset path and the autowork command link usable.", "A fixture proves a missing private directory gives one status line naming the refill command and no silent fallback; no test reads a real login, and no login value appears in any log or report the tests inspect.", "docs/installation.md and pi-autowork/README.md describe the private directory, what is copied and how to refill it."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_autowork_command.py tests/test_install_menu.py", "python3 scripts/affected_tests.py --run --base <captured-task-base>", "python3 skills/docs-sync/scripts/docs.py check .", "autowork tasks validate ."]
exclusions = ["No real credentials, login, provider or model call in any test; disposable fixtures only.", "No change to the interactive Pi home, to another runner's state or to live services; no weakened or deleted test."]
+++
- Sources: Owner decisions of 2026-11-10 (grilling round 3, accepted). Measure for every change: `autowork scorecard` accepted-to-delivered median and p95, baseline saved outside the repository on 2026-11-10.
