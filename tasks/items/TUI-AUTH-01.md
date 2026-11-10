+++
schema = 1
id = "TUI-AUTH-01"
title = "Configure Pi providers and authenticate inside the Autowork TUI"
short = "Configure Pi providers and authentica..."
status = "done"
section = "Now"
rank = 1000
depends_on = []
touches = ["pi-autowork/src/pi_autowork/", "pi-autowork/tests/runner/", "pi-autowork/scripts/", "pi-autowork/README.md", "DESIGN.md", "docs/testing.md"]
resources = ["autowork-tui-model-auth"]
kind = "implementation"
ownership = "worker"
scope = "Replace the model picker handoff to interactive Pi with provider configuration and authentication hosted by Autowork TUI. Use supported installed/pinned Pi SDK authentication and credential-storage contracts, without a parallel auth store. Present available providers even when no models are authenticated, distinguish authentication state, support SDK-supported OAuth and API-key methods with masked input, explicit progress/cancel/failure and automatic model refresh on success. Use the exact selected runner/new-runner PI_CODING_AGENT_DIR throughout; preserve current provider/model choices on cancellation and stale results. Do not require opening the Pi CLI or adding Hermes/Nous. No model call, service start/restart or authentication runs merely from opening the picker."
acceptance = ["From an empty authenticated model catalog, the TUI shows configurable Pi providers and completes supported authentication using in-TUI guidance/secret input and browser OAuth only where required by provider; no manual Pi /login step or Pi interactive terminal is launched.", "Use official Pi auth persistence in the selected profile. Secrets remain masked, absent from logs/errors/task records/argv and never prefilled from private storage. Refresh lists after successful login and preserve model/profile identity across cancellations, stale callbacks and runner switches.", "Pinned offline mocked SDK/OAuth/API-key fixtures exercise success, cancellation, invalid credentials, unavailable provider/helper and empty catalog. Bounded Textual pilots at60x18,80x24,120x32 prove keyboard navigation, visible errors/progress, secret masking and unchanged read-only/browser restrictions without live authentication or service/model operations.", "Existing model-selection and TUI reader/control tests plus focused new bridge/auth tests pass; update product docs, independently review actual implementation and report source checks separately from real user/provider qualification."]
checks = ["python3 scripts/check.py pi-autowork/tests/runner/test_tui_models.py pi-autowork/tests/runner/test_tui_reads.py pi-autowork/tests/runner/test_tui_controls.py", "Run task-owned focused offline auth bridge/provider fixtures and pinned Textual pilots", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No actual account login, production credentials, model calls, credential migrations/deletions, Hermes/Nous setup, service installation/start/restart or upstream Pi edits during implementation/testing. User-initiated authentication in the finished product is the intended feature.", "No dependency upgrades, parallel credential store, hard-coded provider/model defaults, weakened read-only/identity guards or unrelated worktree edits."]
closure = "manual"
closure_actor = "interactive-codex"
closure_timestamp = "2026-11-10T19:03:36.029766+00:00"
closure_reason = "Implemented provider catalog and SDK-owned in-TUI OAuth/API-key authentication, masked stdin prompts, explicit browser action, cancellation and profile identity guards. Focused suites and compact/wide pilots passed; independent review completed and provider-guidance finding repaired with13 passing affected tests. Matching official1.5.0 SDK prepared; no real account/model/service operation or live provider qualification claimed."
closure_evidence = "89877429; /tmp/kit-tui-auth-review-fix.log; pi-autowork/tests/runner/test_pi_auth.py; pi-autowork/tests/runner/test_tui_models.py"
+++
