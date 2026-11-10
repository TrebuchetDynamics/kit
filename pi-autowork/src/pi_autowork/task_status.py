"""Pure display vocabulary shared by committed snapshots and legacy CLI lanes."""
ACTIVE, MERGEABLE, WAITING, BLOCKER = 'Active', 'Mergeable', 'Waiting', 'Blocker'
IN_FLIGHT = ('dispatched', 'running', 'reported', 'integrating', 'integrated')
PHASES = {'dispatched': 'starting', 'running': 'implementing', 'reported': 'implemented',
          'integrating': 'integrating', 'integrated': 'integrated'}
CAUSES = {'blocker': 'blocker', 'scope': 'outside Touches', 'scope_request': 'needs files', 'overlap': 'overlap',
          'report': 'bad report', 'conflict': 'conflict', 'validation': 'validation', 'crash': 'crashed', 'empty': 'no result',
          'launch': 'launch failed', 'contract_changed': 'entry changed', 'moved': 'main moved'}
WAIT_PHASES = {'implemented': 'Implemented', 'waiting to integrate': 'Merge turn', 'batch check': 'Batch check',
               'waiting for a check slot': 'Check slot', 'paused': 'Paused', 'pending': 'Pending'}
ACTIVE_PHASES = {'starting': 'Starting', 'running': 'Implementing', 'implementing': 'Implementing',
                 'verifying': 'Verifying', 'integrating': 'Merging', 'landing': 'Merging'}
WAIT_LABELS = {'Implemented': 'implemented, waiting for review', 'Merge turn': 'reviewed, waiting for their merge turn',
               'Batch check': 'in a batch check', 'Check slot': 'waiting for a check slot',
               'Paused': 'paused by a restart', 'Pending': 'pending'}
WAIT_CAUSES = ('overlap',)


def resolving_conflict(row):
    """Coordinator-observed recovery activity, not merge or verification evidence."""
    return (row.get('state') == 'held' and row.get('cause') == 'conflict'
            and row.get('recovery') == 'resolving_conflict')


def blocked_reason(code):
    """Humanize selection codes while preserving task IDs."""
    import re
    return code.replace('_', ' ').lower() if re.fullmatch(r'[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+', code) else code


def closure_display(info):
    """Closure words and evidence for output, not qualification authority."""
    if not info:
        return None
    provenance = info['provenance']
    if provenance == 'coordinator_verified':
        detail = info['evidence'] or 'Verification evidence not recorded'
    elif provenance == 'manual':
        detail = (f'Manually closed by {info["actor"] or "unknown"} at {info["timestamp"] or "unknown"}; '
                  f'not coordinator-verified. {info["reason"] or "Reason not recorded"}')
    else:
        detail = 'Closure provenance not recorded (legacy); no coordinator verification recorded.'
    return dict(label=info['label'], detail=detail, provenance=provenance,
                verified=info['evidence_valid'] if provenance == 'coordinator_verified' else False)


def phase_status(phase):
    """Only integrated (checks/review passed on the session branch) is Mergeable."""
    if phase == 'integrated':
        return MERGEABLE, 'Verified'
    if phase in WAIT_PHASES:
        return WAITING, WAIT_PHASES[phase]
    return ACTIVE, ACTIVE_PHASES.get(phase, phase.capitalize())


def status(lane):
    return phase_status(lane.phase)


def resolver(asked):
    return 'Needs you' if asked else 'Agent repair'


def blocker_detail(cause, asked=False):
    text = CAUSES.get(cause, cause or 'held')
    return f'{text[:1].upper()}{text[1:]} · {resolver(asked)}'


def task(record, blocked=None):
    """Presentation for a stored task; it does not claim to describe a live worker."""
    if record.status != 'open':
        info = record.closure_info or {}
        verified = info.get('evidence_valid') if info.get('provenance') == 'coordinator_verified' else info.get('verified')
        tone = 'success' if verified is True else 'warning' if verified is False or info.get('provenance') == 'manual' else 'neutral'
        return dict(tone='neutral', closure_tone=tone)
    return dict(tone='warning' if record.section == 'Needs decision' or blocked else 'neutral',
                closure_tone='neutral')


def edit_lifecycle(state):
    """The meaning of a task-store result, independent of host controls or grants."""
    messages = {
        'clean': 'No saved task edits await a commit.',
        'pending_commit': 'Saved locally — pending commit. The runner reads committed records; commit these task edits before it can see the answer. No live authorization is granted.',
        'committed': 'Task edits committed locally. No push, runner start or live authorization.',
    }
    if state not in messages:
        raise ValueError('unknown task edit lifecycle')
    return dict(state=state, message=messages[state])
