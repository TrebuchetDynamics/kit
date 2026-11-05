#!/usr/bin/env python3
"""Strictly type-check the selection and authority allowlist with mypy."""
from pathlib import Path
import shutil
import subprocess
import sys

MYPY = '1.19.1'
ALLOWLIST = ('Src/pi_autowork/engine/task_select.py',
             'Src/pi_autowork/planning_authority.py')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1:
        print('usage: typecheck.py [PATH]', file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    config = root / 'mypy.ini'
    print('Strict mypy allowlist: ' + ', '.join(ALLOWLIST), flush=True)
    targets = args or list(ALLOWLIST)
    if args:
        print('Typecheck target: ' + args[0], flush=True)
    command = [sys.executable, '-m', 'mypy', '--config-file', str(config), *targets]
    try:
        import mypy  # noqa: F401
    except ImportError:
        uv = shutil.which('uv')
        if uv is None:
            print('mypy is not installed and uv is unavailable to provision it', file=sys.stderr)
            return 1
        command = [uv, 'run', '--no-project', '--with', f'mypy=={MYPY}',
                   'mypy', '--config-file', str(config), *targets]
    return subprocess.run(command, cwd=root).returncode


if __name__ == '__main__':
    sys.exit(main())
