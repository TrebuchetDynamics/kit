"""Which Autowork runtime runs: the launcher's choice and the skew report. Fakes only."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

PRODUCT = Path(__file__).resolve().parents[2]
ROOT = PRODUCT.parent
sys.path.insert(0, str(PRODUCT / 'src'))
sys.path.insert(0, str(PRODUCT / 'pi_autowork/engine'))
from pi_autowork import build  # noqa: E402

LAUNCHER = ROOT / 'pi-autowork/bin/autowork'
COPY = ('from pathlib import Path\nimport sys\n'
        'print("ran " + Path(sys.argv[0]).parents[2].name + " " + " ".join(sys.argv[1:]))\n')


class LauncherTests(unittest.TestCase):
    """The launcher must not run a package copy while an installation exists."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.state = self.base / 'state'
        self.checkout = self.base / 'checkout'
        self.installed = self.state / 'installed'
        for root in (self.checkout, self.installed):
            (root / 'pi-autowork/pi_autowork').mkdir(parents=True)
            (root / 'pi-autowork/pi_autowork/command.py').write_text(COPY)
        self.launcher = self.checkout / 'pi-autowork/bin/autowork'
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_bytes(LAUNCHER.read_bytes())
        self.launcher.chmod(self.launcher.stat().st_mode | stat.S_IXUSR)

    def run_launcher(self, argv=('version',), **env):
        started = {key: value for key, value in os.environ.items() if key != 'AUTOWORK_TOOLSET'}
        started.update(PI_AUTOWORK_STATE_DIR=str(self.state), **env)
        return subprocess.run([str(self.launcher), *argv], capture_output=True, text=True,
                              env=started, timeout=60)

    def test_the_installed_toolset_runs_by_default(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ran installed version')

    def test_a_named_checkout_overrides_the_installation_for_development(self):
        result = self.run_launcher(AUTOWORK_TOOLSET=str(self.checkout))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ran checkout version')

    def test_without_an_installation_the_launcher_runs_its_own_checkout(self):
        for path in (self.installed / 'pi-autowork/pi_autowork/command.py',):
            path.unlink()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ran checkout version')

    def test_a_symlink_to_the_installation_still_runs_the_installation_once(self):
        target = self.installed / 'pi-autowork/bin/autowork'
        target.parent.mkdir()
        target.write_bytes(LAUNCHER.read_bytes())
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        link = self.base / 'bin/autowork'
        link.parent.mkdir()
        link.symlink_to(target)
        result = subprocess.run([str(link), 'version'], capture_output=True, text=True,
                                env=dict(os.environ, PI_AUTOWORK_STATE_DIR=str(self.state)), timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'ran installed version')


class ReportTests(unittest.TestCase):
    def test_a_checkout_reports_its_revision_and_a_snapshot_reports_its_name(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder) / 'repo'
            repo.mkdir()
            git = ['git', '-C', str(repo), '-c', 'user.email=t@example.com', '-c', 'user.name=t']
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            subprocess.run([*git, 'commit', '-q', '--allow-empty', '-m', 'one'], check=True)
            head = subprocess.run([*git, 'rev-parse', '--short', 'HEAD'], capture_output=True,
                                  text=True, check=True).stdout.strip()
            self.assertEqual(build.revision(repo), head)
            snapshot = Path(folder) / '0123456789abcdef0123456789abcdef01234567'
            snapshot.mkdir()
            self.assertEqual(build.revision(snapshot), '01234567')
            (snapshot / 'not-a-revision').mkdir()
            self.assertEqual(build.revision(snapshot / 'not-a-revision'), '')

    def test_skew_and_the_repair_are_named_only_when_the_copies_differ(self):
        viewer = {'root': '/dev', 'revision': 'aaaaaaa'}
        installed = {'root': '/installed', 'revision': 'aaaaaaa'}
        self.assertEqual(build.warning({'viewer': viewer, 'installed': installed}), '')
        self.assertEqual(build.line({'viewer': viewer, 'installed': installed}),
                         'viewer aaaaaaa (/dev) · installed aaaaaaa (/installed)')
        stale = {'viewer': viewer, 'installed': {'root': '/installed', 'revision': 'bbbbbbb'}}
        self.assertTrue(build.skew(stale))
        self.assertEqual(build.warning(stale),
                         'viewer aaaaaaa is not installed bbbbbbb: run autowork update')
        self.assertTrue(build.line(stale).endswith('not in sync: run autowork update'))
        self.assertFalse(build.skew({'viewer': viewer, 'installed': None}))
        self.assertEqual(build.line({'viewer': viewer, 'installed': None}),
                         'viewer aaaaaaa (/dev) · no installed toolset')

    def test_the_report_reads_the_installed_toolset_below_the_state_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'state'
            (state / 'installed/pi-autowork/pi_autowork').mkdir(parents=True)
            (state / 'installed/pi-autowork/pi_autowork/command.py').touch()
            found = build.report({'PI_AUTOWORK_STATE_DIR': str(state)}, viewer=Path(folder) / 'checkout')
            self.assertEqual(found['installed']['root'], str(state / 'installed'))
            self.assertFalse(build.skew(found))
            self.assertEqual(build.report({'PI_AUTOWORK_STATE_DIR': str(Path(folder) / 'empty')})['installed'], None)


if __name__ == '__main__':
    unittest.main()
