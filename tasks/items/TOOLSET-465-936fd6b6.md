+++
schema = 1
id = "TOOLSET-465-936fd6b6"
title = "Qualify A–E on a disposable target with the real engine"
short = "Qualify A–E on a disposable target"
status = "done"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 7000
depends_on = []
touches = ["tests/live_qualification.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "The audit adopted five reliability fixes, and their deterministic tests do not exercise the real process, filesystem or remote path. Build tests/live_qualification.py as one on-demand harness with five scenarios, each in a disposable Git repository and state, removed afterwards. A: a real push to a local bare remote whose pre-receive hook stalls past the engine's 300 s timeout, then the remote reconciliation; no real remote. B: a torn BLOCKERS.md (start marker, no end marker) and a failed replacement/commit, then the real questions.update, common.atomic_write and store_questions recovery. C: real dispatch with a legacy prose grant (waits), a structured grant (dispatches), a foreign scope (refused) and a worker edit to tasks/ (held). D: real dispatch with a paused or answered attempt beside a full pool (N+1), and an exclusive or serial holder that is not bypassed. E: one real dispatch with a stub worker, then a resume; inspect provenance.jsonl for the prompt hash, append-only prefix, null missing values and the absence of prompt or environment text. The harness prints one JSON object per scenario, exits nonzero on failure, and reports any product defect instead of changing the expectation. It uses no model, credential, production remote, service or checkout. A model-driven delivery and a live interrupted runner remain the owner's TOOLSET-451, and the owner-deferred 30-day evaluation (TOOLSET-311) is not reopened."
acceptance = ["The harness runs all five scenarios with one command, prints one JSON object per scenario, exits 0 only when every scenario passes, and removes every temporary repository and state directory.", "A drives a real local bare remote with a stalling pre-receive hook: the push outcome is recorded as unknown without raising, the remote refs are reconciled, and a later ordinary push publishes the same fast-forward once; no real remote or force-push is used.", "B starts from a torn block and a failed replacement/commit: the previous bytes survive a failed replacement, the real recovery path repairs exactly one block and commits it, and a second pass does not rewrite it.", "C and D use the real dispatcher: a legacy grant waits, a structured grant dispatches, a foreign scope is refused, a worker edit to tasks/ is held, a paused or answered attempt starts beside a full pool (N+1), and an exclusive, serial or live holder is not bypassed; the evidence is the returned rows and reasons, not mocks of the decision.", "E launches one attempt and then a resume: the first record carries the prompt SHA-256 and no prompt or environment text, the resume appends and leaves the earlier bytes identical, and an unavailable value is null.", "The run uses no model, credential, production remote, service or production checkout, and every product defect is reported with its scenario record rather than hidden by a relaxed expectation."]
checks = ["python3 tests/live_qualification.py --all", "python3 -m py_compile tests/live_qualification.py"]
exclusions = ["No model-driven delivery, real runner interruption or production/repository write; TOOLSET-451 owns the owner's live delivery and the deferred 30-day evaluation stays closed.", "No push to a real remote, no credential, no service start or restart, and no change to another runner's state or another writer's uncommitted files.", "No product code change in this task: a failing scenario is reported as a defect with its evidence, not fixed by editing the harness's expectation."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/TOOLSET-465-936fd6b6.toml"
+++
- Sources: docs/testing.md#live-qualification-harness; docs/research/authorized-autonomy-audit-2026-11-04.md
