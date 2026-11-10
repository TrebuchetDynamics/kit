"""Captured runner presentation: no new inventory or execution authority."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import fleet_view as view, task_snapshot


class RunnerPresentationTests(unittest.TestCase):
    def runner(self, **changes):
        snap = task_snapshot.TaskSnapshot('/repo', '/repo/.git', 'current', 8, 100,
                                         counts=(0, 0, 0, 0, 0, 0), freshness='fresh',
                                         engine_freshness='fresh')
        questions = [view.Question(f'Q-{i}', 'small', 0, 'choose an option') for i in range(3)]
        return view.Runner('repo', state='working', snapshot=snap, questions=questions, **changes)

    def test_same_capture_has_one_runner_label(self):
        runner = self.runner()
        cases = [(runner, 'Waiting on you'),
                 (replace(runner, state='paused'), 'Paused'),
                 (replace(runner, state='not running'), 'Not running'),
                 (replace(runner, questions=[]), 'Idle'),
                 (replace(runner, snapshot=replace(runner.snapshot, counts=None, freshness='unavailable')),
                  'Task inventory unavailable'),
                 (replace(runner, snapshot=replace(runner.snapshot, freshness='stale')),
                  'Waiting on you'),
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
        self.assertEqual(result.label, 'Waiting on you')
        runner.acquisition_errors.append('later mutation')
        self.assertEqual(result.error_count, 2)

    def test_projection_uses_only_captured_inputs(self):
        runner = self.runner()
        runner.repo = '/captured/repo'
        with mock.patch.object(Path, 'is_dir', side_effect=AssertionError('filesystem read')), \
                mock.patch.object(view.task_prepare, 'prepare', side_effect=AssertionError('setup probe')), \
                mock.patch.object(view.main_check, 'alive', side_effect=AssertionError('process read')):
            self.assertEqual(view.presentation(runner).label, 'Waiting on you')
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
        self.assertEqual((result.label, result.counts[0], result.activity), ('Waiting on you', 0, ()))
        receipt['check_slot']['started'] = 999
        self.assertEqual(check.execution_started, 120)
        self.assertEqual(result.captured_at, 100)


if __name__ == '__main__':
    unittest.main()
