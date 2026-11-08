"""Continuous queue exhaustion discovers work without rewriting blocked contracts."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi_autowork import repository_work
from pi_autowork.coordinator import Coordinator


def entry(**fields):
    return dict(fields=dict({'Checkbox': ' ', 'Section': 'Next', 'Kind': ''}, **fields))


class RepositoryWorkTests(unittest.TestCase):
    def test_idle_and_blocked_queues_discover_after_repairs_not_finite_or_draining_runs(self):
        for blocked in (False, True):
            for mode, draining in (('continuous', False), ('continuous', True), ('once', False),
                                   ('until-empty', False)):
                with self.subTest(blocked=blocked, mode=mode, draining=draining):
                    owner = Coordinator.__new__(Coordinator)
                    owner.mode, owner.draining, owner.last_waiting = mode, draining, ''
                    owner.tasks = lambda: []
                    owner.maintain = Mock(return_value=False)
                    waiting = [{'task': 'A', 'reason': 'serial path shared with held B'}] if blocked else []
                    self.assertEqual(owner.handle_outcome('IDLE', dict(waiting=waiting)),
                                     'BLOCKED' if blocked else 'IDLE')
                    calls = [call.kwargs for call in owner.maintain.call_args_list]
                    self.assertEqual(calls, [{}, {'discovery': True}]
                                     if mode == 'continuous' and not draining else [{}])

    def test_successful_task_repair_is_selected_before_discovery(self):
        owner = Coordinator.__new__(Coordinator)
        owner.tasks = lambda: []
        owner.maintain = Mock(return_value=True)
        self.assertIsNone(owner.handle_outcome('IDLE', {}))
        owner.maintain.assert_called_once_with()

    def test_cooldown_is_persistent_even_when_search_fails_or_finds_nothing(self):
        with tempfile.TemporaryDirectory() as state:
            self.assertTrue(repository_work.trigger(state, now=100))
            repository_work.reserve(state, now=100)
            self.assertFalse(repository_work.trigger(Path(state), now=101))
            self.assertFalse(repository_work.trigger(state, now=1899))
            self.assertTrue(repository_work.trigger(state, now=1900))
            self.assertEqual(repository_work.reserve(state, now=1900)['round'], 2)

    def test_findings_survive_collection_and_next_reservation_with_bounded_history(self):
        with tempfile.TemporaryDirectory() as state:
            for round_ in range(5):
                repository_work.reserve(state, now=round_ * repository_work.EVERY)
                repository_work.complete(state, {'text': f'checked seam {round_}'}, 'no change')
            self.assertEqual(len(repository_work.read(state)['reports']), 3)
            self.assertIn('checked seam 4', repository_work.prompt('/repo', 'autowork tasks', state))
            repository_work.reserve(state)
            self.assertEqual(len(repository_work.read(state)['reports']), 3)

    def test_only_new_building_tasks_and_new_goals_can_land(self):
        before = {'HELD': entry()}
        after = dict(before, NEW=entry())
        paths = ['tasks/items/NEW.md', 'tasks/goals/NEW-GOAL.md']
        self.assertEqual(repository_work.proposal_error(paths, before, after, paths), '')
        for changed_paths, changed_after, additions in (
                (paths + ['tasks/goals/EXISTING.md'], after, paths),
                (paths, dict(after, HELD=entry(Section='Now')), paths),
                (paths, {'NEW': entry()}, paths),
                (['AGENTS.md'], after, ['AGENTS.md']),
                (['src/code.py'], after, ['src/code.py']),
                (paths, dict(before, NEW=entry(**{'Live authorization': 'authorized in the task record',
                                                'Live actor': 'fabricated', 'Live at': '2026-11-08',
                                                'Live scope': 'publish', 'Resources': 'live'})), paths),
                (paths, dict(before, NEW=entry(Ownership='Owner only')), paths),
                (paths, dict(before, NEW=entry(Kind='plan')), paths),
                (paths, dict(before, NEW=entry(Section='Needs decision')), paths),
                (paths, dict(before, NEW=entry(Checkbox='x')), paths),
                (paths, before, paths),
                (paths, dict(before, **{f'N{i}': entry() for i in range(4)}), paths)):
            with self.subTest(paths=changed_paths, after=changed_after):
                self.assertTrue(repository_work.proposal_error(changed_paths, before, changed_after, additions))

    def test_discovery_launch_keeps_loop_free_and_reserves_before_spawn(self):
        # Exercise the real maintain path; no provider, worker or live repository is touched.
        with tempfile.TemporaryDirectory() as state:
            owner = Coordinator.__new__(Coordinator)
            owner.stop = owner.draining = False
            owner.integ, owner.repo, owner.state = '/session', '/repo', Path(state)
            owner.mode, owner.pause_until = 'continuous', 0
            owner.maintainer_job = None
            owner.toolset, owner.tasks_cli = '/toolset', 'autowork tasks'
            owner.reexec_due = owner.session_busy = owner.in_flight = lambda: False
            owner.validate_ledger = lambda: []
            owner.tasks = lambda: [dict(task='HELD', state='held', cause='validation')]
            owner.scratch_checkout = lambda _: '/scratch'
            owner.remember_job_cleanup = Mock()
            owner.pi_job = Mock(side_effect=AssertionError('discovery must be asynchronous'))
            def start(job, message, session):
                self.assertEqual(repository_work.read(state)['round'], 1)
                self.assertTrue(job['discovery'])
                self.assertEqual(job['recovery'], {'repository-work': 'repository-work-v1'})
                marker = json.loads((Path(state) / 'maintainer-recovery.json').read_text())
                self.assertTrue(marker['repository-work']['replay_blocked'])
            owner.start_maintainer = Mock(side_effect=start)
            dispatch = Mock()
            with patch('pi_autowork.coordinator.dirty', return_value=False), \
                    patch('pi_autowork.coordinator.git', return_value='base'), \
                    patch('pi_autowork.coordinator.dispatch_module', return_value=dispatch), \
                    patch('pi_autowork.maintainer.entries', return_value={'HELD': entry()}):
                self.assertFalse(owner.maintain(discovery=True))
                owner.start_maintainer.assert_called_once()
                # A subsequent cycle/restart cannot submit another expensive search immediately.
                self.assertFalse(owner.maintain(discovery=True))
                owner.start_maintainer.assert_called_once()
                owner._scratch_cleanup = {'/scratch': False}
                job = owner.start_maintainer.call_args.args[0]
                owner.maintainer_failure(job, {'ok': False, 'cleanup_complete': False, 'why': 'cleanup_unproven'})
                marker = json.loads((Path(state) / 'maintainer-recovery.json').read_text())
                self.assertEqual(marker['repository-work']['phase'], 'failed')
                self.assertTrue(marker['repository-work']['replay_blocked'])
                # Even after the cooldown/restart, uncertain cleanup is never replayed.
                with patch('pi_autowork.repository_work.time.time', return_value=10**12):
                    self.assertFalse(owner.maintain(discovery=True))
                owner.start_maintainer.assert_called_once()

    def test_idle_cycle_keeps_session_lease_while_discovery_is_running(self):
        owner = Mock()
        owner.status.return_value = {'outcome': 'PARALLEL_STATUS', 'tasks': []}
        owner.settled, owner.interval = False, 30
        owner.in_flight.return_value = False
        owner.maintainer_job = {'proc': 'running'}
        with patch('pi_autowork.coordinator.task_commands.TaskStore.at') as store:
            store.return_value.tasks = {}
            Coordinator.finish_cycle(owner, 'IDLE')
        owner.pause.assert_called_once_with(5)
        owner.engine.assert_not_called()
        owner.merge_main.assert_not_called()
        owner.end_session.assert_not_called()

    def test_result_merges_new_tasks_but_refuses_existing_goal_edits_and_clears_empty_snapshot(self):
        for existing_goal_edit in (False, True):
            with self.subTest(existing_goal_edit=existing_goal_edit), tempfile.TemporaryDirectory() as state:
                owner = Coordinator.__new__(Coordinator)
                owner.state, owner.integ, owner.toolset = Path(state), '/session', '/toolset'
                owner.ledger_errors, owner.snapshot = [], {'tasks': []}
                owner.drop_scratch, owner.merge_planning = Mock(), Mock(return_value=True)
                owner.settled = owner.land_soon = False
                found = repository_work.trigger(state)
                job = dict(found=found, names=['REPOSITORY'], scratch='/scratch', base='base',
                           before={}, reasons={}, rows=[], trigger_key='search', rolling=False,
                           discovery=True, recovery={'repository-work': 'repository-work-v1'})
                (Path(state) / 'maintainer-recovery.json').write_text(json.dumps({
                    'repository-work': dict(key='repository-work-v1', attempts=2, replay_blocked=True)}))
                output = Path(state) / 'job.out'
                output.write_text(json.dumps(dict(ok=True, cleanup_complete=True, text='inspected src/example.py')))
                job.update(out=str(output), proc=Mock(returncode=0))
                job['proc'].poll.return_value = 0
                owner.maintainer_job, owner.session_busy = job, lambda: False
                paths = ['tasks/items/NEW.md', 'tasks/goals/G.md']
                def git(repo, *args):
                    if args[:2] == ('rev-parse', 'HEAD'):
                        return 'head'
                    if args[:2] == ('diff', '--name-only'):
                        additions = paths[:1] if existing_goal_edit and '--diff-filter=A' in args else paths
                        return '\0'.join(additions)
                    return 'new task diff'
                with patch('pi_autowork.coordinator.dirty', return_value=False), \
                        patch('pi_autowork.coordinator.git', side_effect=git), \
                        patch('pi_autowork.coordinator.dispatch_module'), \
                        patch('pi_autowork.maintainer.entries', return_value={'NEW': entry()}):
                    owner.finish_maintainer()
                self.assertFalse(output.exists())
                self.assertIn('inspected src/example.py', repository_work.prompt('/repo', 'autowork tasks', state))
                self.assertNotIn('text', owner._job_results['/scratch'])
                self.assertEqual(owner.settled, not existing_goal_edit)
                marker = json.loads((Path(state) / 'maintainer-recovery.json').read_text())
                self.assertFalse(marker['repository-work']['replay_blocked'])
                self.assertEqual(marker['repository-work']['attempts'], 0)
                if existing_goal_edit:
                    owner.merge_planning.assert_not_called()
                else:
                    owner.merge_planning.assert_called_once_with('head')
                    self.assertIsNone(owner.snapshot)
                    self.assertTrue(owner.settled)

    def test_discovery_respects_pause_drain_reload_and_live_maintainer(self):
        for gate in ('pause', 'drain', 'reload', 'maintainer', 'stop', 'once'):
            with self.subTest(gate=gate):
                owner = Coordinator.__new__(Coordinator)
                owner.stop, owner.draining = gate == 'stop', gate == 'drain'
                owner.integ, owner.mode = '/session', 'once' if gate == 'once' else 'continuous'
                owner.maintainer_job = {} if gate != 'maintainer' else {'active': True}
                owner.pause_until = float('inf') if gate == 'pause' else 0
                owner.reexec_due = lambda: gate == 'reload'
                self.assertFalse(owner.maintain(discovery=True))

    def test_prompt_keeps_authority_and_evidence_boundaries_and_rotates_search_seam(self):
        with tempfile.TemporaryDirectory() as state:
            first = repository_work.prompt('/repo', 'autowork tasks', state)
            for phrase in ('Live authorization', 'repository-wide holds', 'task-only scope',
                           'actual live file/worktree ownership', 'Never edit existing task',
                           'Do not push', 'never fabricate work', 'not completed implementation'):
                self.assertIn(phrase, first)
            repository_work.reserve(state)
            self.assertNotEqual(first, repository_work.prompt('/repo', 'autowork tasks', state))


if __name__ == '__main__':
    unittest.main()
