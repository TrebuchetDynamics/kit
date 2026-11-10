"""Bounded action-first fleet acceptance, using pinned offline Textual."""
from pathlib import Path
import subprocess
import unittest


class OperationsTests(unittest.TestCase):
    def pilot(self, case):
        result = subprocess.run(
            ['uv', 'run', '--offline', '--quiet', '--no-project', '--with', 'textual==8.2.8',
             'python3', str(Path(__file__).with_name('tui_operations_pilot.py')), case],
            capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('OPERATIONS OK', result.stdout)

    def test_action_first_fleet_matches_captured_truth(self):
        self.pilot('truth')

    def test_compact_evidence_is_truthful_and_reachable(self):
        self.pilot('evidence')

    def test_input_and_identity_survive_slow_reads(self):
        self.pilot('input')


if __name__ == '__main__':
    unittest.main()
