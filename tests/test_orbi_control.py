"""Repository-scoped Orbi lifecycle controls (Issue #18).

The helper is exercised through real subprocess boundaries (argv only) with
temporary homes and fake `git|uv|gh|pi|node|orbi|systemctl` tools. No real
scheduler, credentials or host deployment is touched. The fixture deployment
"A" stands for an unrelated running deployment that every scenario must
preserve.
"""
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'skills/orbi/scripts/orbi_control.py'
PIN = 'ce97e015ca433a9312e5bdf69353be58ab394fd9'
OLD_PIN = 'a' * 40
OFFICIAL = 'https://github.com/orbi-build/orbi'
SECRET = 'super-secret-token-value'
REPO = 'example/kit'


def load_helper():
    spec = importlib.util.spec_from_file_location('orbi_control', HELPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules['orbi_control'] = module
    spec.loader.exec_module(module)
    return module


helper = load_helper()


def env_dict(text):
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip().removeprefix('export ').strip()] = value.strip()
    return values


def snapshot(path):
    """Content-addressed view of one tree; symlinks are never followed."""
    path = Path(path)
    items = {}
    for entry in [path, *path.rglob('*')]:
        relative = '.' if entry == path else entry.relative_to(path).as_posix()
        if entry.is_symlink():
            items[relative] = 'link:' + os.readlink(entry)
        elif entry.is_dir():
            items[relative] = 'dir'
        elif entry.is_file():
            items[relative] = entry.read_bytes()
    return items


FAKE_SOURCE = '''#!{python}
import json, os, subprocess, sys, time
name = os.path.basename(sys.argv[0])
argv = sys.argv[1:]
record = {{
    "tool": name,
    "argv": argv,
    "cwd": os.getcwd(),
    "env": {{key: os.environ.get(key) for key in (
        "PYTHONPATH", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR",
        "PYTHONDONTWRITEBYTECODE", "PATH", "HOME")}},
}}
with open(os.environ["FAKE_CALLS"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\\n")
with open(os.environ["FAKE_RULES"], encoding="utf-8") as handle:
    rules = json.load(handle)
joined = " ".join(argv)
for rule in rules:
    if rule.get("tool") not in (None, name):
        continue
    if not all(part in joined for part in rule.get("argv_contains", [])):
        continue
    if rule.get("if_exists") and not os.path.exists(rule["if_exists"]):
        continue
    if any(os.environ.get(key) != value
           for key, value in (rule.get("if_env") or {{}}).items()):
        continue
    for directory in rule.get("mkdir", []):
        os.makedirs(directory, exist_ok=True)
    for target, text in (rule.get("write") or {{}}).items():
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
    if rule.get("exec"):
        subprocess.run(rule["exec"], env=os.environ, check=False)
    if rule.get("sleep"):
        time.sleep(rule["sleep"])
    sys.stdout.write(rule.get("stdout", ""))
    sys.stderr.write(rule.get("stderr", ""))
    sys.exit(int(rule.get("exit", 0)))
sys.exit(0)
'''


