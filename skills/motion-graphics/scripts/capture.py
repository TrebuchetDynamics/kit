#!/usr/bin/env python3
"""Capture deterministic frames from an authorized, self-contained HTML timeline."""
import argparse
from itertools import count
import math
from pathlib import Path
import re
import sys

TIMEOUT_MS = 5_000


def seek_frame(page, seconds, errors):
    page.evaluate('''seconds => {
        const result = window.seek(seconds);
        if (result && typeof result.then === 'function')
            throw Error('window.seek(seconds) must draw synchronously');
    }''', seconds)
    page.wait_for_function("document.fonts.status === 'loaded'")
    broken_fonts = page.evaluate("[...document.fonts].filter(f => f.status === 'error').map(f => f.family)")
    if broken_fonts:
        raise RuntimeError(f"Could not load fonts: {', '.join(broken_fonts)}. Embed working font files and retry.")
    frame = page.screenshot()
    if errors:
        raise RuntimeError(errors[0])
    return frame


def capture(args, width, height):
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError as exc:
        raise RuntimeError('Playwright is not installed for this Python; provide an environment '
                           f'with Playwright and matching Chromium, then retry. ({exc})') from exc

    url = args.html.as_uri() + '?render'
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(timeout=TIMEOUT_MS)
        except Error as exc:
            raise RuntimeError('Matching Playwright Chromium is unavailable; provision the matching '
                               f'browser and its system dependencies separately, then retry.\n{exc}') from exc
        page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1,
                                offline=True)
        page.set_default_timeout(TIMEOUT_MS)
        errors = []
        page.on('pageerror', lambda error: errors.append(f'Page error: {error}'))
        page.on('console', lambda message: errors.append(f'Console error: {message.text}')
                if message.type == 'error' else None)

        def route_request(route):
            target = route.request.url
            if target == url or target.startswith(('data:', 'blob:')):
                route.continue_()
            else:
                errors.append(f'External resource: {target}. Inline all assets and retry.')
                route.abort()

        page.route('**/*', route_request)
        page.goto(url, wait_until='load')
        if errors:
            raise RuntimeError(errors[0])
        if not page.evaluate("typeof window.seek === 'function'"):
            raise RuntimeError('window.seek(seconds) is missing in ?render mode. Implement it and retry.')
        if args.font:
            # Start the asynchronous loads without making evaluate wait indefinitely.
            page.evaluate('''fonts => {
                window.__kitFontFailures = null;
                Promise.all(fonts.map(async font => {
                    try { return (await document.fonts.load(font)).length ? null : font; }
                    catch { return font; }
                })).then(results => { window.__kitFontFailures = results.filter(Boolean); });
            }''', args.font)
            page.wait_for_function('window.__kitFontFailures !== null')
            missing = page.evaluate('window.__kitFontFailures')
            if missing:
                raise RuntimeError(f"Missing required font: {', '.join(missing)}. Embed the requested faces and retry.")

        times = [0.0, *args.at, args.duration]
        frames = [seek_frame(page, t, errors) for t in times]
        for seconds, frame in reversed(list(zip(times, frames))):
            if seek_frame(page, seconds, errors) != frame:
                raise RuntimeError(f'Repeat seek differs at {seconds:g}s. Derive the frame from time alone and retry.')
        if args.loop and frames[0] != frames[-1]:
            raise RuntimeError('Loop endpoints differ. Match the frame at the duration to the frame at zero.')
        if all(frame == frames[0] for frame in frames[1:-1]):
            raise RuntimeError('No intermediate frame differs from the start. Check seek or sample a moving interval.')

        args.out.mkdir()
        for i, (seconds, frame) in enumerate(zip(times, frames)):
            path = args.out / f'sample-{i:03}.png'
            path.write_bytes(frame)
            print(f'{path} @ {seconds:g}s')
        if args.fps:
            for i in count():
                seconds = i / args.fps
                if seconds >= args.duration:
                    break  # Endpoint is measured separately, never duplicated in the sequence.
                (args.out / f'frame-{i:06}.png').write_bytes(seek_frame(page, seconds, errors))
            print(f'{i} sequence frames at {args.fps} fps')
        browser.close()
    loop = 'loop endpoints match; ' if args.loop else ''
    print(f'Repeat seeks match; {loop}motion detected.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path, help='trusted local HTML file opened with ?render')
    parser.add_argument('--out', type=Path, required=True, help='new directory for frame PNGs')
    parser.add_argument('--size', required=True, help='viewport WIDTHxHEIGHT in pixels')
    parser.add_argument('--duration', type=float, required=True, help='timeline duration in seconds')
    parser.add_argument('--at', type=float, nargs='+', required=True, help='intermediate times in seconds')
    parser.add_argument('--loop', action='store_true', help='require identical start and end frames')
    parser.add_argument('--font', action='append', help='required embedded CSS font shorthand (repeatable)')
    parser.add_argument('--fps', type=int, help='also capture a numbered PNG sequence at this rate')
    args = parser.parse_args()
    size = re.fullmatch(r'([1-9][0-9]*)x([1-9][0-9]*)', args.size)
    if not size:
        parser.error('--size must be WIDTHxHEIGHT with positive pixel dimensions')
    if not math.isfinite(args.duration) or args.duration <= 0 or any(
            not 0 < t < args.duration for t in args.at):
        parser.error('--duration must be finite and positive; --at times must fall strictly inside it')
    if args.fps is not None and args.fps <= 0:
        parser.error('--fps must be a positive integer')
    args.html = args.html.resolve()
    if not args.html.is_file():
        parser.error(f'HTML file does not exist: {args.html}')
    try:
        capture(args, *map(int, size.groups()))
    except Exception as exc:
        print(f'Capture failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
