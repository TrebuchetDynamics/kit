"""Headless command-result meaning; no execution, mutation or UI effects."""
from dataclasses import dataclass
import json

from pi_autowork import task_status


@dataclass(frozen=True)
class Outcome:
    ok: bool
    message: str
    decision: bool


def interpret(argv, label, result):
    """Interpret a completed command or execution exception, not runner acceptance."""
    decision = argv[1:3] == ['tasks', 'decide'] or (
        argv[1:3] == ['tasks', 'field'] and '--commit' in argv)
    if isinstance(result, Exception):
        return Outcome(False, str(result), decision)
    try:
        output = ((result.stdout or '') + (result.stderr or '')).strip().splitlines()
        ok, message = result.returncode == 0, (output[-1] if output else label)
    except Exception as error:
        return Outcome(False, str(error), decision)
    if ok and decision:
        if '--commit' in argv:
            try:
                receipt = json.loads(result.stdout)
                state = receipt['lifecycle']['state']
                message = receipt['lifecycle']['message']
                if not isinstance(message, str) or not message:
                    raise ValueError('answer lifecycle message unavailable')
                if state != 'committed':
                    if not (argv[1:3] == ['tasks', 'decide'] and '--save-if-detached' in argv
                            and state in ('pending_commit', 'clean') and receipt['commit'] is None
                            and isinstance(receipt['files'], list)
                            and bool(receipt['files']) == (state == 'pending_commit')
                            and all(isinstance(path, str) and path.startswith('tasks/')
                                    and all(part not in ('', '.', '..') for part in path.split('/'))
                                    for path in receipt['files'])):
                        raise ValueError('answer commit not confirmed')
                    message = task_status.edit_lifecycle(state)['message']
            except (ValueError, KeyError, TypeError):
                ok, message = False, 'Answer commit not confirmed; inspect tasks handoff before retrying. Draft kept.'
        else:
            message = task_status.edit_lifecycle('pending_commit')['message']
    return Outcome(ok, message, decision)
