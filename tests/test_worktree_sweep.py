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
        git(self.repo, 'worktree', 'add', '-q', '-b', f'delivery/{name}', str(path))
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

    def inventory(self, *args):
        return {entry['path'].split('/')[-1]: entry
                for entry in json.loads(self.sweep('--json', *args).stdout.split('\n\n')[0])}

    def recording_closeout(self):
        helper = Path(self.tmp.name) / 'closeout.py'
        marker = Path(self.tmp.name) / 'seen'
        helper.write_text(
            'import pathlib, sys\n'
            f'with pathlib.Path({str(marker)!r}).open("a") as log:\n'
            '    print(sys.argv[3], file=log)\n')
        return str(helper), marker

    def test_remove_without_explicit_safety_helper_refuses_before_merging(self):
        ahead = self.worktree('ahead', commit='pending work')
        done = self.sweep('--apply', '--remove', check=False)
        self.assertEqual(done.returncode, 2)
        self.assertIn('explicit existing --closeout safety helper', done.stderr)
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)
        self.assertTrue(ahead.is_dir())

    def test_missing_closeout_refuses_without_deleting_merged_worktree(self):
        finished = self.worktree('finished')
        done = self.sweep('--remove', '--closeout', str(self.repo / 'missing.py'),
                          check=False)
        self.assertEqual(done.returncode, 2)
        self.assertTrue(finished.is_dir())

    def test_explicit_closeout_receives_only_eligible_candidates(self):
        finished = self.worktree('finished')
        gitdir = git(finished, 'rev-parse', '--absolute-git-dir')
        os.utime(gitdir, (1, 1))
        self.worktree('ahead-dirty', commit='unfinished work', dirty=True)
        helper, marker = self.recording_closeout()
        self.sweep('--remove', '--closeout', helper, '--idle-minutes', '30')
        self.assertEqual(marker.read_text().splitlines(), [str(finished)])
        self.assertTrue(finished.is_dir(), 'only the explicit helper may remove it')

    def test_remove_keeps_dirty_merged_worktrees(self):
        modified = self.worktree('modified', dirty=True) / 'app.txt'
        untracked = self.worktree('untracked') / 'draft.txt'
        untracked.write_text('untracked work\n')
        helper, marker = self.recording_closeout()

        entries = self.inventory('--remove', '--closeout', helper)

        self.assertFalse(marker.exists(), 'closeout must not receive any dirty worktree')
        for name in ('modified', 'untracked'):
            with self.subTest(worktree=name):
                entry = entries[name]
                self.assertEqual(entry['state'], 'merged')
                self.assertEqual(entry['closed'], 'kept')
                self.assertIn('dirty', entry['note'])
        self.assertEqual(modified.read_text(), 'edited but uncommitted\n')
        self.assertEqual(untracked.read_text(), 'untracked work\n')

    def test_remove_keeps_recently_active_merged_worktree(self):
        active = self.worktree('active')
        helper, marker = self.recording_closeout()

        entry = self.inventory('--remove', '--closeout', helper, '--idle-minutes', '30')['active']

        self.assertFalse(marker.exists(), 'closeout must not receive the active worktree')
        self.assertEqual(entry['state'], 'merged')
        self.assertEqual(entry['closed'], 'kept')
        self.assertIn('active within 30 min', entry['note'])
        self.assertTrue(active.is_dir())

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

    def test_apply_refuses_a_linked_worktree_before_merging(self):
        linked = self.worktree('linked')
        candidate = self.worktree('candidate')
        (linked / 'app.txt').write_text('linked side\n')
        git(linked, 'commit', '-qam', 'linked side')
        (candidate / 'app.txt').write_text('candidate side\n')
        git(candidate, 'commit', '-qam', 'candidate side')
        before = git(linked, 'rev-parse', 'HEAD')

        done = run(sys.executable, str(SCRIPT), str(linked), '--apply',
                   '--idle-minutes', '0', check=False)

        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(git(linked, 'rev-parse', 'HEAD'), before)
        self.assertEqual(git(linked, 'ls-files', '--unmerged'), '', done.stdout)
        self.assertIn(f'canonical checkout: {self.repo.resolve()}', done.stderr)

    def test_a_conflict_aborts_that_merge_and_keeps_the_other_worktrees(self):
        self.worktree('clash', commit='change app')
        (self.repo / '.worktrees/clash/app.txt').write_text('branch side\n')
        git(self.repo / '.worktrees/clash', 'commit', '-qam', 'branch side')
        clean = self.worktree('clean', commit='independent file')
        (self.repo / 'app.txt').write_text('main side\n')
        git(self.repo, 'commit', '-qam', 'main side')
        done = self.sweep('--apply', check=False)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn('-> conflict', done.stdout)
        self.assertEqual((self.repo / 'clean.txt').read_text(), 'clean\n')
        self.assertFalse((self.repo / git(self.repo, 'rev-parse', '--git-path', 'MERGE_HEAD')).exists())
        self.assertTrue(clean.is_dir())

    def test_it_refuses_when_a_merge_is_already_in_progress(self):
        candidate = self.worktree('candidate')
        git(candidate, 'commit', '-qm', 'empty change', '--allow-empty')
        git(self.repo, 'merge', '--no-ff', '--no-commit', 'delivery/candidate')
        # Nothing is staged, so only the merge-state check can catch this merge.
        self.assertEqual(git(self.repo, 'status', '--porcelain', '--untracked-files=no'), '')
        merge_head = git(self.repo, 'rev-parse', 'MERGE_HEAD')

        done = self.sweep('--apply', check=False)

        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn('a merge is already in progress in the canonical checkout', done.stderr)
        self.assertEqual(git(self.repo, 'rev-parse', 'MERGE_HEAD'), merge_head)
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)

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
