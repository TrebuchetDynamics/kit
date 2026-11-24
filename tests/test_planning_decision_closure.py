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
        interactive = ' '.join((ROOT / 'skills/plan-with-me/SKILL.md').read_text().split())
        for rule in ('user participating in consequential decisions', 'Ask the highest-impact ready question',
                     'A skipped choice stays open', 'no fixed question count'):
            self.assertIn(rule, interactive)

    def test_interview_compatibility_anchor_is_conditional_and_not_a_reread_loop(self):
        pointer = section('skills/shared/RESEARCH-PLAN.md', 'Interactive planning: Plan With Me')
        self.assertIn('../plan-with-me/SKILL.md', pointer)
        self.assertIn('interactive or challenge mode', pointer)
        self.assertLess(len(pointer.split()), 65)
        owner = ' '.join((ROOT / 'skills/plan-with-me/SKILL.md').read_text().split())
        self.assertNotIn('RESEARCH-PLAN.md#interactive-planning-plan-with-me', owner)
        for rule in ('bare “yes” or LGTM', 'round-scoped acceptance',
                     'including confirmation questions', 'exhaustive questioning',
                     'planning synthesis', 'Do not invoke Plan For Me',
                     'Already-loaded sources need no reread'):
            self.assertIn(rule, owner)

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

    def test_conversation_intake_preserves_evidence_and_outcome_sized_issues(self):
        # Instruction checks only: these do not simulate a model reading a chat.
        intake = section('skills/shared/PLAN-HANDOFF.md', 'Conversation findings to issues')
        for rule in ('An explicit target wins', 'several unrelated topics',
                     'Missing or compacted evidence stays unknown',
                     'open and closed issues', 'completed, unsupported',
                     'one fix and acceptance check', 'independently verifiable outcomes',
                     'not an explicit batch', 'without this chat', 'Use reachable sources',
                     'every in-scope topic', 'not its execution permissions'):
            with self.subTest(rule=rule):
                self.assertIn(rule, intake)
        for source, evidence, boundary in (
                ('State-machine analysis', 'unsafe transition', 'Hypotheses versus confirmed failures'),
                ('Grilling, Grill Me or Grill With Docs', 'Accepted answers', 'Skipped questions'),
                ('Bug Harvest', 'Reproducer', 'Already-fixed bugs'),
                ('UI Taste, Impeccable or screenshot review', 'Affected screen/state', 'inspected renders')):
            with self.subTest(source=source):
                rows = [line for line in (ROOT / 'skills/shared/PLAN-HANDOFF.md').read_text().splitlines()
                        if line.startswith(f'| {source} |')]
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertIn(evidence, row)
                self.assertIn(boundary, row)

    def test_preview_and_receipt_distinguish_proposals_from_publication(self):
        receipt = section('skills/shared/PLAN-HANDOFF.md', 'Progress and final receipt')
        preview = receipt.split('### Plan preview', 1)[1].split('### Publication receipt', 1)[0]
        published = receipt.split('### Publication receipt', 1)[1]
        for rule in ('before GitHub publication', 'not a new approval gate',
                     'preview-only/no-write', 'settled answers need no reconfirmation'):
            self.assertIn(rule, receipt)
        for rule in ('observable change', 'acceptance signal', 'real prerequisites',
                     'never invented issue numbers or URLs', 'proposed, not published',
                     'one compact line per issue', 'do not silently omit topics',
                     'Planned checks are not passed checks'):
            self.assertIn(rule, preview)
        for rule in ('verified issue links', 'created, reused, held and unsaved counts',
                     'unmet prerequisite even when the issue has `ai-ready`',
                     'coordination, never a next executable issue', 'actual partial result per issue',
                     'completed, owned/in progress or paused',
                     'Unknown ownership or pause state means eligibility is unverified',
                     'excluding completed, owned or paused work',
                     '**UNSAVED**', '**nothing saved or dispatched**'):
            self.assertIn(rule, published)

    def test_both_routes_reach_single_recovery_policy_and_receipt(self):
        for mode in ('plan-with-me', 'plan-for-me'):
            canonical = ROOT / f'skills/{mode}/SKILL.md'
            adapter = ROOT / f'adapters/skills/{mode}/SKILL.md'
            with self.subTest(mode=mode):
                self.assertIn(f'../../../skills/{mode}/SKILL.md', adapter.read_text())
                self.assertEqual((adapter.parent / f'../../../skills/{mode}/SKILL.md').resolve(), canonical)
                for relative, heading in (
                        ('../shared/PLANNING-CRAFT.md', 'Recovery, provenance and qualification'),
                        ('../shared/PLAN-HANDOFF.md', 'Progress and final receipt'),
                        ('../shared/PLAN-HANDOFF.md', 'Conversation findings to issues')):
                    anchor = heading.lower().replace(',', '').replace(' ', '-')
                    self.assertIn(f'{relative}#{anchor}', canonical.read_text())
                    self.assertTrue(section(str((canonical.parent / relative).resolve().relative_to(ROOT)), heading))
                    self.assertNotIn(f'## {heading}', canonical.read_text())
                for owner in ('PONYTAIL.md', 'COMMUNICATION.md'):
                    self.assertIn(f'../shared/{owner}', canonical.read_text())
                for heading in ('Publication and dependencies',
                                'Persistence, not local-main admission',
                                'Publication receipt', 'Execution handoff'):
                    anchor = heading.lower().replace(',', '').replace(' ', '-')
                    self.assertIn(f'../shared/PLAN-HANDOFF.md#{anchor}', canonical.read_text())
                for boundary in ('Stop planning', 'without implementing or starting a service',
                                 'same coordinator'):
                    self.assertIn(boundary, ' '.join(canonical.read_text().split()))
                self.assertNotIn('An existing Orbi deployment can consume published work immediately', canonical.read_text())

    def test_fully_specified_interactive_request_branches_before_saving(self):
        intake = section('skills/plan-with-me/SKILL.md', 'Learn enough to ask a useful question')
        for rule in ('A fully specified request needs no interview',
                     'In no-write mode, return the complete plan inline and write nothing',
                     'In writable mode, preview the batch, then follow Plan Handoff'):
            self.assertIn(rule, intake)
        self.assertNotIn('save the complete requested batch and stop planning', intake)

    def test_thin_intent_does_not_force_speculative_draft_tasks(self):
        intake = section('skills/plan-with-me/SKILL.md', 'Learn enough to ask a useful question')
        for rule in ('Include draft tasks only when supported by known intent and evidence',
                     'zero invented tasks', 'One question, the highest-impact decision still open'):
            self.assertIn(rule, intake)

    def test_autonomous_completion_allows_evidenced_zero_new_issues(self):
        text = ' '.join((ROOT / 'skills/plan-for-me/SKILL.md').read_text().split())
        for rule in ('missing intent, existing coverage or no-write mode',
                     'explicit disposition', 'every actionable accepted outcome',
                     'new or reused issue', 'proposed contract inline'):
            self.assertIn(rule, text)
        self.assertNotIn('A roadmap or prose plan with no task records', text)
        self.assertNotIn('A plan without tasks is enough', text)

    def test_settled_approach_and_material_choice_are_distinct_branches(self):
        for mode in ('plan-with-me', 'plan-for-me'):
            with self.subTest(mode=mode):
                text = ' '.join((ROOT / f'skills/{mode}/SKILL.md').read_text().split())
                self.assertIn('When a governing decision fixes the approach, cite it', text)
                self.assertIn('acceptance and verification', text)
                self.assertIn('Compare practical approaches when a material choice remains', text)
                self.assertNotIn('Generate several approaches before choosing', text)

    def test_failed_handoff_summaries_route_to_per_issue_receipt(self):
        for path in ('skills/plan-with-me/SKILL.md', 'skills/plan-for-me/SKILL.md',
                     'skills/plan-for-me/references/discovery.md',
                     'skills/shared/RESEARCH-PLAN.md'):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertIn('PLAN-HANDOFF.md#publication-receipt', text)
                self.assertNotIn('Failed persistence is **UNSAVED**', text)
                self.assertNotIn('Identify any failed handoff as UNSAVED', text)
        receipt = section('skills/shared/PLAN-HANDOFF.md', 'Progress and final receipt')
        for rule in ('actual partial result per issue', 'last_verified',
                     '**UNKNOWN**', 'creation never attempted', 'not retry authorization'):
            self.assertIn(rule, receipt)

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

    def test_paired_reconciliation_specimens_retain_page_two_and_failure_evidence(self):
        # Inert model-evaluation inputs and expected results, not a matching engine.
        fixture_dir = ROOT / 'tests/fixtures/planning'
        cases = json.loads((fixture_dir / 'cases.json').read_text())['cases']
        expected = section('tests/fixtures/planning/README.md', 'Paired open-issue reconciliation specimens')
        for scenario in ('issue-inventory', 'issue-drift', 'issue-page-failure'):
            paired = []
            for mode in ('plan-with-me', 'plan-for-me'):
                name = f'{mode}-{scenario}'
                with self.subTest(case=name):
                    self.assertIn(name, cases)
                    route, request, files = cases[name]
                    self.assertEqual(route, f'skills/{mode}/SKILL.md')
                    self.assertIn('do not implement', request)
                    self.assertIn('no-write', request)
                    self.assertIn(name, expected)
                    self.assertIn('GitHub Issues', files['AGENTS.md'])
                    inventory = files['notes/github.md']
                    for evidence in ('Page 1', 'Page 2', 'per_page=3', 'pull_request',
                                     '#812', 'Quiet reconnects', 'external-reporter',
                                     'relevant comments', 'linked PR', 'parent #800',
                                     'blockedBy #805', '#811', 'owner=worker-a',
                                     '#809', 'merged PR #808', '#813'):
                        self.assertIn(evidence, inventory)
                    if scenario == 'issue-drift':
                        for evidence in ('#812 now owned', '#814', 'new match', 'foreign edit'):
                            self.assertIn(evidence, files['notes/refresh.md'])
                    if scenario == 'issue-page-failure':
                        self.assertIn('Page 2: HTTP 403', inventory)
                        self.assertIn('unknown', inventory)
                    paired.append(files)
            self.assertEqual(*paired)
        for outcome in ('#810 covered as-is', '#812 refine only the missing acceptance',
                        '#811 contract and labels unchanged', '#813 related, not blockedBy',
                        '#809 already delivered', 'only P1 new', '#814 reuse after refresh',
                        'no writes', 'Page 2: HTTP 403', 'uniqueness unverified',
                        'NOT_RUN', 'not model recall'):
            self.assertIn(outcome, expected)

    def test_lgtm_continuation_specimens_bind_inputs_to_scoped_results(self):
        """Inert source examples, not executed conversations or a model evaluator."""
        examples = section('skills/lgtm/SKILL.md', 'Examples').split(' - ')
        cases = (
            ('One clear planning recommendation', '`yes`',
             'accept that choice and continue planning, without implementation'),
            ('Latest round: six planning questions', '`yes`',
             'accept the recommended batch and continue planning, not implementation'),
            ('Named retention and access choices', '`lgtm`',
             'settle both choices and continue planning'),
            ('Standalone plan ready', '`lgtm`',
             'accept the plan, save the authorized planning artifacts, then stop'),
            ('Accepted plan', '`implement this plan`',
             'enter the authorized execution workflow'),
            ('Earlier request: implement, commit and push', '`lgtm`',
             'finish the already-authorized implementation, commit and push'),
            ('Earlier implementation permission, then standalone planning', '`lgtm`',
             'finish planning only; earlier unrelated permission does not widen it'),
            ('Continuing no-write and no-push limits', '`lgtm`',
             'discuss only, with no file/GitHub writes, commit or push'),
            ('Completed work with nothing authorized left', '`lgtm`',
             'acknowledge once and stop'),
            ('Session todo list: 2 of 5 done', '`lgtm`',
             'finish the authorized patch, run its tests, and mark each done only after '
             'its check passes; leave push open and report “Push blocked: continuing '
             'no-push limit; explicit scope change required” once, while continuing '
             'independent authorized items'),
            ('Unambiguous four-item cleanup batch in an implementation workflow', '`lgtm`',
             'verify and implement all supported items'),
            ('Equivalent internal test helpers within authorized implementation', '`lgtm`',
             'choose the safe reversible default and continue'),
            ('Retention has a clear recommendation', '`lgtm`',
             'accept retention and ask only about access'),
            ('Round 1 is settled. Round 2 recommends', '`lgtm`',
             'accept both exactly as stated and continue evaluation planning'),
        )
        for checkpoint, reply, outcome in cases:
            with self.subTest(checkpoint=checkpoint, reply=reply):
                matching = [example for example in examples if checkpoint in example]
                self.assertEqual(len(matching), 1, checkpoint)
                self.assertIn(reply, matching[0])
                self.assertIn(outcome, matching[0])
        self.assertIn('Keep Round 1 settled', ' '.join(examples))
        self.assertIn('or start the bot', ' '.join(examples))
        # Acceptance and execution boundaries come from the existing shared owners.
        uncertainty = section('skills/shared/PLANNING-CRAFT.md', 'Consequential uncertainty')
        self.assertIn('LGTM accepts all clear recommendations shown in that round', uncertainty)
        self.assertIn('Explicit partial approval or corrections narrow acceptance', uncertainty)
        authority = section('skills/shared/RESEARCH-PLAN.md', 'Planning artifact and authority contract')
        for rule in ('Acceptance of a plan is not execution authority',
                     'Earlier unrelated implementation permission does not widen this request',
                     'Later explicit instruction to implement the accepted plan',
                     'Do not ask an already-authorized coordinator to approve again'):
            self.assertIn(rule, authority)

    def test_readiness_verdict_distinguishes_failed_and_missing_required_evidence(self):
        audit = section('skills/plan-with-me/references/special-cases.md',
                        'Audits and readiness questions')
        for rule in ('not ready', 'observed failed required check',
                     'even when other checks are unverified',
                     'unverified', 'no required check has an observed failure',
                     'name the missing receipt and qualification action',
                     'not an assumed repair', 'ready',
                     'all required checks have verified passing evidence'):
            with self.subTest(rule=rule):
                self.assertIn(rule, audit)
        for example in ('Unverified: Android device receipt missing',
                        'Not ready: Android check failed; desktop receipt unverified',
                        'Ready: all required desktop and Android checks verified passing'):
            self.assertIn(example, audit)
        self.assertNotIn('ready, or not ready and why', audit)

    def test_challenge_synthesis_hands_off_without_reopening_settled_answers(self):
        synthesis = section('skills/grill-me/SKILL.md', 'Synthesis (when the frontier is empty)')
        for rule in ('answer sources', 'genuinely unresolved or skipped questions',
                     'settled answers stay settled', 'Plan With Me challenge mode',
                     '../shared/PLAN-HANDOFF.md', 'no implementation invitation',
                     'no repeated approval', 'Outside planning', 'confirmation gate'):
            with self.subTest(rule=rule):
                self.assertIn(rule, synthesis)
        self.assertNotIn('Should I start implementing', synthesis)
        skill = ' '.join((ROOT / 'skills/grill-me/SKILL.md').read_text().split())
        self.assertIn('planning handoff is complete', skill.split('**Done when:**', 1)[1])
        self.assertIn('Outside planning, confirm user alignment', skill)
        challenge = section('skills/plan-with-me/SKILL.md', 'Challenge mode')
        self.assertIn('planning synthesis', challenge)

    def test_special_cases_condition_visual_and_flutter_advice_on_evidence(self):
        companion = section('skills/plan-with-me/references/special-cases.md',
                            'Companion frontends and platform scope')
        for rule in ('separate browser build', 'source or user intent confirms Flutter',
                     'without Flutter evidence', 'framework-neutral',
                     'existing website and native companion'):
            self.assertIn(rule, companion)
        self.assertNotIn('clarify whether a separate Flutter browser build is also required', companion)
        quality = section('skills/plan-for-me/references/special-cases.md',
                          'Aspirational quality goals')
        for rule in ('source or user intent', 'relevant visual surface',
                     'desktop and narrow localized render', 'premium CLI',
                     'neither screenshots nor a Flutter build question',
                     'command output, errors and task completion',
                     'not proof of current readiness'):
            self.assertIn(rule, quality)

    def test_special_cases_are_reachable_through_loaded_planning_routes(self):
        # Resolve the real reference chain; these source checks do not call a model.
        for mode in ('plan-with-me', 'plan-for-me'):
            adapter = ROOT / f'adapters/skills/{mode}/SKILL.md'
            owner_link = f'../../../skills/{mode}/SKILL.md'
            self.assertIn(owner_link, adapter.read_text())
            owner = (adapter.parent / owner_link).resolve()
            reference = (owner.parent / 'references/special-cases.md').resolve()
            self.assertIn('references/special-cases.md', owner.read_text())
            self.assertTrue(reference.is_file())
        owner = ROOT / 'skills/plan-with-me/SKILL.md'
        self.assertIn('../grill-me/SKILL.md', section(str(owner.relative_to(ROOT)), 'Challenge mode'))
        grill = (owner.parent / '../grill-me/SKILL.md').resolve()
        self.assertIn('../shared/PLAN-HANDOFF.md', grill.read_text())
        self.assertTrue((grill.parent / '../shared/PLAN-HANDOFF.md').resolve().is_file())

    def test_closure_does_not_widen_planning_writes_or_execution_authority(self):
        contract = section('skills/shared/RESEARCH-PLAN.md', 'Planning artifact and authority contract')
        for rule in ('Save the requested plan/batch, then stop', 'same coordinator',
                     'save nothing, including queue metadata or research scratch',
                     'do not write them during planning',
                     'Acceptance of a plan is not execution authority'):
            self.assertIn(rule, contract)


if __name__ == '__main__':
    unittest.main()
