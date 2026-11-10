#!/usr/bin/env python3
"""On-demand A-E qualification harness for the authorized-autonomy reliability fixes.

Each scenario runs the real engine against a disposable Git repository and state
directory, prints one JSON record, and removes everything afterwards. The harness
uses no model, credential, production remote, service or production checkout; a
stub worker exercises the real launch path. A product defect is reported with its
scenario record; the harness never relaxes an expectation to hide it.

    python3 pi-autowork/tests/engine/live_qualification.py --all

See docs/testing.md#live-qualification-harness-a-e.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import traceback

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[3]
for _entry in (ROOT / 'pi-autowork', ROOT / 'pi-autowork/engine'):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from support import store_fixture  # noqa: E402
import task_execution as execution  # noqa: E402
import parallel_dispatch as dispatch  # noqa: E402
import parallel_integrate as integrate  # noqa: E402
import parallel_state as state  # noqa: E402
import provenance  # noqa: E402
import task_store  # noqa: E402
from support.offline_fixtures import fixture_runtime_root  # noqa: E402
from pi_autowork import coordinator, questions  # noqa: E402

FAKE_WORKER = ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/fake_worker.py'
# The engine's own bound on a publication. Scenario A lets a real pre-receive hook
# stall past it so the TimeoutExpired path is exercised by a real git process.
PUSH_TIMEOUT = 300


class Defect(Exception):
    """An expectation the real engine did not meet; recorded, never relaxed."""


def require(condition, message):
    if not condition:
        raise Defect(message)


def clean_env():
    """Drop the runner's push guard (GIT_CONFIG_* pushInsteadOf) from direct Git calls."""
    return {key: value for key, value in os.environ.items() if not key.startswith('GIT_CONFIG_')}


def git(repo, *argv, check=True):
    result = subprocess.run(['git', '-C', str(repo), *argv], capture_output=True, text=True,
                            env=clean_env())
    if check and result.returncode:
        raise Defect(f'git {" ".join(argv)} failed: {result.stderr.strip()}')
    return result.stdout.strip()


def git_init(repo, bare=False):
    argv = ['git', 'init', '-q', '-b', 'main', str(repo)]
    if bare:
        argv = ['git', 'init', '-q', '--bare', str(repo)]
    subprocess.run(argv, check=True, env=clean_env())
    if not bare:
        git(repo, 'config', 'user.email', 'qualification@example.invalid')
        git(repo, 'config', 'user.name', 'Qualification')


def commit(repo, message='fixture'):
    git(repo, 'add', '-A')
    if subprocess.run(['git', '-C', str(repo), 'diff', '--cached', '--quiet'],
                      env=clean_env()).returncode:
        git(repo, 'commit', '-qm', message)
    return git(repo, 'rev-parse', 'HEAD')


def task(tid, touches, extra=''):
    body = '\n'.join([f'- [ ] {tid} — {tid} task', f'  Scope: change {touches}.',
                      '  Acceptance: changed.', '  Checks: inspect.', f'  Touches: {touches}',
                      '  Dependencies: None.'])
    return body + ('\n' + extra if extra else '') + '\n'


@contextlib.contextmanager
def environment(**values):
    """Set/restore process environment values; a None removes the key."""
    saved = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def force_remove(path):
    shutil.rmtree(path, ignore_errors=True)
    # Read-only mode bits a tool left behind can defeat rmtree; make owner dirs writable.
    for root, directories, _files in os.walk(path, topdown=False):
        for name in directories:
            with contextlib.suppress(OSError):
                os.chmod(os.path.join(root, name), 0o700)
    shutil.rmtree(path, ignore_errors=True)


