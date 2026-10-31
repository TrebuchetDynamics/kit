+++
schema = 1
id = "TOOLSET-421-770cf9d0"
title = "Add a responsive screenshot workflow with verified captures"
short = "Add responsive capture workflow"
status = "open"
goal = "SKILL-STYLE"
section = "Now"
rank = 1000
depends_on = []
touches = ["skills/responsive-screenshots", "adapters/skills/responsive-screenshots", "adapters/pi.mjs", "skills/ask-autowork/SKILL.md", "docs/workflows.md", "docs/cross-host.md", "README.md", "CHANGELOG.md", "tests"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Add an original responsive-screenshot skill with a bundled capture helper, an explicit-only portable adapter on all four hosts, a Pi command, documentation and an offline contract test. The upstream repository that inspired it states no license, so copy no bytes: write the workflow and the helper, and record the provenance in SOURCES.md. The helper must verify what it captured instead of trusting a file's existence, and must install nothing."
acceptance = ["skills/responsive-screenshots states scope, matrix, verification, safety, Boundaries with real siblings and one checkable Done when; SOURCES.md records the inspiration, revision and the no-license decision; the adapter links the native workflow and stays explicit-only.", "scripts/capture.py fixes viewport, device scale, color scheme and reduced motion, waits on network idle, selector and fonts, refuses credential URLs, reports real pixel sizes plus horizontal overflow from two signals, fails a truncated capture, and writes report.md and captures.json with exit codes 0, 1 and 2.", "A live capture run against a local fixture captured 6 of 6 at 375, 768 and 1440 in both schemes with no overflow, and a deliberately wide fixture reported overflow and exited 2 under --fail-on-overflow. Offline checks pass: the new contract test, skill standard, descriptions, portable package, doctor, plugin, bundle, workflow commands and node --test tests/portable_pi.test.mjs. Browser independence and real-site rendering stay unverified by those tests."]
checks = ["python3 scripts/check.py tests/test_responsive_screenshots.py tests/test_skill_standard.py tests/test_portable_package.py", "node --test tests/portable_pi.test.mjs", "python3 skills/responsive-screenshots/scripts/capture.py file:///tmp/rs/ok.html --out /tmp/rs/final --scheme both"]
exclusions = ["No upstream bytes copied, no browser or dependency install, no credentialed or production capture, no committed screenshots, no design review, no publication."]
+++
