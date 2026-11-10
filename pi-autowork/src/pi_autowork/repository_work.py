"""Bounded repository discovery when a continuous runner exhausts its queue.

Uses the existing maintainer checkout, validator and merge path. Discovery can
only add tasks/goals, never loosen an existing task to manufacture progress.
"""
import json
from pathlib import Path
import time

from . import health

EVERY = 1800
LIMIT = 3


def read(state):
    try:
        record = json.loads((Path(state) / 'repository-work.json').read_text())
        return record if isinstance(record, dict) else {}
    except (OSError, ValueError):
        return {}


def trigger(state, *, now=None):
    """Persisted cooldown survives restarts, including failed/no-change searches."""
    now = time.time() if now is None else now
    previous = read(state)
    if previous and now - previous.get('at', now) < EVERY:
        return []
    return [('REPOSITORY', 'discover', 'No existing task can start; inspect independent repository work')]


def reserve(state, *, now=None):
    previous = read(state)
    record = dict(previous, at=time.time() if now is None else now, round=int(previous.get('round', 0)) + 1)
    health.write_status(Path(state) / 'repository-work.json', record)
    return record


def complete(state, result, outcome):
    record = read(state)
    reports = list(record.get('reports', []))
    reports.append(dict(round=record.get('round'), outcome=outcome, text=str(result.get('text') or '')[:16000]))
    record['reports'] = reports[-3:]
    health.write_status(Path(state) / 'repository-work.json', record)


def prompt(repo, tasks, state):
    round_ = int(read(state).get('round', 0)) + 1
    areas = ('tests/reliability', 'documentation', 'UI/UX/accessibility', 'developer tooling')
    area = areas[(round_ - 1) % len(areas)]
    return (
        f'You are discovering independent maintenance work for the continuous Autowork runner of {repo}. '
        'Its existing queue cannot run after bounded task repair. A held milestone, shared serial path, '
        'another session claim or missing Live authorization blocks those tasks, not the entire repository. '
        'Read AGENTS.md, README.md, the standing decision policy and current tasks first. '
        'Respect repository-wide holds, explicit task-only scope, pauses, exclusions and live-operation limits; '
        'if they forbid independent maintenance, report that exact restriction without changing anything. '
        'Never edit existing task or goal records, release another owner, remove dependencies, weaken checks, '
        'grant Live authorization, change instructions or touch runtime state to get work admitted. '
        f'This is search round {round_}; begin with an unexamined seam in {area}, unless stronger concrete '
        'evidence points elsewhere. Use the previous search findings below; avoid repeating an exhausted '
        'search on unchanged evidence. ' + json.dumps(read(state).get('reports', [])) + '\n'
        'Inspect source, callers, tests and user flows in at least two relevant work classes before declaring '
        'no useful eligible delta. Prefer an existing task; do not duplicate its accepted work. '
        'Check actual live file/worktree ownership and choose independent, non-overlapping files. '
        'Find a concrete defect, uncovered important contract, stale operating instruction or measurable friction, '
        'not speculative cleanup or busywork. Do not claim a feature qualified from offline evidence. '
        f'Add at most {LIMIT} bounded ordinary offline building tasks with {tasks} add (and a new goal only '
        'if needed), in Now or Next, without displacing the owner\'s priorities. Each needs source evidence, '
        'user benefit, exact Touches, Acceptance and focused Checks, and genuinely satisfied prerequisites. '
        'Never add another planning/discovery task or a task requiring unavailable authorization or inputs. '
        'Edit only NEW files in tasks/items/ and tasks/goals/. Do not implement in this checkout: the normal '
        f'worker/review pipeline executes admitted tasks. Run {tasks} validate --worktree . and commit once '
        'if useful tasks were found. Do not push or switch branches. If no justified task exists, leave the '
        'checkout unchanged; never fabricate work to keep a counter moving. In your report name checked '
        'paths, findings, rejected candidates, precise remaining restrictions and the next unexamined seam. '
        'End with PI_AUTOWORK_RESULT: completed or PI_AUTOWORK_RESULT: blocked. '
        'A search or queued task is not completed implementation.'
    )


def proposal_error(paths, before, after, added_paths):
    """Discovery is additive; no existing contract or goal can be rewritten."""
    if set(paths) - set(added_paths):
        return 'repository discovery may only add new files'
    if any(before.get(task) != after.get(task) for task in before):
        return 'repository discovery changed an existing task'
    added = set(after) - set(before)
    if not 1 <= len(added) <= LIMIT:
        return f'repository discovery must add 1 to {LIMIT} tasks'
    allowed = {f'tasks/items/{task}.md' for task in added}
    for path in paths:
        if path not in allowed and not (path.startswith('tasks/goals/') and path.endswith('.md')):
            return 'repository discovery changed more than new task/goal records'
    for task in added:
        fields = after[task]['fields']
        if (any(fields.get(key) for key in ('Live authorization', 'Live actor', 'Live at', 'Live scope', 'Ownership'))
                or 'live' in {part.strip().lower() for part in fields.get('Resources', '').split(',')}):
            return 'repository discovery cannot grant authority or add live/owner-only work'
        if (fields.get('Checkbox') != ' ' or fields.get('Section') not in ('Now', 'Next')
                or fields.get('Kind', '').lower() == 'plan'):
            return 'repository discovery must add open building tasks in Now or Next'
    return ''