class Target:
    """A disposable repository, worker root and engine state for one scenario."""

    def __init__(self, name):
        self.name = name
        self.tmp = tempfile.TemporaryDirectory(prefix=f'lq-{name}-')
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        git_init(self.repo)
        self.worker_root = Path(tempfile.mkdtemp(prefix='lq-', dir=fixture_runtime_root()))
        self.spec = self.root / 'spec.json'
        self.spec.write_text('{}')
        self.log = self.root / 'workers.jsonl'
        self.log.touch()
        # A real dispatch owner is a live persistent ancestor, never the helper itself.
        self.owner = os.getppid()
        self.cleaned = False
        self._saved = {}
        self._set_env(XDG_RUNTIME_DIR=str(self.worker_root),
                      PI_AUTOWORK_WORKER_ROOT=str(self.worker_root),
                      PI_AUTOWORK_MIN_FREE_DISK_GB='0',
                      PI_AUTOWORK_PUSH='0',
                      AUTOWORK_GATE_CPUS='100000',
                      FAKE_WORKER_SPEC=str(self.spec),
                      FAKE_WORKER_LOG=str(self.log),
                      AUTOWORK_TELEMETRY_HOST=None, AUTOWORK_TELEMETRY_MODEL=None,
                      AUTOWORK_TELEMETRY_TOOLSET=None)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.cleaned = self.close()
        return False

    def _set_env(self, **values):
        for key, value in values.items():
            self._saved.setdefault(key, os.environ.get(key))
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def write_tasks(self, *bodies):
        store_fixture.write_todo(self.repo, '# Work queue\n\n## Next\n\n' + '\n'.join(bodies))

    def commit_all(self, message='fixture'):
        return commit(self.repo, message)

    def set_spec(self, spec):
        self.spec.write_text(json.dumps(spec))

    def run(self, *args, worker=True):
        argv = [str(self.repo), '--owner-pid', str(self.owner), *args]
        if worker:
            argv += ['--worker-command', json.dumps(
                [sys.executable, str(FAKE_WORKER), '{prompt_file}', '{worktree}'])]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = execution.main(argv)
        text = out.getvalue().strip()
        try:
            return code, json.loads(text)
        except ValueError:
            raise Defect(f'engine output was not JSON ({code}): {text[:400]}')

    def apply(self, *extra):
        return self.run('--apply', '--parallel', *extra)

    def wait(self, timeout=30):
        return self.run('--parallel', '--wait', '--timeout', str(timeout))

    def wait_until_idle(self):
        for _ in range(60):
            _code, result = self.wait(30)
            if result.get('active_workers') == 0:
                return result
        raise Defect('workers did not finish')

    def slots(self):
        common_dir = state.common_dir(self.repo)
        return state.slots(common_dir) if (common_dir / 'slots').exists() else []

    def slot(self, task_id):
        return next((slot for slot in self.slots() if slot['task_id'] == task_id), None)

    def stop_workers(self):
        for slot in self.slots():
            with contextlib.suppress(OSError, ValueError):
                if state.worker_live(slot):
                    dispatch.stop(slot['worker'], slot['worktree'])

    def close(self):
        self.stop_workers()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        force_remove(self.worker_root)
        self.tmp.cleanup()
        force_remove(self.root)
        return not self.root.exists() and not self.worker_root.exists()


