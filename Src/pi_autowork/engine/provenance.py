"""Immutable, allowlisted evidence for one worker launch: what shaped this attempt.

A provenance record describes an execution; it never authorizes one. Admission,
authorization, dispatch policy, integration and closure never read it, so a recorded
profile cannot become an alternative grant. Every value is captured before the worker
starts and is never inferred afterwards: an unavailable value is stored as null with a
reason, not guessed later.

Only allowlisted identity fields and hashes are stored. The prompt is reduced to its
SHA-256 and byte length; no prompt text, environment dump, credential or token is kept.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

SCHEMA = 1
# Repository instruction files a worker host may read, in a stable order.
INSTRUCTION_FILES = ('AGENTS.md', 'CLAUDE.md')


def digest(data):
    return hashlib.sha256(data or b'').hexdigest()


def read_instruction(repo, rev, path):
    """The file's bytes at the pinned revision, or None when it is absent or unreadable."""
    if not rev:
        return None
    try:
        result = subprocess.run(['git', '-C', str(repo), 'show', f'{rev}:{path}'],
                                capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def instructions(repo, rev, paths=INSTRUCTION_FILES):
    """[(path, bytes or None)] as read at a Git revision; None means unavailable, not inferred."""
    return [(path, read_instruction(repo, rev, path)) for path in paths]


def instructions_from(root, paths=INSTRUCTION_FILES):
    """[(path, bytes or None)] as the worker's own worktree has them at capture time."""
    values = []
    for path in paths:
        try:
            source = Path(root, path)
            values.append((path, source.read_bytes() if source.is_file() else None))
        except OSError:
            values.append((path, None))
    return values


def manifest(*, task, attempt, contract_hash, record_revision, rev, host, model, toolset,
             prompt, instructions=(), ownership='worker', live='', live_actor=None,
             live_at=None, live_scope=(), attempt_id=None, worktree_revision=None, captured_at=None):
    """One record from values known before launch.

    ``authorization`` is descriptive: the attempt's declared ownership and live-grant
    identity. It is evidence of what the contract said, never a grant this file can supply.
    """
    prompt = bytes(prompt or b'')
    return dict(
        schema=SCHEMA,
        task=str(task),
        attempt=int(attempt),
        attempt_id=str(attempt_id) if attempt_id else None,
        captured_at=float(time.time() if captured_at is None else captured_at),
        contract_hash=contract_hash or None,
        record_revision=record_revision or None,
        rev=rev or None,
        worktree_revision=worktree_revision or None,
        toolset=toolset or None,
        host=host or None,
        model=model or None,
        prompt=dict(sha256=digest(prompt), bytes=len(prompt)),
        instructions=[dict(path=str(path),
                           sha256=digest(data) if data is not None else None,
                           state='present' if data is not None else 'unavailable')
                      for path, data in instructions],
        authorization=dict(ownership=str(ownership or 'unknown'),
                           live=str(live or ''),
                           live_actor=str(live_actor) if live_actor else None,
                           live_at=str(live_at) if live_at else None,
                           live_scope=[str(item) for item in (live_scope or ())]),
    )


def capture(path, record):
    """Append one immutable JSON line and fsync it. An earlier record is never rewritten."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = (json.dumps(record, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b'\n':
            data = b'\n' + data  # separate a torn earlier line instead of corrupting it
        os.fchmod(fd, 0o600)  # an existing looser-mode file is tightened too
        if os.write(fd, data) != len(data):
            raise OSError('short provenance write')
        os.fsync(fd)
    finally:
        os.close(fd)
    return record


def read(path):
    """Every complete record, oldest first. A missing file is empty; a torn last line is skipped."""
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with path.open('rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                break  # a crash cut the write; never treat a partial line as evidence
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(value, dict) and value.get('schema') == SCHEMA:
                records.append(value)
    return records
