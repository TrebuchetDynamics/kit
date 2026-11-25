"""tx is the tmux session launcher."""
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
        with tempfile.TemporaryDirectory(prefix='kit-tx-') as folder:
            path = Path(folder) / 'tx.config'
            if config is not None:
                path.write_text(config)
            env = {**os.environ, 'TX_CONFIG': str(path),
                   'TX_COLOR': 'never', 'TX_TMUX': 'true',
                   'TX_COMPLETION_COMMAND': str(TX)}
            return subprocess.run(['bash', str(TX), *args], env=env, capture_output=True, text=True, timeout=30)

    def test_unknown_session_alias_is_rejected(self):
        self.assertEqual(self.tx('unknown-session').returncode, 1)

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
        self.assertIn('tx remove <alias-or-pattern> [alias-or-pattern ...]', help_text)
        self.assertIn('tx remove hw1 hw2 hw3 hw4', help_text)
        self.assertIn("tx remove 'hw*'", help_text)
        self.assertIn('Every selector must match', help_text)
        self.assertIn('caller shell before tx runs', help_text)
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
        with tempfile.TemporaryDirectory(prefix='kit-tx-completion-') as folder:
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

    def test_bash_completes_later_remove_operands(self):
        for words in (['remove', 'other', 'samp'],
                      ['remove', 'other', 'sample', 'samp']):
            with self.subTest(words=words):
                result = self.bash_complete(words)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ['sample', 'sample2'])

    def test_completion_generators_retain_alias_command_discovery(self):
        for shell in ('bash', 'fish', 'zsh'):
            with self.subTest(shell=shell):
                result = self.tx('completion', shell)
                self.assertEqual(result.returncode, 0, result.stderr)
                if shell == 'zsh':
                    # Zsh embeds the command-table discovery at generation time.
                    self.assertIn('alias_commands=(kill\n-k\n--kill\nremove\nedit\nwhich)',
                                  result.stdout)
                else:
                    self.assertIn('__complete_alias_commands', result.stdout)
                self.assertIn('__complete_aliases', result.stdout)

    def test_install_print_paths_is_read_only(self):
        with tempfile.TemporaryDirectory(prefix='kit-tx-install-') as folder:
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
        with tempfile.TemporaryDirectory(prefix='kit-tx-tmux-') as folder:
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

    def open_existing_session(self, pane_path):
        with tempfile.TemporaryDirectory(prefix='kit-tx-tmux-') as folder:
            root = Path(folder)
            fake = root / 'tmux'
            shutil.copy(ROOT / 'tests/fixtures/fake_tmux.sh', fake)
            fake.chmod(0o755)
            log = root / 'tmux.log'
            config = root / 'session.config'
            config.write_text('a=/tmp\n')
            env = {**os.environ, 'TX_CONFIG': str(config), 'TX_COLOR': 'never',
                   'TX_TMUX': str(fake), 'FAKE_TMUX_LOG': str(log),
                   'FAKE_RUNNING': 'a', 'FAKE_PANE_PATH': pane_path,
                   'FAKE_PANE_COMMAND': 'bash'}
            env.pop('TMUX', None)
            result = subprocess.run([str(TX), 'a'], env=env, capture_output=True,
                                    text=True, timeout=30)
            return result, log.read_text().splitlines()

    def test_existing_session_in_other_directory_attaches_without_sending_keys(self):
        result, calls = self.open_existing_session('/elsewhere')
        self.assertFalse(any(call.startswith('send-keys ') for call in calls), calls)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('display-message -p -t =a: #{pane_current_path}', calls)
        self.assertIn('attach-session -t =a', calls)
        lines = (result.stdout + result.stderr).splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn('/tmp', lines[0])

    def test_existing_session_in_target_directory_attaches_without_a_hint(self):
        result, calls = self.open_existing_session('/tmp')
        self.assertFalse(any(call.startswith('send-keys ') for call in calls), calls)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('attach-session -t =a', calls)
        self.assertEqual(result.stdout + result.stderr, '')

    def test_the_package_installs_tx_without_the_removed_runner(self):
        package = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(package['bin'], {'tx': 'tmux/tx'})
        self.assertIn('tmux/', package['files'])
        self.assertTrue(os.access(TX, os.X_OK), TX)


class TxRemoveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='tx-remove-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'session.config'
        self.target = self.root / 'target'
        self.target.mkdir()
        self.sentinel = self.target / 'keep.txt'
        self.sentinel.write_bytes(b'untouched\n')
        self.cwd = self.root / 'empty'
        self.cwd.mkdir()
        self.log = self.root / 'tmux.log'
        self.fake = self.root / 'tmux'
        shutil.copy(ROOT / 'tests/fixtures/fake_tmux.sh', self.fake)
        self.fake.chmod(0o755)
        self.env = {**os.environ, 'TX_CONFIG': str(self.path),
                    'TX_COLOR': 'never', 'TX_TMUX': str(self.fake),
                    'FAKE_TMUX_LOG': str(self.log), 'LC_ALL': 'C'}
        self.original = (
            f'# keep\r\nWORK={self.target}\r\n'
            '  hw2,hw1,keep = $WORK  \r\n\r\n'
            'hw4=/missing/target\r\nhw3=$WORK\r\n'
            'Hw1,other=$WORK\r\n').encode()
        self.path.write_bytes(self.original)

    def run_tx(self, *args, script=None):
        command = (['bash', str(TX), *args] if script is None else
                   ['bash', '--noprofile', '--norc', '-c',
                    f'source {shlex.quote(str(TX))}\n{script}'])
        return subprocess.run(command, env=self.env, cwd=self.cwd,
                              capture_output=True, text=True, timeout=30)

    def assert_no_side_effects(self):
        self.assertFalse(self.log.exists(), 'remove must not invoke tmux')
        self.assertEqual(self.sentinel.read_bytes(), b'untouched\n')
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ['keep.txt'])
        self.assertEqual(list(self.root.glob('session.config.tmp.*')), [])

    def assert_removed_hardware(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            f'removed: hw2={self.target}', f'removed: hw1={self.target}',
            'removed: hw4=/missing/target', f'removed: hw3={self.target}'])
        self.assertEqual(self.path.read_bytes(), (
            f'# keep\r\nWORK={self.target}\r\n'
            '  keep = $WORK  \r\n\r\nHw1,other=$WORK\r\n').encode())
        reloaded = self.run_tx('__complete_aliases')
        self.assertEqual(reloaded.returncode, 0, reloaded.stderr)
        self.assertEqual(reloaded.stdout.splitlines(), ['Hw1', 'keep', 'other'])
        self.assert_no_side_effects()

    def test_remove_four_literal_operands(self):
        self.assert_removed_hardware(self.run_tx('remove', 'hw1', 'hw2', 'hw3', 'hw4'))

    def test_remove_literal_wildcard_operand(self):
        self.assert_removed_hardware(self.run_tx('remove', 'hw*'))

    def test_remove_mixed_overlapping_selectors_uses_original_snapshot(self):
        self.assert_removed_hardware(
            self.run_tx('remove', 'hw3', 'hw', 'hw*', 'hw1', 'hw?', 'hw*'))

    def test_basic_patterns_and_wildcard_all(self):
        for selector, removed in [('hw?', ['hw2', 'hw1', 'hw4', 'hw3']),
                                  ('hw[1-4]', ['hw2', 'hw1', 'hw4', 'hw3']),
                                  ('hw[!5]', ['hw2', 'hw1', 'hw4', 'hw3']),
                                  ('hw[[:digit:]]', ['hw2', 'hw1', 'hw4', 'hw3']),
                                  ('hw[!()]', ['hw2', 'hw1', 'hw4', 'hw3']),
                                  ('*', ['hw2', 'hw1', 'keep', 'hw4', 'hw3', 'Hw1', 'other'])]:
            with self.subTest(selector=selector):
                self.path.write_bytes(self.original)
                result = self.run_tx('remove', selector)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([line.split('=', 1)[0] for line in result.stdout.splitlines()],
                                 [f'removed: {alias}' for alias in removed])
                if selector == '*':
                    self.assertEqual(self.path.read_bytes(),
                                     f'# keep\r\nWORK={self.target}\r\n\r\n'.encode())
                else:
                    self.assert_removed_hardware(result)
                self.assert_no_side_effects()

    def test_literal_and_prefix_still_select_one_exact_shortest_alphabetical_alias(self):
        for selector, alias in [('hw', 'hw1'), ('hw2', 'hw2'), ('h', 'h'), ('long', 'longer')]:
            with self.subTest(selector=selector):
                original = b'hw2,hw1,h,longest,longer=/missing\n'
                self.path.write_bytes(original)
                result = self.run_tx('remove', selector)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f'removed: {alias}=/missing\n')
                kept = [a for a in ['hw2', 'hw1', 'h', 'longest', 'longer'] if a != alias]
                self.assertEqual(self.path.read_bytes(), (','.join(kept) + '=/missing\n').encode())
                self.assert_no_side_effects()

    def test_late_rejected_selectors_are_atomic_even_in_a_conditional(self):
        for selector, diagnostic in [('unknown', 'unknown alias: unknown'),
                                     ('absent*', "no aliases match selector: 'absent*'"),
                                     ('hw[', "no aliases match selector: 'hw['"),
                                     ('w*', "no aliases match selector: 'w*'"),
                                     ('hw??', "no aliases match selector: 'hw??'"),
                                     ('@(hw*)', "no aliases match selector: '@(hw*)'"),
                                     ('', "empty selector: ''"),
                                     ('hw1,hw2', 'unknown alias: hw1,hw2')]:
            for conditional in (False, True):
                with self.subTest(selector=selector, conditional=conditional):
                    command = shlex.join(['main', 'remove', 'hw1', selector])
                    result = (self.run_tx(script=f'if {command}; then exit 0; else exit 7; fi')
                              if conditional else self.run_tx('remove', 'hw1', selector))
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(self.path.read_bytes(), self.original)
                    self.assert_no_side_effects()

    def test_unknown_literal_existing_filename_gets_quoting_hint_atomically(self):
        for kind in ('file', 'directory', 'dangling_symlink'):
            filename = self.cwd / 'go.mod'
            if kind == 'file':
                filename.touch()
            elif kind == 'directory':
                filename.mkdir()
            else:
                filename.symlink_to(self.cwd / 'missing')
            with self.subTest(kind=kind):
                result = self.run_tx('remove', 'hw1', 'go.mod', 'hw2')
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(result.stderr.splitlines()[0], 'tx: unknown alias: go.mod')
                hint = '\n'.join(result.stderr.splitlines()[1:])
                self.assertIn('hint:', hint)
                self.assertIn('go.mod', hint)
                self.assertIn('shell', hint)
                self.assertIn('expanded', hint)
                self.assertRegex(hint, r"tx remove '[^']+\*'")
                self.assertEqual(result.stdout, '')
                self.assertEqual(self.path.read_bytes(), self.original)
                self.assert_no_side_effects()
            if kind == 'directory':
                filename.rmdir()
            else:
                filename.unlink()

    def test_unknown_literal_without_filename_has_no_hint(self):
        result = self.run_tx('remove', 'go.mod')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, 'tx: unknown alias: go.mod\n')
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_side_effects()

    def test_existing_filename_does_not_override_literal_or_prefix_alias(self):
        for selector in ('hw1', 'hw'):
            with self.subTest(selector=selector):
                self.path.write_bytes(self.original)
                (self.cwd / selector).touch()
                result = self.run_tx('remove', selector)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                self.assertEqual(result.stdout, f'removed: hw1={self.target}\n')
                self.assertNotIn('hw1', self.run_tx('__complete_aliases').stdout.splitlines())
                self.assertTrue((self.cwd / selector).is_file())
                self.assert_no_side_effects()

    def test_existing_filename_hint_is_remove_only_and_literal_only(self):
        for selector in ('go.mod', 'g*', 'g?', 'g['):
            (self.cwd / selector).touch()
            for args in ((selector,), ('which', selector), ('remove', selector)):
                if args == ('remove', 'go.mod'):
                    continue
                with self.subTest(args=args):
                    result = self.run_tx(*args)
                    self.assertEqual(result.returncode, 1)
                    self.assertNotIn('hint:', result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_side_effects()

    def test_no_operands_is_usage_error_even_without_config(self):
        self.path.unlink()
        result = self.run_tx('remove')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('remove: expected at least one alias or pattern', result.stderr)
        self.assertNotIn('config not found', result.stderr)
        self.assert_no_side_effects()

    def test_publication_failures_are_atomic_even_in_a_conditional(self):
        failures = [
            ('config_render_alias_line() { CFG_LINES[$1]="not a config row"; }', 'cannot parse'),
            ('''printf() {
  if [[ "$1" == '%s\\n' && "${2:-}" == '# keep'* ]]; then
    builtin printf 'injected write failure\\n' >&2
    return 7
  fi
  builtin printf "$@"
}''', 'injected write failure'),
            ('mv() { builtin printf "injected rename failure\\n" >&2; return 7; }',
             'injected rename failure'),
            ('resolve_alias() { builtin printf "injected resolver failure\\n" >&2; return 7; }',
             'injected resolver failure'),
        ]
        for injection, diagnostic in failures:
            for conditional in (False, True):
                with self.subTest(injection=injection, conditional=conditional):
                    command = 'main remove hw1 hw2'
                    if conditional:
                        command = f'if {command}; then exit 0; else exit 7; fi'
                    result = self.run_tx(script=f'{injection}\n{command}')
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertEqual(result.stdout, '')
                    self.assertEqual(self.path.read_bytes(), self.original)
                    self.assert_no_side_effects()

    def test_batch_stages_and_publishes_once(self):
        stages = self.root / 'stages'
        publishes = self.root / 'publishes'
        result = self.run_tx(script=f'''
mktemp() {{ echo stage >> {shlex.quote(str(stages))}; command mktemp "$@"; }}
mv() {{ echo publish >> {shlex.quote(str(publishes))}; command mv "$@"; }}
if main remove hw1 'hw*' hw2; then :; else exit 7; fi
''')
        self.assert_removed_hardware(result)
        self.assertEqual(stages.read_text().splitlines(), ['stage'])
        self.assertEqual(publishes.read_text().splitlines(), ['publish'])

    def test_sourced_bulk_helper_isolates_matching_options(self):
        result = self.run_tx(script="config_load; shopt -s extglob nocasematch; "
                                    "config_remove_aliases 'hw*'; "
                                    "shopt -q extglob nocasematch")
        self.assert_removed_hardware(result)

    def test_default_bash_passes_unquoted_glob_in_empty_cwd(self):
        # No startup files/options or filenames can expand this token before tx sees it.
        env = {key: value for key, value in self.env.items()
               if key not in ('BASH_ENV', 'BASHOPTS', 'SHELLOPTS', 'GLOBIGNORE')}
        result = subprocess.run(
            ['bash', '--noprofile', '--norc', '-c', f'{shlex.quote(str(TX))} remove hw*'],
            env=env, cwd=self.cwd, capture_output=True, text=True, timeout=30)
        self.assert_removed_hardware(result)


class TxConfigModuleTests(unittest.TestCase):
    def source(self, config, script):
        with tempfile.TemporaryDirectory(prefix='kit-tx-config-') as folder:
            path = Path(folder) / 'session.config'
            path.write_text(config)
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never',
                   'TARGET': '/tmp/agent'}
            (Path(folder) / 'agent').mkdir()
            return subprocess.run(['bash', '-c', f'source {shlex.quote(str(TX))}\n{script}'],
                                  env=env, capture_output=True, text=True, timeout=30)

    def assert_rejected_mutation(self, script):
        with tempfile.TemporaryDirectory(prefix='kit-tx-rejected-') as folder:
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
        with tempfile.TemporaryDirectory(prefix='kit-tx-preserved-') as folder:
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
        with tempfile.TemporaryDirectory(prefix='kit-tx-preserve-') as folder:
            path = Path(folder) / 'session.config'
            target = Path(folder) / 'agent with spaces'
            target.mkdir()
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never'}
            for newline in ('\n', '\r\n'):
                with self.subTest(newline=newline):
                    prefix = f'# keep\nWORK={folder}\n\n# row\n'
                    row = '  ga,g = $WORK/agent with spaces  '
                    tail = '\nlast=/other\n'
                    path.write_bytes((prefix + row + tail).replace('\n', newline).encode())
                    for args, keys in ((('add', 'h', str(target)), 'ga,g,h'),
                                       (('edit', 'g', 'g2'), 'ga,g2,h'),
                                       (('remove', 'g2'), 'ga,h'),
                                       (('remove', 'h'), 'ga'),
                                       (('remove', 'ga'), None)):
                        result = subprocess.run(['bash', str(TX), *args], env=env,
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        expected = prefix + (f'  {keys} = $WORK/agent with spaces  \n' if keys else '') + 'last=/other\n'
                        self.assertEqual(path.read_bytes(), expected.replace('\n', newline).encode())

    def test_invalid_mutations_preserve_config_and_reload(self):
        with tempfile.TemporaryDirectory(prefix='kit-tx-reject-') as folder:
            path = Path(folder) / 'session.config'
            original = f'# keep\nWORK={folder}\nga,g=$WORK\nother=/other\n'.encode()
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never'}
            source = f'source {shlex.quote(str(TX))}; config_load; '
            cases = [
                (['bash', str(TX), 'add', 'h,h', folder], None),
                (['bash', str(TX), 'add', 'h,ga', folder], None),
                (['bash', str(TX), 'edit', 'ga', 'h,i'], None),
                (['bash', str(TX), 'edit', 'ga'], 'h,other\n'),
                (['bash', str(TX), 'edit', 'ga', 'other'], None),
                (['bash', '-c', source + 'config_append_alias h,h /other'], None),
                (['bash', '-c', source + 'config_append_alias ga /other'], None),
                (['bash', '-c', source + 'config_rewrite_alias edit ga h,i'], None),
                (['bash', '-c', source + 'config_rewrite_alias edit ga other'], None),
            ]
            for command, input_text in cases:
                with self.subTest(command=command, input=input_text):
                    path.write_bytes(original)
                    result = subprocess.run(command, input=input_text, env=env,
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertRegex(result.stderr, 'duplicate alias|exactly one new alias')
                    self.assertEqual(path.read_bytes(), original)
                    reload = subprocess.run(['bash', str(TX), 'which', 'ga'], env=env,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(reload.returncode, 0, reload.stderr)
                    self.assertEqual(reload.stdout.strip(), folder)
                    self.assertEqual(list(Path(folder).glob('session.config.tmp.*')), [])

    def test_writer_rejects_invalid_candidate_and_cleans_staging(self):
        with tempfile.TemporaryDirectory(prefix='kit-tx-writer-') as folder:
            path = Path(folder) / 'session.config'
            original = b'# keep\nga=/original\n'
            env = {**os.environ, 'TX_CONFIG': str(path), 'TX_COLOR': 'never'}
            for candidate in ('ga=/duplicate', 'new=$UNDEFINED/path', 'not a config row'):
                with self.subTest(candidate=candidate):
                    path.write_bytes(original)
                    script = (f'source {shlex.quote(str(TX))}; config_load; '
                              f'CFG_LINES+=({shlex.quote(candidate)}); config_write')
                    result = subprocess.run(['bash', '-c', script], env=env,
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(path.read_bytes(), original)
                    self.assertEqual(list(Path(folder).glob('session.config.tmp.*')), [])


if __name__ == '__main__':
    unittest.main()
