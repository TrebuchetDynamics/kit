"""Static recovery boundaries, not proof of model recovery or service health."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UnblockSkillTests(unittest.TestCase):
    def test_recovery_targets_github_without_reviving_executor(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for contract in ('current repository', 'GitHub Issues', 'actual ownership',
                         'does not invoke recovery', 'Standing policy:',
                         'Observe the expected transition', 'do not claim success',
                         'do not loop unchanged retries', 'Do not create backlog work',
                         'Orbi remains paused and live-unqualified'):
            self.assertIn(contract, text)
        self.assertNotIn('autowork tasks', text)
        self.assertNotIn('autowork restart', text)

    def test_waits_are_not_successful_recovery(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for contract in ('**Recovered** only', '**Idle** only', '**Blocked**',
                         'No work resumed.', 'smallest concrete question',
                         'unfinished recovery', 'then inspect consumption'):
            self.assertIn(contract, text)
        self.assertIn('A planning closure or an evidenced wait is not recovery', text)

    def test_service_boundary_preserves_pauses_jobs_and_evidence(self):
        text = (ROOT / 'skills/unblock/references/services.md').read_text()
        for contract in ('deliberate-stop', 'pending service jobs',
                         'Observe an existing restart', 'explicit user authorization',
                         'actual executable release', 'attempts/recovery state',
                         'Do not reinstall or', 'Orbi remains paused'):
            self.assertIn(contract, text)
        self.assertNotIn('autowork restart', text)
        self.assertIn('No Hermes runtime', (ROOT / 'adapters/skills/unblock/SKILL.md').read_text())

    def test_workflow_reference_links_exist(self):
        for name in ('skills/unblock/SKILL.md', 'skills/unblock/references/services.md',
                     'adapters/skills/unblock/SKILL.md'):
            source = ROOT / name
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', source.read_text()):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((source.parent / link.split('#')[0]).is_file(), (name, link))


if __name__ == '__main__':
    unittest.main()
