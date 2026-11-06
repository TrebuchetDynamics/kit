"""Instruction contracts only; these do not prove live model adherence."""
from pathlib import Path
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

    def test_fix_branch_preserves_review_default_and_existing_executor(self):
        text = (ROOT / 'skills/improve-codebase-architecture/SKILL.md').read_text()
        for phrase in ('Default to review', 'references/fixes.md',
                       'continue with `/autowork` for one bounded candidate',
                       'commit, push and deployment authority stay separate',
                       'no-write request also rules out the HTML file'):
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
