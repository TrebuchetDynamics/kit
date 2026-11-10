"""Public runner adapters select real, same-release source owners."""
import sys as _sys
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parent),
                 str(_Path(__file__).resolve().parents[3] / 'tests'),
                 str(_Path(__file__).resolve().parents[1]),
                 str(_Path(__file__).resolve().parents[2]),
                 str(_Path(__file__).resolve().parents[2] / 'engine')]
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src_fixture import copy_sources

ROOT = Path(__file__).resolve().parents[3]


class SrcEntrypointTests(unittest.TestCase):
    def test_component_owns_selected_sources(self):
        self.assertTrue((ROOT / 'pi-autowork/src/pi_autowork/engine/task_store.py').is_file())
        self.assertFalse((ROOT / 'src').exists())
        result = subprocess.run(
            [sys.executable, '-B', '-m', 'unittest',
             'pi-autowork/tests/runner/test_main_check.py', '-k', 'test_flutter_failures'],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 1 test', result.stderr)

    def test_legacy_and_canonical_engine_import_orders_keep_actual_owner_identity(self):
        temporary = tempfile.TemporaryDirectory(prefix='pinned release ')
        self.addCleanup(temporary.cleanup)
        selected = copy_sources(Path(temporary.name) / 'selected')
        poison = Path(temporary.name) / 'unrelated cwd'
        (poison / 'pi_autowork').mkdir(parents=True)
        for name in ('pi_autowork/__init__.py', 'task_store.py', 'command.py'):
            (poison / name).write_text('raise AssertionError("foreign source")\n')
        for first in ('task_store', 'pi_autowork.engine.task_store'):
            with self.subTest(first=first):
                code = f'''import sys, importlib, subprocess
from pathlib import Path
root = Path({str(selected)!r})
sys.path[:0] = [str(root / 'pi-autowork/engine'), str(root / 'pi-autowork')]
a = importlib.import_module({first!r})
b = importlib.import_module('pi_autowork.engine.task_store')
assert a is b is importlib.import_module('task_store')
assert Path(a.__file__) == root / 'pi-autowork/src/pi_autowork/engine/task_store.py'
sys.path.insert(0, str(Path.cwd()))  # late imports still belong to the activated release
from pi_autowork import command, task_snapshot, fleet_view
assert Path(command.__file__) == root / 'pi-autowork/src/pi_autowork/command.py'
assert fleet_view.TaskRow is task_snapshot.TaskRow
from pi_autowork import workspaces
from pi_autowork.engine import worktree_paths
original = worktree_paths.worktree_path
try:
    worktree_paths.worktree_path = lambda repo, name: (repo, name)
    assert workspaces.task_path(root, 'repository', 'task') == ('repository', 'task')
finally:
    worktree_paths.worktree_path = original
from pi_autowork import release
from pi_autowork.engine import parallel_state
bridge = (root / release.STATE_FILE).read_text()
for name in ('STATE_SCHEMA', 'STATE_SCHEMA_READS'):
    assert release.schema(bridge, name, None) == getattr(parallel_state, name)
child = subprocess.run([sys.executable, '-B', str(root / 'pi-autowork/pi_autowork/command.py'),
                        'capabilities'], text=True, capture_output=True, timeout=15)
assert child.returncode == 0, child.stderr
import json
assert Path(json.loads(child.stdout)['toolset']) == root
'''
                result = subprocess.run([sys.executable, '-B', '-c', code], cwd=poison,
                                        env=dict(os.environ, PYTHONPATH=str(poison)),
                                        text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_spaced_release_commands_and_missing_owner_never_borrow_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = copy_sources(Path(folder) / 'selected release')
            command = root / 'pi-autowork/pi_autowork/command.py'
            env = dict(os.environ, PYTHONPATH=str(ROOT / 'pi-autowork'))
            args = [sys.executable, '-B', str(command), 'capabilities']
            commands = [(args, env),
                        ([sys.executable, '-B', '-m', 'pi_autowork.command', 'capabilities'],
                         dict(env, PYTHONPATH=str(root / 'pi-autowork')))]
            for argv, environment in commands:
                result = subprocess.run(argv, cwd=folder, env=environment,
                                        text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('prepare_api', result.stdout)
            (root / 'pi-autowork/src/pi_autowork/command.py').unlink()
            for argv, environment in commands:
                result = subprocess.run(argv, cwd=folder, env=environment,
                                        text=True, capture_output=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('missing selected-release source', result.stderr)


if __name__ == '__main__':
    unittest.main()
