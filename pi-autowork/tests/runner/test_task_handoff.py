"""Decision handoff is committed-source evidence, not selection or live authority."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import task_commands as commands


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        shutil.copytree(ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store', self.repo)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        commands.cmd_place(self.repo, 'T-1', 'Needs decision')
        commands.cmd_commit(self.repo)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def report(self):
        return commands.cmd_handoff(self.repo)

    def test_unanswered_saved_committed_and_deferred_are_distinct(self):
        report = self.report()
        self.assertEqual(report['handoff']['decisions'][0]['state'], 'answer_required')
        head = self.git('rev-parse', 'HEAD')
        commands.cmd_decide(self.repo, 'T-1', 'Choose the offline option', section='Now')
        report = self.report()
        row, = report['handoff']['decisions']
        self.assertEqual((row['state'], row['next_action']), ('pending_commit', 'review_commit'))
        self.assertEqual((row['committed_section'], row['saved_section']), ('Needs decision', 'Now'))
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn('do not ask again', report['lifecycle']['message'])
        self.assertFalse(report['handoff']['execution_evaluated'])
        self.assertEqual(report['handoff']['workspace'], str(self.repo.resolve()))
        self.assertEqual(report['handoff']['committed_revision'], head.strip())
        committed = commands.cmd_commit(self.repo, expected=report['pending_revision'])
        self.assertEqual(committed['handoff']['decisions'][0]['state'], 'committed')
        self.assertEqual(self.report()['handoff']['decisions'][0]['state'], 'committed')
        commands.cmd_decide(self.repo, 'T-1', 'Not available yet', section='Needs decision')
        report = self.report()
        self.assertEqual(report['handoff']['decisions'][0]['state'], 'pending_commit')
        commands.cmd_commit(self.repo, expected=report['pending_revision'])
        self.assertEqual(self.report()['handoff']['decisions'][0]['state'], 'deferred')

    def test_unrelated_edits_do_not_count_as_a_new_answer(self):
        commands.cmd_field(self.repo, 'T-1', 'title', 'New wording')
        row, = self.report()['handoff']['decisions']
        self.assertEqual((row['state'], row['next_action']), ('pending_edit', 'review_commit'))
        self.assertNotIn('do not ask again', self.report()['lifecycle']['message'])

    def test_preview_preserves_index_refs_and_objects_and_does_not_grant_authority(self):
        commands.cmd_decide(self.repo, 'T-1', 'yes', section='Now')
        staged = self.repo / 'unrelated.txt'
        staged.write_text('keep staged\n')
        self.git('add', 'unrelated.txt')
        before = (self.git('write-tree'), self.git('show-ref'), self.git('count-objects', '-v'))
        report = self.report()
        self.assertEqual(before, (self.git('write-tree'), self.git('show-ref'), self.git('count-objects', '-v')))
        row, = report['handoff']['decisions']
        self.assertNotEqual(row['committed_record_revision'], row['saved_record_revision'])
        self.assertEqual(len(report['pending_revision']), 64)
        record = commands.cmd_show(self.repo, 'T-1', worktree=True)
        self.assertEqual(record['status'], 'open')
        self.assertEqual(record['live'], 'denied')
        self.assertIn('not runner acceptance', report['handoff']['message'])

    def test_stale_handoff_requires_fresh_review(self):
        commands.cmd_decide(self.repo, 'T-1', 'First answer', section='Now')
        report = self.report()
        commands.cmd_decide(self.repo, 'T-1', 'Changed answer')
        with self.assertRaisesRegex(commands.CommandError, 'changed'):
            commands.cmd_commit(self.repo, expected=report['pending_revision'])

    def test_commit_result_reports_captured_bytes_not_a_later_editor_change(self):
        commands.cmd_decide(self.repo, 'T-1', 'Reviewed answer', section='Now')
        preview = self.report()
        reviewed = preview['handoff']['decisions'][0]['saved_record_revision']
        path = self.repo / 'tasks/items/T-1.md'
        original_git = commands._git
        def racing_git(repo, *args, **kwargs):
            if args and args[0] == 'commit':
                path.write_text(path.read_text().replace('Reviewed answer', 'Later editor answer'))
            return original_git(repo, *args, **kwargs)
        with patch.object(commands, '_git', side_effect=racing_git):
            result = commands.cmd_commit(self.repo, expected=preview['pending_revision'])
        row, = result['handoff']['decisions']
        self.assertEqual((row['state'], row['saved_record_revision']), ('committed', reviewed))
        self.assertEqual(result['handoff']['committed_revision'], result['commit'])
        pending = self.report()['handoff']['decisions'][0]
        self.assertEqual(pending['state'], 'pending_commit')
        self.assertNotEqual(pending['saved_record_revision'], reviewed)

    def test_an_undated_note_is_not_reported_as_an_established_deferral(self):
        commands.cmd_field(self.repo, 'T-1', 'Owner decision', 'Not available yet')
        commands.cmd_commit(self.repo)
        row, = self.report()['handoff']['decisions']
        self.assertEqual(row['state'], 'answer_required')

    def test_read_commands_refuse_interrupted_recovery_without_mutation(self):
        path = self.repo / 'tasks/items/T-1.md'
        before = path.read_bytes()
        after = before + b'\n- Partial edit: kept for explicit recovery\n'
        path.write_bytes(after)
        journal = Path(self.git('rev-parse', '--absolute-git-dir').strip()) / 'autowork-tasks.transaction'
        data = json.dumps([['tasks/items/T-1.md', before.hex(), after.hex()]])
        # Simulate an interrupted external write after this reader already holds
        # the lock, so nested access must enforce the same non-recovery rule.
        with patch.object(commands, '_undo', side_effect=AssertionError('read attempted recovery')):
            with commands.locked(self.repo, recover=False):
                journal.write_text(data)
                for read in (self.report, lambda: commands.cmd_commit(self.repo, dry_run=True)):
                    with self.assertRaisesRegex(commands.CommandError, 'explicit recovery'):
                        read()
                    self.assertEqual(path.read_bytes(), after)
                    self.assertEqual(journal.read_text(), data)
            for read in (self.report, lambda: commands.cmd_commit(self.repo, dry_run=True)):
                with self.assertRaisesRegex(commands.CommandError, 'explicit recovery'):
                    read()
        for args in (['handoff'], ['commit', '--dry-run']):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(ROOT / 'pi-autowork/pi_autowork/command.py'),
                                         'tasks', *args, str(self.repo)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('explicit recovery', result.stderr)
                self.assertEqual(path.read_bytes(), after)
                self.assertEqual(journal.read_text(), data)

    def test_valid_pending_store_can_repair_an_invalid_committed_baseline(self):
        path = self.repo / 'tasks/items/T-1.md'
        valid = path.read_bytes()
        path.write_text('invalid committed record\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'broken baseline')
        clean = self.report()
        self.assertEqual(clean['lifecycle']['state'], 'unknown')
        self.assertFalse(clean['handoff']['committed_inventory_available'])
        path.write_bytes(valid)
        report = self.report()
        self.assertFalse(report['handoff']['committed_inventory_available'])
        self.assertTrue(report['handoff']['baseline_error'])
        self.assertEqual(report['handoff']['decisions'][0]['state'], 'pending_edit')
        result = commands.cmd_commit(self.repo, expected=report['pending_revision'])
        self.assertEqual(result['lifecycle']['state'], 'committed')
        self.assertTrue(self.report()['handoff']['committed_inventory_available'])

    def test_first_store_can_be_committed_without_a_prior_store(self):
        self.git('rm', '-qr', '--cached', 'tasks')
        self.git('commit', '-qm', 'no committed store')
        report = self.report()
        self.assertFalse(report['handoff']['committed_inventory_available'])
        result = commands.cmd_commit(self.repo, expected=report['pending_revision'])
        self.assertEqual(result['lifecycle']['state'], 'committed')
        self.assertTrue(self.report()['handoff']['committed_inventory_available'])

    def test_invalid_store_is_not_reported_as_clean(self):
        (self.repo / 'tasks/items/T-1.md').write_text('not a task record\n')
        with self.assertRaises(ValueError):
            self.report()

    def test_handoff_is_a_read_command_not_an_implicit_commit(self):
        parser = argparse.ArgumentParser()
        commands.add_parser(parser.add_subparsers(dest='command'))
        args = parser.parse_args(['tasks', 'handoff', str(self.repo)])
        self.assertEqual(args.verb, 'handoff')
        self.assertNotIn('handoff', commands.WRITES)
        head = self.git('rev-parse', 'HEAD')
        self.assertIsInstance(commands._run(args, self.repo)['handoff'], dict)
        output = subprocess.check_output([sys.executable, str(ROOT / 'pi-autowork/pi_autowork/command.py'),
                                          'tasks', 'handoff', str(self.repo)], text=True)
        self.assertIn('handoff', json.loads(output))
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)


if __name__ == '__main__':
    unittest.main()
