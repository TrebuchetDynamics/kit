"""Actual subprocess/pipe tests, never launch Pi or contact a provider."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork.planning_rpc import RPC, RPCError, Cancelled, ShutdownOutcome
from pi_autowork.planning import Planner, PlanningError

FAKE = r'''#!/usr/bin/env python3
import json, os, signal, sys, time
from pathlib import Path
mode = Path(__file__).stem
if '--version' in sys.argv:
    print('1.2.0' if mode == 'old_version' else '1.4.0')
    sys.exit(0)
if mode in ('hung', 'settled_hung'):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
log = Path(__file__).with_suffix('.log')
with log.open('a') as out:
    out.write(json.dumps({'argv':sys.argv}) + '\n')

def emit(value):
    sys.stdout.buffer.write(json.dumps(value, ensure_ascii=False).encode() + b'\n')
    sys.stdout.buffer.flush()

for line in sys.stdin.buffer:
    cmd = json.loads(line)
    with log.open('a') as out:
        out.write(json.dumps(cmd) + '\n')
    name = cmd['type']
    data = {}
    if name == 'stall':
        time.sleep(30)
    if name == 'get_commands':
        data = {'commands': [] if mode == 'missing_commands' else [{'name': 'skill:plan-for-me', 'source': 'skill'}]}
    if name == 'get_state':
        data = {'isStreaming': False, 'sessionId': sys.argv[sys.argv.index('--session-id') + 1] if '--session-id' in sys.argv else 'test'}
    if name == 'steer':
        data = {'disposition': 'queued'}
    if name == 'prompt':
        if mode == 'eof':
            sys.exit(0)
        if mode == 'wrong_id':
            emit({'type':'response', 'id':'wrong', 'command':name, 'success':True})
            continue
        sys.stderr.write('private sk-not-for-stdout-test\n' * 20000)
        sys.stderr.flush()
        data = {'disposition': 'handled' if mode == 'handled' else 'queued' if mode == 'queued' else 'started'}
        if mode == 'early':
            emit({'type':'message_end', 'message': {'role':'assistant', 'content':[{'type':'text','text':'before response'}], 'stopReason':'stop'}})
            emit({'type':'agent_settled', 'aborted':False})
    emit({'type':'response', 'id':cmd['id'], 'command':name, 'success':True, 'data':data})
    if name == 'prompt' and mode == 'hung':
        time.sleep(30)
    if name == 'prompt' and mode not in ('handled', 'early', 'wait'):
        text = 'one\u2028two\u2029three'
        if mode == 'planner':
            text = 'A proposed plan.\n```autowork-plan\n' + json.dumps({'files': {'docs/plans/proposed.md': '# Proposed\n'}}) + '\n```'
        emit({'type':'message_update', 'assistantMessageEvent':{'type':'text_delta','delta':text}})
        emit({'type':'agent_end', 'messages':[]})
        if mode == 'agent_end':
            sys.exit(0)
        emit({'type':'message_end', 'message':{'role':'assistant','content':[{'type':'text','text':text}], 'stopReason':'error' if mode == 'error' else 'stop', 'errorMessage':'private-token' if mode == 'error' else ''}})
        emit({'type':'agent_settled', 'aborted':False})
        if mode == 'settled_hung':
            time.sleep(30)
    if name == 'abort':
        emit({'type':'agent_settled', 'aborted':True})
if mode == 'nonzero':
    sys.exit(7)
'''


class RPCTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def client(self, mode, cancel=None, events=None):
        script = self.root / mode
        script.write_text(FAKE)
        script.chmod(0o700)
        client = RPC([str(script)], self.root, self.root / ('private-' + mode),
                     cancel=cancel, on_event=events.append if events is not None else None,
                     command_timeout=.5, run_timeout=3, shutdown_timeout=.2)
        self.addCleanup(client.close)
        return client

    def test_lf_framing_streaming_and_stderr_drain(self):
        events = []
        client = self.client('normal', events=events)
        self.assertEqual(client.request('get_commands')['commands'][0]['name'], 'skill:plan-for-me')
        result = client.turn('literal chat')
        self.assertEqual(result['text'], 'one\u2028two\u2029three')
        self.assertTrue(any(e['type'] == 'message_update' for e in events))
        outcome = client.close()
        self.assertTrue(outcome.clean, outcome)
        self.assertEqual(outcome.returncode, 0)
        self.assertFalse(outcome.forced)
        self.assertTrue(outcome.readers_stopped)
        self.assertTrue(outcome.resources_closed)
        with patch('pi_autowork.planning_rpc.os.killpg', side_effect=AssertionError('repeated signal')):
            self.assertIs(client.close(abort=True), outcome)
        self.assertIsNotNone(client.process.poll())
        self.assertEqual((self.root / 'private-normal').stat().st_mode & 0o777, 0o700)

    def test_dispositions_and_events_before_prompt_response(self):
        self.assertEqual(self.client('handled').turn('x')['status'], 'handled')
        self.assertEqual(self.client('queued').turn('x')['status'], 'ready')
        self.assertEqual(self.client('early').turn('x')['text'], 'before response')

    def test_eof_provider_error_and_agent_end_are_not_success(self):
        for mode in ('eof', 'error', 'agent_end', 'wrong_id'):
            with self.subTest(mode=mode), self.assertRaises(RPCError):
                self.client(mode).turn('x')

    def test_deadline_and_kill_escalation_are_bounded(self):
        client = self.client('hung')
        client.run_timeout = .15
        start = time.monotonic()
        with self.assertRaisesRegex(RPCError, 'deadline'):
            client.turn('wait forever')
        outcome = client.close(abort=True)
        self.assertFalse(outcome.clean)
        self.assertTrue(outcome.forced)
        self.assertEqual(outcome.returncode, -9)
        self.assertIs(client.close(), outcome)
        self.assertLess(time.monotonic() - start, 3)
        self.assertIsNotNone(client.process.poll())
        self.assertFalse(client.reader.is_alive())
        self.assertFalse(client.stderr_reader.is_alive())

    def test_abort_response_is_correlated_during_shutdown(self):
        client = self.client('wait')
        client.request('get_state')
        client.close(abort=True)
        self.assertNotEqual(client.failure, 'uncorrelated Pi RPC response')
        records = [json.loads(line) for line in (self.root / 'wait.log').read_text().splitlines()]
        self.assertIn('abort', [r.get('type') for r in records])

    def test_nonzero_exit_is_not_clean(self):
        client = self.client('nonzero')
        self.assertEqual(client.turn('x')['status'], 'ready')
        outcome = client.close()
        self.assertEqual(outcome.returncode, 7)
        self.assertFalse(outcome.forced)
        self.assertFalse(outcome.clean)

    def test_incomplete_reader_cleanup_is_reported_without_closing_live_pipe(self):
        client = self.client('normal')
        client.request('get_state')
        with patch.object(client.reader, 'is_alive', return_value=True):
            outcome = client.close()
        self.assertFalse(outcome.clean)
        self.assertFalse(outcome.readers_stopped)
        self.assertFalse(outcome.resources_closed)
        self.assertFalse(client.process.stdout.closed)
        # The fixture only simulates a live reader; release its retained resources.
        client.reader.join(2)
        client.process.stdout.close()
        client.raw.close()
        self.assertIs(client.close(), outcome)

    def test_pending_request_observes_close_before_escalation_completes(self):
        client = self.client('hung')
        client.command_timeout = 10
        errors = []
        def request():
            try:
                client.request('stall')
            except RPCError as exc:
                errors.append(str(exc))
        requester = threading.Thread(target=request)
        requester.start()
        deadline = time.monotonic() + 2
        log = self.root / 'hung.log'
        while not log.exists() or 'stall' not in log.read_text():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.01)
        outcomes = []
        closer = threading.Thread(target=lambda: outcomes.append(client.close()))
        closer.start()
        try:
            requester.join(.3)
            self.assertFalse(requester.is_alive())
            self.assertEqual(errors, ['Pi RPC is closed'])
            with self.assertRaisesRegex(RPCError, 'closed'):
                client.request('get_state')
        finally:
            closer.join(3)
            requester.join(3)
        self.assertFalse(closer.is_alive())
        self.assertEqual(client.pending, {})
        self.assertIs(client.close(), outcomes[0])

    def test_resource_close_failure_does_not_skip_other_cleanup(self):
        client = self.client('normal')
        client.request('get_state')
        with patch.object(client.raw, 'close', side_effect=OSError('synthetic failure')):
            outcome = client.close()
        self.assertFalse(outcome.clean)
        self.assertFalse(outcome.resources_closed)
        self.assertEqual(outcome.errors, ('cannot close Pi RPC resource',))
        self.assertTrue(client.errors.closed)
        client.raw.close()

    def test_cancellation_and_steering_same_process(self):
        cancel = threading.Event()
        client = self.client('wait', cancel=cancel)
        outcome = []
        def turn():
            try:
                client.turn('wait')
            except Cancelled:
                outcome.append('cancelled')
            finally:
                client.close()
        thread = threading.Thread(target=turn)
        thread.start()
        time.sleep(.15)
        self.assertEqual(client.request('steer', message='Literal user message:\n/ignore'), {'disposition': 'queued'})
        cancel.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, ['cancelled'])
        self.assertIsNotNone(client.process.poll())


class PlanningShutdownTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / '.gitignore').write_text('/.worktrees/\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        for args in (('init', '-q', '-b', 'main'), ('config', 'user.name', 'Fixture'),
                     ('config', 'user.email', 'fixture@example.invalid'), ('add', '.'),
                     ('commit', '-qm', 'fixture')):
            subprocess.run(['git', '-C', str(self.repo), *args], env=env, check=True,
                           capture_output=True)

    def planner(self, mode):
        script = self.root / mode
        script.write_text(FAKE)
        script.chmod(0o700)
        planner = Planner(self.repo, state_root=self.root / 'state', pi=script)
        ident = planner.create('Investigate shutdown')['id']
        return planner, ident

    def rpc(self, *args, **kwargs):
        client = RPC(*args, **kwargs, shutdown_timeout=.2)
        self.addCleanup(lambda: RPC.close(client))
        return client

    def test_success_is_saved_only_after_clean_shutdown(self):
        planner, ident = self.planner('normal')
        with patch('pi_autowork.planning.RPC', self.rpc):
            self.assertEqual(planner.send(ident)['status'], 'ready')
        meta = planner.get(ident)
        self.assertEqual(meta['status'], 'ready')
        self.assertEqual(meta['turns'], 1)
        self.assertEqual(meta['shutdown'], {'returncode': 0, 'forced': False,
                         'readers_stopped': True, 'resources_closed': True, 'errors': []})
        self.assertEqual([row['role'] for row in planner.history(ident)], ['user', 'assistant'])

    def test_settlement_cannot_succeed_after_forced_or_nonzero_shutdown(self):
        for mode in ('settled_hung', 'nonzero'):
            with self.subTest(mode=mode):
                planner, ident = self.planner(mode)
                with patch('pi_autowork.planning.RPC', self.rpc):
                    with self.assertRaisesRegex(PlanningError, 'shutdown was not clean'):
                        planner.send(ident)
                meta = planner.get(ident)
                self.assertEqual(meta['status'], 'error')
                self.assertEqual(meta['turns'], 0)
                self.assertEqual(meta['shutdown']['returncode'], -9 if mode == 'settled_hung' else 7)
                self.assertEqual(meta['shutdown']['forced'], mode == 'settled_hung')
                self.assertEqual([row['role'] for row in planner.history(ident)], ['user'])
                self.assertNotIn(ident, planner._active)

    def test_incomplete_shutdown_cannot_stage_a_settled_proposal(self):
        planner, ident = self.planner('planner')
        original = RPC.close
        def incomplete(client, abort=False):
            outcome = original(client, abort=abort)
            return ShutdownOutcome(outcome.returncode, False, False, False)
        with patch('pi_autowork.planning.RPC', self.rpc), patch.object(RPC, 'close', incomplete):
            with self.assertRaisesRegex(PlanningError, 'shutdown was not clean'):
                planner.send(ident)
        meta = planner.get(ident)
        self.assertEqual(meta['status'], 'error')
        self.assertEqual(meta['turns'], 0)
        self.assertFalse(meta['shutdown']['readers_stopped'])
        self.assertFalse((Path(meta['worktree']) / 'docs/plans/proposed.md').exists())
        self.assertEqual([row['role'] for row in planner.history(ident)], ['user'])

    def test_missing_or_raised_close_outcome_is_persisted_even_on_turn_failure(self):
        original = RPC.close
        for mode in ('normal', 'missing_commands'):
            for raised in (False, True):
                with self.subTest(mode=mode, raised=raised):
                    planner, ident = self.planner(mode)
                    def close(client, abort=False):
                        original(client, abort=abort)
                        if raised:
                            raise OSError('private synthetic diagnostic')
                        return None  # Legacy/mock clients cannot attest shutdown.
                    with patch('pi_autowork.planning.RPC', self.rpc), patch.object(RPC, 'close', close):
                        with self.assertRaises(PlanningError):
                            planner.send(ident)
                    meta = planner.get(ident)
                    self.assertEqual(meta['status'], 'error')
                    self.assertEqual(meta['turns'], 0)
                    self.assertIn('shutdown', meta['last_error'])
                    self.assertEqual(meta['shutdown'], {'error': 'Pi RPC shutdown outcome unavailable'})
                    self.assertNotIn('private synthetic diagnostic', json.dumps(meta))
                    self.assertNotIn(ident, planner._active)


if __name__ == '__main__':
    unittest.main()
