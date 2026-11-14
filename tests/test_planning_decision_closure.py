"""Focused instruction contracts, not model compliance or reduced-stall evidence."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def section(path, heading):
    text = (ROOT / path).read_text()
    marker = f'## {heading}\n'
    if marker not in text:
        return ''
    return ' '.join(text.split(marker, 1)[1].split('\n## ', 1)[0].split())


class PlanningDecisionClosureTests(unittest.TestCase):
    def test_every_material_finding_gets_an_actionable_disposition(self):
        # Losing the planner-resolvable branch sends technical choices back to owners.
        closure = section('skills/shared/PLANNING-CRAFT.md', 'Decision closure')
        for disposition, action in (
                ('Already answered', 'copy the answer and source into the affected task'),
                ('Planner-resolvable', 'resolve consequential engineering choices within delegated scope'),
                ('Worker-reversible', 'leave reversible coding details to the worker'),
                ('Owner/external-blocked', 'exact missing intent, authority or input and resume condition')):
            with self.subTest(disposition=disposition):
                self.assertIn(disposition, closure)
                self.assertIn(action, closure)
        self.assertIn('No material finding remains unclassified in a ready task', closure)
        self.assertIn('Recheck changed findings, not the whole unchanged planning pass', closure)

    def test_closure_walks_inputs_to_checks_without_inventing_external_blockers(self):
        closure = section('skills/shared/PLANNING-CRAFT.md', 'Decision closure')
        for rule in ('starting inputs through implementation and verification to handoff',
                     'interfaces, data, error, compatibility and migration behavior',
                     'reachable inputs and setup', 'bounded prerequisite repairs',
                     'exact checks and success evidence',
                     'New tests and fixtures the task can create are deliverables, not external blockers',
                     'Keep real live qualification separate and unmet',
                     'no offline substitute or waiver'):
            with self.subTest(rule=rule):
                self.assertIn(rule, closure)

    def test_decision_map_is_prose_not_a_new_schema_or_clear_task_ceremony(self):
        closure = section('skills/shared/PLANNING-CRAFT.md', 'Decision closure')
        for rule in ('selected approach and evidence/reason', 'rejected alternative when meaningful',
                     'affected task IDs and acceptance/check', 'not a new required field',
                     'For a clear task, fill only actual gaps'):
            self.assertIn(rule, closure)
        builder = section('skills/shared/PLANNING-CRAFT.md', 'Builder check before handoff')
        self.assertIn('#decision-closure', builder)
        self.assertNotIn('**Minor**', builder)
        self.assertNotIn('**Theirs**', builder)

    def test_mode_specific_decisions_preserve_interview_and_authority(self):
        craft = section('skills/shared/PLANNING-CRAFT.md', 'Facts and decision authority')
        self.assertIn('Plan For Me resolves evidence-supported engineering trade-offs', craft)
        self.assertIn('Plan With Me retains consequential intent interviews', craft)
        self.assertIn('Never infer authorization from an engineering preference, silence or an Accepted heading', craft)
        interactive = section('skills/shared/RESEARCH-PLAN.md', 'Interactive planning: Plan With Me')
        for rule in ('user participating in consequential decisions', 'Ask the highest-impact ready question',
                     'A skipped choice stays open', 'no fixed question count'):
            self.assertIn(rule, interactive)

    def test_handoff_requires_reachable_contract_not_just_valid_metadata(self):
        handoff = section('skills/shared/PLAN-HANDOFF.md', 'One planning pass, one handoff')
        self.assertIn('PLANNING-CRAFT.md#decision-closure', handoff)
        self.assertIn('Persist each material finding', handoff)
        self.assertIn('exact missing input and resume condition', handoff)
        publication = section('skills/shared/PLAN-HANDOFF.md', 'Publication and dependencies')
        self.assertIn('Read back every issue, governing source', publication)
        research = section('skills/shared/RESEARCH-PLAN.md', 'Research and persistence method')
        self.assertIn('PLANNING-CRAFT.md#decision-closure', research)

    def test_task_scope_closes_repository_obligations_from_source(self):
        evidence = section('skills/shared/PLANNING-CRAFT.md', 'Source-backed task scope')
        for rule in ('Repo obligations triggered:', 'normative doc owner and section',
                     'generated outputs, guards and fixtures',
                     'every planned write in `touches`', 'validation in `checks`',
                     'file:line', 'keep or re-baseline', 'minimum versus maximum',
                     'current event owners', 'nested interactive elements',
                     'Preserve required caveat copy verbatim'):
            self.assertIn(rule, evidence)
        acceptance = section('skills/shared/PLANNING-CRAFT.md', 'Executable acceptance')
        for rule in ('measurement seam', 'units and tolerance', 'observation window',
                     'instrumented API, exact filter and reset point'):
            self.assertIn(rule, acceptance)

    def test_builder_reads_sources_before_runnable_publication(self):
        builder = section('skills/shared/PLANNING-CRAFT.md', 'Builder check before handoff')
        for rule in ('before committing the batch or making it runnable',
                     'implementation, existing tests and normative docs',
                     'cite file:line', 'required docs missing from `touches`'):
            self.assertIn(rule, builder)

    def test_handoff_makes_github_disposition_explicit(self):
        handoff = section('skills/shared/PLAN-HANDOFF.md', 'Publication and dependencies')
        for rule in ('ready/waiting/proposed status', 'actual ownership',
                     'final publication phase', 'Read back labels',
                     'not pickup, implementation or merge'):
            self.assertIn(rule, handoff)

    def test_recovery_preserves_guards_and_original_evidence(self):
        recovery = section('skills/shared/PLANNING-CRAFT.md', 'Recovery, provenance and qualification')
        for rule in ('missing recovery/state-refresh step', 'guard that detects stale state',
                     'Cite the source supporting the repair', 'retain existing negative cases',
                     'never weaken a guard just to unblock work',
                     'narrow provenance stage', 'original oracle bytes and identity',
                     'original versus derived evidence', 'authorized future changes',
                     'never silently overwrite or re-baseline the oracle',
                     'no new evidence registry or file format'):
            with self.subTest(rule=rule):
                self.assertIn(rule, recovery)

    def test_recovery_separates_observation_and_qualification(self):
        recovery = section('skills/shared/PLANNING-CRAFT.md', 'Recovery, provenance and qualification')
        for rule in ('Label historical audits as historical', 'available current observations',
                     'mismatch and remaining uncertainty',
                     'An old host audit is not proof of current service presence',
                     'do not fabricate a live inspection or assume a missing service',
                     'Environment/display restoration has its own acceptance',
                     'application/device qualification remains separately unmet',
                     'until its actual checks run',
                     'native `blockedBy` dependency on its real recovery prerequisite',
                     'independent repairs remain independent',
                     'Do not force a split of an existing owned task merely because runtime failed'):
            with self.subTest(rule=rule):
                self.assertIn(rule, recovery)

    def test_receipt_is_compact_and_distinguishes_possible_from_observed_delivery(self):
        receipt = section('skills/shared/PLAN-HANDOFF.md', 'Progress and final receipt')
        for rule in ('Normally send one useful progress update and a final receipt',
                     'material blockers or long-running work', 'not a rigid message quota',
                     'issue links', 'ready/waiting/proposed', 'native dependencies',
                     'actual checks and unmet gates', 'generic possible consumer',
                     'observed deployment', 'pickup or timers require current evidence',
                     'Kit remains paused and live-unqualified'):
            with self.subTest(rule=rule):
                self.assertIn(rule, receipt)

    def test_both_routes_reach_single_recovery_policy_and_receipt(self):
        for mode in ('plan-with-me', 'plan-for-me'):
            canonical = ROOT / f'skills/{mode}/SKILL.md'
            adapter = ROOT / f'adapters/skills/{mode}/SKILL.md'
            with self.subTest(mode=mode):
                self.assertIn(f'../../../skills/{mode}/SKILL.md', adapter.read_text())
                self.assertEqual((adapter.parent / f'../../../skills/{mode}/SKILL.md').resolve(), canonical)
                for relative, heading in (
                        ('../shared/PLANNING-CRAFT.md', 'Recovery, provenance and qualification'),
                        ('../shared/PLAN-HANDOFF.md', 'Progress and final receipt')):
                    anchor = heading.lower().replace(',', '').replace(' ', '-')
                    self.assertIn(f'{relative}#{anchor}', canonical.read_text())
                    self.assertTrue(section(str((canonical.parent / relative).resolve().relative_to(ROOT)), heading))
                    self.assertNotIn(f'## {heading}', canonical.read_text())
                for owner in ('PONYTAIL.md', 'COMMUNICATION.md'):
                    self.assertIn(f'../shared/{owner}', canonical.read_text())
                for boundary in ('Read-only/questions-only/no-write', 'publish `ai-ready` last',
                                 'Stop planning', 'without implementing or starting a service',
                                 'same coordinator', 'existing issue'):
                    self.assertIn(boundary, ' '.join(canonical.read_text().split()))
                self.assertNotIn('An existing Orbi deployment can consume published work immediately', canonical.read_text())

    def test_paired_recovery_specimens_cover_inputs_and_document_expected_outcomes(self):
        fixture_dir = ROOT / 'tests/fixtures/planning'
        cases = json.loads((fixture_dir / 'cases.json').read_text())['cases']
        readme = ' '.join((fixture_dir / 'README.md').read_text().split())
        inputs = {
            'guard-refresh': {'src/session.py': 'raise ValueError("stale session")',
                              'tests/test_session.py': 'test_rejects_stale',
                              'docs/session.md': 'refresh()'},
            'original-oracle': {'evidence/original.txt': 'preset=amber; result=17',
                                'docs/provenance.md': 'derived',
                                'config/preset.txt': 'preset=violet'},
            'recovery-qualification': {'notes/historical-audit.md': 'historical',
                                       'notes/current-observation.md': 'unverified',
                                       'docs/acceptance.md': 'Android/app',
                                       'notes/issues.md': 'blockedBy'},
        }
        for scenario, sources in inputs.items():
            paired_files = []
            for mode in ('plan-with-me', 'plan-for-me'):
                name = f'{mode}-{scenario}'
                with self.subTest(case=name):
                    self.assertIn(name, cases)
                    route, request, files = cases[name]
                    self.assertEqual(route, f'skills/{mode}/SKILL.md')
                    self.assertIn('do not implement', request)
                    self.assertIn('GitHub Issues', files['AGENTS.md'])
                    for path, evidence in sources.items():
                        self.assertIn(evidence, files[path])
                    self.assertIn(name, readme)
                    paired_files.append(files)
            self.assertEqual(*paired_files)
        for expected in ('retain the stale-state guard and negative cases',
                         'preserve original oracle bytes and identity',
                         'historical/current/unverified', 'qualification remains unmet',
                         'native dependency only on the real recovery prerequisite',
                         'independent repairs stay independent', 'existing owned issue',
                         'no implementation during planning', 'not model adherence',
                         'one useful progress update', 'ready/waiting/proposed'):
            self.assertIn(expected, readme)

    def test_closure_does_not_widen_planning_writes_or_execution_authority(self):
        contract = section('skills/shared/RESEARCH-PLAN.md', 'Planning artifact and authority contract')
        for rule in ('Save the requested plan/batch, then stop', 'same coordinator',
                     'save nothing, including queue metadata or research scratch',
                     'do not write them during planning',
                     'Acceptance of a plan is not execution authority'):
            self.assertIn(rule, contract)


if __name__ == '__main__':
    unittest.main()
