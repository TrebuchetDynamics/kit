"""Task record behavior: missing Touches is a draft; the shared rule has one home."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / 'pi-autowork/pi_autowork/command.py'
FIXTURE = ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store'
PROTOCOL = ROOT / 'skills/shared/RESEARCH-PLAN.md'


class TaskTouchesContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        shutil.copytree(FIXTURE, self.repo)
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', *args],
                       check=True, capture_output=True, text=True)

    def tasks(self, *args):
        result = subprocess.run([sys.executable, str(COMMAND), 'tasks', *args],
                                cwd=self.repo, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def add(self, title, touches=None):
        args = ['add', '--goal', 'G-1', '--title', title, '--short', title,
                '--scope', 'Bounded task', '--acceptance', 'Behavior is proved',
                '--checks', 'true', '--kind', 'implementation', '--ownership', 'worker']
        if touches is not None:
            args += ['--touches', touches]
        return self.tasks(*args).split()[-1]

    def test_missing_touches_is_a_draft_and_a_bounded_write_set_is_runnable(self):
        missing = json.loads(self.tasks('show', self.add('No write set'), '--worktree'))
        self.assertTrue(missing['draft'])
        self.assertIn('touches', missing['missing_fields'])

        bounded = json.loads(self.tasks('show', self.add('Bounded write set', 'src/'), '--worktree'))
        self.assertFalse(bounded['draft'])
        self.assertEqual(bounded['touches'], ['src/'])

    def test_the_shared_protocol_owns_the_rule_once(self):
        text = ' '.join(PROTOCOL.read_text().split())
        for requirement in (
                'Every executable issue has an observable outcome',
                'bounded scope and exclusions',
                'Native GitHub dependencies own ordering'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)
        self.assertNotIn('Every executable task you create or rewrite gets `touches`', text)


if __name__ == '__main__':
    unittest.main()
