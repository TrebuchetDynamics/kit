"""Selected-release screen ownership and host routes, using pinned rendered Textual."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests'))
from src_fixture import copy_sources


class TuiArchitectureTests(unittest.TestCase):
    def probe(self, body):
        with tempfile.TemporaryDirectory() as folder:
            selected = copy_sources(Path(folder) / 'selected release')
            code = (f'import sys\nfrom pathlib import Path\nroot = Path({str(selected)!r})\n'
                    "sys.path.insert(0, str(root / 'pi-autowork'))\n" + body)
            result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project',
                                     '--with', 'textual==8.2.8', 'python', '-B', '-c', code],
                                    cwd=folder, env=dict(os.environ, PYTHONPATH=str(ROOT / 'pi-autowork')),
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_screens_have_one_owner(self):
        self.probe('''import ast, importlib, importlib.util
from pi_autowork import tui_tasks, tui_common, tui
owners = {tui_tasks: ('TasksScreen', 'TaskScreen', 'DecisionScreen', 'NewTask',
                     'PickSection', 'CommitEdits', 'TextPrompt', 'pending_edits'),
          tui_common: ('ReadScreen', 'MenuBar', 'read_input', 'hotkeys', 'publish_text', 'action_text')}
for owner, names in owners.items():
    assert Path(owner.__file__) == root / 'src/pi_autowork' / (owner.__name__.split('.')[-1] + '.py')
    assert not (root / 'pi-autowork/pi_autowork' / Path(owner.__file__).name).exists()
    tree = ast.parse(Path(owner.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert all(alias.name not in ('FleetApp', 'tui', 'pi_autowork.tui') for alias in node.names)
            assert getattr(node, 'module', None) not in ('tui', 'pi_autowork.tui')
    for name in names:
        value = getattr(owner, name)
        assert getattr(tui, name) is value
        assert value.__module__ == owner.__name__
spec = importlib.util.spec_from_file_location('pi_autowork.tui', root / 'pi-autowork/pi_autowork/tui.py')
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)
assert sys.modules[spec.name] is not adapter
assert Path(sys.modules[spec.name].__file__).resolve() == Path(tui.__file__).resolve()
for name in ('tui_common', 'tui_tasks'):
    path = root / 'src/pi_autowork' / (name + '.py')
    original = path.read_bytes()
    path.unlink()
    sys.modules.pop('pi_autowork.' + name)
    try:
        importlib.import_module('pi_autowork.' + name)
    except (ImportError, ValueError):
        pass
    else:
        raise AssertionError('missing selected owner borrowed another release')
    foreign = root.parent / (name + '.py')
    foreign.write_bytes(original)
    path.symlink_to(foreign)
    try:
        importlib.import_module('pi_autowork.' + name)
    except (ImportError, ValueError):
        pass
    else:
        raise AssertionError('foreign owner escaped selected release')
    path.unlink()
    path.write_bytes(original)
''')

    def test_extracted_screens_keep_host_routes(self):
        self.probe(f'''sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
import asyncio
from test_tui_controls import controls_pilot
# Existing rendered assertions cover exactly-once decision/confirmation callbacks,
# compact forms and view-only refusals through the extracted screen identities.
asyncio.run(controls_pilot('answers'))
asyncio.run(controls_pilot('dialogs'))
''')

    def test_screen_modules_participate_in_reload_stamp(self):
        self.probe('''import asyncio, os
from unittest.mock import patch
from types import SimpleNamespace
from pi_autowork import tui, tui_common, tui_tasks
from pi_autowork.tui_reads import ReadCoordinator
for owner in (tui_common, tui_tasks):
    path = Path(owner.__file__)
    stamp = tui.code_stamp() + 10
    os.utime(path, (stamp, stamp))
    assert tui.code_stamp() == stamp
# Exercise the real reload callback with app-owned reader and screen/action gates.
async def check():
    class Host:
        read = tui.FleetApp.read
        reload_if_updated = tui.FleetApp.reload_if_updated
        read_done = tui.FleetApp.read_done
    host = Host()
    host.is_running = True
    host.read_epoch = 0
    host.reads = ReadCoordinator()
    host.reader = host.reads.owner(host.read_done)
    host.screen_stack = [object(), object()]
    host.workers = []
    host.code = -1
    exits = []
    host.exit = exits.append
    try:
        await host.reload_if_updated().wait()
        assert not exits
        host.screen_stack.pop()
        host.workers = [SimpleNamespace(is_running=True)]
        await host.reload_if_updated().wait()
        assert not exits
        host.workers = []
        await host.reload_if_updated().wait()
        assert exits == ['reload']
    finally:
        host.reads.close()
        host.reads.executor.shutdown(wait=True)
asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
