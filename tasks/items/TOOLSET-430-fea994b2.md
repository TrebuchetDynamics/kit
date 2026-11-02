+++
schema = 1
id = "TOOLSET-430-fea994b2"
title = "Kit rename stage 3: documentation and installer prose"
short = "Sweep docs to Kit"
status = "done"
goal = "DOCS-PROVENANCE"
section = "Next"
rank = 3000
depends_on = ["TOOLSET-429-6a727853"]
touches = ["README.md", "docs", "plugins/PLUGINS.md", "install.sh", "install-plugins.sh", "CHANGELOG.md"]
resources = []
kind = "plan"
ownership = "worker"
scope = "Third stage of docs/plans/2026-11-01-rename-to-kit.md, after stage 2. Rewrite every reader-facing reference to the plugin name and command namespace: README first screen, installation, cross-host, workflows, onboarding, reference, uninstall, troubleshooting, plugins/PLUGINS.md, the install.sh and install-plugins.sh labels, plus a migration note naming plugins.entries.autowork and the release that drops it. Keep every autowork reference that means the runner."
acceptance = ["Every documented skill command uses the kit namespace, and every remaining autowork mention means the runner, its CLI or its state directory: a reader can tell the two apart from the page they are on.", "The docs name the old settings key, the new one and the release that removes the fallback, so an upgrading owner knows their opt-out still applies.", "Link, docs-manifest and packaging checks pass, and the documentation review confirms no safety, policy or evidence statement was reworded while renaming."]
checks = ["python3 skills/docs-sync/scripts/docs.py check .", "python3 scripts/check.py tests/test_repo_docs_graphify.py tests/test_portable_package.py"]
exclusions = ["No code, manifest or test sweep; no safety or policy rewording; no live profile write; no publication."]
closure = "manual"
closure_actor = "interactive session doing the docs sweep by hand"
closure_timestamp = "2026-11-02T03:21:48.450100+00:00"
closure_reason = "Stage 3 landed. Reader-facing text now names Kit: README first screen (Kit is the toolset, Autowork is the runner), installation, cross-host, workflows, reference, uninstall and troubleshooting, with /kit: and $kit: examples and plugins.entries.kit as the canonical settings key plus one migration note stating the legacy key keeps being read for a release. Also closed the fresh-install question the plan flagged: update_bundle.plugin_dir prefers an existing directory whose manifest matches, so a native install under plugins/kit is recognized instead of duplicated as plugins/autowork, and hermes plugins enable receives the manifest name; three fixtures cover legacy, renamed and absent installs. Repaired two check breaks that were not mine but blocked main: the doctor fixture now derives plugin skills from disk instead of a hardcoded list, and the new goal adapter gained the shared Ponytail and language links. Verified: full offline check 5 directories 0 failures 3 excluded, node --test tests/portable_pi.test.mjs 4/4, and docs.py check ok. Stage 4 (repository rename, npm publish, live pre-rename profile proof) remains owner-gated."
closure_evidence = "python3 scripts/check.py; node --test tests/portable_pi.test.mjs; python3 skills/docs-sync/scripts/docs.py check .; commit b93548b1"
+++
- Held by: interactive session doing the docs sweep by hand; until 2026-11-02
