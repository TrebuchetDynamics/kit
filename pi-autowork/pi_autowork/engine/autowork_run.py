#!/usr/bin/env python3
"""Run a worker suite/build in the shared fleet full-check pool (stdlib only)."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

from pi_autowork import main_check


def process_identity(pid):
    """Linux process start ticks, so old queue records cannot match a reused PID."""
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return int(fields[1]), int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


def slot_root():
    return main_check.slot_root()


def records(directory):
    for path in Path(directory).glob('*.json') if directory else ():
        try:
            value = json.loads(path.read_text())
            if isinstance(value, dict):
                yield value
        except (OSError, ValueError):
            continue  # an interrupted write is not a wait record


def waiting_records(directory):
    """Only live, identity-matching wrappers still awaiting admission."""
    return [row for row in records(directory)
            if row.get('admitted') is None and not row.get('finished') and row.get('start_ticks')
            and main_check.alive(row.get('pid'), row.get('start_ticks'))]


def queue_intervals(directory, command):
    """Queue intervals attributable to this tool command, including completed wrappers."""
    identity = process_identity(command)
    if identity is None:
        return []
    intervals = []
    for row in records(directory):
        if [command, identity[1]] not in row.get('ancestors', []):
            continue
        end = row.get('admitted') or row.get('finished') or row['updated']
        if (row.get('admitted') is None and not row.get('finished')
                and main_check.alive(row['pid'], row['start_ticks'])):
            end = time.monotonic()
        intervals.append((row['waiting_since'], end))
    return intervals


def queued_seconds(directory, command):
    """Union of attributable waits, including a live queue interval."""
    total = end = 0
    for start, finish in sorted(queue_intervals(directory, command)):
        total += max(0, finish - max(start, end))
        end = max(end, finish)
    return total


def report_wait(directory, report):
    """Enrich an existing worker report; do not manufacture one for a dead worker."""
    path = Path(report)
    if not path.is_file():
        return
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        return
    value['worker_check_slot_wait_seconds'] = sum(
        row.get('wait_seconds', max(0, (row.get('finished') or row['updated']) - row['waiting_since']))
        for row in records(directory))
    temporary = path.with_suffix('.wait.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print('usage: autowork-run <command> [args ...]', file=sys.stderr)
        return 2
    pid = os.getpid()
    parent, ticks = process_identity(pid)
    ancestors, current = [], pid
    while identity := process_identity(current):
        ancestors.append([current, identity[1]])
        current = identity[0]
    row = dict(pid=pid, ppid=parent, start_ticks=ticks, ancestors=ancestors,
               waiting_since=time.monotonic(), admitted=None)
    directory = os.environ.get('AUTOWORK_WORKER_CHECK_DIR')
    record = Path(directory) / f'{pid}-{ticks}.json' if directory else None

    def save():
        if record is not None:
            record.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            row['updated'] = time.monotonic()
            temporary = record.with_suffix('.tmp')
            temporary.write_text(json.dumps(row) + '\n')
            temporary.replace(record)

    lease = None
    announced = False
    try:
        def waiting(ahead):
            nonlocal announced
            row.update(ahead=ahead, holders=main_check.slot_holders())
            save()
            if not announced:
                print('autowork-run: waiting for a worker check slot; queued for a fleet slot; holders: '
                      + ', '.join(row['holders'] or ['unknown']), file=sys.stderr, flush=True)
                announced = True

        admission = (main_check.check_slot(waiting, holder=dict(runner=str(Path.cwd()), pid=pid))
                     if main_check.full_suite_command(shlex.join(argv), Path.cwd()) else nullcontext(None))
        with admission as lease:
            row['admitted'] = time.monotonic()
            row['wait_seconds'] = row['admitted'] - row['waiting_since'] if announced else 0.0
            save()
            # Inherit the lease: killing this supervisor cannot admit another suite while its child runs.
            with subprocess.Popen(argv, pass_fds=(() if lease is None else (lease,)), start_new_session=True) as child:
                interrupted, descendants = False, {}
                def forward(sig, frame):
                    nonlocal interrupted
                    interrupted = True
                    # Test runners can start new sessions and close fds. Capture their identities
                    # before terminating their parent, so reparenting cannot hide a running suite.
                    processes = {int(p.name): process_identity(int(p.name)) for p in Path('/proc').glob('[0-9]*')}
                    pending = [child.pid]
                    while pending:
                        parent = pending.pop()
                        for pid, identity in processes.items():
                            if identity and identity[0] == parent and pid not in descendants:
                                descendants[pid] = identity[1]
                                pending.append(pid)
                    for pid in descendants:
                        try:
                            os.kill(pid, sig)
                        except ProcessLookupError:
                            pass
                    try:
                        os.killpg(child.pid, sig)
                    except ProcessLookupError:
                        pass
                signal.signal(signal.SIGTERM, forward)
                signal.signal(signal.SIGINT, forward)
                rc = child.wait()
            if rc < 0 or interrupted:
                # Finish cancellation even for TERM-ignoring checks that left the command group.
                for pid, ticks in descendants.items():
                    identity = process_identity(pid)
                    if identity and identity[1] == ticks:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            return rc if rc >= 0 else 128 - rc
    except FileNotFoundError as error:
        print(f'autowork-run: {error}', file=sys.stderr)
        return 127
    except PermissionError as error:
        print(f'autowork-run: {error}', file=sys.stderr)
        return 126
    finally:
        row['finished'] = time.monotonic()
        save()


def _compat_main(argv):
    import sys
    previous = sys.argv
    sys.argv = [previous[0], *argv]
    try:
        try:
            sys.exit(main())
        except ValueError as error:
            print(f'autowork-run: {error}', file=sys.stderr)
            sys.exit(2)
    finally:
        sys.argv = previous
