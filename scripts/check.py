#!/usr/bin/env python3
"""Run owned offline unittest suites; never import tests while building inventory."""
import argparse
import ast
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatchcase
import importlib.util
import math
import runpy
import os
import shutil
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

TEST_DIRS = ('tests', 'tests/native', 'skills/docs-sync/scripts',
             'skills/git-commit-push/scripts')
EXCLUSIONS = {
    'tests/integration_plugin.py':
        ('integration', 'requires the optional Hermes loader environment'),
    'tests/integration_autoresearch.py':
        ('integration', 'requires Hermes loader, CLI queue and gateway routing; no model or network calls'),
    'tests/integration_bundle.py':
        ('integration', 'requires an existing isolated Hermes installation'),
}
LIVE_FLAGS = ('CONTAINMENT_LINUX_TESTS', 'RUN_CONTROLLER_BRIDGE_LINUX',
              'HERMES_NATIVE_HANDOFF_TEST', 'HERMES_NATIVE_REGISTRATION_TEST')


def discover_tests(root):
    """Only direct test_*.py children of the maintained test directories."""
    root = Path(root).resolve()
    tests = []
    for directory in TEST_DIRS:
        folder = root / directory
        if (not folder.is_dir()
                or any((root / parent).is_symlink()
                       for parent in (Path(directory), *Path(directory).parents)
                       if parent != Path('.'))):
            continue
        for path in sorted(folder.glob('test_*.py')):
            if (path.is_file() and not path.is_symlink()
                    and path.relative_to(root).as_posix() not in EXCLUSIONS):
                tests.append(path)
    return tests


def test_ids(path):
    """`module.Class.test_name` for each test method, read with ast so nothing is imported;
    empty when the module defines none that way."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), str(path))
    except (OSError, SyntaxError, ValueError):
        return []
    return [f'{path.stem}.{node.name}.{item.name}' for node in tree.body if isinstance(node, ast.ClassDef)
            for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name.startswith('test')]


def units(root, tests, pattern=None, shard=None):
    """Run each module in its own process, or partition static method IDs for CI.

    Dynamic modules run whole on the first shard so they are neither lost nor duplicated.
    """
    for path in tests:
        if shard:
            ids = test_ids(path)
            if not ids:
                if shard[0] == 0:
                    yield path.parent, [path.stem]
                continue
            ids = ids[shard[0]::shard[1]]
            if pattern:
                match = pattern if '*' in pattern else f'*{pattern}*'
                ids = [name for name in ids if fnmatchcase(name, match)]
            if ids:
                yield path.parent, ids
        else:
            yield path.parent, [path.stem]


def shard_spec(value):
    """``I/N``: shard I of N, 1-based."""
    try:
        index, count = (int(part) for part in value.split('/'))
    except ValueError:
        raise argparse.ArgumentTypeError('expected I/N, for example 2/3') from None
    if count <= 0 or not 1 <= index <= count:
        raise argparse.ArgumentTypeError('expected 1 <= I <= N')
    return index - 1, count


def run_unit(directory, names, env, timeout, pattern=None):
    """Use the module runner so multiprocessing spawn has a real entry point.

    Returns (passed, output); the caller prints output so concurrent processes
    never interleave."""
    command = [sys.executable, '-m', 'unittest', *(['-k', pattern] if pattern else []), *names]
    with subprocess.Popen(command, cwd=directory, env=env, text=True,
                          encoding='utf-8', errors='replace',
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          start_new_session=os.name == 'posix') as process:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            output, _ = process.communicate()
            return False, output + f'TIMEOUT: {directory} after {timeout:g}s\n'
    return process.returncode == 0, output


def _cpu_times():
    """The host's aggregate CPU times from /proc/stat: user, nice, system, idle, iowait, ..."""
    with open('/proc/stat') as stat:
        return [int(x) for x in stat.readline().split()[1:]]


def busy_cpus(sample=0.5):
    """CPUs busy at normal priority, excluding lower-priority niced work."""
    first = _cpu_times()
    time.sleep(sample)
    delta = [b - a for a, b in zip(first, _cpu_times())]
    total = sum(delta[:8]) or 1
    nice, idle, iowait = delta[1], delta[3], delta[4]
    return (os.cpu_count() or 1) * (total - nice - idle - iowait) / total


