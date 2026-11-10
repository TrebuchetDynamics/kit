+++
schema = 1
id = "TOOLSET-498"
title = "Isolate concurrent batch tip pointers and verification artifacts"
short = "Isolate concurrent batch artifacts"
status = "done"
section = "Now"
rank = 15000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/coordinator.py", "pi-autowork/src/pi_autowork/worker.py", "pi-autowork/tests/runner/test_worker_tmp.py", "pi-autowork/README.md"]
resources = []
kind = "implementation"
ownership = "coordinator"
scope = "Fix two deterministic namespace collisions for future batch jobs only. Preserve the full unique NamedTemporaryFile basename when deriving its .tip path instead of replacing its random suffix. Give batch full-suite logs/status/rerun artifacts a generation-specific label, shared consistently by gate execution and gate-note lookup; use process identity for legacy direct invocations without a generation. Keep existing immutable tree receipt reuse, generation/admission/source bindings, cleanup proof, concurrency, review and timeout policy. Do not touch current runtime job files or interrupt existing batches."
acceptance = ["A focused test starts an initial batch and merge-train car with a mocked producer and proves distinct tip paths bound to their respective outputs/generations; writing one pointer cannot replace the other.", "A focused test runs the gate path for two generations with local stubbed checks and proves distinct producing artifact labels and consistent note lookup, preserving both sentinel logs. Existing worker scratch, batch closure/publication, receipt and train tests pass; README identifies per-generation tip/check artifacts."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_worker_tmp.py", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No edits to existing runtime pointers/logs/receipts, slots, live contracts, pauses, settings or grants. No forced restart, duplicate verification of live candidates, deployment or gate bypass."]
closure = "manual"
closure_actor = "current-debug-coordinator"
closure_timestamp = "2026-11-10T09:08:09.338177+00:00"
closure_reason = "Offline concurrent batch artifact collisions reproduced and repaired. Both new regressions failed on shared paths; all 74 worker scratch/batch tests, source guard, strict mypy, docs and whitespace passed. Independent review approved. Existing runtime jobs untouched; installed/live qualification remains pending."
closure_evidence = "commit 7cc80714f37cd53d12e2c6b7ff88ac27c3bd1a35; /tmp/kit-batch-namespace-green.log"
+++
- Sources: Recurring user-authorized debug; coordinator.start_batch; worker.batch_gate; README immutable batch publications.
- Evidence: Concurrent initial batch and train used different runs/batch.<random> outputs, but Path.with_suffix('.tip') collapses both to runs/batch.tip. Actual batch.tip was overwritten with the train tip. Both batch_gate calls also use full_suite_gate(state,'batch',...), sharing batch-merged logs, rerun inventories, gate events and status. The observed gate files contained interleaved failures/status from concurrent producers. Existing tree receipts remain separately bound; no false acceptance is inferred.
- Planner call: Reuse existing unpredictable generation for check labels and preserve the unique output filename for tips. No new registry, parser, state migration or queue is needed. Legacy direct calls get a PID-scoped label.
- First action: Add two failing isolated regressions at the existing worker test seam, then implement and review the bounded fix. Keep this new record uncommitted on main until offline closure, preventing the known-unfixed coordinator-ownership admission path from dispatching a duplicate.
- Ownership: Parent debug session owns .worktrees/fix-batch-job-namespace; current initial/train jobs and worker checkouts remain untouched. Offline implementation does not qualify installed/live behavior.