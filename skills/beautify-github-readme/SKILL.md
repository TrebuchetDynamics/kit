---
name: beautify-github-readme
description: "Redesign or audit a GitHub README."
version: 0.1.1
license: MIT
---

# Beautify GitHub README

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

`/beautify-github-readme` (Telegram `/beautify_github_readme`) applies the pinned
[Beautify GitHub README protocol](upstream/PROTOCOL.md) by oil-oil, MIT licensed
([licence](upstream/LICENSE), [provenance](UPSTREAM.json)). This adapter controls
host integration. Read the protocol, then apply the rules below, which take
precedence over it where they differ. Its `references/` and `scripts/` paths resolve
inside `upstream/`, except its README audit: run this skill's
`scripts/audit_readme.py` instead.

## Invocation modes

- **Default: reader audit and publication.** A bare invocation or "beautify it"
  audits the current README and publishes eligible reader problems below, without a scope question.
  Analyze and publish without selection, confirmation or a second command. This
  mode authorizes neither README/asset edits nor implementation of the findings.
- **Explicit edits.** Preserve the protocol's README redesign and asset-only modes
  for requests such as "redesign the whole README" or "only a hero". Reuse scope
  already answered for the current task; corrections and repeat invocations
  continue it unless the user changes it. Ask only for consequential missing intent
  within that explicit edit scope, not before a default reader audit.
- **Explicit audit-only.** "Audit it" or report-only returns findings inline without
  edits or issue publication. For read-only/dry-run/no-write, write nothing,
  including scratch files. A no-dispatch request permits issue publication under
  `ai-planning` but withholds readiness; it does not authorize implementation.
  Scheduled, cron or unattended runs audit only unless their accepted task scope
  authorizes publication or README/asset edits.

## Reader audit and publication

1. **Trace first use.** Compare README claims and examples with current package exports,
   install instructions and documented user paths. Follow the reader from host/package
   selection through installation and the first supported action. Inspect manifests,
   export maps, authoritative guides and relevant tests. Use authoritative registry
   metadata when needed to establish published package availability; a local manifest
   alone does not prove another package nonexistent. Do not run arbitrary README commands
   as verification, install packages or start live workflows for this audit.
2. **Qualify findings.** File observable reader failures, not unaccepted design choices.
   If an install example names a nonexistent published package and repository evidence
   identifies the supported package, file the mismatch without asking about design scope.
   Include the README location, governing source, user impact, bounded correction and
   an exact validation check with its expected result. Separate observed results from
   unrun checks. A subjective branding preference alone yields no issue.
   Hold unsupported findings with the missing evidence and resume condition;
   continue independent supported findings.
3. **Reconcile and publish.** Check current source, open and closed issues, PRs and
   actual ownership before creating work. Reuse covered work; completed or owned
   outcomes create no duplicate issue. Group findings that share a fix and acceptance
   check. Follow the [single-invocation specialist handoff](../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
   for the preview, complete issue contracts, batch verification, native dependencies,
   ai-ready last and publication/partial-failure receipts. Preserve no-dispatch,
   pauses and existing live owners. Stop after publication and report verified issue
   links plus covered/held findings, or explain why zero new issues are warranted.
   Publication is not pickup, implementation or service activation.

## Toolset rules

- **The README is documentation.** Its claims, commands and safety statements are
  Docs Sync facts. A redesign may reorder and shorten copy but must not drop a
  safety or policy statement, invent adoption, benchmarks or compatibility, or
  contradict [docs](../docs-sync/SKILL.md). After editing, run
  `python3 <docs-sync-skill-dir>/scripts/docs.py check <repo>` when the repository
  has `docs/roles.json`, plus the README audit below.
  Before restructuring, record existing heading targets, command/flag semantics and
  policy disclosures; verify them after editing so moved sections do not break
  incoming links or conceal scope expansion. Put host selection, the shortest
  supported install path and a first-use smoke check before task-ledger mechanics,
  migration, recovery or contributor instructions. Use collapsible details for fleet
  setup and long task references, but keep consequential warnings visible directly
  before installation.
- **Branding restraint.** Prefer a plain project heading and real
  product proof over invented logos, oversized title banners or duplicated wordmarks.
  Beautification does not require a new asset or authorize an app-brand redesign.
  If a newly invented mark is rejected, remove it and its embed rather than making
  another unsolicited logo; remove only attributable assets and reconcile task notes
  that still describe the discarded asset as delivered.
- **Pure SVG by default.** Hermes has no bundled image-generation skill. Offer hybrid
  composition only when an image-generation tool is actually available in this
  session and the subject needs raster material; otherwise build deterministic SVG.
  GIF output stays opt-in, as in the protocol, and needs Pillow and `rsvg-convert`.
- **No unsolicited promotion.** Do not make the protocol's step 9 attribution or
  showcase offer. Handle a "README MADE WITH" signature or showcase pull request only
  when the user asks for it, with each external action separately authorized.
- **Inspect asset consumers before replacing them.** Trace README images through
  the site, capture generator and nearest contract tests. When a new title asset
  is warranted, isolate it from shared heroes rather than changing unrelated
  surfaces or forcing recapture. Keep existing capture guards intact;
  label retained older screenshots as older simulated UI, not current parity proof.
- **Preview what you ship.** Apply the
  [shared GUI decision](../shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence)
  for authorized preview interactions and visual claims, including explicit edits;
  source/CLI reader findings need no browser. Render every SVG at 900 px and 360 px wide before
  embedding it, with whatever renderer is installed (`rsvg-convert`, Inkscape or a
  headless browser), and check light and dark backgrounds. Embed with relative paths
  and meaningful `alt` text so the README still reads with images off.
  Also render the composed Markdown with an installed CommonMark renderer and headless
  browser: assert images load and the page has no horizontal overflow at both widths.
  Inspect the opening, section transitions and final links; use full-resolution crops
  when a full-page screenshot downscales text beyond readability. Call this a local
  approximation unless GitHub's actual renderer was exercised.
- **Use the local rendering stack efficiently.** Inventory Markdown CLIs as well as
  Python modules before adding dependencies; an installed `marked` can produce
  local preview HTML even when a Python Markdown package is absent. Preview with
  GitHub-like CSS, then inspect desktop and mobile page overflow, image loading
  and both folded and expanded details/code blocks. Keep wide commands and tables
  scrollable inside their blocks rather than widening the page. Label this a local
  approximation, not hosted GitHub verification. Save each browser capture to a
  distinct descriptive path before the next capture, because screenshot helpers may
  reuse one filename.
- **Delivery stays separate.** Assets go under `assets/readme/` unless the
  repository uses another location. Commit, push or open a pull request only through
  the repository's normal delivery workflow (for example
  [Git Commit Push](../git-commit-push/SKILL.md)) and its existing authority.