def default_jobs():
    """Use one or two test processes without oversubscribing a busy host."""
    try:
        if os.getpriority(os.PRIO_PROCESS, 0) == 0:
            idle = (os.cpu_count() or 1) - math.ceil(busy_cpus())
        else:
            idle = (os.cpu_count() or 1) - int(os.getloadavg()[0])
    except (OSError, ValueError):
        idle = 1
    return max(1, min(2, idle))


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return number


def affected_selection(root, revision_range):
    """Select on the merged checkout; invalid revision ranges never become empty successes."""
    root = Path(root).resolve()
    if revision_range.count('..') != 1 or '...' in revision_range or not all(revision_range.split('..')):
        raise ValueError('--affected requires BASE..HEAD')
    revisions = []
    for rev in revision_range.split('..'):
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', '--end-of-options',
                                 rev + '^{commit}'], capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f'cannot resolve affected revision: {rev}')
        revisions.append(result.stdout.strip())
    result = subprocess.run(['git', '-C', str(root), 'diff', '--name-only', '-z', '--no-renames',
                             *revisions, '--'], capture_output=True, text=True, check=True)
    changed = sorted(p for p in result.stdout.split('\0') if p)
    selector = runpy.run_path(str(root / 'scripts/affected_tests.py'))
    tests, reasons, full = selector['select'](changed, revisions[0], conservative=True)
    return dict(base=revisions[0], head=revisions[1], changed=changed, tests=tests,
                reasons=reasons, full=full, core=['tree_guard', 'docs check'])


def source_guard(root):
    """Check actual selected-release owners without importing product modules.

    Old copies of the checker without a source foundation keep their inventory.
    A present bootstrap is authoritative: missing payloads are not a fallback.
    """
    bootstrap = root / 'scripts/kit_bootstrap.py'
    if not bootstrap.is_file():
        return True
    try:
        layout_api = runpy.run_path(str(bootstrap))['Layout']
        sources = layout_api.python_sources(root)
        for source in sources:
            ast.parse(source.read_bytes(), str(source))
    except (OSError, ImportError, SyntaxError, ValueError) as error:
        location = f'{error.filename}: ' if isinstance(error, SyntaxError) else ''
        print(f'FAIL: source guard: {location}{error}', flush=True)
        return False
    return True


def affected_core(root):
    """Cheap repository contracts, even when no test modules were selected."""
    docs = root / 'skills/docs-sync/scripts/docs.py'
    if docs.is_file():
        return subprocess.run([sys.executable, str(docs), 'check', str(root)], cwd=root).returncode == 0
    return True


PROVISIONED = 'KIT_CHECK_PROVISIONED'


