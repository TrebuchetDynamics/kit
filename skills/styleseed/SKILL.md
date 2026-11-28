---
name: styleseed
description: "Create and maintain a project design system."
license: MIT
---

# StyleSeed

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and the
[communication rules](../shared/COMMUNICATION.md).

1. **Select.** On explicit invocation, read the [pinned StyleSeed protocol](upstream/skills/styleseed/PROTOCOL.md)
   and only the internal workflow it selects. Resolve scripts and `engine/` references from
   the bundled runtime. Treat `ss-*` as internal workflow names, not host commands.
2. **Preflight.** From the project root, run the [local check](upstream/skills/styleseed/preflight.mjs)
   with Node.js 22+. This checks the Kit payload instead of the upstream remote update preflight.
   Add `--render` for the shipped Playwright probes or `--record` to also test Playwright's
   FFmpeg encoder. Use the project's existing `playwright`, `STYLESEED_BROWSER_MODULE`,
   or `--browser PATH`. For a different project renderer or encoder, check that exact
   tool instead; confirm the actual fonts in the render, not just their CSS names.
   Report missing capabilities and leave those checks unmet. Use `/update-kit` for
   an authorized Kit refresh; do not run upstream installers or consolidation.
3. **Resolve.** Use `--agent pi` on Pi and `--agent hermes` on Hermes when compiling
   or checking bundles; on other hosts use their existing mapping. Preserve approved
   tokens (import the project's token canon where supported), branding, stack and motion
   constraints. If a choice cannot be represented, report the gap and keep the existing
   choice. Do not apply setup defaults over it or install a scaffold or provider.
4. **Verify.** Run the selected checks against the actual artifact. Report paths to the
   rules, tokens, and proof you produced, and distinguish compilation from rendering.

## Boundaries

- Use `/brand-identity` for brand directions and assets; `/ui-taste` remains the default for unnamed UI work.
- Review and status requests do not authorize design changes, recompilation or refresh.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE) · [Third-party information](upstream/THIRD_PARTY.md).

**Done when:** the selected workflow reports its result and check outcomes without overwriting approved project choices or claiming missing evidence.
