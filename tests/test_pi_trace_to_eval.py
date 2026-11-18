"""Pi JSONL to Tier 3 trace conversion without a model or repository write."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pi_trace_to_eval import convert  # noqa: E402
from skill_trace_eval import evaluate  # noqa: E402

CHECK = 'python3 scripts/check.py'
SUCCESS_SPEC = {'skill': 'fixture', 'require': [
    {'event': 'command', 'command': r'python3 scripts/check\.py', 'exit': 0},
]}


class PiTraceToEvalTests(unittest.TestCase):
    def convert_command(self, command, structured, tool='bash'):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.jsonl'
            sentinel = Path(temporary) / 'must-not-exist'
            command = command.replace('SENTINEL', str(sentinel))
            records = [
                {'type': 'tool_execution_start', 'toolCallId': 'check', 'toolName': tool,
                 'args': {'command': command}},
                {'type': 'tool_execution_end', 'toolCallId': 'check',
                 'result': {'structuredContent': structured}},
            ]
            original = ('\r\n'.join(json.dumps(record) for record in records) + '\r\n').encode()
            path.write_bytes(original)
            trace = convert(path, 'fixture')
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(sentinel.exists(), 'conversion must never execute recorded commands')
        return trace

    def test_aggregate_success_never_proves_ambiguous_check_success(self):
        commands = [
            f'{CHECK} || true',
            f'{CHECK}; true',
            f'false && {CHECK}',
            f'{CHECK} | cat',
            f'{CHECK}\ntrue',
            f"bash -c '{CHECK}'",
            f"/bin/sh -ec '{CHECK}'",
            f"env bash -lc '{CHECK}'",
            f'({CHECK})',
            f'[[ -n "{CHECK}" ]]',
            f'{{ {CHECK}; }}',
            f'echo $({CHECK})',
            f'echo `{CHECK}`',
            f'{CHECK} > output.txt',
            f'{CHECK} &',
            f'{CHECK} # comment',
            f'{CHECK} \\\n--verbose',
            f'{CHECK} <<EOF\nexample only\nEOF',
            f"{CHECK} --label 'quoted || operator'",
            f"eval '{CHECK}'",
            f'. {CHECK}',
            f'! {CHECK}',
            f'coproc {CHECK}',
            f"{CHECK} 'unterminated",
            f'{CHECK} || true; touch SENTINEL',
        ]
        for tool in ('bash', 'shell'):
            for command in commands:
                with self.subTest(tool=tool, command=command):
                    trace = self.convert_command(command, {'exit_code': 0}, tool)
                    verdict = evaluate(trace, SUCCESS_SPEC)
                    self.assertFalse(verdict['ok'], verdict)
                    self.assertTrue(any('missing required:' in failure
                                        for failure in verdict['failures']))
                    events = [e for e in trace['events'] if e['type'] == 'command']
                    self.assertTrue(events)
                    for event in events:
                        self.assertNotIn('exit', event)
                        self.assertNotIn('result', event)
                        self.assertEqual(event['aggregate_exit_code'], 0)

    def test_simple_command_exact_exit_and_unknown_status(self):
        for structured, expected in [
            ({'exit_code': 0}, 0), ({'exit_code': 1}, 1),
            ({}, None), ({'exit_code': None}, None),
            ({'exit_code': False}, None), ({'exit_code': True}, None),
            ({'exit_code': '0'}, None), ({'exit_code': 0.0}, None),
            ({'exit_code': []}, None), (None, None),
        ]:
            with self.subTest(structured=structured):
                trace = self.convert_command(CHECK, structured)
                event, = trace['events']
                self.assertEqual(event['command'], CHECK)
                if expected is None:
                    self.assertNotIn('exit', event)
                else:
                    self.assertEqual(event['exit'], expected)
                    self.assertIs(type(event['exit']), int)
                verdict = evaluate(trace, SUCCESS_SPEC)
                self.assertEqual(verdict['ok'], expected == 0)

    def test_simple_arguments_and_assignments_keep_success_evidence(self):
        for command in (CHECK, f"{CHECK} --label 'ordinary argument'", f'CI=1 {CHECK}'):
            with self.subTest(command=command):
                trace = self.convert_command(command, {'exit_code': 0})
                self.assertTrue(evaluate(trace, SUCCESS_SPEC)['ok'])
                self.assertEqual(trace['events'][0]['exit'], 0)

    def test_ambiguous_status_remains_provenance_and_forbidden_text_is_visible(self):
        spec = {'skill': 'fixture', 'forbid': [
            {'event': 'command', 'command': r'git commit'},
        ]}
        for status in (0, 1, None, False, '0'):
            for command in ('git commit -m fixture || true', "sh -c 'git commit -m fixture'"):
                with self.subTest(status=status, command=command):
                    trace = self.convert_command(command, {'exit_code': status})
                    verdict = evaluate(trace, spec)
                    self.assertFalse(verdict['ok'])
                    self.assertTrue(any('forbidden action:' in failure
                                        for failure in verdict['failures']))
                    for event in trace['events']:
                        self.assertNotIn('exit', event)
                        if type(status) is int:
                            self.assertEqual(event['aggregate_exit_code'], status)
                        else:
                            self.assertNotIn('aggregate_exit_code', event)

    def test_planner_chat_preview_survives_conversion_in_attempt_order(self):
        preview = 'Plan preview — OWNER/REPO: P1 proposed, not published; parser fix and regression.'
        def assistant(text, part_type='text', role='assistant'):
            return {'type': 'message_end', 'message': {
                'role': role, 'content': [{'type': part_type, part_type: text}]}}

        apply = 'python3 scripts/github_issues.py --repo OWNER/REPO --batch /tmp/batch.json --apply'
        read = [
            {'type': 'tool_execution_start', 'toolCallId': 'read', 'toolName': 'read',
             'args': {'path': 'src/parser.py'}},
            {'type': 'tool_execution_end', 'toolCallId': 'read', 'result': {}},
        ]
        start = {'type': 'tool_execution_start', 'toolCallId': 'apply', 'toolName': 'bash',
                 'args': {'command': apply}}
        end = {'type': 'tool_execution_end', 'toolCallId': 'apply',
               'result': {'structuredContent': {'exit_code': 0}, 'text': preview}}
        for skill in ('plan-with-me', 'plan-for-me'):
            spec = json.loads((ROOT / f'evals/tier3/{skill}.json').read_text())
            for scenario, middle, expected in (
                    ('visible', [assistant(preview), start, end], True),
                    ('after-attempt-start', [start, assistant(preview), end], False),
                    ('unfinished-first-attempt', [{**start, 'toolCallId': 'early'},
                                                  assistant(preview), start, end], False),
                    ('thinking-only', [assistant(preview, 'thinking'), start, end], False),
                    ('user-only', [assistant(preview, role='user'), start, end], False),
                    ('tool-output-only', [start, end], False),
                    ('final-only', [start, end, assistant(preview)], False)):
                with self.subTest(skill=skill, scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / 'trace.jsonl'
                    records = read + middle
                    if scenario != 'final-only':
                        records.append(assistant('Published issue 1; live delivery unverified.'))
                    path.write_text('\n'.join(json.dumps(record) for record in records))
                    trace = convert(path, skill)
                    result = evaluate(trace, spec)
                    self.assertEqual(result['ok'], expected, result)
                    if expected:
                        self.assertEqual([e['type'] for e in trace['events']],
                                         ['read', 'assistant', 'command', 'final'])
                        self.assertEqual(trace['events'][1]['text'], preview)

    def test_tool_wrapper_and_heredoc_are_converted_without_false_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'trace.jsonl'
            records = [
                {'type': 'tool_execution_start', 'toolCallId': '1', 'toolName': 'bash',
                 'args': {'command': "cat src/a.py | head\npython3 - <<'E'\nprint('git commit')\nE"}},
                {'type': 'tool_execution_end', 'toolCallId': '1',
                 'result': {'structuredContent': {'exit_code': 0}}},
                {'type': 'message_end', 'message': {
                    'role': 'assistant', 'provider': 'fixture', 'model': 'fixture',
                    'content': [{'type': 'text', 'text': 'No findings.'}]}},
            ]
            path.write_text('\n'.join(json.dumps(record) for record in records) + '\n')
            trace = convert(path, 'ponytail-review', 'live-fixture')
        commands = [event['command'] for event in trace['events'] if event['type'] == 'command']
        self.assertTrue(any('cat src/a.py' in command for command in commands))
        self.assertFalse(any('git commit' in command for command in commands))
        self.assertTrue(any(event['type'] == 'read' and event['path'] == 'src/a.py'
                            for event in trace['events']))
        self.assertEqual(trace['events'][-1], {'type': 'final', 'text': 'No findings.'})
        self.assertEqual(trace['model'], 'fixture/fixture')


if __name__ == '__main__':
    unittest.main()
