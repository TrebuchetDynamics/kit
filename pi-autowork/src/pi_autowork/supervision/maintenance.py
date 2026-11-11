"""Bounded network/package jobs; session merges remain in the coordinator thread."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pi_autowork import release, service
from pi_autowork.common import LOG, atomic_write, dirty, git, git_ok
from pi_autowork.processes import running, start_time

ATTEMPTS = 3
PUSH_TIMEOUT = 3600  # Includes local pre-push verification, not just the network transfer.
BACKOFF = 30
READBACK_COOLDOWN = 300


def read(owner, name):
    if not getattr(owner, 'state', None):
        return {}
    try:
        record = json.loads((owner.state / f'maintenance-{name}.json').read_text())
        return record if isinstance(record, dict) else {'invalid': True}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return {'invalid': True}


def write(owner, name, record):
    atomic_write(owner.state / f'maintenance-{name}.json', json.dumps(record) + '\n')


def start(owner, name, record, argv, limit, *, publish=False):
    """Persist intent before spawn; the child records its identity before any side effect."""
    done = owner.state / f'maintenance-{name}.exit'
    log = owner.state / f'maintenance-{name}.log'
    done.unlink(missing_ok=True)
    intent = uuid.uuid4().hex
    record['job'] = dict(intent=intent, started=time.time(), limit=limit)
    write(owner, name, record)
    env = owner.job_environment(AUTOWORK_MAINTENANCE_INTENT=intent)
    if publish:
        # Remove only the worker push guard, never hooks or pre-push checks.
        env = {k: v for k, v in env.items() if not k.startswith('GIT_CONFIG_')}
    try:
        with log.open('w') as stream:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'launch',
                                      str(owner.state), name, intent, str(limit), *map(str, argv)],
                                     stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, env=env, start_new_session=True)
        child.returncode = 0  # receipt/start ticks and waitpid own reaping across exec
    except OSError as exc:
        log.write_text(str(exc))
        done.write_text('125\n')


def collect(owner, name, record):
    if not record.get('job'):
        return None
    with open(owner.state / f'maintenance-{name}.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        record.clear()
        record.update(read(owner, name))  # the child may have registered since our first read
        return _collect(owner, name, record)


def _collect(owner, name, record):
    job = record.get('job')
    if not job:
        return None
    if not job.get('pid') and not job.get('cancelled') and time.time() - job['started'] < 10:
        return None  # registration may still be starting; the lock fences late children
    if running(job):
        if time.time() - job['started'] > job['limit'] + 10:
            cleanup_group(job)
        return None
    if job.get('pid', 0) > 0 and not cleanup_group(job):
        return None  # leader exited; descendants still own this attempt until confirmed gone
    try:
        if job.get('pid', 0) > 0:
            os.waitpid(job['pid'], os.WNOHANG)
    except ChildProcessError:
        pass
    try:
        code = int((owner.state / f'maintenance-{name}.exit').read_text())
    except (OSError, ValueError):
        code = 125  # died before its receipt: a push may still have landed
    try:
        with (owner.state / f'maintenance-{name}.log').open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 8192))
            text = stream.read().decode(errors='replace')
    except OSError:
        text = ''
    record.pop('job')  # caller atomically publishes this together with the next phase/outcome
    return code, text


def invalid(owner):
    return any(read(owner, name).get('invalid') for name in ('publication', 'update'))


def busy(owner):
    return any(read(owner, name).get('job') or read(owner, name).get('invalid')
               for name in ('publication', 'update'))


def pending(owner):
    if busy(owner):
        return True
    record = read(owner, 'publication')
    phase = record.get('phase')
    return (phase == 'merge'
            or phase == 'probe' and record.get('probes', 0) < ATTEMPTS
            or phase == 'retry' and record.get('attempts', 0) < ATTEMPTS
            or phase == 'fetch-retry' and record.get('fetch_attempts', 0) < ATTEMPTS)


def cleanup_group(job):
    """Kill only start-tick/token-proven members, using pidfds against PID reuse."""
    found = False
    for folder in Path('/proc').glob('[0-9]*'):
        try:
            fields = (folder / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) != job['pid'] or fields[0] in ('Z', 'X'):
                continue
            if folder.stat().st_uid != os.getuid():
                return False
            marker = f'AUTOWORK_MAINTENANCE_INTENT={job.get("intent", "")}'.encode()
            if not job.get('intent') or marker not in (folder / 'environ').read_bytes().split(b'\0'):
                return False  # unproven group member: retain the job, never overlap another push
            pid = int(folder.name)
            fd = os.pidfd_open(pid)
            try:
                if start_time(pid) == fields[19]:
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                    found = True
            finally:
                os.close(fd)
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, AttributeError):
            return False  # cannot prove cleanup on this host
    return not found


def stop(owner):
    for name in ('publication', 'update'):
        if not getattr(owner, 'state', None):
            return
        with open(owner.state / f'maintenance-{name}.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            record = read(owner, name)
            job = record.get('job')
            if not job:
                continue
            job['cancelled'] = True  # same fence as registration; even pid-less intents cannot run late
            write(owner, name, record)
        if job.get('pid'):
            cleanup_group(job)
        # Keep tracked intent/identity until cleanup and outcome are collected by a later cycle.


def resolved_urls(owner, remote, *, push=False):
    # Match the actual publisher's environment, not the inherited worker push guard.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_CONFIG_')} if push else None
    result = subprocess.run(['git', '-C', str(owner.repo), 'remote', 'get-url',
                             *(['--push'] if push else []), '--all', remote],
                            env=env, capture_output=True, text=True, timeout=5)
    return result.stdout.splitlines() if result.returncode == 0 else []


def endpoint(owner, remote, *, push=False):
    try:
        values = resolved_urls(owner, remote, push=push)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    if len(values) != 1:
        return ''  # single-endpoint evidence cannot qualify a multi-destination push
    return hashlib.sha256(values[0].encode()).hexdigest()


def sync(owner, remote, branch):
    record = read(owner, 'publication')
    if record.get('invalid'):
        return 'invalid-state'
    if record.get('job') or record.get('phase') in ('merge', 'probe'):
        owner.publication_requested = True
        return 'pending'
    target = endpoint(owner, remote)
    if not target:
        return 'no-upstream'
    identity = [git(owner.repo, 'rev-parse', owner.base), remote, branch,
                owner.toolset_rev, os.environ.get('PI_AUTOWORK_PUSH'), target]
    if record.get('sync_identity') == identity and record.get('fetch_attempts', 0) >= ATTEMPTS:
        return 'exhausted'
    attempts = record.get('fetch_attempts', 0) if record.get('sync_identity') == identity else 0
    if time.time() < record.get('retry_at', 0):
        return 'backoff'
    record.update(repository=str(owner.repo), sync_identity=identity, remote=remote, branch=branch, fetch_endpoint=target, phase='fetch',
                  fetch_attempts=attempts + 1)
    start(owner, 'publication', record, ['git', '-C', owner.repo, 'fetch', '--quiet', remote,
                                       f'refs/heads/{branch}:refs/remotes/{remote}/{branch}'], 120)
    return 'pending'


def publish(owner, remote, branch, source):
    record = read(owner, 'publication')
    if record.get('invalid'):
        return 'invalid-state'
    if record.get('job') or record.get('phase') in ('merge', 'probe'):
        owner.publication_requested = True
        return 'pending'
    target = endpoint(owner, remote, push=True)
    if not target:
        LOG.say('Not pushed: publication requires exactly one resolved push destination')
        return 'ambiguous-destination'
    if record.get('endpoint') and record['endpoint'] != target:
        LOG.say('Not pushed: publication destination changed; the recorded outcome stays bound to its endpoint')
        return 'destination-changed'
    identity = [source, remote, branch, owner.toolset_rev, os.environ.get('PI_AUTOWORK_PUSH'), target]
    if record.get('identity') != identity:
        record.update(identity=identity, attempts=0, retry_at=0)
    if record.get('published') == identity:
        return 'already-published'
    if record.get('attempts', 0) >= ATTEMPTS:
        return 'exhausted'
    if time.time() < record.get('retry_at', 0):
        return 'backoff'
    record.update(repository=str(owner.repo), source=source, remote=remote, branch=branch, endpoint=target, phase='push',
                  attempts=record.get('attempts', 0) + 1)
    start(owner, 'publication', record, ['git', '-C', owner.repo, 'push', '--quiet', remote,
                                       f'{source}:refs/heads/{branch}'], PUSH_TIMEOUT, publish=True)
    LOG.say(f'Publishing {source[:12]} to {remote}/{branch} in the background (attempt {record["attempts"]})')
    return 'pending'


def poll_publication(owner):
    record = read(owner, 'publication')
    if not record or record.get('invalid'):
        return
    if (record.get('job') and record.get('phase') == 'push'
            and (owner.authority_problem() or os.environ.get('PI_AUTOWORK_PUSH') != '1')):
        job = record['job']
        if running(job):
            cleanup_group(job)
    result = collect(owner, 'publication', record)
    phase = record.get('phase')
    if result is not None:
        code, text = result
        if phase == 'fetch':
            if code:
                record.update(phase='fetch-retry', retry_at=time.time() + BACKOFF * record['fetch_attempts'])
                LOG.say(f'Upstream fetch deferred (attempt {record["fetch_attempts"]}/{ATTEMPTS}; exit {code})')
            else:
                record.update(phase='merge', fetch_attempts=0)
        elif phase == 'push':
            # Even success needs readback: hooks and transport status are not remote evidence.
            record.update(phase='probe', push_detail=f'push exit {code}', probes=0)
        elif phase == 'probe':
            head = next((line.split()[0] for line in text.splitlines()
                         if len(line.split()) == 2 and line.split()[1] == f'refs/heads/{record["branch"]}'), '')
            if code:
                delay = READBACK_COOLDOWN if record['probes'] >= ATTEMPTS else BACKOFF * record['probes']
                record.update(phase='probe', retry_at=time.time() + delay)
                LOG.say(f'Publication outcome unknown: remote readback {record["probes"]}/{ATTEMPTS} failed; '
                        'no new push until reconciled')
            elif head == record['source']:
                record.update(phase='done', published=record['identity'], retry_at=0)
                LOG.say(f'Pushed {owner.base} to {record["remote"]}/{record["branch"]} '
                        f'({record["source"][:12]}; remote verified)')
            else:
                record.update(phase='retry', retry_at=time.time() + BACKOFF * record['attempts'])
                LOG.say(f'Not published: remote does not name {record["source"][:12]}; '
                        f'attempt {record["attempts"]}/{ATTEMPTS}; {record.get("push_detail", "")}')
        write(owner, 'publication', record)
    if (record.get('job') or getattr(owner, 'stop', False) or getattr(owner, 'restart_pending', False)
            or service.restart_requests(owner.state)):
        return
    phase = record.get('phase')
    if phase == 'probe':
        if time.time() >= record.get('retry_at', 0):
            try:
                urls = resolved_urls(owner, record['remote'], push=True)
            except (OSError, subprocess.TimeoutExpired):
                urls = []
            if (len(urls) != 1
                    or hashlib.sha256(urls[0].encode()).hexdigest() != record.get('endpoint')):
                record.update(retry_at=time.time() + READBACK_COOLDOWN)
                write(owner, 'publication', record)
                LOG.say('Publication outcome unknown: destination changed; no redirected probe or push')
                return
            if record.get('probes', 0) >= ATTEMPTS:
                record['probes'] = 0  # a new read-only recovery window, never a new push attempt
            record['probes'] = record.get('probes', 0) + 1
            start(owner, 'publication', record, ['git', '-C', owner.repo, 'ls-remote', '--heads',
                                               urls[0],
                                               f'refs/heads/{record["branch"]}'], 60)
        return
    if phase not in ('merge', 'retry', 'fetch-retry'):
        return
    if owner.authority_problem() or os.environ.get('PI_AUTOWORK_PUSH') != '1':
        return
    # No session mutation while a review, resolver, train or unconsumed review answer exists.
    # Only an upstream merge mutates the session: a fetch, and a push of a main that is not
    # behind its upstream, do not wait, or a queue that is never idle is never published.
    busy = bool(getattr(owner, 'integration', None) or getattr(owner, 'child', None)
                or getattr(owner, 'prefix_landing', None) or getattr(owner, 'train', None)
                or getattr(owner, 'maintainer_job', None) or owner.resolvers or owner.batch_landing())
    upstream = f'{record["remote"]}/{record["branch"]}'
    configured = git(owner.repo, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', f'{owner.base}@{{u}}')
    if (configured != upstream or record.get('fetch_endpoint')
            and endpoint(owner, record['remote']) != record['fetch_endpoint']
            or record.get('endpoint') and endpoint(owner, record['remote'], push=True) != record['endpoint']):
        record['phase'] = 'done'
        write(owner, 'publication', record)
        return  # never merge/retry against an obsolete publication destination
    if phase == 'merge':
        if git(owner.repo, 'symbolic-ref', '--short', '-q', 'HEAD') != owner.base:
            return
        behind = int(git(owner.repo, 'rev-list', '--count', f'{owner.base}..{upstream}') or 0)
        if not behind:
            pass  # nothing to merge: publication needs neither the session nor an idle runner
        elif busy:
            return
        elif owner.integ and not dirty(owner.integ):
            if (not (owner.merge_planning(upstream) or owner.resolve_upstream_merge(upstream))
                    or owner.fast_forward_main()):
                git(owner.integ, 'merge', '--abort')
                record.update(phase='done')
                write(owner, 'publication', record)
                LOG.say(f'Upstream merge deferred: {upstream} could not land; session preserved')
                return
            LOG.say(f'Pulled {behind} commit(s) from {upstream} into {owner.base}')
        elif owner.integ:
            return
        if record.get('source') and not git_ok(owner.repo, 'merge-base', '--is-ancestor', record['source'], upstream):
            record.pop('published', None)
        record['phase'] = 'ready'
        if git_ok(owner.repo, 'merge-base', '--is-ancestor', owner.base, upstream):
            record['phase'] = 'done'  # fetched remote already contains main; do not run a no-op push/hook
            write(owner, 'publication', record)
            return
        write(owner, 'publication', record)
        owner.push()  # revalidate current release/grant and the exact verified/green SHA
    elif phase in ('retry', 'fetch-retry') and time.time() >= record.get('retry_at', 0):
        if phase == 'retry' and record.get('attempts', 0) >= ATTEMPTS:
            return
        sync(owner, record['remote'], record['branch'])


def poll(owner):
    poll_publication(owner)
    publication = read(owner, 'publication')
    if (getattr(owner, 'publication_requested', False) and not publication.get('job')
            and publication.get('phase') in ('done', 'ready') and not getattr(owner, 'stop', False)
            and not getattr(owner, 'restart_pending', False)):
        owner.publication_requested = False
        owner.sync_upstream()  # coalesce landings while an older exact candidate was in flight
    record = read(owner, 'update')
    result = collect(owner, 'update', record)
    if result is not None:
        code, text = result
        try:
            outcome = json.loads(text.splitlines()[-1])
        except (ValueError, IndexError):
            outcome = dict(ok=False, reason=f'job exited {code}: {text[-300:]}')
        installed = git(owner.package, 'rev-parse', 'HEAD')
        if (not isinstance(outcome, dict) or code != 0
                or outcome.get('ok') and (not outcome.get('revision') or installed != outcome['revision'])):
            outcome = dict(ok=False, blocked=installed, reason='update result no longer qualifies the installed revision')
        previously_blocked = record.get('outcome', {}).get('blocked')
        if not outcome.get('ok') and (installed != record.get('identity', ['', ''])[1] or previously_blocked == installed):
            outcome['blocked'] = installed
        if outcome.get('retry') or outcome.get('current') or outcome.get('ok'):
            record['attempts'] = 0
        record['outcome'] = outcome
        write(owner, 'update', record)
        note = outcome.get('reason') or outcome.get('note') or ''
        if note and not outcome.get('current') and note != owner.last_update_note:
            LOG.say(f'Toolset update deferred: {note}' if not outcome.get('ok') else f'Toolset update: {note}')
        owner.last_update_note = note


def update(owner):
    record = read(owner, 'update')
    if record.get('job') or record.get('invalid'):
        return
    identity = [owner.package, git(owner.package, 'rev-parse', 'HEAD')]
    if record.get('identity') != identity:
        record = dict(identity=identity, attempts=0, outcome=record.get('outcome', {}))
    if record.get('attempts', 0) >= ATTEMPTS:
        return
    record['attempts'] = record.get('attempts', 0) + 1
    argv = [sys.executable, str(Path(__file__).resolve()), 'update', owner.cfg['pi'],
            str(owner.cfg['state_root']), str(owner.state), owner.package, owner.toolset, str(owner.update_wait)]
    start(owner, 'update', record, argv, 600)


def update_package(pi, state_root, state, package, toolset, wait):
    """Existing fleet/schema/lock policy, off-loop; never activate a moving candidate."""
    import fcntl
    with open(Path(state_root) / 'toolset-update.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(ok=False, reason='another runner is updating the toolset', retry=True)
        independent = Path(package).resolve() == (Path(state_root) / 'installed').resolve()
        source = git(package, 'remote', 'get-url', 'origin') if independent else release.package_source(pi, package)
        if not source:
            return dict(ok=False, current=True, reason='no registered Git package')
        check = release.check(state_root, state, package, wait=float(wait), current_toolset=toolset, source=source)
        if not check['ok']:
            return dict(check, retry=True)
        expected = git(package, 'rev-parse', 'FETCH_HEAD')
        if not expected:
            return dict(ok=False, reason='cannot resolve the checked update candidate', retry=True)
        attempts_path = Path(state_root) / 'toolset-update-attempts.json'
        try:
            attempts = json.loads(attempts_path.read_text())
        except (OSError, ValueError):
            attempts = {}
        if attempts.get('revision') != expected:
            attempts = dict(revision=expected, count=0)
        if attempts['count'] >= ATTEMPTS:
            return dict(ok=False, reason=f'update attempts exhausted for {expected}', retry=True)
        attempts['count'] += 1
        atomic_write(attempts_path, json.dumps(attempts) + '\n')
        with open(Path(state) / 'engine.err', 'a') as err:
            argv = (['git', '-C', package, 'merge', '--ff-only', expected] if independent
                    else [pi, 'update', source])
            result = subprocess.run(['timeout', '--foreground', '--kill-after=5', '300', *argv],
                                    stdout=err, stderr=err)
        installed = git(package, 'rev-parse', 'HEAD')
        if result.returncode or not expected or expected != installed:
            return dict(ok=False, reason='update failed or candidate changed; keeping the running release',
                        blocked=installed, expected=expected)
        return dict(ok=True, revision=installed, note=check.get('note', ''))


def launch(state, name, intent, limit, argv):
    from types import SimpleNamespace
    owner = SimpleNamespace(state=Path(state))
    with open(owner.state / f'maintenance-{name}.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = read(owner, name)
        if (record.get('job', {}).get('intent') != intent
                or record['job'].get('cancelled')
                or time.time() - record['job']['started'] >= 10):
            return  # parent retired this intent; a delayed child cannot act on it
        record['job'].update(pid=os.getpid(), start_time=start_time(os.getpid()))
        write(owner, name, record)
    code = 125
    allowed = True
    if name == 'publication':
        owner.repo = record.get('repository')
        push = record.get('phase') != 'fetch'
        expected = record.get('endpoint' if push else 'fetch_endpoint')
        allowed = bool(owner.repo and expected and endpoint(owner, record['remote'], push=push) == expected)
    if allowed:
        try:
            code = subprocess.run(['timeout', '--foreground', '--kill-after=5', str(limit), *argv]).returncode
        except OSError:
            pass
    atomic_write(owner.state / f'maintenance-{name}.exit', str(code) + '\n')
    os.killpg(os.getpid(), signal.SIGKILL)  # no hook/package descendants survive the bounded job


if __name__ == '__main__':
    if sys.argv[1] == 'launch':
        launch(*sys.argv[2:6], sys.argv[6:])
    else:
        print(json.dumps(update_package(*sys.argv[2:])))
