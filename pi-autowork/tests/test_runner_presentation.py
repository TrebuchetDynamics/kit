"""Captured runner presentation: no new inventory or execution authority."""
import contextlib
import io
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi_autowork import command, fleet_view as view, task_snapshot


class RunnerPresentationTests(unittest.TestCase):
    def runner(self, **changes):
        snap = task_snapshot.TaskSnapshot('/repo', '/repo/.git', 'current', 8, 100,
                                         counts=(0, 0, 0, 0, 0, 0), freshness='fresh',
                                         engine_freshness='fresh')
        questions = [view.Question(f'Q-{i}', 'small', 0, 'choose an option') for i in range(3)]
        return view.Runner('repo', state='working', snapshot=snap, questions=questions, **changes)

    def test_same_capture_has_one_runner_label(self):
        runner = self.runner()
        cases = [(runner, 'Blocked'),
                 (replace(runner, state='paused'), 'Paused'),
                 (replace(runner, state='not running'), 'Not running'),
                 (replace(runner, questions=[]), 'Idle'),
                 (replace(runner, snapshot=replace(runner.snapshot, counts=None, freshness='unavailable')),
                  'Task inventory unavailable'),
                 (replace(runner, snapshot=replace(runner.snapshot, freshness='stale')),
                  'Blocked'),
                 (replace(runner, job={'role': 'maintainer'}), 'Working')]
        row = task_snapshot.TaskRow('T-1', 'Task', 'Next', 'Active · Verifying', 'working', bucket='Active')
        review = replace(runner, lanes=[view.Lane('T-1', 'verifying')],
                         snapshot=replace(runner.snapshot, rows=(row,), counts=(1, 0, 0, 0, 0, 1),
                                          joined_lanes=(('T-1', 1, 'verifying'),)))
        cases.append((review, 'Working'))
        for captured, expected in cases:
            with self.subTest(expected=expected, state=captured.state):
                result = view.presentation(captured)
                self.assertEqual(result.label, expected)
                self.assertEqual(view.runner_rows([captured])[0]['State'], (expected, result.style))
                self.assertEqual(view.verdict(captured),
                                 (result.label + (' — ' + result.explanation if result.explanation else ''), result.style))
                self.assertEqual(result.counts, view.task_counts(captured))
                self.assertEqual(result.inventory_freshness, captured.snapshot.freshness)
                self.assertEqual(result.questions, 3 if captured.questions else 0)
        self.assertEqual(view.presentation(review).activity[0].phase, 'verifying')
        self.assertEqual(view.presentation(runner).activity, ())
        self.assertEqual(runner.state, 'working')
        with self.assertRaises(FrozenInstanceError):
            view.presentation(runner).label = 'invented'

    def test_blocked_reason_not_age_distinguishes_owner_repair_and_capacity(self):
        runner = self.runner()
        owner = view.presentation(runner)
        self.assertIn('Needs your action:', owner.explanation)
        for state, minutes in (('blocked', 1), ('stalled', 480)):
            row = task_snapshot.TaskRow('T-1', 'Task', 'Next', 'Blocker · Agent repair',
                                        'held', bucket='Blocker')
            captured = replace(runner, state=state, minutes=minutes, questions=[],
                               snapshot=replace(runner.snapshot, rows=(row,), counts=(0, 0, 0, 1, 0, 1)))
            shown = view.presentation(captured)
            self.assertEqual(shown.label, 'Blocked')
            self.assertIn('Needs repair:', shown.explanation)
            self.assertEqual(captured.state, state)
        mixed = replace(captured, questions=runner.questions)
        self.assertIn('needs your action:', view.presentation(mixed).explanation)
        self.assertIn('Needs repair:', view.presentation(mixed).explanation)
        capacity = replace(runner, questions=[], state=view.health.HOST_WAIT,
                           gate='memory below the required threshold',
                           snapshot=replace(runner.snapshot, counts=(0, 0, 1, 0, 0, 1)))
        shown = view.presentation(capacity)
        self.assertEqual(shown.label, 'Blocked')
        self.assertIn('Waiting for capacity: memory', shown.explanation)
        self.assertEqual(view.summary([captured, mixed]), [('blocked', 2)])
        self.assertEqual(view.state_label(runner), 'blocked')
        owner_row = replace(row, state='Blocker · Needs you', question=True)
        owner_hold = replace(runner, snapshot=replace(runner.snapshot, rows=(owner_row,),
                                                      counts=(0, 0, 0, 1, 0, 1)))
        shown = view.presentation(owner_hold)
        self.assertIn('Needs your action:', shown.explanation)
        self.assertNotIn('Needs repair:', shown.explanation)
        root = dict(id='T-2', kind='held', cause='validation', blocks=1,
                    resolution_owner='AGENT_REPAIR')
        dependency = replace(row, state='Blocker', why='dependency cycle')
        mixed_dependency = replace(owner_hold, repair_roots=[root],
                                   snapshot=replace(owner_hold.snapshot, rows=(dependency,)))
        self.assertIn('Needs repair:', view.presentation(mixed_dependency).explanation)
        legacy = replace(runner, snapshot=None, state='stalled',
                         held=[('T-2', 'validation')],
                         waiting_groups=[dict(label='owner action', count=1)])
        self.assertIn('Needs repair:', view.verdict(legacy)[0])
        self.assertIn('needs your action:', view.verdict(legacy)[0])
        self.assertNotIn('repair_roots', command.runner_json(mixed_dependency))

    def test_cli_uses_captured_state_and_keeps_raw_json(self):
        runner = self.runner()
        for long in (False, True):
            output = io.StringIO()
            with mock.patch.object(command, 'runners', return_value=[runner]), \
                    contextlib.redirect_stdout(output):
                self.assertEqual(command.cmd_ls(SimpleNamespace(json=False, long=long), None), 0)
            text = output.getvalue()
            self.assertIn('1 blocked', text)
            self.assertIn('Blocked — Needs your action:', text)
            self.assertNotIn('1 working', text)
            self.assertEqual(command.runner_json(runner)['state'], 'working')
        self.assertEqual(view.health.display_state('stalled'), 'blocked')
        self.assertEqual(view.health.display_state(view.health.HOST_WAIT), 'blocked')
        self.assertEqual(view.health.display_state('not cycling'), 'not cycling')

    def test_diagnostics_preserve_evidence_without_warning_inflation(self):
        runner = self.runner(acquisition_errors=['pending: read failed', 'pending: read failed'])
        annotations = ('T-9: unmatched execution observation (integrated)',) * 2 + (
            'T-10: unmatched slot activity (running); not inventory evidence',
            'session revision old; canonical revision current',
            'legacy execution observations: contract identity unknown')
        runner.snapshot = replace(runner.snapshot, errors=('pending: read failed', 'inventory: unreadable'),
                                  annotations=annotations)
        runner.lanes = [view.Lane('T-9', 'integrated'), view.Lane('T-10', 'running')]
        result = view.presentation(runner)
        self.assertEqual((result.error_count, result.source_note_count), (2, 4))
        errors = [g for g in result.diagnostics if g.kind == 'error']
        notes = [g for g in result.diagnostics if g.kind == 'source']
        self.assertEqual(tuple(message for g in errors for message in g.originals),
                         (*runner.snapshot.errors, *runner.acquisition_errors))
        self.assertCountEqual([message for g in notes for message in g.originals], annotations)
        self.assertEqual({task for g in notes for task in g.affected_ids}, {'T-9', 'T-10'})
        self.assertEqual((result.counts[0], result.counts[1], result.activity), (0, 0, ()))
        self.assertEqual(result.label, 'Blocked')
        runner.acquisition_errors.append('later mutation')
        self.assertEqual(result.error_count, 2)

    def test_projection_uses_only_captured_inputs(self):
        runner = self.runner()
        runner.repo = '/captured/repo'
        with mock.patch.object(Path, 'is_dir', side_effect=AssertionError('filesystem read')), \
                mock.patch.object(view.task_prepare, 'prepare', side_effect=AssertionError('setup probe')), \
                mock.patch.object(view.main_check, 'alive', side_effect=AssertionError('process read')):
            self.assertEqual(view.presentation(runner).label, 'Blocked')
            runner.prepare_state = 'invalid'
            self.assertEqual(view.presentation(runner).label, 'Task store needs repair')
        with self.assertRaisesRegex(ValueError, 'captured task snapshot'):
            view.presentation(view.Runner('uncaptured'))

    def test_superseded_check_is_separate_from_worker_activity(self):
        receipt = dict(state='running', rev='older-revision', main_head='current-revision',
                       started=100, pid=22, start_time='ticks', check_slot={'state': 'running', 'started': 120})
        runner = self.runner(main_check=receipt)
        with mock.patch.object(view.main_check, 'alive', return_value=True):
            original_line = view.main_check.line(receipt, now=720)
            result = view.presentation(runner)
            self.assertEqual(view.main_check.line(receipt, now=720), original_line)
        check = result.main_check
        self.assertEqual((check.state, check.checked_revision, check.current_revision, check.started,
                          check.execution_started, check.superseded),
                         ('running', 'older-revision', 'current-revision', 100, 120, True))
        self.assertIn('(10m)', original_line)
        self.assertIn('superseded by main', original_line)
        self.assertNotIn('passed', original_line)
        self.assertEqual((result.label, result.counts[0], result.activity), ('Blocked', 0, ()))
        receipt['check_slot']['started'] = 999
        self.assertEqual(check.execution_started, 120)
        self.assertEqual(result.captured_at, 100)


if __name__ == '__main__':
    unittest.main()
