+++
schema = 1
id = "TOOLSET-462-9f8caaab"
title = "Bind publication and restart to the verified release and configuration"
short = "Bind authority to the verified release"
status = "open"
goal = "RELIABILITY-2026-10"
section = "Next"
rank = 5000
depends_on = []
touches = ["Src/pi_autowork/cli.py", "Src/pi_autowork/service.py", "Src/pi_autowork/coordinator.py", "scripts/pi-autowork.sh", "tests/test_autowork_command.py", "tests/test_autowork_push_setting.py", "tests/test_pi_autowork.py", "pi-autowork/README.md", "docs/cross-host.md", "CHANGELOG.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "A running coordinator can keep authority that its current configuration no longer permits. Observed 2026-11-04: after a deliberate `autowork stop`, the unit was left in `failed`; `Restart=on-failure` started the previous release (ecc6aa80, publication default 1) at 19:28:59, and that process published main to origin at 19:51:51 after the repository already contained the opt-in fix. Separately, a one-time push ran while HEAD moved from the verified ec1f6dd6 to 262595d6, publishing a revision that was not the verified one. Make a running coordinator's authority bound to what was verified: (1) a deliberate stop is terminal for authority; the unit must not revive the previous release for a deliberate stop, and any restart re-resolves the release and re-asserts the effective PI_AUTOWORK_PUSH from its verified saved configuration before the first cycle, refusing dispatch when it cannot prove them; (2) publication is bound to the verified revision and grant; a push records the verified HEAD, release and effective grant and refuses when any differs, so it cannot publish unverified commits. Refuse to start dispatch or publish when the release or configuration cannot be confirmed."
acceptance = ["A deliberate stop cannot be followed by an automatic restart that runs the previous release or push grant; a restarted runner re-resolves the release and re-asserts PI_AUTOWORK_PUSH from the saved configuration before its first cycle.", "The runner refuses dispatch with a named reason when its running release or effective push grant differs from the recorded verified configuration; no task runs under an unconfirmed configuration.", "A push refuses when HEAD, the resolved release or the effective grant differs from the verified values and names both; an unknown push outcome still reconciles from the recorded revision and never force-pushes.", "Deterministic tests cover a deliberate stop versus a failure restart, a release changed under a running unit, HEAD moved between verification and push, a grant changed between start and push, and an unconfirmed configuration refusing dispatch.", "Publication stays opt-in (PI_AUTOWORK_PUSH=1 only); no default, global setting, other runner's state or force-push changes, and no live qualification is claimed from the offline tests."]
checks = ["python3 scripts/check.py tests/test_autowork_command.py tests/test_autowork_push_setting.py tests/test_pi_autowork.py", "python3 skills/docs-sync/scripts/docs.py check ."]
exclusions = ["No push, publication or deployment as part of the task; publication remains opt-in.", "No global model, credential, permission or approval-policy change and no modification of another runner's state.", "No force-push and no widening of the existing ownership, lease, lock or review gates; the live stop and restart are verified by the owner, not by the runner."]
+++
- Sources: docs/research/authorized-autonomy-audit-2026-11-04.md#2-durable-effects-and-crash-recovery
