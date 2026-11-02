#!/usr/bin/env python3
"""Tier 3 skill-trace grading. Pure data; never executes trace content.

A trace records what an agent did: reads, writes, commands, task events and its
final answer. A spec names the required and forbidden events for one skill. This
grader checks the trace shape and sequence. It does not call a model and does not
prove that a live agent will behave the same way.

    python3 scripts/skill_trace_eval.py evals/tier3/autowork.json \\
      evals/tier3/traces/autowork-pass.json
"""
import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import re
import sys


class TraceError(ValueError):
    """A malformed trace or spec; nothing was executed."""


def _load(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise TraceError(f'cannot read JSON {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise TraceError(f'{path}: expected one JSON object')
    return value


def _kind(event):
    kind = event.get('type')
    if kind == 'tool':
        return event.get('tool') if event.get('tool') in ('read', 'write', 'edit') else None
    return kind if kind in ('read', 'write', 'edit', 'command', 'final') else None


def _clause_text(clause):
    return json.dumps(clause, sort_keys=True, ensure_ascii=False)


def _matches(event, clause):
    kind = clause.get('event')
    if not isinstance(kind, str):
        raise TraceError('every clause needs an event string')
    if _kind(event) != kind:
        return False
    if 'path' in clause:
        path = event.get('path')
        if not isinstance(path, str) or not fnmatchcase(path, clause['path']):
            return False
    if 'command' in clause:
        command = event.get('command')
        if not isinstance(command, str) or not re.search(clause['command'], command):
            return False
        if 'exit' in clause and event.get('exit') != clause['exit']:
            return False
    if kind == 'final' and 'contains' in clause:
        text = event.get('text')
        if not isinstance(text, str):
            return False
        lowered = text.casefold()
        wanted = clause['contains']
        if isinstance(wanted, str):
            wanted = [wanted]
        if not all(str(item).casefold() in lowered for item in wanted):
            return False
    return True


def evaluate(trace, spec):
    """Return a deterministic verdict for one trace against one skill spec."""
    if not isinstance(trace, dict) or not isinstance(spec, dict):
        raise TraceError('trace and spec must be objects')
    skill = spec.get('skill')
    if not isinstance(skill, str) or not skill:
        raise TraceError('spec needs a skill name')
    events = trace.get('events')
    if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
        raise TraceError('trace.events must be a list of objects')
    failures = []
    if trace.get('skill') != skill:
        failures.append(f'skill mismatch: trace={trace.get("skill")!r} spec={skill!r}')
    matched = {}
    for index, clause in enumerate(spec.get('require', [])):
        found = sum(1 for event in events if _matches(event, clause))
        matched[f'require[{index}]'] = found
        if not found:
            failures.append('missing required: ' + _clause_text(clause))
    for index, clause in enumerate(spec.get('forbid', [])):
        found = sum(1 for event in events if _matches(event, clause))
        matched[f'forbid[{index}]'] = found
        if found:
            failures.append('forbidden action: ' + _clause_text(clause))
    return {'ok': not failures, 'skill': skill,
            'trace': trace.get('name') or trace.get('id') or '',
            'failures': failures, 'matched': matched}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('trace', type=Path)
    args = parser.parse_args(argv)
    try:
        result = evaluate(_load(args.trace), _load(args.spec))
    except TraceError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
