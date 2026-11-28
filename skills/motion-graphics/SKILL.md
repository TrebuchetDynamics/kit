---
name: motion-graphics
description: "Build and render seekable motion graphics."
license: MIT
---

# Motion graphics

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[communication rules](../shared/COMMUNICATION.md). Load the recipes and
capture procedure only when the user selects `/motion-graphics`.

1. **Brief.** Agree on the subject, viewport, duration, loop or hold, deliverable
   and real content. Keep project branding, tokens, framework and motion constraints.
   Select one [timeline recipe](references/recipes.md) for a new artifact; skip the
   recipe for a check of existing HTML. Upstream sizes, timings and tools are advice.
2. **Build.** For an authorized build, deliver self-contained HTML. Implement
   `window.seek(seconds)` to update the whole frame synchronously from the requested
   time alone, in any order. Freeze all playback under `?render`; use no independent
   CSS timers, elapsed time or unseeded randomness. For a loop, map the duration to
   the same frame as zero; for a hold, keep the intended final state. Respect
   reduced-motion behavior outside capture mode.
3. **Verify.** Use the [capture and export procedure](references/capture.md) for
   renders. Seek to scene changes and moving intervals, not just held frames. Inspect
   the PNGs for composition and legibility. Report the times, paths, verdict and
   any missing prerequisites; only encode the requested formats.

[Source pin and hashes](UPSTREAM.json) · [Motion Graphics Skills MIT](upstream/LICENSE).

## Boundaries

- `/genjutsu` designs motion for an application's interactions; `/ui-taste` remains
  the default for unnamed UI work.
- A brief is not permission to build. Use `/plan-for-me` for an authorized planning
  handoff; do not run upstream setup, publish media, or install a runtime from this skill.

**Done when:** the brief is returned or the requested artifact is delivered with its
actual seek, visual and export results and any unmet checks clearly identified.
