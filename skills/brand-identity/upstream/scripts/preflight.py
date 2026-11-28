#!/usr/bin/env python3
"""Kit's read-only capability check. No installer, downloads or project writes."""
import argparse
from importlib import import_module
from pathlib import Path
import sys

# Importing the upstream browser probe must not create bytecode in the package.
sys.dont_write_bytecode = True


def add_options(parser):
    parser.add_argument('--render', action='store_true', help='start and close a local Chromium browser')
    parser.add_argument('--type', action='store_true', help='check font audit, variable-font instancing and WOFF2 libraries')
    parser.add_argument('--outlines', action='store_true', help='also check shaping and SVG outline libraries')
    parser.add_argument('--font', action='append', default=[], type=Path,
                        help='check a licensed local font file (repeat per face; implies --type)')


def check(args):
    if sys.version_info < (3, 10):
        print('Brand Identity needs Python 3.10+. Select a prepared interpreter and retry.', file=sys.stderr)
        return 1
    errors = []
    modules = []
    if args.type or args.outlines or args.font:
        modules += ['fontTools.ttLib', 'fontTools.ttLib.woff2', 'pathops']
    if args.outlines:
        modules.append('uharfbuzz')
    imported = {}
    for name in modules:
        try:
            module = import_module(name)
            if name == 'fontTools.ttLib.woff2' and not module.haveBrotli:
                raise ImportError('the required Brotli backend is missing')
            imported[name] = module
        except (ImportError, OSError) as exc:
            errors.append(f'Python package {name} is unavailable: {exc}')
    if len(imported) != len(modules):
        errors.append(f'Prepare a Python environment using {Path(__file__).resolve().parents[1] / "requirements.txt"}, '
                      'then rerun the check with that interpreter.')
    for path in args.font:
        path = path.expanduser()
        if not path.is_file():
            errors.append(f'Font not found: {path}. Supply the licensed local font file and retry.')
        elif 'fontTools.ttLib' in imported:
            ttlib = imported['fontTools.ttLib']
            try:
                with ttlib.TTFont(path) as font:
                    if not font.getBestCmap():
                        raise ttlib.TTLibError('no usable Unicode character map')
            except (OSError, ttlib.TTLibError, AssertionError, IndexError, KeyError, ValueError) as exc:
                errors.append(f'Cannot read font {path}: {exc}. Supply a readable local font file and retry.')
    if args.render:
        from render_png import launch_check
        result = launch_check(timeout=10)
        if not result['ok']:
            errors.append(f'Chromium browser unavailable: {result["error"]}. '
                          'Prepare Chrome or Chromium, or set BRAND_IDENTITY_BROWSER, then retry.')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('Brand Identity: requested capabilities ready (not an asset or visual check).')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)
    sys.exit(check(parser.parse_args()))
