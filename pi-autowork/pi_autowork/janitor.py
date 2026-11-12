"""Stale agent scratch in a RAM-backed /tmp is removed, so it cannot cap the workers.

Workers and reviewers copied whole repositories into /tmp and left them: on one host 39 GB in
7,839 entries, which made the memory gate start no new worker (TOOLSET-162-d2). A top-level
/tmp entry is removed only when every rule holds: the runner's user owns it, it is not a
socket or a system name, nothing inside it changed for PI_AUTOWORK_TMP_STALE seconds (default
7200; 0 turns the janitor off), no unfinished slot reserves it, and no process uses it as
its working directory or holds a file in it open. One sweep runs per host at most every
SWEEP_EVERY seconds, under a lock; incomplete slot discovery defers cleanup.
Standard library only.

    janitor.py sweep [TMP]   # sweep now and print what was freed
"""
if __name__ == '__main__' and not __package__:
    import runpy
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    _entry = runpy.run_path(str(_root / 'scripts/autowork_bootstrap.py'))
    raise SystemExit(_entry['run'](_root, 'pi_autowork.janitor', sys.argv[1:]))

import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

SWEEP_EVERY = 1800
DEFAULT_STALE = 7200
KEEP = ('.X11-unix', '.ICE-unix', '.font-unix', '.XIM-unix', '.Test-unix')
KEEP_PREFIXES = ('tmux-', 'ssh-', 'systemd-', 'snap-', 'pulse-', 'krb5', 'dbus-', 'claude-')


def stale_after(env=os.environ):
    try:
        return int(env.get('PI_AUTOWORK_TMP_STALE', DEFAULT_STALE))
    except ValueError:
        return DEFAULT_STALE


def in_use(tmp):
    """Top-level names under ``tmp`` that a process works in or holds a file open in."""
    prefix = str(tmp).rstrip('/') + '/'
    used = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        links = [proc / 'cwd']
        try:
            links += list((proc / 'fd').iterdir())
        except OSError:
            pass
        for link in links:
            try:
                target = os.readlink(link)
            except OSError:
                continue
            if target.startswith(prefix):
                used.add(target[len(prefix):].split('/', 1)[0])
    return used


def changed_since(path, cutoff):
    """Whether anything at or under ``path`` was modified at or after ``cutoff``."""
    try:
        if os.lstat(path).st_mtime >= cutoff:
            return True
    except OSError:
        return False
    if not os.path.isdir(path) or os.path.islink(path):
        return False
    for root, dirs, files in os.walk(path, onerror=lambda error: None):
        for name in dirs + files:
            try:
                if os.lstat(os.path.join(root, name)).st_mtime >= cutoff:
                    return True
            except OSError:
                continue
    return False


def size(path):
    total = 0
    for root, _, files in os.walk(path, onerror=lambda error: None):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total if os.path.isdir(path) else (os.lstat(path).st_size if os.path.lexists(path) else 0)


# Bounded runner-state retention (TOOLSET-442): engine.err and the per-run evidence of each
# state key grow without limit. Keep the newest diagnostics and the evidence an unfinished
# slot, an unread gate receipt or a live review still reads; trim the rest by age and size.
ENGINE_ERR_BYTES = 1 << 20
STATE_STALE = 30 * 24 * 3600
STATE_MAX_BYTES = 512 * 1024 * 1024
EVIDENCE_DIRS = ('full-check', 'runs', 'sessions', 'review-tmp')
OPEN_SLOT_STATES = ('held', 'interrupted', 'dispatched', 'running', 'reported', 'integrating', 'integrated')


