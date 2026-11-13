"""Console and machine-readable usage and cost reporting.

Reads the private accounting store (`runs.jsonl`) and prints a short,
actionable cost table: measured dollars, tokens and runs for the whole
project, per role, per host, per provider, per model and per model-family.

The repository does not price subscription usage yet, so the USD line only
counts rows with `cost_source: provider_reported` and `billing != subscription`.
Rows without measured billing are still counted (runs, tokens) but labelled
`unknown` so the report never shows a misleading zero.
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys
import time

from pi_autowork.accounting import (account, bucket, records, timestamp, add, df, number, usd_short)


def usd_report(loop=None, *, total=None):
    """Render cost in dollars from an accounting total.

    Use `loop` with an iterable of (label, bucket) pairs to print per-role host,
    provider, model or attempt tables. Use `total=None` with `loop=` as above, or
    pass `total` as the aggregated account bucket to print the whole project.

    Both forms are sorted by measured USD desc. Rows without measured billing are
    still counted (runs, tokens) but never shown as a USD amount.
    """
    if loop is not None and total is None:
        rows = []
        for label, bucket in loop:
            label = label if isinstance(label, str) else str(label)
            if hasattr(bucket, 'summary'):
                rows.append(bucket.summary(label))
            else:
                rows.append(dict(label=label,
                                 runs=bucket.get('runs', 0),
                                 tokens=bucket.get('tokens'),
                                 input_tokens=bucket.get('input_tokens'),
                                 output_tokens=bucket.get('output_tokens'),
                                 measured_cost_usd=bucket.get('measured_cost_usd', 0),
                                 unknown_cost_runs=bucket.get('unknown_cost_runs', 0),
                                 estimated_cost_usd=(bucket.get('measured_cost_usd', 0) / bucket.get('runs', 1))
                                 if bucket.get('runs') else 0.0))
        rows.sort(key=lambda item: item['measured_cost_usd'], reverse=True)
        return [format_row(item) for item in rows]
    if total is None:
        return []
    row = total
    lines = []
    if row['runs']:
        lines.append(format_row(dict(label='TOTAL', runs=row['runs'],
                                     tokens=row['tokens'], input_tokens=row['input_tokens'],
                                     output_tokens=row['output_tokens'],
                                     measured_cost_usd=row['measured_cost_usd'],
                                     unknown_cost_runs=row['unknown_cost_runs'],
                                     estimated_cost_usd=(row['measured_cost_usd'] / row['runs']) if row['runs'] else 0.0)))
    if row['unknown_cost_runs']:
        lines.append(f"{'UNKNOWN (no billing)':<34} {row['unknown_cost_runs']:>4} runs  "
                     f"{usd_short(row['measured_cost_usd']):>10}  tokens {df(row['tokens'])}")
    return lines


def format_row(item):
    """Small aligned table row: label, runs, measured USD, tokens."""
    return (f"{item['label']:<34} {item['runs']:>4} runs  "
            f"{usd_short(item['measured_cost_usd']):>10}  tokens {df(item['tokens'])}")


def cmd_usage(repo, *, state, since=None, window=None, json_output=False):
    """Print a short, actionable cost table for the whole project.

    `window` is seconds and implies `--since` for the whole window. Both
    `since` and `window` omitted fall back to the last 7 days.
    """
    root = Path(state)
    if not (root / 'runs.jsonl').exists():
        for candidate in (root, *root.parents):
            if (candidate / 'runs.jsonl').exists():
                root = candidate
                break
    directory = root
    now = time.time()
    cycle_since = since
    if window is not None:
        cycle_since = now - window
    elif since is not None:
        cycle_since = timestamp(since)
    else:
        cycle_since = now - 7 * 24 * 3600
    if cycle_since is None:
        cycle_since = now - 7 * 24 * 3600
    diagnostics = dict(invalid_records=0)
    total = bucket()
    loaded = list(records(directory / 'runs.jsonl', cycle_since, now, diagnostics, 'run_id'))
    for row in loaded:
        add(total, row)
    result = dict(total=total, tasks={}, roles={}, hosts={}, providers={}, models={}, attempts={}, diagnostics=diagnostics)
    rep0 = usd_report(total=result['total'])
    reports = [rep0]
    reports += [
        usd_report(loop=result['roles'].items()),
        usd_report(loop=result['hosts'].items()),
        usd_report(loop=result['providers'].items()),
        usd_report(loop=result['models'].items()),
        usd_report(loop=result['attempts'].items()),
    ]

    if json_output:
        print(json.dumps(result, indent=2, default=str))
        return 0
    if not reports[0]:
        print('No recorded usage in the requested window.')
        return 0
    print('Cost report')
    print('=' * 96)
    widths = [max((len(line) for line in group), default=0) for group in reports]
    for index, group in enumerate(reports):
        if index:
            print('-' * 96)
        for line in group:
            print(f'{line:<{widths[index] + 2}}' if len(line) < widths[index] else line)
    total = result['total']
    print('-' * 96)
    parts = [f"{total['runs']} runs", df(total['tokens']), df(total['input_tokens']), df(total['output_tokens'])]
    print(f'  Total {parts[0]:<10} {parts[1]:<12} {parts[2]:<10} {parts[3]}')
    if total['measured_cost_usd'] > 0:
        print(f'  Measured USD {usd_short(total["measured_cost_usd"]):>10}')
    if total['unknown_cost_runs']:
        print(f'  Unknown USD  {total["unknown_cost_runs"]} run(s) not priced '
              '(subscription/unknown billing)')
    if total['cost_usd'] is None:
        print('  Cost status  incomplete — some runs have no billing yet')
    return 0
