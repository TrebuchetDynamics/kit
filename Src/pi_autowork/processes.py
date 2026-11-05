"""Linux process identity and ancestry shared by runner and job liveness readers."""
from collections import namedtuple
import os
from pathlib import Path

ProcessStat = namedtuple('ProcessStat', 'state parent started')


def process_stat(pid, proc='/proc'):
    """Read state, parent PID and start ticks; comm may contain spaces and ')'."""
    try:
        pid = int(pid)
        if pid <= 0:
            return None
        fields = Path(f'{proc}/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return ProcessStat(fields[0], int(fields[1]), fields[19])
    except (OSError, ValueError, TypeError, IndexError):
        return None


def start_time(pid):
    stat = process_stat(pid)
    return stat.started if stat else None


def rss_mb(pid, proc='/proc'):
    """Resident set size in MiB, or None when the process or its status is unreadable."""
    try:
        for line in Path(f'{proc}/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def cpu_seconds(pid, proc='/proc'):
    """User plus system CPU seconds, or None when the process stat is unreadable."""
    try:
        fields = Path(f'{proc}/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
    except (OSError, ValueError, IndexError, AttributeError):
        return None


def descendants(pid, proc='/proc'):
    """Live descendant PIDs of pid, excluding pid itself."""
    try:
        pids = [int(path.name) for path in Path(proc).iterdir() if path.name.isdigit()]
    except OSError:
        return []
    stats = {candidate: process_stat(candidate, proc) for candidate in pids}
    found = []
    for candidate, stat in stats.items():
        if candidate == pid or not stat or stat.state in ('Z', 'X'):
            continue
        parent, seen = stat.parent, set()
        while parent > 1 and parent not in seen:
            if parent == pid:
                found.append(candidate)
                break
            seen.add(parent)
            parent_stat = stats.get(parent) or process_stat(parent, proc)
            if not parent_stat or parent_stat.state in ('Z', 'X'):
                break
            parent = parent_stat.parent
    return found


def alive(pid, started=None):
    """A non-zombie process, matching start ticks when supplied.

    PID-only probes are for transient processes, not persisted runner/job records.
    Use ``running`` for records, whose identity must be present as well as match.
    """
    stat = process_stat(pid)
    return bool(stat and stat.state not in ('Z', 'X') and (started is None or stat.started == str(started)))


def running(record):
    """Only recorded start ticks can establish that a runner or job still lives."""
    return bool(isinstance(record, dict) and record.get('start_time')
                and alive(record.get('pid'), record['start_time']))


def own_process(pid, proc='/proc'):
    """Whether PID is this runner or a descendant (engine helpers/background jobs)."""
    me, seen = os.getpid(), set()
    while isinstance(pid, int) and pid > 1 and pid not in seen:
        if pid == me:
            return True
        seen.add(pid)
        stat = process_stat(pid, proc)
        if not stat or stat.state in ('Z', 'X'):
            return False
        pid = stat.parent
    return False


def process_name(pid):
    try:
        return b' '.join(Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[:3]).decode(errors='replace') \
            or 'helper'
    except OSError:
        return 'helper'