def provision(root):
    """Provision the documented Python and test dependencies unless already available."""
    requirements = root / 'requirements-test.txt'
    if os.environ.get(PROVISIONED) or not requirements.is_file():
        return None
    if sys.version_info[:2] == (3, 12) and importlib.util.find_spec('yaml'):
        return None
    uv = shutil.which('uv')
    if uv is None:
        print('warning: the full check needs CPython 3.12 and requirements-test.txt, and uv is '
              'not installed to provide them', file=sys.stderr)
        return None
    command = [uv, 'run', '--python', '3.12', '--no-project', '--with-requirements',
               str(requirements), 'python', str(Path(__file__).resolve()), *sys.argv[1:]]
    return subprocess.run(command, env=dict(os.environ, **{PROVISIONED: '1'})).returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='owned test modules or directories (default: all offline tests)')
    parser.add_argument('-k', dest='pattern', help='unittest name pattern for focused reproduction (default: all tests)')
    parser.add_argument('--list', action='store_true', help='list inventory without importing or running tests')
    parser.add_argument('--affected', metavar='BASE..HEAD',
                        help='run affected modules and core contracts; unresolved changes select the full suite')
    parser.add_argument('--exclude', action='append', default=[], metavar='PATH',
                        help='leave out these owned test modules or directories (repeatable)')
    parser.add_argument('--shard', type=shard_spec, metavar='I/N',
                        help='run shard I of N of the selected tests (round-robin by test id), for CI matrices')
    parser.add_argument('--timeout', type=float, default=1800, help='seconds allowed per test process (default: 1800)')
    parser.add_argument('--jobs', type=positive_int,
                        help='test processes run at once (default: idle CPUs, 1 to 2; capped at 2)')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be positive')
    root = Path(__file__).resolve().parents[1]
    if argv is None and not args.list:
        code = provision(root)
        if code is not None:
            return code
    tests = discover_tests(root)
    selection = None
    if args.affected:
        if args.paths or args.pattern:
            parser.error('--affected cannot be combined with paths or -k')
        try:
            selection = affected_selection(root, args.affected)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            parser.error(str(error))
        print('Affected selection: ' + ('whole suite' if selection['full'] else 'affected modules'), flush=True)
        for name in selection['tests']:
            print(f'  {name} ({selection["reasons"][name]})', flush=True)
        print('Always run: ' + ', '.join(selection['core']), flush=True)
        tests = [test for test in tests if test.relative_to(root).as_posix() in selection['tests']]
    if args.paths:
        selected = set()
        for name in args.paths:
            path = (root / name).resolve()
            matches = [test for test in tests if test == path or path in test.parents]
            if not path.is_relative_to(root) or not matches:
                parser.error(f'no owned offline tests match: {name}')
            selected.update(matches)
        tests = [test for test in tests if test in selected]
    for name in args.exclude:
        path = (root / name).resolve()
        matches = [test for test in tests if test == path or path in test.parents]
        if not path.is_relative_to(root) or not matches:
            parser.error(f'--exclude matches no selected offline test: {name}')
        tests = [test for test in tests if test not in matches]
    if args.shard:
        print(f'Shard {args.shard[0] + 1} of {args.shard[1]} of the selected tests', flush=True)
    groups = defaultdict(list)
    for path in tests:
        groups[path.parent].append(path)
        if args.list:
            print(f'RUN {path.relative_to(root)}')
    excluded = 0
    for name, (category, reason) in EXCLUSIONS.items():
        if (root / name).is_file():
            print(f'EXCLUDE {name} [{category}]: {reason}', flush=True)
            excluded += 1
    print(f'Offline inventory: {len(tests)} modules in {len(groups)} directories; '
          f'{excluded} excluded. No model/native qualification.', flush=True)
    if args.list:
        return 0
    if not tests and (selection is None or selection['full']):
        print('FAIL: no offline tests found', flush=True)
        return 1
    # Cheap first: conflict markers, Python that does not compile or invalid JSON fail
    # every later test less clearly (markers twice reached main in Python modules).
    guard = root / 'scripts/tree_guard.py'
    if guard.is_file() and subprocess.run([sys.executable, str(guard), '--repo', str(root)]).returncode:
        print('FAIL: the tree guard refused this tree; no tests ran', flush=True)
        return 1
    if not source_guard(root):
        return 1
    if selection is not None and not affected_core(root):
        print('FAIL: an affected core contract refused this tree; no tests ran', flush=True)
        return 1
    # Native tests must not inherit live opt-ins or profile-specific runtime settings.
    env = {k: v for k, v in os.environ.items()
           if k not in LIVE_FLAGS and not k.startswith('KIT_')}
    env['KIT_TOOLSET'] = str(root)
    # Three suites read os.environ['TMPDIR'] and their fixtures shell out to it. CI exports it and
    # every Kit host sets one, but a bare interactive shell does not, and the resulting errors
    # read like a red tree rather than a missing setting.
    env.setdefault('TMPDIR', tempfile.gettempdir())
    support_paths = [str(root / 'tests'), str(root / 'src')]
    existing_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = os.pathsep.join(support_paths + ([existing_pythonpath] if existing_pythonpath else []))
    passed = failed = 0
    work = list(units(root, tests, args.pattern, args.shard))
    # Modules are independent processes; print output grouped in inventory order.
    jobs = min(args.jobs or default_jobs(), 2)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_unit, *unit, env, args.timeout, args.pattern) for unit in work]
        runs = [(unit[0], future) for unit, future in zip(work, futures)]
        for directory, modules in groups.items():
            print(f'CHECK {directory.relative_to(root)} ({len(modules)} modules)', flush=True)
            ok = True
            for result in [run for where, run in runs if where == directory]:
                unit_ok, output = result.result()
                print(output, end='', flush=True)
                ok = ok and unit_ok
            if ok:
                passed += 1
            else:
                failed += 1
    print(f'Offline result: {passed} test directories passed; {failed} failed; '
          f'{excluded} modules excluded.', flush=True)
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
