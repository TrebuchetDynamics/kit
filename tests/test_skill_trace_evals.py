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
        result = evaluate(load(TRACES / 'autowork-fail.json'),
                          load(SPECS / 'autowork.json'))
        self.assertFalse(result['ok'])
        self.assertTrue(any('missing required' in failure for failure in result['failures']))

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
        trace = {'skill': 'autowork', 'events': []}
        for spec in (
                {'skill': 'autowork', 'require': [{'event': 'read', 'pth': '*'}]},
                {'skill': 'autowork', 'require': [{'event': 'read', 'exit': 0}]},
                {'skill': 'autowork', 'require': [{'event': 'command', 'path': '*'}]}):
            with self.subTest(spec=spec), self.assertRaises(TraceError):
                evaluate(trace, spec)

    def test_wrong_skill_and_malformed_trace_are_refused(self):
        spec = load(SPECS / 'autowork.json')
        trace = load(TRACES / 'autowork-pass.json')
        trace['skill'] = 'plan-for-me'
        result = evaluate(trace, spec)
        self.assertFalse(result['ok'])
        self.assertTrue(any('skill mismatch' in failure for failure in result['failures']))
        with self.assertRaises(TraceError):
            evaluate({'skill': 'autowork', 'events': 'not a list'}, spec)

    def test_the_documented_cli_example_runs(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/skill_trace_eval.py'),
             str(SPECS / 'autowork.json'), str(TRACES / 'autowork-pass.json')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
