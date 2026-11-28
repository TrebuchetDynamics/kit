---
name: brand-identity
description: "Compare brand directions and build the selected kit."
license: MIT
---

# Brand Identity

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and the
[communication rules](../shared/COMMUNICATION.md).

1. **Scope.** Read the [pinned protocol](upstream/PROTOCOL.md) on explicit selection only.
   Load its references from `upstream/` as needed. Treat supplied approved marks,
   colors and type as `keep`; do not use defaults or reopen selection for these parts.
2. **Preflight.** Run the [Kit capability check](upstream/scripts/preflight.py) with the same
   Python 3.10+ interpreter as [`brand.py`](upstream/scripts/brand.py). Intake and catalog
   search need no flags. Add `--render` for browser-backed boards, site work and PDFs;
   `--type` for font audits and variable-font instancing, and `--outlines` for
   logo variants and wordmark outlines (includes type). Bind the selected faces to
   licensed local files and check each with `--font PATH`. For a PDF kit with type
   and logo assets, combine `--render --outlines` and the font paths.
   Use a prepared interpreter with the [Python requirements](upstream/requirements.txt).
   Chromium produces PNG and PDF directly; no separate encoder is needed. Run plain
   Python with a bounded shell timeout; ignore the protocol's `uv` bootstrap advice.
   On failure, report the diagnostic and stop the affected operation without
   installing anything or substituting artwork or type.
3. **Compare.** When there is a choice to make, present labeled sets with the same
   specimens and comparison axes. Inspect the board and show the tradeoffs and checks.
   Stop before final export until the user selects a set or combination.
4. **Deliver.** Record the selected set ID and its source paths in the handoff. Use
   `brand.py kit SET_DIR` for that exact set only, or use the supplied approved identity
   as the source. Preserve original inputs. Compare the exported marks, palette and
   type with the approved source; report paths and any checks not run.

## Boundaries

- Use `/styleseed` for the project's reusable design system and `/ui-taste` for UI work that names no design skill.
- A read-only request produces findings, not a generated kit or changes to a site.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE) · [Third-party notices](upstream/THIRD_PARTY_NOTICES.md).

**Done when:** requested findings or comparable directions are delivered, or the selected kit is verified against its approved source; identify any operation blocked by a missing prerequisite.