def _setting(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _running(record):
    """Only recorded start ticks establish that a runner lives (mirrors processes.running)."""
    if not isinstance(record, dict) or not record.get('start_time'):
        return False
    try:
        fields = (Path(f'/proc/{int(record["pid"])}/stat')).read_text().rsplit(')', 1)[1].split()
    except (OSError, KeyError, TypeError, ValueError, IndexError):
        return False
    return fields[0] not in ('Z', 'X') and fields[19] == str(record['start_time'])


def common_dir(repo):
    """The repository's shared Git directory, or None when Git cannot resolve it."""
    try:
        result = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')},
                                capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(result.stdout.strip()) if not result.returncode and result.stdout.strip() else None


def state_record(state_dir):
    """The state key's runner/status record, or an empty mapping when neither reads."""
    for name in ('runner.json', 'status.json'):
        try:
            value = json.loads((Path(state_dir) / name).read_text())
            if isinstance(value, dict):
                return value
        except (OSError, ValueError):
            continue
    return {}


def open_tasks(state_dir):
    """Task names of this state's unfinished slots, or None when discovery is incomplete."""
    repo = state_record(state_dir).get('repo')
    if not repo:
        return None
    common = common_dir(repo)
    if common is None:
        return None
    try:
        paths = list((common / 'autowork-execution' / 'slots').glob('*.json'))
    except OSError:
        return None
    tasks = set()
    for path in paths:
        try:
            slot = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if isinstance(slot, dict) and slot.get('state') in OPEN_SLOT_STATES:
            tasks.add(str(slot.get('task_id') or path.stem))
    return tasks


def open_files():
    """Real paths that live processes hold open right now (files, directories, deleted paths)."""
    held = set()
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        links = [proc / 'cwd']
        try:
            links += list((proc / 'fd').iterdir())
        except OSError:
            pass
        for fd in links:
            try:
                held.add(os.readlink(fd).removesuffix(' (deleted)'))
            except OSError:
                continue
    return held


def _held(path, held):
    """Whether ``path`` or a file under it is in the open-path set."""
    real = os.path.realpath(Path(path))
    return real in held or any(open_path.startswith(real.rstrip('/') + '/')
                               for open_path in held)


def bound_engine_err(state_dir, limit=None, held=None):
    """Keep only the newest ``limit`` bytes of a state key's engine.err: bytes freed."""
    limit = _setting('PI_AUTOWORK_ENGINE_ERR_BYTES', ENGINE_ERR_BYTES) if limit is None else limit
    path = Path(state_dir) / 'engine.err'
    try:
        if limit <= 0 or path.is_symlink() or not path.is_file():
            return 0
        total = path.stat().st_size
        if total <= limit or _held(path, open_files() if held is None else held):
            return 0  # small enough, or a writer still holds it open; bound it once the writer closes
        with open(path, 'rb') as stream:
            stream.seek(total - limit)
            keep = stream.read()
    except OSError:
        return 0
    if b'\n' in keep:
        keep = keep[keep.index(b'\n') + 1:]  # start at a line boundary, not mid-diagnostic
    try:
        path.write_bytes(keep)
    except OSError:
        return 0
    return total - len(keep)


def state_evidence(state_dir):
    """Top-level entries under a state key's evidence directories."""
    for name in EVIDENCE_DIRS:
        base = Path(state_dir) / name
        if not base.is_dir() or base.is_symlink():
            continue
        try:
            yield from base.iterdir()
        except OSError:
            continue


def _live_review(entry):
    """A review/batch scratch (`aw-r-<pid>-*`) whose creating process still lives."""
    match = re.match(r'aw-[rb]-(\d+)-', entry.name)
    if not match:
        return False
    try:
        return (Path(f'/proc/{int(match.group(1))}/stat')).read_text().rsplit(')', 1)[1].split()[0] not in ('Z', 'X')
    except (OSError, ValueError, IndexError):
        return False


def _named_for(name, task):
    """Whether a file name carries ``task`` as a whole segment (so T-1 never matches T-12)."""
    safe = re.sub(r'[^A-Za-z0-9._-]', '-', str(task))
    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(safe) + r'(?![A-Za-z0-9])', name))


def _referenced(entry, tasks, held):
    """Whether an evidence entry is still read by an open slot, gate receipt or review."""
    if _held(entry, held):
        return True
    if entry.parent.name == 'full-check' and entry.suffix in ('.json', '.jsonl'):
        return True  # a gate receipt stays, even after its task closes
    if entry.parent.name == 'review-tmp':
        return _live_review(entry)
    return any(_named_for(entry.name, task) for task in tasks)


def _remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            return False
    return not os.path.lexists(path)


