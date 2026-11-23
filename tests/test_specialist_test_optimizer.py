"""Test Optimizer entry contracts, not live model or publication qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/test-optimizer/SKILL.md'
ADAPTER = ROOT / 'adapters/skills/test-optimizer/SKILL.md'
HANDOFF = ROOT / 'skills/shared/PLAN-HANDOFF.md'


def prose(path):
    return ' '.join(path.read_text().split())


class SpecialistTestOptimizerTests(unittest.TestCase):
    def handoff(self, entry=SKILL):
        # Follow the entry's actual policy opt-in; a generic shared default is not enough.
        match = re.search(r'\[single-invocation specialist handoff\]\(([^)]+)\)',
                          entry.read_text())
        self.assertIsNotNone(match, 'Test Optimizer must opt into the shared handoff')
        target, anchor = match.group(1).split('#')
        self.assertEqual((entry.parent / target).resolve(), HANDOFF)
        self.assertEqual(anchor, 'single-invocation-specialist-handoff')
        return prose(HANDOFF)

    def test_bare_invocation_analyzes_and_publishes_without_follow_up(self):
        skill = prose(SKILL)
        for rule in ('named/current repository', 'without a publication directive',
                     'same invocation', 'changes no tests',
                     "take precedence over the protocol's audit/apply defaults"):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        handoff = self.handoff()
        for rule in ('preview in chat without waiting',
                     'finding numbers, approval, a second command or a planner invocation',
                     'report verified issue links and stop',
                     'neither local implementation nor service activation'):
            self.assertIn(rule, handoff)
        self.assertNotIn('**Apply and verify:** change one coherent batch', skill)

    def test_removal_issues_require_detector_oracle_or_retired_unowned_evidence(self):
        skill = prose(SKILL)
        for rule in ('retained equivalent detector and oracle', 'retired product obligation',
                     'evidence that the test protects no owned behavior or invariant',
                     'equal coverage, similar names and never failing are not equivalence',
                     'Keep an integration test when it catches a real handoff a unit mock cannot',
                     'Unproven removal candidates remain intact',
                     'Carry the detector/oracle mapping or retired/unowned evidence into each issue',
                     'exact test/fixture IDs', 'verification command'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        self.assertIn('distinct boundaries', skill)
        self.assertIn('No default test edits', skill)

    def test_mixed_actionable_held_and_existing_results_publish_complete_supported_batch(self):
        skill = prose(SKILL)
        self.assertIn('**Publish and stop:**', skill)
        handoff = self.handoff()
        for rule in ('all supported, buildable, uncovered outcomes',
                     'Group findings that share a fix and acceptance check',
                     'covered, completed, owned and unsupported findings create no duplicate issue',
                     'Hold only uncertain findings with the reason and resume condition',
                     'continue independent qualifying work',
                     'open and closed issues, linked PRs and ownership',
                     'native `blockedBy`', '`ai-ready` as the **final publication phase**',
                     'no-dispatch', 'human-only', 'live ownership'):
            with self.subTest(rule=rule):
                self.assertIn(rule, handoff)

    def test_zero_qualifying_findings_means_zero_new_issues(self):
        handoff = self.handoff()
        self.assertIn('Zero qualifying findings means zero new issues', handoff)
        self.assertIn('no change is warranted', handoff)
        self.assertIn('no change is warranted', prose(SKILL))

    def test_explicit_report_only_overrides_apply_and_writes_nothing(self):
        skill = prose(SKILL)
        for rule in ('`report only`', '`read-only`', '`no-write`', '`dry-run`',
                     'wins over apply', 'return findings inline and write nothing'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        self.assertIn('no GitHub, label, document or scratch writes', self.handoff())

    def test_authorized_local_apply_is_separate_from_default_publication(self):
        skill = SKILL.read_text()
        self.assertIn('Only an explicitly requested and authorized local fix/apply mode', prose(SKILL))
        self.assertNotIn('a request to reduce/optimize the suite', skill)
        self.assertIn('## Authorized local apply', skill)
        apply = ' '.join(skill.split('## Authorized local apply', 1)[1].split('## ', 1)[0].split())
        for rule in ('one coherent supported batch', 'distinct required oracle',
                     'affected checks', 'required independent review',
                     'ownership, review, PR and human-only gates',
                     'No automatic commit or push'):
            with self.subTest(rule=rule):
                self.assertIn(rule, apply)

    def test_portable_entry_and_mode_guidance_follow_canonical_workflow(self):
        self.handoff(ADAPTER)
        adapter = prose(ADAPTER)
        for link in ('../../../skills/test-optimizer/SKILL.md', '../COMMON.md'):
            self.assertIn(link, adapter)
        self.assertIn('disable-model-invocation: true', adapter)
        self.assertNotIn('Bare invocation audits;', adapter)
        docs = (ROOT / 'docs/workflows.md').read_text().split('## Test optimizer', 1)[1].split('\n## ', 1)[0]
        self.assertIn('same invocation', docs)
        self.assertNotIn('a request\nto reduce/optimize the suite', docs)
        probes = prose(ROOT / 'skills/test-optimizer/references/evaluation.md')
        self.assertIn('publishes justified, uncovered outcomes', probes)
        self.assertIn('Mixed actionable/held/covered', probes)
        self.assertIn('Zero qualifying findings', probes)

    def test_publication_failure_uses_existing_unsaved_and_partial_receipts(self):
        handoff = self.handoff()
        for rule in ('**UNSAVED**, with the exact failure and retry command',
                     'per-issue partial receipt', '**UNKNOWN**',
                     'Inspect ownership and reconcile the cause before retrying',
                     'Do not create a substitute executable queue'):
            self.assertIn(rule, handoff)
        self.assertIn('shared publication receipt', prose(SKILL))


if __name__ == '__main__':
    unittest.main()
