"""Static scheduling boundaries; no live scheduler or model execution."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScheduledProgressTests(unittest.TestCase):
    def test_compatibility_command_never_starts_a_scheduler(self):
        policy = (ROOT / 'skills/autowork/SKILL.md').read_text()
        self.assertIn('never starts, resumes, installs or schedules', policy)
        self.assertIn('Orbi remains paused', policy)
        self.assertIn('live-unqualified', policy)
        self.assertNotIn('references/scheduled-policy.md', policy)

    def test_recovery_preserves_pauses_and_actual_progress_evidence(self):
        policy = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for phrase in ('actual ownership', 'Preserve existing tasks, worktrees, attempts',
                       'do not claim success', 'bounded wait',
                       'No work resumed.', 'explicit pause'):
            self.assertIn(phrase, policy)

    def test_installation_does_not_rewire_preserved_jobs(self):
        policy = (ROOT / 'docs/installation.md').read_text()
        self.assertIn('Existing jobs, IDs, schedules, pause state', policy)
        self.assertIn('Do not rewire legacy executor jobs', policy)
        self.assertIn('never legacy Autowork runners', policy)


if __name__ == '__main__':
    unittest.main()
