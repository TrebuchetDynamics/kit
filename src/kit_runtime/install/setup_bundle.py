"""Complete explicit bundle setup, then verify and rewire every live profile.

Runs only from install/setup entry points, never during plugin discovery.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
_preflight = _KIT_COMPAT.peer(globals(), 'setup_preflight')
preflight, print_plan = _preflight.preflight, _preflight.print_plan

ROOT = _KIT_LAYOUT.root


def live_profiles(root):
    if (root / 'profiles').is_symlink():
        raise ValueError('Refusing symlinked profiles directory')
    result = [('default', root)]
    markers = ('config.yaml', '.env', 'SOUL.md', 'profile.yaml', 'auth.json', 'state.db')
    for home in sorted((root / 'profiles').glob('*')):
        # Hermes ignores tombstoned, invalidly named and unmarked entries, so a
        # stray symlink among them must not abort setup; refuse only live ones.
        if (home.is_dir() and home.name != 'default'
                and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', home.name)
                and not (root / 'profiles/.deleted' / home.name).exists()
                and any((home / m).is_file() or (home / m).is_symlink() for m in markers)):
            if home.is_symlink():
                raise ValueError(f'Refusing shared/symlinked profile: {home.name}')
            result.append((home.name, home))
    return result


def report_elapsed(label, started):
    print(f'{label}: done in {time.monotonic() - started:.1f}s', flush=True)


def read_config(profile, home):
    # For reporting only; never expose arbitrary profile values or fail setup
    # because the optional comparison could not read them.
    config = home / 'config.yaml'
    try:
        if not config.is_symlink():
            if config.is_file():
                return config.read_bytes()
            if not config.exists():
                return b''
    except FileNotFoundError:
        return b''
    except OSError:
        pass
    print(f'Warning: cannot compare config.yaml for {profile}', flush=True)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-home', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--bundle-only', action='store_true', help='Set up bundled skills and commands only')
    parser.add_argument('--no-reload', action='store_true', help='Explicitly defer live gateway wiring')
    parser.add_argument('--yes-deps', action='store_true')
    # Compatibility: full setup and enablement are now defaults.
    parser.add_argument('--setup', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--enable', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = (args.hermes_home or Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')).expanduser()
    if root.parent.name == 'profiles': root = root.parent.parent
    root = root.resolve()
    if not root.is_dir(): parser.error(f'Hermes root does not exist: {root}')
    try:
        profiles = live_profiles(root)
    except ValueError as exc:
        parser.error(str(exc))
    for name in ('install-skills.sh', 'install-plugins.sh'):
        if not (ROOT / name).is_file(): parser.error(f'Missing installer: {name}')
    started = time.monotonic()
    try:
        report = preflight(ROOT, root, profiles, bundle_only=args.bundle_only)
        print_plan(report)
    except (ValueError, OSError, KeyError) as exc:
        print(f'Preflight failed ({type(exc).__name__}); no installation stages started.')
        return 1
    finally:
        report_elapsed('preflight', started)
    if report['errors']:
        return 1
    if args.dry_run:
        print(f'Bundle setup preview: {len(profiles)} profiles; no installation stages started.')
        return 0
    common = ['--hermes-home', str(root)]
    if args.dry_run: common.append('--dry-run')
    plugins = ['bash', str(ROOT / 'install-plugins.sh'), '--sources-only', '--setup', '--enable', *common]
    if args.bundle_only: plugins.append('--bundle-only')
    if args.yes_deps: plugins.append('--yes-deps')
    env = dict(os.environ, HERMES_HOME=str(root))
    receipt_fd = env.pop('KIT_INSTALL_HERMES_RECEIPT_FD', None)
    summary = env.get('KIT_INSTALL_HERMES_SUMMARY') == '1'
    failures = []

    def run(label, command):
        print(f'Setup: {label}', flush=True)
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, check=False)
            if result.returncode:
                print(f'Failed: {label} (exit {result.returncode})', flush=True)
                failures.append(label)
        except OSError as exc:
            print(f'Failed: {label}: {exc}', flush=True)
            failures.append(label)
        finally:
            report_elapsed(label, started)

    run('bundled skills', ['bash', str(ROOT / 'install-skills.sh'), *common])
    before = {profile: read_config(profile, home) for profile, home in profiles} if summary else {}
    run('plugins and configuration', plugins)
    for profile, home in profiles:
        if args.dry_run:
            print(f'Plan: verify bundled skills/plugins and refresh gateway ({profile})')
            continue
        command = ['hermes', '-p', profile, 'kit', 'finalize', '--hermes-home', str(root)]
        if args.bundle_only: command.append('--bundle-only')
        if args.no_reload: command.append('--no-reload')
        # Even partially failed installs must refresh successful registrations and
        # expose missing capabilities. A later pass never masks an earlier failure.
        run(f'verify/wire {profile}', command)
        if summary:
            after = read_config(profile, home)
            change = ('unverified' if before[profile] is None or after is None else
                      'changed' if before[profile] != after else 'unchanged')
            print(f'Profile {profile} settings: {change}', flush=True)
    state = 'incomplete' if failures else 'complete'
    print(f'Bundle setup {state}: {len(profiles)} profiles; {len(failures)} failed stages.')
    receipt = {'status': state, 'gateway_restart': 'not_requested',
               'gateway_restart_action': ('Native setup owns profile wiring; deferred by --no-reload'
                                          if args.no_reload else 'Native setup owns profile wiring; no process restart requested'),
               'failed_stages': failures}
    if failures:
        receipt.update(error='Failed stages: ' + ', '.join(failures),
                       action='Repair the failed stages and rerun ./install.sh --only hermes with the same setup options')
    if receipt_fd is not None:
        try:
            with os.fdopen(int(receipt_fd), 'w', encoding='utf-8') as stream:
                json.dump(receipt, stream)
        except (OSError, ValueError):
            print('Warning: could not send the setup receipt privately; showing it below.')
        else:
            return int(bool(failures))
    print(json.dumps(receipt))
    return int(bool(failures))


if __name__ == '__main__': raise SystemExit(main())
