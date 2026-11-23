"""Unused Code public-entry contracts, not live model or Orbi qualification."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/unused-code/SKILL.md'
ADAPTER = ROOT / 'adapters/skills/unused-code/SKILL.md'
HANDOFF = ROOT / 'skills/shared/PLAN-HANDOFF.md'


def prose(path):
    return ' '.join(path.read_text().split())


class SpecialistUnusedCodeTests(unittest.TestCase):
    def handoff(self, entry=SKILL):
        # Follow the real public entry's opt-in, not an assumed global default.
        match = re.search(r'\[single-invocation specialist handoff\]\(([^)]+)\)',
                          entry.read_text())
        self.assertIsNotNone(match, 'Unused Code must load the shared default route')
        target, anchor = match.group(1).split('#')
        self.assertEqual((entry.parent / target).resolve(), HANDOFF)
        self.assertEqual(anchor, 'single-invocation-specialist-handoff')
        return prose(HANDOFF)

    def test_bare_invocation_analyzes_and_publishes_in_one_pass(self):
        skill = prose(SKILL)
        self.assertIn('With no area supplied, inspect the current repository', skill)
        self.assertIn('without a publication directive', skill)
        self.assertIn('same invocation', skill)
        for rule in ('preview in chat without waiting',
                     'finding numbers, approval, a second command or a planner invocation',
                     'report verified issue links and stop'):
            self.assertIn(rule, self.handoff())
        self.assertIn('before reading the pinned', skill)
        self.assertIn('take precedence over its deletion loop', skill)
        self.assertIn('Default publication does not delete or implement locally', skill)

    def test_reachability_proof_covers_non_graph_consumers(self):
        skill = prose(SKILL)
        for rule in ('public package/CLI/API entrypoints', 're-exports',
                     'runtime discovery', 'registries', 'reflection',
                     'external consumers', 'compatibility promises',
                     'known ownership boundary', 'executable post-delete signal',
                     'empty graph', 'zero inbound edges',
                     'never prove unreachability', '**retain and explain**',
                     'live source', 'declared graph state',
                     'path:symbol', 'liveness checks', 'validation command'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        # Proof is required for issue eligibility, not only the optional delete branch.
        proof = SKILL.read_text().split('## Authorized local fixes', 1)[0]
        self.assertIn('Only candidates that pass this proof gate qualify for cleanup issues',
                      ' '.join(proof.split()))

    def test_mixed_supported_held_and_existing_findings_keep_independent_work(self):
        handoff = self.handoff()
        for rule in ('all supported, buildable, uncovered outcomes',
                     'Group findings that share a fix and acceptance check',
                     'covered, completed, owned and unsupported findings create no duplicate issue',
                     'Hold only uncertain findings with the reason and resume condition',
                     'continue independent qualifying work',
                     'open and closed issues, linked PRs and ownership',
                     'native `blockedBy`', 'final publication phase',
                     'no-dispatch', 'human-only', 'live ownership',
                     'neither local implementation nor service activation'):
            with self.subTest(rule=rule):
                self.assertIn(rule, handoff)
        self.assertIn('Uncertain liveness is held, not a speculative cleanup issue', prose(SKILL))

    def test_zero_qualifying_findings_creates_zero_issues_and_deletes_nothing(self):
        self.assertIn('Zero qualifying findings means zero new issues', self.handoff())
        self.assertIn('no change is warranted', self.handoff())
        self.assertIn('No proven candidate means delete nothing', prose(SKILL))

    def test_explicit_report_only_and_dry_run_write_nothing(self):
        for rule in ('Explicit `report only`, `read-only`, `no-write` or `dry-run`',
                     'report inline and write nothing', 'including scratch files and graphs'):
            self.assertIn(rule, prose(SKILL))
        self.assertIn('no GitHub, label, document or scratch writes', self.handoff())

    def test_only_explicit_authorized_fix_mode_enters_deletion(self):
        text = SKILL.read_text()
        self.assertIn('Only an explicitly requested and authorized local fix/apply mode', prose(SKILL))
        self.assertIn('## Authorized local fixes', text)
        fix = ' '.join(text.split('## Authorized local fixes', 1)[1].split())
        for rule in ('baseline', 'Delete one coherent batch', 'affected validation',
                     'A regression stops further deletion', 'attributable delta',
                     'never use blanket Git restore/clean',
                     'ownership, review, PR and human-only gates',
                     'No automatic commit or push'):
            self.assertIn(rule, fix)

    def test_publication_failure_uses_existing_unsaved_and_partial_receipts(self):
        self.assertIn('shared publication receipt', prose(SKILL))
        for rule in ('**UNSAVED**, with the exact failure and retry command',
                     'per-issue partial receipt', '**UNKNOWN**',
                     'Inspect ownership and reconcile the cause before retrying',
                     'Do not create a substitute executable queue'):
            self.assertIn(rule, self.handoff())

    def test_portable_entry_and_pi_summary_match_the_default(self):
        self.handoff(ADAPTER)
        for rule in ('disable-model-invocation: true', '../COMMON.md',
                     '../../../skills/unused-code/SKILL.md',
                     'Publish proven dead-code cleanup issues.'):
            self.assertIn(rule, ADAPTER.read_text())
        self.assertIn('Publish proven dead-code cleanup issues.', SKILL.read_text())
        self.assertIn("'unused-code': ['unused-code', 'Publish proven dead-code cleanup issues']",
                      (ROOT / 'adapters/pi.mjs').read_text())


if __name__ == '__main__':
    unittest.main()