# --------------------------------------------------------------------------- A
def scenario_a():
    """A real push to a local bare remote whose hook outlives the engine's timeout."""
    evidence = {}
    tmp = tempfile.TemporaryDirectory(prefix='lq-a-')
    root = Path(tmp.name)
    origin, repo = root / 'origin.git', root / 'repo'
    hook_pid = root / 'hook.pid'
    result = None
    try:
        git_init(origin, bare=True)
        git_init(repo)
        (repo / 'a.txt').write_text('a\n')
        base = commit(repo, 'base')
        git(repo, 'remote', 'add', 'origin', str(origin))
        git(repo, 'push', '-q', '-u', 'origin', 'main')
        (repo / 'b.txt').write_text('b\n')
        ahead = commit(repo, 'ahead')

        hook = origin / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\n'
                        f'echo "$$" > {shlex.quote(str(hook_pid))}\n'
                        f'exec sleep {PUSH_TIMEOUT + 30}\n')
        hook.chmod(0o755)

        with environment(PI_AUTOWORK_PUSH='1', PI_AUTOWORK_OPTIMISTIC='0',
                         PI_AUTOWORK_POST_MERGE_POLICY='async'):
            value = coordinator.Coordinator.__new__(coordinator.Coordinator)
            value.repo, value.base, value.integ, value.seen = str(repo), 'main', None, {}
            value.state = root / 'state'
            value.state.mkdir()
            value.ensure_repository = lambda: None
            started = time.monotonic()
            # A hard safety net: the engine must return on its own timeout.
            signal.signal(signal.SIGALRM, _push_alarm)
            signal.alarm(PUSH_TIMEOUT + 60)
            try:
                outcome = value.push()
            except subprocess.TimeoutExpired as exc:  # the defect the fix removed
                raise Defect('push raised TimeoutExpired instead of recording an unknown outcome: '
                             + str(exc))
            finally:
                signal.alarm(0)
            evidence['unknown_seconds'] = round(time.monotonic() - started, 1)
        evidence['outcome'] = outcome
        evidence['remote_after_unknown'] = git(origin, 'rev-parse', '--verify', 'refs/heads/main', check=False)
        require(outcome == 'unknown', f'first push outcome was {outcome!r}, expected unknown')
        require(evidence['remote_after_unknown'] == base,
                'the stalled push changed the remote ref instead of leaving it reconciled at '
                f'{base[:8]}')
        require(value.seen.get('push-note') == 'unknown', 'the unknown outcome was not recorded once')

        # Kill the stalled server-side receiver, then let the ordinary push publish once.
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(hook_pid.read_text().strip()), signal.SIGKILL)
        kill_matching(str(origin))
        time.sleep(0.3)
        hook.unlink()
        for lock in (origin / 'refs/heads').glob('*.lock'):
            with contextlib.suppress(OSError):
                lock.unlink()

        with environment(PI_AUTOWORK_PUSH='1', PI_AUTOWORK_OPTIMISTIC='0',
                         PI_AUTOWORK_POST_MERGE_POLICY='async'):
            second = value.push()
        evidence['second_outcome'] = second
        evidence['remote_after_push'] = git(origin, 'rev-parse', '--verify', 'refs/heads/main', check=False)
        require(second == 'published', f'the ordinary push outcome was {second!r}, expected published')
        require(evidence['remote_after_push'] == ahead,
                'the ordinary push did not publish the fast-forward exactly once')
        evidence['fast_forward_commits'] = int(git(origin, 'rev-list', '--count', f'{base}..{ahead}'))
        require(evidence['fast_forward_commits'] == 1, 'the remote did not receive one fast-forward')
        result = {'ok': True, 'evidence': evidence}
    finally:
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(hook_pid.read_text().strip()), signal.SIGKILL)
        kill_matching(str(origin))
        tmp.cleanup()
        force_remove(root)
        evidence['cleaned'] = not root.exists()
    return result


def _push_alarm(_signum, _frame):
    raise Defect(f'push did not return within {PUSH_TIMEOUT + 60} s')


def kill_matching(text):
    """Kill processes whose command line names ``text`` (an orphaned receive-pack)."""
    if not Path('/proc').is_dir():
        return
    marker = text.encode()
    for entry in Path('/proc').glob('[0-9]*'):
        try:
            if entry.name == str(os.getpid()):
                continue
            if marker in (entry / 'cmdline').read_bytes():
                os.kill(int(entry.name), signal.SIGKILL)
        except (OSError, ValueError, ProcessLookupError):
            continue


