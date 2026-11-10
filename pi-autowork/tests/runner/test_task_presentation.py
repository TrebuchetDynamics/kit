"""Task presentation is a projection, not admission or verification authority."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'pi-autowork'))
from pi_autowork import task_status as task_presentation


class PresentationTests(unittest.TestCase):
    def record(self, status='open', section='Now', closure=None):
        return SimpleNamespace(status=status, section=section, closure_info=closure)

    def test_semantics_do_not_depend_on_prose(self):
        self.assertEqual(task_presentation.task(self.record())['tone'], 'neutral')
        self.assertEqual(task_presentation.task(self.record(section='Needs decision'))['tone'], 'warning')
        self.assertEqual(task_presentation.task(self.record(), 'DEPENDENCY_UNFINISHED')['tone'], 'warning')
        self.assertEqual(task_presentation.task(self.record(status='running'))['tone'], 'neutral')

    def test_closure_tone_uses_evidence_not_a_verified_word(self):
        self.assertEqual(task_presentation.task(self.record('done', closure={
            'label': 'verified', 'provenance': 'coordinator_verified', 'evidence_valid': False
        }))['closure_tone'], 'warning')
        self.assertEqual(task_presentation.task(self.record('done', closure={
            'provenance': 'coordinator_verified', 'evidence_valid': True
        }))['closure_tone'], 'success')
        self.assertEqual(task_presentation.task(self.record('done'))['closure_tone'], 'neutral')

    def test_feedback_contains_no_execution_grants(self):
        for state in ('clean', 'pending_commit', 'committed'):
            result = task_presentation.edit_lifecycle(state)
            self.assertEqual(set(result), {'state', 'message'})
            self.assertEqual(result['state'], state)
        with self.assertRaises(ValueError):
            task_presentation.edit_lifecycle('running')


if __name__ == '__main__':
    unittest.main()
