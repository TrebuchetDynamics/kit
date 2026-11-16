#!/usr/bin/env python3
"""Refresh Kit's dedicated source and delegate to that checkout's suite installer."""
import argparse
import contextlib
import os
from pathlib import Path
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

SOURCE = 'https://github.com/TrebuchetDynamics/kit.git'
COMPONENTS = {'pi', 'pi-bolt', 'tx', 'hermes', 'claude', 'codex', 'orbi'}
NOTICE = ('Default scope: all available components; may bootstrap Pi/Pi-Bolt and restart active '
          'supported integrations. --no-reload does NOT suppress final restarts. Hermes may '
          'perform a nested broader full-suite refresh, including another source advance. '
          'Native prompts, missing-host rules and partial failures remain installer-owned.')


class Hold(Exception):
    """A preserved boundary requiring repair, not a force option."""


def _source_url():
    # Internal fixture seam only; the CLI has no arbitrary-source option.
    return SOURCE


def run(argv, *, cwd=None, env=None, timeout=120, capture=True, pass_fds=()):
    """Bound the whole process group, including native children; preserve terminal prompts."""
    process = subprocess.Popen(argv, cwd=cwd, env=env, text=True, start_new_session=True,
                               pass_fds=pass_fds,
                               stdout=subprocess.PIPE if capture else None,
                               stderr=subprocess.PIPE if capture else None)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout or '', stderr or '')


def git(source, *args, check=True):
    # Ignore caller Git injection/global URL rewrites and optional index refresh writes.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
    result = run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'protocol.file.allow=never',
                  *(['-C', str(source)] if source else []), *args], env=env)
    if check and result.returncode:
        raise Hold(f'Git {args[0]} failed: {result.stderr.strip()}; preserve source and retry after repair')
    return result


def text(source, *args):
    return git(source, *args).stdout.strip()


def safe_path(path, *, owned=False):
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise Hold(f'Symlink destination/ancestor: {part}; choose a persistent non-symlink data directory')
    if path.exists():
        info = path.stat()
        if (owned and info.st_uid != os.getuid()) or info.st_mode & 0o022:
            raise Hold(f'Foreign/unsafe ownership or permissions: {path}; reconcile ownership, then retry')


def destination():
    data = os.environ.get('XDG_DATA_HOME')
    home = Path(os.environ.get('HOME', ''))
    if data and not Path(data).is_absolute():
        raise Hold('XDG_DATA_HOME must be absolute; set an absolute persistent path or unset XDG_DATA_HOME')
    if not home.is_absolute():
        raise Hold('HOME must be absolute; correct HOME and retry')
    base = Path(data) if data else home / '.local/share'
    if base == Path('/tmp') or base == Path('/'):
        raise Hold('Use a dedicated persistent XDG_DATA_HOME, not /tmp or /')
    source = base / 'kit/source'
    if any((parent / '.git').exists() for parent in source.parents):
        raise Hold('Destination is inside a project checkout; use a dedicated persistent XDG_DATA_HOME instead')
    return source


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', '--read-only', '--questions-only', '--list',
                        dest='preview', action='store_true', help='no-write path/argv preview; no host probes')
    parser.add_argument('--no-restarts', action='store_true', help='refuse: installer cannot honor this restriction')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--only')
    selection.add_argument('--all', '--full', action='store_true')
    parser.add_argument('--skip')
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument('--verbose', '-v', action='store_true')
    verbosity.add_argument('--quiet', '-q', action='store_true')
    parser.add_argument('--color', choices=('auto', 'always', 'never'))
    for flag in ('--bundle-only', '--no-reload', '--yes-deps'):
        parser.add_argument(flag, action='store_true')
    parser.add_argument('--hermes-home')
    parser.add_argument('--no-pull', action='store_true', help='already supplied by this helper')
    # A menu cannot be scope-checked before source mutation. Use explicit selection.
    parser.add_argument('--menu', action='store_true', help='unsupported here; use --only/--skip')
    args = parser.parse_args(argv)
    if args.no_restarts:
        raise Hold('No-restarts restriction cannot be honored: --no-reload does not suppress final restart; no changes made')
    if args.menu:
        raise Hold('Menu scope cannot be checked before mutation; use --only/--skip excluding Hermes, or unrestricted full suite')
    selected = set(COMPONENTS)
    for value in (args.only, args.skip):
        if value and set(value.split(',')) - COMPONENTS - {''}:
            raise Hold('Unknown component; choose from ' + ','.join(sorted(COMPONENTS)))
    if args.only:
        selected = set(filter(None, args.only.split(',')))
    if args.skip:
        selected -= set(args.skip.split(','))
    if 'hermes' in selected and selected != COMPONENTS:
        raise Hold('Restricted Hermes selection can launch a nested broader full-suite refresh; '
                   'exclude Hermes (--skip hermes), or separately authorize an unrestricted native cascade; no changes made')
    # Keep literal caller tokens (including spaces) and order; strip only helper-owned flags.
    stripped = {'--dry-run', '--read-only', '--questions-only', '--list', '--no-pull'}
    forwarded = []
    takes_value = {'--only', '--skip', '--color', '--hermes-home'}
    value_next = False
    for arg in argv:
        if value_next:
            forwarded.append(arg)
            value_next = False
        elif arg not in stripped:
            forwarded.append(arg)
            value_next = arg in takes_value
    return args, forwarded


