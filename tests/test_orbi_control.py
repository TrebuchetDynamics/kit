"""Repository-scoped Orbi lifecycle controls (Issue #18).

The helper is exercised through real subprocess boundaries (argv only) with
temporary homes and fake `git|uv|gh|pi|node|orbi|systemctl` tools. No real
scheduler, credentials or host deployment is touched. The fixture deployment
"A" stands for an unrelated running deployment that every scenario must
preserve.
"""
import contextlib
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
    for target, mode in (rule.get("chmod") or {{}}).items():
        os.chmod(target, mode)
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

    def run(self, action, *, platform='linux', dry_run=False, env=None, config=None,
            options=(), failure=None, json_mode=True):
        argv = [action, '--repo-dir', str(self.repo), *options]
        if json_mode:
            argv.append('--json')
        if config is not None:
            argv.extend(['--config', str(config)])
        if dry_run:
            argv.append('--dry-run')
        out, err = io.StringIO(), io.StringIO()
        # Inject before/after a publication or mutating bootstrap/check stage.
        # The real operation still runs for after-failures, exposing interrupted state.
        def invoke():
            return helper.main(argv, env=dict(env or self.env), platform=platform,
                               stdout=out, stderr=err)
        if failure:
            name, when, error = failure
            original = getattr(helper, name)

            def interrupted(*args, **kwargs):
                if when == 'before':
                    raise error
                original(*args, **kwargs)
                raise error

            with mock.patch.object(helper, name, side_effect=interrupted):
                code = invoke()
        else:
            code = invoke()
        document = out.getvalue()
        if json_mode:
            document = json.loads(document) if document.strip() else None
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
            if call['tool'] == 'systemctl':
                self.assertTrue(call['argv'][:2] == ['--user', 'show']
                                and ('ActiveState' in call['argv'] or 'FragmentPath' in call['argv'])
                                or call['argv'][:2] == ['--user', 'is-enabled'], call)
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
        self.assertIs(config['human_review_gate'], False)
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
        self.assertFalse([c for c in dry_calls if c['tool'] == 'uv'])
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
        before = snapshot(conflict.home)
        code, doc, err = conflict.run('setup')
        self.assertEqual(code, 2, err)
        self.assertEqual(doc['error']['code'], 'unit_conflict')
        self.assertIn(str(foreign / 'orbi.toml'), doc['error']['message'])
        self.assertEqual(doc['error']['fix'],
                         'keep one deployment per repository and do not duplicate unit ownership')
        self.assertEqual(snapshot(conflict.home), before)
        self.assert_no_activation(conflict.calls())
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

        # Existing setup is idempotent and keeps its explicit policy and (old) pin.
        first = snapshot(self.h.deploy)
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.assertEqual(snapshot(self.h.deploy), first)
        config_text = (self.h.deploy / 'orbi.toml').read_text()
        (self.h.deploy / 'orbi.toml').write_text(
            config_text.replace(helper.PIN_TRACK, 'sha:' + OLD_PIN)
            .replace('human_review_gate = false', 'human_review_gate = true'))
        first = snapshot(self.h.deploy)
        self.h.deploy_head = OLD_PIN
        self.h.rules()
        self.h.clear_calls()
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + OLD_PIN)
        self.assertIs(self.h.config()['human_review_gate'], True)
        self.assertEqual(snapshot(self.h.deploy), first)
        self.assertFalse(doc['activated'])
        self.assert_no_activation(self.h.calls())
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
            if call['tool'] == 'systemctl':
                self.assertTrue(call['argv'][:2] == ['--user', 'show']
                                and ('ActiveState' in call['argv'] or 'FragmentPath' in call['argv'])
                                or call['argv'][:2] == ['--user', 'is-enabled'], call)
            if call['tool'] == 'orbi':
                self.assertNotIn(call['argv'][0] if call['argv'] else '',
                                 {'setup', 'install-units'}, call)


class FirstDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(Path(self.tmp.name))  # deliberately no donor deployment
        self.metadata = {'providers': {'openai': {
            'baseUrl': 'https://api.openai.com/v1',
            'api': 'openai-responses',
            'models': [{'id': 'gpt-6.1-sol', 'contextWindow': 272000,
                        'maxTokens': 128000}],
        }}}
        self.catalog = self.h.home / 'models.json'
        self.catalog.write_text(json.dumps(self.metadata))
        self.options = ['--pi-providers', str(self.catalog), '--pi-provider', 'openai',
                        '--pi-model', 'gpt-6.1-sol', '--pi-thinking', 'high']

    def test_first_deployment_explicit_preview_and_preparation(self):
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup', options=self.options, dry_run=True)
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['status'], 'planned')
        self.assertFalse(doc['activated'])
        self.assertEqual(snapshot(self.h.home), before)
        code, doc, err = self.h.run('setup', options=self.options)
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['status'], 'prepared')
        self.assertFalse(doc['activated'])
        config = self.h.config()
        self.assertEqual((config['pi_provider'], config['pi_model'], config['pi_thinking']),
                         ('openai', 'gpt-6.1-sol', 'high'))
        self.assertEqual(json.loads((self.h.deploy / '.orbi/pi-providers.json').read_text()),
                         self.metadata)
        calls = self.h.calls()
        self.assertTrue(any(c['tool'] == 'orbi' and c['argv'][0] == 'check'
                            for c in calls))
        SetupBoundaryTests.assert_no_activation(self, calls)

    def test_missing_metadata_has_a_first_deployment_repair(self):
        before = snapshot(self.h.home)
        for dry_run in (True, False):
            code, doc, err = self.h.run('setup', dry_run=dry_run)
            self.assertNotEqual(code, 0)
            self.assertEqual(doc['error']['code'], 'provider_unavailable')
            self.assertFalse(doc['error']['mutated'])
            self.assertIn('--pi-providers', doc['error']['fix'])
            self.assertEqual(snapshot(self.h.home), before)

    def test_invalid_explicit_metadata_fails_before_writes_without_secrets(self):
        cases = ('missing', 'invalid-json', 'not-object', 'providers-list',
                 'provider-not-object', 'unknown-provider', 'unknown-model',
                 'models-not-list', 'missing-context', 'invalid-limit', 'missing-api',
                 'missing-base-url', 'literal-credential', 'bad-variable',
                 'literal-header', 'model-literal-header', 'override-literal-header',
                 'overrides-not-object', 'override-not-object',
                 'symlink', 'symlink-parent')
        for case in cases:
            with self.subTest(case=case):
                h = Harness(Path(self.tmp.name) / case)
                metadata = json.loads(json.dumps(self.metadata))
                entry = metadata['providers']['openai']
                catalog = h.home / 'models.json'
                expected = 'provider_unavailable'
                if case == 'not-object':
                    metadata = []
                elif case == 'providers-list':
                    metadata['providers'] = ['openai']
                elif case == 'provider-not-object':
                    metadata['providers']['openai'] = 'invalid'
                elif case == 'unknown-provider':
                    metadata['providers'] = {'other': entry}
                elif case == 'unknown-model':
                    entry['models'][0]['id'] = 'other'
                elif case == 'models-not-list':
                    entry['models'] = 'invalid'
                elif case == 'missing-context':
                    del entry['models'][0]['contextWindow']
                elif case == 'invalid-limit':
                    entry['models'][0]['maxTokens'] = False
                elif case == 'missing-api':
                    del entry['api']
                elif case == 'missing-base-url':
                    del entry['baseUrl']
                elif case in {'literal-credential', 'bad-variable'}:
                    entry['apiKey'] = SECRET if case == 'literal-credential' else '$' + SECRET
                    expected = 'credential_copy_refused'
                elif case in {'literal-header', 'model-literal-header', 'override-literal-header'}:
                    target = entry if case == 'literal-header' else entry['models'][0]
                    if case == 'override-literal-header':
                        entry['modelOverrides'] = {'other-model': {}}
                        target = entry['modelOverrides']['other-model']
                    target['headers'] = {'Authorization': 'Bearer ' + SECRET}
                    expected = 'credential_copy_refused'
                elif case == 'overrides-not-object':
                    entry['modelOverrides'] = []
                elif case == 'override-not-object':
                    entry['modelOverrides'] = {'other-model': None}
                catalog.write_text(SECRET + '{' if case == 'invalid-json'
                                   else json.dumps(metadata))
                if case == 'missing':
                    catalog.unlink()
                elif case == 'symlink':
                    original = h.home / 'original.json'
                    catalog.rename(original)
                    catalog.symlink_to(original)
                    expected = 'unknown_target'
                elif case == 'symlink-parent':
                    alias = h.home / 'alias'
                    alias.symlink_to(h.home, target_is_directory=True)
                    catalog = alias / 'models.json'
                    expected = 'unknown_target'
                before = snapshot(h.home)
                options = ['--pi-providers', str(catalog), '--pi-provider', 'openai',
                           '--pi-model', 'gpt-6.1-sol']
                for dry_run in (True, False):
                    code, doc, err = h.run('setup', options=options, dry_run=dry_run)
                    self.assertNotEqual(code, 0, (doc, err))
                    self.assertEqual(doc['error']['code'], expected)
                    self.assertFalse(doc['error']['mutated'])
                    self.assertNotIn(SECRET, json.dumps(doc) + err)
                    self.assertEqual(snapshot(h.home), before)
                    self.assertFalse(any(c['tool'] != 'git' for c in h.calls()))

    def test_incomplete_and_non_setup_selectors_are_refused(self):
        before = snapshot(self.h.home)
        options = (['--pi-thinking', 'high'], self.options[:2], self.options[2:6],
                   self.options[:4], [*self.options[:5], ''],
                   [*self.options[:6], '--pi-thinking', ' '])
        for action, selection in [('setup', item) for item in options] + [
                (action, self.options) for action in ('status', 'start', 'stop')]:
            with self.subTest(action=action, selection=selection):
                code, doc, err = self.h.run(action, options=selection)
                self.assertEqual(code, 2, (doc, err))
                self.assertEqual(doc['error']['code'], 'invalid_provider_selection')
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertEqual(self.h.calls(), [])

    def test_bootstrap_cannot_overwrite_existing_selection(self):
        a = self.h.add_deployment_a()
        code, doc, err = self.h.run('setup', options=self.options)
        self.assertEqual(code, 0, (doc, err))
        config_path = self.h.deploy / 'orbi.toml'
        # Existing deployments retain deliberate transport and pin choices.
        config_path.write_text(config_path.read_text().replace(
            helper.PIN_TRACK, 'sha:' + OLD_PIN))
        self.h.deploy_head = OLD_PIN
        self.h.rules()
        before = snapshot(self.h.home)
        for dry_run in (True, False):
            self.h.clear_calls()
            code, doc, err = self.h.run('setup', options=self.options, dry_run=dry_run)
            self.assertEqual(code, 2, (doc, err))
            self.assertEqual(doc['error']['code'], 'provider_override_refused')
            self.assertEqual(snapshot(self.h.home), before)
            self.assertFalse(any(c['tool'] != 'git' for c in self.h.calls()))
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(snapshot(self.h.home), before)
        self.assertEqual(snapshot(a['deploy']), a['snapshot'])

    def test_check_failure_recovers_without_activation(self):
        self.h.rules({'tool': 'orbi', 'argv_contains': ['check'], 'exit': 1,
                      'stderr': 'check=transport reason="transport mismatch" '
                                'fix="orbi setup --config target"'})
        code, doc, err = self.h.run('setup', options=self.options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'validation_failed')
        self.assertTrue(doc['error']['mutated'])
        self.assertIn('partially prepared', doc['error']['fix'])
        self.assertIn('`/orbi setup` without bootstrap inputs', doc['error']['fix'])
        self.assertNotIn('orbi setup --config target', doc['error']['fix'])
        self.h.rules()
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['status'], 'prepared')
        self.assertFalse(doc['activated'])
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_references_and_model_level_api_need_no_credential_copy(self):
        entry = self.metadata['providers']['openai']
        entry['models'][0]['api'] = entry.pop('api')
        for index, reference in enumerate(('$OPENAI_API_KEY', '${OPENAI_API_KEY}')):
            with self.subTest(reference=reference):
                h = Harness(Path(self.tmp.name) / ('reference-' + str(index)))
                entry['apiKey'] = reference
                entry['headers'] = {'Authorization': reference}
                entry['models'][0]['headers'] = {'X-Api-Key': reference}
                entry['modelOverrides'] = {'other-model': {'headers': {'X-Api-Key': reference}}}
                catalog = h.home / 'models.json'
                catalog.write_text(json.dumps(self.metadata))
                code, doc, err = h.run('setup', options=[
                    '--pi-providers', str(catalog), '--pi-provider', 'openai',
                    '--pi-model', 'gpt-6.1-sol'])
                self.assertEqual(code, 0, (doc, err))
                self.assertNotIn('pi_thinking', h.config())
                self.assertEqual(json.loads((h.deploy / '.orbi/pi-providers.json').read_text()),
                                 self.metadata)
                self.assertNotIn('OPENAI_API_KEY=', (h.deploy / '.orbi/env').read_text())
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_donor_credentials_also_fail_before_writes(self):
        a = self.h.add_deployment_a()
        a['metadata']['providers']['openrouter']['apiKey'] = SECRET
        (a['deploy'] / '.orbi/pi-providers.json').write_text(json.dumps(a['metadata']))
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'credential_copy_refused')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertNotIn(SECRET, json.dumps(doc) + err)

    def test_unsupported_transport_fails_before_writes(self):
        before = snapshot(self.h.home)
        for origin in ('http://github.com/example/kit.git',
                       'git://github.com/example/kit.git',
                       'https://notgithub.com/example/kit.git'):
            with self.subTest(origin=origin):
                self.h.rules({'tool': 'git', 'argv_contains': ['config', 'remote.origin.url'],
                              'stdout': origin + '\n'})
                code, doc, err = self.h.run('setup', options=self.options)
                self.assertEqual(code, 2, (doc, err))
                self.assertEqual(doc['error']['code'], 'transport_unsupported')
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse(any(c['tool'] != 'git' for c in self.h.calls()))

    def test_origin_transport_is_preserved(self):
        for index, (origin, transport) in enumerate((
                ('git@github.com:example/kit.git', 'ssh'),
                ('ssh://git@github.com/example/kit.git', 'ssh'),
                ('https://github.com/example/kit.git', 'https'))):
            with self.subTest(origin=origin):
                h = Harness(Path(self.tmp.name) / str(index))
                h.add_deployment_a()  # donor path also preserves SSH
                h.rules({'tool': 'git',
                         'argv_contains': [str(h.repo), 'config', 'remote.origin.url'],
                         'stdout': origin + '\n'})
                code, doc, err = h.run('setup')
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(h.config()['git_transport'], transport)
                self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])
                self.assertFalse(any(c['tool'] == 'git' and
                                     set(c['argv']) & {'set-url', 'remote'}
                                     for c in h.calls()))
                SetupBoundaryTests.assert_no_activation(self, h.calls())


