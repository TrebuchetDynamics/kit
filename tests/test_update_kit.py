"""Updater boundary: local complete repositories, disposable homes, no real hosts/network."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import pty
import selectors
import signal
import subprocess
import sys
import time
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'skills/update-kit/scripts/update_kit.py'
spec = importlib.util.spec_from_file_location('update_kit', HELPER)
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def git(path, *args):
    return subprocess.run(['git', '-C', str(path), *args], check=True,
                          text=True, capture_output=True, timeout=15).stdout.strip()


class UpdateKitTests(unittest.TestCase):
    def setUp(self):
        old_umask = os.umask(0o077)
        self.addCleanup(os.umask, old_umask)
        self.temp = tempfile.TemporaryDirectory(prefix='update kit ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.upstream = self.root / 'upstream'
        self.upstream.mkdir()
        git(self.upstream, 'init', '-q', '-b', 'main')
        git(self.upstream, 'config', 'user.email', 'fixture@example.invalid')
        git(self.upstream, 'config', 'user.name', 'Fixture')
        (self.upstream / 'scripts').mkdir()
        (self.upstream / 'scripts/install_menu.py').write_text('# complete repository\n')
        (self.upstream / 'install.sh').write_text(
            '#!/bin/bash\nset -eu\n'
            'test -f scripts/install_menu.py\n'
            'printf "%s\\0" "$@" >> "$HOME/${NATIVE_NESTED:+native-}installer-argv"\n'
            'echo "pi installed; codex skipped; fixture native outcomes"\n'
            'if [ "${SECONDARY:-}" != "" ]; then\n'
            ' git fetch "$SECONDARY" main\n git merge --ff-only FETCH_HEAD\n'
            ' echo "native nested full-suite refresh"\n'
            ' SECONDARY="" NATIVE_NESTED=1 bash install.sh update --no-pull\nfi\n'
            'exit "${INSTALL_EXIT:-0}"\n')
        git(self.upstream, 'add', '.')
        git(self.upstream, 'commit', '-qm', 'initial')
        self.env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME='',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        for name in ('SECONDARY', 'INSTALL_EXIT', 'NATIVE_NESTED'):
            self.env.pop(name, None)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, self.env, clear=True).start()
        patch.object(updater, '_source_url', return_value=str(self.upstream)).start()
        real_run = updater.run
        def local_transport(argv, **kwargs):
            # Only test transport uses local Git; the production CLI never accepts one.
            argv = ['protocol.file.allow=always' if item == 'protocol.file.allow=never' else item
                    for item in argv]
            return real_run(argv, **kwargs)
        patch.object(updater, 'run', side_effect=local_transport).start()
        # Consumer inspection is tested independently with real/fake lsof below.
        self.real_idle = updater.ensure_idle
        self.temporary_roots = updater.TEMPORARY_ROOTS
        # Disposable fixture homes are intentionally temporary; production has no override.
        patch.object(updater, 'TEMPORARY_ROOTS', ()).start()
        patch.object(updater, 'ensure_idle').start()
        self.source = self.home / '.local/share/kit/source'

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = updater.main(list(args))
        return code, output.getvalue()

    def success(self, *args):
        code, out = self.invoke(*args)
        self.assertEqual(code, 0, out)
        return out

    def argv(self):
        return (self.home / 'installer-argv').read_bytes().split(b'\0')[:-1]

    def advance(self):
        (self.upstream / 'next').write_text('next')
        git(self.upstream, 'add', '.')
        git(self.upstream, 'commit', '-qm', 'next')
        return git(self.upstream, 'rev-parse', 'HEAD')

    def test_fresh_equal_and_fast_forward_reinstall_literal_argv(self):
        old = git(self.upstream, 'rev-parse', 'HEAD')
        flags = ['--only', 'pi,tx', '--hermes-home', str(self.root / 'space $(literal); home')]
        out = self.success(*flags)
        self.assertTrue((self.source / 'scripts/install_menu.py').is_file())
        self.assertEqual(git(self.source, 'remote', 'get-url', 'origin'), updater.SOURCE)
        self.assertIn(old, out)
        self.assertIn('check for updates every run', out)
        self.assertIn('restart only proven affected active integrations', out)
        self.assertIn('Hermes owns native gateway deferrals/restarts', out)
        self.success(*flags)
        new = self.advance()
        out = self.success(*flags)
        self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), new)
        self.assertIn(old, out)
        self.assertIn(new, out)
        expected = [b'update', b'--no-pull', *(arg.encode() for arg in flags)]
        self.assertEqual(self.argv(), expected * 3)

    def test_absolute_xdg_override(self):
        os.environ['XDG_DATA_HOME'] = str(self.root / 'data with spaces')
        self.success('--skip', 'hermes')
        self.assertTrue((self.root / 'data with spaces/kit/source/install.sh').is_file())
        self.assertFalse(self.source.exists())

    def test_secondary_refresh_reports_selected_and_final_sha(self):
        self.success()
        selected = git(self.source, 'rev-parse', 'HEAD')
        final = self.advance()
        # Present the selected revision to the helper and a newer source to native install.
        snapshot = self.root / 'snapshot'
        git(self.root, 'clone', '-q', str(self.source), str(snapshot))
        os.environ['SECONDARY'] = str(self.upstream)
        with patch.object(updater, '_source_url', return_value=str(snapshot)):
            out = self.success()
        self.assertIn('secondary', out.lower())
        self.assertIn(selected, out)
        self.assertIn(final, out)
        self.assertEqual(len(self.argv()), 4)
        self.assertEqual((self.home / 'native-installer-argv').read_bytes(), b'update\0--no-pull\0')

    def test_installer_partial_failure_is_not_rolled_back(self):
        os.environ['INSTALL_EXIT'] = '7'
        code, out = self.invoke('--skip', 'hermes')
        self.assertEqual(code, 7, out)
        self.assertTrue(self.source.exists())
        self.assertIn('final_sha=', out)
        self.assertIn('not rolled back', out)
        self.assertEqual(self.argv(), [b'update', b'--no-pull', b'--skip', b'hermes'])

    def test_unavailable_final_readback_does_not_claim_a_secondary_change(self):
        original = updater.run.side_effect
        installed = False
        def unavailable(argv, **kwargs):
            nonlocal installed
            if installed and argv[-2:] == ['rev-parse', 'HEAD']:
                return subprocess.CompletedProcess(argv, 128, '', 'fixture readback failed')
            result = original(argv, **kwargs)
            if argv[0] == 'bash':
                installed = True
            return result
        os.environ['INSTALL_EXIT'] = '7'
        with patch.object(updater, 'run', side_effect=unavailable):
            code, out = self.invoke('--skip', 'hermes')
        self.assertEqual(code, 7, out)
        self.assertIn('final_sha=NOT_CHECKED', out)
        self.assertIn('fixture readback failed', out)
        self.assertNotIn('Secondary source change', out)

    def test_preview_has_no_writes_or_probes(self):
        for flag in ('--dry-run', '--read-only', '--questions-only', '--list'):
            with self.subTest(flag=flag), patch.object(updater, 'run', side_effect=AssertionError('probe')), \
                    patch.object(updater.shutil, 'which', side_effect=AssertionError('tool probe')):
                out = self.success(flag, '--only', 'pi')
                self.assertIn(str(self.source), out)
                self.assertIn('NOT_CHECKED', out)
                self.assertIn('--no-pull', out)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_incompatible_restrictions_refuse_before_mutation(self):
        cases = [('--no-restarts',), ('--only', 'hermes'), ('--skip', 'pi'),
                 ('--only', 'pi,hermes', '--no-reload'), ('--menu',), ('--sudo',)]
        for args in cases:
            with self.subTest(args=args), patch.object(updater, 'run', side_effect=AssertionError('probe')):
                code, out = self.invoke(*args)
                self.assertNotEqual(code, 0, out)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertIn('restart', self.invoke('--no-restarts')[1])
        self.assertIn('nested', self.invoke('--only', 'hermes')[1])

    def test_temporary_and_host_cache_subtrees_hold_without_writes(self):
        candidates = [*(Path(root) / 'update-kit-review-data' for root in self.temporary_roots),
                      self.home / '.cache/data', self.home / '.pi/agent/packages/data',
                      self.home / '.claude/plugins/cache/data', self.home / '.codex/plugins/cache/data',
                      self.home / '.hermes/plugins/data']
        for data in candidates:
            with self.subTest(data=data), patch.object(updater, 'run', side_effect=AssertionError('probe')), \
                    patch.object(updater.Path, 'mkdir', side_effect=AssertionError('write')):
                os.environ['XDG_DATA_HOME'] = str(data)
                # The home fixtures themselves live under /tmp; isolate the cache rule.
                roots = () if data.is_relative_to(self.home) else self.temporary_roots
                with patch.object(updater, 'TEMPORARY_ROOTS', roots):
                    code, out = self.invoke('--skip', 'hermes')
                self.assertNotEqual(code, 0, out)
                self.assertIn('dedicated persistent data directory', out)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_relative_xdg_and_missing_tools_or_platform_hold(self):
        os.environ['XDG_DATA_HOME'] = 'relative'
        code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('absolute', out)
        os.environ['XDG_DATA_HOME'] = ''
        with patch.object(updater.shutil, 'which', return_value=None):
            code, out = self.invoke()
        self.assertIn('install', out.lower())
        self.assertNotEqual(code, 0)
        with patch.object(updater.sys, 'platform', 'win32'):
            code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('Linux/macOS', out)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_unsafe_existing_sources_preserve_history_and_skip_installer(self):
        mutations = {
            'untracked': lambda: (self.source / 'local').write_text('keep'),
            'tracked': lambda: (self.source / 'install.sh').write_text('keep'),
            'detached': lambda: git(self.source, 'checkout', '--detach'),
            'branch': lambda: git(self.source, 'checkout', '-b', 'other'),
            'origin': lambda: git(self.source, 'remote', 'set-url', 'origin', 'https://foreign.invalid/kit'),
            'unknown': lambda: git(self.source, 'config', '--unset', 'kit.updateKitOwner'),
            'worktree': lambda: git(self.source, 'worktree', 'add', '-b', 'linked', str(self.root / 'linked')),
            'unsafe-config': lambda: git(self.source, 'config', 'core.fsmonitor', 'false'),
            'git-lock': lambda: (self.source / '.git/index.lock').touch(),
            'ignored': lambda: ((self.source / '.git/info').mkdir(exist_ok=True),
                               (self.source / '.git/info/exclude').write_text('cache\n'),
                               (self.source / 'cache').touch()),
            'ahead': lambda: self.local_commit(),
            'diverged': lambda: (self.local_commit(), self.advance()),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                # Each source comes from the updater; no developer clone is adopted.
                with tempfile.TemporaryDirectory(dir=self.root) as home:
                    os.environ['HOME'] = home
                    self.home = Path(home)
                    self.source = self.home / '.local/share/kit/source'
                    self.success('--skip', 'hermes')
                    mutate()
                    before = git(self.source, 'rev-parse', 'HEAD')
                    argv = self.argv()
                    code, out = self.invoke('--skip', 'hermes')
                    self.assertNotEqual(code, 0, out)
                    self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), before)
                    self.assertEqual(self.argv(), argv)

    def local_commit(self):
        git(self.source, '-c', 'user.email=fixture@example.invalid', '-c', 'user.name=Fixture',
            'commit', '--allow-empty', '-qm', 'local only')

    def test_symlink_and_foreign_destination_hold(self):
        self.source.parent.mkdir(parents=True)
        self.source.symlink_to(self.upstream, target_is_directory=True)
        code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('symlink', out.lower())
        self.assertFalse((self.home / 'installer-argv').exists())
        self.source.unlink()
        self.source.mkdir()
        code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('ownership', out.lower())

    def test_failed_clone_retains_stage_and_fetch_failure_preserves_head(self):
        with patch.object(updater, '_source_url', return_value=str(self.root / 'absent')):
            code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertFalse(self.source.exists())
        stages = list(self.source.parent.glob('.source-stage-*'))
        self.assertTrue(stages)
        self.assertIn('failed', (stages[0] / 'update-kit-failure.txt').read_text())
        self.assertIn('retained', out)
        self.success('--skip', 'hermes')
        before = git(self.source, 'rev-parse', 'HEAD')
        argv = self.argv()
        with patch.object(updater, '_source_url', return_value=str(self.root / 'absent')):
            code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), before)
        self.assertEqual(self.argv(), argv)

    def test_lock_is_held_during_installer_and_busy_retries(self):
        import fcntl
        self.source.parent.mkdir(parents=True)
        lock = self.source.parent / '.update-kit.lock'
        with lock.open('w') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('retry', out.lower())
        self.assertFalse(self.source.exists())
        original = updater.run.side_effect
        def checking(argv, **kwargs):
            if argv[:1] == ['bash']:
                with lock.open('r') as contender:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return original(argv, **kwargs)
        with patch.object(updater, 'run', side_effect=checking):
            self.success('--skip', 'hermes')

    def test_live_unknown_and_native_consumers_hold_before_fetch(self):
        import fcntl
        self.success('--skip', 'hermes')
        argv = self.argv()
        with patch.object(updater, 'ensure_idle', side_effect=updater.Hold('Live/unknown source consumer; retry')):
            self.advance()
            head = git(self.source, 'rev-parse', 'HEAD')
            code, out = self.invoke('--skip', 'hermes')
        self.assertNotEqual(code, 0)
        self.assertIn('consumer', out)
        self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), head)
        self.assertEqual(self.argv(), argv)
        # Exercise the real admission owner, not just its injected failure branch.
        for result in (subprocess.CompletedProcess([], 0, '123\\n', ''),
                       subprocess.CompletedProcess([], 1, '', 'unknown visibility'),
                       subprocess.CompletedProcess([], 2, '', '')):
            with patch.object(updater, 'run', return_value=result):
                with self.assertRaises(updater.Hold):
                    self.real_idle(self.source)
        clear = subprocess.CompletedProcess([], 1, '', '')
        native = self.home / '.hermes'
        (native / 'plugins').mkdir(parents=True)
        (native / 'plugins/kit').symlink_to(self.source, target_is_directory=True)
        (native / 'gateway.pid').write_text('{"pid": "unknown"}')
        with patch.object(updater, 'run', return_value=clear):
            with self.assertRaisesRegex(updater.Hold, 'gateway'):
                self.real_idle(self.source)
        (native / 'gateway.pid').unlink()
        lock = native / 'maintenance/toolset-update/lock'
        lock.parent.mkdir(parents=True)
        with lock.open('w') as owner, patch.object(updater, 'run', return_value=clear):
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(updater.Hold, 'native updater'):
                self.real_idle(self.source)

    def test_root_updater_lock_holds_before_fetch_when_only_named_profile_links(self):
        native = self.home / '.hermes'
        flags = ('--skip', 'hermes', '--hermes-home', str(native))
        self.success(*flags)
        head = git(self.source, 'rev-parse', 'HEAD')
        argv = self.argv()
        target = self.advance()
        plugins = native / 'profiles/work/plugins'
        plugins.mkdir(parents=True)
        (plugins / 'kit').symlink_to(self.source, target_is_directory=True)
        # The unlinked root's gateway receipt must not block the retry.
        (native / 'gateway.pid').touch()
        lock = native / 'maintenance/toolset-update/lock'
        lock.parent.mkdir(parents=True)
        holder = '''
import fcntl, sys
with open(sys.argv[1], 'w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print('locked', flush=True)
    sys.stdin.read()
'''
        with patch.object(updater, 'ensure_idle', self.real_idle):
            with subprocess.Popen([sys.executable, '-B', '-c', holder, str(lock)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as owner:
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(owner.stdout, selectors.EVENT_READ)
                        self.assertTrue(selector.select(timeout=5), 'fixture did not acquire the root lock')
                    self.assertEqual(owner.stdout.readline(), 'locked\n')
                    with patch.object(updater, 'git', wraps=updater.git) as commands:
                        code, out = self.invoke(*flags)
                finally:
                    owner.stdin.close()
                    try:
                        owner.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        owner.kill()
                        raise
            self.assertEqual(code, 1, out)
            self.assertIn(f'Concurrent/unknown native updater at {native}; retry after native owner finishes', out)
            self.assertNotIn('fetch', [call.args[1] for call in commands.call_args_list])
            self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), head)
            self.assertEqual(self.argv(), argv)

            out = self.success(*flags)
        self.assertIn('installer_exit=0', out)
        self.assertEqual(git(self.source, 'rev-parse', 'HEAD'), target)
        self.assertEqual(self.argv(), argv * 2)

    def test_real_open_source_consumer_is_detected(self):
        if not updater.shutil.which('lsof'):
            self.skipTest('lsof unavailable for real open-file fixture')
        self.success('--skip', 'hermes')
        # The test itself holds an open source file; real lsof must see it.
        with (self.source / 'install.sh').open(), self.assertRaisesRegex(updater.Hold, 'consumer'):
            self.real_idle(self.source)

    def test_foreign_uid_symlink_ancestor_and_project_path_refuse(self):
        self.source.parent.mkdir(parents=True)
        self.source.mkdir()
        with patch.object(updater.os, 'getuid', return_value=os.getuid() + 1):
            code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('ownership', out)
        os.environ['XDG_DATA_HOME'] = str(self.upstream / 'data')
        code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('project checkout', out)
        self.assertFalse((self.upstream / 'data').exists())
        alias = self.root / 'alias'
        alias.symlink_to(self.home, target_is_directory=True)
        os.environ['XDG_DATA_HOME'] = str(alias / 'data')
        code, out = self.invoke()
        self.assertNotEqual(code, 0)
        self.assertIn('symlink', out.lower())
        self.assertFalse((self.home / 'data').exists())

    def test_public_entry_point_with_real_fixture_processes(self):
        # A child calls the public main, with ONLY source transport substituted internally.
        # There is no production arbitrary-URL flag or real host installer invocation.
        import sys
        program = '''
import importlib.util, sys
spec = importlib.util.spec_from_file_location('update_fixture', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m._source_url = lambda: sys.argv[2]
m.TEMPORARY_ROOTS = ()  # Internal fixture only: the disposable HOME lives in /tmp.
real_run = m.run
def local_transport(argv, **kwargs):
    argv = ['protocol.file.allow=always' if a == 'protocol.file.allow=never' else a for a in argv]
    return real_run(argv, **kwargs)
m.run = local_transport
raise SystemExit(m.main(sys.argv[3:]))
'''
        command = [sys.executable, '-B', '-c', program, str(HELPER), str(self.upstream)]
        for flags in (['--skip', 'hermes'], ['--only', 'pi,tx']):
            result = subprocess.run([*command, *flags], cwd=self.root, capture_output=True,
                                    text=True, timeout=30, env=dict(os.environ))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('pi installed; codex skipped', result.stdout)
            self.assertIn('selected_sha=', result.stdout)
            self.assertIn('final_sha=', result.stdout)
            self.assertIn('installer_exit=0', result.stdout)
        argv = self.argv()
        result = subprocess.run([*command, '--only', 'hermes'], cwd=self.root,
                                capture_output=True, text=True, timeout=30, env=dict(os.environ))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exclude Hermes', result.stderr)
        self.assertEqual(self.argv(), argv)

    def test_native_prompts_keep_the_controlling_terminal(self):
        # Exercise the real subprocess boundary, not a mocked stdin/TTY assertion.
        program = '''
import importlib.util, sys
spec = importlib.util.spec_from_file_location('update_fixture', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
result = m.run(['bash', '-c', 'echo "Native consent?"; read -r answer </dev/tty; '
                'test "$answer" = n || exit 9; echo "refusal preserved"; exit 7'],
               capture=False, timeout=5)
import os
with open('/dev/tty') as terminal:
    assert os.tcgetpgrp(terminal.fileno()) == os.getpgrp(), 'foreground not restored'
raise SystemExit(result.returncode)
'''
        pid, master = pty.fork()
        if pid == 0:
            os.execv(sys.executable, [sys.executable, '-B', '-c', program, str(HELPER)])
        seen, answered, status = b'', False, None
        try:
            deadline = time.monotonic() + 10
            with selectors.DefaultSelector() as selector:
                selector.register(master, selectors.EVENT_READ)
                while time.monotonic() < deadline:
                    if selector.select(timeout=0.1):
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break
                        if not chunk:
                            break
                        seen += chunk
                        if b'Native consent?' in seen and not answered:
                            os.write(master, b'n\n')
                            answered = True
                while time.monotonic() < deadline:
                    waited, child_status = os.waitpid(pid, os.WNOHANG)
                    if waited:
                        status = child_status
                        break
                    time.sleep(0.01)
            self.assertIsNotNone(status, seen.decode(errors='replace'))
            self.assertEqual(os.waitstatus_to_exitcode(status), 7, seen.decode(errors='replace'))
            self.assertIn(b'refusal preserved', seen)
            self.assertTrue(answered)
        finally:
            if status is None:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(master)

    def test_forwarded_flags_match_documented_installer_contract(self):
        flags = ['--full', '--no-reload', '--bundle-only', '--yes-deps', '--quiet',
                 '--color=never', '--hermes-home=space ; $(literal)', '--no-pull']
        self.success(*flags)
        self.assertEqual(self.argv(), [b'update', b'--no-pull', *(a.encode() for a in flags[:-1])])
        # Values that look like helper flags are literal values, not stripped tokens.
        self.success('--only=pi', '--hermes-home=--dry-run')
        self.assertEqual(self.argv()[-2:], [b'--only=pi', b'--hermes-home=--dry-run'])


if __name__ == '__main__':
    unittest.main()
