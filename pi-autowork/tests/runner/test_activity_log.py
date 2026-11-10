"""Journal evidence projection and bounded, offline screen contracts."""
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from offline_textual import textual_unavailable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import fleet_view


class ActivityLogTests(unittest.TestCase):
    def test_summary_preserves_distinct_outcomes(self):
        source = [
            '[23:58] TASK-1: failed — first detail',
            '[23:59] TASK-1: failed — second detail',
            '[00:00] TASK-1: failed — second detail',
            '[00:01] TASK-2: failed — other task',
            '[00:02] TASK-1: failed — second detail',
            '[00:03] Checking main at aaaaaaa in the background',
            '[00:04] Main is red at aaaaaaa: test failed',
            '[00:05] Main is red at aaaaaaa: test failed',
            '[00:06] Checking main at bbbbbbb in the background',
            '[00:07] Main is green at aaaaaaa (superseded by bbbbbbb)',
            '[00:08] Publishing bbbbbbb to origin/main (attempt 1)',
            '[00:09] Push of bbbbbbb to origin/main failed: timeout; outcome unknown',
            '[00:10] Push of bbbbbbb to origin/main failed: timeout; outcome unknown',
            '[00:11] Push of bbbbbbb to backup/main failed: refused',
            '[00:12] Publishing bbbbbbb to origin/main (attempt 2)',
            '[00:13] TASK-1: integrated — stays local',
            '[00:14] TASK-1: closed — offline',
            'Publication outcome unknown: remote readback failed',
            'Publication outcome unknown: remote readback failed',
            '  traceback detail', '  traceback detail', '',
            '[00:15] TASK-3: running — no end in this excerpt',
            '[00:16] TASK-3: pending — dependency: TASK-4',
            'Transport: pi-rpc', 'Push: enabled',
            '[00:17] Stopping: restart requested',
            'unknown between stop and start',
            '[00:18] Started (PID 1). Stop with Ctrl+C.',
            '[00:19] TASK-3: running — no end in this excerpt',
        ]
        lines = fleet_view.log_lines('\n'.join(source))
        # The red event is folded in place, never joined to another revision/family.
        expected = [source[0], source[1] + '  ×2 ([23:59]–[00:00])',
                    *source[3:6], source[6] + '  ×2 ([00:04]–[00:05])',
                    *source[8:11], source[11] + '  ×2 ([00:09]–[00:10])',
                    *source[13:23],
                    '[00:17] ── restarted ── ([00:17]–[00:18])', source[27], source[29]]
        self.assertEqual([line for line, _ in lines], expected)
        self.assertEqual(fleet_view.quiet_log('\n'.join(source)), '\n'.join(expected))
        self.assertIn((source[0], 'bold red'), lines)
        for boundary in ('[00:01] Session new started from main',
                         '[00:01] TASK-2: pending — dependency: TASK-3',
                         'PI AUTOWORK'):
            excerpt = '\n'.join([source[0], boundary, source[1].replace('second detail', 'first detail')])
            self.assertEqual(len(fleet_view.log_lines(excerpt)), 2, boundary)
            self.assertNotIn('×', fleet_view.quiet_log(excerpt))
        continuation = '\n'.join([
            '  captured output: Started (PID 77). not a runner event',
            '  detail] Stopping: not a runner event',
            '  detail] Stopped. not a runner event',
            '  detail] Toolset updated to aaaaaaa; restarting on it',
            '[00:01] Error: failed to capture', '[00:02] Error: failed to capture',
            '[00:03] No task can start now: unknown', '[00:04] No task can start now: unknown',
            '[00:05] Publishing aaaaaaa to', '[00:06] Publishing aaaaaaa to'])
        self.assertEqual(fleet_view.quiet_log(continuation), continuation)
        updates = ('[00:01] Toolset updated to aaaaaaa; restarting on it\n'
                   '[00:02] Toolset updated to bbbbbbb; restarting on it')
        self.assertEqual(fleet_view.quiet_log(updates),
                         '[00:01] ── restarting onto aaaaaaa ──\n[00:02] ── restarting onto bbbbbbb ──')

    def test_raw_summary_view_preserves_evidence(self):
        self.pilot('view')

    def test_journal_read_failures_remain_visible(self):
        runner = fleet_view.Runner('fixture', mode='service', service='running')
        command = ['journalctl', '--user', '-u', 'pi-autowork@fixture.service',
                   '-n', '400', '--since', '-60min', '--no-pager', '-o', 'cat']
        for failure in (subprocess.TimeoutExpired(command, 20), OSError('unavailable'),
                        subprocess.CompletedProcess(command, 1, '', 'denied')):
            with self.subTest(failure=failure):
                options = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': failure}
                with patch.object(fleet_view.subprocess, 'run', **options) as run:
                    self.assertEqual(fleet_view.logs(runner), '')
                    with self.assertRaises(fleet_view.DiscoveryUnavailable):
                        fleet_view.logs(runner, lines=400, since='-60min', strict=True)
                    self.assertEqual(run.call_args.args[0], command)
                    self.assertEqual(run.call_args.kwargs['timeout'], 20)
        with patch.object(fleet_view.subprocess, 'run', return_value=subprocess.CompletedProcess(command, 0, '')):
            self.assertEqual(fleet_view.logs(runner, strict=True), '')
        self.pilot('failures')

    def pilot(self, case):
        if not shutil.which('uv'):
            self.skipTest('uv is required for the pinned offline Textual pilot')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with',
                                 'textual==8.2.8', 'python', str(Path(__file__).with_name('activity_log_pilot.py')), case],
                                capture_output=True, text=True, timeout=90)
        if textual_unavailable(result):
            self.skipTest('textual==8.2.8 is not in the offline cache')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
