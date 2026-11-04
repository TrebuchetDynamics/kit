"""Pi JSONL to Tier 3 trace conversion without a model or repository write."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pi_trace_to_eval import convert  # noqa: E402


class PiTraceToEvalTests(unittest.TestCase):
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