# --------------------------------------------------------------------------- B
def scenario_b():
    """A torn owner-questions block survives failed writes and a real recovery pass."""
    evidence = {}
    tmp = tempfile.TemporaryDirectory(prefix='lq-b-')
    root = Path(tmp.name)
    repo = root / 'repo'
    result = None
    try:
        git_init(repo)
        path = repo / 'BLOCKERS.md'
        torn = ('# Blockers\n\n## Active\n\nowner note kept\n\n' + questions.START
                + '\n\n### Q-A — USER_INPUT — effort input — unblocks 1\n- Needs: partial\n')
        path.write_text(torn)
        git(repo, 'add', '-A')
        git(repo, 'commit', '-qm', 'torn questions')
        head = git(repo, 'rev-parse', 'HEAD')

        question = dict(id='A', type='USER_INPUT', effort='input', unblocks=1, task='A',
                        needs='the full need', answer='the answer', kind='blocker')
        new = questions.update(torn, [question])
        require(new.count(questions.START) == 1 and new.count(questions.END) == 1,
                'questions.update did not repair the torn block to exactly one block')

        value = coordinator.Coordinator.__new__(coordinator.Coordinator)
        value.integ, value.seen, value.land_soon = str(repo), {}, False
        value.session_busy = lambda: False

        mode = stat.S_IMODE(repo.stat().st_mode)
        os.chmod(repo, 0o555)
        try:
            replaced = value.store_questions(path, torn, new)
        finally:
            os.chmod(repo, mode)
        evidence['failed_replacement'] = replaced
        evidence['bytes_after_failed_replacement'] = path.read_text()
        require(replaced == 'write-failed', f'failed replacement returned {replaced!r}')
        require(path.read_text() == torn, 'a failed replacement changed the previous bytes')
        require(git(repo, 'rev-parse', 'HEAD') == head, 'a failed replacement made a commit')

        objects = repo / '.git' / 'objects'
        mode = stat.S_IMODE(objects.stat().st_mode)
        os.chmod(objects, 0o555)
        try:
            failed_commit = value.store_questions(path, torn, new)
        finally:
            os.chmod(objects, mode)
        evidence['failed_commit'] = failed_commit
        require(failed_commit == 'commit-failed', f'failed commit returned {failed_commit!r}')
        require(path.read_text() == new, 'a failed commit left a torn or partial file')
        require(git(repo, 'rev-parse', 'HEAD') == head, 'a failed commit still advanced HEAD')
        require(new.count(questions.START) == 1 and new.count(questions.END) == 1,
                'the replaced file does not hold exactly one complete block')

        recovered = value.store_questions(path, new, new)
        evidence['recovery'] = recovered
        require(recovered == 'written', f'the real recovery pass returned {recovered!r}')
        require(git(repo, 'rev-parse', 'HEAD') != head, 'the recovery pass did not commit the file')
        recovered_bytes = path.read_bytes()
        require(recovered_bytes == new.encode(), 'the recovery did not commit the exact replaced bytes')
        require(path.read_text().count(questions.START) == 1
                and path.read_text().count(questions.END) == 1,
                'the committed file does not hold exactly one block')
        require('owner note kept' in path.read_text(), 'the recovery dropped the owner text')

        second_head = git(repo, 'rev-parse', 'HEAD')
        again = value.store_questions(path, new, new)
        evidence['second_pass'] = again
        evidence['second_commit_unchanged'] = git(repo, 'rev-parse', 'HEAD') == second_head
        evidence['second_bytes_unchanged'] = path.read_bytes() == recovered_bytes
        require(again == 'unchanged', f'the second pass returned {again!r}, expected unchanged')
        require(evidence['second_commit_unchanged'], 'a second pass made another commit')
        require(evidence['second_bytes_unchanged'], 'a second pass rewrote the file')
        require(git(repo, 'status', '--porcelain') == '', 'the recovery left uncommitted changes')
        result = {'ok': True, 'evidence': evidence}
    finally:
        tmp.cleanup()
        force_remove(root)
        evidence['cleaned'] = not root.exists()
    return result


