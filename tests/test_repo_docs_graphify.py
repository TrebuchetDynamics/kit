"""Offline policy contracts; actual Graphify smoke is separate, not model proof."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GraphifyContractTests(unittest.TestCase):
    def test_graphify_is_targeted_to_relationship_analysis(self):
        core = (ROOT / 'skills/docs-sync/SKILL.md').read_text()
        self.assertIn('## 2a. Targeted relationship analysis', core)
        self.assertIn('Routine link, wording and task-metadata repairs use direct source evidence', core)
        self.assertNotIn('Mandatory Graphify analysis', core)
        self.assertIn('references/graphify-analysis.md', core)
        self.assertIn('Graph evidence:', core)
        self.assertIn('Graphify coverage/limitations', core)

    def test_reference_preserves_authority_and_quality(self):
        text = (ROOT / 'skills/docs-sync/references/graphify-analysis.md').read_text()
        for phrase in ('graphify query', 'graphify path', 'graphify explain',
                       'graphify extract', '--code-only', 'EXTRACTED', 'INFERRED',
                       'AMBIGUOUS', 'source_location', 'dirty/untracked',
                       'Audit creates no graph', 'accepted intent',
                       'Dependencies:', 'Ownership:', 'negative/failure',
                       'graphify_unavailable', 'graphify_partial',
                       'No API key is required', 'byte-identical',
                       'not proof of missing behavior', 'do not invent task IDs'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_adapter_owns_one_bounded_freshness_rule(self):
        # Static policy only: it proves the instruction exists, not that a run obeyed it.
        text = (ROOT / 'adapters/skills/graphify/SKILL.md').read_text()
        for phrase in ('graphify_fresh', 'graphify_stale', 'graphify_partial',
                       'graphify_unavailable', 'built_at_commit', 'untouched',
                       'one shared graph per repository', 'never perfectly current'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_carriers_declare_the_graph_state(self):
        # Five skills make topology claims: dead code, blast radius, architecture,
        # folder coupling and test protection. Each points at the installed shared
        # owner; a link into adapters/ breaks in a profile that installs skills only.
        for name in ('unused-code', 'bug-harvest', 'improve-codebase-architecture',
                     'split-folder', 'test-optimizer'):
            with self.subTest(skill=name):
                text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
                self.assertIn('../shared/COMMON-CONTRACT.md#graph-state', text)
                self.assertIn('declared graph', text)
                self.assertNotIn('Mandatory Graphify', text)

    def test_shared_contract_owns_the_graph_state_vocabulary(self):
        text = (ROOT / 'skills/shared/COMMON-CONTRACT.md').read_text()
        self.assertIn('## Graph state', text)
        for state in ('graphify_fresh', 'graphify_stale', 'graphify_partial',
                      'graphify_unavailable'):
            with self.subTest(state=state):
                self.assertIn(state, text)


if __name__ == '__main__':
    unittest.main()
