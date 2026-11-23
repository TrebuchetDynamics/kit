"""Bug Harvest instruction contracts; not live model or Orbi qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/bug-harvest/SKILL.md'
ADAPTER = ROOT / 'adapters/skills/bug-harvest/SKILL.md'
HANDOFF = ROOT / 'skills/shared/PLAN-HANDOFF.md'


def prose(path):
    return ' '.join(path.read_text().split())


class SpecialistBugHarvestTests(unittest.TestCase):
    def test_bare_invocation_opts_into_existing_single_invocation_handoff(self):
        for path in (SKILL, ADAPTER):
            with self.subTest(path=path):
                match = re.search(r'\[single-invocation specialist handoff\]\(([^)]+)\)',
                                  path.read_text())
                self.assertIsNotNone(match, 'default route must load the shared handoff')
                target, anchor = match.group(1).split('#')
                self.assertEqual((path.parent / target).resolve(), HANDOFF)
                self.assertEqual(anchor, 'single-invocation-specialist-handoff')
        self.assertIn('without a publication directive', prose(SKILL))
        self.assertIn('same invocation', prose(SKILL))
        handoff = prose(HANDOFF)
        for rule in ('preview in chat without waiting',
                     'finding numbers, approval, a second command or a planner invocation',
                     'report verified issue links and stop'):
            self.assertIn(rule, handoff)
        self.assertIn('disable-model-invocation: true', ADAPTER.read_text())
        self.assertIn('../../../skills/bug-harvest/SKILL.md', ADAPTER.read_text())

    def test_contextual_state_machine_findings_are_evidence_not_fix_authority(self):
        text = prose(SKILL)
        for rule in ('without arguments after an analysis such as `/state-machine`',
                     'Reuse the state map and evidence', 'not local repairs',
                     'No extra prompt, report file or repeated analysis',
                     'Recheck current source and ownership',
                     "prior skill's read-only default"):
            self.assertIn(rule, text)
        for obsolete in ('findings as the repair scope', 'invocation requests local fixes',
                         'process one candidate at a time through the fix loop below'):
            self.assertNotIn(obsolete, text)
        docs = prose(ROOT / 'docs/workflows.md')
        self.assertIn('bounded publication scope', docs)
        self.assertNotIn('uses the preceding response as the bounded repair scope', docs)
        caller = prose(ROOT / 'skills/state-machine/SKILL.md')
        self.assertIn('bounded publication scope', caller)
        self.assertNotIn('before fixing them', caller)
        self.assertIn('This analysis itself remains read-only', caller)

    def test_verified_defects_need_reproducer_behavior_impact_and_regression(self):
        text = prose(SKILL)
        for rule in ('reproducer', 'observed behavior', 'expected behavior',
                     'concrete impact and trigger', 'regression check',
                     'current failure evidence', 'source locations',
                     'Hypotheses remain leads', 'smallest compatible correction'):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)
        self.assertIn('before reading the pinned', text)
        self.assertIn('take precedence over the upstream fix/campaign loop', text)
        self.assertIn('Default publication does not patch locally', text)

    def test_mixed_actionable_held_and_covered_results_do_not_truncate_batch(self):
        text = prose(SKILL)
        self.assertIn('discovery frontier, not a cap on an explicit batch', text)
        handoff = prose(HANDOFF)
        for rule in ('all supported, buildable, uncovered outcomes',
                     'Group findings that share a fix and acceptance check',
                     'covered, completed, owned and unsupported findings create no duplicate issue',
                     'Hold only uncertain findings with the reason and resume condition',
                     'continue independent qualifying work',
                     'existing open **and closed** issues', 'native `blockedBy`',
                     'final publication phase', 'no-dispatch', 'human-only'):
            with self.subTest(rule=rule):
                self.assertIn(rule, handoff)
        self.assertIn('Hold unresolved product rules', text)

    def test_zero_qualifying_findings_means_zero_new_issues(self):
        self.assertIn('Zero qualifying findings means zero new issues', prose(HANDOFF))
        self.assertIn('no change is warranted', prose(HANDOFF))
        self.assertIn('Never claim no bugs exist', prose(SKILL))

    def test_explicit_report_only_has_no_writes_even_for_repro(self):
        text = prose(SKILL)
        self.assertIn('Explicit `report only`, `read-only`, `no-write` or `dry-run`', text)
        self.assertIn('report inline and write nothing', text)
        self.assertIn('including scratch repro files', text)
        self.assertIn('no GitHub, label, document or scratch writes', prose(HANDOFF))

    def test_authorized_fix_mode_is_a_separate_bounded_route(self):
        text = SKILL.read_text()
        self.assertIn('Only an explicitly requested and authorized local fix/apply mode', prose(SKILL))
        self.assertIn('## Authorized local fixes', text)
        fix = ' '.join(text.split('## Authorized local fixes', 1)[1].split())
        for rule in ('Confirm the failure', 'smallest safe fix',
                     'discriminating regression protection', 'affected checks',
                     'ownership, review, PR and human-only gates',
                     'No automatic commit or push'):
            self.assertIn(rule, fix)

    def test_publication_failure_uses_shared_unsaved_and_partial_receipts(self):
        handoff = prose(HANDOFF)
        for rule in ('**UNSAVED**, with the exact failure and retry command',
                     'per-issue partial receipt', '**UNKNOWN**',
                     'Inspect ownership and reconcile the cause before retrying',
                     'Do not create a substitute executable queue'):
            self.assertIn(rule, handoff)
        self.assertIn('shared publication receipt', prose(SKILL))


if __name__ == '__main__':
    unittest.main()