def validate(source):
    safe_path(source, owned=True)
    if not (source / '.git').is_dir() or (source / '.git').is_symlink():
        raise Hold('Unknown source ownership: expected standalone updater checkout; preserve it and reconcile manually')
    for directory, dirs, files in os.walk(source, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            info = path.lstat()
            if source / '.git' in path.parents and path.is_symlink():
                raise Hold(f'Symlinked Git metadata: {path}; reconcile ownership before retry')
            if info.st_uid != os.getuid() or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022):
                raise Hold(f'Foreign/unsafe ownership: {path}; reconcile before retry')
    marker = git(source, 'config', '--local', '--get', 'kit.updateKitOwner', check=False)
    if marker.stdout.strip() != f'{os.getuid()}:{source}':
        raise Hold('Unknown updater ownership; preserve this checkout and reconcile manually; no arbitrary checkout adoption')
    allowed = {'core.repositoryformatversion', 'core.filemode', 'core.bare', 'core.logallrefupdates',
               'core.ignorecase', 'core.precomposeunicode', 'core.symlinks', 'remote.origin.url',
               'remote.origin.fetch', 'branch.main.remote', 'branch.main.merge', 'kit.updatekitowner'}
    config = text(source, 'config', '--local', '--null', '--list')
    if any(entry.split('\n', 1)[0].lower() not in allowed for entry in config.split('\0') if entry):
        raise Hold('Unknown/unsafe local Git configuration; preserve and reconcile before retry')
    if text(source, 'config', '--local', '--get-all', 'remote.origin.url') != SOURCE:
        raise Hold('Wrong origin; expected fixed HTTPS Kit source; preserve checkout and reconcile origin')
    if text(source, 'symbolic-ref', '--quiet', 'HEAD') != 'refs/heads/main':
        raise Hold('Expected attached main branch; preserve history and reconcile branch before retry')
    if text(source, 'rev-parse', '--is-shallow-repository') != 'false':
        raise Hold('Incomplete/shallow source; preserve it and reconcile before retry')
    if text(source, 'status', '--porcelain', '--untracked-files=all', '--ignored'):
        raise Hold('Tracked/untracked/ignored dirt; preserve edits and reconcile source, then retry')
    if text(source, 'worktree', 'list', '--porcelain').count('worktree ') != 1:
        raise Hold('Extra worktrees; preserve work and reconcile ownership before retry')
    for name in ('index.lock', 'shallow.lock', 'HEAD.lock', 'MERGE_HEAD', 'rebase-merge', 'rebase-apply'):
        if (source / '.git' / name).exists():
            raise Hold(f'Concurrent/incomplete Git ownership ({name}); reconcile owner before retry')
    for required in ('install.sh', 'scripts/install_menu.py'):
        payload = source / required
        if not payload.is_file() or payload.is_symlink():
            raise Hold(f'Incomplete source payload: {payload}; preserve evidence and repair before retry')
    return text(source, 'rev-parse', 'HEAD')


def ensure_idle(source, hermes_home=None):
    """Updater flock is not a global/native ownership lock; uncertainty holds."""
    result = run(['lsof', '-nP', '-a', '-u', str(os.getuid()), '-t', '+D', str(source)])
    if result.stdout.strip() or result.stderr.strip() or result.returncode not in (0, 1):
        raise Hold('Live/unknown source consumer (lsof): ' + result.stdout.strip() + ' ' + result.stderr.strip()
                   + '; quiesce/resolve consumers and retry; no process is stopped')
    # Python can close source files after loading them; open-file inventory alone is insufficient.
    if sys.platform == 'linux':
        for process in Path('/proc').iterdir():
            if not process.name.isdigit() or int(process.name) == os.getpid():
                continue
            try:
                if process.stat().st_uid != os.getuid():
                    continue
                args = (process / 'cmdline').read_bytes().decode(errors='replace').split('\0')
                if any(str(source) in arg for arg in args):
                    raise Hold(f'Live source consumer pid={process.name}; wait for it to finish and retry')
            except FileNotFoundError:
                continue
            except PermissionError as error:
                raise Hold('Unknown process ownership; resolve process visibility before retry') from error
    root = Path(hermes_home or os.environ.get('HERMES_HOME') or Path(os.environ['HOME']) / '.hermes')
    for home in [root, *root.glob('profiles/*')]:
        linked = any(path.is_symlink() and path.resolve() == source
                     for path in (home / 'plugins').glob('*'))
        if not linked:
            continue
        if (home / 'gateway.pid').exists():
            raise Hold(f'Live/unknown linked gateway at {home}; resolve native ownership before retry')
        lock = home / 'maintenance/toolset-update/lock'
        if lock.exists():
            import fcntl
            try:
                with lock.open('r') as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, BlockingIOError) as error:
                raise Hold(f'Concurrent/unknown native updater at {home}; retry after native owner finishes') from error


