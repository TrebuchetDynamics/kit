"""Post-closeout Docs Sync policy. No provider, task-state or Git mutations here."""
from dataclasses import asdict
import re
import subprocess
import posixpath
from urllib.parse import unquote

from .common import GIT, git, git_ok
from .engine.task_select import held_by
from .engine.parallel_plan import overlap

KIND = 'post-completion docs-sync'
FILE_REFERENCE = re.compile(r'(?:[\w%.+-]+/)*[\w%.+-]+\.(?:md|toml)')
EDITABLE = {'title', 'short', 'scope', 'body', 'depends_on'}
DERIVED = {'record_revision', 'contract_hash', 'receipt_valid', 'missing_fields'}


def protected_tasks(rows, source=None):
    """Retained/unlanded attempts are not pending prose, even without a live PID."""
    claimed = {task for task, record in source.tasks.items() if held_by(record)} if source else set()
    return claimed | {r['task'] for r in rows if r.get('task') and
            (r.get('worker_live') or r.get('state') not in ('closed', 'waiting')
             or r.get('root_kind') == 'claim'
             or (r.get('state') == 'waiting' and (r.get('commit') or r.get('worktree') or r.get('admitted_contract_hash'))))}


def landed_receipts(repo, source_rev, canonical_rev):
    """Bind completion to the actual receipt, not just identical close-record prose."""
    def blobs(revision):
        output = git(repo, 'ls-tree', '-r', '-z', revision, '--', 'tasks/evidence')
        if output is None:
            return {}
        return {entry.split('\t', 1)[1]: entry.split('\t', 1)[0].split()[2]
                for entry in output.split('\0') if entry}
    source, canonical = blobs(source_rev), blobs(canonical_rev)
    return {path: blob for path, blob in source.items() if canonical.get(path) == blob}


def triggers(rows, source, canonical, receipts):
    """Closed slots survive restart; only canonical, verified closures trigger a pass.

    Per-completion receipts live in the existing maintainer journal. A removed record
    needs no new run, and editing unrelated prose cannot replay a consumed completion.
    """
    found = []
    for row in rows:
        task = row.get('task')
        record, landed = source.tasks.get(task), canonical.tasks.get(task)
        if (row.get('state') != 'closed' or row.get('worker_live') or record is None
                or landed is None or not record.verified or not landed.verified
                or record.record_revision != landed.record_revision
                or record.closure_evidence not in receipts):
            continue
        identity = f'{row.get("attempt", 0)}:{record.contract_hash}:{receipts[record.closure_evidence]}'
        found.append((task, KIND, identity))
    return sorted(found)


def referenced_paths(text, consumer):
    """Accept root-relative prose paths and file-relative Markdown destinations."""
    found = set()
    for match in FILE_REFERENCE.finditer(unquote(text)):
        path = match[0]
        for candidate in (path, posixpath.join(posixpath.dirname(consumer), path)):
            normalized = posixpath.normpath(candidate)
            if not normalized.startswith(('../', '/')):
                found.add(normalized)
    return found


def plan_paths(store, protected):
    """Existing exact plan references only; shared plans of active tasks stay frozen."""
    allowed, frozen = set(), set()
    for task, record in store.tasks.items():
        goal = store.goals.get(record.goal)
        references = referenced_paths(str(asdict(record)), record.path)
        if goal:
            references |= referenced_paths(str(asdict(goal)), goal.path)
        paths = {p for p in references if p.startswith('docs/plans/') and p.endswith('.md')}
        if task in protected:
            frozen.update(paths)
        elif record.status == 'open':
            allowed.update(paths)
    scopes = [store.tasks[task].touches if task in store.tasks else () for task in protected]
    frozen.update(overlap(allowed, allowed, scopes)['conflicts'])
    return tuple(sorted(allowed - frozen))