def _trim_evidence(state_dir, tasks, *, now, stale, max_bytes, held):
    """(count, bytes) removed of unreferenced evidence, oldest first by age then size."""
    removed = freed = 0
    kept = []
    for entry in state_evidence(state_dir):
        try:
            info = entry.lstat()
        except OSError:
            continue
        if _referenced(entry, tasks, held):
            continue  # evidence still read is never trimmed
        if stale > 0 and info.st_mtime < now - stale:
            amount = size(entry)
            if _remove(entry):
                removed, freed = removed + 1, freed + amount
            continue
        kept.append((info.st_mtime, entry))
    kept.sort(key=lambda item: item[0])  # oldest first, so a size cap frees the least recent
    total = sum(size(entry) for _, entry in kept)
    for _, entry in kept:
        if total <= max_bytes:
            break
        amount = size(entry)
        if _remove(entry):
            total, removed, freed = total - amount, removed + 1, freed + amount
    return removed, freed


def retain_state(state_root, *, now=None, stale=None, max_bytes=None):
    """Bound engine.err and per-run evidence of every state key that is not a live stranger.

    A state key whose record names a live process other than this one is skipped entirely.
    Incomplete slot discovery bounds engine.err but trims no evidence. Returns
    ``(removed, bytes_freed)``.
    """
    now = time.time() if now is None else now
    stale = _setting('PI_AUTOWORK_STATE_STALE', STATE_STALE) if stale is None else stale
    max_bytes = _setting('PI_AUTOWORK_STATE_MAX_BYTES', STATE_MAX_BYTES) if max_bytes is None else max_bytes
    removed = freed = 0
    try:
        states = [p for p in Path(state_root).iterdir() if p.is_dir() and not p.is_symlink()]
    except OSError:
        return removed, freed
    held = open_files()
    for state_dir in states:
        record = state_record(state_dir)
        if _running(record) and record.get('pid') != os.getpid():
            continue  # another live runner's evidence stays untouched
        freed += bound_engine_err(state_dir, held=held)
        tasks = open_tasks(state_dir)
        if tasks is None:
            continue
        count, amount = _trim_evidence(state_dir, tasks, now=now, stale=stale,
                                       max_bytes=max_bytes, held=held)
        removed, freed = removed + count, freed + amount
    return removed, freed


CACHE_DIRS = ('target', 'build', '.dart_tool')
# The review's integration checkout, main-check and maintainer scratch, and session worktrees.
NEVER_PRUNED = ('autowork-integration', 'pi-scratch-', 'pi-autowork-')


def build_caches(worktrees, busy=(), *, stale=None, now=None, urgent=False):
    """Regenerable build output in this runner's own worktrees that may go (TOOLSET-210-53):
    `target/`, `build/` and `.dart_tool/` directly in a worktree under ``worktrees`` that is
    not in ``busy`` (running or verifying slots, the session), ignored by Git there, and, unless
    ``urgent`` (the disk is low), untouched for ``stale`` seconds. Sources are never candidates."""
    stale = DEFAULT_STALE if stale is None else stale
    now = time.time() if now is None else now
    busy = {os.path.realpath(p) for p in busy if p}
    found = []
    try:
        trees = sorted(Path(worktrees).iterdir())
    except OSError:
        return found
    for tree in trees:
        if (not tree.is_dir() or tree.is_symlink() or os.path.realpath(tree) in busy or not (tree / '.git').exists()
                or tree.name.startswith(NEVER_PRUNED)):
            continue
        for name in CACHE_DIRS:
            cache = tree / name
            if not cache.is_dir() or cache.is_symlink():
                continue
            ignored = subprocess.run(['git', '-C', str(tree), 'check-ignore', '-q', name],
                                     capture_output=True).returncode == 0
            if not ignored or (not urgent and changed_since(cache, now - stale)):
                continue
            found.append(cache)
    # Oldest first, so a low disk frees the least recently used output first.
    return sorted(found, key=lambda p: os.lstat(p).st_mtime)


def prune_build_caches(worktrees, busy=(), **options):
    """(count, bytes) removed of build_caches()."""
    count = freed = 0
    for cache in build_caches(worktrees, busy, **options):
        amount = size(cache)
        shutil.rmtree(cache, ignore_errors=True)
        if not cache.exists():
            count, freed = count + 1, freed + amount
    return count, freed