def update(source, flags, args):
    import fcntl
    # Validate before creating the parent/lock, then revalidate under destination ownership.
    for path in (source.parent.parent, source.parent, source):
        safe_path(path, owned=True)
    if source.exists():
        validate(source)
        ensure_idle(source, args.hermes_home)
    source.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lockpath = source.parent / '.update-kit.lock'
    safe_path(lockpath, owned=True)
    fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Hold('Updater busy for this destination; retry after the current invocation finishes') from error
        if source.exists():
            old = validate(source)
            ensure_idle(source, args.hermes_home)
            git(source, 'fetch', '--no-tags', '--no-recurse-submodules', _source_url(), 'refs/heads/main')
            target = text(source, 'rev-parse', 'FETCH_HEAD')
            ancestry = git(source, 'merge-base', '--is-ancestor', old, target, check=False)
            if ancestry.returncode == 1:
                raise Hold(f'Local-ahead/diverged history {old} vs {target}; preserve history and reconcile before retry')
            if ancestry.returncode:
                raise Hold('Git ancestry check failed; preserve source and repair Git history before retry')
            ensure_idle(source, args.hermes_home)
            git(source, 'merge', '--ff-only', '--no-autostash', target)
        else:
            old = 'ABSENT'
            stage = Path(tempfile.mkdtemp(prefix='.source-stage-', dir=source.parent))
            print(f'Clone staging/evidence: {stage} (retained on failure)', flush=True)
            try:
                git(None, 'clone', '--template=', '--branch', 'main', '--', _source_url(), str(stage))
                git(stage, 'remote', 'set-url', 'origin', SOURCE)
                git(stage, 'config', '--local', 'kit.updateKitOwner', f'{os.getuid()}:{stage}')
                validate(stage)
                # Record final identity before publication; never replace an existing destination.
                git(stage, 'config', '--local', 'kit.updateKitOwner', f'{os.getuid()}:{source}')
                if source.exists() or source.is_symlink():
                    raise Hold(f'Destination appeared concurrently; staging retained at {stage}; reconcile ownership')
                stage.rename(source)
            except (Hold, OSError, subprocess.TimeoutExpired) as error:
                (stage / 'update-kit-failure.txt').write_text(str(error) + '\n')
                raise
        selected = text(source, 'rev-parse', 'HEAD')
        print(f'old_sha={old}\nselected_sha={selected}', flush=True)
        argv = ['bash', str(source / 'install.sh'), 'update', '--no-pull', *flags]
        print('Installer: ' + shlex.join(argv), flush=True)
        result = None
        try:
            result = run(argv, cwd=source, timeout=3600, capture=False,
                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), pass_fds=(lock.fileno(),))
            return result.returncode if result.returncode >= 0 else 128 - result.returncode
        finally:
            final = git(source, 'rev-parse', 'HEAD', check=False)
            final_sha = final.stdout.strip() if final.returncode == 0 else 'NOT_CHECKED'
            print(f'final_sha={final_sha}', flush=True)
            if final.returncode:
                print('Final source revision NOT_CHECKED: ' + final.stderr.strip(), flush=True)
            elif final_sha != selected:
                print('Secondary source change during native installation; selected revision was not immutable.', flush=True)
            print(f'installer_exit={result.returncode if result else "INTERRUPTED"}; completed host steps '
                  'are not rolled back. Installation is not live qualification; reload/restart the current '
                  'agent session to discover resources, then verify activation separately.', flush=True)


def main(argv=None):
    try:
        args, flags = parse(list(sys.argv[1:] if argv is None else argv))
        source = destination()
        print(NOTICE, flush=True)
        print(f'Source: {SOURCE} main -> {source}', flush=True)
        if args.preview:
            print('Intended argv: ' + shlex.join(['bash', str(source / 'install.sh'), 'update', '--no-pull', *flags]))
            print('Remote revision, local ownership, host availability and activation: NOT_CHECKED; no probes or writes')
            return 0
        if sys.platform not in ('linux', 'darwin'):
            raise Hold('Supported mutation platforms: Linux/macOS; use --dry-run or a supported host')
        for tool in ('git', 'bash', 'lsof'):
            if not shutil.which(tool):
                raise Hold(f'Missing required tool {tool}; install {tool}, put it on PATH, then retry')
        old_umask = os.umask(0o077)
        try:
            return update(source, flags, args)
        finally:
            os.umask(old_umask)
    except SystemExit as error:
        return error.code
    except KeyboardInterrupt:
        print('Interrupted; source/evidence and completed host steps preserved; inspect before retry', file=sys.stderr)
        return 130
    except (Hold, OSError, subprocess.TimeoutExpired) as error:
        print(f'update-kit held: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
