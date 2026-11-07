"""Pure display vocabulary shared by committed snapshots and the CLI display."""
import re
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


def closure_display(info):
    """A closed task's words: the stored label, its provenance detail and the effective proof."""
    provenance = info.get('provenance') or 'unknown'
    verified = info.get('verified')
    proof = 'verified' if verified is True else 'not verified' if verified is False else 'verification unknown'
    return {'label': info.get('label') or 'Unknown closure',
            'detail': f'{str(provenance).replace("_", " ")} · {proof}',
            'verified': verified, 'provenance': info.get('provenance')}


def blocker_words(code):
    """The human word for a blocker code: a known cause, a humanised code, or a task ID."""
    text = str(code or '')
    if text in CAUSES:
        return CAUSES[text]
    if re.match(r'^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$', text):
        return text.replace('_', ' ').lower()
    return text
