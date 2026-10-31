---
name: responsive-screenshots
description: "Capture pages at breakpoints and check overflow."
disable-model-invocation: true
---

# Responsive Screenshots

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host contract](../COMMON.md), then the
[host-neutral Responsive Screenshots workflow](../../../skills/responsive-screenshots/SKILL.md)
and its capture script. Run the script with this host's terminal; when the Playwright
Python package is absent, use the host's MCP browser tools or its Playwright CLI and
say which path you used. Never install a browser or driver, never put credentials in a
URL, keep captures out of Git unless the request publishes them, and report real pixel
sizes and overflow results rather than a claim that the layout looks right.
