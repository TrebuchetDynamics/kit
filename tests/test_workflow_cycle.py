"""Offline real-ledger lifecycle; review receipts are simulated, no model/native runs."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CycleGuidanceTests(unittest.TestCase):
    def test_caller_controlled_continuation_uses_github_and_preserves_scope(self):
        manual = (ROOT / 'skills/work/SKILL.md').read_text()
        for requirement in ('Honor a supplied issue or scope', 'Continue eligible work',
                            'caller', 'A session end starts no replacement service'):
            self.assertIn(requirement, manual)
        for path in ('skills/autowork/SKILL.md', 'adapters/skills/autowork/SKILL.md'):
            text = (ROOT / path).read_text()
            self.assertIn('Orbi', text)
            self.assertNotIn('autowork start .', text)

    def test_same_task_recovery_and_independent_fallback_keep_real_holds(self):
        iteration = (ROOT / 'skills/autowork/references/iteration-and-decisions.md').read_text()
        for requirement in ('Never block\n   on a first failure', 'non-privileged tooling',
                            'same task', 'consequential choices', 'no automatic failure retry'):
            self.assertIn(requirement, iteration)
        recovery = (ROOT / 'skills/autowork/references/blocker-recovery.md').read_text()
        for requirement in ('original pin', 'original admission evidence', 'pending_approval',
                            'resume step', 'another channel', 'live resource ownership',
                            'inside its contract'):
            self.assertIn(requirement, recovery)
        scheduled = (ROOT / 'skills/autowork/references/scheduled-policy.md').read_text()
        for requirement in ('saved stop/batch limits', 'at-most-one-new-batch',
                            'provenance', 'current ownership', 'checks and required review',
                            'non-overlapping'):
            self.assertIn(requirement, scheduled)
        self.assertNotIn('unknown usage is not zero', scheduled)

    def test_ready_native_and_portable_guidance_use_one_github_contract(self):
        native = (ROOT / 'skills/autowork/SKILL.md').read_text()
        portable = (ROOT / 'adapters/skills/autowork/SKILL.md').read_text()
        self.assertIn('../shared/PLAN-HANDOFF.md', native)
        self.assertIn('../../../skills/autowork/SKILL.md', portable)
        for text in (native, portable):
            self.assertNotIn('--owner-pid', text)
            self.assertNotIn('autowork tasks prepare', text)

    def test_autowork_never_falls_back_to_legacy_execution(self):
        native = (ROOT / 'skills/autowork/SKILL.md').read_text()
        self.assertIn('never starts, resumes, installs or schedules', native)
        self.assertIn('no fallback executor', native)
        self.assertIn('routes explicitly to `/work`', native)

    def test_default_guidance_does_not_route_through_native_card_tools(self):
        paths = ('skills/autowork/SKILL.md',
                 'skills/autowork/references/scheduled-policy.md',
                 'skills/autowork/references/iteration-and-decisions.md',
                 'skills/autowork/references/delivery-batches.md',
                 'skills/shared/ENGINEERING-CYCLE.md')
        for path in paths:
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                for obsolete in ('hermes kanban', 'start_goal.py', 'reconcile.py',
                                 '--goal-max-turns', '--max-retries', '100-turn default'):
                    self.assertNotIn(obsolete, text)
        direct = (ROOT / 'skills/autowork/references/owner-cycle.md').read_text()
        for requirement in ('`tasks/` owns product requirements', 'Selection reads `tasks/` at the base commit',
                            'actual process plus workspace/Git', 'explicit finite timeout',
                            'no token, cost or task-lifetime budgets', 'it never closes the task'):
            self.assertIn(requirement, direct)

    def test_cross_profile_audit_verifies_publication_without_takeover(self):
        text = (ROOT / 'skills/autowork/references/state-and-recovery.md').read_text()
        self.assertIn('## Cross-profile audit and publication evidence', text)
        for requirement in ('git status --porcelain=v1 -z', 'git worktree list --porcelain',
                            'git ls-remote --heads', 'audit_unverified',
                            'last_run_commit', 'published_branch', 'integrated_main',
                            'read-only', 'No automatic commit', 'nonempty',
                            'bounded backlog', 'UTC', 'mode=ro'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_legacy_scheduled_policy_is_not_an_active_entrypoint(self):
        core = (ROOT / 'skills/autowork/SKILL.md').read_text()
        self.assertNotIn('references/scheduled-policy.md', core)
        self.assertIn('migration and recovery only', core)
        self.assertIn('No legacy runner', (ROOT / 'skills/plan-for-me/SKILL.md').read_text())

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
        for path in ('docs-sync/SKILL.md', 'autowork/SKILL.md'):
            self.assertIn('PLAN-HANDOFF.md', (ROOT / 'skills' / path).read_text())
        self.assertIn('ENGINEERING-CYCLE.md',
                      (ROOT / 'skills/autowork/references/whole-spec-execution.md').read_text())

    def test_supporting_guidance_does_not_reintroduce_phase_checklists(self):
        forbidden = {
            'shared/ENGINEERING-CYCLE.md': ['At intake and whenever the work changes phase',
                                           'For each relevant skill, read'],
            'autoresearch/SKILL.md': ['Use verified Addy skills through the engineering-cycle matrix:'],
            'autowork/references/discovery.md': ["skill and its STE-inspired reference with"],
            'autowork/references/handoff.md': ['Before solution design or implementation, load `ponytail`'],
            'autowork/references/backlog-planning.md': ['or immediately\nwhen the observed queue'],
        }
        for path, phrases in forbidden.items():
            text = (ROOT / 'skills' / path).read_text()
            for phrase in phrases:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_approved_autowork_records_authority_without_reapproval(self):
        # Instruction coverage, not evidence of runtime admission or live execution.
        policy = ' '.join((ROOT / 'docs/autonomy.md').read_text().split())
        for requirement in ('without another owner approval',
                            'Every Autowork invocation and recurring occurrence',
                            'fully authorized for its accepted scope',
                            'model execution and its ordinary usage cost',
                            'outside the runner being stopped',
                            'publication and live operations',
                            'not itself evidence of owner approval',
                            'Do not change a running contract',
                            'live_actor', 'live_at', 'live_scope',
                            'continue independent approved work',
                            'Approval is never completion evidence',
                            'Runtime admission still reads the committed typed task records'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, policy)
        for path in ('AGENTS.md',
                     'skills/autowork/references/iteration-and-decisions.md',
                     'pi-autowork/task-store.md'):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertIn('standing', text)
                self.assertIn('approval', text)

    def test_autonomy_does_not_turn_missing_intent_into_approval(self):
        core = (ROOT / 'skills/autowork/SKILL.md').read_text() + (ROOT / 'skills/autowork/references/iteration-and-decisions.md').read_text()
        self.assertNotIn('proceed on the recommended reading', core)
        self.assertIn('continue only independent authorized work', core)
        self.assertIn('Silence never grants', core)
        cycle = (ROOT / 'skills/shared/ENGINEERING-CYCLE.md').read_text()
        for skill in ('api-and-interface-design', 'deprecation-and-migration',
                      'ci-cd-and-automation', 'observability-and-instrumentation',
                      'frontend-ui-engineering', 'context-engineering', 'code-simplification'):
            self.assertIn(skill, cycle)


if __name__ == '__main__':
    unittest.main()
