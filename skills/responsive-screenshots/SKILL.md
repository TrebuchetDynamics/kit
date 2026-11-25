---
name: responsive-screenshots
description: "Capture pages at breakpoints and check overflow."
license: MIT
---

# Responsive Screenshots

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Capture one or more pages at chosen viewport widths, then report what the capture
proves: the file, its real pixel size, whether the page scrolls horizontally, console
errors and failed requests. The bundled
[capture script](scripts/capture.py) does the work; this file sets the scope, the
matrix and the evidence rules. No upstream bytes are used; see [sources](SOURCES.md).

## Scope first

Name the pages and the widths before capturing. A repository file, a local dev server
or a staging URL is the normal case. Standard widths are `375x667`, `768x1024` and
`1440x900`; add `1920x1080` only when desktop density matters. Capture `both` color
schemes when the surface supports a dark theme, and one scheme otherwise.

Say plainly what a capture cannot show: interaction states, animation, data-driven
variants, authenticated pages and anything behind a login. For a design judgement use
`/ui-taste` or `/impeccable`; this workflow only records what rendered.

## Capture

```sh
python3 "<skill-dir>/scripts/capture.py" URL [URL ...] \
  --out screenshots/ \
  --sizes 375x667 768x1024 1440x900 \
  --scheme both \
  --selector "#ready" \
  --fail-on-overflow
```

- The script needs the Playwright Python package and one installed browser. It installs
  nothing. When it reports the package missing, use the host's MCP browser tools or
  `playwright screenshot --viewport-size W,H --full-page`, and say which path you used.
- Each capture sets a fixed viewport, `device_scale_factor=1`, the requested color
  scheme and reduced motion, then waits for network idle, the optional selector and
  `document.fonts`, plus a short settle floor. Waits come from page state, not sleeps.
- Output is `{page}-{sha256}-{class}-{width}x{height}-{scheme}.png` plus `report.md`
  and `captures.json` in the output directory. The readable path-derived page prefix
  is at most 48 characters and excludes query text. The SHA-256 hex digest uses the
  complete original URL string, including scheme, host/port, path, query and fragment.
  Different URL strings retain distinct artifacts even when their content matches.
- Exact repeated URL strings and viewport size pairs are deduplicated in first-seen
  order within one invocation: one result per unique URL/size/color-scheme combination.
  Rerunning the same inputs in the same directory may replace those same captures;
  this is not cross-run version storage.
- Use an ignored directory, or a task-scoped path, so captures never land in a commit
  by accident. Hashing is identity, not anonymization: report URLs and diagnostics
  remain potentially sensitive.

## Verify before reporting

Apply the [shared GUI decision](../shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence)
when making visual claims. Scripted capture and measured overflow diagnostics
need no interaction or snapshot; keep this capture-only scope.

1. Read the exit status: `0` all captured, `1` a capture failed, `2` a usage refusal or
   horizontal overflow under `--fail-on-overflow`. Browser diagnostics alone do not
   change the exit status. `captured` means completion, not page or visual correctness;
   completed captures with diagnostics say `captured with diagnostics`.
2. Read `report.md`: each row states capture status, real pixel size, overflow and
   console-error/failed-request counts. Per-capture details associate recorded diagnostics
   with the URL, viewport and color scheme; the summary gives totals and exit limits.
   `captures.json` retains raw diagnostic lists and actual artifact paths. Markdown
   escapes untrusted values as plain text. A full-page capture is wider than the viewport
   only when the page overflows; a narrower capture is truncated and failed.
3. Check capture failures (a bad URL, a timeout or a missing selector) and recorded
   console errors or failed requests. Fix the cause or report it; never present a
   failed capture as a pass or a completed capture as a page-clean result.
4. Look at one image per breakpoint yourself when the claim is visual. A file that exists
   proves a render happened, not that the layout is correct.

## UI review handoff

After verification, return a concise inline handoff for `/ui-taste` or `/impeccable`.
Use `report.md` and `captures.json` as the evidence sources, not a new artifact.
Keep one entry per relevant route/state, requested viewport and color scheme:

- Give the sanitized route/state and safe steps to reproduce it, including readiness
  selector or session source when used. Remove credentials and private data from paths,
  query text, fragment text, diagnostics and evidence references. If safe reproduction
  context is missing, name that gap instead of exposing it or inventing a state.
- Include requested viewport, color scheme, actual pixel dimensions, horizontal overflow
  (`yes`, `no` or `unknown`), capture status, diagnostics and command exit status.
  Give local evidence paths for the report, JSON record and image when available.
- Separate **Observed** measurements and inspected image findings from **Unverified**
  visual quality, interactions, states or schemes not checked. Captured does not mean visually correct.
  A failed capture is not defect proof: name the cause and repair action. Keep unmeasured
  dimensions and overflow unknown, and do not present a failed image as usable evidence.

Example handoff (illustrative measurements, not a live result):

> Route/state: /settings, default state on the authorized local server.
> Requested: 375x667, light. Actual: 420x900. Overflow: yes. Status: captured; exit 2 under --fail-on-overflow.
> Observed: horizontal overflow recorded. Unverified: visual quality and interactions; image not inspected.
> Reproduce: open /settings in that state; rerun the capture command with --sizes 375x667 --scheme light --fail-on-overflow.
> Evidence: local report.md row and captures.json record for this route/viewport/scheme; image at that record's path.

Failure handoff: `navigation timed out`, status `FAILED`, exit `1`; actual dimensions
and overflow unknown if not measured. Unverified: layout and visual quality.
Repair action: check authorized route availability and any readiness selector, then
rerun the same matrix. Report partial observations separately from the failure.

Preserve user restrictions and existing live owners. This handoff does not authorize
review edits or publication. Do not create GitHub issues or attachments.
Do not upload captures or raw reports.

## Safety and delivery

- Open only pages the request authorizes: local files, a dev server, or staging the owner
  named. Screenshots can expose private data, so treat the output as potentially
  sensitive and keep it out of Git unless the request says to publish it.
- Never put credentials in a URL. The script refuses them. Use the host's own browser
  session for an authenticated page, and record that the capture came from that session.
- Do not install browsers, drivers or dependencies to make a capture work, and do not
  change page content, cookies or host settings.
- Captures are evidence, not delivery: commit, push and deployment keep their own
  authority.

## Boundaries

- Not a design review; use `/ui-taste` for UI playbooks and `/impeccable` for design work.
- Not README artwork or README capture checks; use `/beautify-github-readme`.
- Not a visual-regression baseline service: it captures and reports, and stores no
  reference set.

**Done when:** every requested page and breakpoint has a capture whose real size and
overflow result are reported, or each failure names its cause, with an inline UI review
handoff that separates observed evidence from unverified behavior.