# ------------------------------------------------------------------- C and D
def scenario_c():
    """Real dispatch gates a legacy grant, a structured grant and a foreign scope; a
    worker-authored task-store edit is held by the real integration decision."""
    evidence = {'cleaned': True}
    with Target('c-grant') as grant:
        grant.write_tasks(
            task('GRANT', 'profiles/',
                 '  Ownership: Owner or a coordinator with live authorization.\n'
                 '  Live authorization: owner approved this run on 2026-10-17'),
            task('PLAIN', 'plain.txt', '  Ownership: Toolset coordinator.'))
        grant.set_spec({'GRANT': {'files': {'profiles/installed.txt': 'ok'}, 'sleep': 0.2,
                                  'commit': True}})
        _code, legacy = grant.apply('1', '--max-workers', '1', '--tasks', 'GRANT')
        evidence['legacy_waiting'] = legacy.get('waiting')
        reason = ' '.join(row.get('reason', '') for row in legacy.get('waiting') or [])
        require([row.get('id') for row in legacy.get('dispatched') or []] == [],
                'a legacy prose grant dispatched')
        require('Live actor' in reason or 'Live at' in reason or 'Live scope' in reason,
                f'the legacy grant wait did not name the missing structured fields: {reason!r}')

        record = grant.repo / 'tasks/items/GRANT.md'
        record.write_text(task_store.edit(record.read_text(), dict(
            live_actor='owner', live_at='2026-10-17', live_scope=['profiles/'])))
        grant.commit_all('structured grant')
        # The worker commits a task-store self-grant alongside its real work.
        grant.set_spec({'GRANT': {
            'files': {'profiles/installed.txt': 'ok',
                      'tasks/items/GRANT.md': record.read_text() + '\n- Live authorization: self granted\n'},
            'sleep': 0.2, 'commit': True}})
        _code, structured = grant.apply('1', '--max-workers', '1', '--tasks', 'GRANT')
        evidence['structured_dispatched'] = [row.get('task') for row in structured.get('dispatched') or []]
        require(evidence['structured_dispatched'] == ['GRANT'],
                f'a structured grant did not dispatch: {structured}')
        grant.wait_until_idle()
        slot = grant.slot('GRANT')
        require(slot is not None and slot.get('commit'),
                f'the dispatched worker left no reported commit: {slot}')
        baseline = slot['baseline']
        # The worker also wrote a task-store grant for itself: the real merge decision holds it.
        authored = integrate.worker_task_edits(grant.repo, slot, baseline)
        evidence['worker_task_edits'] = authored
        require('tasks/items/GRANT.md' in authored,
                f'the worker-authored task-store edit was not detected: {authored}')
        try:
            integrate.merge_candidate(grant.repo, slot, baseline)
        except integrate.Hold as exc:
            evidence['held'] = dict(cause=exc.cause, outside=exc.details.get('outside'))
            require(exc.cause == 'scope', f'the worker task edit was held for {exc.cause!r}, not scope')
            require(exc.details.get('outside') == ['tasks/items/GRANT.md'],
                    f'the hold named {exc.details.get("outside")!r}')
        else:
            raise Defect('a worker-authored task-store edit was merged, not held')
    evidence['cleaned'] = grant.cleaned
    with Target('c-foreign') as foreign:
        foreign.write_tasks(
            task('FOREIGN', 'own.txt',
                 '  Ownership: Owner or a coordinator with live authorization.\n'
                 '  Live authorization: owner approved this run on 2026-10-17'))
        foreign_record = foreign.repo / 'tasks/items/FOREIGN.md'
        foreign_record.write_text(task_store.edit(foreign_record.read_text(), dict(
            live_actor='owner', live_at='2026-10-17', live_scope=['elsewhere/'])))
        foreign.commit_all('foreign scope')
        _code, refused = foreign.apply('1', '--max-workers', '1', '--tasks', 'FOREIGN')
        evidence['foreign'] = {'outcome': refused.get('outcome'), 'reason': refused.get('reason')}
        require(refused.get('outcome') == 'ACTION_REQUIRED',
                f'a foreign grant scope was not refused: {refused}')
        require('undeclared scope elsewhere/' in str(refused.get('reason')),
                f'the refusal did not name the foreign scope: {refused.get("reason")!r}')
    evidence['cleaned'] = evidence['cleaned'] and foreign.cleaned
    return {'ok': True, 'evidence': evidence}