## Review-to-revision procedure

1. **Check the review against current source.** Read the actual README and its
   authoritative guides before applying review findings; line numbers and defects
   can describe an older revision. Fix remaining problems, retain useful visuals,
   and prefer reordering or replacing material over adding major sections.
2. **Make every advertised host actionable.** Near the first short example, provide
   a compact host/install/invocation comparison and copyable install commands.
   Label examples by interface, use one preferred spelling per interface and move
   aliases into a small reference. Distinguish portable workflows from host-only
   fleet, messaging and scheduler integration; installed adapters do not establish
   persistent background execution. Do not force readers through a separate long
   guide merely to discover the correct command prefix.
3. **Expose policy choices without changing defaults.** Put the opt-out command
   beside installation and state when it must run, such as before enabling the
   plugin. Keep it outside the default copy-paste block so following the normal
   install does not silently opt the reader out. State which side effects the
   opt-out does not cover.
4. **Validate examples against the authoring contract.** Include required fields
   such as title, scope, acceptance and checks, or label the example shortened
   and link the complete format. Align scope, acceptance, check paths and reported
   changed files. Label task/report examples illustrative, never execution receipts.
   Explain GitHub issue ordering and native dependencies, not manual
   TODO-block edits or removed task CLI commands; keep internal helper paths, revision guards
   and migration commands in references rather than implying scripts are on PATH.
5. **Describe authority and activation precisely.** Explain whether an empty queue
   permits discovery, task recording and implementation in the same invocation
   under broad development authority; retain task-limited scope boundaries.
   Separate files updated from runtime activation and link status checks for
   pending/deferred restarts rather than implying a successful write loaded code.
6. **Match verification to the advertised hosts.** Separate current package checks,
   older isolated-install evidence and live model/messaging qualification. Run
   applicable package/command tests and native manifest validation in addition to
   documentation checks; do not perform fresh installations or live workflows just
   to beautify documentation. Preview the checked candidate before integration.
   Treat GitHub About metadata as a separate external edit requiring scoped
   authority, not an automatic consequence of README permission.

Run the README audit:

```sh
python3 "<beautify-github-readme-skill-dir>/scripts/audit_readme.py" /path/to/README.md
```

It applies the protocol's SVG checks and also follows GitHub's resolution: dark-mode
`<picture><source srcset>` variants, reference-style images, root-relative paths
from the repository root and `<…>` destinations; images in fenced code and confirmed
single-line backtick spans are skipped, including image examples embedded in text.
Multiline spans and ambiguous markup remain conservatively audited because this
lightweight checker does not implement a complete Markdown parser. Literal backticks
in HTML, autolinks and link/image destinations or titles do not open code spans.
Delimiter lookup is indexed; destination scanning tracks quotes, angle delimiters
and balanced parentheses, including continuation lines.
When changing the audit parser, retain visible-image negative checks across block
boundaries and unmatched delimiters; a literal-example fix must not hide real images.

Report the mode used, files changed, what was deliberately left plain, the checks
run and any claim you could not verify.
## Boundaries

- Not product UI design; use `/impeccable`.
- Not application UI review; use `/ui-taste`.

**Done when:** a default reader audit reports verified issue links and covered/held findings (or zero eligible outcomes), an explicit audit-only run reports inline without writes, or requested README/asset edits are complete. Distinguish checks run, verified light/dark rendering and unverified claims; publication never implies implementation.
