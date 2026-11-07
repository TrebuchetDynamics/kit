"""Fleet recovery points at pending task edits, not another copy of the answer."""
from dataclasses import replace
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi_autowork import fleet_view, task_snapshot


class DecisionHandoffTests(unittest.TestCase):
    def runner(self):
        row = task_snapshot.TaskRow('T-1', 'Task', 'Needs decision',
                                    'Waiting · Needs decision · Edit not committed', 'waiting',
                                    question=True, pending=True, bucket='Decision')
        snapshot = task_snapshot.TaskSnapshot('/repo', '/repo/.git', 'committed', 1, 100,
                                              rows=(row,), pending_paths=('tasks/items/T-1.md',),
                                              freshness='fresh', pending_at=time.time())
        return fleet_view.Runner('repo', repo='/repo', state='waiting on you', decisions=1,
                                 questions=[fleet_view.Question('T-1', 'decision', 1, 'Pick a scope')],
                                 snapshot=snapshot)

    def test_pending_question_points_to_handoff_without_changing_inventory(self):
        runner = self.runner()
        self.assertIn('review/commit', fleet_view.needs(runner))
        self.assertIn('T-1', fleet_view.needs(runner))
        self.assertEqual(runner.snapshot.rows[0].bucket, 'Decision')
        self.assertEqual(runner.questions[0].needs, 'Pick a scope')
        self.assertEqual(fleet_view.runner_display(runner)['needs'], fleet_view.needs(runner))

    def test_unknown_or_stale_edits_cannot_suppress_a_question(self):
        for changes in ({'pending_paths': None}, {'freshness': 'stale'}, {'pending_paths': ()},
                        {'pending_at': None}, {'pending_at': 0}, {'pending_at': time.time() + 60}):
            runner = self.runner()
            runner.snapshot = replace(runner.snapshot, **changes)
            self.assertIn('question', fleet_view.needs(runner))

    def test_stop_and_pause_reasons_still_take_priority(self):
        runner = self.runner()
        runner.stop_reason = 'startup refused'
        self.assertEqual(fleet_view.needs(runner), 'startup refused')
        runner.stop_reason, runner.state = '', 'paused'
        self.assertEqual(fleet_view.needs(runner), 'resume it')


if __name__ == '__main__':
    unittest.main()
