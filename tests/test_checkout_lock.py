"""One interactive session writes a checkout at a time (TOOLSET-290-12)."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import checkout_lock

HOOK = Path(__file__).resolve().parents[1] / 'scripts/checkout_lock.py'


class CheckoutLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        for name in ('a.py', 'b.py'):
            (self.repo / name).write_text('x = 1\n')
        self.git('add', '.')
        self.commit('base')
        self.now = time.time()

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-C', str(cwd or self.repo), *args],
                              check=True, capture_output=True, text=True).stdout

    def submodule(self):
        child = Path(self.temp.name) / 'child'
        child.mkdir()
        self.git('init', '-q', '-b', 'main', cwd=child)
        for name in ('a.py', 'b.py'):
            (child / name).write_text('x = 1\n')
        self.git('add', '.', cwd=child)
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=f@example.invalid',
                 'commit', '-qm', 'child', cwd=child)
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(child), 'sub')
        self.commit('initialize submodule')
        return self.repo / 'sub'

    def commit(self, message):
        self.git('-c', 'user.name=F', '-c', 'user.email=f@example.invalid', 'commit', '-qam', message)

    def edit(self, session, name, after=0, tool='Edit', cwd=None):
        """The hook's verdict on ``session`` editing ``name``: '' when allowed, else its reason."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            checkout_lock.hook({'hook_event_name': 'PreToolUse', 'session_id': session, 'tool_name': tool,
                                'transcript_path': f'/t/{session}.jsonl', 'cwd': str(cwd or self.repo),
                                'tool_input': {'file_path': name}}, now=self.now + after)
        text = out.getvalue()
        return json.loads(text)['hookSpecificOutput']['permissionDecisionReason'] if text else ''

    def write(self, name, text='x = 2\n'):
        (self.repo / name).write_text(text)

    def test_a_second_session_is_denied_and_told_why(self):
        self.assertEqual(self.edit('S1', 'a.py'), '')
        self.write('a.py')
        reason = self.edit('S2', 'b.py', after=120)
        self.assertIn('S1', reason)
        self.assertIn('a.py', reason)
        self.assertIn('EnterWorktree', reason)
        self.assertEqual(self.edit('S1', 'b.py', after=130), '')  # the holder keeps writing
        self.assertEqual(checkout_lock.read(self.repo / '.git')['files'], ['a.py', 'b.py'])
        # Reads and other tools are never stopped.
        self.assertEqual(self.edit('S2', 'a.py', after=140, tool='Read'), '')

    def test_the_lock_passes_once_the_holder_is_clean(self):
        self.edit('S1', 'a.py')
        self.write('a.py')
        self.commit('S1 work')
        # Within the grace period the hook ran before S1's edit landed: still S1's.
        self.assertIn('S1', self.edit('S2', 'b.py', after=10))
        self.assertEqual(self.edit('S2', 'b.py', after=120), '')
        self.assertEqual(checkout_lock.read(self.repo / '.git')['session'], 'S2')

    def test_a_dirty_holder_is_never_released_automatically(self):
        self.edit('S1', 'a.py')
        self.write('a.py')
        self.assertIn('a.py', self.edit('S2', 'b.py', after=31 * 60))
        self.assertIn('a.py', self.edit('S2', 'b.py', after=24 * 3600))

    def test_release_names_the_dirty_files(self):
        self.edit('S1', 'new.py')
        self.write('new.py')  # untracked counts as uncommitted
        out = subprocess.run([sys.executable, str(HOOK), 'release', str(self.repo)],
                             capture_output=True, text=True, check=True).stdout
        self.assertIn('session S1', out)
        self.assertIn('these stay uncommitted: new.py', out)
        self.assertIsNone(checkout_lock.read(self.repo / '.git'))
        self.assertEqual(self.edit('S2', 'b.py', after=1), '')

    def test_the_holders_session_end_passes_the_lock(self):
        self.edit('S1', 'a.py')
        self.write('a.py')
        for session, held in (('S2', True), ('S1', False)):  # only the holder's end counts
            checkout_lock.hook({'hook_event_name': 'SessionEnd', 'session_id': session, 'cwd': str(self.repo)})
            self.assertEqual(checkout_lock.read(self.repo / '.git') is not None, held)

    def test_task_worktrees_are_not_locked(self):
        self.edit('S1', 'a.py')
        self.write('a.py')
        task = self.repo / '.worktrees' / 'claude-x'
        self.git('worktree', 'add', '-q', '--detach', str(task))
        self.assertEqual(self.edit('S2', str(task / 'b.py'), after=120, cwd=task), '')
        self.assertEqual(self.edit('S2', str(self.repo / '.worktrees' / 'scratch.txt'), after=120), '')
        self.assertEqual(checkout_lock.read(self.repo / '.git')['session'], 'S1')

    def test_submodule_contention_exemptions_and_owner_release(self):
        parent = self.repo
        self.edit('parent', 'a.py')
        self.repo = self.submodule()
        common = Path(self.git('rev-parse', '--path-format=absolute', '--git-common-dir').strip())
        self.assertEqual(common, parent / '.git' / 'modules' / 'sub')
        self.assertEqual(self.edit('S1', 'a.py'), '')
        self.write('a.py')
        self.assertIsNotNone(checkout_lock.read(common))
        reason = self.edit('S2', 'b.py', after=checkout_lock.GRACE + 1)
        self.assertIn('S1', reason)
        self.assertIn('a.py', reason)
        self.assertIn('EnterWorktree', reason)
        self.assertEqual(checkout_lock.read(common)['session'], 'S1')
        self.assertTrue((common / (checkout_lock.LOCK + '.lock')).is_file())
        self.assertEqual(checkout_lock.read(parent / '.git')['session'], 'parent')

        # A real linked worktree outside .worktrees must also remain exempt.
        task = Path(self.temp.name) / 'sub-linked'
        self.git('worktree', 'add', '-q', '--detach', str(task))
        self.assertEqual(self.edit('S2', 'b.py', cwd=task), '')
        self.assertEqual(self.edit('S2', '.worktrees/scratch.txt'), '')
        self.assertEqual(self.edit('S2', 'a.py', tool='Read'), '')
        self.assertEqual(self.edit('S1', 'b.py'), '')
        self.assertEqual(checkout_lock.read(common)['files'], ['a.py', 'b.py'])
        for session, held in (('S2', True), ('S1', False)):
            checkout_lock.hook({'hook_event_name': 'SessionEnd', 'session_id': session,
                                'cwd': str(self.repo)})
            self.assertEqual(checkout_lock.read(common) is not None, held)
        self.assertEqual((self.repo / 'a.py').read_text(), 'x = 2\n')
        self.assertEqual(checkout_lock.read(parent / '.git')['session'], 'parent')

        self.assertEqual(self.edit('S2', 'a.py'), '')
        self.commit('S2 work')
        self.assertIn('S2', self.edit('S3', 'b.py', after=10))
        self.assertEqual(self.edit('S3', 'b.py', after=checkout_lock.GRACE + 1), '')
        self.assertEqual(checkout_lock.read(common)['session'], 'S3')

    def test_submodule_hook_works_as_a_standalone_copy(self):
        parent = self.repo
        self.repo = self.submodule()
        common = Path(self.git('rev-parse', '--path-format=absolute', '--git-common-dir').strip())
        hooks = Path(self.temp.name) / 'hooks'
        hooks.mkdir()
        standalone = hooks / 'checkout-lock.py'
        standalone.write_bytes(HOOK.read_bytes())

        def run(*args, payload=None):
            result = subprocess.run([sys.executable, str(standalone), *args], cwd=self.repo,
                                    input=json.dumps(payload) if payload else None,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        payload = {'hook_event_name': 'PreToolUse', 'session_id': 'S1', 'tool_name': 'Write',
                   'cwd': str(self.repo), 'tool_input': {'file_path': 'a.py'}}
        self.assertEqual(run(payload=payload), '')
        self.write('a.py')
        self.assertIsNotNone(checkout_lock.read(common))
        record = checkout_lock.read(common)
        record['touched'] = time.time() - checkout_lock.GRACE - 1
        checkout_lock.write(common, record)
        payload.update(session_id='S2', tool_input={'file_path': 'b.py'})
        verdict = json.loads(run(payload=payload))['hookSpecificOutput']
        self.assertEqual(verdict['permissionDecision'], 'deny')
        for evidence in ('S1', 'a.py', 'EnterWorktree', 'release'):
            self.assertIn(evidence, verdict['permissionDecisionReason'])
        self.assertIn('held by session S1', run('status', str(self.repo)))
        released = run('release', str(self.repo))
        self.assertIn('these stay uncommitted: a.py', released)
        self.assertIsNone(checkout_lock.read(common))
        self.assertEqual((self.repo / 'a.py').read_text(), 'x = 2\n')
        self.assertEqual(run(payload=payload), '')
        self.assertEqual(checkout_lock.read(common)['session'], 'S2')
        self.assertIsNone(checkout_lock.read(parent / '.git'))

    def test_paths_outside_git_are_left_alone(self):
        outside = Path(self.temp.name) / 'notes.md'
        self.assertEqual(self.edit('S1', str(outside), cwd=self.temp.name), '')
        self.assertEqual(self.edit('S2', str(outside), cwd=self.temp.name), '')

    def test_the_hook_reads_its_payload_from_stdin(self):
        payload = {'hook_event_name': 'PreToolUse', 'session_id': 'S1', 'tool_name': 'Write',
                   'cwd': str(self.repo), 'tool_input': {'file_path': 'a.py'}}
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                                capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, ''))
        status = subprocess.run([sys.executable, str(HOOK), 'status', str(self.repo)],
                                capture_output=True, text=True, check=True).stdout
        self.assertIn('held by session S1', status)


if __name__ == '__main__':
    unittest.main()
