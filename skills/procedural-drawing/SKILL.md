---
name: procedural-drawing
description: "Draw CPU-rendered illustrations from scene code."
license: MIT
---

# Procedural Drawing

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[communication rules](../shared/COMMUNICATION.md).

1. **Select.** Only run on explicit selection. Search the [style index](styles.md)
   for the requested look. Open the matching library and scene example only.
   They are pinned upstream material ([source record](UPSTREAM.json),
   [MIT license](upstream/LICENSE)). Use their defaults only where the project
   has not supplied branding, tokens, framework choices or motion constraints.
2. **Preflight.** Use Python 3 with [NumPy and Pillow](upstream/requirements.txt).
   Run `python3 -B <skill>/scripts/preflight.py --format png` with the same Python
   as the scene ([script](scripts/preflight.py)). List only the required formats
   (`png`, `jpeg`, `gif`); include `png` if saving stages. For text, resolve the
   actual font files used by the selected scene and pass `--font PATH` for each.
   Record those files with the scene rather than relying on fallback fonts.
   For external video encoding, check the existing encoder (for example, list
   encoders with `ffmpeg -hide_banner -encoders`). Missing dependencies leave the
   affected operation unverified; report them and let the user prepare them.
3. **Render.** Adapt the selected example in the project, preserving its library
   imports and recording the seed, dimensions and runtime versions. Check the
   rendered result twice with identical inputs; compare decoded pixels. Use the
   [shared GUI decision](../shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence)
   and open the result before making visual claims. Report the scene, output,
   seed and results of the checks you ran.

## Boundaries

- For seeded browser sketches, use `/genart`. For unnamed UI work, use `/ui-taste`.

**Done when:** the scene and artifact have a same-environment repeatability result,
or the missing prerequisite or failed comparison is reported.
