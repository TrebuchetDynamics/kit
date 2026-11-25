"""Offline publication, retry and default-dispatch contracts; no live qualification."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('github_issues', ROOT / 'scripts/github_issues.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def task(key, **extra):
    return dict(key=key, title=f'Implement {key}', outcome='Observable result',
                scope='src/cache.py and tests/test_cache.py', exclusions='No API changes',
                acceptance='Eviction test passes', verification='python -m unittest tests.test_cache',
                sources='https://github.com/example/repo/blob/abcdef/spec.md', **extra)


class FakeGitHub:
    def __init__(self):
        self.issues = {}
        self.dependencies = {}
        self.children = {}
        self.label_names = set()
        self.events = []
        self.fail_edge = False
        self.fail_ready = False
        self.ready_timeout = None  # (issue number, accepted before timeout)
        self.create_timeout = None
        self.readback_fails = False
        self.failed = False

    def pages(self, path):
        if path == 'issues?state=all':
            return copy.deepcopy(list(self.issues.values()))
        if path == 'labels':
            return [{'name': name} for name in self.label_names]
        number = int(path.split('/')[1])
        if path.endswith('/dependencies/blocked_by'):
            return [{'id': item} for item in self.dependencies.get(number, set())]
        if path.endswith('/sub_issues'):
            return [{'id': item} for item in self.children.get(number, set())]
        raise AssertionError(path)

    def api(self, path, method='GET', data=None, *, missing_ok=False):
        self.events.append((method, path, copy.deepcopy(data)))
        if path == 'labels':
            self.label_names.add(data['name'])
            return data
        if path.startswith('issues?state=all&'):
            if self.failed and self.readback_fails:
                raise publisher.PublicationError('injected recovery read failure')
            return copy.deepcopy(list(self.issues.values()))
        if path == 'issues':
            number = len(self.issues) + 1
            if self.create_timeout == (number, False):
                self.failed = True
                raise subprocess.TimeoutExpired('gh api', 60)
            self.issues[number] = dict(number=number, id=1000 + number, state='open',
                                       html_url=f'https://github.com/example/repo/issues/{number}',
                                       title=data['title'], body=data['body'],
                                       labels=[{'name': label} for label in data['labels']])
            if self.create_timeout == (number, True):
                self.failed = True
                raise subprocess.TimeoutExpired('gh api', 60)
            return copy.deepcopy(self.issues[number])
        number = int(path.split('/')[1])
        issue = self.issues[number]
        if method == 'GET':
            if self.failed and self.readback_fails:
                raise publisher.PublicationError('injected recovery read failure')
            if path.endswith('/parent'):
                parents = [n for n, children in self.children.items() if issue['id'] in children]
                return copy.deepcopy(self.issues[parents[0]]) if parents else None
            return copy.deepcopy(issue)
        if path.endswith('/dependencies/blocked_by'):
            if self.fail_edge:
                raise publisher.PublicationError('injected edge failure')
            self.dependencies.setdefault(number, set()).add(data['issue_id'])
        elif path.endswith('/sub_issues'):
            self.children.setdefault(number, set()).add(data['sub_issue_id'])
        elif path.endswith('/labels'):
            if self.ready_timeout == (number, False):
                self.failed = True
                raise subprocess.TimeoutExpired('gh api', 60)
            if self.fail_ready and 'ai-ready' in data['labels']:
                raise publisher.PublicationError('injected readiness failure')
            for label in data['labels']:
                if label not in publisher.labels(issue):
                    issue['labels'].append({'name': label})
            if self.ready_timeout == (number, True):
                self.failed = True
                raise subprocess.TimeoutExpired('gh api', 60)
        elif method == 'DELETE' and path.endswith('/labels/ai-planning'):
            issue['labels'] = [label for label in issue['labels'] if label['name'] != 'ai-planning']
        else:
            raise AssertionError((path, method, data))
        return copy.deepcopy(issue)


class PublicationTests(unittest.TestCase):
    def apply_cli(self, api, batch):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'batch.json'
            path.write_text(json.dumps(batch))
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(publisher, 'GitHub', return_value=api), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                status = publisher.main(['--repo', 'example/repo', '--batch', str(path), '--apply'])
        return status, stdout.getvalue(), stderr.getvalue()

    def partial_receipt(self, stderr):
        diagnostic, receipt = stderr.split('\n', 1)
        self.assertTrue(diagnostic.startswith('Publication incomplete: '))
        result = json.loads(receipt)
        self.assertTrue(result['partial'])
        return {row['key']: row for row in result['issues']}

    def test_cli_interrupted_create_reports_in_memory_receipt(self):
        api = FakeGitHub()
        api.label_names.update(publisher.LABELS)
        original = api.api

        def interrupt(path, method='GET', data=None, **kwargs):
            result = original(path, method, data, **kwargs)
            if (method, path) == ('POST', 'issues') and result['number'] == 2:
                raise KeyboardInterrupt
            return result

        api.api = interrupt
        status, stdout, stderr = self.apply_cli(api, {'issues': [task('a'), task('b')]})
        self.assertEqual((status, stdout), (130, ''))
        self.assertEqual(len(stderr.splitlines()), 2)
        self.assertEqual(stderr.splitlines()[0], 'Publication incomplete: interrupted')
        rows = self.partial_receipt(stderr)
        self.assertEqual(rows['a']['creation'], 'saved')
        self.assertEqual(rows['a']['url'], api.issues[1]['html_url'])
        self.assertEqual(rows['b']['creation'], 'unknown')
        self.assertTrue(rows['b']['unverified_write'])
        self.assertEqual(rows['b']['attempted_phase'], 'create')
        self.assertIsNone(rows['b']['number'])
        self.assertEqual([event[:2] for event in api.events], [('POST', 'issues')] * 2)

    def test_cli_interrupted_ready_post_reports_unknown_readiness(self):
        api = FakeGitHub()
        api.label_names.update(publisher.LABELS)
        original = api.api

        def interrupt(path, method='GET', data=None, **kwargs):
            result = original(path, method, data, **kwargs)
            if (method, path) == ('POST', 'issues/1/labels'):
                raise KeyboardInterrupt
            return result

        api.api = interrupt
        status, stdout, stderr = self.apply_cli(api, {'issues': [task('a')]})
        self.assertEqual((status, stdout), (130, ''))
        self.assertEqual(publisher.labels(api.issues[1]), {'ai-planning', 'ai-ready'})
        row = self.partial_receipt(stderr)['a']
        self.assertEqual(row['creation'], 'saved')
        self.assertEqual(row['attempted_phase'], 'ready_post')
        self.assertEqual(row['last_verified']['labels'], ['ai-planning'])
        self.assertEqual(row['readiness'], 'unknown')
        self.assertTrue(row['unverified_write'])
        self.assertEqual(api.events[-1][:2], ('POST', 'issues/1/labels'))

    def test_cli_malformed_create_payload_reports_in_memory_receipt(self):
        api = FakeGitHub()
        api.label_names.update(publisher.LABELS)
        original = api.api

        def malformed(path, method='GET', data=None, **kwargs):
            result = original(path, method, data, **kwargs)
            if (method, path) == ('POST', 'issues') and result['number'] == 2:
                return dict(result, labels=None)  # observe raises TypeError
            return result

        api.api = malformed
        status, stdout, stderr = self.apply_cli(api, {'issues': [task('a'), task('b')]})
        self.assertEqual((status, stdout), (1, ''))
        self.assertEqual(len(stderr.splitlines()), 2)
        self.assertIn('NoneType', stderr.splitlines()[0])
        rows = self.partial_receipt(stderr)
        self.assertEqual(rows['a']['creation'], 'saved')
        self.assertEqual(rows['b']['creation'], 'unknown')
        self.assertTrue(rows['b']['unverified_write'])
        self.assertEqual([event[:2] for event in api.events], [('POST', 'issues')] * 2)

    def test_cli_ready_timeout_preserves_verified_saved_and_unknown_results(self):
        for accepted in (False, True):
            for readback_fails in (False, True):
                with self.subTest(accepted=accepted, readback_fails=readback_fails):
                    api = FakeGitHub()
                    api.ready_timeout = (2, accepted)
                    api.readback_fails = readback_fails
                    batch = {'issues': [task('a'), task('b'), task('c')]}
                    status, stdout, stderr = self.apply_cli(api, batch)
                    self.assertEqual((status, stdout), (1, ''))
                    self.assertIn('timed out', stderr.splitlines()[0])
                    rows = self.partial_receipt(stderr)
                    a, b, c = (rows[key] for key in ('a', 'b', 'c'))
                    self.assertEqual(a['url'], api.issues[1]['html_url'])
                    self.assertEqual(a['last_verified'], {'state': 'open', 'labels': ['ai-ready']})
                    self.assertEqual(a['attempted_phase'], 'complete')
                    self.assertEqual(a['readiness'], 'ready')
                    self.assertEqual(b['creation'], 'saved')
                    self.assertEqual(b['number'], 2)
                    self.assertEqual(b['url'], api.issues[2]['html_url'])
                    self.assertEqual(b['attempted_phase'], 'ready_post')
                    expected = ['ai-planning', 'ai-ready'] if accepted else ['ai-planning']
                    self.assertEqual(sorted(publisher.labels(api.issues[2])), expected)
                    self.assertEqual(b['last_verified']['labels'], ['ai-planning'] if readback_fails else expected)
                    self.assertEqual(b['readiness'], 'unknown' if readback_fails else
                                     'ready' if accepted else 'not_ready')
                    self.assertEqual(b['unverified_write'], readback_fails)
                    if readback_fails:
                        self.assertIn('injected recovery read failure', b['reconciliation_error'])
                    self.assertEqual(c['creation'], 'saved')
                    self.assertEqual(c['url'], api.issues[3]['html_url'])
                    self.assertEqual(c['attempted_phase'], 'verify_batch')
                    self.assertEqual(c['last_verified']['labels'], ['ai-planning'])
                    failed = next(i for i, event in enumerate(api.events)
                                  if event[:2] == ('POST', 'issues/2/labels'))
                    self.assertEqual(api.events[failed + 1:], [('GET', 'issues/2', None)])
                    self.assertEqual(sum(event[:2] == ('POST', 'issues/2/labels')
                                         for event in api.events), 1)
                    # Deliberate stable-key retry reuses issues; no duplicate creates.
                    api.ready_timeout = None
                    api.readback_fails = False
                    status, stdout, stderr = self.apply_cli(api, batch)
                    self.assertEqual((status, stderr), (0, ''))
                    self.assertEqual([row['labels'] for row in json.loads(stdout)], [['ai-ready']] * 3)
                    self.assertEqual(len(api.issues), 3)

    def test_cli_ambiguous_create_is_not_reported_as_never_attempted(self):
        for accepted in (False, True):
            with self.subTest(accepted=accepted):
                api = FakeGitHub()
                api.create_timeout = (2, accepted)
                status, stdout, stderr = self.apply_cli(
                    api, {'issues': [task('a'), task('b'), task('c')]})
                self.assertEqual((status, stdout), (1, ''))
                rows = self.partial_receipt(stderr)
                self.assertEqual(rows['a']['creation'], 'saved')
                self.assertEqual(rows['b']['attempted_phase'], 'create')
                self.assertEqual(rows['b']['creation'], 'saved' if accepted else 'unknown')
                self.assertEqual(rows['b']['unverified_write'], not accepted)
                self.assertEqual(rows['b']['url'], api.issues[2]['html_url'] if accepted else None)
                self.assertEqual(rows['c']['creation'], 'not_attempted')
                self.assertIsNone(rows['c']['last_verified'])
                self.assertIsNone(rows['c']['url'])
                failed = next(i for i, event in enumerate(api.events)
                              if event[0] == 'POST' and event[1] == 'issues'
                              and publisher.marker('b') in event[2]['body'])
                self.assertTrue(all(method == 'GET' for method, _, _ in api.events[failed + 1:]))
                self.assertEqual(sum(method == 'POST' and path == 'issues'
                                     for method, path, _ in api.events), 2)

    def test_cli_create_recovery_failures_remain_unknown_and_bounded(self):
        for recovery in ('read failure', 'duplicate markers', 'page limit'):
            with self.subTest(recovery=recovery):
                api = FakeGitHub()
                api.create_timeout = (1, True)
                api.readback_fails = recovery == 'read failure'
                original = api.api

                def recover(path, method='GET', data=None, **kwargs):
                    result = original(path, method, data, **kwargs)
                    if path.startswith('issues?state=all&'):
                        if recovery == 'duplicate markers':
                            return result * 2
                        if recovery == 'page limit':
                            return [dict(result[0], body='unrelated')] * 100
                    return result

                api.api = recover
                status, stdout, stderr = self.apply_cli(
                    api, {'issues': [task('a'), task('b')]})
                self.assertEqual((status, stdout), (1, ''))
                rows = self.partial_receipt(stderr)
                self.assertEqual(rows['a']['creation'], 'unknown')
                self.assertTrue(rows['a']['unverified_write'])
                self.assertEqual(rows['a']['readiness'], 'unknown')
                self.assertIsNone(rows['a']['url'])
                self.assertIn('reconciliation_error', rows['a'])
                self.assertEqual(rows['b']['creation'], 'not_attempted')
                self.assertEqual(len(api.issues), 1)  # accepted remotely, not proven by readback
                reads = [event for event in api.events if event[1].startswith('issues?state=all&')]
                self.assertEqual(len(reads), 10 if recovery == 'page limit' else 1)
                failed = next(i for i, event in enumerate(api.events) if event[:2] == ('POST', 'issues'))
                self.assertTrue(all(event[0] == 'GET' for event in api.events[failed + 1:]))

    def test_cli_foreign_owned_or_paused_state_is_observed_without_repair(self):
        for hold in ('ai-in-progress', 'ai-paused'):
            with self.subTest(hold=hold):
                api = FakeGitHub()
                original = api.api
                foreign = {}

                def claim(path, method='GET', data=None, **kwargs):
                    result = original(path, method, data, **kwargs)
                    if (method, path) == ('POST', 'issues/1/labels'):
                        api.issues[2]['labels'].append({'name': hold})
                        api.issues[2]['body'] += '\nForeign decision'
                        foreign.update(copy.deepcopy(api.issues[2]))
                    return result

                api.api = claim
                status, stdout, stderr = self.apply_cli(
                    api, {'issues': [task('a'), task('b'), task('c')]})
                self.assertEqual((status, stdout), (1, ''))
                self.assertIn('#2: closed, owned or recovery work', stderr.splitlines()[0])
                rows = self.partial_receipt(stderr)
                self.assertEqual(rows['b']['last_verified']['labels'], sorted(['ai-planning', hold]))
                self.assertEqual(rows['b']['creation'], 'saved')
                self.assertEqual(api.issues[2], foreign)
                self.assertEqual(publisher.labels(api.issues[3]), {'ai-planning'})
                self.assertFalse(any(method != 'GET' and path.startswith(('issues/2/', 'issues/3/'))
                                     for method, path, _ in api.events))

    def test_complete_graph_precedes_readiness_and_retry_is_idempotent(self):
        api = FakeGitHub()
        batch = {'issues': [task('epic', kind='epic'), task('base', epic='epic'),
                            task('consumer', blocked_by=['base'], epic='epic'),
                            task('proposal', ready=False, pending_reason='Need product intent')]}
        result = publisher.publish(api, batch)
        self.assertEqual(len(result), 4)
        self.assertNotIn('ai-ready', publisher.labels(api.issues[1]))
        self.assertNotIn('ai-ready', publisher.labels(api.issues[4]))
        self.assertEqual(api.dependencies[3], {1002})  # ID, not number
        self.assertEqual(api.children[1], {1002, 1003})
        first_ready = next(i for i, (_, path, data) in enumerate(api.events)
                           if path.endswith('/labels') and data == {'labels': ['ai-ready']})
        mutations = [(i, event) for i, event in enumerate(api.events)
                     if event[0] == 'POST' and not event[1].endswith('/labels')]
        self.assertTrue(all(i < first_ready for i, _ in mutations))
        # At least one full dependency readback is done in publish before this phase.
        before = copy.deepcopy(api.issues)
        publisher.publish(api, batch)
        self.assertEqual(api.issues, before)
        self.assertEqual(sum(path == 'issues' and method == 'POST'
                             for method, path, _ in api.events), 4)

    def test_edge_failure_never_dispatches_and_retry_reuses_partial_batch(self):
        api = FakeGitHub()
        batch = {'issues': [task('base'), task('consumer', blocked_by=['base'])]}
        api.fail_edge = True
        with self.assertRaisesRegex(publisher.PublicationError, 'edge failure'):
            publisher.publish(api, batch)
        self.assertEqual(len(api.issues), 2)
        self.assertTrue(all(publisher.labels(row) == {'ai-planning'} for row in api.issues.values()))
        api.fail_edge = False
        publisher.publish(api, batch)
        self.assertEqual(len(api.issues), 2)
        self.assertTrue(all(publisher.labels(row) == {'ai-ready'} for row in api.issues.values()))

    def test_ready_failure_keeps_complete_graph_and_can_retry(self):
        api = FakeGitHub()
        batch = {'issues': [task('a'), task('b', blocked_by=['a'])]}
        api.fail_ready = True
        with self.assertRaises(publisher.PublicationError):
            publisher.publish(api, batch)
        self.assertEqual(api.dependencies[2], {1001})
        api.fail_ready = False
        publisher.publish(api, batch)
        self.assertEqual(len(api.issues), 2)

    def test_cli_retry_after_a_dispatched_issue_becomes_owned_or_closed(self):
        for change in ('owned', 'closed', 'owned with edited body'):
            with self.subTest(change=change):
                api = FakeGitHub()
                batch = {'issues': [task('a'), task('b', blocked_by=['a'])]}
                api.ready_timeout = (2, False)
                status, stdout, stderr = self.apply_cli(api, batch)
                self.assertEqual((status, stdout), (1, ''))
                self.assertIn('timed out', stderr.splitlines()[0])
                rows = self.partial_receipt(stderr)
                self.assertEqual(rows['b']['attempted_phase'], 'ready_post')
                self.assertEqual(rows['b']['last_verified']['labels'], ['ai-planning'])
                self.assertEqual(publisher.labels(api.issues[1]), {'ai-ready'})
                self.assertEqual(api.dependencies[2], {1001})

                a = api.issues[1]
                if change == 'closed':
                    a.update(state='closed', labels=[])
                else:
                    a['labels'] = [{'name': 'ai-in-progress'}]
                if change == 'owned with edited body':
                    a['body'] += '\nNew human decision'
                before = copy.deepcopy(a)
                api.ready_timeout = None
                api.events.clear()

                status, stdout, stderr = self.apply_cli(api, batch)
                writes = [event for event in api.events if event[0] != 'GET']
                self.assertEqual(api.issues[1], before)
                self.assertEqual(api.dependencies[2], {1001})
                if change == 'owned with edited body':
                    self.assertEqual((status, stdout), (1, ''))
                    self.assertEqual(stderr.splitlines()[0],
                                     'Publication incomplete: #1: saved contract changed; reconcile manually')
                    self.assertEqual(publisher.labels(api.issues[2]), {'ai-planning'})
                    self.assertEqual(writes, [])
                else:
                    self.assertEqual((status, stderr), (0, ''))
                    self.assertEqual(json.loads(stdout), [
                        {'key': 'a', 'url': a['html_url'], 'state': before['state'],
                         'labels': sorted(publisher.labels(before))},
                        {'key': 'b', 'url': api.issues[2]['html_url'], 'state': 'open',
                         'labels': ['ai-ready']},
                    ])
                    self.assertEqual(publisher.labels(api.issues[2]), {'ai-ready'})
                    self.assertEqual(writes, [
                        ('POST', 'issues/2/labels', {'labels': ['ai-ready']}),
                        ('DELETE', 'issues/2/labels/ai-planning', None),
                    ])

    def test_no_overwrite_reopen_or_redispatch_of_reconciled_work(self):
        for change in ('closed', 'owned', 'paused', 'withdrawn', 'body', 'epic', 'duplicate', 'edge',
                       'pull request'):
            with self.subTest(change=change):
                api = FakeGitHub()
                batch = {'issues': [task('a')]}
                publisher.publish(api, batch)
                row = api.issues[1]
                if change == 'closed':
                    row['state'] = 'closed'
                elif change in ('owned', 'paused'):
                    row['labels'].append({'name': 'ai-in-progress' if change == 'owned' else 'ai-paused'})
                elif change == 'withdrawn':
                    row['labels'] = []
                elif change == 'body':
                    row['body'] += '\nNew human decision'
                elif change == 'epic':
                    row['labels'].append({'name': 'ai-epic'})
                elif change == 'duplicate':
                    api.issues[2] = copy.deepcopy(row)
                elif change == 'edge':
                    api.dependencies[1] = {9876}
                elif change == 'pull request':
                    row.update(state='closed', pull_request={})
                before = copy.deepcopy(api.issues)
                api.events.clear()
                if change in ('closed', 'owned', 'paused'):
                    result, = publisher.publish(api, batch)
                    self.assertEqual(result['state'], row['state'])
                    self.assertEqual(result['labels'], sorted(publisher.labels(row)))
                else:
                    with self.assertRaises(publisher.PublicationError):
                        publisher.publish(api, batch)
                self.assertEqual(before, api.issues)
                self.assertTrue(all(method == 'GET' for method, _, _ in api.events))

    def test_native_wait_on_pending_prerequisite_is_not_fake_readiness(self):
        api = FakeGitHub()
        publisher.publish(api, {'issues': [task('input', ready=False, pending_reason='Device unavailable'),
                                          task('later', blocked_by=['input'])]})
        self.assertEqual(publisher.labels(api.issues[1]), {'ai-planning'})
        self.assertEqual(publisher.labels(api.issues[2]), {'ai-ready'})
        self.assertEqual(api.dependencies[2], {1001})  # Orbi waits on this native edge

    def test_withdrawn_label_during_publication_is_not_resurrected(self):
        api = FakeGitHub()
        original = api.api

        def withdraw(path, method='GET', data=None):
            result = original(path, method, data)
            if path == 'issues' and method == 'POST':
                api.issues[result['number']]['labels'] = []
            return result

        api.api = withdraw
        with self.assertRaisesRegex(publisher.PublicationError, 'readiness withdrawn'):
            publisher.publish(api, {'issues': [task('a')]})
        self.assertEqual(publisher.labels(api.issues[1]), set())

    def test_false_dependency_readback_leaves_batch_undispatched(self):
        api = FakeGitHub()
        pages = api.pages
        api.pages = lambda path: [] if path.endswith('/dependencies/blocked_by') else pages(path)
        with self.assertRaisesRegex(publisher.PublicationError, 'dependency readback failed'):
            publisher.publish(api, {'issues': [task('a'), task('b', blocked_by=['a'])]})
        self.assertTrue(all(publisher.labels(row) == {'ai-planning'} for row in api.issues.values()))

    def test_final_refresh_refuses_drift_after_an_earlier_ready_post(self):
        cases = {
            'dependency removed': 'dependency readback failed',
            'dependency added': 'dependency readback failed',
            'parent removed': 'epic readback failed',
            'parent changed': 'epic readback failed',
            'parent added': 'epic readback failed',
            'owned': 'owned',
            'paused': 'owned',
            'readiness withdrawn': 'readiness withdrawn',
            'pending dispatched': 'already dispatched',
            'body changed': 'contract changed',
            'title changed': 'contract changed',
            'closed': 'closed',
            'epic added': 'changed epic classification',
            'epic removed': 'changed epic classification',
            'issue read failure': 'issue readback failed',
            'dependency read failure': 'dependency readback failed',
            'dependency read timeout': 'dependency readback failed',
            'parent read failure': 'epic readback failed',
        }
        for change, error in cases.items():
            with self.subTest(change=change):
                api = FakeGitHub()
                b = task('b', blocked_by=['a'], epic='e')
                if change == 'parent added':
                    del b['epic']
                if change == 'epic removed':
                    b['kind'] = 'epic'
                if change == 'pending dispatched':
                    b.update(ready=False, pending_reason='Needs input')
                batch = {'issues': [task('a'), b, task('e', kind='epic'),
                                    task('f', kind='epic')]}
                original, pages = api.api, api.pages
                foreign = {}

                def interleave(path, method='GET', data=None, **kwargs):
                    if foreign and method == 'GET' and (
                        change == 'issue read failure' and path == 'issues/2'
                        or change == 'parent read failure' and path == 'issues/2/parent'
                    ):
                        raise publisher.PublicationError('injected read failure')
                    result = original(path, method, data, **kwargs)
                    if method == 'POST' and path == 'issues/1/labels':
                        row = api.issues[2]
                        if change == 'dependency removed':
                            api.dependencies[2].clear()
                        elif change == 'dependency added':
                            api.dependencies[2].add(9876)
                        elif change in ('parent removed', 'parent changed', 'parent added'):
                            api.children.get(3, set()).discard(row['id'])
                            if change != 'parent removed':
                                api.children[4] = {row['id']}
                        elif change in ('owned', 'paused', 'epic added'):
                            label = {'owned': 'ai-in-progress', 'paused': 'ai-paused',
                                     'epic added': 'ai-epic'}[change]
                            row['labels'].append({'name': label})
                        elif change == 'epic removed':
                            row['labels'] = [{'name': 'ai-planning'}]
                        elif change == 'readiness withdrawn':
                            row['labels'] = []
                        elif change == 'pending dispatched':
                            row['labels'].append({'name': 'ai-ready'})
                        elif change in ('body changed', 'title changed'):
                            row[change.split()[0]] += ' human edit'
                        elif change == 'closed':
                            row['state'] = 'closed'
                        foreign.update(issue=copy.deepcopy(row),
                                       dependencies=copy.deepcopy(api.dependencies),
                                       children=copy.deepcopy(api.children))
                    return result

                def read_dependencies(path):
                    if foreign and path == 'issues/2/dependencies/blocked_by':
                        if change == 'dependency read failure':
                            raise publisher.PublicationError('injected read failure')
                        if change == 'dependency read timeout':
                            raise subprocess.TimeoutExpired('gh api', 60)
                    return pages(path)

                api.api, api.pages = interleave, read_dependencies
                with self.assertRaisesRegex(publisher.PublicationError, f'#2: .*{error}'):
                    publisher.publish(api, batch)
                self.assertTrue(foreign, 'interleaving must happen after A is ready')
                self.assertEqual(publisher.labels(api.issues[1]), {'ai-ready'})
                self.assertEqual(api.issues[2], foreign['issue'])
                self.assertEqual(api.dependencies, foreign['dependencies'])
                self.assertEqual(api.children, foreign['children'])
                if change != 'readiness withdrawn':
                    self.assertIn('ai-planning', publisher.labels(api.issues[2]))
                self.assertNotIn(('POST', 'issues/2/labels', {'labels': ['ai-ready']}), api.events)

    def test_apply_entry_point_reports_success_or_preserves_partial_publication(self):
        for drift in (False, True):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as tmp:
                api = FakeGitHub()
                original = api.api

                def interleave(path, method='GET', data=None, **kwargs):
                    result = original(path, method, data, **kwargs)
                    if drift and method == 'POST' and path == 'issues/1/labels':
                        api.dependencies[2].clear()
                    return result

                api.api = interleave
                path = Path(tmp) / 'batch.json'
                path.write_text(json.dumps({'issues': [task('a'), task('b', blocked_by=['a'])]}))
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch.object(publisher, 'GitHub', return_value=api) as transport, \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    status = publisher.main(['--repo', 'example/repo', '--batch', str(path), '--apply'])
                transport.assert_called_once_with('example/repo')
                self.assertEqual(publisher.labels(api.issues[1]), {'ai-ready'})
                if drift:
                    self.assertEqual(status, 1)
                    self.assertEqual(stdout.getvalue(), '')
                    self.assertEqual(stderr.getvalue().splitlines()[0],
                                     'Publication incomplete: #2: dependency readback failed')
                    rows = self.partial_receipt(stderr.getvalue())
                    self.assertEqual(rows['a']['last_verified']['labels'], ['ai-ready'])
                    self.assertEqual(rows['b']['attempted_phase'], 'verify_dispatch')
                    self.assertEqual(publisher.labels(api.issues[2]), {'ai-planning'})
                    self.assertEqual(api.dependencies[2], set())
                    self.assertNotIn(('POST', 'issues/2/labels', {'labels': ['ai-ready']}), api.events)
                else:
                    self.assertEqual(status, 0)
                    self.assertEqual(stderr.getvalue(), '')
                    self.assertEqual([row['labels'] for row in json.loads(stdout.getvalue())],
                                     [['ai-ready'], ['ai-ready']])
                    self.assertEqual(api.dependencies[2], {1001})

    def test_external_dependency_uses_issue_id_and_keeps_existing_issue(self):
        api = FakeGitHub()
        publisher.publish(api, {'issues': [task('existing')]})
        api.issues[1]['state'] = 'closed'
        result = publisher.publish(api, {'issues': [task('new', blocked_by=[1])]})
        self.assertEqual(api.dependencies[2], {1001})
        self.assertEqual(api.issues[1]['state'], 'closed')
        self.assertEqual(result[0]['key'], 'new')

    def test_invalid_batch_has_no_remote_effect(self):
        cases = [[], [task('a'), task('a')], [task('a', blocked_by=['missing'])],
                 [task('a', blocked_by=['b']), task('b', blocked_by=['a'])],
                 [task('a', blocked_by=[True])], [task('a', ready='false')],
                 [task('a', ready=False)], [task('a', epic='missing')],
                 [dict(task('a'), verification='')], [dict(task('a'), key='x -->')],
                 [task('a', pending_reason='<!-- kit-issue:other -->')],
                 [task('a', depends_on=['typo'])],
                 [task('epic', kind='epic'), task('a', blocked_by=['epic'])],
                 [task('e1', kind='epic', epic='e2'), task('e2', kind='epic', epic='e1')]]
        for issues in cases:
            api = FakeGitHub()
            with self.subTest(issues=issues), self.assertRaises(publisher.PublicationError):
                publisher.publish(api, {'issues': issues})
            self.assertEqual(api.events, [])

    def test_preview_is_nonmutating_and_json_prose_never_enters_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'batch.json'
            issue = task('a')
            issue['scope'] = 'literal $(do-not-run) `text` "quotes" café\nline'
            path.write_text(json.dumps({'issues': [issue]}))
            result = subprocess.run(['python3', str(ROOT / 'scripts/github_issues.py'),
                                     '--repo', 'example/repo', '--batch', str(path)],
                                    text=True, capture_output=True, check=True)
            self.assertFalse(json.loads(result.stdout)['remote_checked'])
            self.assertIn(issue['scope'], json.loads(result.stdout)['issues'][0]['body'])
        with patch.object(publisher.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '{}', '')
            publisher.GitHub('example/repo').api('issues', 'POST', {'body': issue['scope']})
            args, kwargs = run.call_args
            self.assertNotIn('shell', kwargs)
            self.assertNotIn(issue['scope'], args[0])
            self.assertEqual(json.loads(kwargs['input']), {'body': issue['scope']})

    def test_epic_contract_change_or_remote_parent_drift_is_not_silently_kept(self):
        for change in ('removed', 'changed', 'remote'):
            api = FakeGitHub()
            batch = {'issues': [task('e', kind='epic'), task('f', kind='epic'),
                                task('a', epic='e', ready=False, pending_reason='Needs input')]}
            publisher.publish(api, batch)
            if change == 'removed':
                del batch['issues'][2]['epic']
            elif change == 'changed':
                batch['issues'][2]['epic'] = 'f'
            else:
                api.children[1].clear()
                api.children[2] = {1003}
            before = copy.deepcopy(api.children)
            with self.assertRaises(publisher.PublicationError):
                publisher.publish(api, batch)
            self.assertEqual(api.children, before)

    def test_retry_does_not_add_child_to_an_epic_seen_closed_during_reuse(self):
        api = FakeGitHub()
        epic = task('e', kind='epic')
        publisher.publish(api, {'issues': [epic]})
        api.issues[1]['state'] = 'closed'
        original = api.api

        def reopen_epic(path, method='GET', data=None, **kwargs):
            result = original(path, method, data, **kwargs)
            if (method, path) == ('POST', 'issues'):
                api.issues[1]['state'] = 'open'
            return result

        api.api = reopen_epic
        api.events.clear()
        with self.assertRaisesRegex(publisher.PublicationError, '#1: closed'):
            publisher.publish(api, {'issues': [epic, task('a', epic='e')]})
        self.assertEqual(api.issues[1]['state'], 'open')  # foreign reopen after reuse
        self.assertEqual(api.children, {})
        self.assertFalse(any(method != 'GET' and path.startswith('issues/1/')
                             for method, path, _ in api.events))

    def test_newly_owned_child_is_not_linked_into_epic(self):
        api = FakeGitHub()
        original = api.api

        def claim(path, method='GET', data=None, **kwargs):
            result = original(path, method, data, **kwargs)
            if path == 'issues/1/parent':
                api.issues[2]['labels'].append({'name': 'ai-in-progress'})
            return result

        api.api = claim
        with self.assertRaisesRegex(publisher.PublicationError, 'owned'):
            publisher.publish(api, {'issues': [task('e', kind='epic'), task('a', epic='e')]})
        self.assertEqual(api.children, {})
        self.assertTrue(all('ai-ready' not in publisher.labels(row) for row in api.issues.values()))

    def test_optional_parent_404_does_not_swallow_permission_or_network_errors(self):
        api = publisher.GitHub('example/repo')
        with patch.object(publisher.subprocess, 'run') as run:
            for status, allowed in [('404', True), ('403', False), ('500', False)]:
                run.return_value = subprocess.CompletedProcess([], 1, json.dumps({'status': status}), 'failure')
                if allowed:
                    self.assertIsNone(api.api('issues/1/parent', missing_ok=True))
                else:
                    with self.assertRaises(publisher.PublicationError):
                        api.api('issues/1/parent', missing_ok=True)

    def test_api_paginates_dependency_and_issue_lists(self):
        api = publisher.GitHub('example/repo')
        with patch.object(api, 'api', side_effect=[[{'id': i} for i in range(100)], [{'id': 101}]]) as call:
            self.assertEqual(len(api.pages('issues?state=all')), 101)
            self.assertEqual(call.call_args.args[0], 'issues?state=all&per_page=100&page=2')


class DefaultDispatchTests(unittest.TestCase):
    def test_workflow_handles_all_authors_but_preserves_planning_and_delivery(self):
        # Execute the actual inline JS with an API double, rather than matching prose.
        source = (ROOT / '.github/workflows/issue-ready.yml').read_text()
        script = '\n'.join(line[12:] for line in source.split('          script: |\n', 1)[1].splitlines())
        driver = r'''
const script = new (Object.getPrototypeOf(async function(){}).constructor)('github', 'context', 'core', process.argv[1]);
(async () => {
  for (const label of [null, 'ai-planning', 'ai-epic', 'ai-paused', 'ai-in-progress',
      'ai-pr-opened', 'ai-fix-needed', 'ai-awaiting-merge', 'ai-merged', 'ai-blocked', 'ai-needs-detail', 'ai-ready']) {
    for (const state of ['open', 'closed']) {
      const calls = [];
      const github = {rest:{issues:{
        get:async()=>({data:{state,labels:label ? [{name:label}] : [],user:{login:'external-contributor'}}}),
        getLabel:async()=>({}), addLabels:async args=>calls.push(args)
      }}};
      await script(github, {repo:{owner:'example',repo:'repo'},issue:{number:7}}, {info:()=>{}});
      const expected = state === 'open' && label === null ? 1 : 0;
      if (calls.length !== expected) throw Error(`${label}/${state}: ${calls.length}`);
    }
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        subprocess.run(['node', '-e', driver, script], check=True, capture_output=True, text=True)
        self.assertIn('types: [opened, reopened]', source)
        self.assertNotIn('actions/checkout', source)
        self.assertNotIn('${{ github.event.issue.body', source)


if __name__ == '__main__':
    unittest.main()
