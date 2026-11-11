"""A toolset update goes only to a release that reads current state, preferably fleet-idle."""
import json
import sys as _sys
from pathlib import Path as _Path
_sys.path[:0] = [str(_Path(__file__).resolve().parent),
                 str(_Path(__file__).resolve().parents[3] / 'tests'),
                 str(_Path(__file__).resolve().parents[1]),
                 str(_Path(__file__).resolve().parents[2]),
                 str(_Path(__file__).resolve().parents[2] / 'engine')]
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import release  # noqa: E402
from pi_autowork.supervision import maintenance  # noqa: E402
from pi_autowork.processes import start_time  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tests'))
from src_fixture import copy_sources  # noqa: E402

STATE = 'pi-autowork/engine/parallel_state.py'


class ReleaseCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.origin, self.toolset, self.work = root / 'origin.git', root / 'toolset', root / 'work'
        self.state_root, self.own = root / 'state', root / 'state' / 'own'
        self.own.mkdir(parents=True)
        self.git(root, 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        self.git(root, 'clone', '-q', str(self.origin), str(self.work))
        self.publish('STATE_SCHEMA = 1\nSTATE_SCHEMA_READS = (1,)\n', 'release 1')
        self.git(root, 'clone', '-q', str(self.origin), str(self.toolset))

    def git(self, cwd, *args):
        subprocess.run(['git', '-C', str(cwd), '-c', 'user.email=f@example.invalid', '-c', 'user.name=F', *args],
                       check=True, capture_output=True)

    def publish(self, text, message):
        path = self.work / STATE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.git(self.work, 'add', '-A')
        self.git(self.work, 'commit', '-qm', message)
        self.git(self.work, 'push', '-q', 'origin', 'HEAD:main')

    def check(self):
        return release.check(self.state_root, self.own, self.toolset)

    def runner(self, name, in_flight, pid):
        folder = self.state_root / name
        folder.mkdir()
        (folder / 'runner.json').write_text(json.dumps(
            {'pid': pid, 'start_time': start_time(pid), 'repo': '/x/' + name}))
        (folder / 'status.json').write_text(json.dumps({'in_flight': in_flight}))

    def test_late_imports_keep_the_selected_release_while_unused_releases_are_pruned(self):
        copy_sources(self.work)
        actual = self.work / 'pi-autowork/src/pi_autowork/engine/parallel_state.py'
        original = actual.read_text()
        actual.write_text(original + '\nRELEASE_MARKER = 1\n')
        for name, text in {'first.py': 'import pi_autowork\ndef run():\n    from pi_autowork.engine import parallel_state\n    return parallel_state.RELEASE_MARKER\n',
                           'second.py': 'old_api = 1\n'}.items():
            (self.work / name).write_text(text)
        self.publish('STATE_SCHEMA = 1\n', 'old API')
        self.git(self.toolset, 'pull', '-q', '--ff-only')
        # Only this test's child can use its private releases. Unrelated host
        # interpreters with unreadable environments conservatively stop pruning.
        processes = []
        glob = Path.glob
        self.enterContext(patch.object(Path, 'glob', lambda path, pattern:
            iter(processes) if path == Path('/proc') and pattern == '[0-9]*' else glob(path, pattern)))
        selected = release.prepare(self.state_root, self.toolset)
        os.utime(selected / '.git', ns=(1_000_000_000, 1_000_000_000))
        prepared = [selected]
        child = subprocess.Popen([sys.executable, '-u', '-c',
                                  'import sys; sys.path[:0] = [sys.argv[1], sys.argv[1] + "/pi-autowork"]; '
                                  'import first; assert "pi_autowork.engine.parallel_state" not in sys.modules; '
                                  'print("ready", flush=True); input(); '
                                  'print(first.run())', str(selected)],
                                 env=dict(os.environ, PI_AUTOWORK_TOOLSET=str(selected)),
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup_child():
            if child.poll() is None:
                child.kill()
            child.communicate()  # reap and close all three pipes, including on assertion failure

        self.addCleanup(cleanup_child)
        processes.append(Path(f'/proc/{child.pid}'))  # real environ/stat reads, even after exit
        self.assertTrue(select.select([child.stdout], [], [], 10)[0], 'child did not become ready')
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        for number in range(2, 5):
            actual.write_text(original + f'\nRELEASE_MARKER = {number}\n')
            (self.work / 'first.py').write_text('from second import new_api\n')
            (self.work / 'second.py').write_text(f'new_api = {number}\n')
            self.publish(f'STATE_SCHEMA = 1\n# {number}\n', f'release {number}')
            self.git(self.toolset, 'pull', '-q', '--ff-only')
            latest = release.prepare(self.state_root, self.toolset)
            # Older snapshots have explicit, distinct mtimes before the next
            # prepare prunes; no dependence on clock resolution or elapsed sleeps.
            os.utime(latest / '.git', ns=(number * 1_000_000_000, number * 1_000_000_000))
            prepared.append(latest)
        self.assertTrue(selected.is_dir())  # a live child's old release is not pruned
        out, err = child.communicate('\n', timeout=10)
        self.assertEqual((child.returncode, out.strip()), (0, '1'), err)
        release.prepare(self.state_root, self.toolset)
        self.assertFalse(selected.exists())
        self.assertTrue(latest.is_dir())
        self.assertEqual(set((self.state_root / 'releases').glob('*/')), set(prepared[-2:]))

    def test_an_exiting_process_does_not_stop_pruning_but_an_unreadable_interpreter_does(self):
        """Under the full check every fourth prune stopped at a process caught exiting: no command
        line, state R, its environment unreadable. It can select nothing; an interpreter can."""
        with patch.object(release, 'prune'):  # three releases first, none pruned yet
            for number in range(3):
                self.publish(f'STATE_SCHEMA = 1\n# {number}\n', f'release {number}')
                self.git(self.toolset, 'pull', '-q', '--ff-only')
                release.prepare(self.state_root, self.toolset)
        root = self.state_root / 'releases'
        proc = self.state_root / 'proc'

        def process(pid, command, state):
            folder = proc / str(pid)
            folder.mkdir(parents=True)
            (folder / 'cmdline').write_bytes(command)
            (folder / 'stat').write_text(f'{pid} (x) {state} 1 1 1\n')
            (folder / 'environ').write_bytes(b'')
            (folder / 'environ').chmod(0)  # unreadable, as /proc makes an exiting process's
        process(101, b'', 'R')
        if os.access(proc / '101' / 'environ', os.R_OK):
            self.skipTest('file modes do not restrict this user (root)')
        process(102, b'', 'D')
        release.prune(root, proc=str(proc))
        self.assertEqual(len(list(root.glob('*/'))), 2)
        with patch.object(release, 'prune'):
            self.publish('STATE_SCHEMA = 1\n# 3\n', 'release 3')
            self.git(self.toolset, 'pull', '-q', '--ff-only')
            release.prepare(self.state_root, self.toolset)
        process(103, b'/usr/bin/python3\0-u\0', 'S')
        release.prune(root, proc=str(proc))
        self.assertEqual(len(list(root.glob('*/'))), 3)  # usage unknown: everything kept

    def test_status_does_not_create_or_prune_release_worktrees(self):
        cli = self.toolset / 'pi-autowork/pi_autowork/cli.py'
        cli.parent.mkdir(parents=True)
        cli.write_text('print("STATUS fixture")\n')
        before = subprocess.check_output(['git', '-C', str(self.toolset), 'worktree', 'list', '--porcelain'])
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2]),
                   PI_AUTOWORK_PACKAGE=str(self.toolset), PI_AUTOWORK_TOOLSET=str(self.toolset),
                   PI_AUTOWORK_RESELECT='', PI_AUTOWORK_STATE_DIR=str(self.state_root),
                   PI_AUTOWORK_ENV_DIR=str(self.state_root / 'settings'))
        result = subprocess.run([sys.executable, '-c',
                                 'from pi_autowork import release; import sys; '
                                 'release.launch(sys.argv[1], sys.argv[2], ["--status", "--repo", sys.argv[3]])',
                                 str(cli.parent.parent), str(self.toolset / 'pi-autowork/bin/pi-autowork.sh'), str(self.work)],
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertFalse((self.state_root / 'releases').exists(), 'a read-only status created release state')
        self.assertEqual(subprocess.check_output(['git', '-C', str(self.toolset), 'worktree', 'list', '--porcelain']), before)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'STATUS fixture')

    def test_independent_install_updates_without_consulting_interactive_pi(self):
        installed = self.state_root / 'installed'
        self.toolset.rename(installed)
        self.publish('STATE_SCHEMA = 2\nSTATE_SCHEMA_READS = (1, 2)\n', 'release 2')
        with patch.object(release, 'package_source', side_effect=AssertionError('interactive Pi consulted')):
            result = maintenance.update_package('unused', str(self.state_root), str(self.own),
                                                str(installed), str(installed), '0')
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['revision'], subprocess.check_output(
            ['git', '-C', str(installed), 'rev-parse', 'HEAD'], text=True).strip())

    def test_a_compatible_release_may_be_installed(self):
        self.assertEqual(self.check(), dict(ok=False, current=True, reason='already at the newest release'))
        self.publish('STATE_SCHEMA = 2\nSTATE_SCHEMA_READS = (1, 2)\n', 'release 2 reads 1')
        result = self.check()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['schema'], 1)
        self.assertEqual((self.toolset / STATE).read_text(), 'STATE_SCHEMA = 1\nSTATE_SCHEMA_READS = (1,)\n')  # untouched

    def test_a_release_that_cannot_read_this_state_is_refused(self):
        self.publish('STATE_SCHEMA = 2\nSTATE_SCHEMA_READS = (2,)\n', 'release 2 only')
        result = self.check()
        self.assertFalse(result['ok'])
        self.assertIn('cannot read this state (schema 1; it reads [2])', result['reason'])

    def test_the_registered_ref_not_origin_head_controls_schema_compatibility(self):
        self.git(self.work, 'checkout', '-qb', 'stable')
        (self.work / STATE).write_text('STATE_SCHEMA = 2\nSTATE_SCHEMA_READS = (2,)\n')
        self.git(self.work, 'add', STATE)
        self.git(self.work, 'commit', '-qm', 'stable needs schema 2')
        self.git(self.work, 'push', '-q', 'origin', 'HEAD:stable')
        result = release.check(self.state_root, self.own, self.toolset,
                               source='git:github.com/example/toolset@stable')
        self.assertFalse(result['ok'])
        self.assertIn('cannot read this state (schema 1; it reads [2])', result['reason'])

    def test_fetched_declarations_are_parsed_never_executed(self):
        self.publish("STATE_SCHEMA_READS = __import__('os').system('touch pwned')\n", 'hostile')
        self.assertEqual(self.check()['reason'], 'could not read the state schema declarations')
        self.assertFalse(Path('pwned').exists())

    def test_another_runner_with_work_in_flight_defers_the_update(self):
        self.publish('STATE_SCHEMA = 1\nSTATE_SCHEMA_READS = (1,)\n# 2\n', 'release 2')
        self.runner('idle', 0, os.getpid())
        self.runner('gone', 3, 2 ** 22 + 11)  # a dead runner's record does not count
        self.assertTrue(self.check()['ok'])
        self.runner('sierra', 2, os.getpid())
        result = release.check(self.state_root, self.own, self.toolset, wait=1800, now=1000.0)
        self.assertFalse(result['ok'])
        self.assertRegex(result['reason'], r'^other runners have work in flight: sierra \(2 in flight\); '
                                           r'updating to \w+ anyway in 30 min$')
        # Four always-busy runners never reach a checkpoint: once the wait from the first
        # sighting (shared by every runner) is over, the update goes ahead anyway.
        self.assertFalse(release.check(self.state_root, self.own, self.toolset, wait=1800, now=2700.0)['ok'])
        result = release.check(self.state_root, self.own, self.toolset, wait=1800, now=2801.0)
        self.assertTrue(result['ok'], result)
        self.assertIn('with work in flight (sierra (2 in flight))', result['note'])



