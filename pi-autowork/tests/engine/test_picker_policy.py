"""Structural policy regression; not a model-behavior or fleet-progress test."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / 'skills/autowork'


def full_text():
    # Core plus references: phrases may live in either since the v0.22 split.
    return '\n'.join([ROOT.joinpath('SKILL.md').read_text()] + [p.read_text() for p in sorted(ROOT.glob('references/*.md'))])

class PickerPolicyTests(unittest.TestCase):
    def test_exhaustion_requires_new_bounded_evidence_not_scope_expansion(self):
        text=full_text()
        for phrase in ['two consecutive no-selection receipts','DIFFERENT authorized component','not discovery completeness','keep exploration read-only and resource-disjoint','Do not repeat this exploration','Checked scope exhausted','not an enforced runtime guarantee']:
            self.assertIn(phrase,text)
    def test_no_early_exit_and_terminal_results_continue(self):
        text=full_text()
        # Recovery guidance survives; continuation cannot restart the retired executor.
        core = ROOT.joinpath('SKILL.md').read_text()
        for phrase in ['Preserve explicit pauses and existing ownership',
                       'informational invocation changes no services',
                       'no fallback executor', 'do not invent successful pickup']:
            self.assertIn(phrase, core)
        for phrase in ["Ask, don't block", 'work_search', 'not a runtime guarantee']:
            self.assertIn(phrase, text)
        for obsolete in ['Step 0 — fast exit', 'return `[SILENT]` immediately', 'Step 0 fast exit bounds']:
            self.assertNotIn(obsolete, text)

    def test_preserves_authority_and_no_busywork(self):
        text=full_text()
        for phrase in ['No exhaustive scan, broad suite, fabricated task','financial/live/scope gates stay','not product acceptance','exactly `[SILENT]`','no token, cost or time budgets','push, deploy, publish, spend money, place trades','actual process identity']:
            self.assertIn(phrase,text)

    def test_usable_backlog_takes_short_path_and_worker_owns_whole_outcome(self):
        core = ROOT.joinpath('SKILL.md').read_text()
        handoff = ROOT.joinpath('references/handoff.md').read_text()
        discovery = ROOT.joinpath('references/discovery.md').read_text()
        # Legacy recovery references remain, but the public entrypoint is Orbi-only.
        self.assertIn('Orbi', core)
        self.assertIn('never starts, resumes, installs or schedules', core)
        self.assertNotIn('autowork tasks why', core)
        self.assertIn('Historical native-card reference', handoff)
        self.assertIn('Only when no usable backlog task remains', discovery)

    def test_history_reads_require_verified_profile_identity(self):
        text = ROOT.joinpath('references/state-and-recovery.md').read_text()
        for phrase in ['repository basename is not a profile ID',
                       'confirm the exact profile directory exists',
                       'never guess an alias, create a profile',
                       'missing continuity, not an abandoned owner',
                       'SQLite `mode=ro`',
                       'reopen only when the profile inventory or an explicit identity mapping changes']:
            self.assertIn(phrase, text)

    def test_core_stays_lean_and_points_to_every_reference(self):
        core = ROOT.joinpath('SKILL.md').read_text()
        self.assertLess(len(core.encode()), 16000, 'core SKILL.md must stay lean; move detail to references/')
        self.assertIn('../shared/PLAN-HANDOFF.md', core)
        self.assertIn('../../docs/github-native.md', core)
        self.assertNotIn('references/owner-cycle.md', core)
        self.assertNotIn('references/scheduled-policy.md', core)

if __name__=='__main__':unittest.main()
