---
name: genjutsu
description: "Design interaction motion for an interface."
license: MIT
---

# Genjutsu

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[communication rules](../shared/COMMUNICATION.md).

1. **Ground.** Identify the interaction, the current stack and the requested scope.
   Keep the project's branding, tokens, framework and motion constraints. Use the
   upstream playbooks as reference; Kit owns permissions, planning and delivery.
2. **Select.** Read [cast](upstream/skills/cast/PROTOCOL.md) for existing UI motion,
   or [paint](upstream/skills/paint/PROTOCOL.md) for an explicitly requested new
   direction. Read [bunshin](upstream/skills/bunshin/PROTOCOL.md) only for an explicitly
   requested or accepted whole-site team workflow with a real delegation tool.
   Otherwise, use the single-session playbook that fits and report the limitation.
3. **Load.** Start with [motion principles](upstream/skills/_jutsu/motion-principles/PROTOCOL.md).
   For a module named by the playbook, read its `PROTOCOL.md` under
   `upstream/skills/_jutsu/<module>/` and only its relevant references. Read the
   UI/UX data only for the design question at hand. Resolve paths from this skill;
   skip upstream shell loaders, automation, installs and host-specific tool calls.
4. **Apply.** Return a motion brief by default: trigger, start and end states,
   timing, interruption behavior and reduced-motion treatment. For an authorized
   edit, use the existing stack and verify the interaction and reduced-motion state.
   Delegate only if the selected workflow calls for it and this session has the
   needed tools. Give each child a fresh context, scope, completion criterion,
   and read-only or explicit write limits. Preserve checkout ownership and required
   review; do not install a host extension to gain delegation or visual evidence.

[Source pin and hashes](UPSTREAM.json) · [Genjutsu MIT](upstream/LICENSE) ·
[UI/UX Pro Max MIT](upstream/skills/_jutsu/ui-ux-pro-max/LICENSE-upstream.txt).

## Boundaries

- `/ui-taste` remains the default for unnamed UI work; `/motion-graphics` builds
  seekable timeline artifacts rather than app interactions.
- If the request is planning, stop at the brief or the authorized `/plan-for-me`
  GitHub Issue handoff. Do not let an upstream build stage start implementation.
- Briefs need no runtime. For edits, use the project's existing checks and the host's
  available preview tools. Report missing tools or fonts, the repair, and the visual
  checks you could not run. Do not claim real-device performance.

**Done when:** the brief or scoped edit records the selected playbook, motion states,
reduced-motion treatment, and which checks ran or remain unmet.