def reserved_tmp(tmp, state_root=None):
    """Top-level scratch reserved by unfinished slots, or None if discovery failed.

    A sweep is host-wide: consult every registered runner, including stopped ones,
    but read current engine slots, not potentially stale health snapshots or history.
    Incomplete discovery must never turn a held allocation into disposable scratch.
    """
    root = Path(state_root or os.environ.get('PI_AUTOWORK_STATE_DIR') or
                Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'pi-autowork')
    repos, reserved = set(), set()
    for record in [*root.glob('*/runner.json'), *root.glob('*/status.json')]:
        try:
            repo = json.loads(record.read_text()).get('repo')
            if repo:
                repos.add(repo)
        except (OSError, ValueError, AttributeError, TypeError):
            return None
    for repo in repos:
        common = common_dir(repo)
        if common is None:
            return None
        try:
            for slot in (common / 'autowork-execution' / 'slots').glob('*.json'):
                try:
                    phase = json.loads(slot.read_text()).get('state')
                    if phase not in OPEN_SLOT_STATES:
                        continue
                    data = common / 'autowork-execution' / 'slot-data' / slot.stem
                    try:
                        paths = [Path(json.loads((data / 'tmp.json').read_text())['path'])]
                    except FileNotFoundError:  # old slots allocated scratch beside each attempt's report
                        paths = list(data.glob('attempt-*/tmp'))
                    for path in paths:
                        try:
                            relative = path.resolve().relative_to(Path(tmp).resolve())
                        except ValueError:  # an allocation on disk, outside the swept root
                            continue
                        if relative.parts:
                            reserved.add(relative.parts[0])
                except FileNotFoundError:
                    continue  # a slot retired while being read
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    return None
        except OSError:
            return None
    return reserved


def candidates(tmp='/tmp', *, stale=None, now=None, uid=None, used=None, state_root=None):
    """Top-level entries of ``tmp`` that every rule allows removing."""
    stale = stale_after() if stale is None else stale
    if stale <= 0:
        return []
    now = time.time() if now is None else now
    uid = os.getuid() if uid is None else uid
    reserved = reserved_tmp(tmp, state_root)
    if reserved is None:
        return []  # no destructive cleanup without a complete reservation inventory
    used = (in_use(tmp) if used is None else used) | reserved
    cutoff = now - stale
    out = []
    try:
        entries = list(os.scandir(tmp))
    except OSError:
        return []
    for entry in entries:
        name = entry.name
        if name in KEEP or name.startswith(KEEP_PREFIXES) or name in used:
            continue
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if info.st_uid != uid or stat.S_ISSOCK(info.st_mode) or info.st_mtime >= cutoff:
            continue  # the cheap check first; a deep one only for what looks old
        if changed_since(entry.path, cutoff):
            continue
        out.append(entry.path)
    return out


def sweep(tmp='/tmp', **options):
    """Remove every candidate: (count, bytes freed)."""
    count, freed = 0, 0
    for path in candidates(tmp, **options):
        amount = size(path)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                os.unlink(path)
            except OSError:
                continue
        if not os.path.lexists(path):
            count, freed = count + 1, freed + amount
    return count, freed


def sweep_if_due(state_root, tmp='/tmp', now=None):
    """One sweep per host every SWEEP_EVERY seconds: (count, bytes), or None when not due."""
    if stale_after() <= 0:
        return None
    now = time.time() if now is None else now
    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    record = root / 'janitor.json'
    with open(root / 'janitor.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None  # another runner is sweeping
        try:
            last = json.loads(record.read_text()).get('at', 0)
        except (OSError, ValueError, AttributeError):
            last = 0
        if now - last < SWEEP_EVERY:
            return None
        count, freed = sweep(tmp, now=now, state_root=root)
        state_count, state_freed = retain_state(root, now=now)
        count, freed = count + state_count, freed + state_freed
        record.write_text(json.dumps({'at': now, 'removed': count, 'freed_bytes': freed,
                                      'state_removed': state_count, 'state_freed_bytes': state_freed}))
        return count, freed


def main(argv):
    if argv[:1] != ['sweep']:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    count, freed = sweep(argv[1] if len(argv) > 1 else '/tmp')
    print(f'removed {count} stale /tmp entries, {freed / 2 ** 30:.1f} GB')
    return 0


def _compat_main(argv):
    import sys
    previous = sys.argv
    sys.argv = [previous[0], *argv]
    try:
        raise SystemExit(main(sys.argv[1:]))
    finally:
        sys.argv = previous
