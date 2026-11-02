#!/usr/bin/env python3
"""Convert a Pi JSONL session into a Tier 3 trace object.

The converter keeps executed command events, maps read-only `cat`/`head`/`tail`/
`sed`/`git show`/`git diff`/`git log` commands to read events, and keeps the last
assistant text as the final event. Heredoc bodies are removed from the command
text so a quoted example is not mistaken for an executed command.

    python3 scripts/pi_trace_to_eval.py --skill ponytail-review \\
      --name ponytail-review-live session.jsonl -o trace.json
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import sys

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")

def strip_heredocs(command):
    lines = command.splitlines()
    result, delimiter = [], None
    for line in lines:
        if delimiter is None:
            result.append(line)
            match = HEREDOC.search(line)
            if match:
                delimiter = match.group(2)
        elif line.strip() == delimiter:
            result.append(line)
            delimiter = None
    return '\n'.join(result)


def _segments(command):
    return [part.strip() for part in re.split(r'\s*(?:;|&&|\|\|)\s*', command) if part.strip()]


def _read_paths(segment):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return []
    while tokens and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', tokens[0]):
        tokens.pop(0)
    if not tokens:
        return []
    if tokens[:2] in (['git', 'show'], ['git', 'diff'], ['git', 'log']):
        paths = ['HEAD']
        if '--' in tokens:
            paths.extend(token for token in tokens[tokens.index('--') + 1:] if not token.startswith('-'))
        return paths
    if tokens[0] not in ('cat', 'head', 'tail', 'sed'):
        return []
    if tokens[0] == 'sed':
        # Skip the script argument after -n/-e; the remaining tokens are paths.
        skip = False
        paths = []
        for token in tokens[1:]:
            if skip:
                skip = False
                continue
            if token in ('-n', '-e'):
                skip = True
                continue
            if token.startswith('-'):
                continue
            paths.append(token)
        return paths
    return [token for token in tokens[1:] if not token.startswith('-')]


def convert(path, skill, name=None):
    events, starts, final = [], {}, ''
    model = ''
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f'invalid JSONL line: {exc}') from exc
        kind = item.get('type')
        if kind == 'tool_execution_start':
            starts[item.get('toolCallId')] = item
        elif kind == 'tool_execution_end':
            start = starts.pop(item.get('toolCallId'), None)
            if start is None:
                continue
            tool = start.get('toolName')
            args = start.get('args') if isinstance(start.get('args'), dict) else {}
            if tool in ('read', 'write', 'edit') and isinstance(args.get('path'), str):
                events.append({'type': tool, 'path': args['path']})
            elif tool in ('bash', 'shell') and isinstance(args.get('command'), str):
                command = strip_heredocs(args['command'])
                result = item.get('result') if isinstance(item.get('result'), dict) else {}
                structured = result.get('structuredContent') if isinstance(result.get('structuredContent'), dict) else {}
                exit_code = structured.get('exit_code')
                for segment in _segments(command):
                    event = {'type': 'command', 'command': segment, 'raw_command': command}
                    if isinstance(exit_code, int) and not isinstance(exit_code, bool):
                        event['exit'] = exit_code
                    events.append(event)
                    for read_path in _read_paths(segment):
                        events.append({'type': 'read', 'path': read_path, 'derived_from': 'bash'})
        elif kind == 'message_end' and item.get('message', {}).get('role') == 'assistant':
            message = item['message']
            if message.get('provider'):
                model = str(message.get('provider')) + '/' + str(message.get('model') or '')
            text = ''.join(part.get('text', '') for part in message.get('content', [])
                           if isinstance(part, dict) and part.get('type') == 'text')
            if text:
                final = text
    if final:
        events.append({'type': 'final', 'text': final})
    return {'name': name or Path(path).stem, 'skill': skill, 'model': model,
            'note': 'Converted Pi trace; command heredoc bodies removed.',
            'events': events}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--skill', required=True)
    parser.add_argument('--name')
    parser.add_argument('-o', '--output', type=Path)
    args = parser.parse_args(argv)
    try:
        value = convert(args.trace, args.skill, args.name)
    except (OSError, ValueError) as exc:
        print(f'pi_trace_to_eval: {exc}', file=sys.stderr)
        return 1
    text = json.dumps(value, indent=2)
    if args.output:
        args.output.write_text(text + '\n')
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