class Harness:
    def __init__(self, root):
        self.root = root
        self.home = root / 'home'
        self.home.mkdir(parents=True)
        self.bin = root / 'bin'
        self.bin.mkdir()
        self.calls_path = root / 'calls.jsonl'
        self.rules_path = root / 'rules.json'
        self.repo = root / 'repo'
        self.repo.mkdir()
        self.repo_name = REPO
        self.deploy_head = PIN
        self.deploy = self.home / '.local/share' / ('orbi-' + helper.derive_unit_name(REPO))
        self.config_home = self.home / '.config'
        self.data_home = self.home / '.local/share'
        self.unit_dir = self.config_home / 'systemd/user'
        self.unit_dir.mkdir(parents=True)
        self.data_home.mkdir(parents=True)
        self.bootstrap = self.home / '.local/bin/orbi'
        self.bootstrap.parent.mkdir(parents=True)
        self._tools()
        self.env = {
            'HOME': str(self.home),
            'PATH': f'{self.bin}:{self.home}/.local/bin:/usr/local/bin:/usr/bin:/bin',
            'XDG_CONFIG_HOME': str(self.config_home),
            'XDG_DATA_HOME': str(self.data_home),
            'XDG_CACHE_HOME': str(self.home / '.cache'),
            'FAKE_CALLS': str(self.calls_path),
            'FAKE_RULES': str(self.rules_path),
            'FAKE_RENEW': '1',  # a real refresh is requested by an external tick only
        }
        self.a = None
        self.rules()

    def _tools(self):
        tool = self.bin / '_fake.py'
        tool.write_text(FAKE_SOURCE.format(python=sys.executable))
        tool.chmod(0o755)
        for name in ('git', 'uv', 'gh', 'node', 'pi', 'orbi', 'systemctl', 'launchctl'):
            (self.bin / name).symlink_to(tool)
        self.bootstrap.symlink_to(tool)

    def base_rules(self):
        deploy = str(self.deploy)
        repo = str(self.repo)
        return [
            {'tool': 'git', 'argv_contains': [deploy, 'config', 'remote.origin.url'],
             'stdout': OFFICIAL + '.git\n'},
            {'tool': 'git', 'argv_contains': [deploy, 'rev-parse', 'HEAD'],
             'stdout': self.deploy_head + '\n'},
            {'tool': 'git', 'argv_contains': ['clone'], 'mkdir': [deploy]},
            {'tool': 'git', 'argv_contains': ['worktree', 'list'],
             'stdout': f'worktree {repo}\nHEAD {self.deploy_head}\nbranch refs/heads/main\n'},
            {'tool': 'git', 'argv_contains': ['config', 'remote.origin.url'],
             'stdout': 'https://github.com/' + REPO + '.git\n'},
            {'tool': 'git', 'argv_contains': ['rev-parse', '--show-toplevel'],
             'stdout': repo + '\n'},
            {'tool': 'git', 'argv_contains': ['rev-parse', 'HEAD'],
             'stdout': self.deploy_head + '\n'},
            {'tool': 'uv', 'argv_contains': ['tool', 'list'], 'stdout': ''},
            {'tool': 'uv', 'argv_contains': [], 'stdout': ''},
            {'tool': 'gh', 'argv_contains': ['auth', 'status'], 'stdout': 'logged in\n'},
            {'tool': 'gh', 'argv_contains': ['issue', 'list'], 'stdout': '[]\n'},
            {'tool': 'gh', 'argv_contains': ['pr', 'list'], 'stdout': '[]\n'},
            {'tool': 'node', 'argv_contains': [], 'stdout': 'v24.19.0\n'},
            {'tool': 'pi', 'argv_contains': ['auth', 'check'], 'stdout': 'ready\n'},
            {'tool': 'pi', 'argv_contains': [], 'stdout': 'pi 1.0.0\n'},
            {'tool': 'orbi', 'argv_contains': ['--version'], 'stdout': 'orbi 0.7.41\n'},
            {'tool': 'orbi', 'argv_contains': ['check'], 'stdout': 'prerequisites=ok checks=12\n'},
            {'tool': 'orbi', 'argv_contains': ['doctor'], 'stdout': 'slots: 0/1\n'},
            {'tool': 'orbi', 'argv_contains': ['setup'], 'stdout': ''},
            {'tool': 'orbi', 'argv_contains': ['install-units'], 'stdout': ''},
            {'tool': 'orbi', 'argv_contains': [], 'if_env': {'FAKE_RENEW': '1'},
             'exec': ['uv', 'tool', 'install', '--force', '--reinstall', '--editable',
                      '--python', '3.14', deploy]},
            {'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState'],
             'stdout': 'inactive\n'},
            {'tool': 'systemctl', 'argv_contains': ['show', 'FragmentPath'],
             'stdout': '\n'},
            {'tool': 'systemctl', 'argv_contains': ['is-enabled'],
             'stdout': 'disabled\n', 'exit': 1},
            {'tool': 'systemctl', 'argv_contains': [], 'stdout': ''},
        ]

    def rules(self, *extra):
        self.rules_path.write_text(json.dumps([*extra, *self.base_rules()], indent=2))

    def calls(self):
        if not self.calls_path.exists():
            return []
        return [json.loads(line) for line in self.calls_path.read_text().splitlines() if line]

    def clear_calls(self):
        self.calls_path.unlink(missing_ok=True)

    def add_deployment_a(self):
        a_repo = self.root / 'repo-a'
        a_repo.mkdir()
        a_deploy = self.data_home / 'orbi-a'
        (a_deploy / '.orbi').mkdir(parents=True)
        a_config = a_deploy / 'orbi.toml'
        a_config.write_text(
            'source_repos = ["other/repo-a"]\n'
            f'repo_dir = "{a_repo}"\n'
            f'deploy_home = "{a_deploy}"\n'
            'unit_name = "a"\n'
            f'engine_source_track = "sha:{OLD_PIN}"\n'
            'keep_failed_worktrees = true\n'
            'max_concurrency = 2\n'
            'human_review_gate = true\n'
            'base_branch = "main"\n'
            'git_transport = "https"\n'
            'pi_providers = ".orbi/pi-providers.json"\n'
            'pi_provider = "openrouter"\n'
            'pi_model = "vendor/model-a"\n'
        )
        (a_deploy / '.orbi/env').write_text(
            f'SECRET_API_KEY={SECRET}\n'
            f'PYTHONPATH={a_deploy}/src\n'
            f'UV_TOOL_DIR={a_deploy}/.orbi/uv-tools\n'
        )
        metadata = {
            'providers': {'openrouter': {
                'baseUrl': 'https://openrouter.example/api/v1',
                'api': 'openai-completions',
                'models': [{'id': 'vendor/model-a', 'name': 'Model A',
                            'contextWindow': 1048576, 'maxTokens': 943718}],
            }},
        }
        (a_deploy / '.orbi/pi-providers.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (a_deploy / '.orbi/uv-tools').mkdir()
        (a_deploy / '.orbi/bin').mkdir()
        (self.unit_dir / 'orbi-a@.service').write_text(
            '[Service]\nEnvironment="ORBI_CONFIG=' + str(a_config) + '"\n')
        (self.unit_dir / 'orbi-a@.timer').write_text('[Timer]\n')
        self.a = {
            'repo': a_repo, 'deploy': a_deploy, 'config': a_config,
            'metadata': metadata, 'env_text': (a_deploy / '.orbi/env').read_text(),
            'snapshot': snapshot(a_deploy),
            'unit_snapshot': {name: data for name, data in snapshot(self.unit_dir).items()
                              if name in {'.'} or name.startswith('orbi-a')},
            'launcher_snapshot': snapshot(self.bootstrap.parent),
        }
        return self.a

    def scheduler_rules(self, services=None, timers=None, enabled=None, *,
                        installed=True, service_config=None):
        services = services or {}
        timers = timers or {}
        enabled = enabled or {}
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service_file = self.unit_dir / f'{prefix}@.service'
        timer_file = self.unit_dir / f'{prefix}@.timer'
        if installed:
            service_file.write_text(
                '[Service]\nEnvironment="ORBI_CONFIG='
                + str(service_config or self.deploy / 'orbi.toml') + '"\n')
            timer_file.write_text('[Timer]\n')
        rules = []
        for index in range(1, helper.MAX_INSTANCES + 1):
            rules.append({
                'tool': 'systemctl',
                'argv_contains': ['show', f'{prefix}@{index}.timer', 'FragmentPath'],
                'stdout': (str(timer_file) + '\n') if installed else '\n'})
            rules.append({
                'tool': 'systemctl',
                'argv_contains': ['show', f'{prefix}@{index}.service', 'FragmentPath'],
                'stdout': (str(service_file) + '\n') if installed else '\n'})
            rules.append({
                'tool': 'systemctl',
                'argv_contains': ['show', 'ActiveState', f'{prefix}@{index}.timer'],
                'stdout': timers.get(index, 'inactive') + '\n'})
            rules.append({
                'tool': 'systemctl',
                'argv_contains': ['show', 'ActiveState', f'{prefix}@{index}.service'],
                'stdout': services.get(index, 'inactive') + '\n'})
            rules.append({
                'tool': 'systemctl',
                'argv_contains': ['is-enabled', f'{prefix}@{index}.timer'],
                'stdout': ('enabled\n' if enabled.get(index) else 'disabled\n'),
                'exit': 0 if enabled.get(index) else 1})
        return rules

    def run(self, action, *, platform='linux', dry_run=False, env=None, config=None):
        argv = [action, '--repo-dir', str(self.repo), '--json']
        if config is not None:
            argv.extend(['--config', str(config)])
        if dry_run:
            argv.append('--dry-run')
        out, err = io.StringIO(), io.StringIO()
        code = helper.main(argv, env=dict(env or self.env), platform=platform,
                           stdout=out, stderr=err)
        document = json.loads(out.getvalue()) if out.getvalue().strip() else None
        return code, document, err.getvalue()

    def run_external(self, executable, env_overrides, *, refresh=False):
        env = dict(self.env)
        env.update(env_overrides)
        if refresh:
            env['FAKE_RENEW'] = '1'
        else:
            env.pop('FAKE_RENEW', None)
        return subprocess.run([str(executable)], env=env, capture_output=True,
                              text=True, timeout=60)

    def config(self):
        return tomllib.loads((self.deploy / 'orbi.toml').read_text())


class SetupBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(Path(self.tmp.name))
        self.a = self.h.add_deployment_a()

    def a_units(self, harness):
        return {name: data for name, data in snapshot(harness.unit_dir).items()
                if name in {'.'} or name.startswith('orbi-a')}

    def assert_a_unchanged(self):
        self.assertEqual(snapshot(self.a['deploy']), self.a['snapshot'])
        self.assertEqual(self.a_units(self.h), self.a['unit_snapshot'])
        self.assertEqual(snapshot(self.h.bootstrap.parent),
                         self.a['launcher_snapshot'])

    def assert_no_activation(self, calls):
        for call in calls:
            self.assertNotEqual(call['tool'], 'systemctl', call)
            if call['tool'] == 'orbi':
                self.assertNotIn(call['argv'][0] if call['argv'] else '',
                                 {'setup', 'install-units'}, call)

    def test_setup_preserves_execution_boundary(self):
        # Success: prepare B without activating anything, preserving A.
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['status'], 'prepared')
        self.assertFalse(doc['activated'])
        self.assertEqual(doc['deployment']['pin'], helper.PIN_TRACK)
        config = self.h.config()
        self.assertEqual(config['source_repos'], [REPO])
        self.assertEqual(config['engine_source_track'], helper.PIN_TRACK)
        self.assertEqual(config['max_concurrency'], 1)
        self.assertTrue(config['keep_failed_worktrees'])
        self.assertTrue(config['human_review_gate'])
        self.assertEqual(config['pi_provider'], 'openrouter')
        self.assertEqual(config['pi_model'], 'vendor/model-a')
        env = env_dict((self.h.deploy / '.orbi/env').read_text())
        self.assertEqual(env['PYTHONPATH'], str(self.h.deploy / 'src'))
        self.assertEqual(env['UV_TOOL_DIR'], str(self.h.deploy / '.orbi/uv-tools'))
        self.assertEqual(env['UV_TOOL_BIN_DIR'], str(self.h.deploy / '.orbi/bin'))
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertIn(str(self.h.bin), env['PATH'])
        self.assertNotIn(SECRET, (self.h.deploy / '.orbi/env').read_text())
        providers = json.loads((self.h.deploy / '.orbi/pi-providers.json').read_text())
        self.assertEqual(providers, self.a['metadata'])
        self.assertFalse((self.h.deploy / '.orbi/cli-install.json').exists())
        calls = self.h.calls()
        clones = [c for c in calls if c['tool'] == 'git' and c['argv'][:1] == ['clone']]
        self.assertEqual(len(clones), 1)
        self.assertIn(OFFICIAL, clones[0]['argv'])
        self.assert_no_activation(calls)
        self.assert_a_unchanged()

        # Dry-run: plan only, no files, lock, install, fetch or activation.
        self.h.clear_calls()
        dry_tmp = Harness(Path(self.tmp.name) / 'dry')
        dry_tmp.add_deployment_a()
        before = snapshot(dry_tmp.home)
        code, doc, err = dry_tmp.run('setup', dry_run=True)
        self.assertEqual(code, 0, err)
        self.assertTrue(doc['dry_run'])
        self.assertEqual(doc['status'], 'planned')
        self.assertFalse(dry_tmp.deploy.exists())
        self.assertEqual(snapshot(dry_tmp.home), before)
        dry_calls = dry_tmp.calls()
        self.assertFalse([c for c in dry_calls if c['tool'] in {'systemctl', 'uv'}])
        self.assert_no_activation(dry_calls)

        # Missing uv: precise prerequisite failure, no writes.
        missing = Harness(Path(self.tmp.name) / 'missing')
        missing.add_deployment_a()
        (missing.bin / 'uv').unlink()
        before = snapshot(missing.home)
        code, doc, err = missing.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'prerequisite_missing')
        self.assertIn('uv', doc['error']['message'])
        self.assertTrue(doc['error']['fix'])
        self.assertEqual(snapshot(missing.home), before)
        self.assertNoActivationCalls(missing.calls())

        # Incompatible existing bootstrap: fail closed, never reinstall A's launcher.
        broken = Harness(Path(self.tmp.name) / 'broken')
        broken.add_deployment_a()
        broken.rules({'tool': 'orbi', 'argv_contains': ['--version'],
                      'stdout': 'boom\n', 'exit': 1})
        launcher = broken.bootstrap.read_bytes()
        code, doc, err = broken.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'bootstrap_incompatible')
        self.assertIn('bootstrap', doc['error']['message'])
        self.assertEqual(broken.bootstrap.read_bytes(), launcher)
        self.assertFalse(broken.deploy.exists())
        self.assertFalse([c for c in broken.calls() if c['tool'] == 'uv'])
        self.assertEqual(snapshot(broken.home / '.local/share/orbi-a'),
                         broken.a['snapshot'])

        # Conflicting unit ownership: the derived unit name belongs to a foreign pool.
        conflict = Harness(Path(self.tmp.name) / 'conflict')
        conflict.add_deployment_a()
        foreign = conflict.data_home / 'orbi-foreign'
        (foreign / '.orbi').mkdir(parents=True)
        (foreign / 'orbi.toml').write_text(
            'source_repos = ["other/foreign"]\n'
            f'repo_dir = "{conflict.root}/repo-a"\n'
            f'deploy_home = "{foreign}"\n'
            'unit_name = "' + helper.derive_unit_name(REPO) + '"\n')
        code, doc, err = conflict.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'unit_conflict')
        self.assertFalse(conflict.deploy.exists())

        # Unknown existing files or symlinks are never adopted.
        unknown = Harness(Path(self.tmp.name) / 'unknown')
        unknown.add_deployment_a()
        unknown.deploy.mkdir(parents=True)
        (unknown.deploy / 'unknown.txt').write_text('unrelated\n')
        unknown.rules(
            {'tool': 'git',
             'argv_contains': [str(unknown.deploy), 'config', 'remote.origin.url'],
             'exit': 1},
            {'tool': 'git', 'argv_contains': [str(unknown.deploy), 'rev-parse', 'HEAD'],
             'exit': 1})
        code, doc, err = unknown.run('setup')
        self.assertNotEqual(code, 0)
        self.assertIn(doc['error']['code'], {'unknown_target', 'pin_mismatch'})
        self.assertEqual((unknown.deploy / 'unknown.txt').read_text(), 'unrelated\n')

        # Installed unit ownership that belongs elsewhere is refused.
        owned = Harness(Path(self.tmp.name) / 'owned')
        owned.add_deployment_a()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        (owned.unit_dir / f'{prefix}@.service').write_text(
            '[Service]\nEnvironment="ORBI_CONFIG=' + str(owned.a['config']) + '"\n')
        (owned.unit_dir / f'{prefix}@.timer').write_text('[Timer]\n')
        code, doc, err = owned.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'unit_conflict')
        self.assertFalse(owned.deploy.exists())

        # Duplicate task pools for the same repository are ambiguous.
        duplicate = Harness(Path(self.tmp.name) / 'duplicate')
        duplicate.add_deployment_a()
        for name in ('orbi-dup1', 'orbi-dup2'):
            folder = duplicate.data_home / name
            (folder / '.orbi').mkdir(parents=True)
            (folder / 'orbi.toml').write_text(
                f'source_repos = ["{REPO}"]\n'
                f'repo_dir = "{duplicate.repo}"\n'
                f'deploy_home = "{folder}"\n'
                f'unit_name = "{name}"\n')
        code, doc, err = duplicate.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'ambiguous_deployment')
        self.assertFalse(duplicate.deploy.exists())

        # Existing setup is idempotent and keeps its own (old) pin.
        first = snapshot(self.h.deploy)
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.assertEqual(snapshot(self.h.deploy), first)
        config_text = (self.h.deploy / 'orbi.toml').read_text()
        (self.h.deploy / 'orbi.toml').write_text(
            config_text.replace(helper.PIN_TRACK, 'sha:' + OLD_PIN))
        self.h.deploy_head = OLD_PIN
        self.h.rules()
        self.h.clear_calls()
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + OLD_PIN)
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'git'
                          and set(c['argv']) & {'clone', 'checkout', 'fetch'}])
        self.assert_a_unchanged()

    def test_explicit_config_cannot_bypass_duplicate_ownership(self):
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        config = self.h.deploy / 'orbi.toml'
        duplicate = self.h.data_home / 'orbi-duplicate'
        duplicate.mkdir()
        (duplicate / 'orbi.toml').write_text(
            config.read_text().replace(str(self.h.deploy), str(duplicate)))
        before = snapshot(self.h.home)
        for action in ('setup', 'start', 'stop', 'status'):
            with self.subTest(action=action):
                self.h.clear_calls()
                code, doc, err = self.h.run(action, config=config)
                self.assertEqual(code, 2, err)
                self.assertEqual(doc['error']['code'], 'ambiguous_deployment')
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse([c for c in self.h.calls() if c['tool'] != 'git'])

    def test_symlink_targets_and_parents_are_refused_before_writes(self):
        cases = ('staging', 'data-parent', 'config', 'config-parent', 'deploy-home',
                 'state-parent', 'env', 'provider', 'provider-parent', 'staging-state')
        for case in cases:
            with self.subTest(case=case):
                h = Harness(Path(self.tmp.name) / case)
                h.add_deployment_a()
                config = None
                if case in {'staging', 'data-parent', 'staging-state'}:
                    if case == 'staging':
                        destination = h.root / 'unrelated'
                        destination.mkdir()
                        h.deploy.symlink_to(destination, target_is_directory=True)
                    elif case == 'data-parent':
                        alias = h.root / 'data-link'
                        alias.symlink_to(h.data_home, target_is_directory=True)
                        h.env['XDG_DATA_HOME'] = str(alias)
                    else:
                        h.deploy.mkdir()
                        (h.deploy / '.orbi').symlink_to(h.a['deploy'] / '.orbi',
                                                       target_is_directory=True)
                else:
                    code, doc, err = h.run('setup')
                    self.assertEqual(code, 0, err)
                    target_config = h.deploy / 'orbi.toml'
                    if case == 'config-parent':
                        alias = h.root / 'config-link'
                        alias.symlink_to(h.deploy, target_is_directory=True)
                        config = alias / 'orbi.toml'
                    elif case == 'deploy-home':
                        alias = h.root / 'deploy-link'
                        alias.symlink_to(h.deploy, target_is_directory=True)
                        target_config.write_text(target_config.read_text().replace(
                            f'deploy_home = "{h.deploy}"', f'deploy_home = "{alias}"'))
                    elif case == 'provider-parent':
                        alias = h.root / 'provider-link'
                        alias.symlink_to(h.deploy / '.orbi', target_is_directory=True)
                        target_config.write_text(target_config.read_text().replace(
                            'pi_providers = ".orbi/pi-providers.json"',
                            f'pi_providers = "{alias}/pi-providers.json"'))
                    else:
                        relative = {'config': 'orbi.toml', 'state-parent': '.orbi',
                                    'env': '.orbi/env',
                                    'provider': '.orbi/pi-providers.json'}[case]
                        original = h.deploy / relative
                        destination = h.root / 'original'
                        original.rename(destination)
                        original.symlink_to(destination,
                                            target_is_directory=destination.is_dir())
                h.clear_calls()
                before = snapshot(h.home)
                external = (snapshot(h.root / 'original')
                            if (h.root / 'original').exists() else None)
                actions = (('setup',) if case in {'staging', 'data-parent', 'staging-state'}
                           else ('setup', 'start'))
                for action in actions:
                    code, doc, err = h.run(action, config=config)
                    self.assertEqual(code, 2, (case, action, doc, err))
                    self.assertEqual(doc['error']['code'], 'unknown_target')
                    self.assertEqual(snapshot(h.home), before)
                    self.assertFalse([c for c in h.calls() if c['tool'] != 'git'])
                if external is not None:
                    self.assertEqual(snapshot(h.root / 'original'), external)
                self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])

    def assertNoActivationCalls(self, calls):
        for call in calls:
            self.assertFalse(call['tool'] == 'systemctl', call)
            if call['tool'] == 'orbi':
                self.assertNotIn(call['argv'][0] if call['argv'] else '',
                                 {'setup', 'install-units'}, call)


class RuntimeIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(Path(self.tmp.name))
        self.a = self.h.add_deployment_a()
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.a_snapshot = self.a['snapshot']

    def scoped(self, call):
        env = call['env']
        return (env['PYTHONPATH'], env['UV_TOOL_DIR'], env['UV_TOOL_BIN_DIR'],
                env['PYTHONDONTWRITEBYTECODE'])

    def expected(self):
        return (str(self.h.deploy / 'src'),
                str(self.h.deploy / '.orbi/uv-tools'),
                str(self.h.deploy / '.orbi/bin'), '1')

    def test_runtime_isolation(self):
        # First start: install with the exact scoped environment, activate only
        # the target timer and request one first tick.
        self.h.rules(
            {'tool': 'orbi', 'argv_contains': ['setup'],
             'exec': ['uv', 'tool', 'install', '--force', '--reinstall', '--editable',
                      '--python', '3.14', str(self.h.deploy)]},
            *self.h.scheduler_rules(services={1: 'inactive'}, timers={1: 'inactive'},
                                    enabled={1: False}))
        self.h.clear_calls()
        code, doc, err = self.h.run('start')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['status'], 'started')
        calls = self.h.calls()
        orbi_calls = [c for c in calls if c['tool'] == 'orbi']
        self.assertTrue(orbi_calls)
        for call in orbi_calls:
            self.assertTrue(call['argv'], 'bare orbi tick is forbidden')
            self.assertIn(call['argv'][0], {'--version', 'check', 'doctor', 'setup', 'install-units'})
            self.assertEqual(self.scoped(call), self.expected(), call['argv'])
        setup_call = next(c for c in orbi_calls if c['argv'][0] == 'setup')
        self.assertEqual(setup_call['argv'][1:3],
                         ['--config', str(self.h.deploy / 'orbi.toml')])
        self.assertIn('--repo', setup_call['argv'])
        self.assertIn(REPO, setup_call['argv'])
        install_call = next(c for c in orbi_calls if c['argv'][0] == 'install-units')
        self.assertEqual(install_call['argv'][1:3],
                         ['--config', str(self.h.deploy / 'orbi.toml')])
        # The refresh reinstall triggered by the tick inherits B-local uv dirs.
        uv_calls = [c for c in calls if c['tool'] == 'uv']
        self.assertTrue(uv_calls)
        for call in uv_calls:
            self.assertEqual(self.scoped(call), self.expected(), call['argv'])
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        mutations = [c['argv'] for c in calls if c['tool'] == 'systemctl']
        self.assertEqual(sum(1 for argv in mutations if 'enable' in argv), 1)
        self.assertEqual(sum(1 for argv in mutations if 'start' in argv), 1)
        self.assertFalse([argv for argv in mutations
                          if set(argv) & {'stop', 'restart', 'kill', 'disable'}])
        self.assertFalse((self.h.deploy / '.orbi/cli-install.json').exists())

        # The real first tick reads the env file; a genuine fingerprint refresh
        # then reinstalls into B-local directories.
        env_text = (self.h.deploy / '.orbi/env').read_text()
        self.h.clear_calls()
        tick = self.h.run_external(self.h.bootstrap, env_dict(env_text), refresh=True)
        self.assertEqual(tick.returncode, 0, tick.stderr)
        tick_calls = self.h.calls()
        tick_orbi = [c for c in tick_calls if c['tool'] == 'orbi']
        self.assertEqual(len(tick_orbi), 1)
        self.assertEqual(self.scoped(tick_orbi[0]), self.expected())
        tick_uv = [c for c in tick_calls if c['tool'] == 'uv']
        self.assertEqual(len(tick_uv), 1, tick_calls)
        self.assertEqual(self.scoped(tick_uv[0]), self.expected())

        # A's launcher, env and evidence are untouched, and its next invocation works.
        self.assertEqual(snapshot(self.a['deploy']), self.h.a['snapshot'])
        self.assertEqual(
            {name: data for name, data in snapshot(self.h.unit_dir).items()
             if name in {'.'} or name.startswith('orbi-a')},
            self.a['unit_snapshot'])
        self.h.clear_calls()
        a_env = env_dict(self.a['env_text'])
        a_run = self.h.run_external(self.h.bootstrap, a_env)
        self.assertEqual(a_run.returncode, 0, a_run.stderr)
        [a_call] = [c for c in self.h.calls() if c['tool'] == 'orbi']
        self.assertEqual(a_call['env']['PYTHONPATH'], str(self.a['deploy'] / 'src'))
        self.assertEqual(a_call['env']['UV_TOOL_DIR'], str(self.a['deploy'] / '.orbi/uv-tools'))

        # Repeated start with a live worker never enables/restarts/starts anything.
        self.h.rules(*self.h.scheduler_rules(services={1: 'active'}, timers={1: 'active'},
                                             enabled={1: True}))
        self.h.clear_calls()
        code, doc, err = self.h.run('start')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['status'], 'already-running')
        mutations = [c['argv'] for c in self.h.calls() if c['tool'] == 'systemctl']
        self.assertFalse([argv for argv in mutations
                          if set(argv) & {'enable', 'start', 'restart', 'stop', 'kill'}])
        self.assertEqual(snapshot(self.a['deploy']), self.a_snapshot)

        # An incompatible shared bootstrap fails closed before activation.
        self.h.rules({'tool': 'orbi', 'argv_contains': ['--version'],
                      'stdout': 'boom\n', 'exit': 1},
                     *self.h.scheduler_rules(services={1: 'inactive'}))
        self.h.clear_calls()
        code, doc, err = self.h.run('start')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'bootstrap_incompatible')
        calls = self.h.calls()
        self.assertFalse([c for c in calls if c['tool'] == 'systemctl'])
        self.assertFalse([c for c in calls if c['tool'] == 'orbi'
                          and c['argv'][0] in {'setup', 'install-units'}])
        self.assertEqual(snapshot(self.a['deploy']), self.a_snapshot)

        # Failure injection: upstream may have activated before the failure;
        # recovery observes scheduling without further mutation.
        self.h.rules({'tool': 'orbi', 'argv_contains': ['install-units'],
                      'stdout': '', 'stderr': 'unit failure\n', 'exit': 1},
                     *self.h.scheduler_rules(services={1: 'inactive'}))
        self.h.clear_calls()
        code, doc, err = self.h.run('start')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'install_units_failed')
        self.assertTrue(doc['error']['mutated'])
        self.assertIn('install-units', doc['error']['fix'])
        self.assertEqual(doc['activation'], 'possible')
        self.assertIn('scheduler', doc)
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'systemctl'
                          and set(c['argv']) & {'enable', 'disable', 'start', 'stop',
                                               'restart', 'kill'}])
        self.assertEqual(snapshot(self.a['deploy']), self.a_snapshot)

        # Failure injection: setup failure is reported with its recovery step.
        self.h.rules({'tool': 'orbi', 'argv_contains': ['setup'],
                      'stdout': '', 'stderr': 'labels failed\n', 'exit': 2},
                     *self.h.scheduler_rules(services={1: 'inactive'}))
        self.h.clear_calls()
        code, doc, err = self.h.run('start')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'setup_failed')
        self.assertIn('setup', doc['error']['fix'])
        self.assertFalse([c for c in self.h.calls()
                          if c['tool'] == 'orbi' and c['argv'][0] == 'install-units'])

    def test_activation_before_failure_or_timeout_is_reported_without_retry(self):
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        timer, service = f'{prefix}@1.timer', f'{prefix}@1.service'
        marker = self.h.root / 'activated'
        original_run = helper.Context.run
        for command in ('setup', 'install-units'):
            for failure in ('exit', 'timeout', 'unreadable'):
                with self.subTest(command=command, failure=failure):
                    marker.unlink(missing_ok=True)
                    idle = self.h.scheduler_rules()
                    active = self.h.scheduler_rules(services={1: 'active'},
                                                    timers={1: 'active'}, enabled={1: True})
                    for rule in active:
                        rule['if_exists'] = str(marker)
                    if failure == 'unreadable':
                        active = [{'tool': 'systemctl', 'argv_contains': ['show'],
                                   'if_exists': str(marker), 'exit': 1}]
                    self.h.rules(
                        {'tool': 'orbi', 'argv_contains': [command],
                         'exec': ['systemctl', '--user', 'enable', '--now', timer],
                         'exit': 1, 'sleep': 5 if failure == 'timeout' else 0},
                        {'tool': 'systemctl', 'argv_contains': ['--user enable --now', timer],
                         'write': {str(marker): 'active'}}, *active, *idle)
                    self.h.clear_calls()

                    def bounded_run(ctx, argv, **kwargs):
                        if Path(argv[0]).name == 'orbi' and argv[1] == command:
                            kwargs['timeout'] = 1
                        return original_run(ctx, argv, **kwargs)

                    with mock.patch.object(helper.Context, 'run', bounded_run):
                        code, doc, err = self.h.run('start')
                    self.assertNotEqual(code, 0, err)
                    expected = ('command_timeout' if failure == 'timeout'
                                else command.replace('-', '_') + '_failed')
                    self.assertEqual(doc['error']['code'], expected)
                    self.assertTrue(doc['error']['mutated'])
                    self.assertEqual(doc['activation'], 'possible')
                    self.assertIn('may already be activated', doc['error']['message'])
                    self.assertEqual(doc['steps'][-1]['step'], command)
                    self.assertEqual(marker.read_text(), 'active')
                    if failure == 'unreadable':
                        self.assertEqual(doc['scheduler']['state'], 'unavailable')
                    else:
                        self.assertTrue(doc['scheduler']['timers'][timer]['enabled'])
                        self.assertEqual(doc['scheduler']['services'][service]['state'], 'active')
                    calls = self.h.calls()
                    activations = [c['argv'] for c in calls if c['tool'] == 'systemctl'
                                   and set(c['argv']) & {'enable', 'disable', 'start', 'stop',
                                                        'restart', 'kill'}]
                    self.assertEqual(activations, [['--user', 'enable', '--now', timer]])
                    commands = [c['argv'][0] for c in calls if c['tool'] == 'orbi']
                    self.assertEqual(commands.count(command), 1)
                    if command == 'setup':
                        self.assertNotIn('install-units', commands)
                    self.assertEqual(snapshot(self.a['deploy']), self.a_snapshot)