class SetupRecoveryTests(unittest.TestCase):
    setUp = FirstDeploymentTests.setUp
    def test_preflight_tool_list_refuses_before_lock(self):
        self.h.bootstrap.unlink()
        for rule, expected in (({'stdout': 'orbi-cli 1.0'}, 'bootstrap_conflict'),
                               ({'exit': 1, 'stderr': SECRET}, 'bootstrap_unverified')):
            with self.subTest(expected=expected):
                self.h.rules({'tool': 'uv', 'argv_contains': ['tool', 'list'], **rule})
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('setup', options=self.options)
                self.assertNotEqual(code, 0)
                self.assertEqual(doc['error']['code'], expected)
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertNotIn(SECRET, json.dumps(doc) + err)

    def test_setup_requires_verified_timer_enablement(self):
        self.assertEqual(self.h.run('setup', options=self.options)[0], 0)
        for state, status, expected in (('enabled-runtime', 0, 'setup_busy'),
                                        ('', 1, 'scheduler_unavailable'),
                                        ('enabled', 1, 'scheduler_unavailable')):
            with self.subTest(state=state, status=status):
                self.h.rules({'tool': 'systemctl', 'argv_contains': ['is-enabled'],
                              'stdout': state + '\n', 'exit': status, 'stderr': SECRET},
                             *self.h.scheduler_rules())
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('setup')
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], expected)
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertNotIn(SECRET, json.dumps(doc) + err)
                SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_setup_refuses_unverified_loaded_service_ownership(self):
        self.assertEqual(self.h.run('setup', options=self.options)[0], 0)
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        self.h.rules({'tool': 'systemctl',
                      'argv_contains': ['show', f'{prefix}@1.service', 'FragmentPath'],
                      'exit': 1, 'stderr': SECRET})
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_malformed_resume_paths_and_unreadable_env_have_receipts(self):
        self.assertEqual(self.h.run('setup', options=self.options)[0], 0)
        config = self.h.deploy / 'orbi.toml'
        original = config.read_bytes()
        provider = self.h.deploy / '.orbi/pi-providers.json'
        provider.unlink()
        options = [*self.options, '--resume-setup']
        for field in ('deploy_home', 'repo_dir', 'pi_providers', 'pi_provider', 'pi_model',
                      'pi_thinking', 'git_transport', 'engine_source_track'):
            with self.subTest(field=field):
                config.write_text(re.sub(rf'^{field} = .*$', field + ' = 42',
                                         original.decode(), flags=re.MULTILINE))
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('setup', config=config, options=options)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], 'config_invalid')
                self.assertEqual(doc['steps'][-1]['status'], 'failed')
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
        config.write_bytes(original + b'# invalid UTF-8: ' + SECRET.encode() + b'\xff\n')
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup', config=config, options=options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'config_invalid')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        config.write_bytes(original)
        env = self.h.deploy / '.orbi/env'
        env.write_bytes(b'CUSTOM=' + SECRET.encode() + b'\xff\n')
        # Resume may publish the missing provider before discovering an invalid env encoding.
        code, doc, err = self.h.run('setup', config=config, options=options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'file_encoding_invalid')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['steps'][-1]['step'], 'write_isolation_env')
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        self.assertEqual(env.read_bytes(), b'CUSTOM=' + SECRET.encode() + b'\xff\n')
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_publication_interruptions_resume_config_last(self):
        for name in ('write_provider_metadata', 'write_env', 'write_config'):
            for when in ('before', 'after'):
                with self.subTest(name=name, when=when):
                    h = Harness(Path(self.tmp.name) / (name + when))
                    h.add_deployment_a()
                    code, doc, err = h.run('setup', failure=(name, when, OSError(SECRET)))
                    self.assertNotEqual(code, 0)
                    self.assertEqual(doc['error']['code'], 'filesystem_error')
                    self.assertTrue(doc['error']['mutated'])
                    self.assertFalse(doc['activated'])
                    self.assertEqual(doc['steps'][-1]['status'], 'failed')
                    self.assertEqual(doc['steps'][-1]['mutation'], 'possible')
                    self.assertNotIn(SECRET, json.dumps(doc) + err)
                    config = h.deploy / 'orbi.toml'
                    if config.exists():
                        self.assertTrue((h.deploy / '.orbi/env').is_file())
                        self.assertTrue((h.deploy / '.orbi/pi-providers.json').is_file())
                    code, doc, err = h.run('setup')
                    self.assertEqual(code, 0, (doc, err))
                    self.assertEqual((h.deploy / '.orbi/env').stat().st_mode & 0o777, 0o600)
                    self.assertEqual((h.deploy / '.orbi/pi-providers.json').stat().st_mode & 0o777,
                                     0o600)
                    SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_explicit_legacy_resume_is_bounded_and_idempotent(self):
        code, doc, err = self.h.run('setup', options=self.options)
        self.assertEqual(code, 0, (doc, err))
        config = self.h.deploy / 'orbi.toml'
        original = config.read_bytes()
        provider = self.h.deploy / '.orbi/pi-providers.json'
        provider.unlink()
        options = [*self.options[:6], '--resume-setup']  # omitted thinking inherits high
        for repeat in range(2):
            code, doc, err = self.h.run('setup', config=config, options=options)
            self.assertEqual(code, 0, (doc, err))
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(json.loads(provider.read_text()), self.metadata)
            self.assertFalse(doc['activated'])
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup', config=config,
                                   options=[*options, '--pi-thinking', 'low'])
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'resume_refused')
        self.assertEqual(snapshot(self.h.home), before)

    def test_existing_transport_mismatch_precedes_writes(self):
        self.assertEqual(self.h.run('setup', options=self.options)[0], 0)
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace('git_transport = "https"',
                                                    'git_transport = "ssh"'))
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'transport_mismatch')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)

    def test_mutating_stage_timeout_receipt_never_retries(self):
        for name in ('stage_checkout', 'install_bootstrap', 'run_orbi_check'):
            with self.subTest(name=name):
                h = Harness(Path(self.tmp.name) / name)
                h.add_deployment_a()
                if name == 'install_bootstrap':
                    h.bootstrap.unlink()
                code, doc, err = h.run('setup', failure=(name, 'before', helper.ControlError(
                    'command_timeout', 'timed out', fix='inspect manually; never retry unchanged')))
                self.assertNotEqual(code, 0)
                self.assertEqual(doc['error']['code'], 'command_timeout')
                self.assertTrue(doc['error']['mutated'])
                self.assertTrue(doc['steps'][:-1])
                self.assertEqual(doc['steps'][-1]['status'], 'failed')
                self.assertEqual(doc['steps'][-1]['mutation'], 'possible')
                self.assertFalse(doc['activated'])


    def test_python_selection_and_command_order(self):
        for variant, selected in (('compatible', 'python3'), ('older', '3.14'), ('absent', '3.14')):
            with self.subTest(variant=variant):
                h = Harness(Path(self.tmp.name) / variant)
                h.add_deployment_a()
                h.bootstrap.unlink()
                (h.bin / 'python3').symlink_to(h.bin / '_fake.py')
                h.rules({'tool': 'python3', 'exit': 0 if variant == 'compatible' else 1})
                which = helper.Context.which

                def find(ctx, name):
                    return None if name == 'python3' and variant == 'absent' else which(ctx, name)

                with mock.patch.object(helper.Context, 'which', find):
                    before = snapshot(h.home)
                    code, doc, err = h.run('setup', dry_run=True)
                    self.assertEqual(code, 0, (doc, err))
                    self.assertEqual(doc['prerequisites']['python'], selected)
                    self.assertEqual(snapshot(h.home), before)
                    self.assertEqual(doc['deployment']['source'], 'unverified')
                    for name in ('stage_checkout', 'install_bootstrap', 'validate_non_activating'):
                        self.assertIn({'step': name, 'status': 'planned'}, doc['steps'])
                    h.clear_calls()
                    # Fake successful install creates the real fake launcher executable.
                    h.rules({'tool': 'python3', 'exit': 0 if variant == 'compatible' else 1},
                            {'tool': 'uv', 'argv_contains': ['tool', 'install'],
                             'write': {str(h.bootstrap): (h.bin / '_fake.py').read_text()},
                             'chmod': {str(h.bootstrap): 0o755}})
                    code, doc, err = h.run('setup')
                    self.assertEqual(code, 0, (doc, err))
                calls = h.calls()
                listing = next(i for i, c in enumerate(calls)
                               if c['tool'] == 'uv' and c['argv'] == ['tool', 'list'])
                clone = next(i for i, c in enumerate(calls)
                             if c['tool'] == 'git' and c['argv'][0] == 'clone')
                install = next(c for c in calls if c['tool'] == 'uv' and 'install' in c['argv'])
                self.assertLess(listing, clone)
                self.assertEqual(install['argv'][4], selected)
                self.assertNotIn('--force', install['argv'])
                SetupBoundaryTests.assert_no_activation(self, calls)

    def test_tool_list_timeout_is_read_only_and_not_retried(self):
        self.h.bootstrap.unlink()
        before = snapshot(self.h.home)
        run = helper.Context.run
        attempts = []

        def timed(ctx, argv, **kwargs):
            if list(argv)[1:] == ['tool', 'list']:
                attempts.append(argv)
                raise helper.ControlError('command_timeout', 'private timeout ' + SECRET)
            return run(ctx, argv, **kwargs)

        with mock.patch.object(helper.Context, 'run', timed):
            code, doc, err = self.h.run('setup', options=self.options)
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'command_timeout')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(len(attempts), 1)
        self.assertEqual(snapshot(self.h.home), before)
        self.assertNotIn(SECRET, json.dumps(doc) + err)

    def test_resume_unsafe_states_preserve_every_file(self):
        cases = ('model', 'provider', 'thinking', 'content', 'invalid-provider', 'malformed',
                 'external-provider', 'invalid-provider-path', 'external-config', 'changed-pin', 'changed-head',
                 'unknown-checkout', 'symlink-provider', 'symlink-env', 'foreign-owner',
                 'duplicate', 'foreign-unit', 'active-worker', 'unknown-worker', 'enabled-timer')
        for case in cases:
            with self.subTest(case=case):
                h = Harness(Path(self.tmp.name) / case)
                h.add_deployment_a()
                self.assertEqual(h.run('setup')[0], 0)
                config = h.deploy / 'orbi.toml'
                provider = h.deploy / '.orbi/pi-providers.json'
                catalog = h.home / 'models.json'
                catalog.write_bytes(provider.read_bytes())
                provider.unlink()
                options = ['--resume-setup', '--pi-providers', str(catalog),
                           '--pi-provider', 'openrouter', '--pi-model', 'vendor/model-a']
                if case in ('model', 'provider'):
                    options[-1 if case == 'model' else -3] = 'other'
                elif case == 'thinking':
                    options += ['--pi-thinking', 'high']
                elif case in ('content', 'invalid-provider'):
                    provider.write_text('{bad ' + SECRET if case == 'invalid-provider' else '{}')
                elif case == 'malformed':
                    config.write_text('bad=' + SECRET)
                elif case == 'external-provider':
                    config.write_text(config.read_text().replace('.orbi/pi-providers.json',
                                                                str(h.home / 'external.json')))
                elif case == 'invalid-provider-path':
                    config.write_text(config.read_text().replace('".orbi/pi-providers.json"', '42'))
                elif case == 'external-config':
                    destination = h.home / 'external.toml'
                    config.rename(destination)
                    config = destination
                elif case == 'changed-pin':
                    config.write_text(config.read_text().replace(PIN, OLD_PIN))
                elif case == 'changed-head':
                    h.deploy_head = OLD_PIN
                    h.rules()
                elif case == 'unknown-checkout':
                    h.rules({'tool': 'git', 'argv_contains': [str(h.deploy), 'remote.origin.url'],
                             'stdout': 'https://github.com/other/not-orbi'})
                elif case == 'symlink-provider':
                    provider.symlink_to(catalog)
                elif case == 'symlink-env':
                    env = h.deploy / '.orbi/env'
                    env.unlink()
                    env.symlink_to(catalog)
                elif case == 'duplicate':
                    duplicate = h.data_home / 'duplicate'
                    duplicate.mkdir()
                    (duplicate / 'orbi.toml').write_bytes(config.read_bytes())
                elif case == 'foreign-unit':
                    prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                    (h.unit_dir / f'{prefix}@.service').write_text(
                        '[Service]\nEnvironment="ORBI_CONFIG=' + str(h.a['config']) + '"\n')
                elif case in ('active-worker', 'unknown-worker', 'enabled-timer'):
                    h.rules(*h.scheduler_rules(services={1: 'active' if case == 'active-worker'
                                                        else 'unknown' if case == 'unknown-worker'
                                                        else 'inactive'},
                                               enabled={1: case == 'enabled-timer'}))
                before = snapshot(h.home)
                # Exercise the real uid guard without chown or another user's files.
                with mock.patch.object(helper.os, 'getuid',
                                       return_value=os.getuid() + (case == 'foreign-owner')):
                    code, doc, err = h.run('setup', config=config, options=options)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(h.home), before)
                self.assertNotIn(SECRET, json.dumps(doc) + err)
                self.assertTrue(doc['error']['fix'])
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_resume_option_boundary_and_context_free_help(self):
        before = snapshot(self.h.home)
        for action, config, options in (
                ('status', None, ['--resume-setup']),
                ('start', None, ['--resume-setup']),
                ('stop', None, ['--resume-setup']),
                ('setup', None, ['--resume-setup', *self.options]),
                ('setup', self.h.home / 'missing.toml', ['--resume-setup'])):
            code, doc, err = self.h.run(action, config=config, options=options)
            self.assertEqual(code, 2, (doc, err))
            self.assertEqual(doc['error']['code'], 'invalid_resume_selection')
            self.assertFalse(doc['error']['mutated'])
        code, doc, err = self.h.run('help', config='/missing', options=['--resume-setup'])
        self.assertEqual(code, 0, (doc, err))
        self.assertIn('--resume-setup', doc['options'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertEqual(self.h.calls(), [])

    def test_lock_rechecks_concurrent_changes(self):
        import contextlib
        for change in ('config', 'provider', 'env', 'duplicate', 'unit', 'worker', 'pin', 'origin',
                       'bootstrap'):
            with self.subTest(change=change):
                h = Harness(Path(self.tmp.name) / change)
                h.add_deployment_a()
                self.assertEqual(h.run('setup')[0], 0)
                config = h.deploy / 'orbi.toml'
                provider = h.deploy / '.orbi/pi-providers.json'
                catalog = h.home / 'models.json'
                catalog.write_bytes(provider.read_bytes())
                provider.unlink()
                locked = helper.locked
                changed = []

                @contextlib.contextmanager
                def concurrent(ctx, key):
                    with locked(ctx, key):
                        if change in ('config', 'env'):
                            path = config if change == 'config' else h.deploy / '.orbi/env'
                            path.write_text(path.read_text() + '# concurrent change\n')
                        elif change == 'provider':
                            provider.write_text('{}')
                        elif change == 'duplicate':
                            duplicate = h.data_home / 'duplicate'
                            duplicate.mkdir()
                            (duplicate / 'orbi.toml').write_bytes(config.read_bytes())
                        elif change == 'unit':
                            prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                            (h.unit_dir / f'{prefix}@.service').write_text(
                                '[Service]\nEnvironment="ORBI_CONFIG=' + str(h.a['config']) + '"\n')
                        elif change == 'worker':
                            h.rules(*h.scheduler_rules(services={1: 'active'}))
                        elif change == 'pin':
                            h.deploy_head = OLD_PIN
                            h.rules()
                        elif change == 'bootstrap':
                            h.bootstrap.unlink()
                        else:
                            h.rules({'tool': 'git', 'argv_contains': [str(h.repo), 'remote.origin.url'],
                                     'stdout': 'git@github.com:example/kit.git'})
                        changed.append(snapshot(h.home))
                        yield

                with mock.patch.object(helper, 'locked', concurrent):
                    code, doc, err = h.run('setup', config=config, options=[
                        '--resume-setup', '--pi-providers', str(catalog),
                        '--pi-provider', 'openrouter', '--pi-model', 'vendor/model-a'])
                self.assertNotEqual(code, 0, (doc, err))
                self.assertTrue(doc['error']['mutated'])  # acquiring the lock wrote
                self.assertEqual(doc['steps'][-1]['step'], 'recheck_target')
                self.assertEqual(snapshot(h.home), changed[0])
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_atomic_replace_failure_preserves_original_bytes_and_modes(self):
        self.assertEqual(self.h.run('setup', options=self.options)[0], 0)
        path = self.h.deploy / '.orbi/env'
        original = 'CUSTOM_ENTRY=preserved\nPATH=/old\n'
        path.write_text(original)
        path.chmod(0o640)
        before = snapshot(self.h.deploy)
        with mock.patch.object(helper.os, 'replace', side_effect=OSError(SECRET)):
            code, doc, err = self.h.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'filesystem_error')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.deploy), before)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, (doc, err))
        self.assertIn('CUSTOM_ENTRY=preserved', path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.h.deploy / 'orbi.toml').stat().st_mode & 0o777, 0o644)

    def test_conflicting_unpublished_files_refuse_before_lock(self):
        for relative in ('.orbi/env', '.orbi/pi-providers.json'):
            with self.subTest(relative=relative):
                h = Harness(Path(self.tmp.name) / Path(relative).name)
                h.add_deployment_a()
                (h.deploy / '.orbi').mkdir(parents=True)
                (h.deploy / relative).write_text(SECRET)
                before = snapshot(h.home)
                code, doc, err = h.run('setup')
                self.assertEqual(code, 2, (doc, err))
                self.assertEqual(doc['error']['code'], 'publication_conflict')
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(h.home), before)
                self.assertNotIn(SECRET, json.dumps(doc) + err)

    def test_public_cli_success_and_failure_journey(self):
        argv = [sys.executable, '-B', str(HELPER), 'setup', '--repo-dir', str(self.h.repo),
                '--json', *self.options]
        proc = subprocess.run(argv, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['status'], 'prepared')
        self.assertFalse(json.loads(proc.stdout)['activated'])
        config = self.h.deploy / 'orbi.toml'
        provider = self.h.deploy / '.orbi/pi-providers.json'
        provider.unlink()
        argv += ['--config', str(config), '--resume-setup']
        proc = subprocess.run(argv, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        provider.write_text('invalid ' + SECRET)
        before = snapshot(self.h.home)
        proc = subprocess.run(argv, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        doc = json.loads(proc.stdout)
        self.assertEqual(doc['error']['code'], 'resume_refused')
        self.assertIn('preserve', doc['error']['fix'])
        self.assertNotIn(SECRET, proc.stdout + proc.stderr)
        self.assertEqual(snapshot(self.h.home), before)
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())


    def test_atomic_create_failure_leaves_complete_or_absent_files(self):
        for filename in ('pi-providers.json', 'env', 'orbi.toml'):
            for when in ('before', 'after'):
                with self.subTest(filename=filename, when=when):
                    h = Harness(Path(self.tmp.name) / (filename + when))
                    h.add_deployment_a()
                    link = helper.os.link

                    def interrupted(source, destination, **kwargs):
                        if Path(destination).name == filename:
                            if when == 'after':
                                link(source, destination, **kwargs)
                            raise OSError(SECRET)
                        return link(source, destination, **kwargs)

                    with mock.patch.object(helper.os, 'link', interrupted):
                        code, doc, err = h.run('setup')
                    self.assertNotEqual(code, 0)
                    self.assertEqual(doc['error']['code'], 'filesystem_error')
                    self.assertEqual(doc['steps'][-1]['mutation'], 'possible')
                    destination = h.deploy / (filename if filename == 'orbi.toml'
                                              else '.orbi/' + filename)
                    self.assertEqual(destination.exists(), when == 'after')
                    if when == 'after':
                        if filename == 'pi-providers.json':
                            self.assertEqual(json.loads(destination.read_text()), h.a['metadata'])
                        elif filename == 'orbi.toml':
                            self.assertEqual(tomllib.loads(destination.read_text())['source_repos'],
                                             [REPO])
                        else:
                            self.assertEqual(env_dict(destination.read_text())['PYTHONPATH'],
                                             str(h.deploy / 'src'))
                    self.assertFalse(list(h.deploy.rglob('.*.????????')))
                    self.assertNotIn(SECRET, json.dumps(doc) + err)
                    self.assertEqual(h.run('setup')[0], 0)
                    self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])
                    SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_completed_stages_then_exception_keep_truthful_receipt(self):
        for name in ('stage_checkout', 'install_bootstrap', 'run_orbi_check'):
            with self.subTest(name=name):
                h = Harness(Path(self.tmp.name) / name)
                h.add_deployment_a()
                if name == 'install_bootstrap':
                    h.bootstrap.unlink()
                    h.rules({'tool': 'uv', 'argv_contains': ['tool', 'install'],
                             'write': {str(h.bootstrap): (h.bin / '_fake.py').read_text()},
                             'chmod': {str(h.bootstrap): 0o755}})
                code, doc, err = h.run('setup', failure=(name, 'after', OSError(SECRET)))
                self.assertNotEqual(code, 0)
                self.assertEqual(doc['error']['code'], 'filesystem_error')
                self.assertEqual(doc['original_error'], 'filesystem_error')
                self.assertEqual(doc['target'], str(h.deploy / 'orbi.toml'))
                self.assertTrue(doc['error']['mutated'])
                self.assertEqual(doc['steps'][-1]['mutation'], 'possible')
                self.assertTrue(doc['steps'][:-1])
                self.assertFalse(doc['activated'])
                self.assertNotIn(SECRET, json.dumps(doc) + err)
                self.assertEqual(h.run('setup')[0], 0)
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_new_target_ownership_rechecked_after_lock(self):
        import contextlib
        h = self.h
        locked = helper.locked
        written = []

        @contextlib.contextmanager
        def concurrent(ctx, key):
            with locked(ctx, key):
                h.deploy.mkdir()
                (h.deploy / 'orbi.toml').write_text(
                    'source_repos = ["other/repo"]\nunit_name = "foreign"\n')
                written.append(snapshot(h.home))
                yield

        with mock.patch.object(helper, 'locked', concurrent):
            code, doc, err = h.run('setup', options=self.options)
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'target_changed')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(snapshot(h.home), written[0])
        self.assertFalse((h.deploy / '.orbi').exists())
        SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_validation_diagnostics_never_echo_child_secrets(self):
        self.h.rules({'tool': 'orbi', 'argv_contains': ['check'], 'exit': 1,
                      'stderr': 'check=' + SECRET + ' reason="' + SECRET + '"'})
        code, doc, err = self.h.run('setup', options=self.options)
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'validation_failed')
        self.assertEqual(doc['steps'][-1]['step'], 'validate_non_activating')
        self.assertTrue(doc['error']['mutated'])
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())


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


