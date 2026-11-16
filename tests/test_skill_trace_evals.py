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


def publication_trace(skill):
    return {'skill': skill, 'events': [
        {'type': 'tool', 'tool': 'read', 'path': 'src/parser.py'},
        {'type': 'command', 'command': 'python3 scripts/github_issues.py '
         '--repo OWNER/REPO --batch /tmp/batch.json --apply', 'exit': 0},
        {'type': 'final', 'text': 'Published https://github.com/OWNER/REPO/issues/1; '
         'ready, no dependencies. Helper readback succeeded; live delivery unverified.'},
    ]}


class SkillTraceEvalTests(unittest.TestCase):
    def test_planning_helper_publication_passes_without_local_task_write(self):
        for skill in PLANNERS:
            with self.subTest(skill=skill):
                result = evaluate(publication_trace(skill), load(SPECS / f'{skill}.json'))
                self.assertTrue(result['ok'], result['failures'])

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
            for missing in (0, 2):
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
                trace['events'][1] = {'type': 'command', 'command': command}
                if status is not None:
                    trace['events'][1]['exit'] = status
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
                        publication_trace(skill)['events'][1]['command'] + ' ' + help_arg):
                    trace = publication_trace(skill)
                    trace['events'][1]['command'] = command
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
            'systemctl restart pi-autowork.service',
            'launchctl bootstrap gui/1000 /tmp/orbi.plist',
            'launchctl kickstart gui/1000/orbi', 'launchctl load /tmp/worker.plist',
            'orbi start', 'orbi setup --config /tmp/orbi.toml',
            'orbi install-units --config /tmp/orbi.toml',
            'pi-autowork start', 'pi-autowork run', 'pi-autowork resume',
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
            trace['events'][1] = {
                'type': 'tool', 'tool': 'bash',
                'args': {'command': trace['events'][1]['command']},
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
            trace['events'][1] = {'type': 'write', 'path': 'tasks/items/PLAN-1.md'}
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
                        ({'type': 'command', 'command': 'python3 scripts/github_issues.py '
                          '--repo OWNER/REPO --batch /tmp/batch.json', 'exit': 0},
                         'missing required'),
                        ({'type': 'edit', 'path': 'src/parser.py'}, 'forbidden action')):
                    trace = publication_trace(skill)
                    if event['type'] == 'command':
                        trace['events'][1] = event
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
                {'skill': 'ponytail-review', 'require': [{'event': 'command', 'path': '*'}]}):
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
