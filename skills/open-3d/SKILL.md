---
name: open-3d
description: "Build, check and capture procedural browser 3D scenes."
license: MIT
---

# Open 3D

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[communication rules](../shared/COMMUNICATION.md).

1. **Scope.** Use this workflow only on explicit selection. Retain the project's
   branding, tokens, framework and motion constraints. If the result is unclear,
   ask which scene, check or artifact the user wants.
2. **Select.** Read only the matching pinned protocol. Follow another row only
   when the requested result needs it. These are references, not slash commands.

   | Requested work | Protocol |
   | --- | --- |
   | Build procedural Three.js geometry, lighting or camera | [Scene](upstream/skills/threejs-scene/PROTOCOL.md) |
   | Separate, label or section model parts | [Exploded view](upstream/skills/exploded-view/PROTOCOL.md) |
   | Link film playback to scroll | [Scroll film](upstream/skills/scroll-film/PROTOCOL.md) |
   | Plan clips, check loops or composite motion | [Motion assets](upstream/skills/motion-assets/PROTOCOL.md) |
   | Key a clip to produce transparency | [Alpha cutout](upstream/skills/alpha-cutout/PROTOCOL.md) |
   | Build cursor-following motion | [Cursor rig](upstream/skills/cursor-rig/PROTOCOL.md) |
   | Check viewports, motion and rendering errors | [Site check](upstream/skills/site-check/PROTOCOL.md) |
   | Record a timeline or compare clips | [Frame capture](upstream/skills/frame-capture/PROTOCOL.md) |

3. **Preflight.** Follow the [operation checks and capture commands](references/runtime.md)
   before running helpers. Those instructions take precedence over upstream setup
   and recorder paths. Report missing requirements without installing anything.
4. **Verify.** Follow the [shared GUI decision](../shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence).
   Inspect the requested viewport states or output frames. Report encoded fps
   separately from headless browser observations; neither measures device performance.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE)

## Boundaries

- For unnamed UI work, use `/ui-taste`. For a seekable non-3D motion artifact, use `/motion-graphics`.
- Follow existing tool, network and spending permissions; upstream recommendations do not grant access.

**Done when:** the selected artifact or check has observed evidence, or the report names the failed check, repair action and unmet criterion.
