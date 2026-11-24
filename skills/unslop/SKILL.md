---
name: unslop
description: "Turn a UI design audit into GitHub issues for Orbi."
license: CC-BY-4.0
---

# Unslop

Adapted from [unslop by Damir Sokolovsky (@heydamir)](https://github.com/heydamir/unslop/tree/620163eedb3529d9cd23a3994ed8d287d06f760d), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This version turns the design passes into issue planning instead of applying the redesign.

Apply the [Ponytail method](../shared/PONYTAIL.md), [communication rules](../shared/COMMUNICATION.md) and [planning authority contract](../shared/RESEARCH-PLAN.md#planning-artifact-and-authority-contract).

For GUI inspection or visual findings, apply the [shared GUI decision](../shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence) within this planning-only scope.

1. **Find the screen and its job.** Work in the target repository. Use the named flow, screenshot or component; on a bare invocation, inspect the main user-facing flow. Read the project's design decisions and compare the UI with its audience's task. Identify the route, state, viewport and source for each finding. Distinguish what you saw from what you inferred from code. If there is no UI evidence, ask for a route or screenshot rather than inventing a redesign.
2. **Size the intervention.** Name the pattern and its cost: for example, three equally prominent actions hide the one that completes checkout. Preserve features, content, section order and established identity unless the request changes them. For an isolated miss, propose a local fix. If the screen already serves its purpose, say what works; optional refinements need not become issues.
3. **Set the direction before the tickets.** For a broad redesign, describe the product and audience, intended character, a concrete place or material it evokes, one or two pieces of content to emphasize, and one signature detail. What would stop this design fitting a different product if only its name changed? Reuse an accepted brief; if a new brand or product choice needs its owner, show the direction and hold dependent work for that decision.
4. **Plan the changes across the screen.** Review spacing → color → icons → copy → type → layout → details → visuals → motion. Skip passes that add nothing. Group related findings by user-visible outcome, not one ticket per pass. Give each issue a location and current evidence, the chosen change, what stays intact, and a repeatable check. Use sanitized route templates and synthetic data. A screenshot shared for inspection is not permission to attach it to GitHub. For example: at 375px with a validation error, the order total and primary action remain readable without horizontal scrolling; name the route, fixture and test or manual steps to reproduce it. Include keyboard, contrast and reduced-motion checks where the proposed change affects them.
5. **Publish and stop.** Follow [Plan Handoff](../shared/PLAN-HANDOFF.md) to reuse existing work and publish the complete batch in the target repo: create under `ai-planning`, link real native `blockedBy` dependencies, verify, then publish `ai-ready` last. Respect explicit no-dispatch and live ownership. For read-only or dry-run, write nothing and show the issue proposals inline. On failure, separate verified links from **UNSAVED** proposals. If a write timed out, mark its result unverified and reconcile by stable key and current labels before retrying. Report issue URLs, dependencies, readiness and unrun visual checks; Orbi owns implementation.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| “It looks generic, so replace everything.” | Name the affected task and screen evidence first; keep what already works. |
| “The issue is ready, so the design is fixed.” | Readiness is publication, not a render, review or delivery. Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to claims. |

## Red Flags

- “Make it premium” is the only acceptance check.
- A palette, asset or UI patch is being produced instead of an issue contract.

## Boundaries

- For hands-on design, use `/ui-taste` or `/impeccable`. `/unslop` does not edit the UI, generate assets, or start Orbi.
- For general project planning, use `/plan-for-me`.

**Done when:** each supported change maps to a verified issue or a clearly held or unsaved proposal, or the audit explains why no change is warranted.
