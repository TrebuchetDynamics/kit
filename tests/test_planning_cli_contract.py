"""Planning examples at the public task CLI seam; runtime detail stays in test_task_commands."""
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / 'pi-autowork/pi_autowork/command.py'
WORKCENTER = 'skills/shared/TODO-WORKCENTER.md'
PLANNER = 'skills/plan-for-me/SKILL.md'
HANDOFF = 'skills/shared/PLAN-HANDOFF.md'
INTERACTIVE = ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md')
AUTONOMOUS = (PLANNER, 'adapters/skills/plan-for-me/SKILL.md')
SPECIAL_CASES = 'skills/plan-with-me/references/special-cases.md'
TASK_WRITING_LINKS = (
    *((path, ('../../../skills/shared/' if path.startswith('adapters/') else '../shared/')
       + 'RESEARCH-PLAN.md') for path in (*INTERACTIVE, *AUTONOMOUS)),
    ('skills/docs-sync/SKILL.md', '../shared/TODO-WORKCENTER.md'),
    ('adapters/skills/docs-sync/SKILL.md', '../../../skills/docs-sync/SKILL.md'),
    ('skills/autoresearch/SKILL.md', '../shared/RESEARCH-PLAN.md'),
    ('adapters/skills/autoresearch/SKILL.md', '../../../skills/shared/TODO-WORKCENTER.md'),
    ('skills/autowork/SKILL.md', '../shared/TODO-WORKCENTER.md'),
    ('adapters/skills/autowork/SKILL.md', '../../../skills/autowork/SKILL.md'),
    ('skills/autowork/references/backlog-planning.md', '../../shared/TODO-WORKCENTER.md'),
    ('skills/plan-for-me/references/discovery.md', '../../shared/RESEARCH-PLAN.md'),
    ('skills/goal/SKILL.md', '../shared/COMMON-CONTRACT.md'),
    ('skills/autonomous-codebase-improver/SKILL.md', '../shared/TODO-WORKCENTER.md'),
    ('skills/shared/COMMON-CONTRACT.md', 'TODO-WORKCENTER.md'),
)


def prose(path):
    return ' '.join((ROOT / path).read_text().split())


class PlanningCliContractTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / 'repo'
        shutil.copytree(ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store', self.repo)
        for args in (('init', '-q'), ('add', '-A'), ('commit', '-qm', 'fixture')):
            subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid', *args],
                           check=True, capture_output=True, text=True)

    def tasks(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(COMMAND), 'tasks', *args],
                                cwd=self.repo, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        return result

    def show(self):
        return json.loads(self.tasks('show', 'T-1', '--worktree').stdout)

    def test_documented_planning_close_forms_are_manual(self):
        original = (self.repo / 'tasks/items/T-1.md').read_bytes()
        for flags, missing in ((('--by', 'WHO'), '--reason'), (('--reason', 'TEXT'), '--by')):
            refused = subprocess.run([sys.executable, str(COMMAND), 'tasks', 'done', 'T-1', *flags],
                                     cwd=self.repo, capture_output=True, text=True, timeout=60)
            self.assertEqual(refused.returncode, 2)
            self.assertIn(missing, refused.stderr)
            self.assertEqual((self.repo / 'tasks/items/T-1.md').read_bytes(), original)
        for path in (PLANNER, WORKCENTER, 'adapters/skills/plan-for-me/SKILL.md'):
            forms = re.findall(r'`(autowork tasks done [^`]+)`', prose(path))
            self.assertTrue(forms, path)
            for index, form in enumerate(forms):
                with self.subTest(path=path, form=form):
                    tid = self.tasks('add', '--goal', 'G-1', '--title', f'{path} {index}',
                                     '--short', 'Planning close', '--kind', 'plan', '--scope', 'Plan',
                                     '--acceptance', 'Saved', '--checks', 'true', '--touches', 'docs/').stdout.split()[-1]
                    args = shlex.split(form.replace('autowork tasks ', '').replace('[--evidence REF]', ''))
                    args = [tid if arg == 'ID' else arg for arg in args]
                    result = subprocess.run([sys.executable, str(COMMAND), 'tasks', *args],
                                            cwd=self.repo, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    record = json.loads(self.tasks('show', tid, '--worktree').stdout)
                    self.assertEqual((record['status'], record['closure']['provenance']), ('done', 'manual'))
                    self.assertEqual((record['closure']['actor'], record['closure']['reason']), ('WHO', 'TEXT'))
                    self.assertFalse((self.repo / f'tasks/evidence/{tid}.toml').exists())
        center = prose(WORKCENTER)
        for required in ('verified_depends_on', 'owner_waiver', 'owner_qualification', 'Never invent'):
            self.assertIn(required, center)

    def test_documented_literal_update_reconciles_a_stale_read(self):
        center = prose(WORKCENTER)
        read = 'autowork tasks show ID --worktree'
        update = 'autowork tasks field ID --json field.json --expect REV'
        self.assertIn(read, center)
        self.assertIn(update, center)
        shown = json.loads(self.tasks(*['T-1' if arg == 'ID' else arg
                                        for arg in shlex.split(read)[2:]]).stdout)
        literal = '`literal` $(not-a-command) $VAR "quoted" café\nsecond line'
        (self.repo / 'field.json').write_text(json.dumps({'label': 'scope', 'value': literal}), encoding='utf-8')
        self.tasks('field', 'T-1', 'Evidence', 'Concurrent evidence to preserve')
        path = self.repo / 'tasks/items/T-1.md'
        current = path.read_bytes()
        args = [shown['record_revision'] if arg == 'REV' else 'T-1' if arg == 'ID' else arg
                for arg in shlex.split(update)[2:]]
        refused = self.tasks(*args, ok=False)
        self.assertIn('reread', refused.stderr)
        self.assertEqual(path.read_bytes(), current)
        latest = self.show()
        # Reconcile the intended scope delta, not a replay of the earlier whole record.
        self.assertEqual(latest['scope'], shown['scope'])
        self.assertIn('Concurrent evidence to preserve', latest['notes'])
        args[-1] = latest['record_revision']
        self.tasks(*args)
        final = self.show()
        self.assertEqual(final['scope'], literal)
        self.assertIn('Concurrent evidence to preserve', final['notes'])
        for required in ('operation-local', 'reread', 'reapply', 'blind retry', 'stale full snapshot'):
            self.assertIn(required, center)

    def assert_task_writing_routes(self):
        for path, link in TASK_WRITING_LINKS:
            with self.subTest(route=path):
                self.assertRegex(prose(path), r'\]\(' + re.escape(link) + r'(?:#[^)]+)?\)')
                self.assertTrue((ROOT / path).parent.joinpath(link).is_file())

    def test_planners_share_descriptive_task_name_policy(self):
        protocol = 'skills/shared/RESEARCH-PLAN.md'
        craft = 'skills/shared/PLANNING-CRAFT.md'
        self.assert_task_writing_routes()
        records = prose(protocol).split('### Task records', 1)[1].split('## Full requested batch', 1)[0]
        naming = prose(craft).split('## Name things precisely', 1)[1].split('## Plan for an unattended worker', 1)[0]
        for section in (records, naming):
            self.assertIn('TODO-WORKCENTER.md#task-names', section)
        policy = prose(WORKCENTER).split('### Task names', 1)[1].split('### Task descriptions', 1)[0]
        for rule in ('concrete action or observable outcome', 'affected component or user-visible object',
                     'without opening the task', 'condition or failure case only when',
                     'action-led', 'outcome-led', 'padding', 'unexplained acronyms',
                     'Improve', 'Fix', 'Update', 'standalone summary of at most 40 characters',
                     'distinguishing object and outcome', 'Do not merely truncate', 'beside sibling tasks',
                     'repeat the ID', 'Before saving', 'creating or materially refining',
                     'both planning modes', 'no extra interview',
                     'meaning, acceptance, ID, authority or status',
                     'No title length cap', 'CLI validation or selection'):
            with self.subTest(rule=rule):
                self.assertIn(rule, policy)
        for kind, weak, title, short in (
                ('Feature', 'Improve downloads', 'Add invoice downloads for offline review',
                 'Download invoices for offline review'),
                ('Defect', 'Fix retries', 'Stop invoice retries after payment succeeds',
                 'Stop retries after invoice payment'),
                ('Planning', 'Update plan', 'Plan offline invoice checks before rollout',
                 'Plan offline invoice checks')):
            with self.subTest(example=kind):
                self.assertIn(f'| {kind} | {weak} | {title} | {short} |', policy)
                self.assertLessEqual(len(short), 40)

    def test_task_writers_share_actionable_description_policy(self):
        self.assert_task_writing_routes()
        for path in ('skills/shared/RESEARCH-PLAN.md', HANDOFF):
            self.assertIn('TODO-WORKCENTER.md#task-descriptions', prose(path))
        policy = prose(WORKCENTER).split('### Task descriptions', 1)[1].split('## Read orders before selecting', 1)[0]
        for rule in ('Plan For Me', 'Plan With Me', 'Docs Sync', 'Autoresearch', 'Autowork discovery',
                     'other task-producing skills', 'intended behavior change', 'bounded context',
                     'not just a path list', 'constraints and exclusions', 'concrete first action',
                     'source-backed decisions', 'required inputs', 'observable results', 'exact commands',
                     'future tests unrun', 'genuinely unavailable', 'resume condition',
                     'brief notes only where they add information', 'Do not repeat',
                     'Link shared workflow rules', 'mandatory checks', 'as an implementer',
                     'unresolved intent stays explicit', 'active contract', 'No fixed prose length',
                     'not a schema or CLI quality gate'):
            with self.subTest(rule=rule):
                self.assertIn(rule, policy)

    def test_completed_task_retention_is_minimal_and_safe(self):
        # Instruction contract only; this does not prove a live cleanup ran.
        policy = prose(WORKCENTER).split('## Completed-task retention', 1)[1].split('## Rolling planning', 1)[0]
        for rule in ('Delete eligible completed task records', 'Git history',
                     'no arbitrary keep-last-N', 'Audit/read-only', 'actual worker/session activity',
                     'closure and integration', 'ordinary dependency edges', 'inactive surviving tasks',
                     'verified_depends_on', 'manual closure', 'immutable Git',
                     'autowork tasks delete ID', 'warnings, not safety refusals',
                     'dedicated receipts/reports', 'runtime recovery state',
                     'goal status', 'empty history is not proof',
                     'autowork tasks validate --worktree', 'retained record'):
            with self.subTest(rule=rule):
                self.assertIn(rule, policy)
        for path in ('skills/docs-sync/SKILL.md', 'adapters/skills/docs-sync/SKILL.md'):
            text = prose(path)
            self.assertIn('TODO-WORKCENTER.md#completed-task-retention', text)
            self.assertIn('mandatory', text)
            self.assertIn('within scope', text)
        core = prose('skills/docs-sync/SKILL.md')
        self.assertIn('not a separate cleanup approval', core)
        self.assertNotIn('Closed records stay in `tasks/items/` with their evidence', prose(WORKCENTER))
        self.assertNotIn('Preserve completed tasks and historical plan bodies',
                         prose('skills/docs-sync/references/concurrent-maintenance.md'))
        archive = prose('skills/docs-sync/references/todo-archive.md')
        self.assertIn('TODO-WORKCENTER.md#completed-task-retention', archive)
        self.assertNotIn('The closed record stays', archive)
        self.assertIn('frozen, read-only history', archive)

    def test_identifier_guidance_matches_current_allocation_without_renaming_history(self):
        center = prose(WORKCENTER)
        self.assertIn('plain numbered IDs', center)
        self.assertIn('do not append a hash or random suffix', center)
        self.assertIn('Keep existing IDs and references intact', center)
        self.assertNotIn('two-hex-digit', center)
        self.assertNotIn('never create two tasks with the same ID', center)
        before = (self.repo / 'tasks/items/T-1.md').read_bytes()
        self.assertRegex(self.tasks('new-id').stdout.strip(), r'^T-\d+$')
        self.assertEqual((self.repo / 'tasks/items/T-1.md').read_bytes(), before)

    def test_all_planning_routes_require_main_persistence_before_completion(self):
        # Instruction coverage only; no claim that a model or live runner follows it.
        policy = prose(HANDOFF).split('## Main-branch persistence', 1)[1].split(
            '## One planning pass, one handoff', 1)[0]
        for required in ('canonical local `main`', 'before reporting planning complete',
                         'standalone planning, rolling plans and Autowork-owned planning substeps',
                         'git worktree list --porcelain', 'actual writer ownership',
                         'autowork tasks', 'attributable batch', 'branch-local commit',
                         'intermediate save', 'supported path', 'preserving unrelated edits and active workers',
                         'read back', 'autowork tasks validate --worktree .', 'autowork tasks why ID',
                         'on canonical `main`', 'selection was not assessed', 'main persistence pending',
                         'exact blocker', 'no-write and no-commit restrictions take precedence',
                         'no implementation, push, installation or runner-start authority',
                         'same coordinator'):
            with self.subTest(rule=required):
                self.assertIn(required, policy)
        protocol = prose('skills/shared/RESEARCH-PLAN.md')
        self.assertIn('PLAN-HANDOFF.md#main-branch-persistence', protocol)
        self.assertIn('every writable planning route', protocol)
        for path in (*INTERACTIVE, *AUTONOMOUS):
            with self.subTest(route=path):
                text = prose(path)
                self.assertIn('PLAN-HANDOFF.md#main-branch-persistence', text)
                self.assertIn('canonical `main`', text)
                self.assertIn('before reporting planning complete', text)
                self.assertIn('branch-only save remains pending', text)

    def test_readiness_guidance_separates_selection_from_dispatch_and_delivery(self):
        handoff = prose(HANDOFF)
        self.assertIn('committed-store selection', handoff)
        self.assertIn('admission', handoff)
        self.assertIn('dispatch', handoff)
        self.assertIn('branch-local', handoff)
        self.assertIn('consumer', handoff)
        self.assertNotIn('checks the ordered frontier within the named tasks\' goals', handoff)
        center = prose(WORKCENTER)
        for required in ('hot production', 'test modules', 'cold', 'affected', 'full', 'mandatory checks'):
            self.assertIn(required, center)
        planner = prose(PLANNER)
        self.assertIn('prepare_api', planner)
        self.assertIn('same coordinator', planner)
        portable = prose(AUTONOMOUS[1])
        for required in ('[Docs Sync](../docs-sync/SKILL.md)', 'capability/prepare flow',
                         'actual consumer', 'reuse its result while inputs are unchanged',
                         'do not install updates or interrupt workers'):
            with self.subTest(portable_prepare=required):
                self.assertIn(required, portable)

    def test_execution_handoff_names_a_session_or_runner_without_starting_either(self):
        handoff = prose(HANDOFF)
        for required in ('A saved plan is not execution', 'give the user agent the first selection-ready task ID',
                         'Current session', 'Continuous runner', 'autowork start',
                         'Do not imply that a bare `/autowork` ran the plan',
                         'start a runner', 'same coordinator'):
            with self.subTest(shared=required):
                self.assertIn(required, handoff)
        for path, link in ((PLANNER, '../shared/PLAN-HANDOFF.md#execution-handoff'),
                           (INTERACTIVE[0], '../shared/PLAN-HANDOFF.md#execution-handoff'),
                           (AUTONOMOUS[1], '../../../skills/shared/PLAN-HANDOFF.md#execution-handoff'),
                           (INTERACTIVE[1], '../../../skills/shared/PLAN-HANDOFF.md#execution-handoff')):
            with self.subTest(path=path):
                text = prose(path)
                self.assertIn(link, text)
                self.assertIn('first selection-ready task', text)
                self.assertIn('Start no runner here', text)

    def test_planning_handoffs_limit_selection_claims_and_disclose_delivery(self):
        # Entrypoints must not turn a branch's selection result into runtime readiness.
        for path in (*INTERACTIVE, *AUTONOMOUS):
            text = prose(path)
            marker = ('## Save answers and finish the plan' if path == INTERACTIVE[0]
                      else '## Save the plan and hand off' if path == PLANNER
                      else 'Use the [single-pass handoff]')
            handoff = text.split(marker, 1)[1]
            with self.subTest(path=path):
                self.assertIn('autowork tasks why ID', handoff)
                self.assertIn('committed-store selection eligibility and position only', handoff)
                self.assertIn('not resource/ownership admission, capacity or dispatch', handoff)
                self.assertIn('branch-local commit', handoff)
                self.assertIn('actual canonical consumer', handoff)
                self.assertIn('whether that consumer includes the commit', handoff)
                self.assertIn('whether selection was checked there', handoff)
                self.assertIn('runtime and ownership unassessed unless observed', handoff)
                self.assertNotIn('shows whether each task can run', handoff)
                self.assertNotIn('actual readiness result', handoff)

    def test_interactive_runtime_failure_reuses_task_and_coordinator(self):
        # A known failed attempt is recovery evidence, not a new product interview.
        for path in INTERACTIVE:
            with self.subTest(path=path):
                text = prose(path)
                self.assertIn('When existing execution fails without new product uncertainty', text)
                self.assertIn('exact task ID, attempt evidence and failed operation', text)
                self.assertIn('same coordinator for supported recovery', text)
                self.assertIn('do not reopen the product interview or create duplicate tasks', text)
                self.assertIn('single-pass handoff', text)
                self.assertIn('builder check', text)

    def test_autonomous_blocker_routing_preserves_existing_contract_and_recovery(self):
        # Runtime trouble must not trigger blanket fix/skip or forced acceptance splitting.
        for path in AUTONOMOUS:
            text = prose(path)
            with self.subTest(path=path, rule='no blanket fix or split'):
                self.assertNotIn('return a **fix or skip** decision', text)
                self.assertNotIn('skip by splitting the blocked acceptance', text)
            for required in (
                    'classify the observed source and phase',
                    'Resolve engineering planning choices within delegated scope',
                    'existing task or candidate has a runtime, transport, gate or continuation failure',
                    'exact failed operation, task ID, attempt evidence and source-bound candidate evidence',
                    'same coordinator for supported recovery',
                    'no new interview, replacement task or acceptance split just to get moving',
                    'genuinely unavailable external, owner or physical-access inputs pending',
                    'only on affected tasks, with the exact missing input and resume condition',
                    'Split only when authorized scope and evidence justify decomposition',
                    'preserve existing task IDs, contracts, acceptance and history',
                    'never silently waive acceptance',
                    'single-pass handoff', 'builder check'):
                with self.subTest(path=path, rule=required):
                    self.assertIn(required, text)

    def test_ready_continuation_returns_without_executing_inside_planning(self):
        continuation = prose(SPECIAL_CASES).split('## Continuations and live gates', 1)[1]
        for rule in ("recheck that worker's terminal state",
                     'return the ready continuation to the existing authorized coordinator',
                     'execution outside standalone planning under existing scope and limits',
                     'otherwise keep one pending request',
                     'Do not ask again for settled authorization',
                     'explicit current no-execution limit',
                     'preserves existing pauses'):
            with self.subTest(rule=rule):
                self.assertIn(rule, continuation)
        self.assertNotIn('execute the continuation now', continuation)


if __name__ == '__main__':
    unittest.main()
