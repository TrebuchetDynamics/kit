"""Offline subprocess/local-Git fixtures for nonblocking runner maintenance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import coordinator  # noqa: E402
from pi_autowork.supervision import maintenance  # noqa: E402


class AsyncMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aw-maintenance-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo, self.remote = self.root / 'repo', self.root / 'remote.git'
        self.git(self.root, 'init', '-q', '--bare', str(self.remote))
        self.git(self.root, 'init', '-q', '-b', 'main', str(self.repo))
        self.git(self.repo, 'config', 'user.name', 'Fixture')
        self.git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.repo, 'commit', '-qm', 'base', '--allow-empty')
        self.git(self.repo, 'remote', 'add', 'origin', str(self.remote))
        self.git(self.repo, 'push', '-qu', 'origin', 'main')
        self.git(self.repo, 'commit', '-qm', 'verified', '--allow-empty')
        self.source = self.git(self.repo, 'rev-parse', 'HEAD')
        self.owner = coordinator.Coordinator.__new__(coordinator.Coordinator)
        owner = self.owner
        owner.repo, owner.base, owner.integ, owner.seen = str(self.repo), 'main', None, {}
        owner.merge_pending = ''
        owner.state = self.root / 'state'
        owner.state.mkdir()
        owner.cfg = dict(git_common=str(self.repo / '.git'), state_root=str(self.root), pi='fixture-pi')
        owner.package, owner.toolset, owner.toolset_rev = str(self.repo), str(ROOT), 'fixture'
        owner.package_rev = self.git(self.repo, 'rev-parse', '--short', 'HEAD')
        owner.verified = dict(release='fixture', toolset=str(ROOT), push='1', head=self.source)
        (owner.state / 'authority.json').write_text(json.dumps(owner.verified))
        owner.async_maintenance = True
        owner.stop = owner.restart_pending = owner.reload = owner.draining = False
        owner.integration = owner.child = owner.train = owner.prefix_landing = owner.maintainer_job = None
        owner.batch_landing = lambda: []
        owner.last_update_note = ''
        owner.mode = 'continuous'
        for target, attr, value in (
                (coordinator.post_merge_barrier, 'enabled', lambda: False),
                (coordinator.optimistic, 'enabled', lambda: False),
                (coordinator.LOG, 'say', Mock()),
                (coordinator.telemetry, 'observe', Mock())):
            patcher = patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        grant = patch.dict(os.environ, PI_AUTOWORK_PUSH='1')
        grant.start()
        self.addCleanup(grant.stop)
        self.addCleanup(lambda: self.cleanup_jobs())

    def git(self, repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                              check=True, timeout=10).stdout.strip()

    def cleanup_jobs(self):
        maintenance.stop(self.owner)
        for _ in range(100):
            if not any(maintenance.read(self.owner, name).get('job') for name in ('publication', 'update')):
                return
            for name in ('publication', 'update'):
                record = maintenance.read(self.owner, name)
                if maintenance.collect(self.owner, name, record) is not None:
                    maintenance.write(self.owner, name, record)
            time.sleep(.01)

    def until(self, condition):
        deadline = time.monotonic() + 5
        while not condition():
            self.assertLess(time.monotonic(), deadline, 'fixture job did not settle')
            maintenance.poll(self.owner)
            time.sleep(.01)

    def blocked_push(self):
        hook = self.repo / '.git/hooks/pre-push'
        hook.write_text(f'#!/bin/sh\necho $$ > "{self.root / "hook-pid"}"\n'
                        f'touch "{self.root / "hook-started"}"\n'
                        f'while [ ! -f "{self.root / "hook-release"}" ]; do sleep .02; done\n')
        hook.chmod(0o755)
        self.assertEqual(self.owner.push(), 'pending')
        self.until(lambda: (self.root / 'hook-started').exists())

    def test_slow_pre_push_keeps_scheduler_and_main_check_recovery_running_and_pins_sha(self):
        self.blocked_push()
        owner = self.owner
        # Exercise real cycle/begin_cycle without dispatching agents or running project checks.
        for name, result in dict(plan_signature={}, restart_checkpoint=False, in_flight=True,
                                 planning_ready=True, ensure_session=None, follow_base=None,
                                 sweep_tmp=None, check_main=None, land_planning=None,
                                 apply_limits=[], choose_model=('fixture', ''),
                                 dispatch=('PAUSED', {}), handle_outcome=None).items():
            setattr(owner, name, Mock(return_value=result))
        owner.plan_seen = None
        start = time.monotonic()
        owner.cycle()
        owner.cycle()
        self.assertLess(time.monotonic() - start, .5)
        self.assertEqual(owner.check_main.call_count, 2)
        self.assertTrue(maintenance.busy(owner))
        # Main moves while the hook is still checking: only the captured verified SHA can publish.
        self.git(self.repo, 'commit', '-qm', 'not qualified', '--allow-empty')
        (self.root / 'hook-release').touch()
        self.until(lambda: bool(maintenance.read(owner, 'publication').get('published'))
                   and not maintenance.read(owner, 'publication').get('job'))
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), self.source)
        self.assertNotEqual(self.git(self.repo, 'rev-parse', 'HEAD'), self.source)
        self.assertEqual(maintenance.read(owner, 'publication')['published'][0], self.source)

    def test_publication_budget_includes_pre_push_checks_in_both_modes(self):
        with patch.object(maintenance, 'start') as launch:
            self.assertEqual(self.owner.push(), 'pending')
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[4], 3600)
        self.assertTrue(launch.call_args.kwargs['publish'])
        self.owner.async_maintenance = False
        run = subprocess.run
        pushes = []

        def capture(argv, **kwargs):
            if 'push' in argv:
                pushes.append(kwargs['timeout'])
            return run(argv, **kwargs)

        with patch.object(coordinator.subprocess, 'run', side_effect=capture):
            self.assertEqual(self.owner.push(), 'published')
        self.assertEqual(pushes, [3600])
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), self.source)

    def test_fetch_completion_waits_for_review_answer_before_any_session_mutation(self):
        self.owner.integ = str(self.repo)
        self.owner.integration = {'unconsumed': True}
        self.owner.merge_planning = Mock(side_effect=AssertionError('review owns the session'))
        self.owner.fast_forward_main = Mock(side_effect=AssertionError('review owns the session'))
        self.assertEqual(self.owner.sync_upstream(), 'pending')
        self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'merge')
        self.owner.merge_planning.assert_not_called()
        self.owner.fast_forward_main.assert_not_called()
        self.assertFalse(maintenance.read(self.owner, 'publication').get('job'))
        self.owner.integration = None
        self.owner.integ = None
        self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'done')
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), self.source)

    def test_interrupted_publication_is_adopted_and_remote_outcome_reconciled(self):
        self.git(self.repo, 'push', '-q', 'origin', f'{self.source}:main')
        record = dict(repository=str(self.repo), phase='push', source=self.source, remote='origin', branch='main',
                      identity=[self.source, 'origin', 'main', 'fixture', '1'], attempts=1,
                      endpoint=maintenance.endpoint(self.owner, 'origin', push=True),
                      job=dict(pid=99999999, start_time='missing', started=0, limit=300))
        maintenance.write(self.owner, 'publication', record)
        self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'done')
        self.assertEqual(maintenance.read(self.owner, 'publication')['attempts'], 1)
        self.assertIn('published', maintenance.read(self.owner, 'publication'))

    def test_unknown_readback_never_blindly_retries_push_and_has_bounded_probes(self):
        record = dict(repository=str(self.repo), phase='probe', source=self.source, remote='origin', branch='main',
                      identity=[self.source], attempts=1, probes=maintenance.ATTEMPTS, retry_at=time.time() + 300)
        maintenance.write(self.owner, 'publication', record)
        with patch.object(maintenance, 'start') as launch:
            maintenance.poll(self.owner)
            self.assertEqual(self.owner.sync_upstream(), 'pending')
            self.assertEqual(self.owner.push(), 'pending')
        launch.assert_not_called()

    def test_push_retry_exhaustion_and_changed_authority_do_not_launch(self):
        identity = [self.source, 'origin', 'main', 'fixture', '1', maintenance.endpoint(self.owner, 'origin', push=True)]
        maintenance.write(self.owner, 'publication', dict(identity=identity, attempts=maintenance.ATTEMPTS))
        with patch.object(maintenance, 'start') as launch:
            self.assertEqual(self.owner.push(), 'exhausted')
            with patch.dict(os.environ, PI_AUTOWORK_PUSH='0'):
                self.assertEqual(self.owner.push(), 'unverified')
            self.owner.toolset_rev = 'different-release'
            self.assertEqual(self.owner.push(), 'unverified')
        launch.assert_not_called()

    def test_job_timeout_kills_hook_descendants_and_leaves_unknown_outcome_for_readback(self):
        record = dict(repository=str(self.repo), phase='push', source=self.source, remote='origin', branch='main',
                      identity=[self.source], attempts=1,
                      endpoint=maintenance.endpoint(self.owner, 'origin', push=True))
        marker = self.root / 'pid'
        maintenance.start(self.owner, 'publication', record,
                          ['bash', '-c', f'sleep 30 & echo $! > "{marker}"; wait'], .1)
        self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'retry')
        pid = int(marker.read_text())
        from pi_autowork.processes import alive
        self.assertFalse(alive(pid))
        self.assertEqual(maintenance.read(self.owner, 'publication')['attempts'], 1)

    def test_slow_update_discovery_does_not_block_and_defers_reexec_until_collected(self):
        pi = self.root / 'pi'
        pi.write_text(f'#!/bin/sh\ntouch "{self.root / "update-started"}"\n'
                      f'while [ ! -f "{self.root / "update-release"}" ]; do sleep .02; done\n'
                      'exit 0\n')
        pi.chmod(0o755)
        self.owner.cfg['pi'] = str(pi)
        self.owner.last_update, self.owner.update_interval, self.owner.update_wait = 0, 1, 600
        with patch.dict(os.environ, PI_AUTOWORK_PACKAGE_INSTALLED='1'):
            start = time.monotonic()
            self.owner.update_toolset()
            self.assertLess(time.monotonic() - start, .5)
        self.until(lambda: (self.root / 'update-started').exists())
        self.owner.reload = True
        self.owner.reexec = Mock()
        self.owner.restart_if_updated()
        self.owner.reexec.assert_not_called()
        self.assertIn('maintenance', self.owner.merge_operation())
        (self.root / 'update-release').touch()
        self.until(lambda: not maintenance.busy(self.owner))
        self.owner.restart_if_updated()
        self.owner.reexec.assert_called_once()

    def test_toolset_lock_is_nonblocking_and_only_exact_checked_candidate_can_activate(self):
        import fcntl
        lock = (self.root / 'toolset-update.lock').open('a')
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.monotonic()
        result = maintenance.update_package('unused', str(self.root), str(self.owner.state),
                                            str(self.repo), str(ROOT), '600')
        self.assertLess(time.monotonic() - start, .5)
        self.assertTrue(result['retry'])
        fcntl.flock(lock, fcntl.LOCK_UN)
        with patch.object(maintenance.release, 'package_source', return_value='git:example.invalid/repo'), \
                patch.object(maintenance.release, 'check', return_value={'ok': True}), \
                patch.object(maintenance, 'git', side_effect=['checked-sha', 'different-sha']), \
                patch.object(maintenance.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            result = maintenance.update_package('unused', str(self.root), str(self.owner.state),
                                                str(self.repo), str(ROOT), '600')
        self.assertFalse(result['ok'])
        self.assertEqual(result['blocked'], 'different-sha')
        maintenance.write(self.owner, 'update', dict(outcome=dict(blocked=self.source)))
        self.owner.reload = True
        self.owner.reexec = Mock()
        self.owner.restart_if_updated()
        self.owner.reexec.assert_not_called()

    def test_readback_cooldown_recovers_without_any_extra_push(self):
        self.git(self.repo, 'push', '-q', 'origin', f'{self.source}:main')
        record = dict(repository=str(self.repo), phase='probe', source=self.source, remote='origin', branch='main',
                      identity=[self.source], attempts=maintenance.ATTEMPTS,
                      endpoint=maintenance.endpoint(self.owner, 'origin', push=True),
                      probes=maintenance.ATTEMPTS, retry_at=time.time() + 300)
        maintenance.write(self.owner, 'publication', record)
        with patch.object(maintenance, 'start') as launch:
            maintenance.poll(self.owner)
        launch.assert_not_called()
        record['retry_at'] = 0
        maintenance.write(self.owner, 'publication', record)
        real_start = maintenance.start
        commands = []
        def capture(owner, name, record, argv, limit, **kwargs):
            commands.append(argv)
            return real_start(owner, name, record, argv, limit, **kwargs)
        with patch.object(maintenance, 'start', capture):
            self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'done')
        self.assertEqual(len(commands), 1)
        self.assertIn('ls-remote', commands[0])
        self.assertNotIn('push', commands[0])
        self.assertEqual(maintenance.read(self.owner, 'publication')['attempts'], maintenance.ATTEMPTS)

    def test_destination_drift_and_multiple_push_urls_never_redirect_publication(self):
        self.blocked_push()
        record = maintenance.read(self.owner, 'publication')
        fingerprint = record['endpoint']
        self.assertNotIn(str(self.remote), json.dumps(record))
        self.git(self.repo, 'remote', 'set-url', '--push', 'origin', str(self.root / 'new.git'))
        (self.root / 'hook-release').touch()
        # The running Git already resolved its endpoint before entering the real hook.
        self.until(lambda: not maintenance.running(maintenance.read(self.owner, 'publication').get('job')))
        maintenance.poll(self.owner)
        record = maintenance.read(self.owner, 'publication')
        self.assertEqual(record['phase'], 'probe')
        self.assertEqual(record['endpoint'], fingerprint)
        self.assertFalse(record.get('job'))
        self.assertEqual(self.owner.push(), 'pending')
        # A fresh candidate also cannot start a multi-destination push.
        (self.owner.state / 'maintenance-publication.json').unlink()
        self.git(self.repo, 'config', '--add', 'remote.origin.pushurl', str(self.remote))
        with patch.object(maintenance, 'start') as launch:
            self.assertEqual(self.owner.push(), 'ambiguous-destination')
        launch.assert_not_called()

    def test_crash_before_spawn_keeps_intent_and_reconciles_without_repeating_side_effect(self):
        class Crash(BaseException):
            pass
        real_popen = subprocess.Popen
        def crash_launcher(argv, *args, **kwargs):
            if 'launch' in argv:
                raise Crash
            return real_popen(argv, *args, **kwargs)
        with patch.object(maintenance.subprocess, 'Popen', side_effect=crash_launcher):
            with self.assertRaises(Crash):
                self.owner.push()
        record = maintenance.read(self.owner, 'publication')
        self.assertEqual(record['phase'], 'push')
        self.assertEqual(record['attempts'], 1)
        self.assertIn('intent', record['job'])
        self.assertNotIn('pid', record['job'])
        # Expired launch intents are fenced: even a delayed child cannot execute them.
        record['job']['started'] = 0
        maintenance.write(self.owner, 'publication', record)
        marker = self.root / 'late-side-effect'
        maintenance.launch(str(self.owner.state), 'publication', record['job']['intent'], 1,
                           ['touch', str(marker)])
        self.assertFalse(marker.exists())
        real_start = maintenance.start
        commands = []
        def capture(owner, name, record, argv, limit, **kwargs):
            commands.append(argv)
            return real_start(owner, name, record, argv, limit, **kwargs)
        with patch.object(maintenance, 'start', capture):
            self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'retry')
        self.assertTrue(commands and all('push' not in argv for argv in commands))
        self.assertEqual(maintenance.read(self.owner, 'publication')['attempts'], 1)

    def test_crash_after_collect_retains_job_until_atomic_publication_transition(self):
        record = dict(repository=str(self.repo), phase='push', source=self.source, remote='origin', branch='main',
                      identity=[self.source], attempts=1,
                      endpoint=maintenance.endpoint(self.owner, 'origin', push=True),
                      job=dict(pid=99999999, start_time='missing', started=0, limit=300))
        maintenance.write(self.owner, 'publication', record)
        collected = maintenance.read(self.owner, 'publication')
        self.assertEqual(maintenance.collect(self.owner, 'publication', collected)[0], 125)
        self.assertNotIn('job', collected)
        # Simulate losing the in-memory result. Disk still contains the tracked push.
        self.assertIn('job', maintenance.read(self.owner, 'publication'))
        with patch.object(maintenance, 'start') as launch:
            maintenance.poll(self.owner)
        self.assertEqual(launch.call_args.args[3][3], 'ls-remote')
        self.assertEqual(maintenance.read(self.owner, 'publication')['attempts'], 1)

    def test_interrupted_update_that_moved_package_cannot_activate_after_current_probe(self):
        record = dict(identity=[str(self.repo), self.source], attempts=1,
                      job=dict(pid=99999999, start_time='missing', started=0, limit=600))
        maintenance.write(self.owner, 'update', record)
        self.git(self.repo, 'commit', '-qm', 'partially updated', '--allow-empty')
        moved = self.git(self.repo, 'rev-parse', 'HEAD')
        maintenance.poll(self.owner)
        self.assertEqual(maintenance.read(self.owner, 'update')['outcome']['blocked'], moved)
        # A subsequent "already current" discovery cannot erase the activation hold.
        record = maintenance.read(self.owner, 'update')
        record.update(identity=[str(self.repo), moved],
                      job=dict(pid=99999999, start_time='missing', started=0, limit=600))
        maintenance.write(self.owner, 'update', record)
        (self.owner.state / 'maintenance-update.exit').write_text('0')
        (self.owner.state / 'maintenance-update.log').write_text(json.dumps(dict(ok=False, current=True)))
        maintenance.poll(self.owner)
        self.owner.reload = True
        self.owner.reexec = Mock()
        self.owner.restart_if_updated()
        self.owner.reexec.assert_not_called()

    def test_install_attempts_are_bounded_per_checked_revision(self):
        with patch.object(maintenance.release, 'package_source', return_value='git:example.invalid/repo'), \
                patch.object(maintenance.release, 'check', return_value={'ok': True}), \
                patch.object(maintenance, 'git', side_effect=lambda path, *args: 'checked' if args[-1] == 'FETCH_HEAD' else 'old'), \
                patch.object(maintenance.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as install:
            for _ in range(maintenance.ATTEMPTS + 1):
                result = maintenance.update_package('unused', str(self.root), str(self.owner.state),
                                                    str(self.repo), str(ROOT), '600')
        self.assertEqual(install.call_count, maintenance.ATTEMPTS)
        self.assertIn('exhausted', result['reason'])

    def test_non_object_state_is_fail_closed_without_launch_or_budget_reset(self):
        (self.owner.state / 'maintenance-publication.json').write_text('[]')
        with patch.object(maintenance, 'start') as launch:
            self.assertEqual(self.owner.push(), 'invalid-state')
            self.assertEqual(self.owner.sync_upstream(), 'invalid-state')
        launch.assert_not_called()
        self.assertTrue(maintenance.busy(self.owner))

    def test_killed_launcher_cleans_blocked_hook_before_attempt_can_retry(self):
        from pi_autowork.processes import alive
        self.blocked_push()
        record = maintenance.read(self.owner, 'publication')
        hook_pid = int((self.root / 'hook-pid').read_text())
        os.kill(record['job']['pid'], 9)  # only the registered leader, not its group
        self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'retry')
        self.assertFalse(alive(hook_pid))
        self.assertFalse((self.root / 'hook-release').exists())
        self.assertEqual(maintenance.read(self.owner, 'publication')['attempts'], 1)

    def test_stop_cancels_pidless_intent_under_registration_fence(self):
        record = dict(phase='push', attempts=1, job=dict(intent='unspawned', started=time.time(), limit=300))
        maintenance.write(self.owner, 'publication', record)
        maintenance.stop(self.owner)
        marker = self.root / 'late-side-effect'
        maintenance.launch(str(self.owner.state), 'publication', 'unspawned', 1, ['touch', str(marker)])
        self.assertFalse(marker.exists())
        record = maintenance.read(self.owner, 'publication')
        self.assertTrue(record['job']['cancelled'])
        self.assertEqual(record['attempts'], 1)

    def test_child_revalidates_queued_endpoint_before_executing_command(self):
        record = dict(repository=str(self.repo), phase='push', remote='origin', attempts=1,
                      endpoint=maintenance.endpoint(self.owner, 'origin', push=True),
                      job=dict(intent='queued', started=time.time(), limit=300))
        maintenance.write(self.owner, 'publication', record)
        self.git(self.repo, 'remote', 'set-url', '--push', 'origin', str(self.root / 'new.git'))
        marker = self.root / 'must-not-run'
        with patch.object(maintenance.os, 'killpg'):
            maintenance.launch(str(self.owner.state), 'publication', 'queued', 1, ['touch', str(marker)])
        self.assertFalse(marker.exists())
        self.assertEqual((self.owner.state / 'maintenance-publication.exit').read_text().strip(), '125')
        # This was an in-process launcher fixture; do not treat the test interpreter as a child.
        record['job']['pid'] = -1
        maintenance.write(self.owner, 'publication', record)

    def test_update_success_cannot_qualify_a_different_head_at_collection(self):
        record = dict(identity=[str(self.repo), self.source], attempts=1,
                      job=dict(pid=99999999, start_time='missing', started=0, limit=600))
        maintenance.write(self.owner, 'update', record)
        (self.owner.state / 'maintenance-update.exit').write_text('0')
        (self.owner.state / 'maintenance-update.log').write_text(json.dumps(dict(ok=True, revision=self.source)))
        self.git(self.repo, 'commit', '-qm', 'unchecked package movement', '--allow-empty')
        changed = self.git(self.repo, 'rev-parse', 'HEAD')
        maintenance.poll(self.owner)
        self.assertEqual(maintenance.read(self.owner, 'update')['outcome']['blocked'], changed)
        self.owner.reload = True
        self.owner.reexec = Mock()
        self.owner.restart_if_updated()
        self.owner.reexec.assert_not_called()

    def test_consumed_update_receipt_pins_activation_after_package_head_moves(self):
        script = self.repo / 'pi-autowork/bin/pi-autowork.sh'
        command = self.repo / 'pi-autowork/pi_autowork/command.py'
        script.parent.mkdir(parents=True)
        command.parent.mkdir(parents=True)
        script.write_text('#!/bin/bash\ntrue\n')
        command.write_text('pass\n')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-qm', 'qualified package A')
        qualified = self.git(self.repo, 'rev-parse', 'HEAD')
        maintenance.write(self.owner, 'update', dict(identity=[str(self.repo), self.source], attempts=1,
                          job=dict(pid=99999999, start_time='missing', started=0, limit=600)))
        (self.owner.state / 'maintenance-update.exit').write_text('0')
        (self.owner.state / 'maintenance-update.log').write_text(json.dumps(dict(ok=True, revision=qualified)))
        maintenance.poll(self.owner)
        self.assertTrue(maintenance.read(self.owner, 'update')['outcome']['ok'])
        # Drift happens after the successful receipt has already been consumed.
        script.write_text('if then fi\n')
        self.git(self.repo, 'commit', '-qam', 'unchecked package B')
        unchecked = self.git(self.repo, 'rev-parse', 'HEAD')
        self.assertNotEqual(qualified, unchecked)
        self.owner.reexec = Mock()
        self.assertEqual(self.owner.reexec_due(), 'update')
        with patch.object(coordinator.release, 'prepare', wraps=coordinator.release.prepare) as prepare:
            self.owner.restart_if_updated()
        prepare.assert_called_once_with(str(self.root), str(self.repo), revision=qualified)
        self.assertEqual(self.owner.reexec.call_args.kwargs['revision'], qualified)
        # Once A is selected, B cannot cause a repeated automatic activation.
        self.owner.package_rev = self.git(self.repo, 'rev-parse', '--short', qualified)
        self.assertEqual(self.owner.reexec_due(), '')
        with patch.object(coordinator.release, 'prepare') as prepare:
            self.owner.restart_if_updated()
        prepare.assert_not_called()

    def test_explicit_reload_still_reselects_settings_and_release(self):
        maintenance.write(self.owner, 'update', dict(outcome=dict(ok=True, revision=self.source)))
        self.git(self.repo, 'commit', '-qm', 'owner package change', '--allow-empty')
        self.owner.reload = True
        self.owner.reexec = Mock()
        self.assertEqual(self.owner.reexec_due(), 'reload')
        with patch.object(coordinator.release, 'prepare') as prepare:
            self.owner.restart_if_updated()
        prepare.assert_not_called()
        self.assertEqual(self.owner.reexec.call_args.kwargs, {'reload': True})

    def test_invalid_receipt_exits_finite_drain_nonzero_instead_of_waiting_forever(self):
        (self.owner.state / 'maintenance-publication.json').write_text('[]')
        owner = self.owner
        owner.draining, owner.settled, owner.mode = True, False, 'until-empty'
        for name, result in dict(settle=None, handle_requests=None,
                                 status=dict(outcome='PARALLEL_STATUS', tasks=[]), health_update=None,
                                 in_flight=False, tasks=[], maintain=False, stop_maintainer=None,
                                 stop_integration=None).items():
            setattr(owner, name, Mock(return_value=result))
        with self.assertRaises(coordinator.Finish) as done:
            owner.finish_cycle('IDLE')
        self.assertEqual(done.exception.code, 4)

    def test_landings_during_older_push_coalesce_into_fresh_qualified_candidate(self):
        self.blocked_push()
        self.git(self.repo, 'commit', '-qm', 'new qualified landing', '--allow-empty')
        new = self.git(self.repo, 'rev-parse', 'HEAD')
        self.owner.verified['head'] = new
        (self.owner.state / 'authority.json').write_text(json.dumps(self.owner.verified))
        self.assertEqual(self.owner.sync_upstream(), 'pending')
        (self.root / 'hook-release').touch()
        self.until(lambda: maintenance.read(self.owner, 'publication').get('published', [None])[0] == new)
        self.assertEqual(self.git(self.remote, 'rev-parse', 'main'), new)

    def test_fetched_remote_already_contains_candidate_without_noop_push_or_hook(self):
        self.git(self.repo, 'push', '-q', 'origin', f'{self.source}:main')
        marker = self.root / 'unnecessary-hook'
        hook = self.repo / '.git/hooks/pre-push'
        hook.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
        hook.chmod(0o755)
        self.assertEqual(self.owner.sync_upstream(), 'pending')
        self.until(lambda: maintenance.read(self.owner, 'publication').get('phase') == 'done')
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
