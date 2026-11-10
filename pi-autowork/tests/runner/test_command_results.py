"""Command-result meaning without Textual, process execution or task mutations."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import command_results, task_status


class CommandResultsTests(unittest.TestCase):
    def interpret(self, argv, stdout='', stderr='', code=0):
        result = subprocess.CompletedProcess(argv, code, stdout, stderr)
        return command_results.interpret(['autowork', *argv], 'Run action', result)

    def test_generic_output_and_warning_success(self):
        for stdout, stderr, expected in (
                ('first\nlast\n', '', 'last'),
                ('', 'warning\n', 'warning'),
                ('result\n', 'warning\n', 'warning'),
                ('', '', 'Run action')):
            with self.subTest(stdout=stdout, stderr=stderr):
                outcome = self.interpret(['stop', 'repo'], stdout, stderr)
                self.assertEqual(outcome, command_results.Outcome(True, expected, False))

    def test_failed_command_does_not_claim_a_commit(self):
        outcome = self.interpret(['tasks', 'decide', 'T-1', '--commit'],
                                 stdout='not a receipt\n', stderr='commit failed', code=1)
        self.assertEqual(outcome, command_results.Outcome(False, 'commit failed', True))

    def test_execution_exception_keeps_message_and_decision_kind(self):
        for argv, decision in ((['stop', 'repo'], False), (['tasks', 'decide'], True)):
            outcome = command_results.interpret(['autowork', *argv], 'Run action', OSError('unavailable'))
            self.assertEqual(outcome, command_results.Outcome(False, 'unavailable', decision))

    def test_malformed_custom_process_result_remains_a_failure(self):
        class UnreadableResult:
            @property
            def stdout(self):
                raise OSError('output unavailable')
        outcome = command_results.interpret(['autowork', 'tasks', 'decide'], 'Answer', UnreadableResult())
        self.assertEqual(outcome, command_results.Outcome(False, 'output unavailable', True))

    def test_pending_answer_uses_existing_lifecycle(self):
        outcome = self.interpret(['tasks', 'decide', 'T-1'], stdout='ok')
        self.assertEqual(outcome, command_results.Outcome(
            True, task_status.edit_lifecycle('pending_commit')['message'], True))

    def test_committed_answer_requires_receipt(self):
        lifecycle = task_status.edit_lifecycle('committed')
        for argv in (['tasks', 'decide', 'T-1', '--commit'],
                     ['tasks', 'field', 'T-1', 'Owner decision', 'answer', '--commit']):
            with self.subTest(argv=argv):
                outcome = self.interpret(argv, stdout=json.dumps({'lifecycle': lifecycle}))
                self.assertEqual(outcome, command_results.Outcome(True, lifecycle['message'], True))

    def test_detached_save_receipts_require_decide_opt_in_and_saved_paths(self):
        decide = ['tasks', 'decide', 'T-1', '--commit']
        field = ['tasks', 'field', 'T-1', 'Owner decision', 'answer', '--commit']
        for state, files in (('pending_commit', ['tasks/items/T-1.md']), ('clean', [])):
            receipt = dict(lifecycle=task_status.edit_lifecycle(state), files=files, commit=None)
            for argv, expected in ((decide, False), (decide + ['--save-if-detached'], True),
                                   (field + ['--save-if-detached'], False)):
                with self.subTest(state=state, argv=argv):
                    outcome = self.interpret(argv, stdout=json.dumps(receipt))
                    self.assertEqual(outcome.ok, expected)
                    if expected:
                        self.assertEqual(outcome.message, task_status.edit_lifecycle(state)['message'])
                        self.assertNotIn('committed locally', outcome.message)
            for invalid in ({**receipt, 'commit': 'invented'}, {**receipt, 'files': None},
                            {**receipt, 'files': [] if files else ['tasks/items/T-1.md']},
                            {**receipt, 'files': ['not-a-task']},
                            {**receipt, 'lifecycle': {'state': state}}):
                with self.subTest(invalid=invalid):
                    self.assertFalse(self.interpret(decide + ['--save-if-detached'],
                                                    stdout=json.dumps(invalid)).ok)

    def test_invalid_receipts_keep_draft_and_refuse_success(self):
        for receipt in ('not json', '{}', 'null', '[]',
                        '{"lifecycle": null}', '{"lifecycle": {"state": "committed"}}',
                        json.dumps({'lifecycle': task_status.edit_lifecycle('pending_commit')})):
            with self.subTest(receipt=receipt):
                outcome = self.interpret(['tasks', 'decide', 'T-1', '--commit'], stdout=receipt)
                self.assertEqual(outcome, command_results.Outcome(
                    False, 'Answer commit not confirmed; inspect tasks handoff before retrying. Draft kept.', True))

    def test_other_task_commands_keep_generic_result_semantics(self):
        for argv in (['tasks', 'commit'], ['tasks', 'delete', 'T-1'],
                     ['tasks', 'field', 'T-1', 'rank', '1000']):
            with self.subTest(argv=argv):
                self.assertEqual(self.interpret(argv, stdout='ok'), command_results.Outcome(True, 'ok', False))

    def test_imports_with_presentation_modules_unavailable(self):
        code = '''import importlib.abc, sys
class NoPresentation(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('textual', 'rich') or fullname.startswith('pi_autowork.tui'):
            raise ImportError('presentation unavailable: ' + fullname)
sys.meta_path.insert(0, NoPresentation())
from pi_autowork import command_results
assert command_results.interpret(['autowork', 'ls'], 'List', OSError('unavailable')).ok is False
'''
        result = subprocess.run([sys.executable, '-B', '-c', code],
                                cwd=Path(__file__).resolve().parents[2],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
