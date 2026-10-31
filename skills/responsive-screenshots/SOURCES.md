# Sources

The idea for this workflow comes from the `playwright-responsive-screenshots` skill in
[dawiddutoit/custom-claude](https://github.com/dawiddutoit/custom-claude/tree/main/skills/playwright-responsive-screenshots),
read at revision `17b45a90a69608ebd6630d865da20711cf432013`.

That repository states no license, so **no upstream file or text is copied here**. This
workflow is written for Autowork, and it differs on purpose:

- It runs a bundled Python script against the Playwright library instead of requiring
  four MCP browser tools, so it works on every host and keeps the capture reproducible.
- It fixes the color scheme, device scale, reduced motion and settle floor, and waits on
  page state instead of a fixed one-second sleep.
- It marks horizontal overflow from two independent signals: the page's own
  `scrollWidth` and a full-page capture wider than the viewport.
- It fails when a capture is narrower than the requested viewport, so a truncated image
  cannot pass as a breakpoint.
- It refuses URLs with embedded credentials and writes a machine-readable
  `captures.json` beside the Markdown report.
