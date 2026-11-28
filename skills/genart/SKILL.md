---
name: genart
description: "Create and verify seeded generative art."
license: MIT
---

# Genart

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[communication rules](../shared/COMMUNICATION.md).

1. **Select.** Only run on explicit selection. Use the pinned
   [protocol](upstream/PROTOCOL.md) for design guidance. For seeding, read
   [determinism](upstream/references/determinism.md); open only the relevant
   references for other requested work. Preserve supplied branding, tokens,
   frameworks and motion constraints ahead of upstream defaults.
2. **Check.** For a local Canvas 2D sketch, use Kit's
   [render contract and verifier](canvas.md) instead of upstream's install and
   harness instructions. Run the check with existing dependencies. When a
   prerequisite is missing, report it without installing it.
3. **Report.** Include the seeds, environment and comparison results. Apply the
   [shared GUI decision](../shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence)
   and inspect real renders before making visual claims. SVG is manual only:
   inspect the source and local renders; the Canvas verifier checks neither SVG
   serialization nor SVG pixels.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE)

## Boundaries

- For NumPy/Pillow illustrated scenes, use `/procedural-drawing`. For unnamed
  UI work, use `/ui-taste`.
- Local checks do not qualify external publishing, browser parity or devices.

**Done when:** the comparison result or the specific unmet check is reported.
