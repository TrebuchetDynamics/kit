"""A repository that changes under a running coordinator is a deliberate stop."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import release  # noqa: E402
from pi_autowork.coordinator import Coordinator, Finish  # noqa: E402


class RepositoryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'project'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('commit', '--allow-empty', '-qm', 'base')
        self.identity = release.repository_identity(self.repo, clean=True)
        self.assertIsNotNone(self.identity)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def runner(self):
        runner = Coordinator.__new__(Coordinator)
        runner.repo = str(self.repo)
        runner.cfg = {'repo': str(self.repo), 'git_common': self.identity[1]}
        runner.state = self.root / 'state'
        runner.state.mkdir()
        runner.stop = False
        runner.maintainer_job = None
        runner.integration = None
        runner.prefix_landing = None
        runner.train = None
        runner.snapshot = None
        return runner

    def test_healthy_repository_has_no_problem(self):
        self.assertEqual(self.runner().repository_problem(), '')

    def test_a_checkout_marked_bare_stops_for_attention(self):
        self.git('config', 'core.bare', 'true')
        runner = self.runner()
        problem = runner.repository_problem()
        self.assertIn('core.bare', problem)
        with self.assertRaises(Finish) as stopped:
            runner.ensure_repository()
        self.assertEqual(stopped.exception.code, 4)
        self.assertIn('Stopped before any merge or push', stopped.exception.text)
        self.assertTrue(runner.stop)

    def test_a_replaced_repository_stops_for_attention(self):
        self.git('config', 'core.bare', 'true')
        # The runner's configured checkout is still a directory, but not a work tree.
        self.assertTrue(self.repo.is_dir())
        with self.assertRaises(Finish) as stopped:
            self.runner().ensure_repository()
        self.assertEqual(stopped.exception.code, 4)
        self.assertIn('no longer a usable Git work tree', stopped.exception.text)

    def test_an_unrelated_repository_is_an_identity_change(self):
        other = self.root / 'other'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(other)], check=True)
        subprocess.run(['git', '-C', str(other), '-c', 'user.name=F',
                        '-c', 'user.email=f@example.invalid', 'commit', '--allow-empty', '-qm', 'base'],
                       check=True)
        runner = self.runner()
        runner.repo = str(other)
        self.assertIn('Repository identity changed', runner.repository_problem())


if __name__ == '__main__':
    unittest.main()
