"""Offline publication, retry and default-dispatch contracts; no live qualification."""
import copy
import importlib.util
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
        if path == 'issues':
            number = len(self.issues) + 1
            self.issues[number] = dict(number=number, id=1000 + number, state='open',
                                       html_url=f'https://github.com/example/repo/issues/{number}',
                                       title=data['title'], body=data['body'],
                                       labels=[{'name': label} for label in data['labels']])
            return copy.deepcopy(self.issues[number])
        number = int(path.split('/')[1])
        issue = self.issues[number]
        if method == 'GET':
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
            if self.fail_ready and 'ai-ready' in data['labels']:
                raise publisher.PublicationError('injected readiness failure')
            for label in data['labels']:
                if label not in publisher.labels(issue):
                    issue['labels'].append({'name': label})
        elif method == 'DELETE' and path.endswith('/labels/ai-planning'):
            issue['labels'] = [label for label in issue['labels'] if label['name'] != 'ai-planning']
        else:
            raise AssertionError((path, method, data))
        return copy.deepcopy(issue)


class PublicationTests(unittest.TestCase):
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

    def test_no_overwrite_reopen_or_redispatch_of_reconciled_work(self):
        for change in ('closed', 'owned', 'paused', 'withdrawn', 'body', 'epic', 'duplicate', 'edge'):
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
                before = copy.deepcopy(api.issues)
                with self.assertRaises(publisher.PublicationError):
                    publisher.publish(api, batch)
                self.assertEqual(before, api.issues)

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
