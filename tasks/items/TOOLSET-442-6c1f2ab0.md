+++
schema = 1
id = "TOOLSET-442-6c1f2ab0"
title = "Bound per-run evidence and engine.err in runner state"
short = "Bound runner state growth"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 1000
depends_on = []
touches = ["Src/pi_autowork/janitor.py", "pi-autowork/tests/test_janitor.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "engine.err is append-only across the life of a state key, and full-check/, runs/, sessions/ and review-tmp/ keep every run's evidence with no age or size bound. Add a bounded retention pass that keeps what an open slot, an unread gate receipt or an unfinished review still reads, and trims the rest by age and size. Report bytes reclaimed; never delete another live runner's evidence. Restated 2026-11-04: the previous worker died without a commit or changes (attempt 2, cause empty); no candidate exists to retry, so this contract is restated and runs fresh from the current main."
acceptance = ["engine.err is bounded per state key, retaining the newest diagnostics.", "Per-run evidence for closed tasks is bounded by age and size, while files an open slot, an unread gate receipt or an unfinished review references are never removed.", "The pass reports reclaimed bytes and is safe under concurrent runners: it skips another live runner's state and a file being written.", "A fixture proves an open slot's gate receipt survives while a closed task's run evidence is trimmed."]
checks = ["python3 pi-autowork/tests/test_janitor.py"]
exclusions = []
+++
- Sources: ["pi-autowork/README.md#runner-health-reads"]
