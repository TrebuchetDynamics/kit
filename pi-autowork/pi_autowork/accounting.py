"""Private run and owner-time accounting. No prices, billing calls or execution decisions."""

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

ROLES = {'worker': 'worker', 'verify': 'reviewer', 'reviewer': 'reviewer',
         'coordinator': 'coordinator', 'merge': 'coordinator', 'triage': 'coordinator',
         'provision': 'coordinator', 'maintainer': 'coordinator'}
INTERVENTIONS = {'blocker_answered', 'contract_edited', 'hand_closed'}


class AccountBucket:
    """A row for the cost report: measured USD, tokens and runs."""

    def __init__(self):
        self.runs = 0
        self.tokens = None
        self.input_tokens = None
        self.output_tokens = None
        self.measured_cost_usd = 0.0
        self.unknown_cost_runs = 0

    def add(self, row):
        self.runs += 1
        for field in ('tokens', 'input_tokens', 'output_tokens'):
            value = number(row.get(field))
            if value is not None:
                existing = getattr(self, field)
                setattr(self, field, (existing or 0) + value)
        cost = number(row.get('cost_usd'))
        measured = row.get('cost_source') == 'provider_reported' and row.get('billing') != 'subscription'
        if measured:
            self.measured_cost_usd += cost or 0
        else:
            self.unknown_cost_runs += 1

    def summary(self, label):
        return dict(label=label, runs=self.runs, tokens=self.tokens,
                    input_tokens=self.input_tokens, output_tokens=self.output_tokens,
                    measured_cost_usd=self.measured_cost_usd,
                    unknown_cost_runs=self.unknown_cost_runs,
                    estimated_cost_usd=(self.measured_cost_usd / self.runs) if self.runs else 0.0)


def by_task():
    return defaultdict(lambda: AccountBucket())


def df(value):
    """Short human value: bytes/KB/MiB, tokens or currency."""
    if value is None:
        return '—'
    if isinstance(value, (int, float)) and abs(value) >= 1024 ** 3:
        return f'{value / (1024 ** 3):.2f} GiB'
    if isinstance(value, (int, float)) and abs(value) >= 1024 ** 2:
        return f'{value / (1024 ** 2):.2f} MiB'
    if isinstance(value, (int, float)) and abs(value) >= 1024:
        return f'{value / 1024:.2f} KiB'
    if isinstance(value, (int, float)) and abs(value) < 1:
        return f'{value:.4f} B'
    return str(int(value))


def usd_short(value):
    """Short human USD: $1.23, $1.2K, $1.2M."""
    if value is None:
        return '—'
    if value >= 1_000_000:
        return f'${value / 1_000_000:.2f}M'
    if value >= 1_000:
        return f'${value / 1_000:.2f}K'
    return f'${value:.2f}'


def state_dir(repo, root=None):
    common = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--path-format=absolute',
                                      '--git-common-dir'], text=True).strip()
    root = root or os.environ.get('PI_AUTOWORK_STATE_DIR') or str(
        Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'pi-autowork')
    return Path(root) / hashlib.sha256(common.encode()).hexdigest()[:16]


def attributed_task(role, task):
    """Known repository-job labels are not task relationships (legacy records too)."""
    if (role == 'maintainer' and task == 'DOCS-MAINTAINER'
            or role == 'merge' and isinstance(task, str)
            and re.fullmatch(r'(?:pi-autowork/)?[0-9]{8}-[0-9]{6}', task)):
        return None
    return task


