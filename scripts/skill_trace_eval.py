#!/usr/bin/env python3
"""Tier 3 skill-trace grading. Pure data; never executes trace content.

A trace records what an agent did: reads, writes, commands, user-visible assistant
messages and its final answer. A spec names the required and forbidden events for
one skill. This grader checks the trace shape and sequence. It does not call a
model and does not prove that a live agent will behave the same way.

    python3 scripts/skill_trace_eval.py evals/tier3/ponytail-review.json \\
      evals/tier3/traces/ponytail-review-pass.json
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
        tool = event.get('tool')
        if tool in ('read', 'write', 'edit'):
            return tool
        if tool in ('bash', 'shell') and _command(event) is not None:
            return 'command'
        return None
    return kind if kind in ('read', 'write', 'edit', 'command', 'assistant', 'final') else None


def _path(event):
    if isinstance(event.get('path'), str):
        return event['path']
    args = event.get('args')
    if isinstance(args, dict) and isinstance(args.get('path'), str):
        return args['path']
    return None


def _command(event):
    if isinstance(event.get('command'), str):
        return event['command']
    args = event.get('args')
    if isinstance(args, dict) and isinstance(args.get('command'), str):
        return args['command']
    return None


def _exit(event):
    value = event.get('exit')
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    result = event.get('result')
    if isinstance(result, dict):
        structured = result.get('structuredContent')
        if isinstance(structured, dict) and isinstance(structured.get('exit_code'), int):
            return structured['exit_code']
    return None


def _clause_text(clause):
    return json.dumps(clause, sort_keys=True, ensure_ascii=False)


def _check_clause(clause, *, allow_before_first=False):
    if not isinstance(clause, dict):
        raise TraceError('every clause must be an object')
    allowed = {'event', 'path', 'command', 'exit', 'contains', 'text_regex'}
    if allow_before_first:
        allowed.add('before_first')
    unknown = set(clause) - allowed
    if unknown:
        raise TraceError('unknown clause keys: ' + ', '.join(sorted(unknown)))
    kind = clause.get('event')
    if kind not in ('read', 'write', 'edit', 'command', 'assistant', 'final'):
        raise TraceError('clause.event must be read, write, edit, command, assistant or final')
    if 'path' in clause and kind not in ('read', 'write', 'edit'):
        raise TraceError('path is only valid for read, write or edit')
    if ('command' in clause or 'exit' in clause) and kind != 'command':
        raise TraceError('command and exit are only valid for command')
    if 'contains' in clause and kind not in ('assistant', 'final'):
        raise TraceError('contains is only valid for assistant or final')
    if 'text_regex' in clause:
        if kind not in ('assistant', 'final'):
            raise TraceError('text_regex is only valid for assistant or final')
        if not isinstance(clause['text_regex'], str):
            raise TraceError('text_regex must be a regular expression string')
        try:
            re.compile(clause['text_regex'])
        except re.error as exc:
            raise TraceError(f'invalid text_regex: {exc}') from exc
    if 'before_first' in clause:
        _check_clause(clause['before_first'])


def _matches(event, clause):
    kind = clause['event']
    if _kind(event) != kind:
        return False
    if 'path' in clause:
        path = _path(event)
        if not isinstance(path, str) or not fnmatchcase(path, clause['path']):
            return False
    if 'command' in clause:
        command = _command(event)
        if not isinstance(command, str) or not re.search(clause['command'], command):
            return False
        if 'exit' in clause and _exit(event) != clause['exit']:
            return False
    if 'text_regex' in clause:
        text = event.get('text')
        if not isinstance(text, str) or not re.search(clause['text_regex'], text):
            return False
    if kind in ('assistant', 'final') and 'contains' in clause:
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
    for key in ('require', 'forbid'):
        if key in spec and not isinstance(spec[key], list):
            raise TraceError(f'spec.{key} must be a list')
    for index, clause in enumerate(spec.get('require', [])):
        _check_clause(clause, allow_before_first=True)
        candidates = events
        if 'before_first' in clause:
            # The boundary is the first attempt, not the first successful result.
            first = next((i for i, event in enumerate(events)
                          if _matches(event, clause['before_first'])), 0)
            candidates = events[:first]
        found = sum(1 for event in candidates if _matches(event, clause))
        matched[f'require[{index}]'] = found
        if not found:
            diagnostic = ('missing required before first: ' if 'before_first' in clause
                          else 'missing required: ')
            failures.append(diagnostic + _clause_text(clause))
    for index, clause in enumerate(spec.get('forbid', [])):
        _check_clause(clause)
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
