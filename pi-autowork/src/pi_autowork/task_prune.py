"""`autowork tasks prune [repo] [--plan | --apply]`: completed-task retention as one command.

The published retention rules (skills/shared/TODO-WORKCENTER.md, "Completed-task
retention"; skills/docs-sync/references/pruning.md) as a decision table, so no pass
re-derives them by hand. Only finished records (`done`, `superseded`) are candidates.
The first matching row decides; every retained record carries that row's code:

| Code | A finished record is retained while |
| --- | --- |
| OWNERSHIP_UNKNOWN | worker slots or a lease cannot be read: nothing is pruned |
| RUNTIME_SLOT | a worker slot with unfinished work or a live lease holds it |
| UNCOMMITTED | its record differs from HEAD: closure is not integrated yet |
| NEEDS_DECISION | it still sits in `Needs decision` |
| UNVERIFIED_CLOSURE | it claims a verified close whose receipt is missing or invalid |
| GOAL_PROOF | a goal record cites it |
| CITED_BY_OPEN_TASK | an open task's notes cite it |
| CURRENT_DOC | a tracked Markdown document that is not frozen history cites it |
| VERIFIED_DEPENDENCY | a surviving task names it in `verified_depends_on` |
| SUPERSEDED_DEPENDENCY | an open task depends on it and it is superseded: repoint that task first |
| DEPENDENT_IN_FLIGHT | an open task depends on it and an attempt holds that task's contract |
| RETAINED_DEPENDENT | a retained finished record depends on it; its contract is not rewritten |

A frozen archive (`TODO.archive.md`, `docs/TODO-archive.md`, a `doc-ref-guard: record`
document) never blocks: it is history. A `done` record an inactive open task names only in
`depends_on` is deleted and that satisfied edge is removed in the same transaction.

`--plan` (the default) reads the working tree and writes nothing. `--apply` recomputes the
plan under the task lock, refuses when `--expect-plan` names another plan, then deletes
and edits in one validated, recoverable set. Like every task write it changes the working
tree only (`autowork tasks commit` lands it). Receipts under tasks/evidence/ are listed,
never removed; goals, worktrees and runtime state are untouched.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from pi_autowork import task_commands
from pi_autowork.engine import task_store
from pi_autowork.engine.task_store import TaskStore

TERMINAL = ('done', 'superseded')
FROZEN_NAME = re.compile(r'(?i)(?:^|/)todo[._-]archive\.(?:md|markdown)$')
RECORD_MARK = b'doc-ref-guard: record'
_WORD = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*')


def frozen(repo, path, cache=None):
    """Whether a tracked document is frozen history: an archive by name, or one that
    declares `doc-ref-guard: record` in its first 4 kB."""
    cache = {} if cache is None else cache
    if path not in cache:
        found = bool(FROZEN_NAME.search(path))
        if not found:
            try:
                with open(Path(repo) / path, 'rb') as handle:
                    found = RECORD_MARK in handle.read(4096)
            except OSError:
                found = False
        cache[path] = found
    return cache[path]


def _cited(text, ids):
    return ids & set(_WORD.findall(text))


def _document_citations(repo, ids):
    """{ID: 'path:line'} for the first current (not frozen) tracked Markdown line citing it."""
    if not ids:
        return {}
    result = subprocess.run(
        ['git', '-C', str(repo), 'grep', '--no-color', '-n', '-I', '-w', '-F', '-f', '-', '--',
         '*.md', '*.markdown', ':(exclude)tasks/'],
        input='\n'.join(sorted(ids)), capture_output=True, text=True, timeout=120)
    if result.returncode not in (0, 1):
        raise task_commands.CommandError(f'git grep failed: {result.stderr.strip()}')
    found, cache = {}, {}
    for line in result.stdout.splitlines():
        path, _, rest = line.partition(':')
        number, _, text = rest.partition(':')
        hits = _cited(text, ids) - set(found)
        if hits and not frozen(repo, path, cache):
            for tid in hits:
                found[tid] = f'{path}:{number}'
    return found


def plan(repo):
    """The retention decision for every finished record of the working-tree store."""
    store = task_commands.worktree_store(repo)
    tasks = store.tasks
    finished = {t.id for t in tasks.values() if t.status in TERMINAL}
    pending = set(TaskStore.pending(repo))
    held, problems = task_commands.in_flight_facts(repo, report_live_leases=False)
    retain = {}

    def keep(tid, code, detail):
        retain.setdefault(tid, dict(id=tid, status=tasks[tid].status, reason=code, detail=detail))

    goal_cites, task_cites = {}, {}
    for goal in store.goals.values():
        for tid in _cited(f'{goal.source}\n{goal.body}', finished):
            goal_cites.setdefault(tid, goal.id)
    for t in tasks.values():
        if t.status == 'open':
            for tid in _cited(t.body or '', finished - {t.id}):
                task_cites.setdefault(tid, t.id)
    doc_cites = _document_citations(repo, finished)
    for tid in sorted(finished):
        t = tasks[tid]
        if problems:
            keep(tid, 'OWNERSHIP_UNKNOWN', '; '.join(problems))
        elif tid in held:
            keep(tid, 'RUNTIME_SLOT', task_commands.holder_text(held[tid]))
        elif t.path in pending:
            keep(tid, 'UNCOMMITTED', f'{t.path} differs from HEAD; commit its closure first')
        elif t.section == 'Needs decision':
            keep(tid, 'NEEDS_DECISION', 'still in Needs decision; place or answer it first')
        elif t.status == 'done' and t.closure == 'coordinator_verified' and not t.receipt_valid:
            keep(tid, 'UNVERIFIED_CLOSURE', 'verified close without a valid receipt')
        elif tid in goal_cites:
            keep(tid, 'GOAL_PROOF', f'goal {goal_cites[tid]} cites it')
        elif tid in task_cites:
            keep(tid, 'CITED_BY_OPEN_TASK', f'notes of {task_cites[tid]} cite it')
        elif tid in doc_cites:
            keep(tid, 'CURRENT_DOC', f'{doc_cites[tid]} cites it')
    # Typed dependents: a retained record can pin its own dependencies, so repeat until stable.
    changed = True
    while changed:
        changed = False
        for user in sorted(tasks.values(), key=lambda t: t.id):
            surviving_open = user.status == 'open'
            if not surviving_open and user.id not in retain:
                continue  # a finished record that is itself deleted pins nothing
            for dep in sorted({*user.depends_on, *user.verified_depends_on} & (finished - set(retain))):
                if dep == user.id:
                    continue
                if dep in user.verified_depends_on:
                    keep(dep, 'VERIFIED_DEPENDENCY', f'{user.id} names it in verified_depends_on')
                elif not surviving_open:
                    keep(dep, 'RETAINED_DEPENDENT', f'retained record {user.id} depends on it')
                elif tasks[dep].status == 'superseded':
                    keep(dep, 'SUPERSEDED_DEPENDENCY',
                         f'{user.id} depends on it; repoint {user.id} to its successor first')
                elif user.id in held:
                    keep(dep, 'DEPENDENT_IN_FLIGHT',
                         f'{user.id} depends on it and is held ({task_commands.holder_text(held[user.id])})')
                else:
                    continue
                changed = True
    delete = sorted(finished - set(retain))
    gone = set(delete)
    edges = [dict(task=t.id, removes=[d for d in t.depends_on if d in gone],
                  depends_on=[d for d in t.depends_on if d not in gone])
             for t in sorted(tasks.values(), key=lambda t: t.id)
             if t.status == 'open' and gone & set(t.depends_on)]
    receipts = sorted(path for path in (f'tasks/evidence/{tid}.toml' for tid in delete)
                      if (Path(repo) / path).exists())
    reasons = {}
    for item in retain.values():
        reasons[item['reason']] = reasons.get(item['reason'], 0) + 1
    revision = hashlib.sha256(json.dumps(
        [[(tid, tasks[tid].record_revision) for tid in delete],
         [(e['task'], tasks[e['task']].record_revision, e['removes']) for e in edges]]).encode()).hexdigest()
    return dict(read='worktree', finished=len(finished),
                counts=dict(delete=len(delete), retain=len(retain), edges_removed=sum(len(e['removes']) for e in edges),
                            receipts_left=len(receipts)),
                retained_by_reason=dict(sorted(reasons.items())), delete=delete,
                retain=sorted(retain.values(), key=lambda item: (item['reason'], item['id'])),
                edges=edges, receipts_left=receipts, plan_revision=revision)


@task_commands._serialized
def cmd_prune(repo, apply=False, expect=None, summary=False):
    """The plan, applied when asked. One reason per retained record; counts either way."""
    report = plan(repo)
    report['applied'] = False
    if expect and not apply:
        raise task_commands.CommandError('--expect-plan needs --apply')
    if apply:
        if expect and expect != report['plan_revision']:
            raise task_commands.CommandError(
                f"the plan changed since {expect[:12]} was printed (now {report['plan_revision'][:12]}); "
                'read --plan again; nothing written')
        edits = []
        for tid in report['delete']:
            path = task_commands._path(repo, tid)
            edits.append((path, path.read_bytes(), None))
        for edge in report['edges']:
            path = task_commands._path(repo, edge['task'])
            before = path.read_bytes()
            edits.append((path, before, task_store.edit(before.decode(), {'depends_on': edge['depends_on']})))
        if edits:
            task_commands._write_many(repo, edits)
        report['applied'] = True
        report['next'] = ('review `git diff -- tasks`, then `autowork tasks commit`; receipts_left are '
                          'untouched: remove one only after its consumers are reconciled'
                          if edits else 'nothing was eligible; the store is unchanged')
    else:
        report['next'] = (f"autowork tasks prune --apply --expect-plan {report['plan_revision']}"
                          if report['delete'] else 'nothing is eligible; the store is unchanged')
    if summary:
        for key in ('delete', 'retain', 'edges', 'receipts_left'):
            report.pop(key)
    return report