class PartialLifecycleReceiptTests(unittest.TestCase):
    def setUp(self):
        self.h = LifecycleSequenceTests.fresh(self)
        self.prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        self.config = self.h.deploy / 'orbi.toml'
        self.config.write_text(self.config.read_text().replace('max_concurrency = 1',
                                                             'max_concurrency = 2'))
        self.h.env['PRIVATE_SENTINEL'] = SECRET

    def mutations(self):
        return [c['argv'] for c in self.h.calls() if c['tool'] == 'systemctl'
                and set(c['argv']) & {'enable', 'disable', 'start', 'stop', 'kill', 'restart'}]

    def bounded_run(self, failed):
        original = helper.Context.run

        def run(ctx, argv, **kwargs):
            if [str(part) for part in argv] == ['systemctl', *failed]:
                kwargs['timeout'] = 0.2
            return original(ctx, argv, **kwargs)
        return mock.patch.object(helper.Context, 'run', run)

    def assert_receipt(self, doc, code, step, unit, completed):
        self.assertEqual(doc['error']['code'], code)
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['target'], str(self.config))
        self.assertEqual(doc['deployment']['unit_name'], helper.derive_unit_name(REPO))
        self.assertEqual(doc['original_error'], code)
        self.assertEqual(doc['steps'][-1], {'step': step, 'unit': unit,
                                         'status': 'failed', 'error': code,
                                         'mutation': 'possible'})
        self.assertEqual(doc[completed[0]], completed[1])
        self.assertIn('/orbi status', doc['error']['fix'])
        self.assertNotIn('evidence', doc['error'])
        self.assertNotIn(SECRET, json.dumps(doc))

    def test_partial_disable_timeout_and_exit_receipts(self):
        for failed_index in (1, 2):
            for failure in ('exit', 'timeout'):
                for json_mode in (True, False):
                    with self.subTest(index=failed_index, failure=failure, json=json_mode):
                        timers = [f'{self.prefix}@{i}.timer' for i in range(1, failed_index + 1)]
                        failed = ['--user', 'disable', '--now', timers[-1]]
                        self.h.rules({'tool': 'systemctl', 'argv_contains': ['disable', timers[-1]],
                                      'exit': 7, 'stderr': SECRET,
                                      'sleep': 2 if failure == 'timeout' else 0},
                                     *self.h.scheduler_rules(timers={i: 'active' for i in range(1, 6)},
                                                             enabled={i: True for i in range(1, 6)}))
                        self.h.clear_calls()
                        with self.bounded_run(failed):
                            code, doc, err = self.h.run('stop', json_mode=json_mode)
                        expected = 'command_timeout' if failure == 'timeout' else 'command_failed'
                        self.assertEqual(code, 1)
                        self.assertEqual(self.mutations(), [['--user', 'disable', '--now', t]
                                                           for t in timers])
                        if json_mode:
                            self.assert_receipt(doc, expected, 'disable_timer', timers[-1],
                                                ('disabled_timers', timers[:-1]))
                            self.assertEqual(doc['scheduler']['state'], 'ok')
                            self.assertTrue(doc['scheduler']['timers'][timers[-1]]['enabled'])
                        else:
                            self.assertIn('error=' + expected, err)
                            self.assertIn('mutated=True', err)
                            self.assertIn('target=' + str(self.config), err)
                            self.assertIn('unit=' + timers[-1], err)
                            self.assertIn('disabled_timers=' + ','.join(timers[:-1]) + '\n', err)
                            self.assertIn('mutation=possible', err)
                            self.assertNotIn(SECRET, err)
                        self.assertEqual(snapshot(self.h.a['deploy']), self.h.a['snapshot'])

    def test_start_direct_failures_retain_upstream_and_completed_timers(self):
        for failed_step in ('enable_first', 'enable_later', 'first_tick'):
            for failure in ('exit', 'timeout', 'snapshot_unavailable'):
                with self.subTest(step=failed_step, failure=failure):
                    timers = [f'{self.prefix}@{i}.timer' for i in (1, 2)]
                    service = f'{self.prefix}@1.service'
                    index = 1 if failed_step == 'enable_first' else 2
                    failed_unit = service if failed_step == 'first_tick' else timers[index - 1]
                    failed = (['--user', 'start', service] if failed_step == 'first_tick'
                              else ['--user', 'enable', '--now', failed_unit])
                    marker = self.h.root / 'failed'
                    marker.unlink(missing_ok=True)
                    self.h.rules({'tool': 'systemctl', 'argv_contains': failed,
                                  'exit': 7, 'stderr': SECRET, 'write': {str(marker): 'possible'},
                                  'sleep': 2 if failure == 'timeout' else 0},
                                 *([{'tool': 'systemctl', 'argv_contains': ['show'],
                                     'if_exists': str(marker), 'exit': 1, 'stderr': SECRET}]
                                   if failure == 'snapshot_unavailable' else []),
                                 *self.h.scheduler_rules())
                    self.h.clear_calls()
                    with self.bounded_run(failed):
                        code, doc, err = self.h.run('start')
                    self.assertEqual(code, 1, err)
                    expected = 'command_timeout' if failure == 'timeout' else 'command_failed'
                    completed = timers if failed_step == 'first_tick' else timers[:index - 1]
                    self.assert_receipt(doc, expected,
                                        'first_tick' if failed_step == 'first_tick' else 'activate_timer',
                                        failed_unit, ('activated_timers', completed))
                    self.assertEqual(doc['activation'], 'possible')
                    self.assertIn('may already be activated', doc['error']['message'])
                    self.assertEqual([s['step'] for s in doc['steps'][:4]],
                                     ['reuse_existing_deployment', 'lock', 'upstream_setup', 'install_units'])
                    self.assertEqual(self.mutations(),
                                     [['--user', 'enable', '--now', t] for t in completed] + [failed])
                    commands = [c['argv'][0] for c in self.h.calls() if c['tool'] == 'orbi'
                                and c['argv'][0] in {'setup', 'install-units'}]
                    self.assertEqual(commands, ['setup', 'install-units'])
                    mutations = self.mutations()
                    operations = [(c['tool'], c['argv'][0] if c['tool'] == 'orbi' else c['argv'])
                                  for c in self.h.calls()
                                  if (c['tool'] == 'orbi' and c['argv'][0] in {'setup', 'install-units'})
                                  or (c['tool'] == 'systemctl' and c['argv'] in mutations)]
                    self.assertEqual(operations, [('orbi', 'setup'), ('orbi', 'install-units')]
                                     + [('systemctl', argv) for argv in mutations])
                    if failure == 'snapshot_unavailable':
                        self.assertEqual(doc['scheduler']['state'], 'unavailable')

    def test_post_activation_observation_and_failed_recovery_snapshot(self):
        marker = self.h.root / 'installed'
        self.h.rules({'tool': 'orbi', 'argv_contains': ['install-units'],
                      'write': {str(marker): 'installed'}},
                     {'tool': 'systemctl', 'argv_contains': ['show'],
                      'if_exists': str(marker), 'exit': 1, 'stderr': SECRET},
                     *self.h.scheduler_rules())
        code, doc, err = self.h.run('start')
        self.assertEqual(code, 1, err)
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['activation'], 'possible')
        self.assertEqual(doc['steps'][-1]['step'], 'observe_scheduler')
        self.assertEqual(doc['steps'][-1]['mutation'], 'none')
        self.assertIn({'step': 'install_units', 'status': 'ok'}, doc['steps'])
        self.assertEqual(doc['scheduler']['state'], 'unavailable')
        self.assertEqual(self.mutations(), [])
        self.assertNotIn(SECRET, json.dumps(doc))

    def test_lock_only_and_release_errors_are_structured_and_redacted(self):
        original = helper.locked
        for action in ('start', 'stop'):
            for phase in ('acquire', 'release'):
                with self.subTest(action=action, phase=phase):
                    self.h.rules(*self.h.scheduler_rules())
                    self.h.clear_calls()

                    @contextlib.contextmanager
                    def broken_lock(ctx, key):
                        with original(ctx, key):
                            if phase == 'acquire':
                                raise PermissionError(SECRET)
                            yield
                            raise OSError(SECRET)

                    with mock.patch.object(helper, 'locked', broken_lock):
                        code, doc, err = self.h.run(action)
                    self.assertEqual(code, 1, err)
                    self.assertEqual(doc['error']['code'], 'filesystem_error')
                    self.assertTrue(doc['error']['mutated'])
                    self.assertEqual(doc['steps'][-1]['step'],
                                     'lock' if phase == 'acquire' else 'release_lock')
                    self.assertEqual(doc['target'], str(self.config))
                    self.assertNotIn(SECRET, json.dumps(doc))
                    if phase == 'acquire':
                        self.assertEqual(self.mutations(), [])
                    if action == 'start':
                        self.assertEqual(doc['activation'], 'none' if phase == 'acquire' else 'possible')

    def test_preflight_filesystem_and_dry_run_errors_remain_mutation_free(self):
        for action in ('start', 'stop'):
            for dry_run in (False, True):
                with self.subTest(action=action, dry_run=dry_run):
                    self.h.clear_calls()
                    before = snapshot(self.h.home)
                    with mock.patch.object(helper, 'require_unit_ownership',
                                           side_effect=PermissionError(SECRET)):
                        code, doc, err = self.h.run(action, dry_run=dry_run)
                    self.assertEqual(code, 1, err)
                    self.assertFalse(doc['error']['mutated'])
                    self.assertEqual(doc['error']['code'], 'filesystem_error')
                    self.assertNotIn(SECRET, json.dumps(doc))
                    self.assertEqual(snapshot(self.h.home), before)
                    self.assertEqual(self.mutations(), [])

    def test_observation_exceptions_and_unreadable_recovery_keep_primary_error(self):
        original = helper.scheduler_snapshot
        for action in ('start', 'stop'):
            for kind in ('control', 'subprocess'):
                with self.subTest(action=action, kind=kind):
                    marker = self.h.root / 'mutated'
                    marker.unlink(missing_ok=True)
                    self.h.rules({'tool': 'orbi', 'argv_contains': ['install-units'],
                                  'write': {str(marker): 'installed'}},
                                 {'tool': 'systemctl', 'argv_contains': ['disable'],
                                  'write': {str(marker): 'disabled'}}, *self.h.scheduler_rules())
                    reads = []

                    def broken_snapshot(ctx, target):
                        if not marker.exists():
                            return original(ctx, target)
                        reads.append('read')
                        if len(reads) > 1:
                            raise UnicodeError(SECRET)
                        if kind == 'control':
                            raise helper.ControlError('command_timeout', 'original read timed out',
                                                      fix='repair original read', exit_code=3)
                        raise subprocess.CalledProcessError(7, ['fake'], output=SECRET, stderr=SECRET)

                    with mock.patch.object(helper, 'scheduler_snapshot', broken_snapshot), \
                            mock.patch.object(helper, 'pending_services', broken_snapshot):
                        code, doc, err = self.h.run(action)
                    self.assertEqual(code, 3 if kind == 'control' else 1, err)
                    self.assertEqual(doc['error']['code'],
                                     'command_timeout' if kind == 'control' else 'command_failed')
                    self.assertTrue(doc['error']['mutated'])
                    self.assertEqual(doc['steps'][-1]['mutation'], 'none')
                    self.assertEqual(doc['scheduler']['state'], 'unavailable')
                    self.assertEqual(len(reads), 2)
                    self.assertNotIn(SECRET, json.dumps(doc))
                    if kind == 'control':
                        self.assertIn('repair original read', doc['error']['fix'])
                    if action == 'stop':
                        self.assertEqual(len(doc['disabled_timers']), helper.MAX_INSTANCES)
                    else:
                        self.assertEqual(doc['activation'], 'possible')
                        self.assertIn({'step': 'install_units', 'status': 'ok'}, doc['steps'])

    def test_real_cli_start_stop_success_then_partial_failure(self):
        for action, operation, state, step, completed_key in (
                ('start', 'enable', 'started', 'activate_timer', 'activated_timers'),
                ('stop', 'disable', 'stopped', 'disable_timer', 'disabled_timers')):
            with self.subTest(action=action):
                self.h.rules(*self.h.scheduler_rules())
                argv = [sys.executable, '-B', str(HELPER), action,
                        '--repo-dir', str(self.h.repo), '--json']
                success = subprocess.run(argv, env=self.h.env, capture_output=True,
                                         text=True, timeout=30)
                self.assertEqual(success.returncode, 0, success.stderr)
                self.assertEqual(json.loads(success.stdout)['status'], state)
                timer = f'{self.prefix}@2.timer'
                self.h.rules({'tool': 'systemctl',
                              'argv_contains': ['--user', operation, '--now', timer],
                              'exit': 7, 'stderr': SECRET}, *self.h.scheduler_rules())
                self.h.clear_calls()
                failed = subprocess.run(argv, env=self.h.env, capture_output=True,
                                        text=True, timeout=30)
                self.assertEqual(failed.returncode, 1, failed.stderr)
                doc = json.loads(failed.stdout)
                self.assert_receipt(doc, 'command_failed', step, timer,
                                    (completed_key, [f'{self.prefix}@1.timer']))
                self.assertEqual(self.mutations(),
                                 [['--user', operation, '--now', f'{self.prefix}@{i}.timer']
                                  for i in (1, 2)])
                self.assertNotIn(SECRET, failed.stdout + failed.stderr)


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
                                '--pi-providers': ['setup'],
                                '--pi-provider': ['setup'],
                                '--pi-model': ['setup'],
                                '--pi-thinking': ['setup'],
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
