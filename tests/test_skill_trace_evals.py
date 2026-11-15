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


class SkillTraceEvalTests(unittest.TestCase):
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
