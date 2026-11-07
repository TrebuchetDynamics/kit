+++
schema = 1
id = "TOOLSET-475-deac848e"
title = "Deliver continuous in-session Work across portable hosts"
short = "Ship in-session Work registration"
status = "open"
goal = "SKILL-ADHERENCE"
section = "Now"
rank = 1000
depends_on = []
touches = ["skills/work/SKILL.md", "adapters/skills/work/SKILL.md", "adapters/skills/work/agents/openai.yaml", "adapters/pi.mjs", "adapters/skills/autowork/SKILL.md", "skills/autowork/SKILL.md", "skills/autowork/references/iteration-and-decisions.md", "skills/ask-kit/SKILL.md", "README.md", "docs/cross-host.md", "docs/workflows.md", "tests/portable_pi.test.mjs", "tests/test_portable_package.py", "tests/test_skill_standard.py"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Forward-port the already-authored and reviewed idle .worktrees/work-skill candidate onto current main without overwriting newer push/unblock routes or decision-handoff guidance. Deliver host-neutral Work, explicit-only portable/Codex metadata, native Pi work command, router and canonical docs. Work auto-selects, executes, verifies, closes and continues in the current target repository; gated queues trigger bounded useful offline discovery. Preserve caller limits, actual leases, live/owner gates and service-first portable Autowork. Correct manual-close instructions consistently; no engine or service behavior change."
acceptance = ["Portable package and native Pi tests prove work is registered with literal arguments/current-session routing, and metadata is explicit-only on supported hosts without install hooks, model calls or permission changes.", "Instruction contracts prove automatic selection, continued execution, bounded discovery when gated, source-bound checks/manual close, fresh-context reviews and real authority/ownership stop conditions; current push/unblock and all research selectors remain intact."]
checks = ["python3 scripts/check.py tests/test_portable_package.py tests/test_skill_standard.py tests/test_workflow_commands.py tests/test_skill_descriptions.py tests/test_repo_docs_graphify.py", "node --test tests/portable_pi.test.mjs", "python3 skills/docs-sync/scripts/docs.py check .", "git diff --check"]
exclusions = ["No background worker/service start, restart, schedules, installation, push, deployment, live qualification or permission/credential changes. Leave Kit runner stopped as explicitly requested.", "Do not mutate owner-only/live-gated task463, adopt foreign dirty work or overwrite newer main behavior. Preserve the original dirty work-skill candidate as recovery evidence."]
+++
- Sources: User's repeated explicit in-session /work request and accepted retained .worktrees/work-skill implementation; docs/workflows.md Work section will own published semantics.
- Evidence: Main8ba668ef lacks skills/work and adapters/skills/work, adapters/pi.mjs omits work; user currently invokes a worktree-local pointer. Existing candidate was previously reviewed but never integrated. Runtime ownership barrier was resolved by explicit owner-authorized stop of only Kit runner; no restart authorized.
- Work search: Selected portable workflow/registration delivery over ownerlive463 (typed denied), transactional-answer backend (active other writer), or novel work where already-reviewed useful implementation exists. No competing background worker launched.
- Repo obligations triggered: Portable manifests discover adapter folder automatically; native Pi command table, router/docs, command count/package inventory and instruction guards must agree. No manifest/lock/CI/schema changes needed. Current push/unblock and shared handoff guidance are invariants. Checks are offline contract evidence, not model adherence/native deployment proof.