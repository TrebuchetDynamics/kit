"""Native maintenance never dispatches the retired repository executor."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RepositoryStatusTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('repo_status_bundle', ROOT / 'scripts/bundle.py')
        self.bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bundle)

    def test_repository_status_redirects_without_executor_dispatch(self):
        with patch.object(self.bundle.subprocess, 'run') as run:
            for args in ('status', 'STATUS Example', 'status "/example/My Repo"', 'status --help'):
                with self.subTest(args=args):
                    reply = self.bundle.maintenance_reply(args)
                    self.assertIn('executor has been removed', reply)
                    self.assertIn('GitHub Issues/PRs', reply)
                    self.assertIn('`orbi status`', reply)
            self.assertIn('Usage:', self.bundle.maintenance_reply('status "unfinished'))
            run.assert_not_called()

    def test_plugin_status_preserves_setup_diagnostics(self):
        with patch.object(self.bundle, 'list_commands', return_value='PLUGIN HEALTH') as inventory, \
                patch.object(self.bundle.subprocess, 'run') as run:
            self.assertEqual(self.bundle.maintenance_reply('plugin status'), 'PLUGIN HEALTH')
        inventory.assert_called_once_with('')
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
