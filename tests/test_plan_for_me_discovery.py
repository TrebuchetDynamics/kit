"""Offline contracts for bare Plan For Me autonomous project discovery.

These read the real skill, shared contract, adapters and disposable fixtures. They
do not run a model; host/model behavior is evaluated with the planning specimens.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/plan-for-me/SKILL.md'
DISCOVERY = ROOT / 'skills/plan-for-me/references/discovery.md'
RESEARCH_PLAN = ROOT / 'skills/shared/RESEARCH-PLAN.md'
PLANNING_CRAFT = ROOT / 'skills/shared/PLANNING-CRAFT.md'
ADAPTER = ROOT / 'adapters/skills/plan-for-me/SKILL.md'
SCENARIOS = ROOT / 'tests/fixtures/planning/cases.json'


def words(path):
    return ' '.join(path.read_text().split())


class PlanForMeDiscoveryContractTests(unittest.TestCase):
    def test_requests_without_conversation_findings_start_discovery_without_an_interview(self):
        text = words(SKILL)
        for requirement in (
                '## Route the request',
                'references/discovery.md',
                'Do not ask for a goal before investigating',
                'A bare `/plan_for_me` after concrete findings plans those findings',
                'Without that context it is a discovery request, not an interview',
                'Focused planning for that outcome and its authorized prerequisites',
                'Read-only, chat-only, no-write or dry-run',
                'An Orbi-owned planning substep',
                'If the repository has no accepted objective or meaningful source',
                'New product directions stay proposals'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_conversation_scope_precedes_discovery_across_entrypoints(self):
        for path in (SKILL, DISCOVERY, RESEARCH_PLAN):
            with self.subTest(path=path):
                self.assertIn('PLAN-HANDOFF.md#conversation-findings-to-issues', words(path))
                self.assertIn('relevant conversation', words(path))
        mode_row = next(line for line in RESEARCH_PLAN.read_text().splitlines()
                        if line.startswith('| Plan For Me |'))
        self.assertIn('only when neither request nor relevant conversation', mode_row)
        self.assertIn('An explicit target wins', words(SKILL))
        self.assertIn('not the full explicitly requested batch', words(DISCOVERY))

    def test_shared_contract_distinguishes_discovery_from_missing_interactive_intent(self):
        contract = words(RESEARCH_PLAN)
        self.assertIn('project-discovery protocol', contract)
        self.assertIn('Do not ask for a goal before that investigation', contract)
        self.assertIn('Plan With Me asks for the missing goal', contract)
        self.assertIn('Orbi-owned substep stays inside its named task', contract)
        self.assertNotIn('otherwise ask for the missing goal', contract)
        craft = words(PLANNING_CRAFT)
        self.assertIn('Project discovery', craft)
        self.assertIn('never an interview for a goal or invented product scope', craft)

    def test_discovery_reference_defines_goal_authority_evidence_and_batches(self):
        text = words(DISCOVERY)
        for requirement in (
                '## Goal classes',
                'Accepted',
                'Derived engineering',
                'Proposed strategic',
                '## Investigate progressively',
                '`OBSERVED`',
                '`DOCUMENTED`',
                '`INFERRED`',
                '`UNKNOWN`',
                'Goal -> Specification -> Implementation -> Verification -> Task',
                'implemented but unverified',
                'partially implemented',
                '## Prioritize the real frontier',
                'do not fabricate ROI percentages',
                '## Bound the batch',
                'at most eight new tasks',
                '## Reconcile repeated invocations',
                '## Respect authority and persistence',
                'Do not create a local task queue',
                '## Report',
                'Next executable task'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_discovery_allows_ungrouped_tasks(self):
        text = words(DISCOVERY)
        self.assertIn('Goal classes describe intent, not mandatory task grouping', text)
        self.assertIn('A standalone task may be ungrouped', text)
        self.assertIn('an ordinary task needs no epic', text)
        self.assertIn('expansion stays in the `ai-epic`', text)
        self.assertIn('at most eight new tasks', text)
        self.assertIn('observable acceptance and exact known checks', text)
        self.assertIn('bounded scope', text)
        self.assertIn('keep it out of runnable scope until the owner accepts it', text)
        self.assertIn('publish readiness last, but do not implement, restart or schedule', text)
        self.assertNotIn('each executable task needs an existing or justified goal', text)

    def test_read_only_and_coordinator_boundaries_survive_the_default_discovery_route(self):
        text = words(SKILL) + ' ' + words(DISCOVERY)
        for requirement in (
                'save nothing, including queue metadata',
                'same coordinator',
                'authorized prerequisites',
                'Preserve read-only modes, live leases and active workers',
                'preserve the failure'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_portable_adapter_exposes_the_same_discovery_default(self):
        self.assertIn('../../../skills/plan-for-me/SKILL.md', words(ADAPTER))
        text = words(SKILL)
        for requirement in (
                'references/discovery.md',
                'No concrete objective',
                'Do not ask for a goal before investigating',
                'Focused planning',
                'Read-only',
                'An Orbi-owned planning substep'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)

    def test_focused_discovered_and_recovery_routes_consume_shared_decision_closure(self):
        # Entrypoints must not retain the old minor-versus-user triage or fork closure.
        special = ROOT / 'skills/plan-for-me/references/special-cases.md'
        for path, link in (
                (SKILL, '../shared/PLANNING-CRAFT.md#decision-closure'),
                (DISCOVERY, '../../shared/PLANNING-CRAFT.md#decision-closure'),
                (special, '../../shared/PLANNING-CRAFT.md#decision-closure')):
            with self.subTest(path=path):
                text = words(path)
                self.assertIn(link, text)
                target, anchor = link.split('#')
                self.assertEqual((path.parent / target).resolve(), PLANNING_CRAFT)
                self.assertIn('## Decision closure', PLANNING_CRAFT.read_text())
                self.assertNotIn('## Decision closure', path.read_text())
        # Thin adapters load the native policy, rather than duplicating it.
        self.assertIn('../../../skills/plan-for-me/SKILL.md', words(ADAPTER))
        for path in (SKILL,):
            text = words(path)
            self.assertIn('focused tasks and discovered frontiers', text)
            self.assertIn('record planner calls', text)
            self.assertIn('only genuinely owner/external-blocked affected tasks pending', text)
        self.assertNotIn('settle minor ones', words(SKILL))
        self.assertIn('runtime continuation failure is not a new product decision', words(special))
        self.assertIn('Reuse the original task and candidate', words(special))
        self.assertIn('positive trust/capability mechanism is still unidentified', words(special))

    def test_discovery_fixture_matrix_retains_requirements_without_executor(self):
        fixtures = json.loads(SCENARIOS.read_text())
        cases = fixtures['cases']
        required = {'bare-established', 'bare-sparse', 'bare-undefined', 'mature-backlog',
                    'vague-goal', 'verification-gap', 'spec-conflict', 'proposal',
                    'read-only', 'active-dirty', 'repeat', 'large', 'coordinator'}
        self.assertLessEqual(required, set(cases))
        self.assertEqual(cases['bare-established'][1], '')
        self.assertEqual(cases['vague-goal'][1], 'make this better')
        self.assertIn('FMT-02', cases['bare-established'][2]['docs/prd.md'])
        self.assertNotIn('docs/plan.md', cases['bare-sparse'][2])
        self.assertIn('test_trim', cases['bare-sparse'][2]['tests/test_formatting.py'])
        self.assertIn('no product direction', cases['bare-undefined'][2]['README.md'])
        self.assertIn('notes/owner-edit.txt', cases['active-dirty'][2])
        self.assertIn('external-input', fixtures['stall_cases'])
        self.assertIn('ambiguous-round', fixtures['interviews'])
        self.assertFalse(SCENARIOS.with_name('scenarios.py').exists())
        self.assertFalse(SCENARIOS.with_name('interviews.py').exists())


if __name__ == '__main__':
    unittest.main()
