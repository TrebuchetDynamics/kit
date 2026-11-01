"""Worktree sweep: classify every worktree, merge only finished clean ones, keep the rest."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/git-commit-push/scripts/worktree_sweep.py'

ENV = {**os.environ, 'GIT_AUTHOR_NAME': 'fixture', 'GIT_AUTHOR_EMAIL': 'f@example.invalid',
       'GIT_COMMITTER_NAME': 'fixture', 'GIT_COMMITTER_EMAIL': 'f@example.invalid',
       'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null'}


def run(*args, cwd=None, check=True):
    done = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True)
    if check and done.returncode:
        raise AssertionError(f'{" ".join(args)} failed: {done.stderr or done.stdout}')
    return done


def git(repo, *args, check=True):
    return run('git', '-C', str(repo), *args, check=check).stdout.strip()


class WorktreeSweepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-q', '-b', 'main')
        (self.repo / 'app.txt').write_text('base\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-q', '-m', 'base')
        self.base = git(self.repo, 'rev-parse', 'HEAD')

    def worktree(self, name, *, commit=None, dirty=False, lock=False):
        path = self.repo / '.worktrees' / name
        git(self.repo, 'worktree', 'add', '-q', '-b', f'autowork/{name}', str(path))
        if commit:
            (path / f'{name}.txt').write_text(f'{name}\n')
            git(path, 'add', '.')
            git(path, 'commit', '-q', '-m', commit)
        if dirty:
            (path / 'app.txt').write_text('edited but uncommitted\n')
        if lock:
            git(self.repo, 'worktree', 'lock', str(path), '--reason', 'fixture lock')
        return path

    def sweep(self, *args, check=True):
        done = run(sys.executable, str(SCRIPT), str(self.repo), '--idle-minutes', '0', *args, check=check)
        return done

    def inventory(self):
        return {entry['path'].split('/')[-1]: entry
                for entry in json.loads(self.sweep('--json').stdout.split('\n\n')[0])}

    def test_classification_covers_every_state_without_changing_anything(self):
        self.worktree('finished')
        self.worktree('ahead', commit='work in progress')
        self.worktree('ahead-dirty', commit='committed then edited', dirty=True)
        self.worktree('held', commit='locked branch', lock=True)
        before = git(self.repo, 'rev-parse', 'HEAD')
        states = {name: entry['state'] for name, entry in self.inventory().items()}
        self.assertEqual(states, {'finished': 'merged', 'ahead': 'unmerged-clean',
                                  'ahead-dirty': 'unmerged-dirty', 'held': 'locked'})
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), before)

    def test_apply_merges_only_finished_clean_work_and_leaves_the_rest(self):
        self.worktree('finished')
        ahead = self.worktree('ahead', commit='add ahead file')
        dirty = self.worktree('ahead-dirty', commit='committed then edited', dirty=True)
        self.sweep('--apply')
        self.assertEqual((self.repo / 'ahead.txt').read_text(), 'ahead\n')
        self.assertEqual(git(self.repo, 'rev-list', '--count', f'{self.base}..main'), '2')
        self.assertEqual(git(dirty, 'status', '--porcelain'), 'M app.txt')
        self.assertEqual((dirty / 'app.txt').read_text(), 'edited but uncommitted\n')
        self.assertTrue(ahead.is_dir(), 'a merged worktree stays until it is closed out')

    def test_a_conflict_aborts_that_merge_and_keeps_the_other_worktrees(self):
        self.worktree('clash', commit='change app')
        (self.repo / '.worktrees/clash/app.txt').write_text('branch side\n')
        git(self.repo / '.worktrees/clash', 'commit', '-qam', 'branch side')
        clean = self.worktree('clean', commit='independent file')
        (self.repo / 'app.txt').write_text('main side\n')
        git(self.repo, 'commit', '-qam', 'main side')
        done = self.sweep('--apply', check=False)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn('conflict', done.stdout)
        self.assertEqual((self.repo / 'clean.txt').read_text(), 'clean\n')
        self.assertFalse((self.repo / '.git' / 'MERGE_HEAD').exists())
        self.assertTrue(clean.is_dir())

    def test_it_refuses_to_merge_over_a_dirty_canonical_checkout(self):
        self.worktree('ahead', commit='pending work')
        (self.repo / 'app.txt').write_text('uncommitted\n')
        done = self.sweep('--apply', check=False)
        self.assertEqual(done.returncode, 1 if hasattr(done, 'returncode') else 1, done.stderr)
        self.assertIn('refusing', done.stderr + done.stdout)

    def test_it_refuses_when_the_canonical_checkout_is_on_another_branch(self):
        self.worktree('ahead', commit='pending work')
        git(self.repo, 'checkout', '-q', '-b', 'side')
        done = self.sweep('--apply', '--base', 'main', check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('refusing', done.stderr + done.stdout)

    def test_a_recently_active_worktree_is_skipped_until_it_is_idle(self):
        ahead = self.worktree('ahead', commit='in flight')
        done = run(sys.executable, str(SCRIPT), str(self.repo), '--apply', '--idle-minutes', '30',
                   '--json', check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        entries = json.loads(done.stdout.split('\n\n')[0])
        [entry] = [e for e in entries if e['path'].endswith('ahead')]
        self.assertEqual(entry['result'], 'skipped')
        self.assertIn('active within 30 min', entry['note'])
        self.assertFalse((self.repo / 'ahead.txt').exists())
        self.assertTrue(ahead.is_dir())


if __name__ == '__main__':
    unittest.main()
