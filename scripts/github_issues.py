#!/usr/bin/env python3
"""Publish a complete planning batch to GitHub, then dispatch it to Orbi.

Input is transient JSON: {"issues": [{"key": "stable-key", "title": "...",
"outcome": "...", "scope": "...", "exclusions": "...", "acceptance": "...",
"verification": "...", "sources": "...", "blocked_by": ["other-key", 123],
"epic": "epic-key", "kind": "task", "ready": true}]}.
Integer dependencies are existing issue numbers in the target repository.
Run without --apply to validate locally without network or writes. One publisher
per batch; the GitHub create API does not provide atomic deduplication.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

FIELDS = ('outcome', 'scope', 'exclusions', 'acceptance', 'verification', 'sources')
OWNED = {'ai-in-progress', 'ai-pr-opened', 'ai-fix-needed', 'ai-awaiting-merge',
         'ai-merged', 'ai-blocked', 'ai-needs-detail', 'ai-paused'}
LABELS = {'ai-planning': 'Planning incomplete or explicitly undispatched',
          'ai-ready': 'Ready for Orbi delivery', 'ai-epic': 'Coordination only'}


class PublicationError(Exception):
    pass


class GitHub:
    def __init__(self, repo: str):
        self.root = f'repos/{repo}'

    def api(self, path: str, method: str = 'GET', data: Any = None,
            *, missing_ok: bool = False) -> Any:
        args = ['gh', 'api', f'{self.root}/{path}', '--method', method,
                '-H', 'Accept: application/vnd.github+json']
        if data is not None:
            args += ['--input', '-']
        result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                                text=True, capture_output=True, timeout=60)
        if result.returncode:
            try:
                status = str(json.loads(result.stdout).get('status', ''))
            except (ValueError, AttributeError):
                status = ''
            if missing_ok and method == 'GET' and status == '404':
                return None
            raise PublicationError(f'{method} {path}: {result.stderr.strip()}')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def pages(self, path: str) -> list[dict]:
        result = []
        separator = '&' if '?' in path else '?'
        page = 1
        while True:
            rows = self.api(f'{path}{separator}per_page=100&page={page}')
            result.extend(rows)
            if len(rows) < 100:
                return result
            page += 1


def marker(key: str) -> str:
    return f'<!-- kit-issue:{key} -->'


def validate(batch: Any) -> list[dict]:
    if not isinstance(batch, dict) or not isinstance(batch.get('issues'), list) or not batch['issues']:
        raise PublicationError('batch must contain a nonempty issues array')
    issues = batch['issues']
    by_key = {}
    for issue in issues:
        if not isinstance(issue, dict):
            raise PublicationError('each issue must be an object')
        unknown = set(issue) - {'key', 'title', *FIELDS, 'kind', 'ready',
                                'pending_reason', 'blocked_by', 'epic'}
        if unknown:
            raise PublicationError(f'unknown issue fields: {sorted(unknown)}')
        key = issue.get('key', '')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,119}', key):
            raise PublicationError('each issue needs a stable alphanumeric key')
        if key in by_key:
            raise PublicationError(f'duplicate key: {key}')
        by_key[key] = issue
        for field in ('title', *FIELDS):
            value = issue.get(field)
            if not isinstance(value, str) or not value.strip():
                raise PublicationError(f'{key}: missing {field}')
            if '<!-- kit-issue:' in value:
                raise PublicationError(f'{key}: reserved publication marker in {field}')
        if issue.get('kind', 'task') not in ('task', 'epic'):
            raise PublicationError(f'{key}: kind must be task or epic')
        if type(issue.get('ready', True)) is not bool:
            raise PublicationError(f'{key}: ready must be a boolean')
        if 'pending_reason' in issue and (not isinstance(issue['pending_reason'], str)
                                          or '<!-- kit-issue:' in issue['pending_reason']):
            raise PublicationError(f'{key}: pending_reason must be text without publication markers')
        if issue.get('ready') is False and not issue.get('pending_reason', '').strip():
            raise PublicationError(f'{key}: undispatched work needs pending_reason')
        deps = issue.get('blocked_by', [])
        if not isinstance(deps, list) or any(
            not (isinstance(d, str) or type(d) is int and d > 0) for d in deps
        ) or len(set(deps)) != len(deps):
            raise PublicationError(f'{key}: blocked_by must contain distinct keys or positive issue numbers')
    for key, issue in by_key.items():
        for dep in issue.get('blocked_by', []):
            if isinstance(dep, str):
                if dep not in by_key or dep == key:
                    raise PublicationError(f'{key}: unknown or self dependency {dep}')
                if by_key[dep].get('kind') == 'epic':
                    raise PublicationError(f'{key}: depend on executable children, not epic {dep}')
        epic = issue.get('epic')
        if epic is not None and (not isinstance(epic, str) or epic not in by_key
                                 or by_key[epic].get('kind') != 'epic' or epic == key):
            raise PublicationError(f'{key}: epic must name a coordination issue in this batch')
    visiting, visited = set(), set()

    def visit(key, hierarchy=False):
        if key in visiting:
            raise PublicationError(f'{"epic" if hierarchy else "dependency"} cycle at {key}')
        if key in visited:
            return
        visiting.add(key)
        deps = ([by_key[key]['epic']] if by_key[key].get('epic') else []) if hierarchy else by_key[key].get('blocked_by', [])
        for dep in deps:
            if isinstance(dep, str):
                visit(dep, hierarchy)
        visiting.remove(key)
        visited.add(key)

    for hierarchy in (False, True):
        visiting.clear()
        visited.clear()
        for key in by_key:
            visit(key, hierarchy)
    return issues


def body(issue: dict) -> str:
    parts = [marker(issue['key'])]
    if issue.get('epic'):
        # Retry provenance only; the native parent relationship remains authoritative.
        parts.append(f"<!-- kit-parent:{issue['epic']} -->")
    parts.extend(f'## {field.title()}\n\n{issue[field].strip()}' for field in FIELDS)
    if issue.get('pending_reason'):
        parts.append(f"## Pending\n\n{issue['pending_reason']}")
    return '\n\n'.join(parts) + '\n'


def labels(issue: dict) -> set[str]:
    return {label['name'] for label in issue.get('labels', [])}


def safe_existing(issue: dict) -> None:
    if 'pull_request' in issue or issue.get('state') != 'open' or labels(issue) & OWNED:
        raise PublicationError(f"#{issue['number']}: closed, owned or recovery work; reconcile manually")
    if not labels(issue) & {'ai-planning', 'ai-ready'}:
        raise PublicationError(f"#{issue['number']}: readiness withdrawn; reconcile manually")


def publish(api: GitHub, batch: Any) -> list[dict]:
    specs = validate(batch)
    # Read all states rather than GitHub search (index lag can duplicate a retry).
    existing = api.pages('issues?state=all')
    saved = {}
    for spec in specs:
        matches = [row for row in existing if marker(spec['key']) in (row.get('body') or '')]
        if len(matches) > 1:
            raise PublicationError(f"{spec['key']}: ambiguous existing issues")
        if matches:
            row = matches[0]
            safe_existing(row)
            if row['title'] != spec['title'] or row['body'] != body(spec):
                raise PublicationError(f"#{row['number']}: saved contract changed; reconcile manually")
            if (spec.get('kind') == 'epic') != ('ai-epic' in labels(row)):
                raise PublicationError(f"#{row['number']}: changed epic classification")
            if not spec.get('ready', True) and 'ai-ready' in labels(row):
                raise PublicationError(f"#{row['number']}: already dispatched; cannot make pending")
            saved[spec['key']] = row
    external = {}
    for spec in specs:
        for dep in spec.get('blocked_by', []):
            if type(dep) is int and dep not in external:
                row = api.api(f'issues/{dep}')
                if 'pull_request' in row:
                    raise PublicationError(f'#{dep}: a pull request is not an issue dependency')
                if row['state'] == 'open' and 'ai-epic' in labels(row):
                    raise PublicationError(f'#{dep}: depend on executable children, not an open epic')
                external[dep] = row
    known_labels = {row['name'] for row in api.pages('labels')}
    for name, description in LABELS.items():
        if name not in known_labels:
            api.api('labels', 'POST', {'name': name, 'color': 'bfdadc', 'description': description})
    for spec in specs:
        if spec['key'] not in saved:
            initial = ['ai-planning']
            if spec.get('kind') == 'epic':
                initial.append('ai-epic')
            saved[spec['key']] = api.api('issues', 'POST', {
                'title': spec['title'], 'body': body(spec), 'labels': initial})

    def expected_dependencies(spec):
        return {(external[d] if type(d) is int else saved[d])['id']
                for d in spec.get('blocked_by', [])}

    # Never modify the graph of an already-dispatched retry; only exact reuse.
    for spec in specs:
        row = api.api(f"issues/{saved[spec['key']]['number']}")
        safe_existing(row)
        wanted = expected_dependencies(spec)
        path = f"issues/{row['number']}/dependencies/blocked_by"
        actual = {dep['id'] for dep in api.pages(path)}
        if actual - wanted or ('ai-ready' in labels(row) and actual != wanted):
            raise PublicationError(f"#{row['number']}: dependency drift; reconcile manually")
        if row['id'] in wanted:
            raise PublicationError(f"#{row['number']}: self dependency")
        for dep_id in sorted(wanted - actual):
            api.api(path, 'POST', {'issue_id': dep_id})
    def parent_of(number):
        return api.api(f'issues/{number}/parent', missing_ok=True)

    # Native sub-issue links for epics; never reparent existing or owned work.
    for spec in specs:
        child = api.api(f"issues/{saved[spec['key']]['number']}")
        safe_existing(child)
        current_parent = parent_of(child['number'])
        parent = saved.get(spec.get('epic'))
        if current_parent and (not parent or current_parent['id'] != parent['id']):
            raise PublicationError(f"#{child['number']}: epic parent drift; reconcile manually")
        if parent and not current_parent:
            safe_existing(api.api(f"issues/{parent['number']}"))
            if 'ai-ready' in labels(child):
                raise PublicationError(f"#{child['number']}: dispatched issue missing epic link")
            api.api(f"issues/{parent['number']}/sub_issues", 'POST', {'sub_issue_id': child['id']})

    # Verify the entire batch before *any* readiness publication.
    for spec in specs:
        row = api.api(f"issues/{saved[spec['key']]['number']}")
        safe_existing(row)
        if row['body'] != body(spec) or row['title'] != spec['title']:
            raise PublicationError(f"#{row['number']}: contract changed during publication")
        if {dep['id'] for dep in api.pages(f"issues/{row['number']}/dependencies/blocked_by")} != expected_dependencies(spec):
            raise PublicationError(f"#{row['number']}: dependency readback failed")
        actual_parent = parent_of(row['number'])
        expected_parent = saved.get(spec.get('epic'))
        if (actual_parent or {}).get('id') != (expected_parent or {}).get('id'):
            raise PublicationError(f"#{row['number']}: epic readback failed")
    results = []
    for spec in specs:
        number = saved[spec['key']]['number']
        row = api.api(f'issues/{number}')
        safe_existing(row)
        if row['body'] != body(spec) or row['title'] != spec['title']:
            raise PublicationError(f"#{number}: contract changed before dispatch")
        if spec.get('kind') != 'epic' and spec.get('ready', True):
            if 'ai-ready' not in labels(row):
                api.api(f'issues/{number}/labels', 'POST', {'labels': ['ai-ready']})
            if 'ai-planning' in labels(row):
                api.api(f'issues/{number}/labels/ai-planning', 'DELETE')
        current = api.api(f'issues/{number}')
        results.append({'key': spec['key'], 'url': current['html_url'],
                        'state': current['state'], 'labels': sorted(labels(current))})
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--batch', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
            raise PublicationError('--repo must be OWNER/REPO')
        batch = json.loads(args.batch.read_text())
        specs = validate(batch)
        result = publish(GitHub(args.repo), batch) if args.apply else {
            'preview': True, 'remote_checked': False, 'repo': args.repo,
            'issues': [{'key': s['key'], 'title': s['title'], 'body': body(s),
                        'blocked_by': s.get('blocked_by', []),
                        'dispatch': s.get('kind') != 'epic' and s.get('ready', True)} for s in specs]}
        print(json.dumps(result, indent=2))
        return 0
    except (PublicationError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'Publication incomplete: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
