"""install.sh's component menu against fake host CLIs in a throwaway HOME.

The Hermes item runs only as a dry run here: the real setup changes live profiles.
"""
import json
import os
import pty
import shutil
import stat
from types import SimpleNamespace
import selectors
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / 'install.sh'
sys.path.insert(0, str(ROOT / "scripts"))
import install_menu  # noqa: E402
NEW = 'git:github.com/TrebuchetDynamics/kit'

# A fake pi: `pi list` reads installed sources from a file; install and remove edit it.
PI = r'''#!/usr/bin/env bash
echo "pi $*" >> "$FAKE_LOG"
db=$FAKE_HOME/pi-installed
touch "$db"
case $1 in
  list) echo "User packages:"; while read -r src; do [[ -n $src ]] && { echo "  $src"; echo "    $FAKE_HOME/pkg/${src##*/}"; }; done < "$db" ;;
  install) echo "$2" >> "$db"; mkdir -p "$FAKE_HOME/pkg/${2##*/}/scripts" "$FAKE_HOME/pkg/${2##*/}/pi-autowork/bin";
           : > "$FAKE_HOME/pkg/${2##*/}/pi-autowork/bin/autowork" ;;
  remove) grep -vxF "$2" "$db" > "$db.new"; mv "$db.new" "$db" ;;
esac
'''
LOGGING = '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "$FAKE_LOG"\n'


class InstallMenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.bin = self.home / 'fakebin'
        self.bin.mkdir()
        self.log = self.home / 'calls.log'
        self.log.touch()
        self.fake('pi', PI)
        # Every full-suite fixture stays offline, even when Octet is absent.
        self.upstream = self.home / 'upstream-install.sh'
        self.upstream.write_text('''#!/bin/sh
set -eu
printf 'octet-installer %s|%s|%s\\n' "$OCTET_INSTALL_DIR" "$OCTET_NO_MODIFY_PATH" "$*" >> "$FAKE_LOG"
python3 -c 'import hashlib, sys; print("installer-sha256 " + hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$0" >> "$FAKE_LOG"
case "${OCTET_FIXTURE_STAGE:-}" in
  installer|signature|checksum|pre-version) echo "$OCTET_FIXTURE_STAGE refusal" >&2; exit 9 ;;
esac
mkdir -p "$OCTET_INSTALL_DIR"
case "${OCTET_FIXTURE_STAGE:-}" in
  version-exit) printf '#!/bin/sh\\nexit 8\\n' > "$OCTET_INSTALL_DIR/octet" ;;
  version-empty) printf '#!/bin/sh\\nexit 0\\n' > "$OCTET_INSTALL_DIR/octet" ;;
  version-invalid) printf '#!/bin/sh\\necho not-octet\\n' > "$OCTET_INSTALL_DIR/octet" ;;
  *) printf '#!/bin/sh\\necho octet 1.2.3\\n' > "$OCTET_INSTALL_DIR/octet" ;;
esac
chmod 755 "$OCTET_INSTALL_DIR/octet"
if [ "${OCTET_FIXTURE_STAGE:-}" = post-placement ]; then
  echo 'installed octet binary version mismatch' >&2; exit 9
fi
''')
        self.fake('curl', '''#!/usr/bin/env python3
import os, pathlib, shutil, stat, sys
args = sys.argv[1:]
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write('curl ' + ' '.join(args) + '\\n')
if args[-1] != 'https://octet.skaft.org/install':
    raise SystemExit('unexpected network request')
if os.environ.get('OCTET_FIXTURE_STAGE') == 'download':
    raise SystemExit('fixture download failure')
dest = pathlib.Path(args[args.index('--output') + 1])
assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
assert stat.S_IMODE(dest.stat().st_mode) == 0o600
shutil.copyfile(pathlib.Path(os.environ['FAKE_HOME']) / 'upstream-install.sh', dest)
if os.environ.get('OCTET_FIXTURE_STAGE') == 'download-empty':
    dest.write_bytes(b'')
elif os.environ.get('OCTET_FIXTURE_STAGE') == 'download-oversize':
    dest.write_bytes(b'x' * 1048577)
''')
        # A ready private SDK environment keeps these installer-orchestration
        # fixtures offline. The RPC installer has separate real wheel qualification.
        sdk = self.home / '.local/state/pi-autowork/runtimes/pi-rpc-0.2.6/bin/python'
        sdk.parent.mkdir(parents=True)
        sdk.write_text('#!/bin/sh\necho 0.2.6\n')
        sdk.chmod(0o755)
        for name in ('claude', 'codex', 'systemctl'):
            self.fake(name, LOGGING)
        self.env = {'PATH': f'{self.bin}:/usr/bin:/bin', 'HOME': str(self.home), 'FAKE_LOG': str(self.log),
                    'FAKE_HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config'),
                    'PI_AUTOWORK_SYSTEMCTL': str(self.bin / 'systemctl'), 'LANG': 'C.UTF-8',
                    'TMPDIR': str(self.home), 'AUTOWORK_INSTALL_NO_PULL': '1'}  # never pull the checkout under test
        # In-process installer tests must also never discover the real host fleet.
        self.environment = patch.dict(os.environ, self.env)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def fake(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def install(self, *args, stdin=None, env=None):
        return subprocess.run(['bash', str(INSTALL), *args], env={**self.env, **(env or {})}, input=stdin,
                              capture_output=True, text=True, timeout=120)

    def calls(self, prefix=''):
        return [c for c in self.log.read_text().splitlines() if c.startswith(prefix)]

    def test_restart_services_uses_immediate_active_only_restart_and_tries_every_service(self):
        listed = subprocess.CompletedProcess([], 0,
            'pi-autowork@repo.service loaded active running Runner\n'
            'hermes-gateway.service loaded active running Hermes\n'
            'kit-helper.service loaded active running Helper\n'
            'unrelated.service loaded active running Other\n', '')
        with patch.object(install_menu.platform, 'system', return_value='Linux'), \
                patch.object(install_menu.shutil, 'which', return_value='/bin/systemctl'), \
                patch.object(install_menu.subprocess, 'run', return_value=listed) as discover, \
                patch.object(install_menu, 'run_command', side_effect=[(1, 'failure'), (0, ''), (0, '')]) as run:
            with self.assertRaisesRegex(RuntimeError, 'hermes-gateway.service'):
                install_menu.restart_services(install_menu.Output(verbosity=0))
        self.assertIn('--state=active', discover.call_args.args[0])
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 3)
        self.assertEqual(commands[0][-2:], ['try-restart', 'hermes-gateway.service'])
        self.assertEqual(commands[-1][-5:], ['restart', '--stop-workers', '--now', '--if-active', 'repo'])

    def test_restart_phase_runs_on_unchanged_and_failed_installs_but_not_preview(self):
        item = install_menu.Item('fixture', 'Fixture', steps=[
            install_menu.Step('unchanged', run=lambda: 'already current')])
        with patch.object(install_menu, 'restart_services', return_value='restarted') as restart:
            for _ in range(2):
                self.assertEqual(install_menu.install([item], {'fixture'}), 0)
            self.assertEqual(restart.call_count, 2)
            install_menu.install([item], {'fixture'}, dry_run=True)
            self.assertEqual(restart.call_count, 2)
            item.refuse = 'fixture failure'
            self.assertEqual(install_menu.install([item], {'fixture'}), 1)
            self.assertEqual(restart.call_count, 3)

    def test_restart_failure_makes_install_fail(self):
        with patch.object(install_menu, 'restart_services', side_effect=RuntimeError('restart failed')):
            item = install_menu.Item('fixture', 'Fixture')
            self.assertEqual(install_menu.install([item], {'fixture'}), 1)

    def test_every_host_includes_bundled_ponytail_without_a_second_plugin(self):
        self.fake('hermes', LOGGING)
        result = self.install('--only', 'pi,claude,codex,hermes', '--dry-run',
                              '--hermes-home', str(self.home))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('bundled Ponytail'), 4)
        self.assertNotIn('DietrichGebert/ponytail', result.stdout)
        self.assertFalse(self.calls('pi install'))
        self.assertFalse(self.calls('claude plugin install'))
        self.assertFalse(self.calls('codex plugin add'))

    def test_list_marks_missing_hosts(self):
        out = self.install('--list').stdout
        for key in ('pi', 'autowork', 'tx', 'claude', 'codex', 'octet'):
            self.assertRegex(out, rf'{key}\s+available')
        self.assertRegex(out, r'hermes\s+unavailable.*hermes not found')

    def test_full_skips_a_stale_optional_host_launcher(self):
        self.fake('hermes', f'#!/bin/sh\nexec {self.home}/missing-hermes "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--full')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+skipped.*launcher target')
        self.assertIn('codex plugin add kit@autowork-marketplace', self.calls('codex'))
        self.assertRegex(self.install('--list').stdout, r'hermes\s+unavailable.*launcher target')

    def test_an_explicit_stale_host_fails_without_stopping_other_components(self):
        self.fake('hermes', f'#!/bin/sh\nexec {self.home}/missing-hermes "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--only', 'hermes,tx')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+failed.*launcher target')
        self.assertTrue((self.home / '.local/bin/tx').is_file())

    def test_dynamic_shell_targets_are_left_to_native_host_admission(self):
        self.fake('hermes', '#!/bin/sh\nexec "/bin/${AUTOWORK_HOST:-sh}" "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+planned')

    def test_a_working_shell_wrapper_is_available_without_executing_it(self):
        target = self.home / 'real hermes'
        marker = self.home / 'executed'
        target.write_text(f'#!/bin/sh\ntouch {marker}\n')
        target.chmod(0o755)
        self.fake('hermes', f'#!/bin/sh\nexec "{target}" "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+planned')
        self.assertFalse(marker.exists())

    def test_runner_install_survives_removing_interactive_pi(self):
        sys.path.insert(0, str(ROOT / 'pi-autowork/src'))
        from pi_autowork.coordinator import Coordinator
        from pi_autowork import service
        interactive = self.home / '.pi/agent'
        interactive.mkdir(parents=True)
        login = 'disposable-fixture-login'
        (interactive / 'auth.json').write_text(json.dumps({'fixture': login}))
        (interactive / 'settings.json').write_text(json.dumps({'defaultModel': 'fixture', 'packages': ['unwanted']}))
        (interactive / 'sessions').mkdir()
        root = self.home / '.local/state/pi-autowork'
        unit_path = self.home / '.config/systemd/user/pi-autowork@.service'
        unit_path.parent.mkdir(parents=True)
        unit_path.write_text(service.UNIT.format(env_dir=self.home / '.config/pi-autowork', script=interactive / 'removed.sh'))
        result = self.install('--only', 'autowork')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(root / 'installed/pi-autowork/bin/pi-autowork.sh'), unit_path.read_text())
        private = root / 'pi-agent'
        self.assertEqual({p.name for p in private.iterdir()}, {'settings.json', 'auth.json'})
        self.assertEqual(json.loads((private / 'settings.json').read_text()), {'defaultModel': 'fixture'})
        self.assertEqual((private / 'auth.json').read_bytes(), (interactive / 'auth.json').read_bytes())
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in private.iterdir()))
        (interactive / 'settings.json').write_text('{"defaultModel":"updated-fixture"}')
        again = self.install('--only', 'autowork')
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads((private / 'settings.json').read_text())['defaultModel'], 'fixture')
        refreshed = self.install('update', '--only', 'autowork')
        self.assertEqual(refreshed.returncode, 0, refreshed.stdout + refreshed.stderr)
        self.assertEqual(json.loads((private / 'settings.json').read_text())['defaultModel'], 'updated-fixture')
        shutil.rmtree(interactive.parent)
        owner = SimpleNamespace(cfg={'state_root': str(root), 'git_common': str(self.home / 'git')})
        environment = Coordinator.job_environment(owner)
        self.assertEqual(environment['PI_CODING_AGENT_DIR'], str(private))
        self.fake('systemctl', LOGGING + '[[ $2 == is-enabled || $2 == is-active ]] && exit 1\nexit 0\n')
        self.fake('loginctl', '#!/bin/sh\necho yes\n')
        with patch.dict(os.environ, self.env, clear=True):
            service.run('install', repo=str(self.home), base='main', script='removed-interactive-launcher',
                        workers=8, state_root=str(root), hermes_jobs='', argv0='fixture')
        saved = (self.home / '.config/pi-autowork' / f'{self.home.name}.env').read_text()
        self.assertIn(f'PI_CODING_AGENT_DIR={private}', saved)
        self.assertIn(f'PI_AUTOWORK_TOOLSET={root / "installed"}', saved)
        unit = (self.home / '.config/systemd/user/pi-autowork@.service').read_text()
        self.assertIn(str(root / 'installed/pi-autowork/bin/pi-autowork.sh'), unit)
        link = self.home / '.local/bin/autowork'
        installed = root / 'installed'
        self.assertTrue((installed / '.git').is_dir())  # not tied to the removed package's Git directory
        self.assertTrue((installed / 'pi-autowork/bin/pi-autowork.sh').is_file())
        readback = subprocess.run([str(link), 'capabilities'], env=self.env, capture_output=True, text=True)
        self.assertEqual(readback.returncode, 0, readback.stderr)
        self.assertEqual(json.loads(readback.stdout)['toolset'], str(installed))
        self.assertNotIn(login, result.stdout + result.stderr + again.stdout + again.stderr + refreshed.stdout + refreshed.stderr
                         + readback.stdout + readback.stderr + self.log.read_text())

    def test_all_installs_every_available_item_in_order(self):
        result = self.install('--all')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])
        # The cached plugin is dropped first: Claude Code caches by version, and a reinstall of the
        # same version kept the old workflows.
        self.assertEqual(self.calls('claude'), ['claude plugin marketplace add TrebuchetDynamics/kit',
                                                'claude plugin marketplace update autowork',
                                                'claude plugin uninstall --keep-data kit@autowork',
                                                'claude plugin install kit@autowork'])
        self.assertEqual(self.calls('codex'), ['codex plugin marketplace remove autowork-marketplace',
                                               'codex plugin marketplace add TrebuchetDynamics/kit --ref main',
                                               'codex plugin marketplace upgrade autowork-marketplace',
                                               'codex plugin remove kit@autowork-marketplace',
                                               'codex plugin add kit@autowork-marketplace'])
        link = self.home / '.local/bin/autowork'
        self.assertEqual(Path(os.readlink(link)), self.home / '.local/state/pi-autowork/installed/pi-autowork/bin/autowork')
        self.assertEqual((self.home / '.local/bin/tx').read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertTrue((self.home / '.local/share/bash-completion/completions/tx').is_file())
        self.assertTrue((self.home / '.tmux.conf').is_file())  # none existed
        self.assertRegex(result.stdout, r'hermes\s+skipped\s+hermes not found')
        self.assertRegex(result.stdout, r'tx\s+installed')
        self.assertRegex(result.stdout, r'octet\s+installed.*octet 1.2.3')
        self.assertEqual(len(self.calls('octet-installer')), 1)
        self.assert_octet_skills()
        self.assertLess(self.calls().index('codex plugin add kit@autowork-marketplace'),
                        next(i for i, call in enumerate(self.calls()) if call.startswith('octet-installer')))

    def test_codex_install_continues_when_marketplace_is_not_configured_or_installed(self):
        self.fake('codex', LOGGING + '''
if [[ $2 == marketplace && $3 == remove ]]; then
  echo 'Error: marketplace `autowork-marketplace` is not configured or installed' >&2
  exit 1
fi
''')
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('codex plugin marketplace add TrebuchetDynamics/kit --ref main',
                      self.calls('codex'))
        self.assertIn('codex plugin add kit@autowork-marketplace', self.calls('codex'))
        self.assertRegex(result.stdout, r'codex\s+installed')

    def test_codex_marketplace_removal_errors_still_fail_the_install(self):
        self.fake('codex', LOGGING + '''
if [[ $2 == marketplace && $3 == remove ]]; then
  echo 'Error: permission denied while removing marketplace' >&2
  exit 1
fi
''')
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('permission denied', result.stdout)
        self.assertEqual(self.calls('codex'), [
            'codex plugin marketplace remove autowork-marketplace'])
        self.assertRegex(result.stdout, r'codex\s+failed')

    def test_update_runs_the_same_items_as_a_full_install(self):
        result = self.install('update')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Autowork suite update', result.stdout)
        self.assert_octet_skills()
        self.assertRegex(result.stdout, r'octet\s+installed.*octet 1.2.3')
        self.assertIn(f'pi install {NEW}', self.calls('pi'))
        self.assertIn('claude plugin install kit@autowork', self.calls('claude'))
        self.assertIn('codex plugin add kit@autowork-marketplace', self.calls('codex'))

    def assert_octet_skills(self):
        root = self.home / '.octet/skills'
        sources = sorted((ROOT / 'adapters/skills').glob('*/SKILL.md'))
        self.assertGreater(len(sources), 0)
        self.assertEqual({p.parent.name for p in root.glob('*/SKILL.md')},
                         {p.parent.name for p in sources})
        for source in sources:
            target = root / source.parent.name / 'SKILL.md'
            self.assertFalse(target.is_symlink())
            body = target.read_text()
            self.assertEqual(body.partition('\n---\n')[0], source.read_text().partition('\n---\n')[0])
            self.assertIn(f'`{source}`', body)
            self.assertIn(f'`{source.parent}`', body)
            prompt = self.home / '.octet/prompts' / f'kit-{source.parent.name}.md'
            self.assertIn(f'`{source}`', prompt.read_text())
            self.assertIn('$@', prompt.read_text())
        for selector in json.loads((ROOT / 'skills/autoresearch/UPSTREAM.json').read_text())['commands']:
            prompt = self.home / '.octet/prompts' / f'kit-autoresearch-{selector}.md'
            self.assertIn(f'Selected subcommand: {selector}', prompt.read_text())
        self.assertIn('Selected mode: challenge',
                      (self.home / '.octet/prompts/kit-grill-me.md').read_text())

    def test_octet_prompts_preserve_existing_files_and_forward_arguments(self):
        target = self.home / '.octet/prompts/kit-autowork.md'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'custom prompt\xff')
        unrelated = target.parent / 'personal.md'
        unrelated.write_text('personal prompt')
        with patch.object(install_menu, 'HOME', self.home):
            install_menu.install_octet_skills()
            first_stat = target.stat()
            self.assertIn('(0 updated)', install_menu.install_octet_skills())
        self.assertEqual(target.with_name('kit-autowork.md.bak').read_bytes(), b'custom prompt\xff')
        self.assertEqual(target.stat().st_mtime_ns, first_stat.st_mtime_ns)
        self.assertIn('$@', target.read_text())
        self.assertEqual(unrelated.read_text(), 'personal prompt')

    def test_octet_skills_preserve_existing_files_and_refresh_idempotently(self):
        root = self.home / '.octet/skills'
        target = root / 'autowork/SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'custom workflow\xff')
        backup = target.with_name('SKILL.md.bak')
        backup.write_text('earlier backup')
        unrelated = root / 'personal/SKILL.md'
        unrelated.parent.mkdir()
        unrelated.write_text('personal workflow')
        config = self.home / '.octet/config.toml'
        config.write_text('# user configuration\n')
        with patch.object(install_menu, 'HOME', self.home):
            result = install_menu.install_octet_skills()
            self.assertIn('preserved previous files', result)
            self.assertEqual(backup.read_text(), 'earlier backup')
            self.assertEqual(target.with_name('SKILL.md.bak.1').read_bytes(), b'custom workflow\xff')
            first_stat = target.stat()
            self.assertIn('(0 updated)', install_menu.install_octet_skills())
            self.assertEqual(target.stat().st_mtime_ns, first_stat.st_mtime_ns)
            self.assertFalse(target.with_name('SKILL.md.bak.2').exists())
            target.write_text('edited installed workflow')
            install_menu.install_octet_skills()
            self.assertEqual(target.with_name('SKILL.md.bak.2').read_text(), 'edited installed workflow')
        self.assertEqual(unrelated.read_text(), 'personal workflow')
        self.assertEqual(config.read_text(), '# user configuration\n')

    def test_octet_skills_replace_entrypoint_symlink_without_writing_through_it(self):
        original = self.home / 'custom-skill.md'
        original.write_text('keep me')
        target = self.home / '.octet/skills/autowork/SKILL.md'
        target.parent.mkdir(parents=True)
        target.symlink_to(original)
        with patch.object(install_menu, 'HOME', self.home):
            install_menu.install_octet_skills()
        self.assertEqual(original.read_text(), 'keep me')
        self.assertTrue(target.with_name('SKILL.md.bak').is_symlink())
        self.assert_octet_skills()

    def test_octet_skills_refuse_symlinked_directories(self):
        outside = self.home / 'outside'
        outside.mkdir()
        for index, relative in enumerate(('.octet', '.octet/skills', '.octet/skills/autowork', '.octet/prompts')):
            with self.subTest(relative=relative):
                home = self.home / str(index)
                redirected = home / relative
                redirected.parent.mkdir(parents=True)
                redirected.symlink_to(outside, target_is_directory=True)
                with patch.object(install_menu, 'HOME', home):
                    with self.assertRaisesRegex(OSError, 'regular directory'):
                        install_menu.install_octet_skills()
                self.assertFalse(list(outside.iterdir()))
                self.assertFalse(list(home.glob('.octet/skills/*/SKILL.md')))

    def test_octet_install_is_idempotent_but_update_refreshes(self):
        dest = self.home / 'custom bin'
        env = {'AUTOWORK_BIN_DIR': str(dest)}
        first = self.install('--only', 'octet', env=env)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        binary = dest / 'octet'
        before = binary.stat().st_mtime_ns
        skills = {p: p.stat().st_mtime_ns for p in (self.home / '.octet').rglob('*.md')}
        second = self.install('--only', 'octet', env=env)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn('already installed', second.stdout)
        self.assertEqual(len(self.calls('curl')), 1)
        self.assertEqual(len(self.calls('octet-installer')), 1)
        self.assertEqual(binary.stat().st_mtime_ns, before)
        self.assertEqual({p: p.stat().st_mtime_ns for p in skills}, skills)
        updated = self.install('update', '--only', 'octet', env=env)
        self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
        self.assertEqual(len(self.calls('octet-installer')), 2)

    def test_pi_install_is_idempotent_and_stale_registration_is_repaired(self):
        (self.home / 'pi-installed').write_text(NEW + '\n')  # absent package directory
        first = self.install('--only', 'pi')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': [], 'extensions': []}]}))
        second = self.install('--only', 'pi')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn('already installed', second.stdout)
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])
        self.assertEqual(self.calls('pi update'), [])
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertIn('Restart active Kit services', second.stdout)

    def test_octet_bootstrap_uses_official_stable_installer(self):
        import hashlib
        dest = self.home / 'custom bin'
        self.fake('octet', '#!/bin/sh\necho wrong-PATH-version; exit 4\n')
        self.assertFalse((dest / 'octet').exists())
        for args in (('--only', 'octet'), ('update', '--only', 'octet')):
            result = self.install(*args, env={'AUTOWORK_BIN_DIR': str(dest)})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f'{dest / "octet"}: octet 1.2.3', result.stdout)
        self.assertEqual(self.calls('octet-installer'), [f'octet-installer {dest}|1|'] * 2)
        self.assertEqual(self.calls('installer-sha256'),
                         ['installer-sha256 ' + hashlib.sha256(self.upstream.read_bytes()).hexdigest()] * 2)
        for call in self.calls('curl'):
            for flags in ('--proto =https', '--proto-redir =https', '--tlsv1.2',
                          '--connect-timeout 15', '--max-time 300', '--max-redirs 5'):
                self.assertIn(flags, call)
            self.assertTrue(call.endswith('https://octet.skaft.org/install'))
        self.assertFalse(list(self.home.glob('kit-octet-*')))
        self.assert_octet_skills()
        self.assertFalse(list((self.home / '.octet/skills').glob('*/SKILL.md.bak*')))
        self.assertEqual({p.name for p in (self.home / '.octet').iterdir()}, {'skills', 'prompts'})
        self.assertFalse((self.home / '.profile').exists())
        self.assertFalse(self.calls('pi install'))

    def test_octet_skill_failure_keeps_binary_and_continues_other_components(self):
        outside = self.home / 'outside'
        outside.mkdir()
        (self.home / '.octet').symlink_to(outside, target_is_directory=True)
        result = self.install('--only', 'octet,tx')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'octet\s+failed.*regular directory')
        self.assertRegex(result.stdout, r'tx\s+installed')
        self.assertTrue((self.home / '.local/bin/octet').is_file())
        self.assertFalse(list(outside.iterdir()))

    def test_octet_bootstrap_failure_stages(self):
        import contextlib
        import io
        destination = self.home / '.local/bin/octet'
        destination.parent.mkdir(parents=True)
        old = b'#!/bin/sh\necho old-octet\n'
        for stage in ('download', 'download-empty', 'download-oversize',
                      'installer', 'signature', 'checksum', 'pre-version',
                      'post-placement', 'version-exit', 'version-empty', 'version-invalid'):
            with self.subTest(stage=stage):
                destination.write_bytes(old)
                destination.chmod(0o755)
                result = self.install('--only', 'octet,tx', '-q',
                                      env={'OCTET_FIXTURE_STAGE': stage})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertRegex(result.stdout, r'octet\s+failed')
                self.assertRegex(result.stdout, r'tx\s+installed')
                if stage.startswith('download') or stage in ('installer', 'signature', 'checksum', 'pre-version'):
                    self.assertEqual(destination.read_bytes(), old)
                else:
                    self.assertNotEqual(destination.read_bytes(), old)
                    self.assertIn('partial installation', result.stdout)
                    self.assertIn('no rollback', result.stdout)
                self.assertFalse(list(self.home.glob('kit-octet-*')))
                self.assertFalse((self.home / '.octet').exists())
        for prerequisite in ('curl', 'sh', 'python3', 'uname'):
            with self.subTest(prerequisite=prerequisite), \
                 patch.object(install_menu, 'BIN', destination.parent), \
                 patch.object(install_menu.shutil, 'which',
                              side_effect=lambda name: None if name == prerequisite else '/fixture/' + name):
                output = io.StringIO()
                continued = []
                item = install_menu.octet_item(install_menu.Output('never', 0))
                independent = install_menu.Item('other', 'Independent', steps=[
                    install_menu.Step('continue', run=lambda: continued.append(True) or 'ok')])
                with contextlib.redirect_stdout(output):
                    code = install_menu.install([item, independent], {'octet', 'other'},
                                                output=install_menu.Output('never', 0))
                self.assertEqual(code, 1)
                self.assertRegex(output.getvalue(), rf'octet\s+failed.*requires {prerequisite}')
                self.assertEqual(continued, [True])

    def test_octet_platform_selection_and_read_only_modes(self):
        import contextlib
        import io
        for system, machine, libc, supported in (
                ('Linux', 'x86_64', 'glibc', True), ('Darwin', 'x86_64', '', True),
                ('Darwin', 'arm64', '', True), ('Linux', 'aarch64', 'glibc', False),
                ('Linux', 'x86_64', 'musl', False), ('Windows', 'AMD64', '', False)):
            with self.subTest(system=system, machine=machine, libc=libc), \
                 patch.object(install_menu.platform, 'system', return_value=system), \
                 patch.object(install_menu.platform, 'machine', return_value=machine), \
                 patch.object(install_menu.platform, 'libc_ver', return_value=(libc, '')):
                item = install_menu.octet_item()
                self.assertEqual(item.available, supported)
                if not supported:
                    for explicit in (False, True):
                        output = io.StringIO()
                        with contextlib.redirect_stdout(output):
                            code = install_menu.install([item], {'octet'} if explicit else set())
                        self.assertEqual(code, int(explicit))
                        self.assertIn('failed' if explicit else 'skipped', output.getvalue())
                        self.assertIn('unsupported', output.getvalue())
        for args in (('--list',), ('--only', 'octet', '--dry-run'), ('--all', '--skip', 'octet')):
            self.log.write_text('')
            result = self.install(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            if '--dry-run' in args:
                self.assertIn(f'install Kit skills in {self.home / ".octet/skills"}', result.stdout)
            self.assertFalse(self.calls('curl'))
            self.assertFalse(self.calls('octet-installer'))
            self.assertFalse((self.home / '.local/bin/octet').exists())
            self.assertFalse((self.home / '.octet').exists())

    def test_a_marketplace_from_a_configured_source_is_used_and_not_rewritten(self):
        # Claude Code refuses `marketplace add` when settings list that marketplace from
        # another source, here this repository's checkout. That source is the owner's
        # choice: the install uses it instead of failing or replacing it.
        refusal = ("its source doesn't match its extraKnownMarketplaces entry "
                   "in user or managed settings")
        self.fake('claude', '''#!/usr/bin/env bash
printf 'claude %s\\n' "$*" >> "$FAKE_LOG"
if [[ $2 == marketplace && $3 == add ]]; then
  printf 'Cannot add marketplace autowork: %s\\n' "$REFUSAL" >&2
  exit 1
fi
exit 0
''')
        self.env['REFUSAL'] = refusal
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('claude plugin uninstall --keep-data kit@autowork', self.calls('claude'))
        self.assertIn('claude plugin install kit@autowork', self.calls('claude'))
        self.assertIn('kept the existing configuration', result.stdout)
        self.assertRegex(result.stdout, r'claude\s+installed')

    def test_an_unrelated_marketplace_failure_still_fails_the_item(self):
        self.fake('claude', '''#!/usr/bin/env bash
printf 'claude %s\\n' "$*" >> "$FAKE_LOG"
if [[ $2 == marketplace && $3 == add ]]; then
  echo 'Failed to add marketplace: network unavailable' >&2
  exit 1
fi
exit 0
''')
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('network unavailable', result.stdout)
        self.assertRegex(result.stdout, r'claude\s+failed')
        self.assertNotIn('claude plugin install kit@autowork', self.calls('claude'))

    def test_a_marketplace_recording_a_folder_this_host_lacks_installs_anyway(self):
        # Settings and Claude Code's own registry can name a checkout this host does not
        # have: renamed, moved, or never cloned here. `marketplace update` then fails on
        # the missing path, so that registration is dropped instead of being required.
        gone = self.home / 'gone' / 'autowork'
        self.write_claude_config(gone)
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), [
            'claude plugin marketplace remove autowork',
            'claude plugin marketplace add TrebuchetDynamics/kit',
            'claude plugin marketplace update autowork',
            'claude plugin uninstall --keep-data kit@autowork',
            'claude plugin install kit@autowork'])
        self.assertIn('gone/autowork is gone', result.stdout)
        self.assertRegex(result.stdout, r'claude\s+installed')

    def test_a_recorded_marketplace_folder_that_exists_is_left_alone(self):
        checkout = self.home / 'checkout'
        checkout.mkdir()
        self.write_claude_config(checkout)
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('claude plugin marketplace remove autowork', self.calls('claude'))
        self.assertIn('claude plugin marketplace add TrebuchetDynamics/kit', self.calls('claude'))

    def write_claude_config(self, folder):
        """Record `folder` as the marketplace's source, the way a checkout registration does."""
        source = {'source': 'directory', 'path': str(folder)}
        (self.home / '.claude').mkdir(exist_ok=True)
        (self.home / '.claude/settings.json').write_text(
            json.dumps({'extraKnownMarketplaces': {'autowork': {'source': source}}}))
        (self.home / '.claude/plugins').mkdir(parents=True, exist_ok=True)
        (self.home / '.claude/plugins/known_marketplaces.json').write_text(
            json.dumps({'autowork': {'source': source, 'installLocation': str(folder)}}))

    def test_a_transient_preflight_race_is_retried_once(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        import install_menu
        original = install_menu.run_command
        self.addCleanup(setattr, install_menu, 'run_command', original)
        answers = [(1, 'ValueError: Destination changed since preflight: /x/skills/SKILL.md'), (0, '')]
        install_menu.run_command = lambda argv, output: answers.pop(0)
        continued = self.home / 'after-retry'
        def next_step():
            continued.touch()
            return 'finished next step'
        item = install_menu.Item('hermes', 'Hermes plugin', steps=[
            install_menu.Step('update_bundle.py', ['true'], retry_on='changed since preflight'),
            install_menu.Step('dependent step', run=next_step)])
        code = install_menu.install([item], {'hermes'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 0)
        self.assertEqual(answers, [])  # the second (successful) run consumed the queue
        self.assertTrue(continued.exists())

    def test_a_failure_without_the_retry_marker_is_not_retried(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import install_menu
        original = install_menu.run_command
        self.addCleanup(setattr, install_menu, 'run_command', original)
        seen = []

        def fake(argv, output):
            seen.append(argv)
            return 1, 'some other failure'

        install_menu.run_command = fake
        item = install_menu.Item('hermes', 'Hermes plugin', steps=[
            install_menu.Step('update_bundle.py', ['true'], retry_on='changed since preflight')])
        code = install_menu.install([item], {'hermes'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 1)
        self.assertEqual(len(seen), 1)

    def test_partial_suite_reports_structured_hermes_cause_with_bounded_fallback(self):
        import contextlib
        import io
        import json
        import sys
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        import install_menu
        failures = (
            ('native log\n' + json.dumps({'status': 'incomplete', 'error': 'Unproven checkout',
                'action': 'Preserve local commits; retry ./install.sh --only hermes'}, indent=2),
             'Unproven checkout'),
            (json.dumps({'status': 'incomplete', 'recovery': {'profiles': {
                'default': {'error': 'Native scanner denied staged source'}}},
                'action': 'Preserve backup; retry ./install.sh --only hermes'}, indent=2),
             'Native scanner denied staged source'),
            ('network unavailable\n{\n  "status": "incomplete",\n}', 'network unavailable'),
            ('x' * 4000 + '\nGit fetch failed\n}', 'Git fetch failed'),
        )
        for text, cause in failures:
            with self.subTest(cause=cause):
                items = [install_menu.Item(key, key, steps=[install_menu.Step('install', [key])])
                         for key in ('pi', 'autowork', 'tx', 'hermes', 'claude', 'codex')]
                output = io.StringIO()
                with patch.object(install_menu, 'run_command',
                        side_effect=lambda argv, _: (1, text) if argv == ['hermes'] else (0, 'ok')), \
                     contextlib.redirect_stdout(output):
                    code = install_menu.install(items, {item.key for item in items},
                                                output=install_menu.Output('never', 0))
                self.assertEqual(code, 1)
                summary = output.getvalue().split('Summary:')[1]
                self.assertIn('6 installed', summary)  # five components plus service activation
                self.assertIn(cause, summary)
                self.assertNotIn('failed    }', summary)
                self.assertLess(len(summary), 2000)
                if cause == 'Unproven checkout': self.assertIn('--only hermes', summary)

    def test_no_arguments_installs_full_suite_with_verbose_output(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])
        self.assertIn('claude plugin install kit@autowork', self.calls('claude'))
        self.assertIn('codex plugin add kit@autowork-marketplace', self.calls('codex'))
        self.assertTrue((self.home / '.local/bin/autowork').is_symlink())
        self.assertTrue((self.home / '.local/bin/tx').is_file())
        self.assertIn('$ codex plugin add kit@autowork-marketplace', result.stdout)
        self.assertRegex(result.stdout, r'octet\s+installed.*octet 1.2.3')
        self.assertRegex(result.stdout, r'hermes\s+skipped.*hermes not found')

    def test_default_install_enables_the_pi_package_without_extra_flags(self):
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [
            {'source': NEW, 'skills': [], 'extensions': []},
        ]}))
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertIn('enabled', result.stdout)

    def test_dry_run_defaults_to_the_full_suite_without_installing(self):
        self.fake('hermes', LOGGING)
        (self.home / '.hermes').mkdir()
        result = self.install('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ('pi', 'autowork', 'tx', 'hermes', 'claude', 'codex'):
            self.assertRegex(result.stdout, rf'{key}\s+planned')
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(self.calls('hermes'), [])
        self.assertRegex(result.stdout, r'octet\s+planned')
        self.assertFalse(self.calls('curl'))
        self.assertFalse(self.calls('octet-installer'))
        self.assertFalse((self.home / '.local/bin').exists())
        self.assertIn('enable the package skills and commands in Pi settings', result.stdout)

    def test_tx_keeps_an_existing_tmux_config(self):
        mine = b'set -g mouse on\n# mine\n'
        paths = ('.tmux.conf', '.tmux/style.tmux', '.tmux/git-status.sh', '.tmux/short-path.sh',
                 '.local/share/bash-completion/completions/tx', '.zsh/completions/_tx',
                 '.config/fish/completions/tx.fish')
        for relative in paths:
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(mine)
        preview = self.install('--full', '--skip', 'hermes,pi', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse((self.home / '.local/bin/tx').exists())
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stderr)
        for relative in paths:
            self.assertEqual((self.home / relative).read_bytes(), mine, relative)
        self.assertIn('kept your existing .tmux.conf', result.stdout)
        self.assertEqual(self.calls('pi install'), [])
        config = self.home / '.tmux.conf'
        config.unlink()
        config.symlink_to(self.home / 'absent-user-config')
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(config.is_symlink())
        self.assertFalse(config.exists())

    def test_an_installed_package_is_updated_and_its_runners_move_onto_it(self):
        (self.home / 'pi-installed').write_text(NEW + '\n')
        (self.home / 'pkg/kit').mkdir(parents=True)
        result = self.install('update', '--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('pi update'), [f'pi update {NEW}'])
        self.assertRegex(result.stdout, r'pi\s+installed')

    def test_menu_toggles_items_and_needs_a_terminal(self):
        result = self.install('--dry-run', '--menu', stdin='3 5 6\n\n', env={'AUTOWORK_INSTALL_UI': 'text'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[x] 1 Pi package', result.stdout)
        self.assertRegex(result.stdout, r'tx\s+skipped\s+not chosen')
        self.assertRegex(result.stdout, r'pi\s+planned')
        self.assertEqual(self.calls('pi install'), [])  # a dry run runs nothing
        self.assertIn('no terminal for the menu', self.install('--menu').stderr)

    def test_failed_steps_remain_failures_even_when_output_says_already(self):
        self.fake('claude', LOGGING + 'echo "boom: no network" >&2; exit 1\n')
        self.fake('codex', LOGGING + 'echo "marketplace already added" >&2; exit 4\n')
        report = self.home / 'install.jsonl'
        result = self.install('--full', '--skip', 'hermes,pi', '-q',
                              env={'AUTOWORK_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 1)
        import json
        rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['claude'], {'item': 'claude', 'status': 'failed', 'exit': 1})
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'failed', 'exit': 4})
        self.assertEqual(rows['tx'], {'item': 'tx', 'status': 'installed', 'exit': 0})
        self.assertEqual(rows['hermes'], {'item': 'hermes', 'status': 'skipped', 'exit': None})
        self.assertRegex(result.stdout, r'claude\s+failed\s+boom: no network')
        self.assertRegex(result.stdout, r'codex\s+failed.*marketplace already added')
        self.assertIn('unknown item(s): nope', self.install('--only', 'nope').stderr)
        (self.bin / 'codex').unlink()
        self.install('--full', '--skip', 'hermes,pi', '-q',
                     env={'AUTOWORK_INSTALL_REPORT': str(report)})
        rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'skipped', 'exit': None})

    def test_failed_marketplace_update_preserves_plugin_and_continues_other_hosts(self):
        self.fake('claude', LOGGING + '''
if [[ "$*" == "plugin marketplace update autowork" ]]; then
    echo "fixture marketplace unavailable" >&2
    exit 23
fi
''')
        report = self.home / 'install.jsonl'
        result = self.install('--only', 'claude,codex', '-q',
                              env={'AUTOWORK_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), [
            'claude plugin marketplace add TrebuchetDynamics/kit',
            'claude plugin marketplace update autowork'])
        self.assertIn('codex plugin add kit@autowork-marketplace', self.calls('codex'))
        import json
        rows = {row['item']: row for row in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['claude'], {'item': 'claude', 'status': 'failed', 'exit': 23})
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'installed', 'exit': 0})

    def test_step_exceptions_stop_only_the_failed_component(self):
        import contextlib
        import io
        for failure in ('missing executable', 'callable OS error', 'callable subprocess error'):
            with self.subTest(failure=failure):
                dependent, independent = [], []
                def fail():
                    if failure == 'callable OS error':
                        raise OSError('fixture denied')
                    raise subprocess.CalledProcessError(7, 'fixture')
                step = (install_menu.Step('missing executable', [str(self.home / 'absent')])
                        if failure == 'missing executable' else install_menu.Step('failed callable', run=fail))
                items = [install_menu.Item('failed', 'Failed component', steps=[step,
                             install_menu.Step('dependent step', run=lambda: dependent.append('ran') or 'ok')]),
                         install_menu.Item('other', 'Independent component', steps=[
                             install_menu.Step('independent step', run=lambda: independent.append('ran') or 'ok')])]
                with contextlib.redirect_stdout(io.StringIO()):
                    code = install_menu.install(items, {'failed', 'other'}, output=install_menu.Output('never', 0))
                self.assertEqual(code, 1)
                self.assertEqual(dependent, [])
                self.assertEqual(independent, ['ran'])

    def test_exhausted_retry_stops_dependent_steps_and_preserves_failure_receipt(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        attempts = self.home / 'attempts'
        report = self.home / 'install.jsonl'
        continued = []
        script = (f'from pathlib import Path; p = Path({str(attempts)!r}); '
                  'p.write_text(p.read_text() + "x" if p.exists() else "x"); '
                  'print("changed since preflight"); raise SystemExit(23)')
        item = install_menu.Item('retry', 'Retry fixture', steps=[
            install_menu.Step('retryable command', [sys.executable, '-c', script],
                              retry_on='changed since preflight'),
            install_menu.Step('dependent step', run=lambda: continued.append('ran') or 'ok')])
        with patch.dict(os.environ, AUTOWORK_INSTALL_REPORT=str(report)), contextlib.redirect_stdout(io.StringIO()):
            code = install_menu.install([item], {'retry'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 1)
        self.assertEqual(attempts.read_text(), 'xx')
        self.assertEqual(continued, [])
        rows = [json.loads(line) for line in report.read_text().splitlines()]
        self.assertEqual(rows[0], {'item': 'retry', 'status': 'failed', 'exit': 23})
        self.assertEqual(rows[1], {'item': 'services', 'status': 'installed', 'exit': 0})

    def test_full_selects_all_hosts_and_bundled_skills(self):
        self.fake('hermes', LOGGING)
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ('pi', 'autowork', 'tx', 'hermes', 'claude', 'codex'):
            self.assertRegex(result.stdout, rf'{key}\s+planned')
        self.assertIn('codex plugin add kit@autowork-marketplace', result.stdout)
        self.assertIn('setup_bundle.py', result.stdout)
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(self.calls('hermes'), [])

    def test_explicit_missing_host_fails_but_other_items_continue(self):
        result = self.install('--only', 'hermes,tx')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, r'hermes\s+failed.*hermes not found')
        self.assertTrue((self.home / '.local/bin/tx').is_file())

    def test_default_output_shows_both_child_streams(self):
        self.fake('codex', LOGGING + 'echo "skill stdout"; echo "skill stderr" >&2\n')
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skill stdout', result.stdout)
        self.assertIn('skill stderr', result.stdout)
        self.assertIn('[1/1]', result.stdout)
        self.assertNotIn('\x1b[', result.stdout)

    def test_verbose_prints_commands_and_quiet_keeps_failure_details(self):
        self.fake('codex', LOGGING + 'echo "registered skills"\n')
        result = self.install('--only', 'codex', '--verbose')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('$ codex plugin add', result.stdout)
        self.assertIn('registered skills', result.stdout)
        result = self.install('--only', 'codex', '--quiet')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('registered skills', result.stdout)
        self.assertNotIn('$ codex', result.stdout)
        self.assertRegex(result.stdout, r'codex\s+installed')
        self.fake('codex', LOGGING + 'echo "failure context"; echo "failure cause" >&2; exit 4\n')
        result = self.install('--only', 'codex', '--quiet')
        self.assertEqual(result.returncode, 1)
        self.assertIn('failure context', result.stdout)
        self.assertIn('failure cause', result.stdout)
        self.assertIn('exit 4', result.stdout)

    def test_color_controls_and_no_color_environment(self):
        for args, env, colored in (
            (('--color', 'always'), {}, True),
            (('--color', 'never'), {}, False),
            ((), {'NO_COLOR': '1', 'TERM': 'xterm-256color'}, False),
            (('--color', 'always'), {'NO_COLOR': '1'}, True),
        ):
            with self.subTest(args=args, env=env):
                result = self.install('--full', '--dry-run', *args, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual('\x1b[' in result.stdout, colored)

    def test_auto_color_uses_terminal_and_respects_opt_out(self):
        for env, colored in (({'TERM': 'xterm'}, True),
                             ({'TERM': 'dumb'}, False),
                             ({'TERM': 'xterm', 'NO_COLOR': '1'}, False)):
            with self.subTest(env=env):
                master, slave = pty.openpty()
                try:
                    result = subprocess.run(['bash', str(INSTALL), '--only', 'codex', '--dry-run'],
                                            env={**self.env, **env}, stdout=slave,
                                            stderr=subprocess.PIPE, timeout=10)
                    os.close(slave)
                    slave = None
                    chunks = []
                    while True:
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break  # Linux PTY reports EIO when its writer closes.
                        if not chunk:
                            break
                        chunks.append(chunk)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(b'\x1b[' in b''.join(chunks), colored)
                finally:
                    os.close(master)
                    if slave is not None:
                        os.close(slave)

    def test_child_output_arrives_before_command_exits(self):
        # The child cannot finish until the parent receives its prompt.
        # A capture-until-exit implementation deadlocks this handshake.
        self.fake('codex', LOGGING + 'printf "waiting for input: "; read -r answer; '
                  'test "$answer" = continue || exit 9\n')
        with subprocess.Popen(['bash', str(INSTALL), '--only', 'codex'], env=self.env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
            seen = b''
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout, selectors.EVENT_READ)
                    # marketplace remove, add, upgrade and plugin add prompt; the cache drop does not
                    for _ in range(4):
                        pending = b''
                        while b'waiting for input: ' not in pending:
                            self.assertTrue(selector.select(timeout=5), seen.decode(errors='replace'))
                            chunk = os.read(proc.stdout.fileno(), 4096)
                            self.assertTrue(chunk, seen.decode(errors='replace'))
                            pending += chunk
                            seen += chunk
                        proc.stdin.write(b'continue\n')
                        proc.stdin.flush()
                tail, _ = proc.communicate(timeout=5)
                seen += tail
                self.assertEqual(proc.returncode, 0, seen.decode(errors='replace'))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    def test_hermes_options_reach_the_hermes_item(self):
        self.fake('hermes', LOGGING)
        result = self.install('--only', 'hermes', '--dry-run', '--hermes-home', '/h', '--yes-deps')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('setup_bundle.py --yes-deps --dry-run --hermes-home /h', result.stdout)
        # Profiles with their own plugin clone (`hermes plugins install`) are updated: setup
        # would refuse them as "another checkout".
        clone = self.home / '.hermes/profiles/work/plugins/autowork'
        (clone / '.git').mkdir(parents=True)
        result = self.install('--only', 'hermes', '--dry-run')
        self.assertIn(f"update_bundle.py --hermes-home {self.home / '.hermes'}", result.stdout)
        self.assertNotIn('setup_bundle.py', result.stdout)


    def test_tx_moves_a_symlink_aside_instead_of_writing_through_it(self):
        elsewhere = self.home / 'other-checkout/tx'
        elsewhere.parent.mkdir()
        elsewhere.write_text('someone else\'s tx\n')
        (self.home / '.local/bin').mkdir(parents=True)
        (self.home / '.local/bin/tx').symlink_to(elsewhere)
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(elsewhere.read_text(), 'someone else\'s tx\n')
        self.assertFalse((self.home / '.local/bin/tx').is_symlink())
        self.assertEqual((self.home / '.local/bin/tx').read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertEqual(Path(os.readlink(self.home / '.local/bin/tx.bak')), elsewhere)

    def test_a_second_replacement_keeps_the_first_backup(self):
        command = self.home / '.local/bin/autowork'
        command.parent.mkdir(parents=True)
        for content in ('first script\n', 'second script\n'):
            if command.is_symlink():
                command.unlink()
            command.write_text(content)
            (self.home / '.local/bin/tx').write_text('old ' + content)
            result = self.install('--only', 'autowork,tx')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        bin = self.home / '.local/bin'
        self.assertEqual((bin / 'autowork.bak').read_text(), 'first script\n')
        self.assertEqual((bin / 'autowork.bak.1').read_text(), 'second script\n')
        self.assertEqual((bin / 'tx.bak').read_text(), 'old first script\n')
        self.assertEqual((bin / 'tx.bak.1').read_text(), 'old second script\n')

    def test_a_filtered_pi_package_counts_as_installed(self):
        package = self.home / 'pkg/autowork'
        (package / 'pi-autowork/bin').mkdir(parents=True)
        (package / 'pi-autowork/bin/autowork').touch()
        self.fake('pi', LOGGING + f'[ "$1" = list ] && printf "User packages:\\n  {NEW} (filtered)\\n    {package}\\n"\ntrue\n')
        result = self.install('--only', 'pi,autowork')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('pi update'), [])
        self.assertEqual(Path(os.readlink(self.home / '.local/bin/autowork')),
                         self.home / '.local/state/pi-autowork/installed/pi-autowork/bin/autowork')

    def test_install_clears_empty_pi_filters_that_hide_skills_and_commands(self):
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        other = {'source': 'npm:other', 'skills': []}
        settings.write_text(json.dumps({'packages': [
            {'source': NEW, 'skills': [], 'extensions': []},
            other,
        ]}))
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW, other])
        self.assertIn('enabled', result.stdout)

    def test_install_keeps_a_deliberate_partial_pi_filter(self):
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [
            {'source': NEW, 'skills': ['+./adapters/skills'], 'extensions': []},
        ]}))
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'],
                         [{'source': NEW, 'skills': ['+./adapters/skills']}])

    def test_pi_agent_directory_override_is_honored(self):
        agent = self.home / 'custom-agent'
        agent.mkdir()
        settings = agent / 'settings.json'
        settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': []}]}))
        result = self.install('--only', 'pi', env={'PI_CODING_AGENT_DIR': str(agent)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertFalse((self.home / '.pi/agent/settings.json').exists())

    def test_setup_only_hermes_options_are_refused_for_profile_clones(self):
        self.fake('hermes', LOGGING)
        (self.home / '.hermes/profiles/work/plugins/autowork/.git').mkdir(parents=True)
        for flag in ('--no-reload', '--bundle-only', '--yes-deps'):
            with self.subTest(flag=flag):
                result = self.install('--only', 'hermes,tx', flag)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertRegex(result.stdout, rf'hermes\s+failed\s+{flag} cannot apply')
                self.assertNotIn('update_bundle.py --hermes-home', self.calls())
                self.assertRegex(result.stdout, r'tx\s+installed')

    def test_hermes_without_a_home_is_unavailable_not_a_failed_setup(self):
        self.fake('hermes', LOGGING)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+skipped\s+no Hermes home at .*\.hermes')
        self.assertRegex(self.install('--list').stdout, r'hermes\s+unavailable.*no Hermes home')
        result = self.install('--only', 'hermes')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, r'hermes\s+failed\s+no Hermes home')
        self.assertEqual(self.calls('hermes'), [])

class PullCheckoutTests(unittest.TestCase):
    """install.sh first fast-forwards its own checkout (owner request 2026-10-21)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.origin, self.clone, self.other = base / 'origin.git', base / 'clone', base / 'other'
        run = lambda *a, cwd=None: subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True)
        run('git', 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        for repo in (self.clone, self.other):
            run('git', 'clone', '-q', str(self.origin), str(repo))
            run('git', '-C', str(repo), 'config', 'user.email', 'o@example.invalid')
            run('git', '-C', str(repo), 'config', 'user.name', 'O')
        (self.other / 'f').write_text('1')
        run('git', '-C', str(self.other), 'add', '-A')
        run('git', '-C', str(self.other), 'commit', '-qm', 'one')
        run('git', '-C', str(self.other), 'push', '-q', 'origin', 'main')
        run('git', '-C', str(self.clone), 'pull', '-q')
        (self.other / 'f').write_text('2')
        run('git', '-C', str(self.other), 'commit', '-qam', 'two')
        run('git', '-C', str(self.other), 'push', '-q', 'origin', 'main')
        self.run_git = run

    def head(self, repo):
        return subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout

    def test_a_clean_checkout_behind_its_upstream_is_fast_forwarded(self):
        said = []
        self.assertTrue(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertEqual(self.head(self.clone), self.head(self.other))
        self.assertIn('Updated this checkout', said[0])
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))  # up to date: quiet
        self.assertEqual(len(said), 1)

    def test_local_changes_are_installed_as_they_are(self):
        (self.clone / 'f').write_text('mine')
        said = []
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertEqual((self.clone / 'f').read_text(), 'mine')
        self.assertIn('local changes', said[0])

    def test_a_detached_or_local_only_checkout_is_not_pulled(self):
        self.run_git('git', '-C', str(self.clone), 'checkout', '-q', '--detach')
        said = []
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertIn('no upstream', said[0])
        self.assertFalse(install_menu.pull_checkout(Path(self.tmp.name), write=said.append))  # not a checkout
        self.assertEqual(len(said), 1)


if __name__ == '__main__':
    unittest.main()