def scenario_d():
    """A paused attempt resumes beside a full pool with one reserve; an exclusive holder
    is not bypassed."""
    evidence = {}
    with Target('d-nplus1') as nplus1:
        nplus1.write_tasks(task('A', 'a.txt'), task('B', 'b.txt'), task('C', 'c.txt'))
        nplus1.set_spec({
            'A': {'files': {'a.txt': 'half'}, 'sleep': 0.2, 'commit': False, 'blockers': ['Which unit?']},
            'B': {'files': {'b.txt': 'half'}, 'sleep': 60, 'commit': False},
            'C': {'files': {'c.txt': 'half'}, 'sleep': 60, 'commit': False}})
        _code, first = nplus1.apply('1', '--max-workers', '1')
        require([row.get('task') for row in first.get('dispatched') or []] == ['A'],
                f'the first dispatch did not start A: {first}')
        nplus1.wait_until_idle()
        slot = nplus1.slot('A')
        require(slot is not None and (slot['state'], slot.get('cause')) == ('held', 'blocker'),
                f'A did not become a held blocker: {slot}')

        _code, fresh = nplus1.apply('1', '--max-workers', '1')
        require([row.get('task') for row in fresh.get('dispatched') or []] == ['B'],
                f'fresh work did not fill the pool: {fresh}')
        answer = nplus1.root / 'answer.txt'
        answer.write_text('Use metres.')
        _code, answered = nplus1.run('--parallel-answer', 'A', '--answer-file', str(answer), worker=False)
        require(answered.get('outcome') == 'ANSWERED', f'A was not answered: {answered}')

        nplus1.set_spec({
            'A': {'files': {'a.txt': 'done'}, 'sleep': 60, 'commit': False},
            'B': {'files': {'b.txt': 'half'}, 'sleep': 60, 'commit': False},
            'C': {'files': {'c.txt': 'half'}, 'sleep': 60, 'commit': False}})
        _code, resumed = nplus1.apply('1', '--max-workers', '1')
        evidence['n_plus_one'] = {
            'dispatched': [row.get('task') for row in resumed.get('dispatched') or []],
            'owner_slot': resumed.get('owner_slot'),
            'configured_max_workers': resumed.get('configured_max_workers'),
            'max_workers': resumed.get('max_workers'),
            'active_workers': resumed.get('active_workers'),
            'waiting': resumed.get('waiting')}
        require(evidence['n_plus_one']['dispatched'] == ['A'],
                'the paused attempt did not resume beside a full pool')
        require((resumed.get('owner_slot'), resumed.get('configured_max_workers'),
                 resumed.get('max_workers')) == (1, 1, 2),
                f'the reserved slot was not reported as one: {evidence["n_plus_one"]}')
        require(resumed.get('active_workers') == 2, 'the resumed attempt did not run beside the holder')
        require([row.get('id') for row in resumed.get('waiting') or []] == ['C'],
                f'fresh work took a second reserve: {resumed.get("waiting")}')
    evidence['cleaned'] = nplus1.cleaned

    with Target('d-exclusive') as exclusive:
        exclusive.write_tasks(task('A', 'a.txt', '  Resources: exclusive'), task('E', 'e.txt'))
        exclusive.set_spec({
            'A': {'files': {'a.txt': 'half'}, 'sleep': 0.2, 'commit': False, 'blockers': ['Which unit?']},
            'E': {'files': {'e.txt': 'half'}, 'sleep': 60, 'commit': False}})
        _code, _first = exclusive.apply('1', '--max-workers', '1')
        exclusive.wait_until_idle()
        answer = exclusive.root / 'answer.txt'
        answer.write_text('Go on.')
        _code, answered = exclusive.run('--parallel-answer', 'A', '--answer-file', str(answer), worker=False)
        require(answered.get('outcome') == 'ANSWERED', f'A was not answered: {answered}')
        exclusive.set_spec({
            'A': {'files': {'a.txt': 'done'}, 'sleep': 60, 'commit': False},
            'E': {'files': {'e.txt': 'half'}, 'sleep': 60, 'commit': False}})
        _code, occupied = exclusive.apply('1', '--max-workers', '1', '--tasks', 'E')
        require([row.get('task') for row in occupied.get('dispatched') or []] == ['E'],
                f'the exclusive holder did not fill the pool: {occupied}')
        _code, blocked = exclusive.apply('1', '--max-workers', '1')
        evidence['exclusive'] = {'dispatched': [row.get('task') for row in blocked.get('dispatched') or []],
                                 'owner_slot': blocked.get('owner_slot'),
                                 'waiting': blocked.get('waiting')}
        require(evidence['exclusive']['dispatched'] == [],
                'the reserved slot bypassed an exclusive holder')
        require(blocked.get('owner_slot') == 0, 'a reserve was spent beside an exclusive holder')
        require(any('must run alone' in row.get('reason', '') for row in blocked.get('waiting') or []),
                f'the exclusive wait was not named: {blocked.get("waiting")}')
    evidence['cleaned'] = evidence.get('cleaned', True) and exclusive.cleaned
    return {'ok': True, 'evidence': evidence}


