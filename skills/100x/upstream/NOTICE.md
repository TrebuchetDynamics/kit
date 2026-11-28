# Notices

100x reuses ideas, structure and some wording from pstack under the MIT License. This file lists what came from where, and carries the upstream license text.

## pstack

- Source: https://github.com/cursor/plugins/tree/main/pstack
- Pinned commit: `bf0c7cd80abdbf7fe47b634978a7d1b4071f71a7` (version 0.15.42)
- Copyright (c) 2026 Lauren Tan

Adapted from pstack.

- The decisions log columns and writing rules, from the `show-me-your-work` skill. See `skills/100x/references/decisions.md` and `lib/decisions.mjs`.
- The unattended run skeleton (exit predicate first, one row per iteration), from the `autonomous-run` playbook. See `skills/100x/references/unattended.md`.
- The working rules in the router (restate the goal, label claims, never block on the human, run it instead of asking), from `poteto-mode`. See `skills/100x/SKILL.md`.
- The principle summaries in `skills/100x/references/principles.md`, condensed from the principle skills.

Not taken from pstack. Delegated implementation, swarm and arena panels, per-role subagent models, pull request endings.

### pstack license

```
MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## unslop-text

It is the owner's own project (MIT), in its own repository. A pinned copy of the folder it publishes as a skill ships in `vendor/`, unmodified, and `companions.json` records the commit. The pinned folder holds the skill only, so it carries no license file of its own. The MIT License of that project covers its folder here, as the MIT License of this repository covers the rest. Change it in its own repository, then run `node scripts/vendor-companions.mjs`.
