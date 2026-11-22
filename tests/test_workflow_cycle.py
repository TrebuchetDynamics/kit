"""Offline real-ledger lifecycle; review receipts are simulated, no model/native runs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CycleGuidanceTests(unittest.TestCase):

    def test_default_guidance_does_not_route_through_native_card_tools(self):
        paths = ('skills/shared/ENGINEERING-CYCLE.md',)
        for path in paths:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                for obsolete in ('hermes kanban', 'start_goal.py', 'reconcile.py',
                                 '--goal-max-turns', '--max-retries', '100-turn default'):
                    self.assertNotIn(obsolete, text)

    def test_cycle_routes_available_skills_and_preserves_authority(self):
        policy = ROOT / 'skills/shared/ENGINEERING-CYCLE.md'
        self.assertTrue(policy.is_file(), 'missing shared engineering cycle')
        text = policy.read_text()
        for requirement in ('interview-me', 'spec-driven-development', 'documentation-and-adrs',
                            'planning-and-task-breakdown', 'incremental-implementation',
                            'test-driven-development', 'code-review-and-quality',
                            'skills/.hub/lock.json', 'systematic-debugging',
                            'No native card admission',
                            'tasks/todo.md', 'review acceptance', 'NOT_CHECKED'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)
        for path in ('docs-sync/SKILL.md', 'unblock/SKILL.md'):
            self.assertIn('PLAN-HANDOFF.md', (ROOT / 'skills' / path).read_text())

    def test_supporting_guidance_does_not_reintroduce_phase_checklists(self):
        forbidden = {
            'shared/ENGINEERING-CYCLE.md': ['At intake and whenever the work changes phase',
                                           'For each relevant skill, read'],
            'autoresearch/SKILL.md': ['Use verified Addy skills through the engineering-cycle matrix:'],
        }
        for path, phrases in forbidden.items():
            text = (ROOT / 'skills' / path).read_text()
            for phrase in phrases:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_approved_scope_retains_authority_without_reviving_executor(self):
        policy = ' '.join((ROOT / 'docs/autonomy.md').read_text().split())
        for requirement in ('without another owner approval',
                            'fully authorized for its accepted scope',
                            'model execution and its ordinary usage cost',
                            'publication and live operations',
                            'not itself evidence of owner approval',
                            'Do not change a running contract',
                            'Approval is never completion evidence',
                            'Orbi remains paused'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, policy)

    def test_autonomy_does_not_turn_missing_intent_into_approval(self):
        policy = (ROOT / 'docs/autonomy.md').read_text()
        for requirement in ('human-only requirements', 'explicit exclusions',
                            'cannot override', 'Never route around an access-control denial'):
            self.assertIn(requirement, policy)
        cycle = (ROOT / 'skills/shared/ENGINEERING-CYCLE.md').read_text()
        for skill in ('api-and-interface-design', 'deprecation-and-migration',
                      'ci-cd-and-automation', 'observability-and-instrumentation',
                      'frontend-ui-engineering', 'context-engineering', 'code-simplification'):
            self.assertIn(skill, cycle)


if __name__ == '__main__':
    unittest.main()
