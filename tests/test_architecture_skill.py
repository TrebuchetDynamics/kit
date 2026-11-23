"""Instruction contracts only; these do not prove live model adherence."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ArchitectureSkillTests(unittest.TestCase):
    def test_discovery_uses_graphify_and_ponytail_with_source_evidence(self):
        text = (ROOT / 'skills/improve-codebase-architecture/SKILL.md').read_text()
        for phrase in ('Load `/graphify`', 'build no graph', 'native search',
                       '../shared/COMMON-CONTRACT.md#graph-state',
                       '../ponytail/upstream/skills/ponytail/PROTOCOL.md',
                       'Verify every graph lead in current source',
                       'severity separate from the confidence',
                       'An unmeasured speed claim stays a hypothesis'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_portable_graphify_handoff_links_to_existing_adapter(self):
        skill = ROOT / 'skills/improve-codebase-architecture/SKILL.md'
        match = re.search(r'\[Graphify adapter\]\(([^)]+)\)', skill.read_text())
        self.assertIsNotNone(match, 'portable handoff needs an explicit file link')
        target = (skill.parent / match.group(1)).resolve()
        self.assertEqual(target, ROOT / 'adapters/skills/graphify/SKILL.md')
        self.assertTrue(target.is_file())

    def test_host_contract_uses_discovered_locations_not_guessed_paths(self):
        text = ' '.join((ROOT / 'adapters/skills/COMMON.md').read_text().split())
        self.assertIn('host-discovered skill metadata or an explicit file link', text)
        self.assertIn('Do not infer `skills/<command>/SKILL.md`', text)

    def test_bare_invocation_uses_one_shared_publication_handoff(self):
        skill = ROOT / 'skills/improve-codebase-architecture/SKILL.md'
        adapter = (ROOT / 'adapters/skills/improve-codebase-architecture/SKILL.md').read_text()
        docs = (ROOT / 'docs/workflows.md').read_text()
        match = re.search(r'\[single-invocation specialist handoff\]\(([^)]+)\)', skill.read_text())
        self.assertIsNotNone(match, 'default route must load the shared policy')
        path, anchor = match.group(1).split('#')
        handoff_path = (skill.parent / path).resolve()
        self.assertEqual(handoff_path, ROOT / 'skills/shared/PLAN-HANDOFF.md')
        self.assertEqual(anchor, 'single-invocation-specialist-handoff')
        handoff = ' '.join(handoff_path.read_text().split())
        for phrase in ('## Single-invocation specialist handoff',
                       'without a publication directive', 'same invocation',
                       'all supported, buildable, uncovered outcomes',
                       'Group findings that share a fix',
                       'finding numbers, approval, a second command or a planner invocation',
                       'preview in chat without waiting', 'report verified issue links and stop'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, handoff)
        self.assertIn('../../../skills/improve-codebase-architecture/SKILL.md', adapter)
        self.assertIn('single-invocation-specialist-handoff', adapter)
        self.assertNotIn('until the owner confirms', adapter)
        self.assertIn('architecture publication pilot', docs)
        self.assertIn('/improve-codebase-architecture src/runner\n', docs)
        self.assertNotIn('Default review writes', docs)
        for obsolete in ('Default to review', 'ask which candidate', 'review stops with a next choice'):
            self.assertNotIn(obsolete, skill.read_text())

    def test_mixed_findings_require_evidence_and_continue_past_holds(self):
        skill = ' '.join((ROOT / 'skills/improve-codebase-architecture/SKILL.md').read_text().split())
        handoff = ' '.join((ROOT / 'skills/shared/PLAN-HANDOFF.md').read_text().split())
        for phrase in ('affected callers', 'failure or cost evidence',
                       'smallest compatible fix', 'compatibility risk', 'verification command',
                       'Hold unresolved ADR decisions and speculative refactors',
                       'Do not link temporary HTML as a governing source'):
            self.assertIn(phrase, skill)
        for phrase in ('Hold only uncertain findings with the reason and resume condition',
                       'continue independent qualifying work',
                       'covered, completed, owned and unsupported findings create no duplicate issue',
                       'Check the repository, existing open **and closed** issues',
                       'native `blockedBy`', 'final publication phase',
                       'no-dispatch', 'human-only'):
            self.assertIn(phrase, handoff)

    def test_zero_qualifying_findings_creates_no_issues(self):
        handoff = ' '.join((ROOT / 'skills/shared/PLAN-HANDOFF.md').read_text().split())
        self.assertIn('Zero qualifying findings means zero new issues', handoff)
        self.assertIn('report covered/held dispositions or that no change is warranted', handoff)

    def test_explicit_report_only_is_inline_and_writes_nothing(self):
        skill = ' '.join((ROOT / 'skills/improve-codebase-architecture/SKILL.md').read_text().split())
        handoff = ' '.join((ROOT / 'skills/shared/PLAN-HANDOFF.md').read_text().split())
        self.assertIn('Explicit `report only`, `read-only`, `no-write` or `dry-run`', skill)
        self.assertIn('report inline and write nothing', skill)
        self.assertIn('no-write request also rules out the HTML file', skill)
        self.assertIn('no GitHub, label, document or scratch writes', handoff)

    def test_publication_failure_uses_existing_recovery_not_a_new_queue(self):
        handoff = ' '.join((ROOT / 'skills/shared/PLAN-HANDOFF.md').read_text().split())
        for phrase in ('**UNSAVED**, with the exact failure and retry command',
                       'per-issue partial receipt', '**UNKNOWN**',
                       'Inspect ownership and reconcile the cause before retrying',
                       'Do not create a substitute executable queue'):
            self.assertIn(phrase, handoff)

    def test_authorized_fix_branch_stays_separate_from_default_publication(self):
        text = ' '.join((ROOT / 'skills/improve-codebase-architecture/SKILL.md').read_text().split())
        for phrase in ('explicit request to fix, apply, patch or optimize', 'references/fixes.md',
                       'implement one bounded candidate within the accepted scope',
                       'commit, push and deployment authority stay separate',
                       'Default publication does not implement findings locally',
                       'ownership', 'review and PR gates'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_fix_branch_requires_regression_measurement_and_review(self):
        text = ' '.join(
            (ROOT / 'skills/improve-codebase-architecture/references/fixes.md')
            .read_text().split()
        )
        for phrase in ('confirm it fails for the claimed reason',
                       'repeated baseline measurements', 'before editing',
                       'repeat the same workload', 'variability',
                       'behavior regression blocks completion',
                       'Load `/ponytail-review`', 'existing review lane',
                       'Preserve unrelated', 'Definition of Done'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
