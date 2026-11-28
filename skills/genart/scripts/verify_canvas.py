#!/usr/bin/env python3
"""Check a trusted local Canvas 2D sketch at 256×256 in Chromium."""
import argparse
from base64 import b64decode
from hashlib import sha256
from pathlib import Path
from shutil import which
import sys
from urllib.parse import quote, unquote, urlencode, urlsplit

ORIGIN = 'http://localhost'
SIZE = 256
SEEDS = ('0x1a2b3c4d' + '12345678' * 7, '0x89abcdef' + 'fedcba98' * 7)
TIMEOUT_MS = 5_000


def canvas_pixels(page):
    page.wait_for_function('window.rendered === true && document.fonts.status === "loaded"')
    return b64decode(page.evaluate('''size => {
        const [canvas, extra] = document.querySelectorAll('canvas');
        if (!canvas || extra || canvas.width !== size || canvas.height !== size)
            throw Error(`Expected one ${size}×${size} canvas`);
        for (const font of document.fonts) {
            if (font.status === 'error') throw Error(`Cannot load local font ${font.family}`);
        }
        const ctx = canvas.getContext('2d');
        if (!ctx) throw Error('Expected a Canvas 2D context; SVG and WebGL are not checked');
        const bytes = ctx.getImageData(0, 0, size, size).data;
        let binary = '';
        for (let i = 0; i < bytes.length; i += 8192)
            binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        return btoa(binary);
    }''', SIZE))


def renders(browser, sketch, first, *rerenders):
    errors = []
    with browser.new_context(device_scale_factor=1, viewport={'width': SIZE, 'height': SIZE},
                             service_workers='block') as context:
        def local_asset(route):
            url = urlsplit(route.request.url)
            if f'{url.scheme}://{url.netloc}' == ORIGIN and route.request.method == 'GET':
                path = (sketch.parent / unquote(url.path).lstrip('/')).resolve()
                if path.is_relative_to(sketch.parent) and path.is_file():
                    route.fulfill(path=path)
                    return
            errors.append(f'{route.request.resource_type} unavailable: {route.request.url}; '
                          'use a readable asset under the sketch directory')
            route.abort()

        context.route('**/*', local_asset)
        context.set_default_timeout(TIMEOUT_MS)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        query = urlencode({'hash': first, 'width': SIZE, 'height': SIZE})
        try:
            page.goto(f'{ORIGIN}/{quote(sketch.name)}?{query}')
            pixels = [canvas_pixels(page)]
            for seed in rerenders:
                page.evaluate('''hash => {
                    window.rendered = false;
                    window.render(hash);
                }''', seed)
                pixels.append(canvas_pixels(page))
        finally:
            if errors:
                raise ValueError('; '.join(errors)) from None
        return pixels


def verify(browser, sketch):
    a, b = SEEDS
    fresh_a = [renders(browser, sketch, a)[0] for _ in range(3)]
    fresh_b = [renders(browser, sketch, b)[0] for _ in range(3)]
    sequence = renders(browser, sketch, a, b, a)
    first, second = fresh_a[0], fresh_b[0]
    changed = sum(any(abs(first[i + c] - second[i + c]) >= 16 for c in range(4))
                  for i in range(0, len(first), 4)) / (SIZE * SIZE)
    checks = (
        ('repeatability', len(set(fresh_a)) == len(set(fresh_b)) == 1,
         'three fresh contexts per seed'),
        ('distinctness', changed >= 0.01, f'{changed:.2%} of pixels differ by ≥16 in an RGBA channel; need ≥1%'),
        ('A→B→A', sequence == [first, second, first], 'same page must match fresh A, B, A'),
    )
    print(f'Chromium {browser.version}; Canvas 2D {SIZE}×{SIZE}; '
          f'seed A {a} sha256={sha256(first).hexdigest()}; seed B {b} sha256={sha256(second).hexdigest()}')
    for label, passed, detail in checks:
        print(f'{"ok" if passed else "FAIL"} {label}: {detail}')
    return 0 if all(passed for _, passed, _ in checks) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sketch', type=Path, help='local HTML file; assets must be under its directory')
    parser.add_argument('--chromium', default='chromium', help='installed Chromium executable (default: chromium on PATH)')
    args = parser.parse_args()
    sketch = args.sketch.resolve()
    chromium = which(args.chromium)
    if not chromium:
        print('FAIL: Chromium executable not found. Supply an installed executable with --chromium.', file=sys.stderr)
        return 1
    if not sketch.is_file() or sketch.suffix.lower() != '.html':
        parser.error('supply an existing local .html sketch')
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        print('FAIL: Python Playwright not available. Use a Python environment with playwright.', file=sys.stderr)
        return 1
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chromium, timeout=TIMEOUT_MS,
                args=['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none'])
            return verify(browser, sketch)
    except (Error, OSError, ValueError) as exc:
        print(f'FAIL: {exc}\nCheck the local Chromium/Playwright runtime and the sketch render contract.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
