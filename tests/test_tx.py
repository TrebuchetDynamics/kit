"""tx is the tmux session launcher; runners are the autowork command's."""
import json
import os
import shutil
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TX = ROOT / 'tmux' / 'tx'


class TxTests(unittest.TestCase):
    def tx(self, *args, config=None):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-') as folder:
            path = Path(folder) / 'tx.config'
            if config is not None:
                path.write_text(config)
            env = {**os.environ, 'TX_CONFIG': str(path),
                   'TX_COLOR': 'never', 'TX_TMUX': 'true'}
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

    def test_flag_forms_dispatch_through_the_table(self):
        result = self.tx('-l', config='a=/tmp\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('tx sessions', result.stdout)

    def test_command_table_drives_help_and_completion(self):
        commands = self.tx('__complete_commands').stdout.split()
        self.assertEqual(commands, ['help', 'ls', 'kill', 'kill-all', 'init', 'add',
                                    'remove', 'edit', 'doctor', 'which', 'config',
                                    'install', 'completion'])
        aliases = self.tx('__complete_alias_commands').stdout.split()
        self.assertEqual(aliases, ['kill', '-k', '--kill', 'remove', 'edit',
                                   'which'])
        help_text = self.tx('help').stdout
        self.assertIn('tx kill <alias>', help_text)
        self.assertNotIn('__complete_', help_text)

    def test_install_print_paths_is_read_only(self):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-install-') as folder:
            home = Path(folder)
            env = {**os.environ, 'HOME': str(home),
                   'TMUX_CONF_TARGET': str(home / 'tmux.conf'),
                   'TMUX_HELPER_DIR': str(home / 'tmux'),
                   'TX_BIN_DIR': str(home / 'bin'),
                   'TX_BIN_NAME': 'tx'}
            result = subprocess.run(['sh', str(ROOT / 'tmux/install.sh'), '--print-paths'],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('TMUX_CONF_TARGET=', result.stdout)
            self.assertIn('TX_BIN_DIR=', result.stdout)
            self.assertFalse((home / 'tmux.conf').exists())
            self.assertFalse((home / 'bin').exists())

    def test_session_module_uses_a_fake_tmux_adapter(self):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-tmux-') as folder:
            root = Path(folder)
            fake = root / 'tmux'
            shutil.copy(ROOT / 'tests/fixtures/fake_tmux.sh', fake)
            fake.chmod(0o755)
            log = root / 'tmux.log'
            config = root / 'session.config'
            config.write_text('a=/tmp\nb=/tmp\n')
            env = {**os.environ, 'TX_CONFIG': str(config), 'TX_COLOR': 'never',
                   'TX_TMUX': str(fake), 'FAKE_TMUX_LOG': str(log),
                   'FAKE_RUNNING': 'a', 'FAKE_PANE_PATH': '/tmp',
                   'FAKE_PANE_COMMAND': 'bash'}

            def run(*args):
                return subprocess.run(['bash', str(TX), *args], env=env,
                                      capture_output=True, text=True, timeout=30)

            listed = run('ls')
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn('1 running', listed.stdout)
            killed = run('kill', 'a')
            self.assertEqual(killed.returncode, 0, killed.stderr)
            self.assertIn('killed: a', killed.stdout)
            self.assertIn('kill-session -t =a', log.read_text())
            idle = run('kill', 'b')
            self.assertEqual(idle.returncode, 0, idle.stderr)
            self.assertIn('not running: b', idle.stdout)
            attached = run('a')
            self.assertEqual(attached.returncode, 0, attached.stderr)
            self.assertIn('attach-session -t =a', log.read_text())

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