def prompt(repo, tasks, found, protected, plans, revision):
    names = ', '.join(task for task, _, _ in found)
    return (
        f'You are the DOCS-MAINTAINER for {repo}. Run /skill:docs-sync in scoped Maintain mode '
        f'after these verified tasks closed and landed: {names}. This is post-completion maintenance, '
        'not another implementation or discovery round. Read the installed Docs Sync workflow and '
        'its shared completed-task retention, task-name and task-description rules. '
        'Prune eligible completed task records and their unneeded dedicated receipts; Git is the archive. '
        'Inspect every retained record for a current dependency, proof or ownership need. '
        'Improve pending task titles, short names, scope descriptions and Description/Notes/Sources body notes from current '
        'source and accepted intent; maintain the existing referenced plans listed below. '
        'Do not manufacture edits when wording is already clear. Preserve scope meaning, acceptance, '
        'checks, exclusions, priority, section, dependencies, goal status, ownership and live authority. '
        'The sole dependency exception is removing already-satisfied ordinary edges to done qualified '
        'records you delete. Never remove verified_depends_on, waive qualification, weaken a plan, '
        'invent approval, close/reopen/supersede work, create tasks or goals, or change runtime state. '
        'Never touch an active or retained/unlanded attempt or its shared plan. '
        f'Protected IDs at admission: {", ".join(sorted(protected)) or "none"}; recheck before editing. '
        'Unknown ownership means retain. Use ' + tasks + ' (show, field, delete) for records; delete '
        'only after safety checks, because delete warnings do not prevent unsafe removal. '
        'Receipts may only be deleted alongside their eligible task, never created or modified. '
        'Preserve remaining proof through reachable immutable Git references, for example '
        f'git show {revision}:tasks/items/ID.md. Retain a record if a typed gate or other consumer needs it. '
        'Do not replace removed records with completion lists/reports. Do not delete worktrees, '
        'runtime recovery files, shared specifications, accepted plan documents or frozen archives. '
        f'Exact editable existing plans: {", ".join(plans) or "none"}. '
        'No other document/product code path is authorized. Validate with ' + tasks +
        ' validate --worktree . and check surviving references. Commit the bounded changes once '
        'in this checkout; do not push, switch branches, dispatch workers or install/restart services. '
        'A no-change result is valid when nothing safe/useful remains. End with '
        'PI_AUTOWORK_RESULT: completed or PI_AUTOWORK_RESULT: blocked; give cleanup counts, '
        'changed pending IDs and concrete retention reasons, not a completed-task ledger.'
    )


