#!/usr/bin/env python3
"""Check only the local inputs needed for this drawing; do not create files."""
import argparse
from io import BytesIO
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('png', 'jpeg', 'gif'), nargs='+',
                        required=True, help='Pillow output formats the operation needs')
    parser.add_argument('--font', type=Path, action='append', default=[],
                        help='actual font file used by the scene (repeat for each)')
    args = parser.parse_args()
    try:
        import numpy
        import PIL
        from PIL import Image, ImageFont
    except (ImportError, OSError) as exc:
        print(f'FAIL: NumPy and Pillow are required in this Python environment: {exc}', file=sys.stderr)
        return 1
    for package, version, minimum in [('NumPy', numpy.__version__, (1, 24)),
                                      ('Pillow', PIL.__version__, (10, 0))]:
        if tuple(map(int, version.split('.')[:2])) < minimum:
            required = '.'.join(map(str, minimum))
            print(f'FAIL: {package} {version}; use an environment with {package}>={required}.', file=sys.stderr)
            return 1
    for font in args.font:
        try:
            ImageFont.truetype(str(font.resolve(strict=True)), 12)
        except OSError as exc:
            print(f'FAIL: cannot load font {font}: {exc}. Supply the intended local font file.', file=sys.stderr)
            return 1
    for output_format in args.format:
        try:
            Image.new('RGB', (2, 2)).save(BytesIO(), format=output_format.upper())
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            print(f'FAIL: Pillow {output_format} encoder unavailable: {exc}. Use a Pillow build with that encoder.',
                  file=sys.stderr)
            return 1
    print(f'ok NumPy {numpy.__version__}, Pillow {PIL.__version__}; '
          f'encoders: {", ".join(args.format)}; font files checked: {len(args.font)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
