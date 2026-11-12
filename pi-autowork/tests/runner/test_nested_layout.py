"""An invalid selected source release must not replace a running coordinator."""
from pathlib import Path
import sys as _sys
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parent),
                 str(_Path(__file__).resolve().parents[3] / 'tests'),
                 str(_Path(__file__).resolve().parents[1]),
                 str(_Path(__file__).resolve().parents[2]),
                 str(_Path(__file__).resolve().parents[2] / 'engine')]
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2]),
                str(Path(__file__).resolve().parents[3] / 'tests')]
from pi_autowork import coordinator
from src_fixture import copy_sources


class NestedLayoutTests(unittest.TestCase):
    def test_updater_refuses_nested_syntax_and_missing_payload_before_reexec(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate = copy_sources(Path(folder) / 'candidate', entries=('pi-autowork/bin/pi-autowork.sh',))
            runner = coordinator.Coordinator.__new__(coordinator.Coordinator)
            runner.cfg = {'state_root': folder}
            runner.package, runner.package_rev = str(candidate), 'old'
            runner.toolset_rev, runner.mode = 'running', 'continuous'
            runner.reload = False
            cases = (candidate / 'pi-autowork/pi_autowork/legacy/reader.py',
                     candidate / 'pi-autowork/pi_autowork/engine/task_store.py',
                     candidate / 'pi-autowork/pi_autowork/worker.py',
                     candidate / 'pi-autowork/pi_autowork/coordinator.py',
                     candidate / 'pi-autowork/pi_autowork/tui_common.py',
                     candidate / 'pi-autowork/pi_autowork/tui_tasks.py')
            for path in cases:
                original = path.read_bytes()
                if path.name == 'reader.py':
                    path.write_text('if syntax error\n')
                else:
                    path.unlink()
                    if path.name == 'tui_tasks.py':
                        foreign = Path(folder) / 'foreign.py'
                        foreign.write_bytes(original)
                        path.symlink_to(foreign)
                runner.package_rev = 'old'
                with self.subTest(path=path), patch.object(coordinator, 'git', return_value='new'), \
                        patch.object(coordinator.release, 'prepare', return_value=candidate), \
                        patch.object(runner, 'reexec') as reexec, patch.object(coordinator.LOG, 'say'):
                    runner.restart_if_updated()
                    reexec.assert_not_called()
                    self.assertEqual(runner.toolset_rev, 'running')
                path.unlink(missing_ok=True)
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
