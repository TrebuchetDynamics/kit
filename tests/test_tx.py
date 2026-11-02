"""tx is the tmux session launcher; runners are the autowork command's."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TX = ROOT / 'tmux' / 'tx'


class TxTests(unittest.TestCase):
    def tx(self, *args):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-') as folder:
            env = {**os.environ, 'TX_CONFIG': str(Path(folder) / 'tx.config'), 'TX_COLOR': 'never'}
            return subprocess.run(['bash', str(TX), *args], env=env, capture_output=True, text=True, timeout=30)

    def test_tx_has_no_autowork_commands(self):
        # The dynamic config path can legitimately contain the project/profile name.
        help_lines = self.tx('help').stdout.splitlines()
        self.assertNotIn('autowork', '\n'.join(line for line in help_lines if not line.startswith('  Current: ')))
        self.assertNotIn('autowork', TX.read_text())
        self.assertEqual(self.tx('autowork').returncode, 1)  # just an unknown alias

    def test_help_guard_still_rejects_a_real_autowork_command(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        with patch.object(self, 'tx', return_value=SimpleNamespace(
                stdout='  tx autowork\n  Current: /example/autowork/tx.config\n', returncode=1)):
            with self.assertRaises(AssertionError):
                self.test_tx_has_no_autowork_commands()

    def test_the_package_installs_tx_and_autowork(self):
        package = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(package['bin'], {'autowork': 'pi-autowork/bin/autowork', 'tx': 'tmux/tx'})
        for folder in ('tmux/', 'pi-autowork/bin/'):
            self.assertIn(folder, package['files'])
        for path in (TX, ROOT / 'pi-autowork/bin/autowork'):
            self.assertTrue(os.access(path, os.X_OK), path)


class TxConfigModuleTests(unittest.TestCase):
    def source(self, config, script):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-config-') as folder:
            path = Path(folder) / 'session.config'
            path.write_text(config)
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never',
                   'TARGET': '/tmp/agent'}
            (Path(folder) / 'agent').mkdir()
            return subprocess.run(['bash', '-c', f'source {shlex.quote(str(TX))}\n{script}'],
                                  env=env, capture_output=True, text=True, timeout=30)

    def test_source_does_not_run_main_and_config_owns_the_grammar(self):
        config = '# keep\nWORK=/tmp\n# row\nga,g=$WORK/agent\n'
        result = self.source(config, 'config_load; printf "%s\\n" "${ALIAS_TO_PATH[g]}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '/tmp/agent')

    def test_append_and_rewrite_preserve_comments_vars_and_order(self):
        config = '# keep\nWORK=/tmp\n# row\nga,g=$WORK/agent\n'
        result = self.source(
            config,
            'config_load; config_append_alias h "$TARGET"; config_rewrite_alias edit g g2; cat "$TX_CONFIG"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '# keep\nWORK=/tmp\n# row\nga,g2,h=$WORK/agent\n')


if __name__ == '__main__':
    unittest.main()
