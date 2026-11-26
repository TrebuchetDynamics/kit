"""Real installer orchestration with fake child processes, no network or profiles."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src_fixture import copy_sources

ROOT = Path(__file__).resolve().parents[1]


class CompleteSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo with spaces'
        copy_sources(self.repo)
        self.home = Path(self.tmp.name) / 'hermes home'
        self.home.mkdir()
        for name in ('sample', 'deleted', 'ghost'):
            p = self.home / 'profiles' / name
            p.mkdir(parents=True)
            if name != 'ghost': (p / 'config.yaml').touch()
        (self.home / 'profiles/.deleted').mkdir()
        (self.home / 'profiles/.deleted/deleted').touch()
        self.log = self.repo / 'calls.jsonl'
        self.env = dict(os.environ, HERMES_HOME=str(self.home), LOG=str(self.log))
        # These tests exercise orchestration after admission; the real preflight
        # and its no-write failure paths are covered in test_preflight.py.
        (self.repo / 'scripts/setup_preflight.py').write_text(
            "def preflight(*args, **kwargs): return {'errors': [], 'plan': []}\n"
            "def print_plan(report): pass\n")
        for name in ('install-skills.sh', 'install-plugins.sh'):
            (self.repo / name).write_text('''#!/bin/bash
python3 - "$0" "$@" <<'CHILD'
import json,os,sys
with open(os.environ['LOG'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
sys.exit(int(os.environ.get('CHILD_FAIL','0')))
CHILD
''')
        binary = self.repo / 'hermes'
        binary.write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['LOG'],'a') as f:f.write(json.dumps(['hermes']+sys.argv[1:])+'\\n')
sys.exit(5 if os.environ.get('VERIFY_FAIL')==sys.argv[2] else 0)
''')
        binary.chmod(0o755)
        self.env['PATH'] = str(self.repo) + ':' + self.env['PATH']

    def run_setup(self, *args):
        self.assertTrue((ROOT / 'scripts/setup_bundle.py').is_file(), 'missing complete setup orchestrator')
        return subprocess.run([sys.executable, str(self.repo / 'scripts/setup_bundle.py'), *args],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_missing_declared_source_payload_refuses_before_any_stage(self):
        copy_sources(self.repo)
        for name in ('plugin.yaml', 'plugins/defaults.json', 'plugins/PLUGINS.md',
                     'src/kit_runtime/install/preflight_config.py'):
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        skill = self.repo / 'skills/example/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('fixture')
        spec = importlib.util.spec_from_file_location('copied_preflight', self.repo / 'scripts/setup_preflight.py')
        pre = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pre)
        payload = ['scripts/kit_bootstrap.py', 'src/kit_bootstrap.py',
                   *['src/kit_runtime/install/' + name for name in (
                       'install_skills.py', 'setup_bundle.py', 'setup_preflight.py',
                       'setup_runtime.py', 'install_graphify.py')]]
        before = sorted(self.home.rglob('*'))
        for name in payload:
            with self.subTest(missing=name):
                path = self.repo / name
                body = path.read_bytes()
                path.unlink()
                try:
                    with patch.object(pre, 'runtime_check', return_value=[]), \
                         patch.object(pre.shutil, 'which', return_value='/bin/available'), \
                         patch.object(pre.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stdout='')) as run:
                        report = pre.preflight(self.repo, self.home, [('default', self.home)], bundle_only=True)
                    self.assertTrue(any(name in error for error in report['errors']), report)
                    run.assert_not_called()
                    self.assertEqual(before, sorted(self.home.rglob('*')))
                finally:
                    path.write_bytes(body)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_default_installs_skills_configures_and_finalizes_each_live_profile(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(calls[0][0].endswith('install-skills.sh'))
        self.assertTrue(calls[1][0].endswith('install-plugins.sh'))
        for option in ('--sources-only', '--setup', '--enable'): self.assertIn(option, calls[1])
        self.assertEqual([c[2] for c in calls[2:]], ['default', 'sample'])
        self.assertTrue(all(c[3:5] == ['kit', 'finalize'] for c in calls[2:]))
        receipt = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(receipt['status'], 'complete')
        self.assertEqual(receipt['gateway_restart'], 'not_requested')

    def test_failure_keeps_finalization_and_nonzero_status(self):
        self.env['CHILD_FAIL'] = '9'
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([c[2] for c in self.calls() if c[0]=='hermes'], ['default','sample'])
        self.assertIn('incomplete', result.stdout.lower())
        receipt = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(receipt['gateway_restart'], 'not_requested')
        self.assertIn('failed stages', receipt['error'].lower())

    def use_suite_entrypoint(self):
        copy_sources(self.repo, entries=('install.sh', 'scripts/install_menu.py', 'scripts/checkout_lock.py',
                                         'install-skills.sh', 'install-plugins.sh', 'plugin.yaml',
                                         'plugins/defaults.json', 'plugins/PLUGINS.md'))
        # Exercise actual preflight planning and skill installation; only the
        # native runtime compatibility check needs an installed Hermes.
        shim = self.repo / 'scripts/setup_preflight.py'
        shim.write_text(shim.read_text() + '\ndef runtime_check(*args): return []\n')
        systemctl = self.repo / 'systemctl'
        systemctl.write_text('#!/bin/sh\nexit 1\n')
        systemctl.chmod(0o755)
        for name in ('alpha', 'beta'):
            skill = self.repo / 'skills' / name
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('fixture')
        hermes = self.repo / 'hermes'
        hermes.write_text(f'#!{sys.executable}\n' + '''\
import argparse, os, sys
from pathlib import Path
import yaml
profile, action, option = sys.argv[2:5]
root = Path(os.environ['HERMES_HOME'])
home = root if profile == 'default' else root / 'profiles' / profile
if (action, option) == ('plugins', 'enable'):
    raise SystemExit(0)
if (action, option) == ('config', 'set'):
    config = home / 'config.yaml'
    settings = (yaml.safe_load(config.read_text()) or {}) if config.exists() else {}
    key, value = sys.argv[-2:]
    parent = settings
    *parts, leaf = key.split('.')
    for part in parts:
        parent = parent.setdefault(part, {})
    parent[leaf] = yaml.safe_load(value)
    config.write_text(yaml.safe_dump(settings))
    raise SystemExit(0)
assert (action, option) == ('kit', 'finalize'), sys.argv
assert os.environ.get('KIT_VERIFY_SETUP_POLICY') == '1'
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
import bundle
bundle.inventory = lambda: {}
failed = profile == os.environ.get('VERIFY_FAIL')
result = dict(home=str(home), status='incomplete' if failed else 'ready', settings='current',
              gateway='unreachable' if failed else 'commands_reloaded',
              verified_gateway_commands=['kit:alpha', 'kit:beta'],
              errors=['gateway control endpoint unavailable'] if failed else [],
              note='Existing sessions may retain their previous tools.')
runtime = bundle._KIT_COMPAT.peer(vars(bundle), 'setup_runtime')
runtime.finalize = lambda *_: (result, int(failed))
parser = argparse.ArgumentParser()
bundle.setup_parser(parser)
raise SystemExit(bundle.handle_cli(parser.parse_args(['finalize', *sys.argv[5:]])))
''')

    def run_hermes_item(self, *args):
        return subprocess.run(['bash', str(self.repo / 'install.sh'), '--no-pull', '--only', 'hermes',
                               '--bundle-only', '--skip', 'orbi', *args], cwd=self.repo,
                              env=dict(self.env, HOME=self.tmp.name,
                                       PATH=f'{self.repo}:{Path(sys.executable).parent}:{self.env["PATH"]}',
                                       KIT_BIN_DIR=str(Path(self.tmp.name) / 'bin'),
                                       KIT_SYSTEMCTL=str(self.repo / 'systemctl'),
                                       KIT_INSTALL_REPORT=str(self.repo / 'install-report.jsonl')),
                              capture_output=True, text=True, timeout=30)

    def test_suite_hermes_repeat_reports_counts_status_and_timings(self):
        self.use_suite_entrypoint()
        first = self.run_hermes_item()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn('Installed: alpha (sample)', first.stdout)
        self.assertIn('Profile sample config.yaml: changed', first.stdout)
        self.assertIn('Apply: config approvals.mode=manual (sample)', first.stdout)
        repeat = self.run_hermes_item()
        self.assertEqual(repeat.returncode, 0, repeat.stdout + repeat.stderr)
        for profile in ('default', 'sample'):
            self.assertEqual(repeat.stdout.count(f'Skills ({profile}): 0 installed, 0 planned, 2 skipped, 0 failed'), 2)
            self.assertIn(f'Profile {profile}: ready; settings current; gateway commands_reloaded', repeat.stdout)
            self.assertIn(f'Profile {profile} config.yaml: unchanged', repeat.stdout)
            self.assertIn(f'Note: {profile}: Existing sessions may retain their previous tools.', repeat.stdout)
        for step in ('preflight', 'bundled skills', 'plugins and configuration', 'verify/wire sample'):
            self.assertRegex(repeat.stdout, rf'{step}: done in \d+\.\ds')
        self.assertRegex(repeat.stdout, r'profile settings: done in \d+s')
        self.assertNotIn('Plan: config ', repeat.stdout)
        self.assertNotIn('Apply: config ', repeat.stdout)
        self.assertNotIn('already exists:', repeat.stdout)
        self.assertNotIn('"verified_gateway_commands"', repeat.stdout)
        self.assertNotIn('{"status": "complete"', repeat.stdout)
        self.assertIn('Hermes: native gateway disposition not_requested', repeat.stdout)
        rows = [json.loads(line) for line in (self.repo / 'install-report.jsonl').read_text().splitlines()]
        hermes = next(row for row in rows if row['item'] == 'hermes')
        self.assertEqual(hermes['gateway_restart'], 'not_requested')
        verbose = self.run_hermes_item('--verbose')
        self.assertEqual(verbose.returncode, 0, verbose.stdout + verbose.stderr)
        self.assertIn('Skip: alpha (sample) already exists:', verbose.stdout)
        self.assertIn('"verified_gateway_commands"', verbose.stdout)
        self.assertIn('{"status": "complete"', verbose.stdout)

    def test_suite_hermes_summarizes_failures_without_hiding_the_cause(self):
        self.use_suite_entrypoint()
        self.env['VERIFY_FAIL'] = 'sample'
        failed = self.run_hermes_item()
        self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
        self.assertIn('Profile sample: incomplete; settings current; gateway unreachable', failed.stdout)
        self.assertIn('gateway control endpoint unavailable', failed.stdout)
        self.assertIn('Repair the failed stages and rerun ./install.sh --only hermes', failed.stdout)
        self.assertNotIn('"verified_gateway_commands"', failed.stdout)
        incomplete = self.home / 'profiles/sample/skills/beta/SKILL.md'
        incomplete.unlink()
        refused = self.run_hermes_item()
        self.assertNotEqual(refused.returncode, 0, refused.stdout + refused.stderr)
        self.assertIn(f'Failed: beta (sample): incomplete existing skill at {incomplete.parent}; preserved', refused.stdout)
        self.assertIn('Preflight failed; no installation stages started.', refused.stdout)
        self.assertIn('Skills (sample): 0 installed, 0 planned, 1 skipped, 1 failed', refused.stdout)
        self.assertNotIn('already exists:', refused.stdout)
        self.assertFalse(incomplete.exists())

    def test_verification_failure_does_not_claim_complete(self):
        self.env['VERIFY_FAIL'] = 'sample'
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('incomplete', result.stdout.lower())

    def test_named_profile_home_resolves_to_all_profiles_and_bundle_only_forwards(self):
        self.env['HERMES_HOME'] = str(self.home / 'profiles/sample')
        result = self.run_setup('--bundle-only', '--no-reload')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--bundle-only', self.calls()[1])
        receipt = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(receipt['gateway_restart'], 'not_requested')
        self.assertIn('deferred by --no-reload', receipt['gateway_restart_action'])
        for call in self.calls()[2:]:
            self.assertIn('--bundle-only', call)
            self.assertIn('--no-reload', call)
            self.assertEqual(call[call.index('--hermes-home')+1], str(self.home))

    def test_symlinked_profile_refuses_before_configuration(self):
        import shutil
        sample=self.home/'profiles/sample'
        shutil.rmtree(sample)
        shared=Path(self.tmp.name)/'shared'
        shared.mkdir()
        (shared/'config.yaml').touch()
        sample.symlink_to(shared,target_is_directory=True)
        self.assertNotEqual(self.run_setup().returncode,0)
        self.assertEqual(self.calls(),[])

    def test_profile_symlinks_hermes_ignores_do_not_abort_setup(self):
        profiles=self.home/'profiles'
        shared=Path(self.tmp.name)/'shared'
        shared.mkdir()
        (shared/'config.yaml').touch()
        (profiles/'.deleted/gone').touch()
        (profiles/'gone').symlink_to(shared,target_is_directory=True)
        (profiles/'Bad.Name').symlink_to(shared,target_is_directory=True)
        (profiles/'dangling').symlink_to(Path(self.tmp.name)/'missing')
        empty=Path(self.tmp.name)/'empty'
        empty.mkdir()
        (profiles/'unmarked').symlink_to(empty,target_is_directory=True)
        result=self.run_setup()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([c[2] for c in self.calls()[2:]],['default','sample'])

    def test_dry_run_never_finalizes_and_invalid_flags_never_run_children(self):
        self.assertEqual(self.run_setup('--dry-run').returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertNotEqual(self.run_setup('--unknown').returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__': unittest.main()
