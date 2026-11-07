"""Static Unblock scope contracts; not proof of model recovery or service health."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UnblockSkillTests(unittest.TestCase):
    def test_recovery_has_a_default_target_and_an_explicit_fleet_scope(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        self.assertIn('current repository', text)
        self.assertIn('all', text)
        for contract in ('healthy runners are read-only', 'does not invoke recovery',
                         'without an', 'interview', 'Standing policy:',
                         'Observe the expected transition', 'do not claim success',
                         'do not loop unchanged retries', 'Do not create backlog work'):
            self.assertIn(contract, text)
        for forbidden in ('assume all owner approvals', 'clear every hold', 'disable required checks'):
            self.assertNotIn(forbidden, text)

    def test_waits_are_blocked_outcomes_not_successful_recovery(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for contract in ('**Recovered** only', '**Idle** only', '**Blocked**',
                         'No work resumed.', 'smallest concrete question',
                         'unfinished recovery', 'then inspect consumption',
                         'a planning closure or an evidenced wait is not recovery'):
            self.assertIn(contract, text)
        self.assertNotIn('or has an evidenced wait, external gate or ownership limit', text)

    def test_service_branch_preserves_pauses_jobs_and_interruption_authority(self):
        text = (ROOT / 'skills/unblock/references/services.md').read_text()
        for contract in ('deliberate-stop', 'pending service jobs',
                         'autowork restart TARGET', 'before any',
                         'Observe an existing restart', '--stop-workers --now',
                         'requires explicit user authorization', 'actual executable release',
                         'updating a shared package can affect runners outside'):
            self.assertIn(contract, text)
        self.assertIn('No Hermes runtime', (ROOT / 'adapters/skills/unblock/SKILL.md').read_text())

    def test_workflow_and_service_reference_links_exist(self):
        for name in ('skills/unblock/SKILL.md', 'skills/unblock/references/services.md',
                     'adapters/skills/unblock/SKILL.md'):
            source = ROOT / name
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', source.read_text()):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((source.parent / link.split('#')[0]).is_file(), (name, link))


if __name__ == '__main__':
    unittest.main()
