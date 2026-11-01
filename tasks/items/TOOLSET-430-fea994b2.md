+++
schema = 1
id = "TOOLSET-430-fea994b2"
title = "Kit rename stage 3: documentation and installer prose"
short = "Sweep docs to Kit"
status = "open"
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
+++
