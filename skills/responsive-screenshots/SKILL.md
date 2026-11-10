---
name: responsive-screenshots
description: "Capture pages at breakpoints and check overflow."
license: MIT
---

# Responsive Screenshots

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

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
- Output is `{page}-{class}-{width}x{height}-{scheme}.png` plus `report.md` and
  `captures.json` in the output directory. Use an ignored directory, or a task-scoped
  path, so captures never land in a commit by accident.

## Verify before reporting

1. Read the exit status: `0` all captured, `1` a capture failed, `2` a usage refusal or
   horizontal overflow under `--fail-on-overflow`.
2. Read `report.md`: each row states the real pixel size and the overflow result. A
   full-page capture is wider than the viewport only when the page overflows; a capture
   narrower than the viewport is truncated and failed.
3. Check the named failures: a bad URL, a timeout, a missing selector, console errors or
   failed requests. Fix the cause or report it; never present a failed capture as a pass.
4. Look at one image per breakpoint yourself when the claim is visual. A file that exists
   proves a render happened, not that the layout is correct.

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
overflow result are reported, or each failure names its cause.
