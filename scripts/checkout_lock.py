#!/usr/bin/env python3
"""One interactive writer per checkout (TOOLSET-290-12); also a standalone Claude Code hook.

The first session to edit a file in a repository's canonical checkout holds it until
every file it edited is clean (committed or reverted) or the session ends. A dead
owner also lets go after the grace period, without discarding its edits. Another
session's edit there is denied, naming the holder and its files; it works in
`.worktrees/` through EnterWorktree meanwhile. Reads and `.worktrees/` are never locked.

Install in ~/.claude/hooks and register PreToolUse (Edit|Write|MultiEdit|NotebookEdit)
and SessionEnd. By hand: checkout_lock.py status|release [REPO].
"""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

EDIT_TOOLS = ('Edit', 'Write', 'MultiEdit', 'NotebookEdit')
# A holder whose last edit is this recent is not passed on for looking clean: the hook runs
# before the edit lands, so its file is still clean for that moment.
GRACE = 60
LOCK = 'interactive-writer.json'


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'git command failed')
    return result.stdout.rstrip('\n')  # porcelain lines start with a space


def locked_checkout(path):
    """(canonical checkout, Git common dir) when ``path`` is in a canonical checkout and not
    under its `.worktrees/`; else None. Linked worktrees, and paths outside Git, are never locked."""
    folder = Path(path).absolute()
    folder = folder if folder.is_dir() else folder.parent
    while not folder.is_dir():
        folder = folder.parent
    try:
        top = Path(git(folder, 'rev-parse', '--show-toplevel')).resolve()
        common = Path(git(folder, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
        first = git(folder, 'worktree', 'list', '--porcelain', '-z').split('\0\0')[0].split('\0')
    except ValueError:
        return None
    if 'bare' in first or not first[0].startswith('worktree '):
        return None
    # Submodules list their Git directory (.git/modules/NAME), whose core.worktree
    # points at the canonical checkout. Resolve that checkout before comparing.
    canonical = Path(git(first[0][9:], 'rev-parse', '--show-toplevel')).resolve()
    if canonical != top:
        return None
    try:
        Path(path).absolute().resolve().relative_to(top / '.worktrees')
        return None
    except ValueError:
        return top, common


def dirty(root, files):
    """The ``files`` (relative to ``root``) with uncommitted changes, including ignored paths."""
    if not files:
        return []
    out = git(root, 'status', '--porcelain', '-z', '--untracked-files=all',
              '--ignored=traditional', '--', *files)
    entries = [e[3:] for e in out.split('\0') if len(e) > 3]
    return sorted(f for f in files if f in entries or any(e.startswith(f.rstrip('/') + '/') for e in entries))


def transaction(common):
    """An exclusive lock on the record for one read-modify-write."""
    stream = open(Path(common) / (LOCK + '.lock'), 'a')
    fcntl.flock(stream, fcntl.LOCK_EX)
    return stream


def read(common):
    try:
        record = json.loads((Path(common) / LOCK).read_text())
        return record if isinstance(record, dict) and record.get('session') else None
    except (OSError, ValueError):
        return None


def write(common, record):
    path = Path(common) / LOCK
    if record is None:
        path.unlink(missing_ok=True)
        return
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(record))
    os.replace(tmp, path)


def process(pid):
    """Parent PID, start time and command; None only when ps confirms no such PID."""
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'ppid=', '-o', 'lstart=', '-o', 'comm='],
                            capture_output=True, text=True, timeout=5,
                            env={**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC'})
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return None
    fields = result.stdout.split(None, 6)
    if result.returncode or len(fields) != 7:
        raise ValueError('could not determine checkout owner process')
    return int(fields[0]), ' '.join(fields[1:6]), fields[6].strip()


def owner():
    """Identify the session parent, skipping short-lived hook command shells."""
    pid = os.getppid()
    try:
        while pid > 1:
            info = process(pid)
            if info is None:
                break
            parent, started, command = info
            if Path(command).name.lstrip('-') not in ('sh', 'bash', 'dash', 'zsh', 'ksh', 'fish'):
                return {'pid': pid, 'started': started}
            pid = parent
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass  # Unknown liveness retains the original dirty-file protection.
    return {}


def dead_owner(record):
    if not record.get('pid') or not record.get('started'):
        return False  # Legacy records have no liveness evidence.
    try:
        info = process(record['pid'])
        return info is None or info[1] != record['started']
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def passed_on(record, root, now):
    """After the grace period, a clean holder or a confirmed dead owner lets go."""
    return now - record.get('touched', 0) >= GRACE and (
        dead_owner(record) or not dirty(root, record.get('files') or []))


def deny(reason):
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                             'permissionDecisionReason': reason}}))


def hook(payload, now=None):
    now = time.time() if now is None else now
    event, session = payload['hook_event_name'], payload.get('session_id') or ''
    if event == 'SessionEnd':
        found = locked_checkout(Path(payload.get('cwd') or '.'))
        if found:
            with transaction(found[1]):
                if (read(found[1]) or {}).get('session') == session:
                    write(found[1], None)
        return
    if event != 'PreToolUse' or payload.get('tool_name') not in EDIT_TOOLS or not session:
        return
    tool = payload.get('tool_input') or {}
    target = tool.get('file_path') or tool.get('notebook_path')
    if not target:
        return
    target = Path(payload.get('cwd') or '.') / target
    found = locked_checkout(target)
    if not found:
        return
    root, common = found
    relative = str(target.absolute().resolve().relative_to(root))
    with transaction(common):
        record = read(common)
        if record and record['session'] != session and not passed_on(record, root, now):
            files = dirty(root, record.get('files') or []) or record.get('files') or []
            deny(f'Another session ({record["session"]}) is editing this checkout: '
                 + ', '.join(files[:8]) + (f' and {len(files) - 8} more' if len(files) > 8 else '')
                 + '. One interactive session writes a checkout at a time. Work in an isolated '
                 'worktree (EnterWorktree, under .worktrees/) or wait until those files are committed. '
                 f'The owner can free it with: python3 {Path(__file__).resolve()} release {root}')
            return
        files = record['files'] if record and record['session'] == session else []
        write(common, {'session': session, 'transcript': payload.get('transcript_path') or '',
                       'files': sorted({*files, relative}), 'since': record['since'] if files else now,
                       'touched': now, **owner()})


def main(argv):
    if not argv:
        hook(json.load(sys.stdin))
        return 0
    if argv[0] not in ('status', 'release') or len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    found = locked_checkout(Path(argv[1] if len(argv) > 1 else '.'))
    if not found:
        print('not a canonical checkout', file=sys.stderr)
        return 1
    root, common = found
    with transaction(common):
        record = read(common)
        if not record:
            print(f'{root}: no interactive writer')
            return 0
        left = dirty(root, record.get('files') or [])
        print(f'{root}: held by session {record["session"]} since '
              + time.strftime('%Y-%m-%d %H:%M', time.localtime(record.get('since', 0)))
              + (f'; uncommitted: {", ".join(left)}' if left else '; its files are clean'))
        if argv[0] == 'release':
            write(common, None)
            print('released' + (f'; these stay uncommitted: {", ".join(left)}' if left else ''))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (KeyError, OSError, ValueError) as exc:
        print(f'Checkout lock: {exc}', file=sys.stderr)
        sys.exit(1)
