"""Instruction contracts and real disposable Git examples, not model/cron qualification."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'skills/git-commit-push/references/worktree-closeout.md'
SWEEP = ROOT / 'skills/git-commit-push/scripts/worktree_sweep.py'


class WorktreeCloseoutTests(unittest.TestCase):
    def reference(self):
        self.assertTrue(REFERENCE.is_file(), 'Missing worktree closeout contract')
        return REFERENCE.read_text()

    def test_legacy_closeout_is_retained_but_not_an_orbi_entrypoint(self):
        self.assertIn('worktree-closeout.md', (ROOT / 'skills/shared/WORKTREE-ISOLATION.md').read_text())
        self.assertIn('Preserve task data, attempts,', (ROOT / 'README.md').read_text())

    def test_contract_preserves_live_and_unfinished_work(self):
        text = self.reference()
        for requirement in ('main', 'master', 'active', 'locked', 'ignored',
                            'unmerged', 'receipts', 'cleanup pending',
                            'no hard limit', 'No push', 'not a runtime guarantee'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)
        self.assertIn('requires an explicit existing `--closeout` helper', text)
        self.assertIn('no automatic deletion or unsafe Git fallback', text)

    def git(self, root, *args, check=True):
        return subprocess.run(['git', '-C', str(root), *args], check=check,
                              text=True, capture_output=True)

    def fixture(self, root, branch):
        canonical = root / 'canonical'
        canonical.mkdir()
        self.git(canonical, 'init', '-q', '-b', branch)
        self.git(canonical, 'config', 'user.name', 'Fixture')
        self.git(canonical, 'config', 'user.email', 'fixture@example.invalid')
        (canonical / '.gitignore').write_text('ignored-cache/\n')
        (canonical / 'base.txt').write_text('base\n')
        self.git(canonical, 'add', '.gitignore', 'base.txt')
        self.git(canonical, 'commit', '-qm', 'base')
        worktree = root / 'task worktree'
        self.git(canonical, 'worktree', 'add', '-q', '-b', 'task/example', str(worktree))
        (worktree / 'result.txt').write_text('verified fixture result\n')
        self.git(worktree, 'add', 'result.txt')
        self.git(worktree, 'commit', '-qm', 'task')
        commit = self.git(worktree, 'rev-parse', 'HEAD').stdout.strip()
        return canonical, worktree, commit

    def test_missing_helper_preserves_all_worktree_states_on_main_and_master(self):
        for branch in ('main', 'master'):
            for state in ('merged', 'unmerged', 'dirty', 'ignored', 'locked', 'wrong-target', 'moved-head'):
                with self.subTest(branch=branch, state=state), tempfile.TemporaryDirectory() as folder:
                    canonical, worktree, commit = self.fixture(Path(folder), branch)
                    if state != 'unmerged':
                        self.git(canonical, 'merge', '--ff-only', 'task/example')
                    if state == 'wrong-target':
                        self.git(canonical, 'switch', '-q', '-c', 'feature')
                    if state == 'locked':
                        self.git(canonical, 'worktree', 'lock', str(worktree))
                    if state == 'dirty':
                        (worktree / 'untracked.txt').write_text('preserve\n')
                    if state == 'ignored':
                        (worktree / 'ignored-cache').mkdir()
                        (worktree / 'ignored-cache/receipt.json').write_text('{}\n')
                    if state == 'moved-head':
                        (worktree / 'later.txt').write_text('not integrated\n')
                        self.git(worktree, 'add', 'later.txt')
                        self.git(worktree, 'commit', '-qm', 'later work')
                    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
                    env.update(CANONICAL=str(canonical), TASK_WORKTREE=str(worktree))
                    result = subprocess.run(
                        [sys.executable, str(SWEEP), str(canonical), '--remove'],
                        cwd=canonical, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn('explicit existing --closeout safety helper', result.stderr)
                    self.assertTrue(worktree.exists(), result.stdout)
                    self.assertTrue(canonical.is_dir())
                    expected = 'feature' if state == 'wrong-target' else branch
                    self.assertEqual(self.git(canonical, 'branch', '--show-current').stdout.strip(), expected)
                    listed = self.git(canonical, 'worktree', 'list', '--porcelain').stdout
                    self.assertIn(str(worktree), listed)


if __name__ == '__main__':
    unittest.main()
