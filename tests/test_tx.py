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

    def test_completion_aliases_use_the_config_parser_without_tmux(self):
        result = self.tx('__complete_aliases', config=(
            '# aliases need not have existing target directories\n'
            'WORK=/nonexistent\n'
            'sample,sample2=$WORK/project\n'
            'other=~/other\n'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['other', 'sample', 'sample2'])
        empty = self.tx('__complete_aliases', config='# no aliases\n')
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(empty.stdout, '')

    def bash_complete(self, words):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-completion-') as folder:
            config = Path(folder) / 'session.config'
            config.write_text('sample,sample2=/nonexistent\nother=/tmp\n')
            env = {**os.environ, 'TX_CONFIG': str(config),
                   'TX_TMUX': '/nonexistent/tmux', 'TX_COMPLETION_COMMAND': 'tx'}
            script = '\n'.join([
                f'source <({shlex.quote(str(TX))} completion bash)',
                f'COMP_WORDS=({shlex.quote(str(TX))} {shlex.join(words)})',
                f'COMP_CWORD={len(words)}',
                '_tx_completion',
                'printf "%s\\n" "${COMPREPLY[@]}"',
            ])
            return subprocess.run(['bash', '--noprofile', '--norc', '-c', script],
                                  env=env, capture_output=True, text=True, timeout=30)

    def test_bash_completes_alias_prefix_on_tab(self):
        result = self.bash_complete(['samp'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ['sample', 'sample2'])
        command = self.bash_complete(['comp'])
        self.assertEqual(command.stdout.splitlines(), ['completion'])

    def test_bash_completes_alias_arguments_for_commands_and_flags(self):
        commands = self.tx('__complete_alias_commands').stdout.split()
        for command in commands:
            with self.subTest(command=command):
                result = self.bash_complete([command, 'samp'])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ['sample', 'sample2'])

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
            env.pop('TMUX', None)  # This case exercises attach, not switch-client.

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

    def assert_rejected_mutation(self, script):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-rejected-') as folder:
            path = Path(folder) / 'session.config'
            original = b'# keep\r\nWORK=/tmp\r\na=$WORK\r\nb=/tmp\r\n'
            path.write_bytes(original)
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never'}
            result = subprocess.run(
                ['bash', '-c', f'source {shlex.quote(str(TX))}\n{script}'],
                env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(path.read_bytes(), original, result.stderr)
            self.assertEqual(list(Path(folder).glob('session.config.tmp.*')), [])
            reload = subprocess.run(['bash', str(TX), '__complete_aliases'], env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(reload.returncode, 0, reload.stderr)
            self.assertEqual(reload.stdout.splitlines(), ['a', 'b'])

    def test_invalid_alias_mutations_leave_config_unchanged(self):
        scripts = [
            'main add new,new /tmp',
            'main edit a b,c',
            'main edit a new,other',
            'main edit a b',
            'main edit a a',
            'config_load; config_append_alias new,new /tmp',
            'config_load; config_rewrite_alias edit a new,other',
        ]
        for script in scripts:
            with self.subTest(script=script):
                self.assert_rejected_mutation(script)

    def test_config_writer_rejects_invalid_candidates_before_publication(self):
        for line in ('a=/tmp', 'not a config row', 'new=$UNDEFINED'):
            with self.subTest(line=line):
                self.assert_rejected_mutation(
                    f'config_load; CFG_LINES+=({shlex.quote(line)}); config_write')

    def test_config_writer_rejects_invalid_candidates_in_a_conditional(self):
        for line in ('a=/tmp', 'not a config row', 'new=$UNDEFINED',
                     'UNUSED=$UNDEFINED'):
            with self.subTest(line=line):
                self.assert_rejected_mutation(
                    f'config_load; CFG_LINES+=({shlex.quote(line)}); '
                    'if config_write; then exit 0; else exit 7; fi')

    def test_failed_publication_preserves_config_and_cleans_staging_file(self):
        scripts = [
            'config_load; CFG_LINES+=("new=/tmp"); mv() { return 7; }; config_write',
            'config_load; CFG_LINES+=("new=/tmp"); mv() { return 7; }; '
            'if config_write; then exit 0; else exit 7; fi',
            'config_load; CFG_LINES+=("new=/tmp"); printf() { return 7; }; '
            'if config_write; then exit 0; else exit 7; fi',
        ]
        for script in scripts:
            with self.subTest(script=script):
                self.assert_rejected_mutation(script)

    def test_valid_mutations_preserve_crlf_comments_variables_and_order(self):
        with tempfile.TemporaryDirectory(prefix='autowork-tx-preserved-') as folder:
            path = Path(folder) / 'session.config'
            path.write_bytes(b'# keep\r\nWORK=/tmp\r\n  a,b = $WORK/agent  \r\n\r\n')
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never'}
            script = f'''source {shlex.quote(str(TX))}
config_load
config_append_alias c /tmp/agent
config_rewrite_alias edit b renamed
config_rewrite_alias remove a
'''
            result = subprocess.run(['bash', '-c', script], env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_bytes(),
                             b'# keep\r\nWORK=/tmp\r\n  renamed,c = $WORK/agent  \r\n\r\n')
            self.assertEqual(list(Path(folder).glob('session.config.tmp.*')), [])

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
