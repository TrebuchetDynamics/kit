"""GitHub planning publication and authority contracts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLANNER = 'skills/plan-for-me/SKILL.md'
HANDOFF = 'skills/shared/PLAN-HANDOFF.md'
INTERACTIVE = ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md')


def prose(path):
    return ' '.join((ROOT / path).read_text().split())


class PlanningCliContractTests(unittest.TestCase):
    def test_runtime_failure_preserves_existing_contract(self):
        text = prose('skills/shared/RESEARCH-PLAN.md').split(
            '## Existing execution is not a new planning problem', 1)[1]
        for rule in ('same coordinator', 'exact failed operation and evidence',
                     'existing issue', 'Do not create a replacement implementation task'):
            self.assertIn(rule, text)
        for path in (PLANNER, INTERACTIVE[0]):
            self.assertIn('../shared/RESEARCH-PLAN.md#shared-planning-interface', prose(path))
            self.assertIn('../shared/PLAN-HANDOFF.md#execution-handoff', prose(path))

    def test_active_planning_routes_share_github_authority(self):
        for path in ('skills/unslop/SKILL.md', 'skills/docs-sync/SKILL.md',
                     'skills/shared/RESEARCH-PLAN.md', HANDOFF):
            text = prose(path)
            with self.subTest(path=path):
                self.assertIn('GitHub', text)
                self.assertIn('ai-ready', text)
                self.assertIn('UNSAVED', text)
        for path in (PLANNER, INTERACTIVE[0]):
            self.assertIn('../shared/PLAN-HANDOFF.md#publication-and-dependencies', prose(path))
            self.assertIn('../shared/PLAN-HANDOFF.md#persistence-not-local-main-admission', prose(path))
        for name in ('plan-for-me', 'plan-with-me', 'unslop', 'docs-sync', 'unblock'):
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

    def test_all_requests_reconcile_outcomes_against_complete_issue_inventory(self):
        text = prose(HANDOFF).split('## Open-issue reconciliation', 1)[1].split('## ', 1)[0]
        for rule in ('focused and discovery', 'before proposing new work',
                     'verified target repository', 'pagination exhaustion',
                     'exclude PRs from issue counts', 'number/ID, URL, title',
                     'full bodies', 'relevant comments', 'linked PRs',
                     'ownership', 'native dependencies', 'parents',
                     'outcome, acceptance, subsystem, aliases and referenced evidence',
                     'different title or author', 'closed issues/PRs',
                     'reuse the inventory during the interview',
                     'refresh candidate identity, state and ownership', 'new matches',
                     'partial or unavailable', 'failed page', 'uniqueness',
                     'read-only', 'inline without mutations'):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)

    def test_reconciliation_preserves_contracts_and_separates_relationships(self):
        text = prose(HANDOFF).split('## Open-issue reconciliation', 1)[1].split('## ', 1)[0]
        for rule in ('covered as-is', 'refine an unowned open issue in place',
                     'link genuinely complementary work', 'already delivered',
                     'new', 'only the accepted delta', 'IDs, history, third-party intent',
                     'contract and labels unchanged', 'existing owner',
                     'cross-reference with a reason', 'actual prerequisites',
                     'file overlap', 'blockedBy', 'stable-key publisher idempotence',
                     'not topic matching', 'No automatic closing, merging, reopening or relabeling'):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)

    def test_planners_and_protocol_route_to_reconciliation_and_show_ids(self):
        for path in (PLANNER, INTERACTIVE[0], 'skills/shared/RESEARCH-PLAN.md'):
            with self.subTest(path=path):
                self.assertIn('PLAN-HANDOFF.md#open-issue-reconciliation', prose(path))
        text = prose(HANDOFF)
        for heading in ('### Plan preview', '### Publication receipt'):
            section = text.split(heading, 1)[1].split('### ', 1)[0]
            self.assertIn('reused, improved, related and new', section)
            self.assertIn('IDs', section)

    def test_local_main_and_legacy_store_are_not_admission_requirements(self):
        text = prose(HANDOFF)
        self.assertIn('no longer requires', text)
        self.assertIn('canonical local `main` commit', text)



if __name__ == '__main__':
    unittest.main()
