+++
schema = 1
id = "TOOLSET-507"
title = "Preserve tx config when alias mutations are invalid"
short = "Invalid alias updates preserve tx config"
status = "done"
section = "Now"
rank = 21000
depends_on = []
touches = ["tmux/tx", "tmux/README.md", "tests/test_tx.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Validate alias additions and renames inside the existing config module, then validate the complete staged config before atomic publication. Invalid mutations must leave the original config unchanged. Preserve valid commands, comments, variables, formatting, and prefix selection."
acceptance = ["Duplicate alias additions and multi-alias renames fail before changing the original config; regression tests check byte equality and a successful reload after rejection.", "The config writer rejects an invalid complete candidate before publication and removes its staging file.", "Valid add, edit, and remove operations preserve comments, variables, ordering, and CRLF behavior."]
checks = ["python3 -m unittest discover -s tests -p test_tx.py", "bash -n tmux/tx", "git diff --check -- tmux/tx tmux/README.md tests/test_tx.py"]
exclusions = ["No installation, commit, push, unrelated completion or installation changes, concurrent-writer locking, or config grammar redesign."]
closure = "coordinator_verified"
closure_evidence = "tasks/evidence/TOOLSET-507.toml"
+++
- Sources: docs/plans/tx-architecture-2026-11-01.md; owner-approved architecture candidate 1 in the current conversation.
- Owner decision: Implement only config integrity. Do not install or commit.
- Candidate: Local changes in tmux/tx, tests/test_tx.py and tmux/README.md validate staged configs before publication, reject duplicate additions and multi-alias renames, and clean staging files on failure. Existing staged completion changes were preserved.
- Evidence: The original tx source (SHA-256 00a66a61f9eeddd6f59075aa80cf66c14b773e9d632ca9515db1f27041cb6ea4) fails nine mutation/publication regression cases. The current source (5a19d69d99bd2d0fa5a4c18b406b4ed6d09143777daf7eb63091a6adb9e67b13) passes all 16 tests in python3 -m unittest discover -s tests -p test_tx.py. bash -n tmux/tx and the scoped git diff --check pass. A temporary-directory CLI check also passed additions, explicit and prompted renames, prefix removal/resolution, paths with spaces, variables, comments and staging cleanup.
- Review: Self-review traced config_write and its callers, validation failure paths, staging cleanup, and valid mutation preservation. Independent review is unavailable in this host. Concurrent writer locking and live tmux behavior were not checked.
- Documentation: Updated tmux/README.md with uniqueness, single-alias rename and validation-failure guarantees.
- Reuse: Kept the existing parser, config module and tests. Removed adapter-owned duplicate checks; added no library, dependency, install change or concurrency mechanism. Other architecture candidates remain outside this task.
- Next action: Review the uncommitted candidate and its checks; integration and task closure remain pending. Do not replay implementation. Commit and installation require later owner authorization.