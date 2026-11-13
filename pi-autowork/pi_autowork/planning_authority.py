"""Machine-enforced planning write rules: paths, size, secrets and authority.

This module is the one home for the limits a planning proposal must satisfy before
it can be staged. The human planning policy lives in
``skills/shared/RESEARCH-PLAN.md`` and ``skills/shared/PLANNING-PROTOCOL.md``; this
module supplies the exact machine checks and the prompt block generated from them.
It deliberately does not parse task records. ``task_store.planner_authority`` owns
record schema and authority diffs.
"""
from pathlib import PurePosixPath
import re

MAX_FILE = 256 * 1024
MAX_TOTAL = 2 * 1024 * 1024
MAX_FILES = 64
TASK_PATH = re.compile(r'tasks/(?:items|goals)/[A-Za-z0-9][A-Za-z0-9_-]*\.md\Z')
DOC_ROOTS = (('docs', 'plans'), ('docs', 'specs'))
SECRET = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{12,}'
                    r'|\bBearer [A-Za-z0-9._~+/=-]{12,}'
                    r'|(?i:API_KEY|ACCESS_TOKEN|PASSWORD|CLIENT_SECRET)\s*[=:]\s*["\']?[^\s"\']{8,}')


class PlanningAuthorityError(ValueError):
    """A planning proposal refused by a machine-enforced rule."""


def path_allowed(name: str) -> PurePosixPath:
    """Return the normalized path, or refuse a path outside the planning allowlist."""
    if not isinstance(name, str) or len(name) > 240:
        raise PlanningAuthorityError('invalid planning path')
    parts = name.split('/')
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', part) or part in ('.', '..')
           for part in parts):
        raise PlanningAuthorityError('unsafe planning path: ' + name)
    if any(re.search(r'(?i)credential|secret|evidence|^\.git$', part) for part in parts):
        raise PlanningAuthorityError('sensitive planning path refused: ' + name)
    doc = len(parts) >= 3 and tuple(parts[:2]) in DOC_ROOTS and name.endswith('.md')
    if not TASK_PATH.fullmatch(name) and not doc:
        raise PlanningAuthorityError('path outside planning allowlist: ' + name)
    return PurePosixPath(name)


def check_files(files: dict[str, str]) -> None:
    """Refuse an empty, oversized or secret-bearing proposal before any write."""
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES:
        raise PlanningAuthorityError(f'proposal must contain 1-{MAX_FILES} complete files')
    total = 0
    for name, content in files.items():
        path_allowed(name)
        if not isinstance(content, str) or '\x00' in content:
            raise PlanningAuthorityError('planning files must contain UTF-8 text')
        size = len(content.encode('utf-8'))
        total += size
        if size > MAX_FILE or total > MAX_TOTAL:
            raise PlanningAuthorityError('proposal exceeds size budget')
        if SECRET.search(content):
            raise PlanningAuthorityError('credential-like content refused in proposal')


def policy_text() -> str:
    """The machine limits injected into the planning prompt, generated once."""
    return (
        'Machine-enforced planning rules:\n'
        '- Allowed output: tasks/items/<ID>.md, tasks/goals/<ID>.md, '
        'docs/plans/**/*.md and docs/specs/**/*.md.\n'
        '- No deletions, credentials, evidence, symlinks or executable files.\n'
        '- Preserve closure, owner attestations, holds and live permissions.\n'
        '- New live obligations require explicit live = "denied" and ownership = "owner"; '
        'include no live grant fields. Existing live resource gates stay unchanged.\n'
        '- Use schema-1 TOML task records (read the bundled pi-autowork/task-store.md).\n'
        f'- At most {MAX_FILES} files, {MAX_FILE // 1024} KiB per file, '
        f'{MAX_TOTAL // (1024 * 1024)} MiB total.\n'
    )
