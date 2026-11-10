"""`autowork tasks ...`: read and edit a repository's tasks/ store. Standard library only.

Reads (list, show, why, validate) use a pinned commit, HEAD by default; --worktree reads
uncommitted edits. Writes (add, field, place, move, hold, release, done, supersede, goal)
change task files in the working tree; only explicit --commit on decide or answer-note
field writes commits the answer alone. Each takes the repository's task
lock, refuses a file that changed since it was read (or since the revision `--expect`
names), refuses a contract change to a task a worker or lease holds, and validates the
whole would-be store before the write is kept. A written file grants no authority beyond
its typed fields, and a declared check still needs the existing approval to run.
`prepare` brings a repository to a valid store (task_prepare.py).
"""
import argparse
from contextlib import contextmanager, nullcontext
from datetime import date, datetime, timezone
import fcntl
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading

from pi_autowork import landing, task_handoff, task_status
from pi_autowork.engine import task_select  # noqa: E402
from pi_autowork.engine import task_store  # noqa: E402
from pi_autowork.engine.task_store import StoreError, TaskStore, WriteError  # noqa: E402

STEP = 1000
# Worker slot states with unfinished work: nothing converts under them.
OCCUPYING = ('dispatched', 'running', 'reported', 'integrating', 'integrated', 'held', 'interrupted')
# ...and those whose attempt is still live: its contract may not change under it. A held or
# interrupted attempt is waiting for exactly that repair.
ACTIVE = ('dispatched', 'running', 'reported', 'integrating', 'integrated')
# The fields a task's contract hash covers, plus its goal: what an admitted attempt ran against.
CONTRACT = ('scope', 'acceptance', 'checks', 'depends_on', 'touches', 'resources', 'kind', 'ownership',
            'live', 'live_actor', 'live_at', 'live_scope', 'waiver_actor', 'waiver_at', 'waiver_for',
            'exclusions', 'goal', 'verified_depends_on')


class CommandError(Exception):
    """A refusal with its message; nothing was written."""


def _git(repo, *args, env=None, raw=False):
    clean = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                            env={**clean, **(env or {})}, timeout=60)
    if result.returncode:
        raise CommandError(f'git {args[0]} failed: {result.stderr.strip()}')
    return result.stdout if raw else result.stdout.strip()


_task_locks = threading.local()


