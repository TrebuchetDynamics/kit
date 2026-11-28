"""The Unblock inventory entry point with fixture configs, scheduler and gh."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_orbi_control as orbi

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'skills/unblock/scripts/inventory.py'
REPO = 'other/repo-a'
HEAD = '1' * 40


def issue(number, *labels, repo=REPO):
    return {'number': number, 'title': f'Issue {number}',
            'html_url': f'https://github.com/{repo}/issues/{number}',
            'labels': [{'name': name} for name in labels]}


def marker(kind, **fields):
    return f'<!-- orbi:{kind}:v1 {json.dumps(fields)} -->'


class UnblockInventoryTests(unittest.TestCase):
    lists = orbi.HostStatusTests.lists
    unit = orbi.HostStatusTests.unit
    detail = orbi.HostStatusTests.detail

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.h = orbi.Harness(Path(tmp.name))
        self.h.add_deployment_a()
        self.extra = self.h.config_home / 'orbi/extra/orbi.toml'
        self.extra.parent.mkdir(parents=True)
        self.extra.write_text('source_repos = ["Other/Repo-A", "second/repo"]\n')
        self.cwd = self.h.root / 'not-a-checkout'
        self.cwd.mkdir()
        self.worker = 'orbi-a@17.service'

    def service_rules(self, number=42):
        invocation, pid, run = 'c' * 32, '222', '1234abcd'
        yield from self.lists('--user', [self.unit(self.worker, 'active')])
        yield from self.lists('--system')
        yield self.detail('--user', self.worker, ActiveState='active', MainPID=pid, InvocationID=invocation,
                          WorkingDirectory=self.h.data_home / 'orbi-a',
                          FragmentPath=self.h.unit_dir / 'orbi-a@.service')
        if number is not None:
            yield {'tool': 'journalctl', 'argv_contains': ['--user', self.worker], 'stdout': json.dumps({
                'MESSAGE': f'INFO [{run}] run_start issue={REPO}#{number} run={run} phase=implement',
                '_PID': pid, '_SYSTEMD_INVOCATION_ID': invocation}) + '\n'}

    def api(self, repo, path, *pages, error=False):
        return {'tool': 'gh', 'argv_contains': ['api', f'repos/{repo}/{path}', '--method', 'GET',
                                               '--hostname', 'github.com', '--paginate', '--slurp'],
                'stdout': json.dumps(pages) if not error else '', 'exit': int(error),
                'stderr': 'private gh error detail' if error else ''}

    def pr(self, number):
        return {'number': number, 'html_url': f'https://github.com/{REPO}/pull/{number}',
                'head': {'ref': f'task-{number}', 'sha': HEAD}}

    def pr_reads(self, number, *, bucket='pending', latest=HEAD):
        yield {'tool': 'gh', 'argv_contains': ['pr', 'checks', str(number), '--required', '--json',
                                               'name,state,bucket,link', 'github.com/' + REPO],
               'stdout': json.dumps([{'name': 'test', 'state': 'IN_PROGRESS', 'bucket': bucket,
                                      'link': f'https://github.com/{REPO}/actions/runs/1'}]) if bucket else '',
               'exit': 0 if bucket else 1,
               'stderr': '' if bucket else f"no required checks reported on the 'task-{number}' branch\n"}
        yield {'tool': 'gh', 'argv_contains': ['pr', 'view', str(number), '--json',
                                               'state,headRefName,headRefOid,mergeable', 'github.com/' + REPO],
               'stdout': json.dumps({'state': 'OPEN', 'headRefName': f'task-{number}', 'headRefOid': latest,
                                     'mergeable': 'MERGEABLE'})}

    def run_cli(self, *rules):
        self.h.rules(*rules)
        before = orbi.snapshot(self.h.home)
        result = subprocess.run([sys.executable, '-B', str(CLI), '--json'], cwd=self.cwd,
                                env=self.h.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(orbi.snapshot(self.h.home), before)
        for call in self.h.calls():
            tool, args = call['tool'], call['argv']
            if tool == 'gh':
                if args[0] == 'api':
                    self.assertEqual(args[2:], ['--hostname', 'github.com', '--method', 'GET',
                                                '--paginate', '--slurp'])
                    self.assertTrue(args[1].startswith((f'repos/{REPO}/', 'repos/second/repo/')))
                else:
                    self.assertIn(args[:2], (['pr', 'checks'], ['pr', 'view']))
            elif tool == 'systemctl':
                self.assertIn(args[1], ('list-units', 'list-unit-files', 'show'))
            else:
                self.assertIn(tool, ('journalctl', 'git'))
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)

    def test_cli_inventories_pages_markers_prs_and_verified_worker(self):
        config = self.h.data_home / 'orbi-a/orbi.toml'
        config.write_text(config.read_text().replace('["other/repo-a"]', '["Other/Repo-A", "second/repo"]'))
        older = marker('failure', schema=1, reason_code='provider_quota', action_code='wait_quota',
                       retry_safe=True, outcome='blocked')
        latest = marker('failure', schema=1, reason_code='review_budget_exhausted', action_code='decide',
                        retry_safe=False, outcome='blocked')
        option = {'label': 'Preserve candidate', 'description': 'Amend the ticket',
                  'action': 'amend_requeue', 'recommended': True, 'reason': 'No loss of work'}
        question = marker('question', schema=1, decision_class='authority', question={
            'id': 'q2', 'kind': 'choice', 'summary': 'Review stalled', 'question': 'How should delivery resume?',
            'options': [{'label': 'Close', 'description': 'Close work', 'action': 'close_all'}, option]})
        answer = marker('answer', q='q2', action='accept', value=option['label'], by='maintainer')
        def reply(issue_number, comment_id):
            return {'body': answer, 'id': comment_id, 'node_id': f'IC_kwFixture{comment_id}',
                    'html_url': f'https://github.com/{REPO}/issues/{issue_number}#issuecomment-{comment_id}'}

        receipt = '<!-- orbi-answer-command comment=IC_kwFixture107 -->'
        rejected = '<!-- orbi-answer-command-rejected comment=IC_kwFixture108 -->'
        automatic = '<!-- orbi:comment=requeued -->\n' + question.replace('authority', 'pick_best') + '\n' + marker(
            'answer', q='q2', action='accept', value=option['label'], by='orbi')
        older_owner = {**issue(9, 'owner-task', 'ai-planning', 'ai-blocked'),
                       'created_at': '2026-05-04T09:00:00Z'}
        base_block_url = f'https://github.com/{REPO}/issues/11#issuecomment-110'
        result, doc = self.run_cli(
            *self.service_rules(),
            self.api(REPO, 'issues?state=open&per_page=100',
                     [issue(1, 'ai-blocked'), issue(2, 'ai-fix-needed'), issue(3, 'ai-decision'),
                      issue(4, 'ai-pr-opened'), issue(5, 'ai-planning', 'ai-epic'), issue(6, 'ai-ready'),
                      {**issue(8, 'owner-task'), 'created_at': '2026-11-26T11:00:00Z'},
                      {**issue(10, 'owner-task'), 'pull_request': {}, 'created_at': '2026-01-01T00:00:00Z'}],
                     [issue(7, 'ai-planning'), issue(11, 'ai-blocked'), issue(42, 'ai-in-progress'), older_owner]),
            self.api(REPO, 'issues?state=closed&per_page=100',
                     [issue(15, 'ai-ready'), issue(16, 'ai-ops-only'),
                      {**issue(17, 'ai-blocked'), 'pull_request': {}}, issue(18, 'owner-task', 'ai-blocked')],
                     [issue(19, 'ai-blocked', 'ai-merged', 'bug'), issue(20, 'ai-fix-needed'),
                      issue(21, 'ai-in-progress'), issue(22, 'ai-pr-opened')]),
            # Orbi can update a deduplicated failure in place, behind a newer comment ID.
            self.api(REPO, 'issues/1/comments?per_page=100',
                     [{'body': latest, 'updated_at': '2026-11-26T12:00:00Z'}],
                     [{'body': older, 'updated_at': '2026-11-26T11:00:00Z'}]),
            self.api(REPO, 'issues/2/comments?per_page=100',
                     [{'body': question}, reply(2, 107)], [{'body': receipt}]),
            self.api(REPO, 'issues/3/comments?per_page=100',
                     [{'body': question}, reply(3, 108), {'body': rejected}]),
            self.api(REPO, 'issues/4/comments?per_page=100', [{'body': automatic}]),
            self.api(REPO, 'issues/7/comments?per_page=100', [{'body': question}, reply(7, 109)]),
            self.api(REPO, 'issues/11/comments?per_page=100', [{'html_url': base_block_url,
                     'body': marker('failure', schema=1, reason_code='base_ci_red', action_code='fix_ticket',
                                    retry_safe=False, outcome='blocked') + '\n' + marker(
                         'base-ci-red', schema=1, state='waiting', base_branch='release', base_sha=HEAD,
                         pr=22, failing_checks=['test'])}]),
            self.api(REPO, 'issues/42/comments?per_page=100', []),
            self.api(REPO, 'pulls?state=open&per_page=100', [self.pr(22)], [self.pr(11)]),
            *self.pr_reads(22, bucket=None), *self.pr_reads(11),
            self.api('second/repo', 'issues?state=open&per_page=100',
                     [issue(42, 'ai-in-progress', repo='second/repo')]),
            self.api('second/repo', 'issues/42/comments?per_page=100', []),
            self.api('second/repo', 'issues?state=closed&per_page=100', []),
            self.api('second/repo', 'pulls?state=open&per_page=100', []))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(doc['schema_version'], 1)
        self.assertEqual([r['repo'] for r in doc['repositories']], [REPO, 'second/repo'])
        first, second = doc['repositories']
        self.assertEqual(first['owner_tasks'], {'count': 2, 'oldest': {
            'url': older_owner['html_url'], 'created_at': older_owner['created_at']}})
        self.assertEqual(second['owner_tasks'], {'count': 0, 'oldest': None})
        self.assertFalse(any(call['tool'] == 'gh' and '/comments?' in arg
                             and any(f'/issues/{n}/' in arg for n in (8, 9, 10, 18))
                             for call in self.h.calls() for arg in call['argv']))
        self.assertEqual(next(d for d in first['deployments'] if d['unit'] == self.worker)['state'],
                         'running')
        self.assertIn('prepared-only', {d['state'] for d in first['deployments']})
        prepared = next(d for d in second['deployments'] if d['config'] == str(self.extra))
        self.assertEqual(prepared['state'], 'prepared-only')
        second_issue, = second['open_issues']
        self.assertIs(second_issue['live_local_worker'], False)
        by_number = {i['number']: i for i in first['open_issues']}
        self.assertEqual(list(by_number), [1, 2, 3, 4, 7, 11, 42])
        self.assertEqual(by_number[1]['failure'], {'reason_code': 'review_budget_exhausted', 'action_code': 'decide'})
        self.assertEqual(by_number[11]['failure'], {'reason_code': 'base_ci_red', 'action_code': 'fix_ticket',
                                                  'comment_url': base_block_url})
        self.assertIsNone(by_number[2]['open_question'])
        self.assertEqual(by_number[3]['open_question']['id'], 'q2')
        self.assertEqual(by_number[3]['open_question']['recommended_option'], option)
        self.assertIsNone(by_number[4]['open_question'])
        self.assertEqual(by_number[7]['open_question']['recommended_option'], option)
        self.assertIs(by_number[42]['live_local_worker'], True)
        self.assertIs(by_number[4]['live_local_worker'], False)
        self.assertEqual({i['number']: i['labels'] for i in first['closed_issues']}, {
            15: ['ai-ready'], 19: ['ai-blocked', 'ai-merged', 'bug'], 20: ['ai-fix-needed'],
            21: ['ai-in-progress'], 22: ['ai-pr-opened'],
        })
        wait, absent = first['open_prs']
        self.assertEqual((wait['number'], wait['head'], wait['head_sha'], wait['mergeability']),
                         (11, 'task-11', HEAD, 'MERGEABLE'))
        self.assertEqual(wait['required_checks']['result'], 'pending')
        self.assertEqual(absent['required_checks'], {'result': 'not_reported', 'checks': []})

    def test_cli_preserves_independent_results_on_failed_read_and_head_change(self):
        result, doc = self.run_cli(
            *self.service_rules(number=None),
            self.api(REPO, 'issues?state=open&per_page=100', [issue(42, 'ai-in-progress')]),
            self.api(REPO, 'issues/42/comments?per_page=100', []),
            self.api(REPO, 'issues?state=closed&per_page=100', error=True),
            self.api(REPO, 'pulls?state=open&per_page=100', [self.pr(11)]),
            *self.pr_reads(11, bucket='pass', latest='2' * 40),
            *(self.api('second/repo', path, []) for path in ('issues?state=open&per_page=100',
                                                            'issues?state=closed&per_page=100',
                                                            'pulls?state=open&per_page=100')))
        self.assertEqual(result.returncode, 1)
        first, second = doc['repositories']
        self.assertIn('closed issues: gh api exited 1', result.stderr)
        self.assertIn('verify gh authentication', result.stderr)
        self.assertNotIn('private gh error detail', result.stdout + result.stderr)
        self.assertIsNone(first['closed_issues'])
        self.assertIsNone(first['open_issues'][0]['live_local_worker'])
        self.assertEqual(first['open_prs'][0]['head_sha'], '2' * 40)
        self.assertEqual(first['open_prs'][0]['required_checks'], {'result': 'unknown', 'checks': []})
        self.assertEqual(second['errors'], [])

    def test_cli_marks_owner_task_coverage_unavailable_when_open_issue_list_fails(self):
        result, doc = self.run_cli(
            *self.service_rules(number=None),
            self.api(REPO, 'issues?state=open&per_page=100', error=True),
            self.api(REPO, 'issues?state=closed&per_page=100', []),
            self.api(REPO, 'pulls?state=open&per_page=100', []),
            *(self.api('second/repo', path, []) for path in ('issues?state=open&per_page=100',
                                                            'issues?state=closed&per_page=100',
                                                            'pulls?state=open&per_page=100')))
        self.assertEqual(result.returncode, 1)
        self.assertIn('open issues: gh api exited 1; verify gh authentication', result.stderr)
        first, second = doc['repositories']
        self.assertIsNone(first['owner_tasks'])
        self.assertEqual(second['owner_tasks'], {'count': 0, 'oldest': None})