def scenario_e():
    """One real dispatch and a resume append allowlisted provenance only."""
    evidence = {}
    data = None
    with Target('e') as target:
        target.write_tasks(task('A', 'a.txt').replace('change a.txt.', 'change a.txt (MARKER-XYZ).'))
        (target.repo / 'AGENTS.md').write_text('repository instructions\n')
        target.commit_all('task and instructions')
        target.set_spec({'A': {'files': {'a.txt': 'half'}, 'sleep': 0.2, 'commit': False,
                              'blockers': ['Which unit?']}})
        with environment(AUTOWORK_TELEMETRY_MODEL=None, AUTOWORK_TELEMETRY_TOOLSET=None,
                         PI_AUTOWORK_TEST_SECRET='tok-9f3c'):
            _code, first = target.apply('1', '--max-workers', '1')
            require([row.get('task') for row in first.get('dispatched') or []] == ['A'],
                    f'the first dispatch did not start A: {first}')
            target.wait_until_idle()
            slot = target.slot('A')
            require(slot is not None and (slot['state'], slot.get('cause')) == ('held', 'blocker'),
                    f'A did not become a held blocker: {slot}')
            answer = target.root / 'answer.txt'
            answer.write_text('Use metres.')
            _code, answered = target.run('--parallel-answer', 'A', '--answer-file', str(answer), worker=False)
            require(answered.get('outcome') == 'ANSWERED', f'A was not answered: {answered}')
            common_dir = state.common_dir(target.repo)
            data = dispatch.data_dir(common_dir, target.slot('A'))
            first_bytes = (data / 'provenance.jsonl').read_bytes()
            first_prompt = (data / 'prompt.md').read_bytes()
            target.set_spec({'A': {'files': {'a.txt': 'done'}, 'sleep': 0.2, 'commit': False}})
            _code, resumed = target.apply('1', '--max-workers', '1')
            require([row.get('task') for row in resumed.get('dispatched') or []] == ['A'],
                    f'the attempt did not resume: {resumed}')
            target.wait_until_idle()
            after = (data / 'provenance.jsonl').read_bytes()

        records = provenance.read(data / 'provenance.jsonl')
        evidence['records'] = len(records)
        require(len(records) == 2, f'expected two provenance records, found {len(records)}')
        require(after.startswith(first_bytes), 'the resume rewrote earlier provenance bytes')
        require(records[0]['prompt'] == dict(
            sha256=hashlib.sha256(first_prompt).hexdigest(), bytes=len(first_prompt)),
            f'the first record does not carry the prompt hash: {records[0]["prompt"]}')
        require(records[0]['model'] is None and records[0]['toolset'] is None,
                'an unavailable model/toolset value was inferred instead of stored as null')
        require(records[0]['instructions'][1]['state'] == 'unavailable'
                and records[0]['instructions'][1]['sha256'] is None,
                'an absent CLAUDE.md was not recorded as null/unavailable')
        text = after.decode()
        for forbidden in ('MARKER-XYZ', 'repository instructions', 'tok-9f3c',
                          'PI_AUTOWORK_TEST_SECRET'):
            require(forbidden not in text, f'provenance captured forbidden text: {forbidden}')
        evidence['prompt_sha256'] = records[0]['prompt']['sha256']
        evidence['append_only_prefix'] = len(first_bytes)
        evidence['null_values'] = {'model': records[0]['model'], 'toolset': records[0]['toolset']}
    evidence['cleaned'] = target.cleaned
    return {'ok': True, 'evidence': evidence}


SCENARIOS = {'A': scenario_a, 'B': scenario_b, 'C': scenario_c, 'D': scenario_d, 'E': scenario_e}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the A-E live qualification harness.')
    parser.add_argument('--all', action='store_true', help='run every scenario A-E')
    parser.add_argument('--scenario', action='append', choices=sorted(SCENARIOS),
                        help='run one scenario (repeatable); --all runs every scenario')
    args = parser.parse_args(argv)
    selected = list(SCENARIOS) if args.all or not args.scenario else args.scenario
    if not args.all and not args.scenario:
        parser.error('choose --all (or --scenario)')
    failed = False
    for name in selected:
        record = {'scenario': name, 'ok': False}
        try:
            # The engine's own log lines are private; stdout carries only scenario JSON.
            with contextlib.redirect_stdout(io.StringIO()):
                result = SCENARIOS[name]()
            record.update(result)
        except Defect as exc:
            record.update(ok=False, defect=str(exc))
        except Exception as exc:  # an unexpected product or harness error is still evidence
            record.update(ok=False, error=f'{type(exc).__name__}: {exc}',
                          traceback=traceback.format_exc().splitlines()[-6:])
        failed = failed or not record.get('ok')
        print(json.dumps(record, sort_keys=True), flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