def proposal_error(before, after, current, canonical, rows, paths, deleted_paths, plans):
    """Reject unsafe housekeeping before merge; prose instructions are not a guard."""
    protected = protected_tasks(rows, current)
    scopes = [current.tasks[task].touches if task in current.tasks else () for task in protected]
    if overlap(paths, paths, scopes)['conflicts']:
        return 'post-completion paths overlap an owned or unknown attempt scope'
    removed = set(before.tasks) - set(after.tasks)
    if set(after.tasks) - set(before.tasks):
        return 'post-completion maintenance cannot add tasks'
    if before.goals != after.goals or before.goals != current.goals:
        return 'post-completion maintenance must preserve goals and qualification gates'
    for task in removed:
        record, landed = before.tasks[task], canonical.tasks.get(task)
        if (record.status != 'done' or not record.qualified or landed is None
                or not landed.qualified or landed.record_revision != record.record_revision):
            return f'{task}: deletion requires qualified, canonically landed completion'
    for task, record in before.tasks.items():
        proposed = after.tasks.get(task)
        if proposed == record:
            continue
        live, landed = current.tasks.get(task), canonical.tasks.get(task)
        if (task in protected or live is None or live.record_revision != record.record_revision
                or landed is None or landed.record_revision != record.record_revision):
            return f'{task}: maintenance input changed or an attempt owns it'
        if proposed is None:
            continue
        if record.status != 'open':
            return f'{task}: retained closed records are immutable'
        # Body notes carry decisions and ownership too. Limit prose edits to explicit
        # descriptive labels; do not let a spelling pass erase Held by / Owner decision.
        def fixed_notes(body):
            return '\n'.join(line for line in body.splitlines()
                             if line.strip() and not re.match(r'^- (Description|Notes|Sources): ', line))
        if fixed_notes(record.body) != fixed_notes(proposed.body):
            return f'{task}: maintenance changed ownership, decisions or non-descriptive notes'
        old, new = asdict(record), asdict(proposed)
        if any(old[k] != new[k] for k in old if k not in EDITABLE | DERIVED):
            return f'{task}: maintenance changed acceptance, scheduling or authority'
        dropped = set(record.depends_on) - set(proposed.depends_on)
        if (set(proposed.depends_on) - set(record.depends_on) or not dropped <= removed
                or dropped & set(record.verified_depends_on)):
            return f'{task}: only satisfied ordinary dependencies of pruned tasks may be removed'
    # Never erase a typed verification obligation, including one on a closed consumer.
    effective = {**current.tasks, **{task: record for task, record in after.tasks.items()
                                    if before.tasks.get(task) != record}}
    for task in removed:
        effective.pop(task, None)
    if any(set(r.depends_on) & removed or set(r.verified_depends_on) & removed
           for r in effective.values()):
        return 'a surviving task still depends on a pruned record'
    allowed_plans = set(plans) & set(plan_paths(current, protected))
    records = {r.path for r in before.tasks.values()}
    receipts = {f'tasks/evidence/{task}.toml' for task in removed}
    reports = {f'docs/tasks/{task}{suffix}.md' for task in removed for suffix in ('', '-report', '-repair')}
    for path in paths:
        if path in records:
            continue
        if path in receipts | reports and path in deleted_paths:
            continue
        if path in allowed_plans and path not in deleted_paths:
            continue
        return 'post-completion maintenance changed an unauthorized path: ' + path
    return None


def reference_error(repo, deleted_paths, revision, *, ref='HEAD', exclude=()):
    """Do not remove evidence still referenced by a tracked consumer; immutable refs work."""
    paths = sorted(p for p in deleted_paths if p)
    if not paths:
        return None
    # Basenames are not a safe prefilter: Markdown can percent-encode every byte.
    # Inspect all textual path/encoded-destination consumers, then normalize them.
    argv = [*GIT, '-C', str(repo), 'grep', '-I', '-l', '-z', '-E',
            r'\.(md|toml)|%[0-9a-fA-F]{2}']
    found = subprocess.run([*argv, ref, '--', *(f':(literal,exclude){p}' for p in exclude)],
                           capture_output=True, text=True)
    if found.returncode not in (0, 1):
        return 'post-completion reference inspection failed'
    pattern = re.compile('|'.join(re.escape(p) for p in paths))
    immutable = re.compile(r'([a-f0-9]{40}(?:[a-f0-9]{24})?):(' + pattern.pattern + ')')
    checked = set()
    for item in found.stdout.split('\0'):
        if not item:
            continue
        consumer = item.removeprefix(ref + ':')
        content = git(repo, 'show', ref + ':' + consumer)
        if content is None:
            return 'post-completion consumer inspection failed: ' + consumer
        content = unquote(content)
        for match in immutable.finditer(content):
            evidence_ref, path = match.groups()
            if (evidence_ref, path) not in checked:
                if not (git_ok(repo, 'cat-file', '-e', evidence_ref + ':' + path)
                        and git_ok(repo, 'merge-base', '--is-ancestor', evidence_ref, revision)):
                    return 'post-completion immutable evidence is unavailable: ' + path
                checked.add((evidence_ref, path))
        remaining = immutable.sub('', content)
        referenced = set(paths) & referenced_paths(remaining, consumer)
        if referenced:
            return 'a tracked consumer still references pruned evidence: ' + sorted(referenced)[0]
    return None
