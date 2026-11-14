"""GitHub planning publication and authority contracts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKCENTER = 'skills/shared/TODO-WORKCENTER.md'
PLANNER = 'skills/plan-for-me/SKILL.md'
HANDOFF = 'skills/shared/PLAN-HANDOFF.md'
INTERACTIVE = ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md')


def prose(path):
    return ' '.join((ROOT / path).read_text().split())


class PlanningCliContractTests(unittest.TestCase):
    def test_runtime_failure_preserves_existing_contract(self):
        for path in (PLANNER, INTERACTIVE[0]):
            text = prose(path)
            with self.subTest(path=path):
                self.assertIn('same coordinator', text)
                self.assertIn('existing issue', text)
                self.assertIn('candidate evidence', text)
                self.assertIn('do not create replacement work', text)

    def test_active_planning_routes_share_github_authority(self):
        for path in (PLANNER, INTERACTIVE[0], 'skills/docs-sync/SKILL.md',
                     'skills/shared/RESEARCH-PLAN.md', HANDOFF):
            text = prose(path)
            with self.subTest(path=path):
                self.assertIn('GitHub', text)
                self.assertIn('ai-ready', text)
                self.assertIn('UNSAVED', text)
                for command in ('autowork tasks add', 'autowork tasks validate', 'autowork tasks prepare'):
                    self.assertNotIn(command, text)
        for name in ('plan-for-me', 'plan-with-me', 'docs-sync', 'work', 'autowork', 'pending'):
            text = prose(f'adapters/skills/{name}/SKILL.md')
            self.assertIn(f'../../../skills/{name}/SKILL.md', text)
            self.assertIn('../COMMON.md', text)

    def test_handoff_publishes_complete_native_graph_before_readiness(self):
        text = prose(HANDOFF)
        for required in ('observable', '**Scope:**', '**Exclusions:**', '**Acceptance:**',
                         '**Verification:**', '**Sources:**', 'blockedBy', 'ai-epic',
                         'ai-planning', 'final publication phase', 'regardless of author',
                         'open **and closed**', 'actual ownership', 'UNSAVED',
                         'no GitHub, label, document or scratch writes',
                         'not pickup, implementation or merge'):
            self.assertIn(required, text)

    def test_local_main_and_legacy_store_are_not_admission_requirements(self):
        text = prose(HANDOFF)
        self.assertIn('no longer requires', text)
        self.assertIn('canonical local `main` commit', text)
        center = prose(WORKCENTER)
        for required in ('Retired as an active backlog contract', 'migration',
                         'Preserve existing task data', 'currently owned work stays undispatched',
                         'immutable'):
            self.assertIn(required, center)

    def test_runtime_handoffs_do_not_revive_old_executor(self):
        runner = prose('skills/autowork/SKILL.md')
        self.assertIn('never starts, resumes, installs or schedules', runner)
        self.assertIn('Orbi', runner)
        manual = prose('skills/work/SKILL.md')
        self.assertIn('Labels are not an atomic lock', manual)
        self.assertIn('fresh context window', manual)
        self.assertIn('independent review', manual)
        self.assertIn('GitHub', prose('skills/pending/SKILL.md'))


if __name__ == '__main__':
    unittest.main()