class LifecycleSequenceTests(unittest.TestCase):
    CASES = (
        ('active', {1: 'active'}, {1: 'active'}, {1: True}, 'running', 'draining', False),
        ('activating', {1: 'activating'}, {1: 'active'}, {1: True}, 'running', 'draining', False),
        ('idle', {1: 'inactive'}, {1: 'inactive'}, {1: False}, 'stopped', 'stopped', True),
        ('surplus', {1: 'inactive'}, {1: 'active'}, {1: True, 2: True, 3: True},
         'prepared', 'stopped', True),
    )

    def fresh(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        harness = Harness(Path(tmp.name))
        harness.add_deployment_a()
        code, doc, err = harness.run('setup')
        self.assertEqual(code, 0, err)
        harness.clear_calls()
        return harness

    def test_lifecycle_sequence(self):
        for name, services, timers, enabled, state, stop_state, expect_tick in self.CASES:
            with self.subTest(case=name):
                h = self.fresh()
                prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                h.rules(*h.scheduler_rules(services=services, timers=timers,
                                           enabled=enabled))

                # Status and dry-run are read-only: identical tree, no lock/receipt.
                before = snapshot(h.home)
                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['platform'], 'linux')
                self.assertEqual(doc['deployment']['state'], state)
                self.assertEqual(doc['deployment']['source'], 'verified')
                self.assertEqual(doc['deployment']['bootstrap'], 'compatible')
                self.assertEqual(doc['queue']['state'], 'ok')
                self.assertEqual(doc['queue']['ready'], [])
                read_calls = h.calls()
                self.assertFalse([c for c in read_calls if c['tool'] == 'systemctl'
                                  and set(c['argv']) & {'enable', 'disable', 'start',
                                                        'stop', 'restart', 'daemon-reload'}])
                for action in ('start', 'stop'):
                    h.clear_calls()
                    code, doc, err = h.run(action, dry_run=True)
                    self.assertEqual(code, 0, err)
                    self.assertTrue(doc['dry_run'])
                    self.assertEqual(doc['status'], 'planned')
                    self.assertFalse([c for c in h.calls()
                                      if c['tool'] in {'uv', 'systemctl'}
                                      and set(c['argv']) & {'enable', 'disable', 'start',
                                                            'stop', 'restart', 'daemon-reload'}])
                self.assertEqual(snapshot(h.home), before)

                # Idempotent start: exactly one tick when idle, never for a live worker.
                h.clear_calls()
                code, doc, err = h.run('start')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['status'], 'started' if expect_tick else 'already-running')
                mutation_args = [c['argv'] for c in h.calls() if c['tool'] == 'systemctl']
                self.assertEqual(bool([a for a in mutation_args if 'start' in a]),
                                 expect_tick)
                self.assertFalse([a for a in mutation_args
                                  if set(a) & {'stop', 'restart', 'kill', 'disable'}])
                self.assertFalse([c for c in h.calls()
                                  if c['tool'] == 'orbi' and not c['argv']])

                # Timer-only stop: every owned instance (including surplus) is
                # disabled; no service is stopped or killed.
                h.rules(*h.scheduler_rules(services=services, timers=timers,
                                           enabled=enabled))
                h.clear_calls()
                code, doc, err = h.run('stop')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['status'], stop_state)
                self.assertEqual(len(doc['disabled_timers']), helper.MAX_INSTANCES)
                for index in range(1, helper.MAX_INSTANCES + 1):
                    self.assertIn(f'{prefix}@{index}.timer', doc['disabled_timers'])
                calls = h.calls()
                for call in calls:
                    if call['tool'] != 'systemctl':
                        continue
                    if 'disable' in call['argv']:
                        self.assertTrue(call['argv'][-1].endswith('.timer'), call)
                    for forbidden in ('stop', 'restart', 'kill'):
                        self.assertNotIn(forbidden, call['argv'], call)
                if stop_state == 'draining':
                    self.assertTrue(doc['pending_services'])
                else:
                    self.assertEqual(doc['pending_services'], [])
                self.assertFalse([c for c in calls if c['tool'] == 'orbi'
                                  and (not c['argv'] or c['argv'][0] in {'setup', 'install-units'})])

                # Final read reflects the disabled timers.
                h.rules(*h.scheduler_rules(services=services, timers={},
                                           enabled={}))
                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['deployment']['state'],
                                 'running' if services.get(1) == 'active' else
                                 ('running' if services.get(1) == 'activating' else 'stopped'))

    def test_unsupported_platforms_change_nothing(self):
        h = self.fresh()
        h.rules(*h.scheduler_rules())
        before = snapshot(h.home)
        code, doc, err = h.run('status', platform='darwin')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['platform'], 'darwin')
        self.assertEqual(doc['scheduler']['state'], 'launchd')
        self.assertFalse([c for c in h.calls() if c['tool'] == 'systemctl'])
        for action in ('setup', 'start', 'stop'):
            for dry_run in (False, True):
                h.clear_calls()
                code, doc, err = h.run(action, platform='darwin', dry_run=dry_run)
                self.assertEqual(code, 2)
                self.assertEqual(doc['error']['code'], 'unsupported_platform')
                self.assertIn('status', doc['error']['message'])
                self.assertFalse([c for c in h.calls()
                                  if c['tool'] in {'systemctl', 'launchctl', 'uv'}
                                  or (c['tool'] == 'orbi' and c['argv'][0] in
                                      {'setup', 'install-units'})])
                self.assertEqual(snapshot(h.home), before)
        h.clear_calls()
        code, doc, err = h.run('status', platform='win32')
        self.assertEqual(code, 2)
        self.assertEqual(doc['error']['code'], 'unsupported_platform')
        self.assertEqual(snapshot(h.home), before)

    def test_unobserved_services_never_report_stopped_or_request_a_tick(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        for output, exit_code in (('', 1), ('inactive\n', 1), ('', 0), ('unexpected\n', 0)):
            with self.subTest(output=output, exit_code=exit_code):
                h.rules({'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState', service],
                         'stdout': output, 'exit': exit_code}, *h.scheduler_rules())
                h.clear_calls()
                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['deployment']['state'], 'unavailable')
                for action in ('stop', 'start'):
                    code, doc, err = h.run(action)
                    self.assertNotEqual(code, 0, err)
                    self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
                self.assertFalse([c for c in h.calls() if c['tool'] == 'systemctl'
                                  and set(c['argv']) & {'enable', 'disable', 'start', 'stop',
                                                       'restart', 'kill'}])

        # A read can fail only after the timers have been disabled. Preserve the
        # partial mutation and uncertainty instead of claiming successful drain.
        marker = h.root / 'disabled'
        h.rules({'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState', service],
                 'if_exists': str(marker), 'exit': 1},
                {'tool': 'systemctl', 'argv_contains': ['disable'],
                 'write': {str(marker): 'disabled'}}, *h.scheduler_rules())
        h.clear_calls()
        code, doc, err = h.run('stop')
        self.assertNotEqual(code, 0, err)
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(len(doc['disabled_timers']), helper.MAX_INSTANCES)
        self.assertIn({'unit': service, 'state': 'unavailable'}, doc['pending_services'])
        self.assertFalse([c for c in h.calls() if c['tool'] == 'systemctl'
                          and set(c['argv']) & {'enable', 'start', 'stop', 'restart', 'kill'}])

    def test_missing_queue_evidence_is_unavailable_not_empty(self):
        h = self.fresh()
        h.rules({'tool': 'gh', 'argv_contains': ['issue', 'list'],
                 'stdout': '', 'stderr': 'auth unavailable\n', 'exit': 1},
                *h.scheduler_rules())
        code, doc, err = h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['state'], 'unavailable')
        self.assertNotIn('ready', doc['queue'])