class InstalledToolsetTests(unittest.TestCase):
    """The runner runs from the package installed under the Autowork name when Pi has several."""
    def test_the_renamed_package_wins_over_an_earlier_listed_copy(self):
        from pi_autowork import cli
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            old, new = base / 'old-toolset', base / 'autowork'
            for copy in (old, new):
                for name in ('pi-autowork/engine/owner_cycle.py', 'pi-autowork/engine/task_store.py'):
                    (copy / name).parent.mkdir(parents=True, exist_ok=True)
                    (copy / name).touch()
            pi = base / 'pi'

            def listing(*rows):
                pi.write_text('#!/usr/bin/env bash\necho "User packages:"\n'
                              + ''.join(f'echo "  {src}"\necho "    {path}"\n' for src, path in rows))
                pi.chmod(0o755)
                return cli.installed_toolset(str(pi))
            self.assertEqual(listing(('git:github.com/TrebuchetDynamics/old-toolset', old),
                                     ('git:github.com/TrebuchetDynamics/kit (filtered)', new)),
                             str(new.resolve()))
            self.assertEqual(listing(('npm:other', base), ('git:github.com/TrebuchetDynamics/old-toolset', old)),
                             str(old.resolve()))
            self.assertIsNone(listing(('npm:other', base)))

class PackageUpdateTests(unittest.TestCase):
    """Updates must use Pi's declaration, never a local checkout's Git remote."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'checkout with spaces'
        self.package.mkdir()
        self.git(self.package, 'init', '-q', '-b', 'main')
        schema = self.package / STATE
        schema.parent.mkdir(parents=True)
        schema.write_text('STATE_SCHEMA = 1\nSTATE_SCHEMA_READS = (1,)\n')
        self.git(self.package, 'add', '.')
        self.git(self.package, 'commit', '-qm', 'installed release')
        self.before = self.git(self.package, 'rev-parse', 'HEAD')
        upstream = self.root / 'upstream'
        self.git(self.root, 'clone', '-q', str(self.package), str(upstream))
        self.git(upstream, 'commit', '-qm', 'compatible update', '--allow-empty')
        self.expected = self.git(upstream, 'rev-parse', 'HEAD')
        self.git(self.package, 'remote', 'add', 'origin', str(upstream))
        self.listing = self.root / 'listing'
        self.calls = self.root / 'updates.jsonl'
        self.fetch_log = self.root / 'fetches.jsonl'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # Observe real child fetches, including the requested ref, without network access.
        git = self.bin / 'git'
        git.write_text(f'#!{sys.executable}\nimport json, os, sys\n'
                       f'if sys.argv[3:4] == ["fetch"]:\n'
                       f'    with open({str(self.fetch_log)!r}, "a") as out:\n'
                       f'        out.write(json.dumps(sys.argv[4:]) + "\\n")\n'
                       f'os.execv({shutil.which("git")!r}, sys.argv)\n')
        git.chmod(0o755)
        self.pi = self.root / 'pi'
        self.pi.write_text(f'#!{sys.executable}\nimport json, subprocess, sys\nfrom pathlib import Path\n'
                           f'if sys.argv[1:] == ["list"]:\n'
                           f'    print(Path({str(self.listing)!r}).read_text())\n'
                           f'else:\n'
                           f'    checkpoint = json.loads(Path({str(self.root / "toolset-update-attempts.json")!r}).read_text())\n'
                           f'    assert checkpoint["revision"] == {self.expected!r}\n'
                           f'    with open({str(self.calls)!r}, "a") as out:\n'
                           f'        out.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                           f'    subprocess.run(["git", "-C", {str(self.package)!r}, "reset", "--hard", "FETCH_HEAD"], check=True)\n')
        self.pi.chmod(0o755)

    def git(self, cwd, *args):
        return subprocess.run(['git', '-C', str(cwd), '-c', 'user.email=f@example.invalid', '-c', 'user.name=F', *args],
                              check=True, capture_output=True, text=True, timeout=10).stdout.strip()

    def declare(self, source):
        self.listing.write_text(f'User packages:\n  git:github.com/example/other\n'
                                f'    {self.root / "other"}\n'
                                f'  {source}\n    {self.package}\n')

    def update(self):
        from pi_autowork import coordinator
        runner = coordinator.Coordinator.__new__(coordinator.Coordinator)
        runner.mode, runner.update_interval, runner.last_update = 'continuous', 1, 0
        # Match the string paths supplied by CLI config / PI_AUTOWORK_PACKAGE.
        runner.package = runner.toolset = str(self.package)
        runner.state = self.root / 'state'
        runner.state.mkdir(exist_ok=True)
        runner.cfg = {'pi': str(self.pi), 'state_root': str(self.root), 'git_common': str(self.package / '.git')}
        runner.update_wait = 600
        runner.last_update_note = ''
        self.git(self.package, 'reset', '--hard', self.before)
        for path in (self.calls, self.fetch_log, self.package / '.git/FETCH_HEAD'):
            path.unlink(missing_ok=True)
        # Old processes can inherit this incorrect flag for a local package.
        with patch.dict(os.environ, PI_AUTOWORK_PACKAGE_INSTALLED='1',
                        PATH=str(self.bin) + os.pathsep + os.environ['PATH']):
            try:
                runner.update_toolset()
                self.assertIn('job', maintenance.read(runner, 'update'))
                self.collect_update(runner)
                self.outcome = maintenance.read(runner, 'update')['outcome']
                self.assertEqual((runner.state / 'maintenance-update.exit').read_text().strip(), '0')
            finally:
                maintenance.stop(runner)
                self.collect_update(runner)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        self.fetches = [json.loads(line) for line in self.fetch_log.read_text().splitlines()] if self.fetch_log.exists() else []
        return calls, len(self.fetches)

    def collect_update(self, runner):
        deadline = time.monotonic() + 10
        while maintenance.read(runner, 'update').get('job'):
            self.assertLess(time.monotonic(), deadline, 'fixture update did not settle')
            maintenance.poll(runner)
            time.sleep(.01)

    def test_local_packages_never_fetch_or_update_even_with_an_old_installed_flag(self):
        for source in ('../../git/autowork', str(self.package)):
            with self.subTest(source=source):
                self.declare(source)
                calls, checks = self.update()
                self.assertEqual(calls, [])
                self.assertEqual(checks, 0)
                self.assertFalse((self.package / '.git/FETCH_HEAD').exists())
                self.assertTrue(self.outcome['current'], self.outcome)

    def test_managed_packages_use_the_exact_registered_source_including_ref(self):
        for source in ('git:github.com/TrebuchetDynamics/kit',
                       'git:github.com/TrebuchetDynamics/kit@main',
                       'https://github.com/TrebuchetDynamics/kit'):
            with self.subTest(source=source):
                self.declare(source + ' (filtered)')
                calls, checks = self.update()
                self.assertEqual(calls, [['update', source]])
                self.assertEqual(checks, 1)
                self.assertEqual(self.fetches, [['-q', '--', 'origin', release.package_ref(source)]])
                self.assertTrue(self.outcome['ok'], self.outcome)
                self.assertEqual(self.outcome['revision'], self.expected)

    def test_registered_refs_do_not_confuse_ssh_usernames_with_refs(self):
        for source, expected in (
                ('git:github.com/example/repo@feature/fix', 'feature/fix'),
                ('https://github.com/example/repo@stable', 'stable'),
                ('git:ssh://git@github.com/example/repo@v2', 'v2'),
                ('git:git@github.com:example/repo@v2', 'v2'),
                ('git:ssh://git@github.com/example/repo', 'HEAD'),
                ('git:git@github.com:example/repo', 'HEAD')):
            with self.subTest(source=source):
                self.assertEqual(release.package_ref(source), expected)

    def test_bootstrap_marks_only_managed_sources_as_package_installed(self):
        cli = self.package / 'pi-autowork/pi_autowork/cli.py'
        cli.parent.mkdir(parents=True)
        cli.write_text('import os; print(os.environ["PI_AUTOWORK_PACKAGE_INSTALLED"])\n')
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2]),
                   PI_BIN=str(self.pi), PI_AUTOWORK_RESELECT='auto',
                   PI_AUTOWORK_ENV_DIR=str(self.root / 'settings'),
                   # disposable: the real state root may hold an installed release
                   PI_AUTOWORK_STATE_DIR=str(self.root / 'empty-state'))
        for source, installed in ((str(self.package), '0'),
                                  ('../../git/autowork', '0'),
                                  ('git:github.com/TrebuchetDynamics/kit', '1')):
            with self.subTest(source=source):
                self.declare(source)
                result = subprocess.run([sys.executable, '-c',
                    'from pi_autowork import release; import sys; '
                    'release.launch(sys.argv[1], sys.argv[2], ["--status", "--repo", sys.argv[3]])',
                    str(cli.parent.parent), str(self.package / 'pi-autowork/bin/pi-autowork.sh'), str(self.package)],
                    env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), installed)
        independent = self.root / 'installed'
        self.package.rename(independent)
        self.pi.unlink()
        cli = independent / 'pi-autowork/pi_autowork/cli.py'
        cli.write_text('import json, os; print(json.dumps({k: os.environ[k] for k in '
                       '["PI_AUTOWORK_PACKAGE_INSTALLED", "PI_AUTOWORK_TOOLSET", "PI_CODING_AGENT_DIR"]}))\n')
        env = {k: v for k, v in env.items() if not k.startswith('PI_AUTOWORK_')}
        env['PI_AUTOWORK_STATE_DIR'] = str(self.root)
        env['PI_CODING_AGENT_DIR'] = str(self.root / 'removed-interactive')
        result = subprocess.run([sys.executable, '-c',
            'from pi_autowork import release; import sys; '
            'release.launch(sys.argv[1], sys.argv[2], ["--status", "--repo", sys.argv[3]])',
            str(cli.parent.parent), str(independent / 'pi-autowork/bin/pi-autowork.sh'), str(independent)],
            env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'PI_AUTOWORK_PACKAGE_INSTALLED': '1',
                         'PI_AUTOWORK_TOOLSET': str(independent), 'PI_CODING_AGENT_DIR': str(self.root / 'pi-agent')})

    def test_unknown_or_unreadable_package_declarations_do_not_update(self):
        self.listing.write_text('User packages:\n  git:github.com/example/other\n'
                                f'    {self.root / "other"}\n')
        self.assertEqual(self.update(), ([], 0))
        self.assertFalse((self.package / '.git/FETCH_HEAD').exists())
        self.listing.unlink()
        self.assertEqual(self.update(), ([], 0))
        self.assertFalse((self.package / '.git/FETCH_HEAD').exists())
        self.pi.unlink()  # missing executable is also an unreadable declaration
        self.assertEqual(self.update(), ([], 0))


if __name__ == '__main__':
    unittest.main()
