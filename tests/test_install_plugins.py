"""Installer integration tests; the fake CLI never touches real Hermes profiles."""
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from src_fixture import copy_sources


SCRIPT = Path(__file__).resolve().parents[1] / 'install-plugins.sh'
MANIFEST = ('https://hermes-agent.nousresearch.com/docs/plugins/sample-addon all profiles\n'
            'https://hermes-agent.nousresearch.com/docs/plugins/example-plugin default profile only\n')


class InstallPluginsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo with spaces'
        (self.repo / 'plugins').mkdir(parents=True)
        self.script = self.repo / 'install-plugins.sh'
        copy_sources(self.repo, entries=('install-plugins.sh', 'plugin.yaml', 'plugins/defaults.json'))
        self.manifest = self.repo / 'plugins/PLUGINS.md'
        self.manifest.write_text(MANIFEST)
        self.hermes_root = self.root / 'hermes home'
        for name in ('coder', 'research', 'deleted'):
            profile = self.hermes_root / 'profiles' / name
            profile.mkdir(parents=True)
            (profile / 'config.yaml').write_text('')
        (self.hermes_root / 'profiles/ghost').mkdir()
        (self.hermes_root / 'profiles/.deleted').mkdir()
        (self.hermes_root / 'profiles/.deleted/deleted').touch()
        (self.hermes_root / 'active_profile').write_text('research')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'hermes'
        fake.write_text('''#!/bin/bash
printf '%s|%s\\n' "$HERMES_HOME" "$*" >> "$CALL_LOG"
[[ "${FAIL_PROFILE:-}" != "$2" ]]
''')
        fake.chmod(0o755)
        self.log = self.root / 'calls'
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'],
                        HERMES_HOME=str(self.hermes_root), CALL_LOG=str(self.log))

    def run_installer(self, *args):
        return subprocess.run(['bash', str(self.script), '--sources-only', *args], cwd=self.root,
                              env=self.env, text=True, capture_output=True, timeout=30)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_identity_matrix_before_any_component_mutation(self):
        for case in ('canonical', 'legacy-kit', 'legacy-manifest', 'same-source', 'distinct-source', 'foreign', 'missing', 'malformed', 'malformed-body', 'quoted-conflict'):
            with self.subTest(case=case):
                plugins = self.hermes_root / 'profiles/coder/plugins'
                if plugins.exists():
                    shutil.rmtree(plugins)
                plugins.mkdir()
                if case in ('canonical', 'same-source', 'distinct-source'):
                    (plugins / 'kit').symlink_to(self.repo)
                if case in ('legacy-kit', 'same-source'):
                    (plugins / 'autowork').symlink_to(self.repo)
                elif case not in ('canonical',):
                    legacy = plugins / 'autowork'
                    legacy.mkdir()
                    if case != 'missing':
                        (legacy / 'plugin.yaml').write_text({
                            'legacy-manifest': 'name: autowork\n',
                            'distinct-source': 'name: kit\n',
                            'foreign': 'name: other\n',
                            'malformed': 'name: [kit]\n',
                            'malformed-body': 'name: kit\nsettings: [\n',
                            'quoted-conflict': 'name: kit\n"name": autowork\n',
                        }[case])
                    (legacy / 'private-state').write_bytes(b'keep\x00evidence')
                self.log.unlink(missing_ok=True)
                result = self.run_installer('--setup')
                if case in ('canonical', 'legacy-kit'):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('|-p coder plugins enable kit', '\n'.join(self.calls()))
                    self.assertEqual((plugins / ('kit' if case == 'canonical' else 'autowork')).resolve(), self.repo)
                    self.assertFalse((plugins / ('autowork' if case == 'canonical' else 'kit')).exists())
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(str(plugins), result.stderr)
                    self.assertEqual(self.calls(), [], 'identity failure must precede every component mutation')
                    if (plugins / 'autowork/private-state').exists():
                        self.assertEqual((plugins / 'autowork/private-state').read_bytes(), b'keep\x00evidence')

    def test_bundle_enable_timeout_reports_failure(self):
        limiter = self.bin / 'timeout'
        limiter.write_text('#!/bin/sh\n[ "$1" = 120 ] || exit 99\nshift\nprintf "%s\\n" "$*" >> "$TIMEOUT_LOG"\nexit 124\n')
        limiter.chmod(0o755)
        trace = self.root / 'timeouts'
        self.env['TIMEOUT_LOG'] = str(trace)
        result = self.run_installer('--bundle-only')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(trace.read_text().splitlines(), [
            f'hermes -p {name} plugins enable kit' for name in ('default', 'coder', 'research')])
        self.assertFalse(any('plugins enable' in row for row in self.calls()))
        self.assertIn('3 failed', result.stdout)
        self.assertIn('Kit enablement failed (coder, exit 124; 120-second limit)', result.stderr)
        self.assertIn('Inspect Hermes and rerun setup', result.stderr)

    def test_public_setup_entrypoint_preview_success_and_duplicate_failure(self):
        copy_sources(self.repo, entries=('install-skills.sh',))
        skill = self.repo / 'skills/demo'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('fixture skill\n')
        runtime = self.root / 'hermes_cli/plugins.py'
        runtime.parent.mkdir()
        runtime.write_text('def inject_message(origin=None): pass\ndef register_skill(): pass\n')
        # Native strict-YAML validation is a host boundary, not a test dependency.
        validator = self.root / '.venv/bin/python'
        validator.parent.mkdir(parents=True)
        validator.write_text('#!/bin/sh\ncase "$2" in */src/autowork_runtime/install/preflight_config.py) ;; *) exit 99 ;; esac\n[ "$3" = --core ] || exit 99\n')
        validator.chmod(0o755)
        self.env['HOME'] = str(self.root)
        command = ['bash', str(self.script), '--bundle-only', '--no-reload']
        def run(*args):
            return subprocess.run([*command, *args], cwd=self.root, env=self.env,
                                  text=True, capture_output=True, timeout=30)
        preview = run('--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertIn('plugins/kit', preview.stdout)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.hermes_root / 'skills').exists())
        result = run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Bundle setup complete', result.stdout)
        for name, home in [('default', self.hermes_root),
                           ('coder', self.hermes_root / 'profiles/coder'),
                           ('research', self.hermes_root / 'profiles/research')]:
            self.assertEqual((home / 'plugins/kit').resolve(), self.repo)
            self.assertFalse((home / 'plugins/autowork').exists())
            self.assertEqual((home / 'skills/demo/SKILL.md').read_text(), 'fixture skill\n')
            self.assertIn(str(self.hermes_root) + f'|-p {name} kit finalize --hermes-home {self.hermes_root} --bundle-only --no-reload', self.calls())
        self.assertFalse(any('enable autowork' in row for row in self.calls()))
        legacy = self.hermes_root / 'profiles/coder/plugins/autowork'
        legacy.symlink_to(self.repo)
        self.log.unlink()
        result = run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate Kit registrations', result.stdout)
        self.assertIn('reconcile registrations', result.stdout)
        self.assertEqual(self.calls(), [])
        self.assertTrue(legacy.is_symlink())
        # Owner resolves the duplicate registration, not its source or private state.
        legacy.unlink()
        self.assertEqual(run('--dry-run').returncode, 0)

    def test_profile_scopes_and_running_outside_repository(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [str(self.hermes_root) + '|' + command for command in (
            '-p default plugins install sample-addon', '-p coder plugins install sample-addon',
            '-p research plugins install sample-addon', '-p default plugins install example-plugin')])

    def test_dry_run_never_invokes_cli(self):
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn('-p default plugins install example-plugin', result.stdout)
        self.assertIn('-p coder plugins install sample-addon', result.stdout)

    def test_invalid_later_entry_prevents_every_install(self):
        self.manifest.write_text(MANIFEST + 'https://example.com/evil all profiles\n')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertIn('line 3', result.stderr)

    def test_existing_install_is_not_overwritten(self):
        target = self.hermes_root / 'plugins/sample-addon'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').write_text('name: sample-addon\n')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 3)
        self.assertFalse(any('|-p default plugins install sample-addon' in c for c in self.calls()))

    def test_failure_is_reported_but_other_targets_are_attempted(self):
        self.env['FAIL_PROFILE'] = 'coder'
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls()), 4)
        self.assertIn('sample-addon (coder)', result.stderr)

    def test_named_home_resolves_back_to_root(self):
        self.env['HERMES_HOME'] = str(self.hermes_root / 'profiles/coder')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 4)
        self.assertTrue(all(c.startswith(str(self.hermes_root) + '|') for c in self.calls()))

    def test_comments_crlf_duplicates_and_no_final_newline(self):
        self.manifest.write_bytes(('# comment\r\n\r\n' + MANIFEST + MANIFEST.rstrip()).encode())
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 4)

    def test_missing_home_and_unknown_option_fail_before_cli(self):
        for args in [('--hermes-home', str(self.root / 'absent')), ('--typo',)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_installer(*args).returncode, 0)
                self.assertEqual(self.calls(), [])

    def test_conflicting_scopes_and_empty_manifest_fail_before_cli(self):
        for manifest in ('# empty\n', MANIFEST +
                         'https://hermes-agent.nousresearch.com/docs/plugins/sample-addon default profile only\n'):
            with self.subTest(manifest=manifest):
                self.manifest.write_text(manifest)
                result = self.run_installer()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.calls(), [])

    def test_incomplete_existing_directory_reports_failure(self):
        (self.hermes_root / 'plugins/sample-addon').mkdir(parents=True)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('existing path is not a plugin', result.stderr)
        self.assertEqual(len(self.calls()), 3)

    def test_explicit_home_overrides_environment(self):
        other = self.root / 'other home'
        other.mkdir()
        result = self.run_installer('--hermes-home', str(other))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [str(other) + '|-p default plugins install sample-addon',
                                       str(other) + '|-p default plugins install example-plugin'])

    def test_github_plugin_url_and_existing_install(self):
        self.manifest.write_text('https://github.com/dietrichgebert/ponytail all profiles\n')
        target = self.hermes_root / 'plugins/ponytail'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').touch()
        (target.parent / '.install-metadata.json').write_text(json.dumps({
            'ponytail': {'source': 'https://github.com/dietrichgebert/ponytail.git'}}))
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [str(self.hermes_root) + '|' + command for command in (
            '-p coder plugins install https://github.com/dietrichgebert/ponytail',
            '-p research plugins install https://github.com/dietrichgebert/ponytail')])

    def test_skill_repository_installs_each_skill_per_profile(self):
        self.manifest.write_text('skills https://github.com/addyosmani/agent-skills all profiles\n')
        git = self.bin / 'git'
        git.write_text('''#!/bin/bash
dest=${@: -1}
mkdir -p "$dest/skills/build" "$dest/skills/review"
touch "$dest/skills/build/SKILL.md" "$dest/skills/review/SKILL.md"
''')
        git.chmod(0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 6)
        self.assertIn(str(self.hermes_root) +
                      '|-p coder skills install addyosmani/agent-skills/skills/build --yes', self.calls())
        self.assertIn(str(self.hermes_root) +
                      '|-p default skills install addyosmani/agent-skills/skills/review --yes', self.calls())

    def test_github_installed_name_comes_from_provenance(self):
        self.manifest.write_text('https://github.com/owner/repo default profile only\n')
        target = self.hermes_root / 'plugins/different-name'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').touch()
        (target.parent / '.install-metadata.json').write_text(json.dumps({
            'different-name': {'source': 'https://github.com/owner/repo.git'}}))
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_unrelated_github_basename_is_not_treated_as_installed(self):
        self.manifest.write_text('https://github.com/owner/repo default profile only\n')
        target = self.hermes_root / 'plugins/repo'
        target.mkdir(parents=True)
        (target / 'plugin.yaml').touch()
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_graphify_cli_is_not_sent_to_plugin_installer(self):
        self.manifest.write_text('https://github.com/Graphify-Labs/graphify all profiles\n' + MANIFEST)
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('graphify', result.stdout.lower())
        self.assertEqual(len(self.calls()), 0)

    def test_enable_and_dependency_consent_are_explicit_flags(self):
        result = self.run_installer('--enable', '--yes-deps')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 4)
        self.assertTrue(all(c.endswith('--enable --yes-deps') for c in self.calls()))

    def test_setup_applies_gateway_default_only_where_bundle_is_installed(self):
        self.manifest.write_text('https://hermes-agent.nousresearch.com/docs/plugins/example-plugin default profile only\n')
        plugin = self.hermes_root / 'profiles/coder/plugins/autowork'
        plugin.parent.mkdir(parents=True)
        plugin.symlink_to(self.repo)
        result = self.run_installer('--setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        for profile in ('coder', 'default'):
            self.assertIn(str(self.hermes_root) + f'|-p {profile} config set plugins.entries.kit.allow_gateway_injection true', self.calls())
            self.assertNotIn(str(self.hermes_root) + f'|-p {profile} config set plugins.entries.autowork.allow_gateway_injection true', self.calls())

    def test_setup_uses_each_installed_profiles_explicit_or_default_policy(self):
        self.manifest.write_text('https://hermes-agent.nousresearch.com/docs/plugins/example-plugin default profile only\n')
        plugin = self.hermes_root / 'profiles/coder/plugins/autowork'
        plugin.parent.mkdir(parents=True)
        plugin.symlink_to(self.repo)
        (self.hermes_root / 'profiles/coder/config.yaml').write_text(
            'plugins:\n  entries:\n    kit:\n      settings:\n        runtime_policy: autonomous\n')
        (self.hermes_root / 'profiles/research/config.yaml').write_text(
            'approvals:\n  mode: smart\nagent:\n  max_turns: 37\n')
        preview = self.run_installer('--setup', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('Runtime policy=autonomous (coder)', preview.stdout)
        self.assertIn('command approvals=off (coder)', preview.stdout)
        self.assertIn('Runtime policy=interactive (default)', preview.stdout)
        self.assertIn('Plan: config approvals.mode=smart (research)', preview.stdout)
        self.assertIn('Plan: config agent.max_turns=37 (research)', preview.stdout)
        self.assertEqual(self.calls(), [])
        result = self.run_installer('--setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.hermes_root) + '|-p coder config set approvals.mode off', self.calls())
        self.assertIn(str(self.hermes_root) + '|-p default config set approvals.mode manual', self.calls())
        self.assertIn(str(self.hermes_root) + '|-p research config set agent.max_turns 37', self.calls())

    def test_bundle_only_installs_and_enables_every_live_profile_idempotently(self):
        preview = self.run_installer('--bundle-only', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.hermes_root / 'plugins').exists())
        for _ in range(2):
            result = self.run_installer('--bundle-only')
            self.assertEqual(result.returncode, 0, result.stderr)
        for name, home in [('default', self.hermes_root),
                           ('coder', self.hermes_root / 'profiles/coder'),
                           ('research', self.hermes_root / 'profiles/research')]:
            self.assertEqual((home / 'plugins/kit').resolve(), self.repo)
            self.assertIn(str(self.hermes_root) + f'|-p {name} plugins enable kit', self.calls())
        self.assertFalse((self.hermes_root / 'profiles/deleted/plugins').exists())
        self.assertFalse((self.hermes_root / 'profiles/ghost/plugins').exists())
        self.assertFalse(any('plugins install' in c or 'skills install' in c for c in self.calls()))

    def test_bundle_install_preserves_conflicting_existing_path(self):
        target = self.hermes_root / 'profiles/coder/plugins/autowork'
        target.mkdir(parents=True)
        marker = target / 'user-file'
        marker.write_text('preserve')
        result = self.run_installer('--bundle-only')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'preserve')
        self.assertFalse(any('|-p coder plugins enable' in c for c in self.calls()))

    def test_permissions_are_applied_before_activation_for_every_profile(self):
        result = self.run_installer('--bundle-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        for profile in ('default', 'coder', 'research'):
            prefix = str(self.hermes_root) + f'|-p {profile} '
            enabled = calls.index(prefix + 'plugins enable kit')
            for setting in ('plugins.entries.kit.allow_gateway_injection true',
                            'approvals.mode manual', 'approvals.destructive_slash_confirm true',
                            'approvals.mcp_reload_confirm true', 'agent.max_turns 90',
                            'skills.platform_disabled {}'):
                self.assertLess(calls.index(prefix + 'config set ' + setting), enabled)

    def test_setup_honors_runtime_defaults_opt_out(self):
        # settings wins over the legacy config subtree, exactly like _opted_out.
        (self.hermes_root / 'profiles/coder/config.yaml').write_text(
            'plugins:\n  entries:\n    autowork:\n      settings:\n        apply_runtime_defaults: false\n')
        (self.hermes_root / 'profiles/research/config.yaml').write_text(
            'plugins:\n  entries:\n    autowork:\n      config:\n        apply_runtime_defaults: false\n'
            '      settings:\n        apply_runtime_defaults: true\n')
        self.manifest.write_text('https://hermes-agent.nousresearch.com/docs/plugins/example-plugin default profile only\n')
        preview = self.run_installer('--bundle-only', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('runtime-defaults opt-out (coder)', preview.stdout)
        self.assertFalse(any(line.startswith('Plan: config ') and line.endswith('(coder)')
                             for line in preview.stdout.splitlines()))
        self.assertIn('Plan: config approvals.mode=manual (research)', preview.stdout)
        for args in (('--bundle-only',), ('--setup',)):
            self.log.unlink(missing_ok=True)
            result = self.run_installer(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = self.calls()
            prefix = str(self.hermes_root) + '|-p '
            self.assertFalse([c for c in calls if c.startswith(prefix + 'coder config set')], calls)
            self.assertIn(prefix + 'coder plugins enable kit', calls)
            for profile in ('default', 'research'):
                for setting in ('plugins.entries.kit.allow_gateway_injection true',
                                'approvals.mode manual', 'skills.platform_disabled {}'):
                    self.assertIn(prefix + f'{profile} config set ' + setting, calls)

    def test_skill_dry_run_does_not_clone_or_install(self):
        self.manifest.write_text('skills https://github.com/addyosmani/agent-skills all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\necho git >> "$CALL_LOG"\nexit 1\n')
        git.chmod(0o755)
        result = self.run_installer('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertIn('addyosmani/agent-skills', result.stdout)
        self.assertIn('research', result.stdout)

    def test_skill_clone_failure_is_reported(self):
        self.manifest.write_text('skills https://github.com/addyosmani/agent-skills all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nexit 1\n')
        git.chmod(0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('clone', result.stderr.lower())
        self.assertEqual(self.calls(), [])

    def test_empty_skill_repository_reports_failure(self):
        self.manifest.write_text('skills https://github.com/owner/empty all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nmkdir -p "${@: -1}/skills"\n')
        git.chmod(0o755)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('no skills/', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_skill_install_failures_do_not_stop_other_profiles(self):
        self.manifest.write_text('skills https://github.com/owner/pack all profiles\n')
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nmkdir -p "${@: -1}/skills/build"\ntouch "${@: -1}/skills/build/SKILL.md"\n')
        git.chmod(0o755)
        self.env['FAIL_PROFILE'] = 'coder'
        result = self.run_installer()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls()), 3)
        self.assertIn('skill build (coder)', result.stderr)


if __name__ == '__main__':
    unittest.main()