@contextmanager
def locked(repo, *, recover=True):
    """Serialize task access; mutation helpers recover, read-only previews refuse recovery."""
    git_dir = Path(_git(repo, 'rev-parse', '--absolute-git-dir'))
    key = (os.getpid(), git_dir)
    if not hasattr(_task_locks, 'held'):
        _task_locks.held = set()
    journal = git_dir / 'autowork-tasks.transaction'
    if key in _task_locks.held:
        if not recover and journal.exists():
            raise CommandError('interrupted task transaction needs explicit recovery; read changed nothing')
        yield
        return
    with open(git_dir / 'autowork-tasks.lock', 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        _task_locks.held.add(key)
        try:
            if not recover and journal.exists():
                raise CommandError('interrupted task transaction needs explicit recovery; read changed nothing')
            if recover:
                conflicts = _undo(repo, journal)
                if conflicts:
                    raise CommandError('interrupted task edit undone; external edits preserved: ' + ', '.join(conflicts))
            yield
        finally:
            _task_locks.held.remove(key)
            fcntl.flock(handle, fcntl.LOCK_UN)


def _serialized(function):
    @wraps(function)
    def serialized(repo, *args, **kwargs):
        with locked(repo):
            return function(repo, *args, **kwargs)
    return serialized


def in_flight(repo, states=OCCUPYING):
    """(task IDs a worker slot in ``states`` or a live lease holds, problems reading that
    state). Engine modules are imported here only: other commands need none of them."""
    from pi_autowork.engine import parallel_state
    from pi_autowork.engine import task_execution
    held, problems = set(), []
    common = parallel_state.common_dir(Path(repo))
    try:
        slots = parallel_state.slots(common) if (common / 'slots').is_dir() else []
    except ValueError as exc:
        problems.append(f'worker slots cannot be read ({exc})')
        slots = []
    held |= {s['task_id'] for s in slots if s['state'] in states}
    try:
        if parallel_state.live_coordinator(common):
            problems.append('a live parallel coordinator lease')
    except ValueError as exc:
        problems.append(f'the coordinator lease cannot be read ({exc})')
    try:
        lease = task_execution.read(common / 'active.json') if (common / 'active.json').exists() else None
        if lease and task_execution.active_owner(lease):
            problems.append('a live sequential execution lease')
            if isinstance(lease.get('task_id'), str):
                held.add(lease['task_id'])
    except ValueError as exc:
        problems.append(f'the sequential execution lease cannot be read ({exc})')
    return held, problems


def _unheld(repo, tid):
    """Refuse a contract change to a task an attempt holds: integration would set it aside."""
    held, _ = in_flight(repo, ACTIVE)
    if tid in held:
        raise CommandError(f'{tid} is held by a worker slot or a live lease; its contract cannot change now')


def revision(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def expect(repo, tid, rev, goal=False):
    """Refuse when the record is no longer the revision the caller decided from."""
    if rev and revision(_path(repo, tid, goal)) != rev:
        raise CommandError(f'{tid} changed since revision {rev[:12]} was read; reread it; nothing written')


@_serialized
def worktree_store(repo):
    """Read the worktree through an isolated throwaway commit; real objects, index,
    HEAD and refs are untouched. The returned records outlive the temporary objects."""
    if not (Path(repo) / 'tasks').is_dir():
        raise StoreError('tasks/:1: no task store in the working tree')
    with tempfile.TemporaryDirectory() as tmp, task_store.temporary_objects(repo) as objects:
        env = {**objects, 'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        try:
            head = _git(repo, 'rev-parse', '--verify', '-q', 'HEAD', env=env)
        except CommandError:
            head = ''  # An unborn repository can still bootstrap a task store.
        if head:
            _git(repo, 'read-tree', head, env=env)
        _git(repo, 'add', '-A', '--', 'tasks', env=env)
        tree = _git(repo, 'write-tree', env=env)
        ident = {'GIT_AUTHOR_NAME': 'autowork', 'GIT_AUTHOR_EMAIL': 'autowork@localhost',
                 'GIT_COMMITTER_NAME': 'autowork', 'GIT_COMMITTER_EMAIL': 'autowork@localhost'}
        commit = _git(repo, 'commit-tree', tree, *(['-p', head] if head else []), '-m', 'worktree tasks',
                      env={**env, **ident})
        return TaskStore.at(repo, commit, env=objects)


def _path(repo, tid, goal=False):
    return Path(repo) / 'tasks' / ('goals' if goal else 'items') / f'{tid}.md'


def _contents(path):
    return path.read_bytes() if path.exists() else None


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _staged_path(path):
    return path.with_name(f'.{path.name}.autowork-tasks.tmp')


def _stage_bytes(path, content):
    tmp = _staged_path(path)
    # An interrupted restore may have linked this staging inode into the live
    # record. Never truncate/reuse it: a later external edit can be on that inode.
    tmp.unlink(missing_ok=True)
    with tmp.open('xb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    return tmp


def _replace_bytes(path, content):
    """Flush a same-filesystem replacement before advancing the transaction."""
    tmp = _staged_path(path)
    try:
        _stage_bytes(path, content)
        os.replace(tmp, path)
        _sync_dir(path.parent)
    finally:
        tmp.unlink(missing_ok=True)


def _claimed_path(path):
    return path.with_name(f'.{path.name}.autowork-tasks.undo')


def _restore_missing(path, source):
    """Publish a saved inode without replacing anything an external editor created."""
    try:
        os.link(source, path)
    except FileExistsError:
        return False
    _sync_dir(path.parent)
    return True


def _undo_record(path, before, after):
    """Claim the current inode before inspecting it, never overwrite on restore.

    A crash can leave the claimed inode beside the record; the journal makes the
    next undo resume it. If another editor creates a path while we undo, retain
    both versions rather than replacing the editor's new path. ``after`` is None
    when the interrupted batch removed the record.
    """
    if after is None:
        # The batch deleted the record. Restore it only while the name is vacant:
        # an externally recreated record stays authoritative.
        current = _contents(path)
        if current == before:
            return []
        if current is not None:
            return [path]
        if before is None:
            return []
        tmp = _stage_bytes(path, before)
        try:
            restored = _restore_missing(path, tmp)
        finally:
            tmp.unlink(missing_ok=True)
        return [] if restored else [path]
    saved = _claimed_path(path)
    if not saved.exists():
        current = _contents(path)
        if current == before:
            return []
        if current != after:
            return [path]
        try:
            os.rename(path, saved)
        except FileNotFoundError:
            return [] if before is None else [path]  # preserve an external deletion
        _sync_dir(path.parent)
    if _contents(saved) != after:
        # It changed after our read but before the atomic claim. Put it back only
        # if the name is still vacant; otherwise keep its bytes at the saved path.
        if _restore_missing(path, saved) or (path.exists() and os.path.samefile(path, saved)):
            saved.unlink()
            _sync_dir(path.parent)
            return [path]
        return [path, saved]
    if before is not None:
        tmp = _stage_bytes(path, before)
        _restore_missing(path, tmp)
        tmp.unlink()
    conflicts = [] if _contents(path) == before else [path]
    saved.unlink()
    _sync_dir(path.parent)
    return conflicts


def _undo(repo, journal):
    """Restartable undo: claim each path before deciding whether to restore it."""
    if not journal.exists():
        return []
    try:
        records = []
        for name, before, after in json.loads(journal.read_text()):
            if not re.fullmatch(r'tasks/(?:items|goals)/[A-Za-z0-9][A-Za-z0-9_-]*\.md', name):
                raise ValueError('invalid record path')
            records.append((Path(repo) / name, bytes.fromhex(before) if before is not None else None,
                            bytes.fromhex(after) if after is not None else None))
    except (ValueError, TypeError) as exc:
        raise CommandError(f'cannot recover {journal.name}: {exc}') from None
    conflicts = []
    for path, before, after in reversed(records):
        conflicts.extend(str(p.relative_to(repo)) for p in _undo_record(path, before, after))
        _staged_path(path).unlink(missing_ok=True)
    journal.unlink()
    _sync_dir(journal.parent)
    return conflicts


@_serialized
def _write_many(repo, edits):
    """Compare every input before writing, then apply and validate one recoverable set.

    An edit's ``after`` of None removes that path. The journal is durable before the
    first replacement; its removal commits the set. Exceptions undo immediately,
    process death on the next locked access. Working-tree readers use the same lock
    and cannot observe half a batch.
    """
    edits = list(edits)
    records = []
    for path, before, after in edits:
        if _claimed_path(path).exists():
            raise CommandError(f'reconcile preserved external bytes at {_claimed_path(path)} before writing')
        if _contents(path) != before:
            raise CommandError(f'{path.relative_to(repo)} changed since it was read; nothing written')
        records.append((str(path.relative_to(repo)), before.hex() if before is not None else None,
                        after.encode().hex() if after is not None else None))
    journal = Path(_git(repo, 'rev-parse', '--absolute-git-dir')) / 'autowork-tasks.transaction'
    _replace_bytes(journal, json.dumps(records).encode())
    try:
        for path, before, after in edits:
            path.parent.mkdir(parents=True, exist_ok=True)
            if after is None:
                path.unlink()
                _sync_dir(path.parent)
            else:
                _replace_bytes(path, after.encode())
        worktree_store(repo)
    except BaseException as exc:
        conflicts = _undo(repo, journal)
        if isinstance(exc, StoreError):
            detail = 'external edits preserved: ' + ', '.join(conflicts) if conflicts else 'nothing written'
            raise CommandError(f'{exc}; {detail}') from None
        raise
    journal.unlink()
    _sync_dir(journal.parent)


def _write(repo, path, before, after):
    _write_many(repo, [(path, before, after)])


def _section_ranks(store, section, without=None):
    """Open tasks of a section in priority order: (rank, id) pairs."""
    return sorted((t.rank, t.id) for t in store.tasks.values()
                  if t.section == section and t.status == 'open' and t.id != without and t.rank is not None)


def bottom_rank(store, section, without=None):
    ranks = [rank for rank, _ in _section_ranks(store, section, without)]
    return (max(ranks) // STEP + 1) * STEP if ranks else STEP


def place_between(ranked, position):
    """New ranks to insert one item at ``position`` of ``ranked`` [(rank, id)], as
    {id or None: rank}; None is the inserted item. Midpoint when a gap exists; else only
    the contiguous run without room is spread, never the whole section."""
    items = [None if i == position else ranked[i - (i > position)][1] for i in range(len(ranked) + 1)]
    rank = {tid: r for r, tid in ranked}
    a = b = position
    while True:
        lower = rank[items[a - 1]] if a > 0 else None
        upper = rank[items[b + 1]] if b + 1 < len(items) else None
        count = b - a + 1
        if lower is None or upper is None or upper - lower > count:
            break
        b += 1  # take in the next gapless neighbour; past the last one there is always room
    window = items[a:b + 1]
    if lower is None and upper is None:
        values = [STEP * (k + 1) for k in range(count)]
    elif upper is None:
        values = [lower + STEP * (k + 1) for k in range(count)]
    elif lower is None:
        values = [upper - STEP * (count - k) for k in range(count)]
    else:
        gap = (upper - lower) / (count + 1)
        values = [lower + round(gap * (k + 1)) for k in range(count)]
    return {tid: value for tid, value in zip(window, values) if tid is None or rank.get(tid) != value}


def new_id(repo, store, prefix=None):
    """Next plain numbered ID; never reuse numbers retained in local Git history."""
    task_ids, goal_ids = set(store.tasks), set(store.goals)
    history = _git(repo, 'log', '--all', '--full-history', '-m', '--no-renames',
                   '--format=', '--name-only', '--diff-filter=A', '-z',
                   '--', 'tasks/items', 'tasks/goals', raw=True)
    for path in history.split('\0'):
        if match := re.fullmatch(r'tasks/(items|goals)/([^/]+)\.md', path):
            (task_ids if match[1] == 'items' else goal_ids).add(match[2])
    ids = task_ids | goal_ids
    archive = Path(repo) / 'TODO.archive.md'
    if archive.is_file():
        ids |= set(re.findall(r'\b[A-Za-z][A-Za-z0-9_]*-\d+(?:-(?:[0-9a-f]{8}|[0-9a-f]{2}))?\b', archive.read_text()))
    numbered = [m.groups() for m in (re.fullmatch(r'([A-Za-z][A-Za-z0-9_]*)-(\d+)(?:-(?:[0-9a-f]{8}|[0-9a-f]{2}))?', i)
                                     for i in ids) if m]
    if prefix is None:  # the tasks' most common prefix; never a goal's
        own = [m.group(1) for m in (re.fullmatch(r'([A-Za-z][A-Za-z0-9_]*)-\d+(?:-(?:[0-9a-f]{8}|[0-9a-f]{2}))?', t)
                                    for t in (store.tasks or task_ids)) if m]
        pool = own or [p for p, n in numbered if f'{p}-{n}' not in goal_ids]
        prefix = max(sorted(set(pool)), key=pool.count) if pool else 'T'
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', prefix):
        raise CommandError('invalid prefix: letters, digits or underscores, starting with a letter')
    numbers = [n for p, n in numbered if p == prefix]
    number = str(max([0] + [int(n) for n in numbers]) + 1).zfill(max([3] + [len(n) for n in numbers]))
    return f'{prefix}-{number}'


def _task(store, tid):
    if tid not in store.tasks:
        raise CommandError(f'unknown task {tid}')
    return store.tasks[tid]


def _set(repo, tid, changes, note=None):
    path = _path(repo, tid)
    before = path.read_bytes()
    text = task_store.edit(before.decode(), changes) if changes else before.decode()
    if note:
        text = task_store.set_note(text, *note)
    _write(repo, path, before, text)


# --- commands --------------------------------------------------------------------------

def _read(repo, rev='HEAD', worktree=False):
    return worktree_store(repo) if worktree else TaskStore.at(repo, rev)


def _selection_source(store, rev='HEAD', worktree=False):
    """Selection explains a snapshot, never worker admission or current runtime state."""
    return dict(only=True, admission_evaluated=False, runtime_evaluated=False,
                source='working-tree' if worktree else 'committed', ref=None if worktree else rev,
                revision=store.rev, revision_ephemeral=worktree)


def cmd_list(repo, rev='HEAD', worktree=False):
    store = _read(repo, rev, worktree)
    from pi_autowork.task_snapshot import task_display
    ready = {t.id: n + 1 for n, t in enumerate(task_select.order(store))}
    rows = []
    for t in sorted(store.tasks.values(), key=lambda t: (t.status != 'open', t.section or '', t.rank or 0, t.id)):
        blocked = task_select.blocking(store, t)
        rows.append(dict(id=t.id, title=t.title, section=t.section, rank=t.rank, status=t.status, goal=t.goal,
                         position=ready.get(t.id), blocked_by=blocked.code if blocked else None,
                         closure=t.closure_info, presentation=task_status.task(t, blocked.code if blocked else None), display=task_display(t, store),
                         selection=_selection_source(store, rev, worktree)))
    return rows


def cmd_show(repo, tid, rev='HEAD', worktree=False):
    store = _read(repo, rev, worktree)
    t = _task(store, tid)
    from pi_autowork.task_snapshot import task_display
    blocked = task_select.blocking(store, t)
    return dict(id=t.id, title=t.title, short=t.short, status=t.status, goal=t.goal, section=t.section,
                rank=t.rank, display=task_display(t, store), depends_on=list(t.depends_on),
                verified_depends_on=list(t.verified_depends_on),
                closure=t.closure_info, presentation=task_status.task(t, blocked.code if blocked else None), touches=list(t.touches), resources=list(t.resources),
                kind=t.kind.value, ownership=t.ownership.value, live=t.live.value, scope=t.scope,
                live_actor=t.live_actor, live_at=t.live_at, live_scope=list(t.live_scope),
                waiver_actor=t.waiver_actor, waiver_at=t.waiver_at, waiver_for=t.waiver_for,
                acceptance=list(t.acceptance), checks=list(t.checks), exclusions=list(t.exclusions),
                draft=t.draft, missing_fields=list(t.missing_fields), contract_hash=t.contract_hash,
                record_revision=t.record_revision, path=t.path, rev=store.rev, notes=t.body)


def cmd_why(repo, tid, rev='HEAD'):
    store = TaskStore.at(repo, rev)
    first, reasons = task_select.why(store, tid)
    return dict(task=tid, eligible=bool(reasons) and reasons[0].code == 'POSITION', first=first,
                reasons=[dict(code=r.code, detail=r.detail) for r in reasons],
                closure=store.tasks[tid].closure_info if tid in store.tasks else None,
                selection=_selection_source(store, rev))


def cmd_validate(repo, rev='HEAD', worktree=False):
    store = worktree_store(repo) if worktree else TaskStore.at(repo, rev)
    drafts = sorted(t.id for t in store.tasks.values() if t.draft)
    return dict(ok=True, tasks=len(store.tasks), goals=len(store.goals), drafts=drafts,
                pending=list(TaskStore.pending(repo)))


def cmd_goals(repo, rev='HEAD', worktree=False):
    """Every goal record, in priority order: the fields the TUI and the Paseo plugin show."""
    store = _read(repo, rev, worktree)
    return [dict(id=g.id, title=g.title, priority=g.priority, source=g.source, status=g.status, focus=g.focus,
                 depends_on=list(g.depends_on), contract_hash=g.contract_hash, record_revision=g.record_revision,
                 path=g.path, notes=g.body, rev=store.rev)
            for g in sorted(store.goals.values(), key=lambda g: (g.priority if g.priority is not None else 10**9, g.id))]


def cmd_handoff(repo):
    """One read-only, exact-snapshot recovery report; never save, commit or start work."""
    return cmd_commit(repo, dry_run=True)


def cmd_commit(repo, message=None, dry_run=False, expected=None):
    with locked(repo, recover=not dry_run):
        return _commit_snapshot(repo, message, dry_run, expected)


def _commit_snapshot(repo, message=None, dry_run=False, expected=None, *, records=None,
                     expected_head=None, expected_branch=None):
    """Preview and commit the same immutable tasks/ snapshot, never unrelated staged edits.

    The pending revision binds HEAD and the resulting tree. A protected commit refuses
    drift under the task lock before touching the real index or HEAD. Normal Git hooks
    still run; edits made after snapshotting remain uncommitted in the working tree.
    """
    repo = Path(repo)
    if not (repo / 'tasks').is_dir():
        raise CommandError('no tasks/ store in the working tree')
    reason = landing.checkout_operation(repo, read_git=_git)
    if reason:
        raise CommandError('cannot commit task edits while ' + reason)
    objects = task_store.temporary_objects(repo) if dry_run else nullcontext({})
    with tempfile.TemporaryDirectory() as tmp, objects as object_env:
        env = {**object_env, 'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
        head = _git(repo, 'rev-parse', 'HEAD')
        if expected_head is not None and head != expected_head:
            raise CommandError('repository HEAD changed; answer remains pending; nothing committed')
        _git(repo, 'read-tree', head, env=env)
        if records is None:
            _git(repo, 'add', '-A', '--', 'tasks', env=env)
        else:
            # Answer-only snapshots are derived from HEAD, not from mutable task files.
            for name, content in records.items():
                blob_file = Path(tmp) / 'answer'
                blob_file.write_text(content)
                blob = _git(repo, 'hash-object', '-w', str(blob_file), env=env)
                _git(repo, 'update-index', '--cacheinfo', f'100644,{blob},{name}', env=env)
        tree = _git(repo, 'write-tree', env=env)
        branch = _git(repo, 'rev-parse', '--symbolic-full-name', 'HEAD')
        if expected_branch is not None and branch != expected_branch:
            raise CommandError('repository branch changed; answer remains pending; nothing committed')
        pending = hashlib.sha256(f'{branch}\n{head}\n{tree}\n'.encode()).hexdigest()
        if expected is not None and expected != pending:
            raise CommandError('pending task edits changed; review the diff again; nothing committed')
        files = _git(repo, 'diff', '--name-only', '-z', head, tree, '--', 'tasks',
                     env=env, raw=True).rstrip('\0').split('\0')
        files = [name for name in files if name]
        diff = _git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-color', head, tree,
                    '--', 'tasks', env=env, raw=True)
        result = dict(files=files, diff=diff, commit=None, dry_run=dry_run, pending_revision=pending,
                      lifecycle=task_status.edit_lifecycle('pending_commit' if files else 'clean'))
        baseline, baseline_error = None, None
        try:
            baseline = TaskStore.at(repo, head)
        except StoreError as exc:
            # A valid pending store can repair invalid or absent committed records.
            # Baseline evidence is unknown, not a veto on the validated candidate.
            baseline_error = str(exc)
        if not files:
            result['handoff'] = task_handoff.describe(baseline, baseline, (), head, str(repo.resolve()), baseline_error)
            if baseline is None:
                result['lifecycle'] = dict(state='unknown', message='Committed task store unavailable: ' + baseline_error)
            return result
        # Validate exactly the staged snapshot, not a second read of mutable files.
        ident = {'GIT_AUTHOR_NAME': 'autowork', 'GIT_AUTHOR_EMAIL': 'autowork@localhost',
                 'GIT_COMMITTER_NAME': 'autowork', 'GIT_COMMITTER_EMAIL': 'autowork@localhost'}
        with task_store.temporary_objects(repo) as validation_objects:
            validation_env = {**env, **validation_objects, **ident}
            # Preview blobs live in a private object store too; retain it as an alternate.
            if object_env:
                validation_env['GIT_ALTERNATE_OBJECT_DIRECTORIES'] += os.pathsep + object_env['GIT_OBJECT_DIRECTORY']
            candidate = _git(repo, 'commit-tree', tree, '-p', head, '-m', 'validate pending tasks', env=validation_env)
            saved = TaskStore.at(repo, candidate, env=validation_env)
            result['handoff'] = task_handoff.describe(baseline, saved, files, head, str(repo.resolve()), baseline_error)
        answered = [row['task'] for row in result['handoff']['decisions'] if row['state'] == 'pending_commit']
        if answered:
            result['lifecycle']['message'] += (' Saved answers: ' + ', '.join(answered)
                                               + '; do not ask again while their reviewed commit is pending.')
        if dry_run:
            return result
        if (_git(repo, 'rev-parse', 'HEAD') != head
                or _git(repo, 'rev-parse', '--symbolic-full-name', 'HEAD') != branch
                or landing.checkout_operation(repo, read_git=_git)):
            raise CommandError('repository state changed; review pending task edits again; nothing committed')
        if records is not None and _git(repo, 'diff', '--cached', '--name-only', head, '--', *records):
            raise CommandError('answer record acquired staged edits; review them separately; nothing committed')
        text = ' '.join((message or '').split()) or f'tasks: {len(files)} record edit(s)'
        if records is not None:
            commit = _commit_answer_snapshot(repo, head, branch, tree, env, text, files)
        else:
            _git(repo, 'commit', '-q', '-m', text, env=env)
            commit = _git(repo, 'rev-parse', 'HEAD')
            if (_git(repo, 'rev-parse', commit + '^{tree}') != tree
                    or _git(repo, 'rev-list', '--parents', '-n', '1', commit).split() != [commit, head]):
                raise CommandError('commit hooks or another writer changed the snapshot; inspect the retained commit')
            _git(repo, 'reset', '-q', commit, '--', *files)
        result.update(commit=commit, lifecycle=task_status.edit_lifecycle('committed'),
                      handoff=task_handoff.describe(saved, saved, (), commit, str(repo.resolve())))
        return result


def _commit_answer_snapshot(repo, head, branch, tree, env, message, files):
    """Run commit hooks on a private, branch-preserving snapshot, then CAS-publish.

    Reserve the real HEAD and index before hooks: branch switches and git add must
    not race publication. Never commit an old private tree on a newer real parent.
    Other worktrees can still move the branch; update-ref's expected-old guard wins.
    """
    git_dir = Path(_git(repo, 'rev-parse', '--absolute-git-dir'))
    common = _git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    index = git_dir / 'index'
    index_lock, head_lock = git_dir / 'index.lock', git_dir / 'HEAD.lock'
    acquired_index = acquired_head = publication_attempted = installed = False
    try:
        with index_lock.open('xb') as reserved:
            acquired_index = True
            with head_lock.open('x'):
                acquired_head = True
                if (_git(repo, 'rev-parse', 'HEAD') != head
                        or _git(repo, 'rev-parse', '--symbolic-full-name', 'HEAD') != branch
                        or landing.checkout_operation(repo, read_git=_git)):
                    raise CommandError('repository state changed before answer commit; nothing committed')
                if _git(repo, 'diff', '--cached', '--name-only', head, '--', *files):
                    raise CommandError('answer record acquired staged edits; nothing committed')
                with tempfile.TemporaryDirectory() as tmp:
                    private = Path(tmp) / 'git'
                    private.mkdir()
                    (private / 'objects').mkdir()
                    (private / 'refs').mkdir()
                    # Hook wrappers may locate sibling helpers through --git-common-dir.
                    (private / 'hooks').symlink_to(Path(common) / 'hooks', target_is_directory=True)
                    (private / 'HEAD').write_text(f'ref: {branch}\n')
                    # Flatten the effective checkout configuration, not just config.worktree:
                    # includeIf.onbranch and gitdir conditions must not silently skip hooks.
                    config = _git(repo, 'config', '--null', '--list', '--includes', raw=True)
                    for item in config.rstrip('\0').split('\0'):
                        if not item:
                            continue
                        key, separator, value = item.partition('\n')
                        if key == 'include.path' or (key.startswith('includeif.') and key.endswith('.path')):
                            continue
                        if key == 'extensions.refstorage' and value != 'files':
                            raise CommandError('answer commits currently require files-based Git ref storage')
                        token = value if separator else f'autowork-valueless-{os.urandom(12).hex()}'
                        _git(repo, 'config', '--file', str(private / 'config'), '--add', key, token)
                        if not separator:
                            config_file = private / 'config'
                            config_file.write_text(config_file.read_text().replace(f' = {token}\n', '\n', 1))
                    hooks = _git(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks')
                    _git(repo, 'config', '--file', str(private / 'config'), '--replace-all', 'core.hooksPath', hooks)
                    refs = _git(repo, 'for-each-ref', '--format=%(objectname) %(refname)').splitlines()
                    refs = [line for line in refs if line.partition(' ')[2] != branch]
                    refs.append(f'{head} {branch}')
                    (private / 'packed-refs').write_text('\n'.join(sorted(refs)) + '\n')
                    objects = _git(repo, 'rev-parse', '--path-format=absolute', '--git-path', 'objects')
                    commit_env = {**env, 'GIT_DIR': str(private), 'GIT_WORK_TREE': str(repo.resolve()),
                                  'GIT_OBJECT_DIRECTORY': objects, 'GIT_CONFIG_NOSYSTEM': '1',
                                  'GIT_CONFIG_GLOBAL': os.devnull}
                    _git(repo, 'commit', '-q', '-m', message, env=commit_env)
                    commit = _git(repo, 'rev-parse', 'HEAD', env=commit_env)
                    if (_git(repo, 'rev-parse', commit + '^{tree}') != tree
                            or _git(repo, 'rev-list', '--parents', '-n', '1', commit).split() != [commit, head]):
                        raise CommandError(f'commit hooks changed the answer snapshot {commit}; nothing published')
                    prepared = Path(tmp) / 'index'
                    shutil.copyfile(index, prepared)
                    _git(repo, 'reset', '-q', commit, '--', *files, env={'GIT_INDEX_FILE': str(prepared)})
                    reserved.write(prepared.read_bytes())
                    reserved.flush()
                    os.fsync(reserved.fileno())
                    if (_git(repo, 'rev-parse', 'HEAD') != head
                            or _git(repo, 'rev-parse', '--symbolic-full-name', 'HEAD') != branch
                            or landing.checkout_operation(repo, read_git=_git)):
                        raise CommandError('repository state changed during answer commit; nothing published')
                    # A separate detached publisher shares refs but does not try to lock
                    # the real HEAD we reserved. Its explicit branch update is a CAS.
                    publisher = Path(tmp) / 'publisher'
                    publisher.mkdir()
                    (publisher / 'HEAD').write_text(head + '\n')
                    (publisher / 'commondir').write_text(common + '\n')
                    publish_env = {'GIT_DIR': str(publisher), 'GIT_WORK_TREE': str(repo.resolve())}
                    publication_attempted = True
                    _git(repo, '-c', f'core.hooksPath={hooks}', 'update-ref', '-m', message,
                         branch, commit, head, env=publish_env)
                    os.replace(index_lock, index)
                    installed = True
                    _sync_dir(git_dir)
                    return commit
    except (CommandError, OSError, subprocess.SubprocessError) as exc:
        if publication_attempted and not installed:
            raise CommandError(f'answer publication needs reconciliation; prepared index retained at '
                               f'{index_lock}; inspect the branch before recovery: {exc}') from exc
        raise
    finally:
        if acquired_head:
            head_lock.unlink(missing_ok=True)
        # Once CAS starts, a lost response cannot prove that no publication happened.
        # After installation, this path may belong to a new writer: never unlink it.
        if acquired_index and not publication_attempted:
            index_lock.unlink(missing_ok=True)


def cmd_new_id(repo, prefix=None):
    return new_id(repo, worktree_store(repo), prefix)


def _same_title(title):
    return ' '.join(title.lower().split())


@_serialized
def cmd_add(repo, goal=None, title=None, short=None, section='Now', scope=None, acceptance=(), checks=(), touches=(),
            depends_on=(), task_id=None, prefix=None, resources=(), exclusions=(), kind='implementation',
            ownership='worker', sources=None, verified_depends_on=(), notes=None):
    """One complete record in one write. A task of the same goal with the same title, open or
    done, is the same outcome: it is refused, naming that task, so a repeated pass adds nothing."""
    root = Path(repo)
    if (root / 'tasks').exists() or (root / 'tasks').is_symlink():
        store = worktree_store(repo)
    else:
        if any((root / name).exists() for name in ('TODO.md', 'goals.json')):
            raise CommandError('legacy task files exist: run `autowork tasks prepare` before adding work')
        store = TaskStore(rev='', tasks={}, goals={})
    if goal is not None and goal not in store.goals:
        raise CommandError(f'unknown goal {goal}')
    if not isinstance(title, str) or not title.strip():
        raise CommandError('title must be a nonempty string')
    if short is None:
        short = title if len(title) <= 40 else title[:37].rstrip() + '...'
    for dep in depends_on:
        if dep not in store.tasks:
            raise CommandError(f'unknown task dependency {dep}')
    same = sorted(t.id for t in store.tasks.values()
                  if t.goal == goal and t.status != 'superseded' and _same_title(t.title) == _same_title(title))
    if same:
        group = f'under {goal}' if goal is not None else 'without a goal'
        raise CommandError(f'{same[0]} already records "{title}" {group}; change that task instead')
    tid = task_id or new_id(repo, store, prefix)
    if tid in store.tasks:
        raise CommandError(f'{tid} already exists')
    fields = dict(schema=1, id=tid, title=title, short=short, status='open', section=section,
                  rank=bottom_rank(store, section), depends_on=list(depends_on), touches=list(touches),
                  resources=list(resources), kind=kind, ownership=ownership, exclusions=list(exclusions))
    if goal is not None:
        fields['goal'] = goal
    if verified_depends_on:
        fields['verified_depends_on'] = list(verified_depends_on)
    if scope:
        fields['scope'] = scope
    if acceptance:
        fields['acceptance'] = list(acceptance)
    if checks:
        fields['checks'] = list(checks)
    # Canonical records keep render's newline policy; an explicit raw body must
    # retain its exact ending, including no newline or several trailing newlines.
    text = task_store.render(fields, '\n') if notes is None else task_store.render(fields) + notes
    if sources:
        text = task_store.set_note(text, 'Sources', ' '.join(sources.split()))
    _write(repo, _path(repo, tid), None, text)
    return tid


@_serialized
def cmd_goal(repo, gid, title=None, source=None, priority=None, status=None, focus=None, depends_on=None,
             evidence=None):
    """Add a goal, or change the given fields of an existing one. A met goal names its evidence
    (an executed, passing check), kept as the goal's `Evidence:` note; focus moves to this goal
    from any other. The first goal of a repository starts its store. Returns 'added' or 'changed'."""
    if any(p.is_file() for p in (Path(repo) / 'tasks').glob('*/*.md')):
        store = worktree_store(repo)
    else:  # no record yet: this goal starts tasks/ (Git keeps no empty folder)
        if any((Path(repo) / name).exists() for name in ('TODO.md', 'goals.json')):
            raise CommandError(f'{repo} keeps its tasks in TODO.md and goals.json: run `autowork tasks prepare` to convert it first')
        store = TaskStore(rev='', tasks={}, goals={})
        (Path(repo) / 'tasks' / 'goals').mkdir(parents=True, exist_ok=True)
        (Path(repo) / 'tasks' / 'items').mkdir(exist_ok=True)
    if gid in store.tasks:
        raise CommandError(f'{gid} is a task, not a goal')
    changes = {k: v for k, v in dict(title=title, source=source, priority=priority, status=status, focus=focus,
                                      depends_on=list(depends_on) if depends_on is not None else None).items()
               if v is not None}
    if status == 'met' and not (evidence or '').strip():
        raise CommandError('a met goal needs --evidence naming the executed, passing check')
    qualifications = []
    if status == 'met':
        owned = [t for t in store.tasks.values() if t.goal == gid and t.status != 'superseded']
        unfinished = [t.id for t in owned if t.status != 'done']
        unqualified = [t.id for t in owned if t.status == 'done' and not t.qualified]
        if unfinished or unqualified:
            raise CommandError('goal cannot be met: unfinished tasks ' + ', '.join(unfinished)
                               + '; closed tasks need owner_waiver or owner_qualification: ' + ', '.join(unqualified))
        qualifications = [f'{t.id}: {t.owner_waiver or t.owner_qualification}' for t in owned if not t.verified]
    for other in depends_on or ():
        if other not in store.goals:
            raise CommandError(f'unknown goal {other}')
    if qualifications:
        evidence += '; Owner waivers/qualifications: ' + '; '.join(qualifications)
    note = ('Evidence', ' '.join(evidence.split())) if evidence else None
    path = _path(repo, gid, goal=True)
    edits = []
    if focus:
        for other in store.goals.values():
            if other.focus and other.id != gid:
                other_path = _path(repo, other.id, goal=True)
                before = other_path.read_bytes()
                edits.append((other_path, before, task_store.edit(before.decode(), {'focus': False}, goal=True)))
    if gid not in store.goals:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', gid):
            raise CommandError('a goal ID uses letters, digits, underscores or hyphens')
        missing = [f'--{k}' for k in ('title', 'source', 'priority') if k not in changes]
        if missing:
            raise CommandError('a new goal needs ' + ', '.join(missing))
        fields = dict(dict(schema=1, id=gid, status='unmet', focus=False, depends_on=[]), **changes)
        text = task_store.render(fields, '\n', goal=True)
        edits.append((path, None, task_store.set_note(text, *note) if note else text))
        _write_many(repo, edits)
        return 'added'
    if not changes and not note:
        raise CommandError('nothing to change')
    before = path.read_bytes()
    text = task_store.edit(before.decode(), changes, goal=True) if changes else before.decode()
    edits.append((path, before, task_store.set_note(text, *note) if note else text))
    _write_many(repo, edits)
    return 'changed' + ('; owner waivers/qualifications: ' + '; '.join(qualifications) if qualifications else '')


TYPED = {'rank': int, 'depends_on': list, 'touches': list, 'resources': list, 'acceptance': list,
         'checks': list, 'exclusions': list, 'title': str, 'short': str, 'scope': str, 'goal': str,
         'kind': str, 'ownership': str, 'live': str, 'verified_depends_on': list,
         'owner_waiver': str, 'owner_qualification': str, 'live_actor': str, 'live_at': str,
         'live_scope': list, 'waiver_actor': str, 'waiver_at': str, 'waiver_for': str}


@_serialized
def cmd_field(repo, tid, key, value, *, raw_notes=False, commit=False):
    """A typed header field (rank, touches, ...) or, for any other label, a note line such as
    `Held by` or `Owner decision` in the task's body."""
    _task(worktree_store(repo), tid)
    if commit:
        if key not in ('Owner decision', 'Blocker resolution') or raw_notes:
            raise CommandError('--commit on field is only for Owner decision or Blocker resolution notes')
        return _commit_answer(repo, tid, (key, ' '.join(value.split())))
    if key.startswith('closure'):
        raise CommandError('closure metadata is written only by done or the coordinator')
    if key in ('status', 'section', 'id', 'schema'):
        raise CommandError(f'use place or supersede to change {key}')
    if key in CONTRACT:
        _unheld(repo, tid)
    if key == 'notes' and raw_notes:
        path = _path(repo, tid)
        before = path.read_bytes()
        lines = before.decode().splitlines(keepends=True)
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == '+++')
        _write(repo, path, before, ''.join(lines[:end + 1]) + value)
    elif key in TYPED:
        kind = TYPED[key]
        if kind is int:
            try:
                parsed = value if type(value) is int else int(value)
            except ValueError:
                raise CommandError(f'{key} must be an integer') from None
        elif kind is list:
            parsed = value if isinstance(value, list) else (json.loads(value) if value.strip().startswith('[')
                                                           else [v.strip() for v in value.split(',') if v.strip()])
        else:
            parsed = value
        _set(repo, tid, {key: parsed})
    else:
        _set(repo, tid, {}, (key, ' '.join(value.split())))


@_serialized
def cmd_place(repo, tid, section, decision=None):
    """Move an open task to the bottom of a section; ``decision`` also records why, as its
    `Owner decision:` note."""
    store = worktree_store(repo)
    t = _task(store, tid)
    if t.status != 'open':
        raise CommandError(f'{tid} is {t.status}')
    if section not in ('Now', 'Next', 'Needs decision'):
        raise CommandError('section is Now, Next or Needs decision')
    if section != t.section:
        _unheld(repo, tid)
    note = None
    if decision:
        decision = ' '.join(decision.split())
        if not re.match(r'^\d{4}-\d{2}-\d{2}\b', decision):
            decision = f'{date.today().isoformat()}: {decision}'
        note = ('Owner decision', decision)
    _set(repo, tid, {'section': section, 'rank': bottom_rank(store, section, without=tid)}, note)


def _commit_answer(repo, tid, note, section=None):
    """Save an answer and commit only its delta against HEAD; retain all other edits.

    A staged target or a draft contract needs separate review. Other tasks and even
    unrelated notes in this record are neither staged nor silently committed.
    """
    head = _git(repo, 'rev-parse', 'HEAD')
    branch = _git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    if branch not in ('main', 'master'):
        raise CommandError('answer --commit requires main or master checked out; nothing written')
    reason = landing.checkout_operation(repo, read_git=_git)
    if reason:
        raise CommandError('cannot commit an answer while ' + reason)
    store = TaskStore.at(repo, head)
    committed = _task(store, tid)
    current = _task(worktree_store(repo), tid)
    if committed.status != 'open' or current.status != 'open':
        raise CommandError('answer --commit requires an open committed task')
    if any(getattr(committed, key) != getattr(current, key) for key in CONTRACT):
        raise CommandError('task has an uncommitted contract change; review it separately; nothing written')
    name = committed.path
    if _git(repo, 'diff', '--cached', '--name-only', head, '--', name):
        raise CommandError('task has staged edits; review them separately before committing an answer; nothing written')
    changes = {}
    if section is not None:
        if section not in ('Now', 'Next', 'Needs decision'):
            raise CommandError('section is Now, Next or Needs decision')
        if section != committed.section or section != current.section:
            _unheld(repo, tid)
        changes = dict(section=section, rank=bottom_rank(store, section, without=tid))
    text = _git(repo, 'show', f'{head}:{name}', raw=True)
    if changes:
        text = task_store.edit(text, changes)
    text = task_store.set_note(text, *note)
    _set(repo, tid, changes, note)
    try:
        result = _commit_snapshot(repo, f'tasks: answer {tid}', records={name: text},
                                  expected_head=head, expected_branch=f'refs/heads/{branch}')
    except (CommandError, StoreError, WriteError, OSError, subprocess.SubprocessError) as exc:
        raise CommandError(f'Answer saved locally — pending commit or commit outcome unconfirmed: {exc}. '
                           'Inspect tasks handoff before retrying; no runner acceptance is claimed.') from exc
    if not result['files']:
        result['lifecycle'] = task_status.edit_lifecycle('committed')
    return result


@_serialized
def cmd_decide(repo, tid, decision, section=None, *, commit=False):
    """Record owner direction, optionally moving an open task; no completion/authority inference."""
    decision = ' '.join(decision.split())
    if not decision:
        raise CommandError('decide needs a nonempty decision')
    if _task(worktree_store(repo), tid).status != 'open':
        raise CommandError('decide requires an open task')
    if not re.match(r'^\d{4}-\d{2}-\d{2}\b', decision):
        decision = f'{date.today().isoformat()}: {decision}'
    if commit:
        return _commit_answer(repo, tid, ('Owner decision', decision), section)
    if section is not None:
        cmd_place(repo, tid, section, decision=decision)
    else:
        _set(repo, tid, {}, ('Owner decision', decision))


@_serialized
def cmd_move(repo, tid, direction):
    """One place up or down within the task's section; returns {id: new rank} changed."""
    store = worktree_store(repo)
    t = _task(store, tid)
    ranked = _section_ranks(store, t.section)
    index = [i for _, i in ranked].index(tid)
    target = index - 1 if direction == 'up' else index + 1
    if not 0 <= target < len(ranked):
        raise CommandError(f'{tid} is already at the {"top" if direction == "up" else "bottom"} of {t.section}')
    rest = [pair for pair in ranked if pair[1] != tid]
    changes = place_between(rest, target)
    changes[tid] = changes.pop(None)
    edits = []
    for other, rank in sorted(changes.items(), key=lambda item: item[0] != tid):
        path = _path(repo, other)
        before = path.read_bytes()
        edits.append((path, before, task_store.edit(before.decode(), {'rank': rank})))
    _write_many(repo, edits)
    return changes


@_serialized
def cmd_hold(repo, tid, by, until=None):
    """Keep the runner off an open task: its record's `Held by:` note, never its status. A
    held task is never selected or dispatched, and still blocks its dependents and tasks that
    share its resources or serial work, until the note is removed or its date passes."""
    t = _task(worktree_store(repo), tid)
    if t.status != 'open':
        raise CommandError(f'{tid} is {t.status}; only an open task can be held')
    if until and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', until):
        raise CommandError('--until is a date: YYYY-MM-DD')
    value = ' '.join(by.split()) + (f'; until {until}' if until else '')
    _set(repo, tid, {}, ('Held by', value))


@_serialized
def cmd_release(repo, tid):
    """Remove the task's `Held by:` note so the runner may select it again."""
    _task(worktree_store(repo), tid)
    path = _path(repo, tid)
    before = path.read_bytes()
    text = before.decode()
    after = re.sub(r'(?m)^- Held by: .*\n?', '', text)
    if after == text:
        raise CommandError(f'{tid} is not held')
    _write(repo, path, before, after)


@_serialized
def cmd_done(repo, tid, by, reason, evidence=None):
    """Manually close any task kind; never manufacture verification or a receipt."""
    t = _task(worktree_store(repo), tid)
    if t.status != 'open':
        raise CommandError(f'{tid} is {t.status}')
    if not by.strip() or not reason.strip():
        raise CommandError('done needs nonempty --by and --reason')
    _unheld(repo, tid)
    _set(repo, tid, dict(status='done', closure='manual', closure_actor=' '.join(by.split()),
                        closure_timestamp=datetime.now(timezone.utc).isoformat(),
                        closure_reason=' '.join(reason.split()),
                        closure_evidence=' '.join(evidence.split()) if evidence and evidence.strip() else None,
                        owner_waiver=None, owner_qualification=None))


@_serialized
def reopen(repo, tid, reason):
    """Open a done task again, at the bottom of its section, with why as its `Reopened:` note:
    the runner's answer to a close whose receipt no longer matches the task's contract."""
    store = worktree_store(repo)
    t = _task(store, tid)
    if t.status != 'done':
        raise CommandError(f'{tid} is {t.status}')
    section = t.section or 'Now'
    _set(repo, tid, {'status': 'open', 'section': section, 'rank': bottom_rank(store, section, without=tid),
                     **{key: None for key in task_store._CLOSURE_FIELDS}},
         ('Reopened', ' '.join(reason.split())))


@_serialized
def cmd_supersede(repo, tid, by, reason):
    store = worktree_store(repo)
    _task(store, tid)
    for other in by:
        _task(store, other)
    _unheld(repo, tid)
    note = ('Superseded by', f'{", ".join(by)}; {" ".join(reason.split())}')
    _set(repo, tid, {'status': 'superseded'}, note)


@_serialized
def cmd_delete(repo, tid):
    """Remove any task record from the store, whatever its status or holder.

    Returns the warnings that did not stop the deletion: busy worker/lease state and
    other tasks that still name it as a dependency. Worktrees, commits, evidence and
    goals stay; a dependent task keeps its dangling reference until it is edited.
    """
    store = worktree_store(repo)
    _task(store, tid)
    path = _path(repo, tid)
    before = path.read_bytes()
    held, problems = in_flight(repo)
    warnings = []
    if tid in held:
        warnings.append(f'{tid} is held by a worker slot or a live execution lease')
    warnings.extend(problems)
    dependents = sorted(t.id for t in store.tasks.values()
                        if t.id != tid and (tid in t.depends_on or tid in t.verified_depends_on))
    if dependents:
        warnings.append('other tasks still depend on it: ' + ', '.join(dependents))
    _write(repo, path, before, None)
    return warnings


# --- CLI -------------------------------------------------------------------------------

def add_parser(sub):
    tasks = sub.add_parser('tasks', help='read and edit the tasks/ store')
    verbs = tasks.add_subparsers(dest='verb', required=True)
    for name in ('list', 'validate', 'new-id'):
        p = verbs.add_parser(name)
        p.add_argument('repo', nargs='?', default='.')
        if name in ('validate', 'list'):
            p.add_argument('--worktree', action='store_true', help='read uncommitted edits too')
        if name == 'new-id':
            p.add_argument('--prefix')
        if name != 'new-id':
            p.add_argument('--rev', default='HEAD')
    for name in ('show', 'why'):
        p = verbs.add_parser(name)
        p.add_argument('task')
        p.add_argument('repo', nargs='?', default='.')
        p.add_argument('--rev', default='HEAD')
        if name == 'show':
            p.add_argument('--worktree', action='store_true', help='read uncommitted edits too')
    p = verbs.add_parser('prepare', help='detect, convert, recover and diagnose the store (Docs Sync runs it first)')
    p.add_argument('repo', nargs='?', default='.')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='read only: report the state and what would be done')
    mode.add_argument('--no-commit', action='store_true',
                      help='stage a conversion in the working tree and index; never move HEAD')
    mode.add_argument('--force', action='store_true',
                      help="the owner's force: convert now; stop this repository's service, live workers and "
                           'other lease holders, set every attempt aside with its work kept, commit planning '
                           'edits, convert and start the service again')
    p = verbs.add_parser('add')
    p.add_argument('repo', nargs='?', default='.')
    for flag in ('--goal', '--title', '--short'):
        p.add_argument(flag, default=argparse.SUPPRESS)
    p.add_argument('--section', default=argparse.SUPPRESS, choices=('Now', 'Next', 'Needs decision'))
    p.add_argument('--id', dest='task_id', default=argparse.SUPPRESS)
    p.add_argument('--scope', default=argparse.SUPPRESS)
    p.add_argument('--kind', default=argparse.SUPPRESS, choices=('implementation', 'plan', 'inspection'))
    p.add_argument('--ownership', default=argparse.SUPPRESS, choices=('worker', 'coordinator', 'owner'))
    p.add_argument('--sources', default=argparse.SUPPRESS,
                   help='the accepted path#anchor it comes from, kept as its Sources note')
    for flag in ('--acceptance', '--checks', '--touches', '--depends-on', '--verified-depends-on', '--resources', '--exclusions'):
        p.add_argument(flag, action='append', default=argparse.SUPPRESS,
                       help='one item or a JSON array of strings; may be repeated')
    p = verbs.add_parser('field')
    p.add_argument('task')
    p.add_argument('label', nargs='?', default=argparse.SUPPRESS)
    p.add_argument('value', nargs='?', default=argparse.SUPPRESS)
    p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--commit', action='store_true', help='save and commit only this answer note (Owner decision or Blocker resolution)')
    p = verbs.add_parser('place')
    p.add_argument('task'); p.add_argument('section', choices=('Now', 'Next', 'Needs decision'))
    p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--decision', help='also record this as its Owner decision (dated, one line)')
    p = verbs.add_parser('decide', help='record dated owner direction without implying completion or live authorization')
    p.add_argument('task'); p.add_argument('decision'); p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--section', choices=('Now', 'Next', 'Needs decision'), help='optionally move the open task')
    p.add_argument('--commit', action='store_true', help='save and commit only this answer and requested section, not other edits')
    p = verbs.add_parser('move')
    p.add_argument('task'); p.add_argument('direction', choices=('up', 'down'))
    p.add_argument('repo', nargs='?', default='.')
    p = verbs.add_parser('hold', help="keep the runner off an open task (its `Held by:` note)")
    p.add_argument('task'); p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--by', required=True, help='who holds it, for example "an interactive session"')
    p.add_argument('--until', help='YYYY-MM-DD; the hold ends after this day')
    p = verbs.add_parser('release', help='remove the hold so the runner may select the task')
    p.add_argument('task'); p.add_argument('repo', nargs='?', default='.')
    p = verbs.add_parser('done', help='manually close any task kind; does not verify acceptance')
    p.add_argument('task'); p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--by', required=True, help='actor responsible for the manual closure')
    p.add_argument('--reason', required=True)
    p.add_argument('--evidence', help='optional evidence reference, not a passing check claim')
    p = verbs.add_parser('supersede')
    p.add_argument('task'); p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--by', action='append', required=True)
    p.add_argument('--reason', required=True)
    p = verbs.add_parser('delete', help='remove any task record; worktrees, commits, evidence and goals stay')
    p.add_argument('task'); p.add_argument('repo', nargs='?', default='.')
    p = verbs.add_parser('goal', help='add a goal, or change its title, source, priority, status, focus or dependencies')
    p.add_argument('goal'); p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--title', default=argparse.SUPPRESS)
    p.add_argument('--source', default=argparse.SUPPRESS, help='the accepted plan or spec it comes from, path#anchor')
    p.add_argument('--priority', type=int, default=argparse.SUPPRESS, help='1 is first among goals')
    p.add_argument('--status', default=argparse.SUPPRESS, choices=('unmet', 'partial', 'unverified', 'met'))
    p.add_argument('--focus', action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS,
                   help='the one goal whose tasks go first')
    p.add_argument('--depends-on', action='append', default=argparse.SUPPRESS, help='a goal that must be met first')
    p.add_argument('--evidence', default=argparse.SUPPRESS, help='for --status met: the executed, passing check')
    p = verbs.add_parser('goals', help='every goal record as JSON, in priority order')
    p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--worktree', action='store_true', help='read uncommitted edits too')
    p.add_argument('--rev', default='HEAD')
    p = verbs.add_parser('handoff', help='read the exact pending diff and decision handoff; no writes or runner actions')
    p.add_argument('repo', nargs='?', default='.')
    p = verbs.add_parser('commit', help="commit the working tree's tasks/ edits and nothing else")
    p.add_argument('repo', nargs='?', default='.')
    p.add_argument('--message', '-m', help='the commit message (default names the number of edits)')
    p.add_argument('--dry-run', action='store_true', help='show paths, diff and pending_revision; commit nothing')
    p.add_argument('--expect-pending', metavar='REVISION', help='require the exact pending_revision from --dry-run')
    for name in ('list', 'show'):
        verbs.choices[name].add_argument('--json', action='store_true', help='emit JSON (the default)')
    for name in ('add', 'field', 'goal'):
        verbs.choices[name].add_argument('--json', dest='json_input', metavar='FILE',
                                        help='read literal values from one JSON object (use - for stdin)')
    for name in WRITES:
        if name not in ('add', 'commit'):
            verbs.choices[name].add_argument('--expect', metavar='REVISION',
                                             help='refuse unless the record is still this revision (show --worktree)')
    return tasks


WRITES = ('add', 'field', 'place', 'decide', 'move', 'hold', 'release', 'done', 'supersede', 'delete', 'goal',
          'commit')

# JSON keys follow option names with underscores; `id` is the add option --id.
_INPUT_TYPES = {
    'add': {**{k: str for k in ('goal', 'title', 'short', 'section', 'id', 'scope', 'kind', 'ownership',
                                'sources', 'notes')},
            **{k: list for k in ('acceptance', 'checks', 'touches', 'depends_on', 'verified_depends_on',
                                 'resources', 'exclusions')}},
    'goal': dict(title=str, source=str, priority=int, status=str, focus=bool, depends_on=list, evidence=str),
    'field': dict(label=str, value=object),
}
_INPUT_DEFAULTS = {
    'add': dict(goal=None, short=None, section='Now', task_id=None, scope=None, kind='implementation', ownership='worker',
                sources=None, notes=None, **{k: [] for k in ('acceptance', 'checks', 'touches', 'depends_on',
                                                          'verified_depends_on', 'resources', 'exclusions')}),
    'goal': {k: None for k in _INPUT_TYPES['goal']},
    'field': {},
}


def _input_values(args):
    """Decode data, never shell text. Refuse bad/mixed input before locking or writing."""
    types = _INPUT_TYPES.get(args.verb)
    if types is None:
        return
    source = getattr(args, 'json_input', None)
    if source is not None:
        try:
            if source == '-':
                values = json.load(sys.stdin)
            else:
                with open(source, encoding='utf-8') as handle:
                    values = json.load(handle)
        except (OSError, ValueError, UnicodeError) as exc:
            raise CommandError(f'cannot read --json {source}: {exc}') from None
        if not isinstance(values, dict):
            raise CommandError('--json needs one JSON object')
        for key in values:
            if key not in types:
                raise CommandError(f'unknown --json key {key}')
        if any(hasattr(args, 'task_id' if key == 'id' else key) for key in types):
            raise CommandError('--json cannot be combined with value flags or label/value arguments')
        if args.verb == 'add' and 'notes' in values and 'sources' in values:
            raise CommandError('--json notes and sources conflict; include the Sources line in notes instead')
        if args.verb == 'field' and 'label' in values:
            types = {**types, 'value': TYPED.get(values['label'], str) if isinstance(values['label'], str) else str}
        for key, value in values.items():
            kind = types[key]
            if args.verb == 'field' and values.get('label') == 'goal' and key == 'value' and value is None:
                continue  # Explicitly remove optional grouping; the active-contract guard still applies.
            if type(value) is not kind or (kind is list and any(not isinstance(v, str) for v in value)):
                raise CommandError(f'--json {key} must be {kind.__name__}' + (' of strings' if kind is list else ''))
        for key, value in values.items():
            setattr(args, 'task_id' if key == 'id' else key, value)
    elif args.verb == 'add':
        for key, kind in types.items():
            if kind is not list or not hasattr(args, key):
                continue
            items = []
            for value in getattr(args, key):
                if not value.lstrip().startswith('['):
                    items.append(value)
                    continue
                flag = '--' + key.replace('_', '-')
                try:
                    parsed = json.loads(value)
                except ValueError:
                    items.append(value)  # Bracket-leading shell checks/globs remain literal items.
                    continue
                if not isinstance(parsed, list) or any(not isinstance(v, str) for v in parsed):
                    raise CommandError(f'{flag} needs a JSON array of strings')
                items.extend(parsed)
            setattr(args, key, items)
    required = {'add': ('title',), 'field': ('label', 'value'), 'goal': ()}[args.verb]
    missing = [key for key in required if not hasattr(args, key)]
    if missing:
        raise CommandError('missing required values: ' + ', '.join(missing))
    for key, value in _INPUT_DEFAULTS[args.verb].items():
        if not hasattr(args, key):
            setattr(args, key, value)


def run(args, repo):
    """Print the result as JSON (reads) or one line (writes); return the exit code. Writes
    hold the repository's task lock, so two writers never interleave."""
    try:
        _input_values(args)
        if args.verb in WRITES:
            with locked(repo, recover=not (args.verb == 'commit' and args.dry_run)):
                if getattr(args, 'expect', None):
                    goal = args.verb == 'goal'
                    expect(repo, args.goal if goal else args.task, args.expect, goal)
                out = _run(args, repo)
        else:
            out = _run(args, repo)
    except (CommandError, StoreError, WriteError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(out if isinstance(out, str) else json.dumps(out, indent=2))
    return 0


def _run(args, repo):
    verb = args.verb
    if verb == 'list':
        out = cmd_list(repo, args.rev, args.worktree)
    elif verb == 'show':
        out = cmd_show(repo, args.task, args.rev, args.worktree)
    elif verb == 'why':
        out = cmd_why(repo, args.task, args.rev)
    elif verb == 'validate':
        out = cmd_validate(repo, args.rev, args.worktree)
    elif verb == 'new-id':
        out = cmd_new_id(repo, args.prefix)
    elif verb == 'goals':
        out = cmd_goals(repo, args.rev, args.worktree)
    elif verb == 'handoff':
        out = cmd_handoff(repo)
    elif verb == 'commit':
        out = cmd_commit(repo, args.message, args.dry_run, args.expect_pending)
    elif verb == 'add':
        out = 'added ' + cmd_add(repo, args.goal, args.title, args.short, args.section, args.scope,
                                 args.acceptance, args.checks, args.touches, args.depends_on, args.task_id,
                                 resources=args.resources, exclusions=args.exclusions, kind=args.kind,
                                 ownership=args.ownership, sources=args.sources,
                                 verified_depends_on=args.verified_depends_on, notes=args.notes)
    elif verb == 'field':
        result = cmd_field(repo, args.task, args.label, args.value,
                           raw_notes=args.json_input is not None, commit=args.commit)
        out = result if args.commit else f'ok {args.task} {args.label}'
    elif verb == 'place':
        cmd_place(repo, args.task, args.section, args.decision)
        out = f'ok {args.task} -> {args.section}'
    elif verb == 'decide':
        result = cmd_decide(repo, args.task, args.decision, args.section, commit=args.commit)
        out = result if args.commit else f'ok {args.task} decision recorded (not committed)'
    elif verb == 'move':
        changes = cmd_move(repo, args.task, args.direction)
        out = 'ok ' + ', '.join(f'{tid} rank {rank}' for tid, rank in changes.items())
    elif verb == 'hold':
        cmd_hold(repo, args.task, args.by, args.until)
        out = f'ok {args.task} held'
    elif verb == 'release':
        cmd_release(repo, args.task)
        out = f'ok {args.task} released'
    elif verb == 'done':
        cmd_done(repo, args.task, args.by, args.reason, args.evidence)
        out = f'ok {args.task} done'
    elif verb == 'supersede':
        cmd_supersede(repo, args.task, args.by, args.reason)
        out = f'ok {args.task} superseded'
    elif verb == 'delete':
        warnings = cmd_delete(repo, args.task)
        out = f'ok {args.task} deleted' + ''.join(f'; warning: {warning}' for warning in warnings)
    elif verb == 'goal':
        out = f'{cmd_goal(repo, args.goal, args.title, args.source, args.priority, args.status, args.focus, args.depends_on, args.evidence)} goal {args.goal}'
    return out
