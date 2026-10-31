#!/usr/bin/env python3
"""Capture one or more pages at responsive breakpoints and verify each result.

Usage:
    python3 capture.py URL [URL ...] --out DIR [options]

Each capture records the file path, the real pixel size, whether the page scrolls
horizontally at that width, console errors and failed requests. Exit status is 0 when
every capture succeeded, 1 when any capture failed, and 2 for a usage refusal or a
horizontal overflow when --fail-on-overflow was requested.

The Playwright Python package and a browser must already be installed. This script
installs nothing and reads no credentials: it opens http(s) and file URLs only.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

STANDARD_SIZES = ('375x667', '768x1024', '1440x900')
MIN_WIDTH, MAX_WIDTH = 200, 3840
MIN_HEIGHT, MAX_HEIGHT = 200, 2160


@dataclass
class Result:
    url: str
    scheme: str
    label: str
    width: int
    height: int
    path: str = ''
    pixel_width: int = 0
    pixel_height: int = 0
    overflow: bool | None = None
    console_errors: list = field(default_factory=list)
    failed_requests: list = field(default_factory=list)
    error: str = ''


def parse_size(text):
    match = re.fullmatch(r'(\d+)\s*[x×]\s*(\d+)', text.strip())
    if not match:
        raise argparse.ArgumentTypeError(f'expected WIDTHxHEIGHT, got {text!r}')
    width, height = int(match.group(1)), int(match.group(2))
    if not MIN_WIDTH <= width <= MAX_WIDTH:
        raise argparse.ArgumentTypeError(f'width {width} is outside {MIN_WIDTH}-{MAX_WIDTH}')
    if not MIN_HEIGHT <= height <= MAX_HEIGHT:
        raise argparse.ArgumentTypeError(f'height {height} is outside {MIN_HEIGHT}-{MAX_HEIGHT}')
    return width, height


def label_for(width):
    """A stable class name from the width, so files sort by breakpoint."""
    if width <= 480:
        return 'mobile'
    if width <= 1024:
        return 'tablet'
    return 'desktop'


def page_slug(url):
    parsed = urlparse(url)
    if parsed.scheme == 'file':
        name = Path(parsed.path).stem or 'page'
    else:
        path = parsed.path.strip('/')
        name = path.replace('/', '-') if path else 'index'
        if parsed.query:
            name += '-q' + re.sub(r'[^a-z0-9]+', '-', parsed.query.lower()).strip('-')[:40]
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()
    return slug or 'page'


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https', 'file'):
        raise ValueError(f'unsupported scheme {parsed.scheme!r}: use http, https or file')
    if parsed.username or parsed.password:
        raise ValueError('URLs with embedded credentials are refused; use a browser session instead')


def capture_one(browser, url, width, height, scheme, out_dir, settle_ms, timeout_s,
                selector, full_page, reduced_motion):
    result = Result(url=url, scheme=scheme, label=label_for(width),
                    width=width, height=height)
    context = browser.new_context(viewport={'width': width, 'height': height},
                                  device_scale_factor=1,
                                  color_scheme=scheme,
                                  reduced_motion=reduced_motion)
    try:
        page = context.new_page()
        page.set_default_timeout(int(timeout_s * 1000))
        page.on('console', lambda msg: result.console_errors.append(msg.text)
                if msg.type == 'error' else None)
        page.on('requestfailed', lambda req: result.failed_requests.append(
            f'{req.method} {req.url} {req.failure}'))
        page.goto(url, wait_until='networkidle', timeout=int(timeout_s * 1000))
        if selector:
            page.wait_for_selector(selector, timeout=int(timeout_s * 1000))
        page.evaluate('document.fonts && document.fonts.ready')
        if settle_ms:
            page.wait_for_timeout(settle_ms)
        result.overflow = page.evaluate(
            '() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')
        name = f'{page_slug(url)}-{result.label}-{width}x{height}-{scheme}.png'
        target = out_dir / name
        page.screenshot(path=str(target), full_page=full_page, animations='disabled')
        result.path = str(target)
        result.pixel_width, result.pixel_height = png_size(target)
        # A full-page capture is as wide as the scrollable content. Wider than the viewport
        # is the overflow finding itself; narrower means the capture is truncated.
        if result.pixel_width > width:
            result.overflow = True
        if not target.is_file() or target.stat().st_size == 0:
            result.error = 'screenshot file is empty'
        elif result.pixel_width < width:
            result.error = (f'captured width {result.pixel_width} is narrower than the requested '
                            f'viewport width {width}')
        elif full_page and result.pixel_height < height:
            result.error = (f'full-page height {result.pixel_height} is below the viewport '
                            f'height {height}')
    except Exception as exc:  # Playwright raises its own error types; report, never traceback.
        result.error = str(exc).strip().splitlines()[0][:300]
    finally:
        context.close()
    return result


def png_size(path):
    """Read width and height from a PNG IHDR block without a third-party library."""
    data = Path(path).read_bytes()[:33]
    if len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR':
        return 0, 0
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')


def write_reports(results, out_dir):
    payload = [result.__dict__ for result in results]
    (out_dir / 'captures.json').write_text(json.dumps(payload, indent=2) + '\n')
    lines = ['# Responsive captures', '',
             f'{len(results)} capture(s). Each row is one page, width and color scheme.', '',
             '| Page | Breakpoint | Scheme | Size | Overflow | File |',
             '| --- | --- | --- | --- | --- | --- |']
    for r in results:
        size = f'{r.pixel_width}x{r.pixel_height}' if r.pixel_width else 'not captured'
        status = 'FAILED' if r.error else ('yes' if r.overflow else 'no')
        lines.append(f'| {r.url} | {r.label} {r.width}x{r.height} | {r.scheme} | {size} | '
                     f'{status} | `{Path(r.path).name or "-"}` |')
    failed = [r for r in results if r.error]
    overflow = [r for r in results if r.overflow]
    lines += ['', '## Result', '']
    lines.append(f'- Captured: {len(results) - len(failed)} of {len(results)}.')
    lines.append(f'- Horizontal overflow: {len(overflow)} capture(s).')
    for r in failed:
        lines.append(f'- Failed: {r.url} {r.width}x{r.height} {r.scheme}: {r.error}')
    for r in overflow:
        lines.append(f'- Overflow: {r.url} at {r.width}px ({r.scheme}).')
    lines += ['', 'Full-page pixel height varies with content; only the width and the '
                  'minimum height are checked here.']
    (out_dir / 'report.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('urls', nargs='+', help='http(s) or file URLs to capture')
    parser.add_argument('--out', type=Path, required=True, help='output directory')
    parser.add_argument('--sizes', nargs='+', type=parse_size, default=[parse_size(s) for s in STANDARD_SIZES],
                        help=f'WIDTHxHEIGHT breakpoints (default: {" ".join(STANDARD_SIZES)})')
    parser.add_argument('--scheme', choices=('light', 'dark', 'both'), default='light')
    parser.add_argument('--selector', default='', help='wait for this CSS selector first')
    parser.add_argument('--settle-ms', type=int, default=300,
                        help='minimum time to wait after the load settles (default: 300)')
    parser.add_argument('--timeout', type=float, default=30, help='per-step timeout in seconds')
    parser.add_argument('--no-full-page', action='store_true', help='capture the viewport only')
    parser.add_argument('--motion', choices=('reduce', 'no-preference'), default='reduce',
                        help='emulated reduced-motion preference (default: reduce)')
    parser.add_argument('--fail-on-overflow', action='store_true',
                        help='exit 2 when a capture scrolls horizontally')
    args = parser.parse_args()

    try:
        for url in args.urls:
            validate_url(url)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Playwright is not installed for this Python: install it and a browser, or use '
              'the host MCP browser tools. Nothing was captured.', file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    schemes = ('light', 'dark') if args.scheme == 'both' else (args.scheme,)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for url in args.urls:
                for width, height in args.sizes:
                    for scheme in schemes:
                        result = capture_one(browser, url, width, height, scheme, args.out,
                                             args.settle_ms, args.timeout, args.selector,
                                             not args.no_full_page, args.motion)
                        results.append(result)
                        state = 'FAILED' if result.error else ('overflow' if result.overflow else 'ok')
                        print(f'{state:9} {result.label:7} {width}x{height} {scheme:5} '
                              f'{Path(result.path).name or result.error}')
        finally:
            browser.close()

    write_reports(results, args.out)
    failed = [r for r in results if r.error]
    overflow = [r for r in results if r.overflow]
    print(f'\n{len(results) - len(failed)}/{len(results)} captured; {len(overflow)} with horizontal '
          f'overflow. Report: {args.out / "report.md"}')
    if failed:
        return 1
    if overflow and args.fail_on_overflow:
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
