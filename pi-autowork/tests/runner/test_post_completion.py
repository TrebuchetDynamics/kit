"""Offline post-close Docs Sync events, proposal gates and coordinator handoff."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import maintainer, post_completion as sync
from pi_autowork.coordinator import Coordinator
from pi_autowork.engine.task_store import TaskStore
from support import store_fixture

ROOT = Path(__file__).resolve().parents[3]


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        store_fixture.write_todo(self.repo, '- [ ] A — Completed feature\n  Scope: Feature\n'
                                 '  Acceptance: Works\n  Checks: true\n  Touches: src/a.py\n'
                                 '- [ ] B — Pending feature\n  Scope: Pending\n'
                                 '  Acceptance: Still works\n  Checks: true\n  Touches: src/b.py\n')
        source = TaskStore.at(self.repo, 'HEAD')
        self.goal = next(iter(source.goals.values()))
        self.done = replace(source.tasks['A'], status='done', closure='coordinator_verified',
                            closure_timestamp=None, closure_evidence='tasks/evidence/A.toml', receipt_valid=True)
        self.open = source.tasks['B']
        self.before = self.store(self.done, self.open)
        self.rows = [dict(task='A', state='closed', attempt=1), dict(task='B', state='waiting')]

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture',
                               '-c', 'user.email=fixture@example.invalid', *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def store(self, *records):
        return SimpleNamespace(tasks={r.id: r for r in records}, goals={}, rev=self.git('rev-parse', 'HEAD'))

    def events(self, rows, source, canonical, receipt='proof'):
        return sync.triggers(rows, source, canonical, {'tasks/evidence/A.toml': receipt})

    def error(self, after, *, current=None, canonical=None, rows=None, paths=None, deleted=(), plans=()):
        return sync.proposal_error(self.before, after, current or self.before, canonical or self.before,
                                   self.rows if rows is None else rows,
                                   paths or [self.done.path], set(deleted), plans)

    def test_only_finalized_canonical_verified_completion_triggers(self):
        expected = self.events(self.rows, self.before, self.before)
        self.assertEqual([(t, k) for t, k, _ in expected], [('A', sync.KIND)])
        for state in ('reported', 'integrated', 'closing', 'held', 'running'):
            self.assertEqual(self.events([dict(self.rows[0], state=state)], self.before, self.before), [])
        self.assertEqual(self.events([dict(self.rows[0], worker_live=True)], self.before, self.before), [])
        self.assertEqual(self.events(self.rows, self.before, self.store(self.open)), [])
        self.assertEqual(self.events(self.rows, self.before,
                                    self.store(replace(self.done, record_revision='new'))), [])
        self.assertEqual(self.events(self.rows, self.store(replace(self.done, receipt_valid=False)), self.before), [])
        self.assertEqual(sync.triggers(self.rows, self.before, self.before, {}), [])

    def test_completion_receipt_survives_restart_and_cosmetic_edits(self):
        found = self.events(self.rows, self.before, self.before)
        self.assertEqual(maintainer.pending(self.repo, found), found)
        maintainer.remember(self.repo, trigger_key=maintainer.key(found), found=found, outcome='no change')
        self.assertEqual(maintainer.pending(self.repo, found), [])
        cosmetic = self.store(replace(self.done, title='Clarified', record_revision='new'), self.open)
        self.assertEqual(maintainer.pending(self.repo, self.events(self.rows, cosmetic, cosmetic)), [])
        # A repeated close can have identical task bytes and no timestamp; its receipt is new.
        self.assertTrue(maintainer.pending(self.repo, self.events(self.rows, self.before, self.before, 'new-proof')))
        self.assertEqual(maintainer.pending(self.repo, found), [])

    def test_new_receipt_must_land_even_when_record_bytes_are_identical(self):
        path = self.repo / 'tasks/evidence/A.toml'
        path.parent.mkdir(parents=True)
        path.write_text('first receipt')
        self.git('add', '.')
        self.git('commit', '-qm', 'first closure')
        canonical = self.git('rev-parse', 'HEAD')
        first = sync.landed_receipts(self.repo, canonical, canonical)
        self.assertTrue(sync.triggers(self.rows, self.before, self.before, first))
        path.write_text('second receipt')
        self.git('add', '.')
        self.git('commit', '-qm', 'new unlanded closure receipt')
        source = self.git('rev-parse', 'HEAD')
        unlanded = sync.landed_receipts(self.repo, source, canonical)
        self.assertEqual(sync.triggers(self.rows, self.before, self.before, unlanded), [])
        self.assertNotEqual(first, sync.landed_receipts(self.repo, source, source))

    def test_burst_coalesces_without_losing_later_completions(self):
        found = [(f'A-{i}', sync.KIND, 'attempt:contract:closed') for i in range(maintainer.LIMIT + 4)]
        self.assertEqual(maintainer.pending(self.repo, found), found)
        maintainer.remember(self.repo, trigger_key=maintainer.key(found), found=found, outcome='merged')
        extra = ('NEW', sync.KIND, 'attempt:contract:closed')
        self.assertEqual(maintainer.pending(self.repo, [*found, extra]), [extra])

    def test_failure_and_refusal_do_not_spin_or_reset_technical_budget(self):
        found = self.events(self.rows, self.before, self.before)
        identity = maintainer.recovery_key(found[0], {}, {}, set())
        self.assertEqual(identity, maintainer.item_key(found[0]))
        maintainer.remember(self.repo, trigger_key=maintainer.key(found), found=found,
                            outcome='technical failure', technical=True)
        self.assertEqual(maintainer.pending(self.repo, found, eligible=lambda _: False), [])
        maintainer.remember(self.repo, trigger_key=maintainer.key(found), found=found, outcome='refused: unsafe')
        self.assertEqual(maintainer.pending(self.repo, found), [])

    def test_safe_pruning_and_pending_clarification(self):
        self.open = replace(self.open, depends_on=('A',))
        self.before = self.store(self.done, self.open)
        after = self.store(replace(self.open, title='Connect feature', short='Connect feature',
                                   scope='Clarified pending scope', depends_on=()))
        paths = [self.done.path, self.open.path, 'tasks/evidence/A.toml', 'docs/tasks/A-report.md']
        self.assertIsNone(self.error(after, paths=paths, deleted=paths[:1] + paths[2:]))

    def test_unfinished_unqualified_or_unlanded_task_cannot_be_deleted(self):
        for record in (replace(self.done, status='open'), replace(self.done, receipt_valid=False),
                       replace(self.done, closure='manual', receipt_valid=False)):
            self.before = self.store(record, self.open)
            self.assertIn('qualified', self.error(self.store(self.open)))
        self.before = self.store(self.done, self.open)
        self.assertIn('landed', self.error(self.store(self.open), canonical=self.store(self.open)))

    def test_active_retained_or_newly_changed_records_are_protected(self):
        for state in ('running', 'dispatched', 'reported', 'held', 'interrupted', 'integrating', 'integrated', 'closing'):
            rows = [self.rows[0], dict(task='B', state=state)]
            changed = self.store(self.done, replace(self.open, title='Changed'))
            self.assertIn('owns', self.error(changed, rows=rows))
        self.assertIn('owns', self.error(self.store(self.open), rows=[dict(self.rows[0], worker_live=True)]))
        self.assertIn('changed', self.error(self.store(self.open),
                                           current=self.store(replace(self.done, record_revision='changed'), self.open)))

    def test_typed_acceptance_authority_priorities_and_goals_cannot_change(self):
        for changes in ({'acceptance': ('Less',)}, {'checks': ()}, {'rank': 0}, {'section': 'Next'},
                        {'status': 'done'}, {'resources': ('live',)}, {'verified_depends_on': ('A',)},
                        {'exclusions': ('Different',)}, {'owner_waiver': 'Invented'}):
            with self.subTest(changes=changes):
                self.assertIn('acceptance', self.error(self.store(self.done, replace(self.open, **changes))))
        after = self.store(self.done, self.open)
        after.goals['G'] = 'met'
        self.assertIn('goals', self.error(after))
        self.assertIn('add tasks', self.error(self.store(self.done, self.open, replace(self.open, id='C'))))

    def test_verification_dependencies_and_remaining_consumers_keep_records(self):
        self.open = replace(self.open, depends_on=('A',), verified_depends_on=('A',))
        self.before = self.store(self.done, self.open)
        self.assertIn('depends', self.error(self.store(self.open)))
        self.assertIn('dependencies', self.error(self.store(replace(self.open, depends_on=()))))
        self.assertIn('acceptance', self.error(self.store(replace(self.open, depends_on=(), verified_depends_on=()))))

    def test_only_exact_existing_nonactive_plans_are_allowed(self):
        self.open = replace(self.open, body='- Sources: docs/plans/feature.md#accepted\n')
        self.before = self.store(self.done, self.open)
        plans = sync.plan_paths(self.before, set())
        self.assertEqual(plans, ('docs/plans/feature.md',))
        self.assertEqual(sync.plan_paths(self.before, {'B'}), ())
        self.assertIsNone(self.error(self.before, paths=list(plans), plans=plans))
        self.assertIn('unauthorized', self.error(self.before, paths=list(plans), plans=plans, deleted=plans))
        self.assertIn('unauthorized', self.error(self.before, paths=['docs/plans/new.md'], plans=plans))
        self.assertIn('unauthorized', self.error(self.before, paths=list(plans), plans=plans,
                                                rows=[self.rows[0], dict(task='B', state='running')]))

    def test_receipts_may_only_be_deleted_with_their_eligible_record(self):
        for path in ('src/code.py', 'tasks/evidence/A.toml', 'tasks/evidence/B.toml', 'docs/tasks/other.md'):
            self.assertIn('unauthorized', self.error(self.before, paths=[path]))
        self.assertIn('unauthorized', self.error(self.store(self.open), paths=['tasks/evidence/A.toml']))
        self.assertIsNone(self.error(self.store(self.open), paths=['tasks/evidence/A.toml'],
                                     deleted=['tasks/evidence/A.toml']))

    def test_still_referenced_evidence_is_retained_unless_pinned_to_reachable_git(self):
        old = self.git('rev-parse', 'HEAD')
        path = self.done.path
        (self.repo / path).unlink()
        readme = self.repo / 'README.md'
        readme.write_text('Required evidence: ' + path)
        self.git('add', '.')
        self.git('commit', '-qm', 'candidate')
        self.assertIn('still references', sync.reference_error(self.repo, {path}, old))
        readme.write_text('Required evidence: git show ' + old + ':' + path)
        self.git('add', '.')
        self.git('commit', '-qm', 'immutable evidence')
        self.assertIsNone(sync.reference_error(self.repo, {path}, old))
        readme.write_text('Required evidence: ' + 'f' * 40 + ':' + path)
        self.git('add', '.')
        self.git('commit', '-qm', 'invalid evidence')
        self.assertIn('unavailable', sync.reference_error(self.repo, {path}, old))

    def test_retained_waiting_slots_and_sequential_claims_stay_frozen(self):
        proposed = self.store(self.done, replace(self.open, scope='Changed'))
        for fields in ({'admitted_contract_hash': 'retained'}, {'worktree': '/retained'},
                       {'commit': 'candidate'}, {'root_kind': 'claim'}):
            self.assertIn('owns', self.error(proposed, rows=[dict(task='B', state='waiting', **fields)]))
        held = replace(self.open, body='- Held by: reviewer\n')
        self.before = self.store(self.done, held)
        self.assertIn('owns', self.error(self.store(self.done, replace(held, body=''))))

    def test_protected_body_notes_cannot_be_invented_rewritten_or_removed(self):
        for label in ('Owner decision', 'Owner waiver', 'Owner qualification', 'Evidence', 'Verified', 'Live authorization'):
            with self.subTest(label=label):
                protected = f'- {label}: original\n'
                self.before = self.store(self.done, self.open)
                self.assertIn('notes', self.error(self.store(self.done, replace(self.open, body=protected))))
                original = replace(self.open, body=protected)
                self.before = self.store(self.done, original)
                for body in ('', protected.replace('original', 'invented')):
                    self.assertIn('notes', self.error(self.store(self.done, replace(original, body=body))))
        self.before = self.store(self.done, self.open)
        self.assertIsNone(self.error(self.store(self.done, replace(self.open, body=self.open.body + '\n- Description: Clearer.\n'))))

    def test_new_current_consumers_prevent_deleting_their_dependencies(self):
        for dependencies in ({'depends_on': ('A',)}, {'verified_depends_on': ('A',)}):
            current = self.store(self.done, self.open, replace(self.open, id='C', **dependencies))
            self.assertIn('depends', self.error(self.store(self.open), current=current))
        current = self.store(self.done, replace(self.open, depends_on=('A',)))
        self.assertIn('depends', self.error(self.store(self.open), current=current))

    def test_shared_plan_in_active_structured_contract_is_frozen(self):
        plan = 'docs/plans/shared.md'
        pending = replace(self.open, body='- Sources: ' + plan)
        for fields in ({'scope': plan}, {'acceptance': (plan,)}, {'checks': (plan,)}, {'touches': (plan,)}):
            active = replace(self.open, id='C', **fields)
            self.assertEqual(sync.plan_paths(self.store(pending, active), {'C'}), ())

    def test_active_directory_glob_or_unknown_scope_protects_plans_and_reports(self):
        plan = 'docs/plans/shared.md'
        pending = replace(self.open, body='- Sources: ' + plan)
        for touches in (('docs/plans/',), ('docs/**/*.md',), ()):
            active = replace(self.open, id='C', touches=touches)
            source = self.store(pending, active)
            self.assertEqual(sync.plan_paths(source, {'C'}), ())
        for touches in (('docs/tasks/',), ('docs/**/*.md',), ()):
            active = replace(self.open, id='C', touches=touches)
            self.before = self.store(self.done, self.open, active)
            self.assertIn('scope', self.error(self.store(self.open, active),
                rows=[dict(task='C', state='running')], paths=['docs/tasks/A-report.md'],
                deleted=['docs/tasks/A-report.md']))

    def test_shared_plan_in_active_goal_body_is_frozen(self):
        plan = 'docs/plans/shared.md'
        pending = replace(self.open, body='- Sources: ' + plan)
        source = self.store(pending, replace(self.open, id='C'))
        source.goals[self.goal.id] = replace(self.goal, body='- Sources: ../../docs/plans/shared.md')
        self.assertEqual(sync.plan_paths(source, {'C'}), ())

    def test_relative_and_normalized_references_preserve_dedicated_reports(self):
        report = 'docs/tasks/A-report.md'
        path = self.repo / report
        path.parent.mkdir(parents=True)
        path.write_text('Evidence')
        consumer = self.repo / 'docs/plans/current.md'
        consumer.parent.mkdir(parents=True)
        consumer.write_text('[Evidence](../tasks/A-report.md#proof)')
        self.git('add', '.')
        self.git('commit', '-qm', 'relative report consumer')
        old = self.git('rev-parse', 'HEAD')
        path.unlink()
        self.git('add', '.')
        self.git('commit', '-qm', 'unsafe proposal')
        self.assertIn('still references', sync.reference_error(self.repo, {report}, old))
        for link in ('../tasks/A%2Dreport.md', '../tasks/%41%2Dreport.%6Dd'):
            consumer.write_text('[Evidence](' + link + '#proof)')
            self.git('add', '.')
            self.git('commit', '-qm', 'encoded relative consumer')
            self.assertIn('still references', sync.reference_error(self.repo, {report}, old))
        self.assertIn('docs/plans/shared.md', sync.referenced_paths(
            '[Plan](../../docs/plans/sub/../shared.md)', 'tasks/items/B.md'))

    def test_multiple_immutable_consumers_keep_the_original_scan_revision(self):
        old = self.git('rev-parse', 'HEAD')
        path = self.done.path
        (self.repo / path).unlink()
        for name in ('consumer1.md', 'consumer2.md'):
            (self.repo / name).write_text('Evidence: git show ' + old + ':' + path)
        self.git('add', '.')
        self.git('commit', '-qm', 'pin two consumers')
        self.assertIsNone(sync.reference_error(self.repo, {path}, old))

    def test_current_reference_scan_excludes_only_paths_the_proposal_replaces(self):
        old = self.git('rev-parse', 'HEAD')
        path = self.done.path
        (self.repo / 'consumer.md').write_text('Needs ' + path)
        self.git('add', '.')
        self.git('commit', '-qm', 'concurrent new consumer')
        self.assertIn('still references', sync.reference_error(self.repo, {path}, old, exclude=[path]))
        self.assertIsNone(sync.reference_error(self.repo, {path}, old, exclude=[path, 'consumer.md']))

    def test_prompt_routes_docs_sync_and_keeps_non_completion_proof_separate(self):
        text = sync.prompt('/repo', 'autowork tasks', [('A', sync.KIND, 'proof')], {'B'}, (), 'a' * 40)
        for phrase in ('/skill:docs-sync', 'names', 'scope descriptions', 'plans', 'delete',
                       'verified_depends_on', 'Protected IDs', 'Git is the archive',
                       'No other document/product code', 'Do not manufacture edits'):
            self.assertIn(phrase, text)

    def owner(self):
        owner = Coordinator.__new__(Coordinator)
        owner.state, owner.repo, owner.integ, owner.base = self.repo, str(self.repo), str(self.repo), 'HEAD'
        owner.stop, owner.maintainer_job = False, None
        owner.integ_branch = 'session'
        owner.toolset, owner.tasks_cli, owner.verify_timeout = ROOT, 'autowork tasks', 10
        owner.in_flight = lambda: True  # Other workers do not prevent a safe isolated docs pass.
        owner.session_busy = owner.reexec_due = lambda: False
        owner.validate_ledger = lambda: []
        owner.status = lambda: dict(outcome='PARALLEL_STATUS', tasks=self.rows,
                                    task_source={'revision': self.git('rev-parse', 'HEAD'), 'workspace': str(self.repo),
                                                 'repository_identity': str(self.repo / '.git')})
        owner.scratch_checkout, owner.drop_scratch = Mock(return_value=str(self.repo)), Mock()
        owner.start_maintainer, owner.remember_job_cleanup = Mock(), Mock()
        return owner

    def test_real_maintain_path_reserves_before_async_submission_and_respects_recovery(self):
        owner = self.owner()
        with (patch('pi_autowork.engine.task_queue.store', return_value=self.before),
              patch.object(sync, 'landed_receipts', return_value={'tasks/evidence/A.toml': 'proof'})):
            self.assertFalse(owner.maintain(completion=True))
            owner.start_maintainer.assert_called_once()
            job, message, _ = owner.start_maintainer.call_args.args
            self.assertTrue(job['completion'])
            self.assertIn('/skill:docs-sync', message)
            recovery = json.loads((self.repo / 'maintainer-recovery.json').read_text())
            self.assertEqual(recovery[next(iter(job['recovery']))]['phase'], 'in_flight')
            # A process crash before result collection cannot buy another provider call.
            owner.maintain(completion=True)
            owner.start_maintainer.assert_called_once()

    def test_no_change_collection_yields_a_cycle_to_previously_blocked_planning(self):
        owner = self.owner()
        output = self.repo / '.git' / 'docs-result.json'
        output.write_text(json.dumps({'ok': True}))
        owner.maintainer_job = dict(completion=True, scratch=str(self.repo), out=str(output),
                                    proc=Mock(returncode=0, poll=lambda: 0))
        owner._job_results = {str(self.repo): {'cleanup_complete': True}}
        owner._scratch_cleanup = {str(self.repo): True}
        owner.maintainer_result = Mock(return_value=False)  # valid no-change or bounded refusal
        owner.settled = False
        owner.finish_maintainer()
        self.assertTrue(owner.settled)
        self.assertIsNone(owner.maintainer_job)
        self.assertFalse(output.exists())

    def test_maintenance_launch_defers_on_unknown_or_stale_activity_and_reload(self):
        for gate in ('unknown', 'stale', 'reload', 'busy'):
            owner = self.owner()
            if gate == 'unknown':
                owner.status = lambda: {}
            elif gate == 'stale':
                owner.status = lambda: dict(outcome='PARALLEL_STATUS', tasks=self.rows, task_source={'revision': 'old'})
            elif gate == 'reload':
                owner.reexec_due = lambda: True
            else:
                owner.session_busy = lambda: True
            self.assertFalse(owner.maintain(completion=True))
            owner.start_maintainer.assert_not_called()

    def test_finite_final_landing_is_followed_by_docs_sync_before_exit(self):
        for outcome in ('WAITING', 'DRAINING', 'IDLE'):
            owner = self.owner()
            owner.settle = owner.handle_requests = owner.health_update = Mock()
            owner.settled, owner.draining, owner.mode = False, True, 'once'
            owner.in_flight = lambda: False
            owner.interval, owner.once_task = 5, 'A'
            owner.pause = Mock()
            owner.finish = Mock(side_effect=AssertionError('final landing must precede docs collection'))
            landed = []
            owner.merge_main = lambda: landed.append(True)
            def start(**kwargs):
                if landed:
                    owner.maintainer_job = {'active': True}
            owner.maintain = Mock(side_effect=start)
            owner.finish_cycle(outcome)
            self.assertEqual(owner.maintain.call_count, 2)
            owner.pause.assert_called_once()

    def test_collection_rechecks_source_identity_and_ownership(self):
        owner = self.owner()
        old = self.git('rev-parse', 'HEAD')
        job = dict(base=old, scratch=str(self.repo), completion_store=self.before, completion_plans=())
        proposed = self.store(self.done, replace(self.open, title='Clear pending name'))
        with patch('pi_autowork.engine.task_queue.store', return_value=self.before):
            self.assertIsNone(owner.completion_proposal_error(job, proposed, [self.open.path], old))
            self.rows[1]['state'] = 'running'
            self.assertIn('owns', owner.completion_proposal_error(job, proposed, [self.open.path], old))
            self.rows[1]['state'] = 'waiting'
            with patch('pi_autowork.task_commands.in_flight', return_value=({'B'}, ['a live sequential execution lease'])):
                self.assertIn('ownership', owner.completion_proposal_error(job, proposed, [self.open.path], old))
            original = owner.status()
            for source in ({'revision': 'old'}, {'workspace': '/foreign'}, {'repository_identity': '/foreign'}):
                owner.status = lambda: dict(original, task_source={**original['task_source'], **source})
                self.assertIn('stale', owner.completion_proposal_error(job, proposed, [self.open.path], old))

    def test_common_finish_path_schedules_before_once_drain_or_wait_return(self):
        for mode, outcome in (('continuous', 'WAITING'), ('once', 'DRAINING'), ('until-empty', 'IDLE')):
            owner = self.owner()
            owner.settle = owner.handle_requests = owner.health_update = Mock()
            owner.settled, owner.draining, owner.mode = False, True, mode
            owner.in_flight = lambda: False
            owner.interval = 5
            owner.pause = Mock()
            owner.finish = Mock(side_effect=AssertionError('must collect docs before finite exit'))
            def start(**kwargs):
                self.assertEqual(kwargs, {'completion': True})
                owner.maintainer_job = {'active': True}
            owner.maintain = Mock(side_effect=start)
            owner.finish_cycle(outcome)
            owner.maintain.assert_called_once_with(completion=True)
            owner.pause.assert_called_once()


if __name__ == '__main__':
    unittest.main()