class InterfaceAndSkillTests(unittest.TestCase):
    def test_help_is_read_only_and_names_every_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp))
            scratch = h.root / 'scratch'
            scratch.mkdir()
            before = snapshot(h.home)
            expected = {'status': 'none', 'setup': 'staging', 'start': 'scheduler',
                        'stop': 'scheduler', 'help': 'none'}
            for options in ([], ['--repo-dir', '/missing/repo', '--config',
                                  '/missing/config', '--dry-run']):
                for json_mode in (True, False):
                    with self.subTest(options=options, json=json_mode):
                        result = subprocess.run(
                            [sys.executable, '-B', str(HELPER), 'help', *options,
                             *(['--json'] if json_mode else [])],
                            cwd=scratch, env=dict(h.env), capture_output=True,
                            text=True, timeout=20)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, '')
                        if json_mode:
                            document = json.loads(result.stdout)
                            self.assertEqual(set(document), {
                                'action', 'platform', 'mutations_supported', 'actions',
                                'options', 'errors', 'boundaries'})
                            self.assertEqual(document['action'], 'help')
                            self.assertEqual(list(document['actions']), list(expected))
                            for action, mutation in expected.items():
                                entry = document['actions'][action]
                                self.assertEqual(set(entry), {
                                    'effect', 'mutates', 'platforms', 'when'})
                                self.assertEqual(entry['mutates'], mutation)
                                self.assertTrue(entry['effect'])
                                self.assertTrue(entry['when'])
                            for flag, actions in {
                                '--repo-dir': ['status', 'setup', 'start', 'stop'],
                                '--config': ['status', 'setup', 'start', 'stop'],
                                '--dry-run': ['setup', 'start', 'stop'],
                                '--json': list(expected),
                            }.items():
                                self.assertEqual(document['options'][flag]['applies_to'],
                                                 actions)
                            self.assertEqual(set(document['errors']),
                                             {'exit', 'mutated', 'code', 'fix'})
                            self.assertIn('Exit 0 means success or help',
                                          document['errors']['exit'])
                            self.assertIn('error.mutated, not the exit code',
                                          document['errors']['mutated'])
                            for boundary in ('no repository or deployment',
                                             'Status is read-only',
                                             'Only setup stages source/config',
                                             'only start/stop touch the scheduler',
                                             'Not an executor or scheduler',
                                             '/unblock', '/git-commit-push',
                                             'Local visibility only'):
                                self.assertIn(boundary, ' '.join(document['boundaries']))
                            self.assertNotIn(SECRET, result.stdout)
                        else:
                            self.assertIn('[status|setup|start|stop|help]', result.stdout)
                            for action, mutation in expected.items():
                                lines = [line for line in result.stdout.splitlines()
                                         if line.startswith(f'  {action} [')]
                                self.assertEqual(len(lines), 1)
                                self.assertIn(f'[{mutation}]', lines[0])
                        self.assertEqual(h.calls(), [])
                        self.assertEqual(snapshot(h.home), before)

    def test_help_reports_platform_limits(self):
        # No repo-dir is injected: help must not bind a deployment or environment.
        # Argparse itself uses locale/terminal variables; assert the helper context
        # binds no environment, including the injected caller environment.
        for platform, normalized, supported in (
                ('linux-gnu', 'linux', True), ('darwin', 'darwin', False),
                ('win32', 'win32', False)):
            with self.subTest(platform=platform), \
                    mock.patch.object(helper, 'repo_identity', side_effect=AssertionError), \
                    mock.patch.object(helper, 'select_target', side_effect=AssertionError), \
                    mock.patch.object(helper, 'Context', wraps=helper.Context) as context, \
                    mock.patch.object(helper.os, 'getcwd', side_effect=AssertionError), \
                    mock.patch.object(helper.Path, 'read_text', side_effect=AssertionError), \
                    mock.patch.object(helper.Path, 'open', side_effect=AssertionError), \
                    mock.patch.object(helper.subprocess, 'run', side_effect=AssertionError):
                out = io.StringIO()
                code = helper.main(['help', '--json'], env=mock.Mock(),
                                   platform=platform, stdout=out)
                self.assertEqual(code, 0)
                self.assertEqual(context.call_args.kwargs['env'], {})
                self.assertEqual(context.call_args.kwargs['cwd'], '.')
                doc = json.loads(out.getvalue())
                self.assertEqual(doc['platform'], normalized)
                self.assertEqual(doc['mutations_supported'], supported)
                self.assertEqual(doc['actions']['status']['platforms'], ['linux', 'darwin'])
                self.assertEqual(doc['actions']['help']['platforms'], ['all'])
                for action in ('setup', 'start', 'stop'):
                    self.assertEqual(doc['actions'][action]['platforms'], ['linux'])

    def test_unknown_action_points_at_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp))
            before = snapshot(h.home)
            for json_mode in (False, True):
                result = subprocess.run(
                    [sys.executable, '-B', str(HELPER), 'bogus',
                     *(['--json'] if json_mode else [])],
                    cwd=h.root, env=dict(h.env), capture_output=True, text=True,
                    timeout=20)
                self.assertEqual(result.returncode, 2)
                if json_mode:
                    doc = json.loads(result.stdout)
                    self.assertEqual(doc['action'], 'bogus')
                    self.assertEqual(doc['error']['code'], 'unknown_action')
                    self.assertFalse(doc['error']['mutated'])
                    self.assertEqual(doc['error']['fix'],
                                     'run /orbi help for the supported actions and their effects')
                else:
                    self.assertIn('error=unknown_action', result.stderr)
                    self.assertIn('fix=run /orbi help', result.stderr)
                self.assertEqual(h.calls(), [])
                self.assertEqual(snapshot(h.home), before)

    def test_help_keeps_python_floor_and_argparse_usage(self):
        out = io.StringIO()
        with mock.patch.object(helper.sys, 'version_info', (3, 10)), \
                mock.patch.object(helper.subprocess, 'run', side_effect=AssertionError):
            code = helper.main(['help', '--json'], stdout=out)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())['error']['code'], 'python_unsupported')
        self.assertFalse(json.loads(out.getvalue())['error']['mutated'])
        for flag in ('-h', '--help'):
            result = subprocess.run([sys.executable, '-B', str(HELPER), flag],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('[status|setup|start|stop|help]', result.stdout)
            for action in ('status', 'setup', 'start', 'stop', 'help'):
                self.assertRegex(result.stdout, rf'{action} \[(none|staging|scheduler)\]')

    def test_default_action_is_status_and_cli_uses_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp))
            before = snapshot(h.home)
            result = subprocess.run(
                [sys.executable, '-B', str(HELPER), '--repo-dir', str(h.repo), '--json'],
                env=dict(h.env), capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            self.assertEqual(document['action'], 'status')
            self.assertEqual(document['deployment']['state'], 'absent')
            self.assertEqual(snapshot(h.home), before)
            self.assertFalse((HELPER.parent / '__pycache__').exists())

    def test_skill_contract_names_the_router_and_high_risk_sections(self):
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        metadata = yaml.safe_load(skill.split('---', 2)[1])
        self.assertEqual(metadata['name'], 'orbi')
        self.assertLessEqual(len(metadata['description']), 60)
        self.assertIn('## Boundaries', skill)
        self.assertEqual(skill.count('**Done when:**'), 1)
        self.assertIn('## Common Rationalizations', skill)
        self.assertIn('| Rationalization | Reality |', skill)
        self.assertIn('## Red Flags', skill)
        self.assertIn('../shared/DEFINITION-OF-DONE.md', skill)
        self.assertIn('references/lifecycle.md', skill)
        self.assertIn('scripts/orbi_control.py', skill)
        self.assertIn('`/orbi [status|setup|start|stop|help]`', skill)
        self.assertIn('**Help first.**', skill)
        self.assertIn("helper's `help`", skill)
        self.assertIn('observed output', skill)
        self.assertIn('macOS', skill)
        self.assertIn('explicit pauses, cutover requirements and human-only gates', skill)
        router = (ROOT / 'skills/ask-kit/SKILL.md').read_text()
        self.assertIn('`/orbi`', router)
        reference = (ROOT / 'skills/orbi/references/lifecycle.md').read_text()
        self.assertIn('[status|setup|start|stop|help]', reference)
        self.assertIn('for lifecycle actions; `help` prints a compact human block', reference)
        for topic in ('PYTHONPATH', 'UV_TOOL_DIR', 'UV_TOOL_BIN_DIR',
                      f'sha:{PIN}', 'five', 'draining', 'is read-only', 'help'):
            self.assertIn(topic, reference)


if __name__ == '__main__':
    unittest.main()
