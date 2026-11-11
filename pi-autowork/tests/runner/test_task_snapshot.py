"""Committed inventory and compatible runtime evidence at the public capture seam."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine'))
from support import store_fixture
import task_queue
from task_store import TaskStore, StoreError, edit
from pi_autowork import command, fleet_view, task_snapshot


class TaskSnapshotTests(unittest.TestCase):
    def test_committed_deferred_owner_live_end_to_end(self):
        from pi_autowork.engine import parallel_status
        from pi_autowork import health, questions
        store_fixture.write_todo(self.repo, '## Now\n- [ ] A — Owner live action\n- [ ] B — Dependent\n')
        a = self.repo / 'tasks/items/A.md'
        b = self.repo / 'tasks/items/B.md'
        original = edit(a.read_text(), dict(ownership='owner', live='denied'))
        b.write_text(edit(b.read_text(), dict(depends_on=['A'])))
        for note, deferred in (('2026-11-01: deferred: waiting', True),
                               ('2026-11-01: deferred: waiting\n- Owner decision: 2026-11-02: proceed', False),
                               ('', False)):
            with self.subTest(note=note):
                a.write_text(original + ('\n- Owner decision: ' + note + '\n' if note else ''))
                subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T',
                                '-c', 'user.email=t@example.invalid', 'commit', '-qam', 'decision'], check=True)
                value = parallel_status.snapshot(self.repo)
                snap = task_snapshot.capture(self.repo, engine_observation=value, generation=1)
                rows = {row.task: row for row in snap.rows}
                self.assertEqual(rows['A'].state == 'Deferred', deferred)
                self.assertEqual(task_queue.store(self.repo).tasks['B'].status, 'open')
                self.assertEqual(task_queue.store(self.repo).tasks['A'].ownership, 'owner')
                self.assertEqual(task_queue.store(self.repo).tasks['A'].live, 'denied')
                if deferred:
                    self.assertFalse(rows['A'].question)
                    self.assertEqual(rows['A'].bucket, 'Deferred')
                    self.assertEqual(snap.counts, (0, 0, 2, 0, 0, 2))
                    self.assertEqual({row.task for row in fleet_view.task_view(snap.rows, 'waiting')}, {'A', 'B'})
                    self.assertEqual(questions.build(value, self.repo), [])
                    (self.repo / 'state').mkdir(exist_ok=True)
                    health.update(self.repo / 'state', value)
                self.assertEqual(health.classify(dict(value, active_workers=1)), 'working')

    def test_daily_provider_quota_is_explained_without_changing_task_authority(self):
        from pi_autowork import task_status
        store = task_queue.store(self.repo)
        record = store.tasks['A']
        observation = dict(state='held', cause='empty', reason=(
            'worker runtime failed (provider_failure): 429: {"message":"Rate limit exceeded: '
            'free-models-per-day", "private":"do-not-display"}'))
        row = task_snapshot.task_row(record, store, observation=observation)
        self.assertEqual(row.bucket, 'Blocker')
        self.assertIn('quota exhausted', row.why)
        self.assertNotIn('do-not-display', row.why)
        self.assertFalse(row.question)
        self.assertEqual(record.status, 'open')
        self.assertEqual(task_status.provider_limit_notice('429 server busy'), '')
        self.assertEqual(task_status.provider_limit_notice('free-models-per-day without an HTTP code'), '')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        store_fixture.write_todo(self.repo, '## Now\n- [ ] A — Alpha\n- [ ] B — Beta\n'
                                '## Next\n- [ ] C — Gamma\n## Needs decision\n- [ ] D — Decide\n')

    def observation(self, **updates):
        store = task_queue.store(self.repo)
        return dict(task_source=dict(workspace=str(self.repo), repository_identity=str(self.repo / '.git'),
                                     revision=store.rev, observed_at=time.time()),
                    tasks=[dict(task=t.id, state='waiting', contract_hash=t.contract_hash,
                                admitted_contract_hash=None) for t in store.tasks.values()], **updates)

    def test_owner_action_is_not_awaiting_dispatch(self):
        store_fixture.write_todo(self.repo, '## Now\n- [ ] A — Supply signed input\n'
                                '- [ ] B — Publish accepted result\n- [ ] C — Reconcile result\n'
                                '- [ ] E — Ordinary worker\n## Needs decision\n- [ ] D — Decide\n')
        for task, ownership in (('A', 'owner'), ('B', 'owner'), ('C', 'coordinator'),
                                ('D', 'owner'), ('E', 'worker')):
            path = self.repo / f'tasks/items/{task}.md'
            path.write_text(edit(path.read_text(), dict(ownership=ownership, live='denied',
                scope='Perform the recorded action.', acceptance=['Result recorded'],
                checks=['Check recorded result'], touches=['result.txt']))
                + ('\n- Owner decision: 2026-11-07: yes\n' if task == 'B' else ''))
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'typed ownership'], check=True)
        original = task_queue.store(self.repo)
        question = fleet_view.Question('B', 'input', 0, 'Perform the recorded action.',
                                      'Approval already saved.', 'owner_action')
        for evidence in ('absent', 'waiting', 'stale', 'mismatch', 'question'):
            with self.subTest(evidence=evidence):
                obs = self.observation()
                for row in obs['tasks']:
                    row['reason'] = 'ready; awaiting dispatch'
                if evidence == 'absent':
                    obs = None
                elif evidence == 'stale':
                    obs['task_source']['observed_at'] = 1
                elif evidence == 'mismatch':
                    obs['task_source']['repository_identity'] = '/another/.git'
                elif evidence == 'question':
                    obs['questions'] = [question]
                snap = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
                rows = {row.task: row for row in snap.rows}
                self.assertEqual(set(rows), {'A', 'B', 'C', 'D', 'E'})
                self.assertEqual(snap.counts, (0, 0, 2, 2, 1, 5))
                for task in ('A', 'B'):
                    row = rows[task]
                    self.assertEqual((row.bucket, row.state), ('Blocker', 'Blocker'))
                    self.assertIn('owner action', row.why)
                    self.assertNotIn('dispatch', row.why)
                    self.assertEqual(row.question, evidence == 'question' and task == 'B')
                    display = task_snapshot.task_display(original.tasks[task], original, row=row)
                    self.assertEqual((display['bucket'], display['why']), (row.bucket, row.why))
                    canonical = task_snapshot.task_display(original.tasks[task], original)
                    self.assertEqual((canonical['bucket'], canonical['why']), ('Blocker', 'owner action required'))
                self.assertEqual((rows['C'].bucket, rows['C'].why), ('Waiting', 'awaiting coordinator action'))
                self.assertEqual((rows['E'].bucket, rows['E'].why), ('Waiting', 'ready; awaiting dispatch'))
                self.assertEqual((rows['D'].bucket, rows['D'].why), ('Decision', 'in Needs decision'))
                if evidence == 'question':
                    self.assertIn('; you: ' + question.needs, rows['B'].why)
        obs = self.observation()
        for row in obs['tasks']:
            if row['task'] in ('A', 'B'):
                row.update(state='running' if row['task'] == 'A' else 'integrated',
                           admitted_contract_hash=row['contract_hash'])
        snap = task_snapshot.capture(self.repo, engine_observation=obs, generation=2)
        self.assertEqual(snap.counts, (1, 1, 2, 0, 1, 5), 'compatible in-flight evidence retains precedence')
        self.assertEqual(task_queue.store(self.repo).tasks, original.tasks, 'display changes no gates or closure')

    def test_a_saved_plan_refusal_is_agent_repair_not_ready_or_owner_authority(self):
        path = self.repo / 'tasks/items/A.md'
        path.write_text(edit(path.read_text(), {'kind': 'plan'}))
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'accepted plan'], check=True)
        original = task_queue.store(self.repo).tasks['A']
        obs = self.observation(maintainer={'items': {'task:A': dict(
            digest=original.record_revision, outcome='refused: it changed more than planning files')}})
        obs['tasks'][0]['reason'] = 'ready for planning'
        result = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
        row = next(row for row in result.rows if row.task == 'A')
        self.assertEqual(row.bucket, 'Blocker')
        self.assertEqual(row.state, 'Blocker · Planning repair')
        self.assertIn('changed more than planning files', row.why)
        self.assertFalse(row.question)
        self.assertEqual(result.counts, (0, 0, 2, 1, 1, 4))
        self.assertEqual(task_queue.store(self.repo).tasks['A'], original, 'display grants no authority')
        obs['maintainer']['items']['task:A']['digest'] = 'old task revision'
        fresh = task_snapshot.capture(self.repo, engine_observation=obs, generation=2)
        self.assertEqual(next(row for row in fresh.rows if row.task == 'A').why, 'ready for planning')

    def test_membership_is_one_pinned_commit_not_pending_or_session_union(self):
        first = task_snapshot.capture(self.repo, engine_observation=None, generation=1)
        self.assertEqual(first.counts, (0, 0, 3, 0, 1, 4))
        self.assertEqual([r.task for r in first.rows], ['A', 'B', 'C', 'D'])
        self.assertTrue(all(r.why == 'ready; awaiting dispatch' for r in first.rows[:3]))
        path = self.repo / 'tasks/items/A.md'
        path.write_text(edit(path.read_text(), {'section': 'Needs decision'}))
        pending = task_snapshot.capture(self.repo, engine_observation=None, generation=2)
        self.assertEqual(pending.counts, first.counts)
        self.assertIn('tasks/items/A.md', pending.pending_paths)
        self.assertTrue(pending.rows[0].pending)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'decision'], check=True)
        changed = task_snapshot.capture(self.repo, engine_observation=None, generation=3)
        self.assertEqual(changed.counts, (0, 0, 2, 0, 2, 4))
        self.assertNotEqual(changed.revision, first.revision)
        store_fixture.write_todo(self.repo, '## Now\n- [ ] NEW — New committed task\n')
        final = task_snapshot.capture(self.repo, engine_observation=None, generation=4)
        self.assertEqual([r.task for r in final.rows], ['NEW'])
        self.assertEqual(final.counts, (0, 0, 1, 0, 0, 1))
        self.assertEqual(first.generation, 1)

    def test_display_is_words_only_and_store_rows_do_not_claim_runtime(self):
        store = task_queue.store(self.repo)
        row = task_snapshot.task_display(store.tasks['A'], store)
        self.assertEqual(set(row), {'state', 'bucket', 'why', 'question', 'pending', 'blocker', 'closure', 'record_revision'})
        self.assertEqual((row['state'], row['bucket']), ('Waiting', 'Waiting'))
        self.assertEqual(row['why'], 'ready; awaiting dispatch')
        self.assertFalse(row['question'])
        self.assertIsNone(row['closure'])
        decision = task_snapshot.task_display(store.tasks['D'], store)
        self.assertEqual((decision['state'], decision['bucket']), ('Waiting · Needs decision', 'Decision'))
        self.assertEqual(decision['why'], 'in Needs decision')
        task_row = task_snapshot.TaskRow('A', 'Alpha', 'Now', 'Waiting', 'waiting', 'ready', True)
        self.assertEqual(task_snapshot.task_display(store.tasks['A'], store, row=task_row)['question'], True)

    def test_only_compatible_current_observations_can_classify_inventory(self):
        path = self.repo / 'tasks/items/C.md'
        path.write_text(edit(path.read_text(), {'depends_on': ['D']}))
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'dependency'], check=True)
        obs = self.observation()
        by_id = {r['task']: r for r in obs['tasks']}
        by_id['A'].update(state='running', admitted_contract_hash=by_id['A']['contract_hash'], attempt=2)
        by_id['B'].update(state='integrated', admitted_contract_hash=by_id['B']['contract_hash'], attempt=1)
        by_id['C'].update(state='waiting', reason='dependency: D')
        obs['stopped_groups'] = [dict(label='D (outside Now/Next)', tasks=['C'], count=99)]
        obs['tasks'].append(dict(task='ORPHAN', state='integrated', contract_hash='old'))
        obs['task_source']['revision'] = 'session-revision'
        good = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
        self.assertEqual(good.counts, (1, 1, 0, 1, 1, 4))
        self.assertIn('session', ' '.join(good.annotations))
        self.assertIn('ORPHAN', ' '.join(good.annotations))
        runner = fleet_view.Runner('fixture', repo=str(self.repo), state='working', snapshot=good)
        display = command.runner_json(runner)['display']
        for row in good.rows:
            task = display['tasks'][row.task]
            self.assertEqual((task['state'], task['bucket'], task['why'], task['question'], task['pending']),
                             (row.state, row.bucket, row.why, row.question, row.pending))
        self.assertEqual(display['needs'], fleet_view.needs(runner))
        self.assertEqual(display['blockers'], fleet_view.blockers(runner))
        # A raw slot/log may be stale even when today's observed current hash matches.
        for change in ('admitted', 'source', 'legacy', 'age', 'duplicate', 'slot'):
            with self.subTest(change=change):
                bad = json.loads(json.dumps(obs))
                if change == 'admitted':
                    for row in bad['tasks'][:2]:
                        row['admitted_contract_hash'] = 'old-contract'
                elif change == 'source':
                    bad['task_source']['repository_identity'] = '/another/.git'
                elif change == 'legacy':
                    for row in bad['tasks']:
                        row.pop('contract_hash', None)
                elif change == 'age':
                    bad['task_source']['observed_at'] = 1
                elif change == 'duplicate':
                    bad['tasks'] += bad['tasks'][:2]
                else:
                    bad['tasks'][0]['state'] = 'waiting'
                    bad['tasks'][1]['state'] = 'waiting'
                    bad['lanes'] = [fleet_view.Lane('A', 'implementing'), fleet_view.Lane('B', 'integrated')]
                result = task_snapshot.capture(self.repo, engine_observation=bad, generation=2)
                self.assertEqual(result.counts[:2], (0, 0))
                self.assertEqual(sum(result.counts[:5]), 4)

    def test_freshness_bounds_historical_noise_without_hiding_current_mismatches(self):
        obs = self.observation()
        obs['tasks'].extend(dict(task=f'RETIRED-{i}', state='closed') for i in range(100))
        obs['tasks'].append(dict(task='UNKNOWN-ACTIVE', state='running'))
        snap = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
        runner = fleet_view.Runner('fixture', repo=str(self.repo), snapshot=snap)
        summary = fleet_view.freshness(runner)
        self.assertLess(len(summary), 1500, 'history must not displace the task rows')
        self.assertIn('UNKNOWN-ACTIVE', summary, 'current mismatches take priority over history')
        self.assertIn('100 unmatched closed', summary)
        self.assertEqual(len(snap.annotations), 101, 'full source diagnostics remain available')
        self.assertEqual(snap.counts, (0, 0, 3, 0, 1, 4), 'annotations cannot change membership')

    def test_done_task_observations_are_history_not_inventory_annotations(self):
        store_fixture.write_todo(self.repo, '## Now\n- [ ] A — Alpha\n- [ ] OLD — Old closed task\n')
        path = self.repo / 'tasks/items/OLD.md'
        path.write_text(edit(path.read_text(), {'status': 'done'}))
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'done'], check=True)
        obs = self.observation()
        self.assertIn('OLD', {row['task'] for row in obs['tasks']})
        snapshot = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
        self.assertNotIn('OLD', ' '.join(snapshot.annotations))
        self.assertEqual([row.task for row in snapshot.closed_rows], ['OLD'])
        self.assertEqual(snapshot.counts[-1], 1)

    def test_conflict_recovery_is_active_only_with_current_compatible_evidence(self):
        obs = self.observation()
        row = next(r for r in obs['tasks'] if r['task'] == 'A')
        row.update(state='held', cause='conflict', admitted_contract_hash=row['contract_hash'],
                   recovery='resolving_conflict')
        snap = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
        self.assertEqual(snap.rows[0].state, 'Active · Resolving conflict')
        self.assertEqual(snap.rows[0].kind, 'working')
        self.assertIn('verification still required', snap.rows[0].why)
        self.assertEqual(snap.counts, (1, 0, 2, 0, 1, 4))
        runner = fleet_view.Runner('fixture', repo=str(self.repo), snapshot=snap)
        self.assertEqual(command.runner_json(runner)['display']['tasks']['A']['state'], snap.rows[0].state)
        for change in ('stale', 'contract', 'finished', 'other_hold', 'reported', 'decision'):
            with self.subTest(change=change):
                bad = json.loads(json.dumps(obs))
                candidate = bad['tasks'][0]
                if change == 'stale':
                    bad['task_source']['observed_at'] = 1
                elif change == 'contract':
                    candidate['admitted_contract_hash'] = 'old'
                elif change == 'finished':
                    candidate.pop('recovery')
                elif change == 'other_hold':
                    candidate['cause'] = 'validation'
                elif change == 'reported':
                    candidate['state'] = 'reported'
                else:
                    candidate['task'] = 'D'
                    bad['tasks'] = [candidate]
                    candidate['contract_hash'] = candidate['admitted_contract_hash'] = task_queue.store(self.repo).tasks['D'].contract_hash
                result = task_snapshot.capture(self.repo, engine_observation=bad, generation=2)
                self.assertEqual(result.counts[:2], (0, 0))
                if change in ('finished', 'other_hold'):
                    self.assertEqual(result.rows[0].bucket, 'Blocker')
                elif change == 'reported':
                    self.assertEqual(result.rows[0].state, 'Waiting · Implemented')

    def test_stale_log_phase_cannot_upgrade_a_current_reported_attempt(self):
        obs = self.observation()
        row = next(r for r in obs['tasks'] if r['task'] == 'A')
        row.update(state='reported', admitted_contract_hash=row['contract_hash'], attempt=2, started_at=time.time() - 60)
        slots = self.repo / '.git/autowork-execution/slots'
        slots.mkdir(parents=True)
        (slots / 'A.json').write_text(json.dumps(dict(task_id='A', state='reported', attempt=2, started_at=row['started_at'])))
        data = self.repo / '.git/autowork-execution/slot-data/A/attempt-2'
        data.mkdir(parents=True)
        (data / 'contract.json').write_text(json.dumps(dict(contract_hash=row['contract_hash'])))
        state = self.repo / 'runtime'
        state.mkdir()
        (state / 'runner.log').write_text('2020-01-01T00:00:00+00:00 A: landing\n')
        obs['lanes'] = fleet_view.lanes(fleet_view.Runner('repo', repo=str(self.repo), state_dir=str(state)))
        snapshot = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
        self.assertEqual(snapshot.counts, (0, 0, 3, 0, 1, 4))
        self.assertEqual(snapshot.rows[0].state, 'Waiting · Implemented')

    def test_rejected_execution_roots_do_not_stop_compatible_inventory(self):
        for kind in ('incompatible', 'duplicate', 'orphan', 'stale_state'):
            with self.subTest(kind=kind):
                obs = self.observation()
                root = next(r for r in obs['tasks'] if r['task'] == 'B')
                root.update(state='held', cause='blocker', admitted_contract_hash='old')
                if kind == 'duplicate':
                    root['admitted_contract_hash'] = root['contract_hash']
                    obs['tasks'].append(dict(root))
                if kind == 'orphan':
                    root['task'] = 'ORPHAN'
                if kind == 'stale_state':
                    root.update(state='waiting', admitted_contract_hash=None)
                obs['roots'] = [dict(id=root['task'], kind='held', cause='blocker', tasks=['A'], blocks=1)]
                obs['stopped_groups'] = [dict(label='old blockage', tasks=['A'], count=1)]
                snap = task_snapshot.capture(self.repo, engine_observation=obs, generation=1)
                self.assertEqual((snap.rows[0].bucket, snap.rows[0].why), ('Waiting', 'ready; awaiting dispatch'))

    def test_no_health_and_legacy_inventory_propagate_committed_stopping_dependencies(self):
        for task, dependency in (('A', 'B'), ('B', 'D')):
            path = self.repo / f'tasks/items/{task}.md'
            path.write_text(edit(path.read_text(), {'depends_on': [dependency]}))
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'dependencies'], check=True)
        for observation in (None, {'tasks': [['A', 'waiting', '', '']]},
                            dict(self.observation(), task_source={'observed_at': 1})):
            with self.subTest(observation=observation):
                snap = task_snapshot.capture(self.repo, engine_observation=observation, generation=1)
                self.assertEqual(snap.counts, (0, 0, 1, 2, 1, 4))
                self.assertIn('D', snap.rows[0].why)

    def test_runner_json_retains_raw_fields_when_selection_notes_are_invalid(self):
        path = self.repo / 'tasks/items/A.md'
        path.write_text(edit(path.read_text(), dict(scope='Fixture task', acceptance=['Fixture acceptance'],
                                                   checks=['fixture check'], touches=['fixture.py']))
                        + '\n- Held by: reviewer; until 2026-02-30\n')
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                        'commit', '-qam', 'invalid hold date'], check=True)
        snapshot = task_snapshot.capture(self.repo, engine_observation=None, generation=1)
        runner = fleet_view.Runner('fixture', repo=str(self.repo), state='idle', blocker='raw reason',
                                   snapshot=snapshot)
        record = command.runner_json(runner)
        self.assertEqual((record['name'], record['state'], record['blocker']), ('fixture', 'idle', 'raw reason'))
        self.assertEqual(record['display']['tasks']['A']['state'], snapshot.rows[0].state)
        self.assertIn('Selection unavailable:', record['display']['tasks']['A']['blocker'])
        self.assertIn('Needs unavailable:', record['display']['needs'])

    def test_presentation_is_output_only_for_execution_modules(self):
        import ast
        package = Path(task_snapshot.__file__).parent
        paths = [*package.joinpath('engine').rglob('*.py'),
                 *(package / name for name in ('coordinator.py', 'worker.py', 'landing.py',
                                               'optimistic.py', 'post_merge_barrier.py'))]
        functions = {'task_display', 'runner_display', 'closure_display', 'task_row'}
        modules = {'task_snapshot', 'task_status'}
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((functions | modules).intersection(a.name for a in node.names), path)
                    self.assertNotIn((node.module or '').split('.')[-1], modules, path)
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(a.name.split('.')[-1] in modules for a in node.names), path)
                elif isinstance(node, ast.Call):
                    self.assertNotIn(getattr(node.func, 'attr', None), functions, path)

    def test_unavailable_is_not_empty_and_pending_failure_is_not_clean(self):
        observation = self.observation()
        good = task_snapshot.capture(self.repo, engine_observation=observation, generation=1)
        with mock.patch.object(TaskStore, 'pending', side_effect=StoreError('pending denied')):
            failed = task_snapshot.capture(self.repo, engine_observation=None, generation=2)
        self.assertIsNone(failed.pending_paths)
        self.assertIn('pending denied', ' '.join(failed.errors))
        with mock.patch.object(task_queue, 'store', side_effect=StoreError('read denied')):
            unavailable = task_snapshot.capture(self.repo, engine_observation=None, generation=3)
            stale = task_snapshot.capture(self.repo, engine_observation=None, generation=4, last_good=good)
        self.assertIsNone(unavailable.counts)
        self.assertIsNone(fleet_view.task_counts(fleet_view.Runner('unknown')))
        for invalid in ('invalid observation', {'task_source': 'invalid source'},
                        {'task_source': {'observed_at': 'not a timestamp'}}):
            with self.subTest(invalid=invalid):
                result = task_snapshot.capture(self.repo, engine_observation=invalid, generation=4)
                self.assertEqual(result.counts, good.counts)
                self.assertEqual(result.engine_freshness, 'unknown')
                self.assertTrue(result.errors)
        self.assertEqual(stale.counts, good.counts)
        self.assertEqual((stale.revision, stale.captured_at, stale.freshness),
                         (good.revision, good.captured_at, 'stale'))
        future = time.time() + fleet_view.health.STALE_AFTER + 1
        with mock.patch.object(task_snapshot.time, 'time', return_value=future), \
                mock.patch.object(task_queue, 'store', side_effect=StoreError('read denied')):
            for obs in (observation, dict(observation, status_unavailable_since=future - 1)):
                stale = task_snapshot.capture(self.repo, engine_observation=obs, generation=5, last_good=good)
                self.assertEqual(stale.engine_freshness, 'stale')
                self.assertEqual(stale.engine_source.observed_at, good.engine_source.observed_at)
        store_fixture.write_todo(self.repo, '')
        empty = task_snapshot.capture(self.repo, engine_observation=None, generation=5)
        self.assertEqual(empty.counts, (0, 0, 0, 0, 0, 0))


if __name__ == '__main__':
    unittest.main()
