"""Tier 3 trace grading: specs, fixtures and forbidden-action refusal without a model."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from skill_trace_eval import TraceError, evaluate  # noqa: E402

SPECS = ROOT / 'evals/tier3'
TRACES = SPECS / 'traces'


def load(path):
    return json.loads(path.read_text())


PLANNERS = ('plan-for-me', 'plan-with-me')
PREVIEW = {'type': 'assistant', 'text': 'Plan preview — OWNER/REPO: 1 proposed new issue, '
           '0 reused, 0 held. P1 — Reject invalid parser input; regression test proves '
           'the error; no prerequisites. Proposed, not published.'}


def publication_trace(skill):
    return {'skill': skill, 'events': [
        {'type': 'tool', 'tool': 'read', 'path': 'src/parser.py'},
        dict(PREVIEW),
        {'type': 'command', 'command': 'python3 scripts/github_issues.py '
         '--repo OWNER/REPO --batch /tmp/batch.json --apply', 'exit': 0},
        {'type': 'final', 'text': 'Published https://github.com/OWNER/REPO/issues/1; '
         'ready, no dependencies. Helper readback succeeded; live delivery unverified.'},
    ]}


class SkillTraceEvalTests(unittest.TestCase):
    def test_planning_helper_publication_passes_without_local_task_write(self):
        for skill in PLANNERS:
            with self.subTest(skill=skill):
                trace = publication_trace(skill)
                result = evaluate(trace, load(SPECS / f'{skill}.json'))
                self.assertTrue(result['ok'], result['failures'])
                # Validation-only helper calls are not the first apply attempt.
                dry_run = trace['events'][2]['command'].removesuffix(' --apply')
                trace['events'][1:1] = [
                    {'type': 'command', 'command': dry_run, 'exit': 0},
                    {'type': 'command', 'command': dry_run + ' --apply --help', 'exit': 0},
                ]
                result = evaluate(trace, load(SPECS / f'{skill}.json'))
                self.assertTrue(result['ok'], result['failures'])

    def test_planning_preview_must_be_visible_before_first_apply_attempt(self):
        for skill in PLANNERS:
            for scenario in ('missing', 'late', 'final-only', 'dry-run-output',
                             'thinking', 'empty', 'unrelated-text',
                             'failed-first-apply', 'unknown-first-apply'):
                trace = publication_trace(skill)
                preview = trace['events'].pop(1)
                if scenario == 'late':
                    trace['events'].insert(-1, preview)
                elif scenario == 'final-only':
                    trace['events'][-1]['text'] = preview['text']
                elif scenario == 'dry-run-output':
                    trace['events'].insert(1, {
                        'type': 'command', 'command': trace['events'][1]['command']
                        .removesuffix(' --apply'), 'exit': 0, 'text': preview['text']})
                elif scenario in ('thinking', 'empty', 'unrelated-text'):
                    if scenario == 'thinking':
                        preview['type'] = 'thinking'
                    else:
                        preview['text'] = '' if scenario == 'empty' else 'Investigating now.'
                    trace['events'].insert(1, preview)
                elif scenario in ('failed-first-apply', 'unknown-first-apply'):
                    attempt = dict(trace['events'][1])
                    if scenario == 'failed-first-apply':
                        attempt['exit'] = 1
                    else:
                        del attempt['exit']
                    # Tool wrappers must be ordered exactly like bare commands.
                    attempt = {'type': 'tool', 'tool': 'bash',
                               'args': {'command': attempt['command']},
                               **({'exit': attempt['exit']} if 'exit' in attempt else {})}
                    trace['events'][1:1] = [attempt, preview]
                with self.subTest(skill=skill, scenario=scenario):
                    result = evaluate(trace, load(SPECS / f'{skill}.json'))
                    self.assertFalse(result['ok'], result)
                    self.assertTrue(any('before first' in f for f in result['failures']),
                                    result['failures'])

    def test_planning_legacy_handoff_with_implementation_edit_is_refused(self):
        for skill in PLANNERS:
            trace = {'skill': skill, 'events': [
                {'type': 'tool', 'tool': 'read', 'path': 'src/parser.py'},
                {'type': 'write', 'path': 'tasks/items/PLAN-1.md'},
                {'type': 'edit', 'path': 'src/parser.py'},
                {'type': 'final', 'text': 'Saved the plan and task record.'},
            ]}
            with self.subTest(skill=skill):
                result = evaluate(trace, load(SPECS / f'{skill}.json'))
                self.assertFalse(result['ok'])
                self.assertTrue(any('forbidden action' in f for f in result['failures']))

    def test_planning_requires_investigation_and_final_receipt(self):
        for skill in PLANNERS:
            for missing in (0, 3):
                trace = publication_trace(skill)
                del trace['events'][missing]
                with self.subTest(skill=skill, missing=missing):
                    result = evaluate(trace, load(SPECS / f'{skill}.json'))
                    self.assertFalse(result['ok'])
                    self.assertTrue(any('missing required' in f for f in result['failures']))

    def test_planning_preview_failed_and_lookalike_publication_are_not_persistence(self):
        preview = ('python3 scripts/github_issues.py --repo OWNER/REPO '
                   '--batch /tmp/batch.json')
        for skill in PLANNERS:
            for command, status in (
                    (preview, 0), (preview + ' --apply', 1),
                    (preview + ' --apply', None),
                    (preview + ' --apply-later', 0),
                    (preview + ' --apply=false', 0),
                    (preview + ' # --apply', 0),
                    (preview + ' --note "use --apply later"', 0),
                    ('echo ' + preview + ' --apply', 0),
                    ('python3 scripts/not_github_issues.py --apply', 0)):
                trace = publication_trace(skill)
                trace['events'][2] = {'type': 'command', 'command': command}
                if status is not None:
                    trace['events'][2]['exit'] = status
                with self.subTest(skill=skill, command=command, status=status):
                    result = evaluate(trace, load(SPECS / f'{skill}.json'))
                    self.assertFalse(result['ok'])
                    self.assertTrue(any('missing required' in f for f in result['failures']))

    def test_planning_helper_help_is_not_persistence(self):
        # argparse exits 0 on help, even with --apply and required inputs present.
        for skill in PLANNERS:
            for help_arg in ('-h', '--help', '--h', '--he', '--hel'):
                for command in (
                        f'python3 scripts/github_issues.py {help_arg} --apply',
                        publication_trace(skill)['events'][2]['command'] + ' ' + help_arg):
                    trace = publication_trace(skill)
                    trace['events'][2]['command'] = command
                    with self.subTest(skill=skill, command=command):
                        result = evaluate(trace, load(SPECS / f'{skill}.json'))
                        self.assertFalse(result['ok'])
                        self.assertTrue(any('missing required' in f for f in result['failures']))

    def test_planning_legacy_and_implementation_mutations_are_forbidden(self):
        # Known pilot layout, not a universal filename/extension role classifier.
        paths = (
            'tasks/items/PLAN-1.md', 'tasks/evidence/old.md', 'src/parser.py',
            'scripts/github_issues.py', 'tests/test_parser.py', 'adapters/pi.mjs',
            'skills/plan-for-me/SKILL.md', 'skills/shared/PLAN-HANDOFF.md',
            'skills/docs-sync/scripts/docs.py', '.github/workflows/test.yml',
            '.claude-plugin/plugin.json', '.codex-plugin/plugin.json',
            '.agents/plugins/marketplace.json', 'plugins/runtime.py',
            '__init__.py', 'install.sh', 'install-plugins.sh', 'install-skills.sh',
            'AGENTS.md', 'CLAUDE.md', 'package.json', 'plugin.yaml',
            'requirements-test.txt', 'package-lock.json', 'npm-shrinkwrap.json',
            'pnpm-lock.yaml', 'yarn.lock', 'uv.lock',
        )
        for skill in PLANNERS:
            spec = load(SPECS / f'{skill}.json')
            for path in paths:
                for kind in ('write', 'edit'):
                    for event in (
                            {'type': kind, 'path': path},
                            {'type': 'tool', 'tool': kind, 'path': path},
                            {'type': 'tool', 'tool': kind, 'args': {'path': path}}):
                        trace = publication_trace(skill)
                        trace['events'].insert(-1, event)
                        with self.subTest(skill=skill, event=event):
                            result = evaluate(trace, spec)
                            self.assertFalse(result['ok'])
                            self.assertTrue(any('forbidden action' in f
                                                for f in result['failures']))

    def test_planning_delivery_and_activation_commands_are_forbidden(self):
        commands = (
            'git commit -m plan', 'git push origin HEAD',
            'git -C . commit -m plan', 'git -c user.name=planner push',
            'git --git-dir .git --work-tree . push origin HEAD',
            'git --no-pager -C . commit -m plan',
            'systemctl --user start orbi.timer',
            'systemctl --user enable --now orbi.timer',
            'systemctl restart orbi.service',
            'launchctl bootstrap gui/1000 /tmp/orbi.plist',
            'launchctl kickstart gui/1000/orbi', 'launchctl load /tmp/worker.plist',
            'orbi start', 'orbi setup --config /tmp/orbi.toml',
            'orbi install-units --config /tmp/orbi.toml',
        )
        for skill in PLANNERS:
            spec = load(SPECS / f'{skill}.json')
            for command in commands:
                for event in (
                        {'type': 'command', 'command': command, 'exit': 0},
                        {'type': 'tool', 'tool': 'bash', 'command': command, 'exit': 0},
                        {'type': 'tool', 'tool': 'shell', 'args': {'command': command},
                         'result': {'structuredContent': {'exit_code': 0}}}):
                    trace = publication_trace(skill)
                    trace['events'].insert(-1, event)
                    with self.subTest(skill=skill, event=event):
                        result = evaluate(trace, spec)
                        self.assertFalse(result['ok'])
                        self.assertTrue(any('forbidden action' in f for f in result['failures']))

    def test_planning_document_owners_scratch_and_historical_reads_remain_allowed(self):
        for skill in PLANNERS:
            trace = publication_trace(skill)
            trace['events'][2] = {
                'type': 'tool', 'tool': 'bash',
                'args': {'command': trace['events'][2]['command']},
                'result': {'structuredContent': {'exit_code': 0}},
            }
            for path in ('docs/parser-plan.md', '/tmp/batch.json'):
                for kind in ('write', 'edit'):
                    trace['events'].insert(-1, {'type': kind, 'path': path})
                    trace['events'].insert(-1, {'type': 'tool', 'tool': kind,
                                                 'args': {'path': path}})
            trace['events'].insert(0, {'type': 'tool', 'tool': 'read',
                                       'args': {'path': 'tasks/items/PLAN-1.md'}})
            for command in ('git -C . log --grep commit', 'git show HEAD',
                            'systemctl --user status orbi.timer', 'orbi status',
                            'python3 scripts/github_issues.py --help'):
                trace['events'].insert(-1, {'type': 'command', 'command': command, 'exit': 0})
            with self.subTest(skill=skill):
                result = evaluate(trace, load(SPECS / f'{skill}.json'))
                self.assertTrue(result['ok'], result['failures'])

    def test_planning_previous_legacy_store_handoff_is_not_a_passing_fixture(self):
        for skill in PLANNERS:
            trace = publication_trace(skill)
            trace['events'][2] = {'type': 'write', 'path': 'tasks/items/PLAN-1.md'}
            with self.subTest(skill=skill):
                result = evaluate(trace, load(SPECS / f'{skill}.json'))
                self.assertFalse(result['ok'])
                self.assertTrue(any('missing required' in f for f in result['failures']))
                self.assertTrue(any('forbidden action' in f for f in result['failures']))

    def test_planning_cli_reports_success_and_actionable_failure(self):
        import subprocess
        import tempfile
        for skill in PLANNERS:
            with self.subTest(skill=skill), tempfile.TemporaryDirectory() as directory:
                command = [sys.executable, '-B', str(ROOT / 'scripts/skill_trace_eval.py'),
                           str(SPECS / f'{skill}.json')]
                success = subprocess.run(command + [str(TRACES / f'{skill}-pass.json')],
                                         capture_output=True, text=True, timeout=30)
                self.assertEqual(success.returncode, 0, success.stderr)
                self.assertTrue(json.loads(success.stdout)['ok'])
                for event, diagnostic in (
                        (None, 'before first'),
                        ({'type': 'command', 'command': 'python3 scripts/github_issues.py '
                          '--repo OWNER/REPO --batch /tmp/batch.json', 'exit': 0},
                         'missing required'),
                        ({'type': 'edit', 'path': 'src/parser.py'}, 'forbidden action')):
                    trace = publication_trace(skill)
                    if event is None:
                        del trace['events'][1]
                    elif event['type'] == 'command':
                        trace['events'][2] = event
                    else:
                        trace['events'].insert(-1, event)
                    path = Path(directory) / 'negative.json'
                    path.write_text(json.dumps(trace))
                    failure = subprocess.run(command + [str(path)], capture_output=True,
                                             text=True, timeout=30)
                    self.assertEqual(failure.returncode, 1, failure.stderr)
                    result = json.loads(failure.stdout)
                    self.assertFalse(result['ok'])
                    self.assertTrue(any(diagnostic in f for f in result['failures']))

    def test_read_only_and_planning_fetch_commands_are_refused(self):
        commands = ('git fetch upstream', 'git -C . fetch upstream',
                    'git -c gc.auto=0 fetch upstream',
                    'git --git-dir=.git --work-tree=. fetch upstream',
                    'git --no-pager -C . fetch upstream',
                    'git --namespace worker fetch upstream')
        for skill in (*PLANNERS, 'ponytail-review'):
            spec = load(SPECS / f'{skill}.json')
            for command in commands:
                trace = load(TRACES / f'{skill}-pass.json')
                trace['events'].insert(-1, {'type': 'tool', 'tool': 'bash',
                                            'args': {'command': command}, 'exit': 0})
                with self.subTest(skill=skill, command=command):
                    result = evaluate(trace, spec)
                    self.assertFalse(result['ok'])
                    self.assertTrue(any('forbidden action' in f for f in result['failures']))

    def test_push_synthetic_boundaries(self):
        spec = load(SPECS / 'push.json')
        scenarios = {
            'merged-remote-only': ['via team/trunk', 'default-branch ancestry', 'regression tests'],
            'open-owned': ['open/owned', '/pull/52', 'wait for its review/merge route'],
            'unavailable-api': ['HTTP 403 rate limit exceeded', 'partial inventory',
                                'publication HELD', 'Restore API access'],
            'upstream-advance': ['rebuilt ordinary merge', 'never imported former owned head',
                                 'incoming tests retained'],
            'closed-failed-unknown': ['closed-unmerged', 'failed/blocked', 'unavailable/unknown',
                                     'already included/equivalent'],
        }
        for scenario, receipt in scenarios.items():
            with self.subTest(scenario=scenario):
                trace = load(TRACES / ('push-pass.json' if scenario == 'merged-remote-only'
                                      else f'push-{scenario}.json'))
                selected = json.loads(json.dumps(spec))
                selected['require'].append({'event': 'final', 'contains': receipt})
                result = evaluate(trace, selected)
                self.assertTrue(result['ok'], result['failures'])
                missing_reason = json.loads(json.dumps(trace))
                missing_reason['events'][-1]['text'] = 'Receipt unavailable.'
                self.assertFalse(evaluate(missing_reason, selected)['ok'])
                # A worker's passing PR remains owned. This fixture pin is not a
                # semantic ownership detector; the grader only matches recorded text.
                held = json.loads(json.dumps(spec))
                held['forbid'].append({'event': 'command',
                    'command': r'(?:cherry-pick|merge)\s+' + 'e' * 40 + r'|gh pr (?:checkout|merge) 52'})
                for command in ('git cherry-pick ' + 'e' * 40, 'git merge ' + 'e' * 40,
                                'gh pr checkout 52', 'gh pr merge 52'):
                    bad = json.loads(json.dumps(trace))
                    bad['events'].insert(-1, {'type': 'command', 'command': command, 'exit': 0})
                    self.assertFalse(evaluate(bad, held)['ok'])
                missing = json.loads(json.dumps(trace))
                missing['events'] = [e for e in missing['events'] if e['type'] != 'final']
                self.assertFalse(evaluate(missing, spec)['ok'])

    def test_push_local_scope_matrix_has_zero_sibling_actions(self):
        # Synthetic events, NOT measured host/model tool calls. The same local
        # invocation is independent of the number/state/location of siblings.
        spec = load(SPECS / 'push.json')
        for count in (0, 32):
            for scenario in ('dirty', 'locked', 'active', 'unique-commits',
                             'clean-invoking', 'linked-invoking', 'nested-sibling'):
                trace = load(TRACES / 'push-local-scope.json')
                siblings = [f'/fixture/out-of-scope/sibling-{i}' for i in range(count)]
                if scenario == 'linked-invoking':
                    siblings.append('/fixture/out-of-scope/canonical')
                if scenario == 'nested-sibling':
                    siblings.append('/fixture/invoking/nested-worker')
                trace['context'].update(unrelated_worktrees=count, scenario=scenario,
                                        out_of_scope=siblings, sibling_state=scenario)
                for event in trace['events']:
                    if 'worktree list' in event.get('command', ''):
                        event['stdout'] = 'worktree /fixture/invoking\n\n' + ''.join(
                            f'worktree {path}\n\n' for path in siblings)
                if scenario == 'clean-invoking':
                    trace['events'] = [e for e in trace['events'] if not (
                        e.get('type') == 'command' and
                        (' add ' in e['command'] or ' commit ' in e['command']))]
                    trace['events'][-1]['text'] = trace['events'][-1]['text'].replace(
                        'eligible edited.txt saved at ' + '1' * 40 + '.',
                        'none; invoking checkout clean.')
                elif scenario == 'linked-invoking':
                    trace['context']['invoking_checkout'] = '/fixture/invoking-linked'
                    for event in trace['events']:
                        if 'stdout' in event:
                            event['stdout'] = event['stdout'].replace(
                                '/fixture/invoking', '/fixture/invoking-linked')
                    trace['events'][-1]['text'] = trace['events'][-1]['text'].replace(
                        'Local scope: /fixture/invoking;', 'Local scope: /fixture/invoking-linked;')
                with self.subTest(count=count, scenario=scenario):
                    result = evaluate(trace, spec)
                    self.assertTrue(result['ok'], result['failures'])
                    # The scope guards themselves count zero, not merely an
                    # assertion that the final answer claimed no inspection.
                    guarded = [i for i, clause in enumerate(spec['forbid'])
                               if 'out-of-scope' in json.dumps(clause)
                               or 'nested-worker' in json.dumps(clause)
                               or 'worktree[_-]sweep' in clause.get('command', '')]
                    self.assertTrue(guarded, 'missing sibling/sweep guards')
                    self.assertEqual(sum(result['matched'][f'forbid[{i}]']
                                         for i in guarded), 0)
                    self.assertTrue(any('fetch team' in e.get('command', '')
                                        for e in trace['events']))

    def test_push_refuses_sibling_access_and_indirect_sweeps(self):
        # Known fixture roots and tip, not arbitrary path-role inference.
        spec = load(SPECS / 'push.json')
        commands = (
            'git -C /fixture/out-of-scope/sibling-0 status --porcelain',
            'git -C /fixture/out-of-scope/canonical diff',
            'stat /fixture/out-of-scope/sibling-0/src/parser.py',
            'ps aux | grep /fixture/out-of-scope/sibling-0',
            'cat /fixture/invoking/nested-worker/AGENTS.md',
            'find /fixture/invoking/nested-worker -type f',
            'git add -- nested-worker/src/parser.py',
            'git --literal-pathspecs add -- /fixture/invoking/nested-worker',
            'git add -- .', 'git add -A',
            'git merge --no-ff ' + '9' * 40,
            'git cherry-pick ' + '9' * 40,
            'python3 skills/git-commit-push/scripts/worktree_sweep.py /fixture/invoking',
            'python3 -c "import runpy; runpy.run_path(\'worktree_sweep.py\')"',
            'sh -c "python3 worktree_sweep.py /fixture/invoking"',
            '/git-commit-push all',
        )
        events = [{'type': 'command', 'command': cmd, 'exit': 0} for cmd in commands]
        for path in ('/fixture/out-of-scope/sibling-0/src/parser.py',
                     '/fixture/out-of-scope/canonical/AGENTS.md',
                     '/fixture/invoking/nested-worker/src/parser.py'):
            events.extend({'type': kind, 'path': path} for kind in ('read', 'write', 'edit'))
        for event in events:
            for wrapped in (False, True):
                trace = load(TRACES / 'push-local-scope.json')
                if wrapped:
                    kind = event['type']
                    event = {'type': 'tool', 'tool': 'bash' if kind == 'command' else kind,
                             'args': {k: v for k, v in event.items() if k != 'type'}}
                trace['events'].insert(-1, event)
                with self.subTest(event=event):
                    result = evaluate(trace, spec)
                    self.assertFalse(result['ok'], result)
                    self.assertTrue(any('forbidden action' in f for f in result['failures']))

    def test_push_requires_git_checkout_identity_and_local_scope_receipt(self):
        spec = load(SPECS / 'push.json')
        for missing in ('identity', 'scope', 'not-inspected'):
            trace = load(TRACES / 'push-local-scope.json')
            if missing == 'identity':
                trace['events'] = [e for e in trace['events']
                                   if '--show-toplevel' not in e.get('command', '')]
            else:
                phrase = 'Local scope:' if missing == 'scope' else 'other worktrees were not inspected'
                trace['events'][-1]['text'] = trace['events'][-1]['text'].replace(phrase, '')
            with self.subTest(missing=missing):
                result = evaluate(trace, spec)
                self.assertFalse(result['ok'])
                self.assertTrue(any('missing required' in f for f in result['failures']))

    def test_push_scope_cli_reports_refusal_and_repair(self):
        import subprocess
        command = [sys.executable, str(ROOT / 'scripts/skill_trace_eval.py'),
                   str(SPECS / 'push.json')]
        success = subprocess.run(command + [str(TRACES / 'push-local-scope.json')],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(success.returncode, 0, success.stderr)
        failure = subprocess.run(command + [str(TRACES / 'push-sibling-fail.json')],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(failure.returncode, 1, failure.stdout + failure.stderr)
        self.assertIn('forbidden action', failure.stdout)
        self.assertIn('nested-worker', failure.stdout)
        self.assertIn('worktree[_-]sweep', failure.stdout)
        # Repair the invocation scope, not the recorded evidence: a separate
        # conforming synthetic invocation passes. No history is rewritten.
        self.assertTrue(json.loads(success.stdout)['ok'])

    def test_push_read_only_fixture_rejects_fetch_without_running_it(self):
        # The existing grader has no conditional modes or semantic candidate engine.
        # Apply the existing read-only clauses to a push audit scenario explicitly.
        spec = load(SPECS / 'ponytail-review.json')
        spec['skill'] = 'push'
        trace = load(TRACES / 'push-read-only.json')
        self.assertTrue(evaluate(trace, spec)['ok'])
        for command in ('git fetch upstream', 'git -C . -c gc.auto=0 fetch upstream'):
            bad = json.loads(json.dumps(trace))
            bad['events'].insert(-1, {'type': 'command', 'command': command, 'exit': 0})
            self.assertFalse(evaluate(bad, spec)['ok'])

    def test_every_spec_has_a_passing_fixture(self):
        specs = sorted(SPECS.glob('*.json'))
        self.assertTrue(specs)
        for spec_path in specs:
            spec = load(spec_path)
            with self.subTest(skill=spec['skill']):
                trace = load(TRACES / f"{spec['skill']}-pass.json")
                result = evaluate(trace, spec)
                self.assertTrue(result['ok'], result['failures'])
                self.assertEqual(result['skill'], spec['skill'])

    def test_forbidden_write_fails_the_review_spec(self):
        result = evaluate(load(TRACES / 'ponytail-review-fail.json'),
                          load(SPECS / 'ponytail-review.json'))
        self.assertFalse(result['ok'])
        self.assertTrue(any('forbidden action' in failure for failure in result['failures']))

    def test_missing_required_check_fails(self):
        trace = load(TRACES / 'ponytail-review-pass.json')
        trace['events'] = [e for e in trace['events'] if e['type'] != 'final']
        result = evaluate(trace, load(SPECS / 'ponytail-review.json'))
        self.assertFalse(result['ok'])
        self.assertTrue(any('missing required' in failure for failure in result['failures']))

    def test_failed_validation_command_does_not_satisfy_requirement(self):
        trace = load(TRACES / 'docs-sync-pass.json')
        for event in trace['events']:
            if event['type'] == 'command':
                event['exit'] = 1
        result = evaluate(trace, load(SPECS / 'docs-sync.json'))
        self.assertFalse(result['ok'])
        self.assertTrue(any('missing required' in failure for failure in result['failures']))

    def test_delivery_trace_refuses_destructive_history(self):
        spec = load(SPECS / 'git-commit-push.json')
        for command in ('git reset --hard', 'git -C . push --force', 'git clean -fd'):
            trace = load(TRACES / 'git-commit-push-pass.json')
            trace['events'].insert(-1, {'type': 'command', 'command': command, 'exit': 0})
            with self.subTest(command=command):
                result = evaluate(trace, spec)
                self.assertFalse(result['ok'])
                self.assertTrue(any('forbidden action' in failure for failure in result['failures']))

    def test_edit_and_tool_wrapped_commit_are_refused(self):
        spec = load(SPECS / 'ponytail-review.json')
        base = load(TRACES / 'ponytail-review-pass.json')
        for extra in ({'type': 'edit', 'path': 'src/parser.py'},
                      {'type': 'tool', 'tool': 'bash', 'args': {'command': 'git -C . commit -m x'}}):
            trace = json.loads(json.dumps(base))
            trace['events'].insert(-1, extra)
            with self.subTest(extra=extra):
                result = evaluate(trace, spec)
                self.assertFalse(result['ok'])
                self.assertTrue(any('forbidden action' in failure for failure in result['failures']))

    def test_tool_wrapped_read_path_and_safe_git_log_pass(self):
        spec = load(SPECS / 'ponytail-review.json')
        trace = {'skill': 'ponytail-review', 'events': [
            {'type': 'tool', 'tool': 'read', 'args': {'path': 'src/parser.py'}},
            {'type': 'command', 'command': 'git log --grep commit', 'exit': 0},
            {'type': 'final', 'text': 'No findings.'},
        ]}
        self.assertTrue(evaluate(trace, spec)['ok'])

    def test_spec_typos_and_wrong_fields_are_refused(self):
        trace = {'skill': 'ponytail-review', 'events': []}
        for spec in (
                {'skill': 'ponytail-review', 'require': [{'event': 'read', 'pth': '*'}]},
                {'skill': 'ponytail-review', 'require': [{'event': 'read', 'exit': 0}]},
                {'skill': 'ponytail-review', 'require': [{'event': 'command', 'path': '*'}]},
                {'skill': 'ponytail-review', 'require': [
                    {'event': 'assistant', 'before_first': []}]},
                {'skill': 'ponytail-review', 'require': [
                    {'event': 'assistant', 'before_first': {'event': 'command', 'path': '*'}}]},
                {'skill': 'ponytail-review', 'require': [
                    {'event': 'assistant', 'before_first': {
                        'event': 'command', 'before_first': {'event': 'final'}}}]},
                {'skill': 'ponytail-review', 'forbid': [
                    {'event': 'assistant', 'before_first': {'event': 'command'}}]}):
            with self.subTest(spec=spec), self.assertRaises(TraceError):
                evaluate(trace, spec)

    def test_wrong_skill_and_malformed_trace_are_refused(self):
        spec = load(SPECS / 'ponytail-review.json')
        trace = load(TRACES / 'ponytail-review-pass.json')
        trace['skill'] = 'plan-for-me'
        result = evaluate(trace, spec)
        self.assertFalse(result['ok'])
        self.assertTrue(any('skill mismatch' in failure for failure in result['failures']))
        with self.assertRaises(TraceError):
            evaluate({'skill': 'ponytail-review', 'events': 'not a list'}, spec)

    def test_the_documented_cli_example_runs(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/skill_trace_eval.py'),
             str(SPECS / 'ponytail-review.json'), str(TRACES / 'ponytail-review-pass.json')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