def append(path, row):
    """One private O_APPEND write; a leading newline separates a prior torn record."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = (json.dumps(row, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b'\n':
            data = b'\n' + data
        if os.write(fd, data) != len(data):
            raise OSError('short accounting write')
        os.fsync(fd)
    finally:
        os.close(fd)


def attention(repo, minutes, *, task=None, note=None, category='manual', root=None):
    if number(minutes) is None:
        raise ValueError('minutes must be a finite nonnegative number')
    if task is not None and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', task):
        raise ValueError('invalid task ID')
    append(state_dir(repo, root) / 'attention.jsonl',
           dict(event_id=uuid.uuid4().hex, time=time.time(), task=task, minutes=minutes,
                category=category, note=note))


def parse_window(argv):
    """Parse an optional --since/--window pair into (since, until) timestamps."""
    since = None
    until = None
    for index, arg in enumerate(argv):
        if arg in ('--since', '--window'):
            if index + 1 >= len(argv):
                raise ValueError(f'{arg} needs a value')
            raw = argv[index + 1]
            try:
                value = float(raw)
            except ValueError:
                raise ValueError(f'expected seconds, got: {raw}') from None
            if value < 0:
                raise ValueError(f'expected nonnegative seconds, got: {raw}')
            if arg == '--since':
                since = time.time() - value
            else:
                until = time.time() + value
    return since, until


def timestamp(value):
    if number(value) is not None:
        return value
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def records(path, since, now, diagnostics, identity):
    seen = set()
    invalid = 'invalid_run_records' if identity == 'run_id' else 'invalid_attention_records'
    try:
        stream = path.open()
    except FileNotFoundError:
        return
    with stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not line.endswith('\n') or not isinstance(row, dict):
                    raise ValueError('incomplete record')
                stamp = timestamp(row.get('time'))
                if stamp is None:
                    raise ValueError('missing timestamp')
            except (ValueError, TypeError):
                diagnostics['invalid_records'] += 1
                diagnostics[invalid] += 1
                continue
            if not since <= stamp <= now:
                continue
            # Legacy rows had no run ID: retain each line, rather than collapsing
            # legitimate equal runs that happened in the same second.
            key = row.get(identity)
            if key is not None and not isinstance(key, str):
                diagnostics['invalid_records'] += 1
                diagnostics[invalid] += 1
                continue
            if key and key in seen:
                diagnostics['duplicate_runs' if identity == 'run_id' else 'duplicate_attention'] += 1
                continue
            if key:
                seen.add(key)
            yield row


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def df(value):
    """Short human value: bytes/KB/MiB, tokens or currency."""
    if value is None:
        return '—'
    if isinstance(value, (int, float)) and abs(value) >= 1024 ** 3:
        return f'{value / (1024 ** 3):.2f} GiB'
    if isinstance(value, (int, float)) and abs(value) >= 1024 ** 2:
        return f'{value / (1024 ** 2):.2f} MiB'
    if isinstance(value, (int, float)) and abs(value) >= 1024:
        return f'{value / 1024:.2f} KiB'
    if isinstance(value, (int, float)) and abs(value) < 1:
        return f'{value:.4f} B'
    return str(int(value))


def usd_short(value):
    """Short human USD: $1.23, $1.2K, $1.2M."""
    if value is None:
        return '—'
    if value >= 1_000_000:
        return f'${value / 1_000_000:.2f}M'
    if value >= 1_000:
        return f'${value / 1_000:.2f}K'
    return f'${value:.2f}'


def bucket():
    return dict(runs=0, tokens=None, input_tokens=None, output_tokens=None,
                measured_cost_usd=0, unknown_cost_runs=0, cost_usd=None, cost_status='missing')


def add(target, row):
    first = target['runs'] == 0
    target['runs'] += 1
    for field in ('tokens', 'input_tokens', 'output_tokens'):
        value = number(row.get(field))
        target[field] = value if first else (target[field] + value
                                            if value is not None and target[field] is not None else None)
    cost = number(row.get('cost_usd'))
    measured = row.get('cost_source') == 'provider_reported' and row.get('billing') != 'subscription'
    # New partial runs preserve the measured subset, without claiming a complete bill.
    partial = number(row.get('measured_cost_usd')) if measured else None
    target['measured_cost_usd'] += (partial if partial is not None else cost or 0) if measured else 0
    target['unknown_cost_runs'] += not measured or cost is None
    target['cost_usd'] = target['measured_cost_usd'] if not target['unknown_cost_runs'] else None
    target['cost_status'] = 'measured' if target['cost_usd'] is not None else 'missing'


def add_groups(target, row, role):
    add(target, row)
    add(target['roles'].setdefault(role, bucket()), row)
    host, model = row.get('host') or 'unknown', row.get('model') or 'unknown'
    provider = row.get('provider')
    group = next((g for g in target['host_models'] if (g['host'], g['provider'], g['model'])
                  == (host, provider, model)), None)
    if group is None:
        group = dict(host=host, provider=provider, model=model, **bucket())
        target['host_models'].append(group)
    add(group, row)


def measure(repo, since, now, *, tasks=(), verified=(), lifecycle=(), root=None):
    """Windowed usage; retries add spend, never another verified/delivered task.

    Measured subtotals are lower bounds when any billing is missing. Unrecorded
    owner time is unknown even when another task has recorded minutes.
    """
    directory = state_dir(repo, root)
    diagnostics = dict(invalid_records=0, invalid_run_records=0, invalid_attention_records=0,
                       duplicate_runs=0, duplicate_attention=0)
    total, unattributed = bucket(), bucket()
    by_task = {}

    def task_row(task):
        if task not in by_task:
            by_task[task] = dict(**bucket(), roles={}, attempts={}, host_models=[],
                                 owner_minutes=None, interventions={})
        return by_task[task]

    for task in tasks:
        task_row(task)
    for row in records(directory / 'runs.jsonl', since, now, diagnostics, 'run_id'):
        add(total, row)
        # These production jobs operate on the whole repository/session. Their
        # legacy task labels were job names, not relationships to actual tasks.
        task = attributed_task(row.get('role'), row.get('task'))
        role = ROLES.get(row.get('role')) if isinstance(row.get('role'), str) else None
        if not isinstance(task, str) or task in ('', 'unknown') or not role:
            add(unattributed, row)
            continue
        target = task_row(task)
        add_groups(target, row, role)
        attempt = row.get('attempt_id')
        if not isinstance(attempt, str) or not attempt:
            attempt = 'unknown'
        add_groups(target['attempts'].setdefault(attempt, dict(**bucket(), roles={}, host_models=[])), row, role)
    owner_minutes, unattributed_minutes, categories = None, None, Counter()
    for row in records(directory / 'attention.jsonl', since, now, diagnostics, 'event_id'):
        minutes = number(row.get('minutes'))
        if minutes is None:
            diagnostics['invalid_records'] += 1
            diagnostics['invalid_attention_records'] += 1
            continue
        owner_minutes = (owner_minutes or 0) + minutes
        categories[row.get('category') or 'unknown'] += 1
        task = row.get('task')
        if isinstance(task, str) and task:
            target = task_row(task)
            target['owner_minutes'] = (target['owner_minutes'] or 0) + minutes
        else:
            unattributed_minutes = (unattributed_minutes or 0) + minutes
    delivered = set()
    seen = set()
    for fact in lifecycle:
        identity = fact.get('event_id')
        if identity in seen or not since <= fact.get('timestamp', 0) <= now:
            continue
        seen.add(identity)
        task, kind = fact.get('task_id'), fact.get('event')
        if not task or task == 'unknown':
            continue
        if kind == 'delivered':
            delivered.add(task)
        if kind in INTERVENTIONS:
            counts = task_row(task)['interventions']
            counts[kind] = counts.get(kind, 0) + 1
    verified = set(verified)
    for task in delivered | verified:
        task_row(task)
    # Missing usage for a counted completion must not become a free completion.
    missing = any(not by_task[t]['runs'] for t in delivered | verified)
    if missing or diagnostics['invalid_run_records']:
        total.update(cost_usd=None, cost_status='missing')
    return dict(**total, tasks=by_task, unattributed=unattributed, diagnostics=diagnostics,
                unknown_cost_tasks=sorted(t for t, r in by_task.items() if r['cost_usd'] is None),
                owner_minutes=owner_minutes, unattributed_owner_minutes=unattributed_minutes,
                attention_categories=dict(categories), verified_tasks=len(verified), delivered_tasks=len(delivered),
                cost_per_verified_task_usd=total['cost_usd'] / len(verified)
                if verified and total['cost_usd'] is not None else None,
                cost_per_delivered_task_usd=total['cost_usd'] / len(delivered)
                if delivered and total['cost_usd'] is not None else None)


def usd(total, *, tasks=(), verified=(), cycle=None):
    """Render cost in dollars from a windowed accounting total.

    The repo does not price subscription usage, so only rows carrying
    `cost_source: provider_reported` and `billing != subscription` become USD.
    Everything else is reported as unknown (never zero).
    """
    if cycle is not None:
        cost = 0.0
        known = 0
        for row in cycle:
            if row.get('cost_source') == 'provider_reported' and row.get('billing') != 'subscription':
                cost += number(row.get('cost_usd')) or 0
                known += 1
        return dict(measured_cost_usd=cost, measured_runs=known, runs=len(cycle), unknown=0)
    if total['cost_usd'] is None:
        return dict(measured_cost_usd=0.0, measured_runs=total['runs'] - total['unknown_cost_runs'],
                    runs=total['runs'], unknown=total['unknown_cost_runs'])
    return dict(measured_cost_usd=total['cost_usd'], measured_runs=total['runs'],
                runs=total['runs'], unknown=0)


def account(repo, root=None, *, since=None, window=None):
    """Return measured tokens, USD and per-model totals for a time window.

    `window` is seconds and implies `--since` for the whole window. Both
    `since` and `window` omitted fall back to the last 7 days.
    """
    directory = state_dir(repo, root)
    now = time.time()
    cycle_since, cycle_until = since, None
    if window is not None:
        cycle_since, cycle_until = now - window, now
    elif since is not None:
        cycle_since = timestamp(since)
        cycle_until = now
    else:
        cycle_since = now - 7 * 24 * 3600
        cycle_until = now
    if cycle_until > now:
        cycle_until = now
    diagnostics = dict(invalid_records=0)
    total = bucket()
    roles = {}
    hosts = {}
    providers = {}
    models = {}
    attempts = {}
    for row in records(directory / 'runs.jsonl', cycle_since, cycle_until, diagnostics, 'run_id'):
        add(total, row)
        role = row.get('role')
        if role not in ROLES:
            role = None
        if role not in roles:
            roles[role] = bucket()
        add(roles[role], row)
        host = row.get('host') or 'unknown'
        if host not in hosts:
            hosts[host] = bucket()
        add(hosts[host], row)
        provider = row.get('provider') or 'unknown'
        if provider not in providers:
            providers[provider] = bucket()
        add(providers[provider], row)
        model = row.get('model') or 'unknown'
        if model not in models:
            models[model] = bucket()
        add(models[model], row)
        key = (row.get('host'), provider, model)
        if key not in attempts:
            attempts[key] = bucket()
        add(attempts[key], row)
    return dict(total=total, tasks=by_task(), roles=roles, hosts=hosts, providers=providers,
                models=models, attempts=attempts, diagnostics=diagnostics)
