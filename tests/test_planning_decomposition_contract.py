"""Planning instruction guards, not model-adherence or worker-speed evidence."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CRAFT = ' '.join((ROOT / 'skills/shared/PLANNING-CRAFT.md').read_text().split())
DISCOVERY = (ROOT / 'skills/plan-for-me/references/discovery.md').read_text()


class PlanningDecompositionContractTests(unittest.TestCase):
    def test_discovery_stops_only_after_selection_uncertainties_are_resolved(self):
        # Keep the decision next to investigation, not hidden in publication rules.
        investigation = ' '.join(DISCOVERY.split('## Investigate progressively', 1)[1]
                                 .split('## Build the project model', 1)[0].split())
        for rule in ('### Stop or widen',
                     'source evidence, observable acceptance',
                     'existing-issue and active-ownership check',
                     'remaining uncertainties',
                     'change selection, priority, prerequisites, scope or safety',
                     'inspect the relevant area before selecting affected work',
                     'unresolved material risk',
                     'Stop widening when the frontier is supported',
                     'no identified open choice could change it',
                     'not a file or time quota'):
            with self.subTest(rule=rule):
                self.assertIn(rule, investigation)

    def test_discovery_tracing_and_report_preserve_the_uninspected_boundary(self):
        text = ' '.join(DISCOVERY.split())
        for rule in ('Within the inspected boundary, trace each important requirement',
                     'supports the frontier or could change its selection',
                     '**Inspection boundary**',
                     'uninspected, not free of gaps',
                     'not repository-wide certification'):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)
        self.assertNotIn('Trace each important requirement:', DISCOVERY)

    def test_discovery_reuses_coverage_without_truncating_explicit_batches(self):
        text = ' '.join(DISCOVERY.split())
        for rule in ('Reuse covering issues rather than manufacture new findings',
                     'at most eight new tasks',
                     'not the full explicitly requested batch',
                     '../../shared/RESEARCH-PLAN.md#full-requested-batch'):
            with self.subTest(rule=rule):
                self.assertIn(rule, text)
        full_batch = (ROOT / 'skills/shared/RESEARCH-PLAN.md').read_text().split(
            '## Full requested batch', 1)[1].split('## Research and persistence method', 1)[0]
        self.assertIn('every requested outcome', full_batch)
        self.assertIn('Do not stop when the', full_batch)
        # Matched model cases remain specifications, not fabricated model receipts.
        scenarios = (ROOT / 'tests/fixtures/planning/README.md').read_text().split(
            '## Discovery stop/widen scenarios', 1)[1].split('## Paired recovery', 1)[0]
        self.assertIn('**NOT_RUN**', scenarios)
        for case, expectations in (
                ('Stable frontier', ('Stop widening', 'API/storage inspected boundary',
                                     'gallery uninspected')),
                ('Material prerequisite', ('UNKNOWN', 'duplicate a committed write',
                                          'before selecting', 'retry work pending')),
                ('Existing coverage', ('Reuse #800', 'preserve its owner/PR', 'zero new tasks')),
                ('Explicit batch', ('all nine outcomes', 'reusing FMT-01',
                                    'eight-new-task discovery ceiling'))):
            with self.subTest(case=case):
                row = next(line for line in scenarios.splitlines()
                           if line.startswith(f'| **{case}**'))
                for expectation in expectations:
                    self.assertIn(expectation, row)

    def test_bounded_large_file_fix_needs_no_extraction_task(self):
        for rule in ('Re-cut ownership for cohesion',
                     'observed conflict cost and testability',
                     'not an arbitrary file-size threshold'):
            with self.subTest(rule=rule):
                self.assertIn(rule, CRAFT)
        self.assertNotIn('gets a first task that extracts', CRAFT)
        self.assertNotIn('longer than about 1500 lines', CRAFT)

    def test_file_overlap_ranks_without_fake_dependencies(self):
        for rule in ('report actual overlap instead of inventing product prerequisites',
                     'Native GitHub `blockedBy` edges represent real dependencies',
                     'not preferred order or file overlap',
                     'overlap is not a promise of no conflict'):
            with self.subTest(rule=rule):
                self.assertIn(rule, CRAFT)
        self.assertNotIn('Tasks that can run together have disjoint writes', CRAFT)
        self.assertNotIn('a file that unlanded work also names waits', CRAFT)

    def test_real_conflicts_and_protected_paths_still_coordinate(self):
        for rule in ('Orbi has no cross-deployment capacity or ownership lock',
                     'do not promise serialization from a legacy task resource field',
                     'CI, manifests and sensitive changes retain repository gates',
                     'Name shared registry/interface changes once'):
            with self.subTest(rule=rule):
                self.assertIn(rule, CRAFT)

    def test_public_seam_budget_keeps_required_checks_and_review(self):
        budget = 'at most one focused test per behavior'
        self.assertIn(budget, CRAFT)
        for rule in ('Prefer extending an existing public test seam',
                     'A new focused file or class is optional',
                     'No tests merely for docs, config or renames',
                     'instruction-contract guard tests the instruction behavior itself',
                     'Reuse existing negative guards',
                     'Preserve every task-required check and independent review',
                     "repository's documented affected-test selection",
                     'preserve required CI and merge checks',
                     'Offline instruction checks do not prove model adherence'):
            with self.subTest(rule=rule):
                self.assertIn(rule, CRAFT)
        self.assertNotIn("Put each task's tests in a new focused test file or class", CRAFT)
        self.assertNotIn('the full check run on the merged tree', CRAFT)


if __name__ == '__main__':
    unittest.main()
