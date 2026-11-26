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
import shlex
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
NEW_PIN = 'b' * 40
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
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('\"', "'"):
            value = value[1:-1]
        values[key.strip().removeprefix('export ').strip()] = value
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
os.environ.setdefault("FAKE_CALLS", {calls!r})
os.environ.setdefault("FAKE_RULES", {rules!r})
name = os.path.basename(sys.argv[0])
argv = sys.argv[1:]
record = {{
    "tool": name,
    "argv": argv,
    "cwd": os.getcwd(),
    "env": {{key: os.environ.get(key) for key in (
        "PYTHONPATH", "UV_TOOL_DIR", "UV_TOOL_BIN_DIR",
        "PYTHONDONTWRITEBYTECODE", "PATH", "HOME", "GIT_OPTIONAL_LOCKS")}},
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


@contextlib.contextmanager
def root_owned(*paths):
    """Report the given files as root-owned without changing them."""
    original = Path.lstat
    chosen = {Path(path) for path in paths}

    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if Path(path) in chosen:
            fields = list(info[:10])
            fields[4] = 0
            return os.stat_result(fields)
        return info

    with mock.patch.object(Path, 'lstat', lstat):
        yield


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
        tool.write_text(FAKE_SOURCE.format(python=sys.executable, calls=str(self.calls_path), rules=str(self.rules_path)))
        tool.chmod(0o755)
        for name in ('pi', 'pi-bolt'):
            (self.bin / name).write_text(tool.read_text())
            (self.bin / name).chmod(0o755)
        for name in ('git', 'uv', 'gh', 'node', 'orbi', 'systemctl', 'launchctl', 'journalctl'):
            (self.bin / name).symlink_to(tool)
        self.bootstrap.symlink_to(tool)

    def base_rules(self):
        deploy = str(self.deploy)
        repo = str(self.repo)
        return [
            {'tool': 'git', 'argv_contains': ['ls-remote', '--tags', OFFICIAL, 'refs/tags/v*'],
             'stdout': f'{self.deploy_head}\trefs/tags/v0.7.41\n'},
            {'tool': 'git', 'argv_contains': ['rev-parse', '--local-env-vars'],
             'stdout': 'GIT_DIR\nGIT_WORK_TREE\n'},
            {'tool': 'git', 'argv_contains': [deploy, 'rev-parse', '--show-toplevel'],
             'stdout': deploy + '\n'},
            {'tool': 'git', 'argv_contains': [deploy, 'rev-parse', '--git-common-dir'],
             'stdout': deploy + '/.git\n'},
            {'tool': 'git', 'argv_contains': [deploy, 'config', 'remote.origin.url'],
             'stdout': OFFICIAL + '.git\n'},
            {'tool': 'git', 'argv_contains': [deploy, 'rev-parse', 'HEAD'],
             'stdout': self.deploy_head + '\n'},
            {'tool': 'git', 'argv_contains': ['clone'], 'mkdir': [deploy + '/.git']},
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
            {'tool': 'gh', 'argv_contains': ['api', 'graphql'],
             'stdout': json.dumps({'data': {'repository': {'issues': {
                 'nodes': [], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}}})},
            {'tool': 'gh', 'argv_contains': ['pr', 'list'], 'stdout': '[]\n'},
            {'tool': 'node', 'argv_contains': [], 'stdout': 'v24.19.0\n'},
            {'tool': 'pi', 'argv_contains': ['auth', 'check'], 'stdout': 'ready\n'},
            {'tool': 'pi', 'argv_contains': [], 'stdout': 'pi 1.0.0\n'},
            {'tool': 'pi-bolt', 'argv_contains': ['auth', 'check'], 'stdout': 'ready\n'},
            {'tool': 'pi-bolt', 'argv_contains': [], 'stdout': 'pi-bolt fixture\n'},
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

    def loaded_unit_rule(self, unit, *, service_config=None, **overrides):
        fragment = self.unit_dir / (unit.split('@')[0] + '@.' + unit.rsplit('.', 1)[1])
        props = dict(Id=unit, LoadState='loaded', FragmentPath=str(fragment), NeedDaemonReload='no',
                     DropInPaths='', ConsistsOf='', BoundBy='', RequiredBy='', RequisiteOf='',
                     PropagatesStopTo='', OnFailure='', OnSuccess='')
        if unit.endswith('.timer'):
            props['Triggers'] = unit.removesuffix('.timer') + '.service'
        else:
            bootstrap = self.home / '.local/bin/orbi'
            props.update(WorkingDirectory=str(self.deploy),
                         Environment=shlex.quote('ORBI_CONFIG=' + str(service_config or self.deploy / 'orbi.toml')),
                         EnvironmentFiles=f'{self.deploy}/.orbi/env (ignore_errors=yes)',
                         UnsetEnvironment='', KillMode='control-group',
                         ExecStart=f'{{ path={bootstrap} ; argv[]={bootstrap} ; ignore_errors=no ; }}')
        props.update(overrides)
        return {'tool': 'systemctl', 'argv_contains': ['show', '--all', '-pId', unit],
                'stdout': ''.join(f'{k}={v}\n' for k, v in props.items())}

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
        for index in sorted(set(range(1, helper.MAX_INSTANCES + 1)) | set(services) | set(timers) | set(enabled)):
            if installed:
                rules.extend(self.loaded_unit_rule(f'{prefix}@{index}.{kind}', service_config=service_config)
                             for kind in ('timer', 'service'))
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

    def enable_timer_rules(self, *timers):
        rules = []
        for timer in timers:
            enabled = str(self.root / (timer + '.enabled'))
            rules.extend([
                {'tool': 'systemctl', 'argv_contains': ['enable', '--now', timer],
                 'write': {enabled: '1'}},
                {'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState', timer],
                 'if_exists': enabled, 'stdout': 'active\n'},
                {'tool': 'systemctl', 'argv_contains': ['is-enabled', timer],
                 'if_exists': enabled, 'stdout': 'enabled\n'},
            ])
        return rules

    def stop_service_rules(self, service):
        stopped = str(self.root / (service + '.stopped'))
        return [{'tool': 'systemctl', 'argv_contains': ['stop', service],
                 'write': {stopped: '1'}},
                {'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState', service],
                 'if_exists': stopped, 'stdout': 'inactive\n'}]

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


# Verbatim source from orbi-build/orbi at
# ce97e015ca433a9312e5bdf69353be58ab394fd9: src/orbi/config.py and pi_session.py.
PINNED_ENV_LOADER = r'''def _load_deploy_env_file(deploy_home: Path) -> None:
    """Merge `<deploy_home>/.orbi/env` into the process environment.

    The documented env-file-first flow (getting-started step 4) writes the
    provider key to this gitignored file, and the installed unit loads it
    via `EnvironmentFile` at service start — the CLI process does not, so
    `orbi setup` and friends must read it themselves or the documented
    step 4 -> 5 flow fails verbatim. Plain systemd EnvironmentFile syntax:
    `KEY=VALUE` lines, optional `export ` prefix, matching single/double
    quotes stripped, blank lines and `#` comments skipped. A variable
    already exported in the shell wins (`setdefault`): the shell export is
    the documented override for manual ticks. A missing file is a no-op
    (a keyless local server needs no env file at all); a line without `=`
    is a misconfiguration and fails fast.
    """
    env_file = deploy_home / ".orbi" / "env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):]
        if "=" not in stripped:
            raise ValueError(
                f"malformed line in env file {env_file}: {stripped!r} "
                "(expected KEY=VALUE)"
            )
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ('"', "'")
        ):
            value = value[1:-1]
        os.environ.setdefault(name, value)
'''
PINNED_EXTENSION_ENV = r'''def pi_extension_env(config) -> dict[str, str]:
    """Return extension variables for the Pi child only; never log them."""
    values: dict[str, str] = {}
    for extension in config.pi_extensions:
        if extension["enabled"]:
            values.update(extension["env"])
    return values
'''

class HarnessSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(Path(self.tmp.name))
        self.h.add_deployment_a()
        # Real, distinct executables: resolving a normal installed symlink is supported.
        self.bolt = self.h.bin / 'bolt target'
        self.bolt.write_text('#!' + sys.executable + '\n'
            'import json, os, signal, sys\n'
            'with open(' + repr(str(self.h.root / 'bolt-calls.jsonl')) + ', "a") as f: '
            'f.write(json.dumps({"argv":sys.argv[1:], "PATH":os.environ.get("PATH"), '
            '"HOME":os.environ.get("HOME"), "agent":os.environ.get("PI_CODING_AGENT_DIR")}) + "\\n")\n'
            'if sys.argv[1:] == ["--version"]: print("bolt fixture"); sys.exit(0)\n'
            'if sys.argv[1:3] == ["auth", "check"]: sys.exit(0)\n'
            'if sys.argv[1:] == ["signal"]: os.kill(os.getpid(), signal.SIGTERM)\n'
            'print(json.dumps({"argv": sys.argv[1:], "pid": os.getpid(), '
            '"inherited": os.environ.get("PROBE")}))\n'
            'sys.exit(23)\n')
        self.bolt.chmod(0o755)
        (self.h.bin / 'pi-bolt').unlink()
        (self.h.bin / 'pi-bolt').symlink_to(self.bolt)

    def test_default_launcher_real_worker_reviewer_exec_and_receipts(self):
        self.h.rules({'tool': 'orbi', 'argv_contains': ['check'], 'exec': ['pi', '--version']})
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, (doc, err))
        evidence = doc['deployment']['harness']
        self.assertEqual(evidence['requested_kind'], 'pi-bolt')
        self.assertEqual(evidence['selection_source'], 'default')
        self.assertEqual(evidence['state'], 'verified')
        self.assertEqual(evidence['executable'], str(self.bolt))
        traces = [json.loads(line) for line in (self.h.root / 'bolt-calls.jsonl').read_text().splitlines()]
        self.assertIn(['auth', 'check', '--provider', 'openrouter', '--no-refresh'], [t['argv'] for t in traces])
        self.assertGreaterEqual(sum(t['argv'] == ['--version'] for t in traces), 2)
        for trace in traces:
            self.assertEqual(trace['PATH'].split(':')[0], str(self.h.deploy / '.orbi/harness-bin'))
            self.assertEqual(trace['HOME'], str(self.h.home))
        target = helper.deployment_from(self.h.deploy / 'orbi.toml')
        hostile_bin = self.h.root / 'hostile'
        hostile_bin.mkdir()
        (hostile_bin / 'pi').write_text('#!/bin/sh\nexit 77\n')
        (hostile_bin / 'pi').chmod(0o755)
        hostile = dict(self.h.env, PATH=str(hostile_bin) + ':' + self.h.env['PATH'], PROBE='inherited')
        env = helper.scoped_env(helper.Context(env=hostile), target)
        self.assertEqual(__import__('shutil').which('pi', path=env['PATH']),
                         evidence['launcher'])
        for role in ('implement', 'review'):
            argv = ['--print', '--session-dir', role + ' space', '', 'a"b', '$literal']
            proc = subprocess.Popen(['pi', *argv], env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            out, _ = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 23)
            observed = json.loads(out)
            self.assertEqual(observed['argv'], argv)
            self.assertEqual(observed['pid'], proc.pid)  # exec, not a wrapper child
            self.assertEqual(observed['inherited'], 'inherited')
        proc = subprocess.run(['pi', 'signal'], env=env, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, -15)
        for action in ('status', 'start'):
            code, receipt, err = self.h.run(action, dry_run=action == 'start', env=hostile)
            self.assertEqual(code, 0, (receipt, err))
            self.assertEqual(receipt['deployment']['harness']['executable'], str(self.bolt))

    def test_missing_default_never_falls_back_or_writes(self):
        (self.h.bin / 'pi-bolt').unlink()
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('setup')
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'prerequisite_missing')
        self.assertIn('pi-bolt', json.dumps(doc))
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        proc = subprocess.run([sys.executable, '-B', str(HELPER), 'setup',
            '--repo-dir', str(self.h.repo), '--json'], env=self.h.env,
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        failure = json.loads(proc.stdout)
        self.assertEqual(failure['error']['code'], 'prerequisite_missing')
        self.assertIn('pi-bolt', failure['error']['message'])
        self.assertFalse(failure['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)

    def test_selection_reuse_conflict_and_drift(self):
        self.assertEqual(self.h.run('setup', options=['--harness', 'pi'])[0], 0)
        self.assertEqual(self.h.run('setup')[1]['deployment']['harness']['requested_kind'], 'pi')
        before = snapshot(self.h.home)
        code, doc, _ = self.h.run('setup', options=['--harness', 'pi-bolt'])
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'harness_conflict')
        self.assertEqual(snapshot(self.h.home), before)
        launcher = self.h.deploy / '.orbi/harness-bin/pi'
        launcher.write_text('#!/bin/sh\nexit 0\n')
        code, doc, _ = self.h.run('status')
        self.assertEqual(code, 0)
        self.assertEqual(doc['deployment']['harness']['state'], 'drift')
        self.assertNotEqual(self.h.run('start', dry_run=True)[0], 0)


    def test_public_cli_stock_pi_and_help_are_explicit_and_nonmutating(self):
        argv = [sys.executable, '-B', str(HELPER), 'setup', '--repo-dir', str(self.h.repo),
                '--harness', 'pi', '--json']
        proc = subprocess.run(argv, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        evidence = json.loads(proc.stdout)['deployment']['harness']
        self.assertEqual(evidence['requested_kind'], 'pi')
        self.assertEqual(evidence['selection_source'], 'explicit')
        before = snapshot(self.h.home)
        for action in ('status', 'start'):
            code, text, err = self.h.run(action, dry_run=action == 'start', json_mode=False)
            self.assertEqual(code, 0, (text, err))
            self.assertIn('deployment.harness.requested_kind=pi', text)
            self.assertIn('deployment.harness.state=verified', text)
        code, doc, _ = self.h.run('help', options=['--harness', 'pi-bolt'])
        self.assertEqual(code, 0, doc)
        self.assertIn('new default', doc['options']['--harness']['effect'])
        self.assertEqual(snapshot(self.h.home), before)
        for action in ('status', 'start', 'stop'):
            code, doc, _ = self.h.run(action, options=['--harness', 'pi'])
            self.assertNotEqual(code, 0)
            self.assertEqual(doc['error']['code'], 'bootstrap_override_refused' if action == 'start'
                             else 'invalid_harness_selection')

    def test_config_last_retry_reuses_partial_explicit_selection(self):
        code, failure, _ = self.h.run('setup', options=['--harness', 'pi'],
                                    failure=('write_config', 'before', OSError(SECRET)))
        self.assertNotEqual(code, 0)
        self.assertTrue(failure['error']['mutated'])
        self.assertFalse((self.h.deploy / 'orbi.toml').exists())
        saved = (self.h.deploy / '.orbi/env').read_bytes()
        hostile = self.h.root / 'alternate'
        hostile.mkdir()
        for name in ('pi', 'pi-bolt'):
            (hostile / name).write_text('#!/bin/sh\nexit 77\n')
            (hostile / name).chmod(0o755)
        code, doc, _ = self.h.run('setup', env=dict(self.h.env,
            PATH=str(hostile) + ':' + self.h.env['PATH']))
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc['deployment']['harness']['requested_kind'], 'pi')
        self.assertEqual(doc['deployment']['harness']['selection_source'], 'explicit')
        self.assertEqual(doc['deployment']['harness']['executable'], str(self.h.bin / 'pi'))
        self.assertEqual((self.h.deploy / '.orbi/env').read_bytes(), saved)

    def test_unpublished_routing_drift_refuses_before_retry_writes(self):
        code, failure, _ = self.h.run('setup',
                                    failure=('write_config', 'before', OSError(SECRET)))
        self.assertNotEqual(code, 0, failure)
        env_path = self.h.deploy / '.orbi/env'
        original = env_path.read_bytes()
        env_path.write_bytes(re.sub(rb'^PATH=.*$', b"PATH='/usr/bin:/bin'",
                                    original, flags=re.MULTILINE))
        before = snapshot(self.h.home)
        code, doc, _ = self.h.run('setup')
        self.assertNotEqual(code, 0, doc)
        self.assertEqual(doc['error']['code'], 'harness_drift')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertFalse((self.h.deploy / 'orbi.toml').exists())

    def test_malformed_existing_credential_metadata_is_bounded_and_redacted(self):
        self.assertEqual(self.h.run('setup')[0], 0)
        catalog = self.h.deploy / '.orbi/pi-providers.json'
        original = json.loads(catalog.read_text())
        for key, value in (('headers', [SECRET]), ('modelOverrides', [SECRET]),
                           ('modelOverrides', {'model': SECRET})):
            with self.subTest(key=key, value=value):
                data = json.loads(json.dumps(original))
                data['providers']['openrouter'][key] = value
                catalog.write_text(json.dumps(data))
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('start', dry_run=True)
                self.assertNotEqual(code, 0, doc)
                self.assertEqual(doc['error']['code'], 'auth_unverified')
                self.assertNotIn(SECRET, json.dumps(doc) + err)
                self.assertEqual(snapshot(self.h.home), before)

    def test_final_child_extension_environment_contract(self):
        self.assertEqual(self.h.run('setup')[0], 0)
        config = self.h.deploy / 'orbi.toml'
        original = config.read_bytes()
        target = helper.deployment_from(config)
        env = helper.scoped_env(helper.Context(env=self.h.env), target)
        ns = {}
        exec(PINNED_EXTENSION_ENV, ns)
        from types import SimpleNamespace
        for key, value in (('PATH', '/hostile'), ('HOME', '/other'),
                           ('PI_CODING_AGENT_DIR', str(self.h.home / '.pi/agent')),
                           ('PATH', env['PATH']), ('HOME', env['HOME'])):
            with self.subTest(key=key, value=value):
                extension = {'source': 'npm:fixture@1.0.0', 'enabled': True, 'env': {key: value}}
                pi_env = ns['pi_extension_env'](SimpleNamespace(pi_extensions=[extension]))
                pi_env['PI_CODING_AGENT_DIR'] = '/worktree/.orbi/pi-agent'
                # Exact final merge from pinned src/orbi/pi_process.py, spawn_pi.
                native_child = {k: v for k, v in {**env, **pi_env}.items()
                                if k != 'ORBI_TELEGRAM_BOT_TOKEN'}
                self.assertEqual(native_child['PI_CODING_AGENT_DIR'], '/worktree/.orbi/pi-agent')
                config.write_bytes(original + ('\n[[pi_extensions]]\nsource = "npm:fixture@1.0.0"\n'
                    '[pi_extensions.env]\n' + key + ' = ' + json.dumps(value) + '\n').encode())
                before = snapshot(self.h.home)
                self.h.clear_calls()
                code, doc, _ = self.h.run('start', dry_run=True)
                compatible = key != 'PI_CODING_AGENT_DIR' and native_child[key] == env[key]
                self.assertEqual(code == 0, compatible, doc)
                if not compatible:
                    self.assertEqual(doc['error']['code'], 'extension_env_mismatch')
                    self.assertIn(key, doc['error']['message'])
                self.assertEqual(snapshot(self.h.home), before)
                SetupBoundaryTests.assert_no_activation(self, self.h.calls())
        config.write_bytes(original + b'\n[[pi_extensions]]\nsource = "npm:fixture@1.0.0"\nenabled = false\n[pi_extensions.env]\nPATH = "/hostile"\n')
        self.assertEqual(self.h.run('start', dry_run=True)[0], 0)
        for location in ('ambient', 'ambient-home', 'persisted'):
            config.write_bytes(original)
            env_path = self.h.deploy / '.orbi/env'
            prior = env_path.read_bytes()
            overrides = dict(self.h.env)
            if location == 'ambient':
                overrides['PI_CODING_AGENT_DIR'] = '/foreign/profile'
            elif location == 'ambient-home':
                overrides['HOME'] = '/foreign/home'
            else:
                env_path.write_bytes(re.sub(rb'^HOME=.*$', b"HOME='/foreign/home'", prior, flags=re.MULTILINE))
            code, doc, _ = self.h.run('start', dry_run=True, env=overrides)
            self.assertNotEqual(code, 0)
            self.assertEqual(doc['error']['code'], 'auth_home_mismatch')
            env_path.write_bytes(prior)

    def test_legacy_unmigrated_and_absent_unknown_evidence(self):
        code, doc, _ = self.h.run('status')
        self.assertEqual(code, 0)
        self.assertIsNone(doc['deployment']['harness']['requested_kind'])
        self.assertIn('unconfigured', doc['deployment']['harness']['reason'])
        self.assertEqual(self.h.run('setup')[0], 0)
        env_path = self.h.deploy / '.orbi/env'
        env_path.write_text(''.join(line for line in env_path.read_text().splitlines(keepends=True)
                                   if not line.startswith('KIT_ORBI_')))
        (self.h.deploy / '.orbi/harness-bin/pi').unlink()
        stored_path = env_dict(env_path.read_text())['PATH']
        for action in ('setup', 'status', 'start'):
            code, doc, _ = self.h.run(action, dry_run=action == 'start')
            self.assertEqual(code, 0, doc)
            evidence = doc['deployment']['harness']
            self.assertEqual(evidence['management'], 'legacy')
            self.assertIsNone(evidence['requested_kind'])
            self.assertEqual(evidence['executable'], str(self.h.bin / 'pi'))
            self.assertEqual(env_dict(env_path.read_text())['PATH'], stored_path)
        before = snapshot(self.h.home)
        code, doc, _ = self.h.run('setup', options=['--harness', 'pi'])
        self.assertNotEqual(code, 0)
        self.assertEqual(doc['error']['code'], 'harness_migration_required')
        self.assertEqual(snapshot(self.h.home), before)
        env_path.write_text(''.join(line for line in env_path.read_text().splitlines(keepends=True)
                                   if not line.startswith('PATH=')))
        code, doc, _ = self.h.run('status')
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc['deployment']['harness']['state'], 'unknown')
        self.assertIn('service resolution unverified', doc['deployment']['harness']['resolution'])
        # Relative/empty PATH components resolve against a process cwd, not
        # necessarily the service WorkingDirectory; do not claim service evidence.
        for path in ('.:/usr/bin', ':/usr/bin'):
            env_path.write_text('PATH=' + path + '\n')
            before = snapshot(self.h.home)
            code, doc, _ = self.h.run('status')
            self.assertEqual(code, 0, doc)
            evidence = doc['deployment']['harness']
            self.assertEqual(evidence['state'], 'unknown')
            self.assertIsNone(evidence['executable'])
            self.assertIn('service resolution unverified', evidence['resolution'])
            self.assertEqual(snapshot(self.h.home), before)

    def test_managed_drift_and_unavailable_preserve_evidence(self):
        self.assertEqual(self.h.run('setup')[0], 0)
        env_path = self.h.deploy / '.orbi/env'
        launcher = self.h.deploy / '.orbi/harness-bin/pi'
        env_before, launcher_before = env_path.read_bytes(), launcher.read_bytes()
        for case in ('partial', 'invalid', 'duplicate', 'path', 'missing-launcher', 'symlink', 'nonexec', 'missing-target'):
            with self.subTest(case=case):
                if case == 'partial':
                    env_path.write_bytes(b'\n'.join(line for line in env_before.split(b'\n')
                                                   if not line.startswith(b'KIT_ORBI_HARNESS_SOURCE=')))
                elif case == 'invalid':
                    env_path.write_bytes(env_before.replace(b"KIT_ORBI_HARNESS='pi-bolt'", b"KIT_ORBI_HARNESS='invalid'"))
                elif case == 'duplicate':
                    env_path.write_bytes(env_before + b"KIT_ORBI_HARNESS='pi-bolt'\n")
                elif case == 'path':
                    env_path.write_bytes(re.sub(rb"^PATH=.*$", b"PATH='/usr/bin:/bin'", env_before, flags=re.MULTILINE))
                elif case == 'missing-launcher':
                    launcher.unlink()
                elif case == 'symlink':
                    launcher.unlink()
                    launcher.symlink_to(self.bolt)
                elif case == 'nonexec':
                    launcher.chmod(0o600)
                else:
                    self.bolt.rename(self.bolt.with_suffix('.saved'))
                before = snapshot(self.h.home)
                code, doc, _ = self.h.run('status')
                self.assertEqual(code, 0, doc)
                self.assertIn(doc['deployment']['harness']['state'], ('drift', 'unavailable'))
                for action in ('setup', 'start'):
                    code, failure, _ = self.h.run(action, dry_run=True)
                    self.assertNotEqual(code, 0, failure)
                    self.assertFalse(failure['error']['mutated'])
                    self.assertIn('harness', failure['deployment'])
                self.assertEqual(snapshot(self.h.home), before)
                env_path.write_bytes(env_before)
                if launcher.is_symlink():
                    launcher.unlink()
                launcher.write_bytes(launcher_before)
                launcher.chmod(0o755)
                if not self.bolt.exists():
                    self.bolt.with_suffix('.saved').rename(self.bolt)

    def test_env_literals_native_loader_and_unrelated_bytes(self):
        spaced = Harness(Path(self.tmp.name) / 'interior space')
        spaced.add_deployment_a()
        (spaced.deploy / '.orbi').mkdir(parents=True)
        env_path = spaced.deploy / '.orbi/env'
        unrelated = b'# original\r\nCREDENTIAL="literal \\ value"\r\nOTHER=  keep spacing  \nLAST=no-final-newline'
        env_path.write_bytes(unrelated)
        env_path.chmod(0o640)
        code, doc, _ = spaced.run('setup')
        self.assertEqual(code, 0, doc)
        self.assertTrue(env_path.read_bytes().endswith(unrelated))
        self.assertEqual(env_path.stat().st_mode & 0o777, 0o640)
        target = helper.deployment_from(spaced.deploy / 'orbi.toml')
        ns = {'Path': Path, 'os': os}
        exec(PINNED_ENV_LOADER, ns)
        with mock.patch.dict(os.environ, {}, clear=True):
            ns['_load_deploy_env_file'](spaced.deploy)
            self.assertEqual(dict(os.environ), helper.persisted_env(target))
        for value in ("/bad'quote", '/bad"quote', '/bad\\slash', '/bad\nline',
                      '/bad\x00nul', '/bad\tcontrol', '/bad\x7fdel', '/bad\x85nel',
                      '/bad\u2028line', '/bad\u2029paragraph', ' /edge', '/edge ',
                      '/bad:colon', 'relative'):
            with self.subTest(value=repr(value)):
                with self.assertRaises(helper.ControlError):
                    helper.env_literal(value, path=True)
        for suffix in ('quoted"', "quoted'", 'back\\slash', 'control\n',
                       'unicode\x85control', 'colon:part'):
            with self.subTest(suffix=repr(suffix)):
                h = Harness(Path(self.tmp.name) / ('invalid-' + suffix))
                h.add_deployment_a()
                before = snapshot(h.home)
                code, failure, _ = h.run('setup')
                self.assertNotEqual(code, 0, failure)
                self.assertFalse(failure['error']['mutated'])
                self.assertEqual(snapshot(h.home), before)

    def test_custom_provider_auth_references_reviewer_and_redaction(self):
        self.assertEqual(self.h.run('setup')[0], 0)
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text() + '\nreview_pi_provider = "custom-review"\nreview_pi_model = "review-model"\n')
        catalog = self.h.deploy / '.orbi/pi-providers.json'
        data = json.loads(catalog.read_text())
        data['providers']['openrouter']['apiKey'] = '$IMPLEMENT_KEY'
        data['providers']['custom-review'] = {
            'baseUrl': 'https://custom.invalid/v1', 'api': 'openai-completions',
            'apiKey': '${REVIEW_KEY}', 'headers': {'X-Custom': '$HEADER_KEY'},
            'models': [{'id': 'review-model', 'contextWindow': 100, 'maxTokens': 50}]}
        catalog.write_text(json.dumps(data))
        # The global catalog does not contain either custom deployment selection.
        user_models = self.h.home / '.pi/agent/models.json'
        user_models.parent.mkdir(parents=True)
        user_models.write_text('{"providers":{}}')
        original_catalog = user_models.read_bytes()
        self.h.rules({'tool': 'pi-bolt', 'argv_contains': ['auth', 'check'], 'exit': 2})
        env_path = self.h.deploy / '.orbi/env'
        prior = env_path.read_bytes()
        keys = ('IMPLEMENT_KEY', 'REVIEW_KEY', 'HEADER_KEY')
        ambient = dict(self.h.env, **{key: SECRET for key in keys})
        # Even shell-only values cannot qualify service readiness.
        code, failure, _ = self.h.run('start', dry_run=True, env=ambient)
        self.assertNotEqual(code, 0)
        self.assertEqual(failure['error']['code'], 'credential_reference_missing')
        self.assertIn('IMPLEMENT_KEY', failure['error']['message'])
        env_path.write_bytes(prior + b'IMPLEMENT_KEY=' + SECRET.encode() + b'\n')
        code, failure, _ = self.h.run('start', dry_run=True, env=ambient)
        self.assertNotEqual(code, 0)
        self.assertIn('HEADER_KEY', failure['error']['message'])
        credentials = b''.join(key.encode() + b'=' + SECRET.encode() + b'\r\n' for key in keys)
        env_path.write_bytes(prior + credentials)
        before = snapshot(self.h.home)
        self.h.clear_calls()
        (self.h.root / 'bolt-calls.jsonl').unlink()
        code, doc, err = self.h.run('setup')
        self.assertEqual(code, 0, doc)
        traces = [json.loads(line) for line in (self.h.root / 'bolt-calls.jsonl').read_text().splitlines()]
        self.assertFalse(any(t['argv'][:2] == ['auth', 'check'] for t in traces))
        self.assertEqual([item['state'] for item in doc['prerequisites']['auth']],
                         ['references_available', 'references_available'])
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        self.assertEqual(snapshot(self.h.home), before)
        self.assertEqual(user_models.read_bytes(), original_catalog)
        self.assertFalse(any(c['argv'][:2] == ['auth', 'check'] for c in self.h.calls()))
        config.write_text(config.read_text() + '\n[[pi_extensions]]\nsource = "npm:fixture@1.0.0"\n[pi_extensions.env]\nREVIEW_KEY = ""\n')
        self.assertEqual(self.h.run('start', dry_run=True)[1]['error']['code'], 'credential_reference_missing')
        # Without declared references a failed selected-harness stored-auth check
        # must remain auth_unverified, not a config/schema authentication pass.
        data['providers']['openrouter'].pop('apiKey')
        catalog.write_text(json.dumps(data))
        # Custom target in this class is an independent executable; make its
        # supported auth check fail rather than relying on fake tool-name rules.
        self.bolt.write_text('#!/bin/sh\nexit 2\n')
        code, failure, _ = self.h.run('start', dry_run=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(failure['error']['code'], 'auth_unverified')
        self.assertIn('openrouter', failure['error']['message'])


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
                                and ('ActiveState' in call['argv'] or 'FragmentPath' in call['argv']
                                     or call['argv'][3:] == ['-p', 'LastTriggerUSec',
                                                            '-p', 'NextElapseUSecRealtime'])
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
                                and ('ActiveState' in call['argv'] or 'FragmentPath' in call['argv']
                                     or call['argv'][3:] == ['-p', 'LastTriggerUSec',
                                                            '-p', 'NextElapseUSecRealtime'])
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
                        '--pi-model', 'gpt-6.1-sol', '--pi-thinking', 'high', '--allow-metered']

    def test_explicit_metered_bootstrap_requires_confirmation(self):
        options = self.options[:6]
        before = snapshot(self.h.home)
        for action in ('setup', 'start'):
            with self.subTest(action=action):
                code, doc, err = self.h.run(action, options=options)
                self.assertEqual(code, 2, (doc, err))
                self.assertEqual(doc['error']['code'], 'metered_confirmation_required')
                self.assertIn('openai/gpt-6.1-sol', doc['error']['message'])
                self.assertIn('--allow-metered', doc['error']['fix'])
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                code, doc, err = self.h.run(action, options=[*options, '--allow-metered'], dry_run=True)
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(doc['status'], 'planned')
                self.assertEqual(snapshot(self.h.home), before)

    def test_documented_public_setup_routes_have_the_delegated_fake_host_effects(self):
        # Execute the helper argv named by the public instruction table. This proves
        # the real delegated CLI boundary, not a host model's interpretation of it.
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        routes = dict(re.findall(r'\| `(setup[^`]*?)` \| `([^`]+)` \|', skill))
        for index, public in enumerate(('setup', 'setup --dry-run',
                                        'setup --prepare-only',
                                        'setup --prepare-only --dry-run')):
            with self.subTest(public=public):
                h = Harness(Path(self.tmp.name) / str(index))
                argv = shlex.split(routes[public])
                before = snapshot(h.home)
                result = subprocess.run(
                    [sys.executable, '-B', str(HELPER), *argv, '--repo-dir', str(h.repo),
                     '--json', *self.options, '--harness', 'pi'], env=h.env,
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                doc = json.loads(result.stdout)
                preview = '--dry-run' in argv
                prepare_only = '--prepare-only' in public
                self.assertEqual(doc['action'], 'setup' if prepare_only else 'start')
                self.assertEqual(doc['status'], 'planned' if preview else
                                 ('prepared' if prepare_only else 'started'))
                if preview:
                    self.assertEqual(snapshot(h.home), before)
                else:
                    self.assertEqual(doc['deployment']['harness']['requested_kind'], 'pi')
                    config = h.config()
                    self.assertEqual((config['pi_provider'], config['pi_model']),
                                     ('openai', 'gpt-6.1-sol'))
                if prepare_only or preview:
                    SetupBoundaryTests.assert_no_activation(self, h.calls())
                else:
                    self.assertEqual(doc['preparation']['state'], 'prepared')
                    operations = [c['argv'][0] for c in h.calls() if c['tool'] == 'orbi']
                    self.assertEqual(operations.count('check'), 1)
                    self.assertEqual(operations.count('setup'), 1)
                    self.assertEqual(operations.count('install-units'), 1)

    def test_protection_observations_do_not_gate_public_setup_or_existing_start(self):
        # Official REST GET branch exposes `protected`; a protection-only 403
        # leaves details unknown. These are prior read-only owner observations,
        # not a new protection probe in Kit's activation path.
        # https://docs.github.com/en/rest/branches/branches#get-a-branch
        # https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection
        routes = dict(re.findall(r'\| `(setup[^`]*?)` \| `([^`]+)` \|',
                                 (ROOT / 'skills/orbi/SKILL.md').read_text()))
        branch = f'repos/{REPO}/branches/main'
        for state, protected, denied in (('protected', True, False),
                                         ('unprotected', False, False),
                                         ('protection-only-403', False, True)):
            with self.subTest(observation=state):
                h = Harness(Path(self.tmp.name) / state)
                prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                rules = [
                    {'tool': 'gh', 'argv_contains': ['api', branch + '/protection'],
                     'stdout': '' if denied else '{}',
                     'stderr': 'HTTP 403 Forbidden' if denied else '',
                     'exit': 1 if denied else 0},
                    {'tool': 'gh', 'argv_contains': ['api', branch],
                     'stdout': json.dumps({'name': 'main', 'protected': protected})},
                    {'tool': 'orbi', 'argv_contains': ['doctor'], 'exit': 1,
                     'stdout': ('protection details: HTTP 403' if denied else
                                'merge_gate: FAILED classic protection enforces admins'
                                if protected else 'main unprotected')}]
                h.rules(*rules)
                observed = subprocess.run(['gh', 'api', branch], env=h.env,
                                          capture_output=True, text=True, timeout=10)
                self.assertEqual(observed.returncode, 0, observed.stderr)
                self.assertEqual(json.loads(observed.stdout)['protected'], protected)
                if denied:
                    details = subprocess.run(['gh', 'api', branch + '/protection'],
                                             env=h.env, capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(details.returncode, 0)
                    self.assertIn('403', details.stderr)
                for public, argv, options in (('setup', shlex.split(routes['setup']), self.options),
                                               ('start', ['start'], [])):
                    with self.subTest(public=public):
                        if public == 'start':
                            h.rules(*rules, *h.enable_timer_rules(f'{prefix}@1.timer'),
                                    *h.scheduler_rules())
                        h.clear_calls()
                        result = subprocess.run(
                            [sys.executable, '-B', str(HELPER), *argv, '--repo-dir',
                             str(h.repo), '--json', *options], env=h.env,
                            capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                        doc = json.loads(result.stdout)
                        self.assertEqual(doc['status'], 'started')
                        self.assertEqual(doc['preparation']['state'],
                                         'prepared' if public == 'setup' else 'skipped')
                        mutations = [c['argv'] for c in h.calls() if c['tool'] == 'systemctl'
                                     and set(c['argv']) & {'enable', 'start', 'disable',
                                                         'stop', 'kill', 'restart'}]
                        self.assertEqual(mutations, [['--user', 'enable', '--now', f'{prefix}@1.timer'],
                                                     ['--user', 'start', f'{prefix}@1.service']])
                        # Kit neither queries nor changes protection to permit activation.
                        self.assertFalse([c for c in h.calls() if c['tool'] == 'gh'
                                          and 'api' in c['argv']])
                        config = h.config()
                        self.assertEqual(config['engine_source_track'], 'sha:' + PIN)
                        self.assertFalse(config['human_review_gate'])
                    # A failed doctor diagnostic is still visible, not a Kit start refusal.
                    code, status, err = h.run('status')
                    self.assertEqual(code, 0, err)
                    self.assertEqual(status['doctor']['state'], 'failed')

    def test_start_keeps_github_auth_and_repository_validation_refusals(self):
        for name, rule, code, repair in (
                ('auth', {'tool': 'gh', 'argv_contains': ['auth', 'status'], 'exit': 1},
                 'gh_auth_unavailable', 'gh auth login'),
                ('repo-access', {'tool': 'orbi', 'argv_contains': ['check'], 'exit': 1,
                                 'stderr': 'repository access denied (HTTP 403)'},
                 'validation_failed', 'setup --prepare-only')):
            with self.subTest(failure=name):
                h = Harness(Path(self.tmp.name) / name)
                h.rules(rule)
                result = subprocess.run(
                    [sys.executable, '-B', str(HELPER), 'start', '--repo-dir', str(h.repo),
                     '--json', *self.options], env=h.env,
                    capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                doc = json.loads(result.stdout)
                self.assertEqual(doc['error']['code'], code)
                self.assertIn(repair, doc['error']['fix'])
                self.assertEqual(doc['activation'], 'none')
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_public_setup_default_preserves_degraded_timer_failure_receipt(self):
        routes = dict(re.findall(r'\| `(setup[^`]*?)` \| `([^`]+)` \|',
                                 (ROOT / 'skills/orbi/SKILL.md').read_text()))
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        timer, service = f'{prefix}@1.timer', f'{prefix}@1.service'
        marker = self.h.root / 'installed'
        loaded = self.h.scheduler_rules()
        writes = {str(marker): 'installed'}
        for suffix in ('service', 'timer'):
            path = self.h.unit_dir / f'{prefix}@.{suffix}'
            writes[str(path)] = path.read_text()
            path.unlink()
        for rule in loaded:
            rule['if_exists'] = str(marker)
        self.h.rules({'tool': 'orbi', 'argv_contains': ['install-units'],
                      'write': writes},
                     {'tool': 'systemctl', 'argv_contains': ['--user enable --now', timer],
                      'exit': 7}, *loaded)
        # Real CLI process with the exact helper argv from public setup's table.
        result = subprocess.run(
            [sys.executable, '-B', str(HELPER), *shlex.split(routes['setup']),
             '--repo-dir', str(self.h.repo), '--json', *self.options], env=self.h.env,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['preparation']['state'], 'prepared')
        self.assertEqual(doc['original_error'], 'command_failed')
        self.assertEqual(doc['recurring_scheduling'], 'incomplete')
        self.assertEqual(doc['first_tick'], 'requested')
        self.assertEqual(doc['activated_timers'], [])
        self.assertEqual(doc['steps'][-1]['unit'], timer)
        mutations = [c['argv'] for c in self.h.calls() if c['tool'] == 'systemctl'
                     and set(c['argv']) & {'enable', 'start', 'disable', 'stop', 'kill', 'restart'}]
        self.assertEqual(mutations, [['--user', 'enable', '--now', timer],
                                     ['--user', 'start', service]])

    def test_first_start_prepares_validates_and_activates_once(self):
        for kind in (None, 'pi', 'donor'):
            with self.subTest(harness=kind):
                h = self.h if kind is None else Harness(Path(self.tmp.name) / kind)
                if kind == 'donor':
                    h.add_deployment_a()
                    options = []
                else:
                    options = self.options + (['--harness', kind] if kind else [])
                result = subprocess.run(
                    [sys.executable, '-B', str(HELPER), 'start', '--repo-dir', str(h.repo),
                     '--json', *options], env=h.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                doc = json.loads(result.stdout)
                self.assertEqual(doc['action'], 'start')
                self.assertEqual(doc['preparation']['state'], 'prepared')
                self.assertEqual(doc['deployment']['harness']['requested_kind'],
                                 'pi' if kind == 'pi' else 'pi-bolt')
                self.assertEqual(doc['status'], 'started')
                operations = [c['argv'][0] for c in h.calls() if c['tool'] == 'orbi']
                self.assertEqual(operations.count('check'), 1)
                self.assertEqual(operations.count('setup'), 1)
                self.assertEqual(operations.count('install-units'), 1)
                self.assertLess(operations.index('check'), operations.index('setup'))
                self.assertTrue((h.deploy / 'orbi.toml').is_file())
                self.assertEqual(sum(c['tool'] == 'git' and 'clone' in c['argv']
                                     for c in h.calls()), 1)
                if kind == 'donor':
                    self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])

    def test_first_start_preparation_failure_never_activates(self):
        self.h.rules({'tool': 'orbi', 'argv_contains': ['check'], 'exit': 1})
        code, doc, err = self.h.run('start', options=self.options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['action'], 'start')
        self.assertEqual(doc['error']['code'], 'validation_failed')
        self.assertIn('orbi check failed with exit 1', doc['error']['message'])
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['preparation']['state'], 'failed')
        self.assertEqual(doc['preparation']['steps'][-1]['step'], 'validate_non_activating')
        self.assertEqual(doc['activation'], 'none')
        self.assertIn('`/orbi setup --prepare-only`', doc['error']['fix'])
        self.assertTrue((self.h.deploy / 'orbi.toml').is_file())
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_absent_start_cli_preview_is_write_free_and_defers_activation_checks(self):
        before = snapshot(self.h.home)
        result = subprocess.run(
            [sys.executable, '-B', str(HELPER), 'start', '--repo-dir', str(self.h.repo),
             '--json', '--dry-run', *self.options], env=self.h.env,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['preparation']['state'], 'planned')
        self.assertEqual(doc['deployment']['source'], 'unverified')
        self.assertEqual(doc['deployment']['harness']['state'], 'unknown')
        self.assertEqual(doc['activation'], 'planned')
        self.assertFalse(doc['activated'])
        self.assertIn({'step': 'validate_non_activating', 'status': 'planned'}, doc['steps'])
        self.assertEqual(doc['steps'][-2]['status'], 'deferred')
        text = subprocess.run(
            [sys.executable, '-B', str(HELPER), 'start', '--repo-dir', str(self.h.repo),
             '--dry-run', *self.options], env=self.h.env,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(text.returncode, 0, text.stderr)
        for line in ('preparation.state=planned', 'activation=planned', 'activated=False'):
            self.assertIn(line + '\n', text.stdout)
        self.assertEqual(snapshot(self.h.home), before)
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())
        self.assertFalse(any(c['tool'] == 'git' and set(c['argv']) & {'clone', 'fetch'}
                             for c in self.h.calls()))
        self.assertFalse(any(c['tool'] == 'orbi' and c['argv'][0] == 'check'
                             for c in self.h.calls()))

    def test_start_preparation_prerequisite_failures_are_honest_and_write_free(self):
        before = snapshot(self.h.home)
        for dry_run in (True, False):
            code, doc, err = self.h.run('start', dry_run=dry_run)
            self.assertNotEqual(code, 0, (doc, err))
            self.assertEqual(doc['error']['code'], 'provider_unavailable')
            self.assertFalse(doc['error']['mutated'])
            self.assertEqual(doc['preparation']['state'], 'failed')
            self.assertIn('--pi-providers', doc['error']['fix'])
            self.assertEqual(snapshot(self.h.home), before)
        (self.h.bin / 'pi-bolt').unlink()
        code, doc, err = self.h.run('start', options=self.options, dry_run=True)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'prerequisite_missing')
        self.assertIn('pi-bolt', doc['error']['message'])
        self.assertFalse(doc['error']['mutated'])
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_interrupted_preparation_retry_and_activation_timeout_keep_receipts(self):
        code, doc, err = self.h.run('start', options=self.options,
                                    failure=('write_config', 'before', OSError(SECRET)))
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['preparation']['state'], 'failed')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['steps'][-1]['step'], 'write_config')
        self.assertFalse((self.h.deploy / 'orbi.toml').exists())
        saved = (self.h.deploy / '.orbi/env').read_bytes()
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())
        timeout_error = helper.ControlError('command_timeout', 'fixture upstream setup timeout')
        with mock.patch.object(helper, 'run_upstream_step', side_effect=timeout_error) as activation:
            code, doc, err = self.h.run('start', options=self.options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['preparation']['state'], 'prepared')
        self.assertEqual(doc['error']['code'], 'command_timeout')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['activation'], 'possible')
        self.assertEqual(doc['activated_timers'], [])
        self.assertEqual(activation.call_count, 1)
        self.assertEqual((self.h.deploy / '.orbi/env').read_bytes(), saved)
        self.assertNotIn(SECRET, json.dumps(doc))

    def test_post_preparation_failure_retains_success_and_mutation(self):
        with mock.patch.object(helper, 'start_plan', side_effect=helper.ControlError(
                'bootstrap_unverified', 'fixture activation preflight failure')):
            code, doc, err = self.h.run('start', options=self.options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'bootstrap_unverified')
        self.assertEqual(doc['original_error'], 'bootstrap_unverified')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['preparation']['state'], 'prepared')
        self.assertEqual(doc['activation'], 'none')
        self.assertEqual(doc['preparation']['steps'][-1]['step'], 'validate_non_activating')
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_start_holds_drift_during_validation_and_after_rebind(self):
        for phase in ('validation', 'rebind'):
            with self.subTest(phase=phase):
                h = Harness(Path(self.tmp.name) / phase)
                original_check = helper.run_orbi_check
                original_validate = helper.validate_target
                changed = False

                def change(target):
                    nonlocal changed
                    changed = True
                    # Valid metadata with changed bytes must not become a new baseline.
                    path = target.deploy_home / '.orbi/pi-providers.json'
                    path.write_text(path.read_text() + '\n')

                def check(ctx, target):
                    result = original_check(ctx, target)
                    if phase == 'validation':
                        change(target)
                    return result

                def validate(target, repo):
                    original_validate(target, repo)
                    if phase == 'rebind' and not changed:
                        change(target)

                with mock.patch.object(helper, 'run_orbi_check', check), \
                        mock.patch.object(helper, 'validate_target', validate):
                    code, doc, err = h.run('start', options=self.options)
                self.assertTrue(changed)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], 'target_changed')
                self.assertTrue(doc['error']['mutated'])
                self.assertEqual(doc['preparation']['state'],
                                 'failed' if phase == 'validation' else 'prepared')
                self.assertEqual(doc['activation'], 'none')
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_prepared_binding_drift_is_held_before_activation(self):
        original_lock = helper.locked
        for drift in ('config', 'provider', 'ownership', 'repo', 'harness', 'source', 'unit'):
            with self.subTest(drift=drift):
                h = Harness(Path(self.tmp.name) / drift)
                count = 0

                @contextlib.contextmanager
                def changed_lock(ctx, key):
                    nonlocal count
                    count += 1
                    if count == 2:  # setup lock is released before activation lock
                        if drift == 'config':
                            path = h.deploy / 'orbi.toml'
                            path.write_text(path.read_text().replace('max_concurrency = 1',
                                                                     'max_concurrency = 2'))
                        elif drift == 'provider':
                            (h.deploy / '.orbi/pi-providers.json').write_text('{}')
                        elif drift == 'ownership':
                            (h.repo / 'orbi.toml').write_text((h.deploy / 'orbi.toml').read_text())
                        elif drift == 'repo':
                            h.rules({'tool': 'git', 'argv_contains': [str(h.repo), 'remote.origin.url'],
                                     'stdout': 'https://github.com/foreign/repo.git\n'})
                        elif drift == 'source':
                            h.deploy_head = OLD_PIN
                            h.rules()
                        elif drift == 'unit':
                            prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                            (h.unit_dir / f'{prefix}@.service').write_text(
                                '[Service]\nEnvironment="ORBI_CONFIG=/foreign/orbi.toml"\n')
                        else:
                            (h.deploy / '.orbi/harness-bin/pi').write_text('# changed launcher\n')
                    with original_lock(ctx, key):
                        yield

                with mock.patch.object(helper, 'locked', changed_lock):
                    code, doc, err = h.run('start', options=self.options)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], {
                    'ownership': 'ambiguous_deployment', 'source': 'source_drift',
                    'unit': 'unit_conflict'}.get(drift, 'target_changed'))
                self.assertTrue(doc['error']['mutated'])
                self.assertEqual(doc['preparation']['state'], 'prepared')
                self.assertEqual(doc['activation'], 'none')
                self.assertEqual(count, 2)
                SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_existing_active_start_skips_preparation_and_rejects_selectors(self):
        code, doc, err = self.h.run('setup', options=self.options)
        self.assertEqual(code, 0, (doc, err))
        self.h.rules(*self.h.scheduler_rules(services={1: 'active'}, timers={1: 'active'},
                                            enabled={1: True}))
        before = snapshot(self.h.home)
        with mock.patch.object(helper, 'command_setup', side_effect=AssertionError):
            for dry_run in (True, False):
                self.h.clear_calls()
                code, doc, err = self.h.run('start', dry_run=dry_run)
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(doc['preparation']['state'], 'skipped')
                self.assertEqual(doc['first_tick'], 'already-active')
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse(any(c['tool'] == 'systemctl' and
                                     set(c['argv']) & {'enable', 'start'} for c in self.h.calls()))
                for options in (self.options, ['--harness', 'pi-bolt']):
                    code, doc, err = self.h.run('start', options=options, dry_run=dry_run)
                    self.assertEqual(code, 2, (doc, err))
                    self.assertEqual(doc['error']['code'], 'bootstrap_override_refused')
                    self.assertFalse(doc['error']['mutated'])
                    self.assertEqual(snapshot(self.h.home), before)

    def test_start_refuses_existing_partial_foreign_and_explicit_missing_targets(self):
        for state in ('explicit-missing', 'foreign', 'partial', 'resume'):
            with self.subTest(state=state):
                h = Harness(Path(self.tmp.name) / state)
                config, options = None, []
                if state == 'explicit-missing':
                    config = h.deploy / 'orbi.toml'
                elif state == 'resume':
                    options = ['--resume-setup', '--config', str(h.deploy / 'orbi.toml'), *self.options]
                else:
                    code, doc, err = h.run('setup', options=self.options)
                    self.assertEqual(code, 0, (doc, err))
                    if state == 'foreign':
                        path = h.deploy / 'orbi.toml'
                        path.write_text(path.read_text().replace(REPO, 'foreign/repo'))
                    else:
                        (h.deploy / '.orbi/pi-providers.json').unlink()
                before = snapshot(h.home)
                h.clear_calls()
                with mock.patch.object(helper, 'command_setup', side_effect=AssertionError):
                    code, doc, err = h.run('start', config=config, options=options)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], {
                    'explicit-missing': 'config_missing', 'foreign': 'config_mismatch',
                    'partial': 'provider_unavailable', 'resume': 'invalid_resume_selection'}[state])
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(doc['preparation']['state'], 'skipped')
                self.assertEqual(snapshot(h.home), before)
                SetupBoundaryTests.assert_no_activation(self, h.calls())

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
                           '--pi-model', 'gpt-6.1-sol', '--allow-metered']
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
                (action, self.options) for action in ('status', 'stop')]:
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
        self.assertIn('`/orbi setup --prepare-only` without bootstrap inputs', doc['error']['fix'])
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
                # Service readiness requires a pre-existing file reference, not shell-only auth.
                (h.deploy / '.orbi').mkdir(parents=True)
                (h.deploy / '.orbi/env').write_text('OPENAI_API_KEY=' + SECRET + '\n')
                code, doc, err = h.run('setup', options=[
                    '--pi-providers', str(catalog), '--pi-provider', 'openai',
                    '--pi-model', 'gpt-6.1-sol', '--allow-metered'])
                self.assertEqual(code, 0, (doc, err))
                self.assertNotIn('pi_thinking', h.config())
                self.assertEqual(json.loads((h.deploy / '.orbi/pi-providers.json').read_text()),
                                 self.metadata)
                self.assertIn('OPENAI_API_KEY=' + SECRET + '\n', (h.deploy / '.orbi/env').read_text())
                self.assertNotIn(SECRET, json.dumps(doc) + err)
                self.assertEqual(doc['prerequisites']['auth'][0]['state'], 'references_available')
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
        # Managed selection validation now refuses invalid env encoding before any writes.
        code, doc, err = self.h.run('setup', config=config, options=options)
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'harness_drift')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(doc['steps'][-1]['step'], 'preflight_target')
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        self.assertEqual(env.read_bytes(), b'CUSTOM=' + SECRET.encode() + b'\xff\n')
        SetupBoundaryTests.assert_no_activation(self, self.h.calls())

    def test_publication_interruptions_resume_config_last(self):
        for name in ('write_provider_metadata', 'write_launcher', 'write_env', 'write_config'):
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
            self.assertIn('/orbi setup --prepare-only --resume-setup', doc['error']['fix'])
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
        # Exercise legacy isolation repair; managed metadata drift is intentionally refused.
        (self.h.deploy / '.orbi/harness-bin/pi').unlink()
        original = 'CUSTOM_ENTRY=preserved\nPATH=' + self.h.env['PATH'] + '\n'
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
                self.assertEqual(doc['error']['code'],
                                 'env_invalid' if relative == '.orbi/env' else 'publication_conflict')
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
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        self.h.rules(
            {'tool': 'orbi', 'argv_contains': ['setup'],
             'exec': ['uv', 'tool', 'install', '--force', '--reinstall', '--editable',
                      '--python', '3.14', str(self.h.deploy)]},
            *self.h.enable_timer_rules(f'{prefix}@1.timer'),
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
            self.assertIn(call['argv'][0], {'--version', 'check', 'doctor', 'setup', 'install-units',
                                            'sync-engine-source'})
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
                        failed = ['--user', 'disable', '--now', '--no-reload', timers[-1]]
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
                        self.assertEqual(self.mutations(), [['--user', 'disable', '--now', '--no-reload', t]
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
                    if failed_step != 'first_tick':
                        self.assertEqual(doc['first_tick'], 'requested' if failure == 'exit' else
                                         ('blocked' if failure == 'snapshot_unavailable' else 'not-requested'))
                        self.assertEqual(doc['recurring_scheduling'], 'incomplete')
                    self.assertIn('may already be activated', doc['error']['message'])
                    self.assertEqual([s['step'] for s in doc['steps'][:9]],
                                     ['reuse_existing_deployment', 'lock', 'recheck_target',
                                      'set_release_track', 'sync_engine_source', 'pin_release',
                                      'validate_non_activating', 'upstream_setup', 'install_units'])
                    self.assertEqual(self.mutations(),
                                     [['--user', 'enable', '--now', t] for t in completed] + [failed]
                                     + ([['--user', 'start', service]] if failure == 'exit'
                                        and failed_step != 'first_tick' else []))
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

    def test_timer_failure_first_tick_uses_fresh_idle_evidence_and_keeps_error(self):
        timer, service = f'{self.prefix}@1.timer', f'{self.prefix}@1.service'
        marker = self.h.root / 'timer-failed'
        for request in ('success', 'exit', 'timeout'):
            with self.subTest(request=request):
                marker.unlink(missing_ok=True)
                # A failed enable may nevertheless enable/activate the timer.
                fresh = self.h.scheduler_rules(timers={1: 'active'}, enabled={1: True})
                for rule in fresh:
                    rule['if_exists'] = str(marker)
                self.h.rules(
                    {'tool': 'systemctl', 'argv_contains': ['--user enable --now', timer], 'exit': 7,
                     'write': {str(marker): 'partial'}, 'stderr': SECRET},
                    {'tool': 'systemctl', 'argv_contains': ['start', service],
                     'exit': 0 if request == 'success' else 9,
                     'sleep': 2 if request == 'timeout' else 0, 'stderr': SECRET},
                    *fresh, *self.h.scheduler_rules())
                self.h.clear_calls()
                with self.bounded_run(['--user', 'start', service]):
                    code, doc, err = self.h.run('start')
                self.assertEqual(code, 1, err)
                self.assert_receipt(doc, 'command_failed', 'activate_timer', timer,
                                    ('activated_timers', []))
                self.assertIn('exit 7', doc['error']['message'])
                self.assertEqual(doc['first_tick'], {'success': 'requested', 'exit': 'failed',
                                                     'timeout': 'unverified'}[request])
                evidence = doc['first_tick_evidence']
                self.assertEqual(evidence['unit'], service)
                self.assertEqual(evidence['scheduler']['pending_jobs'], [])
                self.assertTrue(evidence['scheduler']['timers'][timer]['enabled'])
                if request != 'success':
                    self.assertEqual(evidence['error'], 'command_timeout' if request == 'timeout'
                                     else 'command_failed')
                self.assertEqual(self.mutations(), [['--user', 'enable', '--now', timer],
                                                   ['--user', 'start', service]])
                calls = self.h.calls()
                failed_at = next(i for i, c in enumerate(calls) if c['argv'] == self.mutations()[0])
                start_at = next(i for i, c in enumerate(calls) if c['argv'] == self.mutations()[1])
                reads = calls[failed_at + 1:start_at]
                self.assertTrue(any('list-jobs' in c['argv'] for c in reads))
                self.assertTrue(any('FragmentPath' in c['argv'] for c in reads))
                self.assertTrue(any('ActiveState' in c['argv'] for c in reads))
                self.assertFalse([c for c in calls if c['tool'] == 'orbi' and not c['argv']])
                self.assertEqual(snapshot(self.h.a['deploy']), self.h.a['snapshot'])

    def test_timer_failure_blocks_first_tick_on_unsafe_fresh_evidence(self):
        timer, service = f'{self.prefix}@1.timer', f'{self.prefix}@1.service'
        marker = self.h.root / 'timer-failed'
        original_config = self.config.read_text()
        for unsafe in ('active', 'activating', 'reloading', 'deactivating', 'unknown',
                       'unavailable', 'pending_service', 'pending_timer', 'surplus_worker',
                       'foreign', 'config_drift', 'repo_drift', 'missing_service',
                       'missing_timer', 'timer_transition', 'enablement_unknown', 'jobs_unreadable'):
            with self.subTest(unsafe=unsafe):
                marker.unlink(missing_ok=True)
                self.config.write_text(original_config)
                fresh = []
                writes = {str(marker): 'failed'}
                if unsafe in helper.DRAIN_STATES | {'unknown'}:
                    fresh = self.h.scheduler_rules(services={1: unsafe})
                elif unsafe == 'surplus_worker':
                    fresh = self.h.scheduler_rules(services={6: 'active'})
                    fresh.insert(0, {'tool': 'systemctl', 'argv_contains': ['list-units'],
                                     'stdout': f'{self.prefix}@6.service loaded active running -\n'})
                elif unsafe in ('pending_service', 'pending_timer', 'jobs_unreadable'):
                    unit = service if unsafe == 'pending_service' else timer
                    fresh = [{'tool': 'systemctl', 'argv_contains': ['list-jobs'],
                              'stdout': 'unreadable\n' if unsafe == 'jobs_unreadable' else
                                        f'42 {unit} start waiting\n'}]
                elif unsafe == 'unavailable':
                    fresh = [{'tool': 'systemctl', 'argv_contains': ['show'], 'exit': 1}]
                elif unsafe == 'foreign':
                    foreign = self.h.root / f'{self.prefix}@1.service'
                    foreign.write_text(f'Environment="ORBI_CONFIG={self.h.a["config"]}"\n')
                    fresh = [{'tool': 'systemctl', 'argv_contains': ['show', service, 'FragmentPath'],
                              'stdout': str(foreign) + '\n'}]
                elif unsafe == 'config_drift':
                    writes[str(self.config)] = original_config + '# changed\n'
                elif unsafe == 'repo_drift':
                    fresh = [{'tool': 'git', 'argv_contains': ['config', 'remote.origin.url'],
                              'stdout': 'https://github.com/other/repo.git\n'}]
                elif unsafe in ('missing_service', 'missing_timer'):
                    fresh = [{'tool': 'systemctl', 'argv_contains': ['show', 'FragmentPath',
                              service if unsafe == 'missing_service' else timer], 'stdout': '\n'}]
                elif unsafe == 'timer_transition':
                    fresh = self.h.scheduler_rules(timers={1: 'activating'})
                elif unsafe == 'enablement_unknown':
                    fresh = [{'tool': 'systemctl', 'argv_contains': ['is-enabled', timer],
                              'stdout': 'unknown\n', 'exit': 1}]
                for rule in fresh:
                    rule['if_exists'] = str(marker)
                self.h.rules({'tool': 'systemctl', 'argv_contains': ['--user enable --now', timer],
                              'exit': 7, 'write': writes}, *fresh, *self.h.scheduler_rules())
                self.h.clear_calls()
                code, doc, err = self.h.run('start')
                self.assertEqual(code, 1, err)
                self.assertEqual(doc['original_error'], 'command_failed')
                self.assertEqual(doc['first_tick'], 'blocked')
                self.assertTrue(doc['first_tick_evidence']['reason'])
                self.assertEqual(self.mutations(), [['--user', 'enable', '--now', timer]])
                self.assertEqual(snapshot(self.h.a['deploy']), self.h.a['snapshot'])
        self.config.write_text(original_config)

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
                    enabled = (self.h.enable_timer_rules(*(f'{self.prefix}@{i}.timer' for i in (1, 2)))
                               if action == 'start' else [])
                    self.h.rules(*enabled, *self.h.scheduler_rules())
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
                        self.assertEqual(doc['activation'], 'none' if phase == 'acquire' else 'started')

    def test_unlock_failure_does_not_replace_failed_timer_operation(self):
        original_flock = helper.fcntl.flock
        handles = []

        def broken_unlock(handle, operation):
            if operation == helper.fcntl.LOCK_UN:
                handles.append(handle)
                raise OSError(SECRET)
            return original_flock(handle, operation)

        for action, operation, step, completed_key in (
                ('start', 'enable', 'activate_timer', 'activated_timers'),
                ('stop', 'disable', 'disable_timer', 'disabled_timers')):
            for failure in ('exit', 'timeout'):
                with self.subTest(action=action, failure=failure):
                    timers = [f'{self.prefix}@{i}.timer' for i in (1, 2)]
                    argv = ['--user', operation, '--now']
                    if action == 'stop':
                        argv.append('--no-reload')
                    failed = [*argv, timers[-1]]
                    self.h.rules({'tool': 'systemctl', 'argv_contains': failed,
                                  'exit': 7, 'stderr': SECRET,
                                  'sleep': 2 if failure == 'timeout' else 0},
                                 *self.h.scheduler_rules())
                    self.h.clear_calls()
                    with mock.patch.object(helper.fcntl, 'flock', broken_unlock), \
                            self.bounded_run(failed):
                        try:
                            code, doc, err = self.h.run(action)
                        finally:
                            # Close even on the red path: a retained traceback can
                            # otherwise hold the lock and block the next subtest.
                            closed = bool(handles) and all(h.closed for h in handles)
                            for handle in handles:
                                handle.close()
                            handles.clear()
                    self.assertEqual(code, 1, err)
                    expected = 'command_timeout' if failure == 'timeout' else 'command_failed'
                    self.assert_receipt(doc, expected, step, timers[-1],
                                        (completed_key, timers[:-1]))
                    self.assertTrue(closed, 'lock handle must close even if unlock fails')
                    self.assertEqual(self.mutations(),
                                     [[*argv, t] for t in timers]
                                     + ([['--user', 'start', f'{self.prefix}@1.service']]
                                        if action == 'start' and failure == 'exit' else []))
                    self.assertNotIn(SECRET, err)

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

                    def broken_snapshot(ctx, target, **kwargs):
                        if not marker.exists():
                            return original(ctx, target, **kwargs)
                        reads.append('read')
                        if len(reads) > 1:
                            raise UnicodeError(SECRET)
                        if kind == 'control':
                            raise helper.ControlError('command_timeout', 'original read timed out',
                                                      fix='repair original read', exit_code=3)
                        raise subprocess.CalledProcessError(7, ['fake'], output=SECRET, stderr=SECRET)

                    with mock.patch.object(helper, 'scheduler_snapshot', broken_snapshot):
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
                enabled = (self.h.enable_timer_rules(*(f'{self.prefix}@{i}.timer' for i in (1, 2)))
                           if action == 'start' else [])
                self.h.rules(*enabled, *self.h.scheduler_rules())
                argv = [sys.executable, '-B', str(HELPER), action,
                        '--repo-dir', str(self.h.repo), '--json']
                success = subprocess.run(argv, env=self.h.env, capture_output=True,
                                         text=True, timeout=30)
                self.assertEqual(success.returncode, 0, success.stderr)
                self.assertEqual(json.loads(success.stdout)['status'], state)
                timer = f'{self.prefix}@2.timer'
                flags = ['--user', operation, '--now']
                if action == 'stop':
                    flags.append('--no-reload')
                self.h.rules({'tool': 'systemctl',
                              'argv_contains': [*flags, timer],
                              'exit': 7, 'stderr': SECRET}, *self.h.scheduler_rules())
                self.h.clear_calls()
                failed = subprocess.run(argv, env=self.h.env, capture_output=True,
                                        text=True, timeout=30)
                self.assertEqual(failed.returncode, 1, failed.stderr)
                doc = json.loads(failed.stdout)
                self.assert_receipt(doc, 'command_failed', step, timer,
                                    (completed_key, [f'{self.prefix}@1.timer']))
                self.assertEqual(self.mutations(),
                                 [[*flags, f'{self.prefix}@{i}.timer'] for i in (1, 2)]
                                 + ([['--user', 'start', f'{self.prefix}@1.service']]
                                    if action == 'start' else []))
                self.assertNotIn(SECRET, failed.stdout + failed.stderr)


class LifecycleSequenceTests(unittest.TestCase):
    CASES = (
        ('active', {1: 'active'}, {1: 'active'}, {1: True}, 'running', False),
        ('activating', {1: 'activating'}, {1: 'active'}, {1: True}, 'transitional', False),
        ('idle', {1: 'inactive'}, {1: 'inactive'}, {1: False}, 'stopped', True),
        ('surplus', {1: 'inactive'}, {1: 'active'}, {1: True, 2: True, 3: True},
         'prepared', False),
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

    def test_public_cli_stops_active_worker_after_disabling_timers(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        h.rules(*h.stop_service_rules(service), *h.scheduler_rules(services={1: 'active'}))
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'stop', '--repo-dir',
                                 str(h.repo), '--json'], env=h.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        doc = json.loads(result.stdout)
        self.assertEqual(doc['status'], 'stopped')
        self.assertEqual(doc['stopped_services'], [service])
        self.assertEqual(doc['pending_services'], [])
        mutations = [c['argv'] for c in h.calls() if c['tool'] == 'systemctl'
                     and set(c['argv']) & {'disable', 'stop', 'kill', 'restart'}]
        self.assertEqual(mutations, [['--user', 'disable', '--now', '--no-reload', f'{prefix}@{i}.timer']
                                     for i in range(1, helper.MAX_INSTANCES + 1)] +
                         [['--user', 'stop', service]])
        self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])

    def test_stop_disables_runtime_timer_before_stopping_worker(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        timer, service = f'{prefix}@1.timer', f'{prefix}@1.service'
        disabled = str(h.root / 'runtime-disabled')
        # Disabling real symlinks without a reload marks all loaded units stale,
        # even though their effective runtime bindings haven't changed.
        stale_worker = h.loaded_unit_rule(service, NeedDaemonReload='yes')
        stale_worker['if_exists'] = disabled
        next_timer = h.loaded_unit_rule(f'{prefix}@2.timer', NeedDaemonReload='yes')
        next_timer['if_exists'] = disabled
        h.rules(stale_worker, next_timer,
                {'tool': 'systemctl', 'argv_contains': ['disable', '--runtime', timer],
                 'write': {disabled: '1'}},
                {'tool': 'systemctl', 'argv_contains': ['is-enabled', timer],
                 'if_exists': disabled, 'stdout': 'disabled\n', 'exit': 1},
                {'tool': 'systemctl', 'argv_contains': ['is-enabled', timer],
                 'stdout': 'enabled-runtime\n'},
                *h.stop_service_rules(service), *h.scheduler_rules(services={1: 'active'}))
        code, doc, err = h.run('stop')
        self.assertEqual(code, 0, (doc, err))
        self.assertIn(timer, doc['disabled_timers'])
        self.assertEqual(doc['stopped_services'], [service])
        calls = [c['argv'] for c in h.calls() if c['tool'] == 'systemctl']
        runtime_disable = ['--user', 'disable', '--runtime', '--no-reload', timer]
        self.assertLess(calls.index(runtime_disable), calls.index(['--user', 'stop', service]))

    def test_stop_refuses_foreign_or_overridden_loaded_worker(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        foreign = h.unit_dir / service
        foreign.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={h.a["config"]}"\n')
        for override in (
                {'FragmentPath': str(foreign)},
                {'WorkingDirectory': str(h.a['deploy'])},
                {'Environment': f'ORBI_CONFIG={h.a["config"]}'},
                {'DropInPaths': '/foreign/override.conf'},
                {'BoundBy': 'orbi-a@1.service'}):
            with self.subTest(override=override):
                h.rules(h.loaded_unit_rule(service, **override), *h.scheduler_rules(services={1: 'active'}))
                h.clear_calls()
                code, doc, err = h.run('stop')
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], 'unit_conflict')
                self.assertEqual(doc['stopped_services'], [])
                self.assertFalse([c for c in h.calls() if c['tool'] == 'systemctl'
                                  and set(c['argv']) & {'stop', 'kill', 'restart', 'cancel'}])

    def test_scoped_stop_check_accepts_only_benign_vendor_dropins(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        vendor = h.root / 'vendor/service.d'
        vendor.mkdir(parents=True)
        benign = vendor / '10-timeout-abort.conf'
        benign.write_text('# vendor\n[Service]\nTimeoutStopFailureMode=abort\n')
        hostile = vendor / '20-override.conf'
        hostile.write_text('[Service]\nEnvironment=ORBI_CONFIG=/elsewhere/orbi.toml\n')
        for path in (benign, hostile):
            path.chmod(0o644)
        ctx = helper.Context(env=h.env, platform='linux')
        target = helper.deployment_from(h.deploy / 'orbi.toml')
        with mock.patch.object(helper, 'VENDOR_DROPIN_DIRS', (vendor,)), root_owned(benign, hostile):
            h.rules(h.loaded_unit_rule(service, DropInPaths=str(benign)), *h.scheduler_rules())
            helper.require_quiesce_unit(ctx, target, service)
            for dropins in (str(hostile), f'{benign} {hostile}', '/foreign/override.conf'):
                with self.subTest(dropins=dropins):
                    h.rules(h.loaded_unit_rule(service, DropInPaths=dropins), *h.scheduler_rules())
                    with self.assertRaises(helper.ControlError) as caught:
                        helper.require_quiesce_unit(ctx, target, service)
                    self.assertEqual(caught.exception.code, 'unit_conflict')

    def test_stop_refuses_inactive_worker_with_foreign_loaded_binding(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        h.rules(h.loaded_unit_rule(service, Environment=f'ORBI_CONFIG={h.a["config"]}'),
                *h.scheduler_rules())
        code, doc, err = h.run('stop')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'unit_conflict')
        self.assertEqual(doc['stopped_services'], [])
        self.assertFalse(any('stop' in c['argv'] for c in h.calls()))

    def test_stop_refuses_timer_pointing_to_another_deployment(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        timer = f'{prefix}@1.timer'
        h.rules(h.loaded_unit_rule(timer, Triggers='orbi-a@1.service'), *h.scheduler_rules())
        code, doc, err = h.run('stop')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'unit_conflict')
        self.assertFalse(any(set(c['argv']) & {'disable', 'stop', 'kill', 'restart', 'cancel'}
                             for c in h.calls() if c['tool'] == 'systemctl'))

    def test_stop_never_cancels_a_job_whose_identity_changed(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        seen = str(h.root / 'jobs-observed')
        h.rules({'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'if_exists': seen,
                 'stdout': '42 orbi-a@1.service start waiting\n'},
                {'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'if_exists': str(h.root / 'paused'),
                 'stdout': f'42 {service} start waiting\n', 'write': {seen: '1'}},
                {'tool': 'systemctl', 'argv_contains': ['disable', '--now'],
                 'write': {str(h.root / 'paused'): '1'}}, *h.scheduler_rules())
        code, doc, err = h.run('stop')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertIn('pending start changed', doc['error']['message'])
        self.assertFalse(any('cancel' in c['argv'] for c in h.calls()))

    def test_stop_requires_idle_readback_even_after_successful_stop_command(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        service = f'{prefix}@1.service'
        h.rules(*h.scheduler_rules(services={1: 'active'}))  # stop exits 0, but the unit is still active
        code, doc, err = h.run('stop')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertEqual(doc['steps'][-1]['step'], 'verify_quiescent')
        self.assertEqual(doc['pending_services'], [{'unit': service, 'state': 'active'}])
        self.assertIn(['--user', 'stop', service], [c['argv'] for c in h.calls() if c['tool'] == 'systemctl'])

    def test_stop_configured_slots_above_five(self):
        for active_worker in (False, True):
            with self.subTest(active_worker=active_worker):
                h = self.fresh()
                config = h.deploy / 'orbi.toml'
                config.write_text(config.read_text().replace('max_concurrency = 1',
                                                           'max_concurrency = 6'))
                prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                timers = [f'{prefix}@{i}.timer' for i in range(1, 7)]
                service = f'{prefix}@6.service'
                disabled = [h.root / f'disabled-{i}' for i in range(1, 7)]
                mutations = []
                for timer, marker in zip(timers, disabled):
                    mutations.extend([
                        {'tool': 'systemctl', 'argv_contains': ['disable', '--now', timer],
                         'write': {str(marker): 'disabled'}},
                        {'tool': 'systemctl', 'argv_contains': ['is-enabled', timer],
                         'if_exists': str(marker), 'stdout': 'disabled\n', 'exit': 1},
                        {'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState', timer],
                         'if_exists': str(marker), 'stdout': 'inactive\n'}])
                h.rules(*mutations, *h.stop_service_rules(service), *h.scheduler_rules(
                    services={6: 'active' if active_worker else 'inactive'},
                    timers=dict.fromkeys(range(1, 7), 'active'),
                    enabled=dict.fromkeys(range(1, 7), True)))
                before = snapshot(h.home)
                for dry_run in (True, False):
                    result = subprocess.run(
                        [sys.executable, '-B', str(HELPER), 'stop', '--repo-dir', str(h.repo),
                         '--json', *(['--dry-run'] if dry_run else [])], env=h.env,
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                    doc = json.loads(result.stdout)
                    self.assertEqual(doc['disabled_timers'], timers)
                    self.assertEqual(doc['pending_services'],
                                     [{'unit': service, 'state': 'active'}] if dry_run and active_worker else [])
                    self.assertEqual(doc['status'], 'planned' if dry_run else 'stopped')
                    if dry_run:
                        self.assertEqual(snapshot(h.home), before)
                        self.assertFalse(any(marker.exists() for marker in disabled))
                    else:
                        self.assertTrue(all(marker.exists() for marker in disabled))
                        self.assertEqual(doc['stopped_services'], [service] if active_worker else [])
                mutations = [c['argv'] for c in h.calls() if c['tool'] == 'systemctl'
                             and set(c['argv']) & {'enable', 'disable', 'start', 'stop',
                                                   'kill', 'restart'}]
                self.assertEqual(mutations,
                                 [['--user', 'disable', '--now', '--no-reload', timer] for timer in timers]
                                 + ([['--user', 'stop', service]] if active_worker else []))
                self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])

    def test_stop_failure_receipt_observes_configured_slot_above_five(self):
        h = self.fresh()
        config = h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace('max_concurrency = 1',
                                                   'max_concurrency = 6'))
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        timer = f'{prefix}@6.timer'
        h.rules({'tool': 'systemctl', 'argv_contains': ['disable', '--now', timer], 'exit': 7},
                *h.scheduler_rules(timers={6: 'active'}, enabled={6: True}))
        code, doc, err = h.run('stop')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'command_failed')
        self.assertEqual(doc['steps'][-1]['unit'], timer)
        self.assertNotIn(timer, doc['disabled_timers'])
        self.assertTrue(doc['scheduler']['timers'][timer]['enabled'])
        self.assertEqual(doc['scheduler']['inventory']['scan_last'], 6)

    def test_setup_configured_slots_above_five_are_busy(self):
        h = self.fresh()
        config = h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace('max_concurrency = 1',
                                                   'max_concurrency = 6'))
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        for services, timers, enabled in (({}, {}, {6: True}),
                                         ({}, {6: 'active'}, {}),
                                         ({6: 'active'}, {}, {})):
            for dry_run in (True, False):
                with self.subTest(services=services, timers=timers, enabled=enabled,
                                  dry_run=dry_run):
                    # Include slot 6's inactive fragments in every fixture variant.
                    h.rules(*h.scheduler_rules(services={6: 'inactive', **services},
                                               timers=timers, enabled=enabled))
                    h.clear_calls()
                    before = snapshot(h.home)
                    code, doc, err = h.run('setup', dry_run=dry_run)
                    self.assertNotEqual(code, 0, (doc, err))
                    self.assertEqual(doc['error']['code'], 'setup_busy')
                    self.assertIn(f'{prefix}@6.service', doc['scheduler']['services'])
                    inventory = doc['scheduler']['inventory']
                    self.assertEqual(inventory['scan_last'], 6)
                    self.assertTrue(inventory['configured_slots_covered'])
                    self.assertIn('`/orbi stop` if interruption is intended', doc['error']['fix'])
                    self.assertIn('preserve recovery inputs', doc['error']['fix'])
                    self.assertEqual(snapshot(h.home), before)
                    SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_stop_rechecks_owned_timers_after_lock(self):
        for observation_fails in (False, True):
            with self.subTest(observation_fails=observation_fails):
                h = self.fresh()
                prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
                timers = [f'{prefix}@{i}.timer' for i in (1, 2)]
                scheduler = h.scheduler_rules(enabled={1: True, 2: True})
                absent = [
                    {'tool': 'systemctl',
                     'argv_contains': ['show', f'{prefix}@{i}.timer', 'FragmentPath'],
                     'stdout': '\n'} for i in range(2, helper.MAX_INSTANCES + 1)]
                disabled = [h.root / f'disabled-{i}' for i in (1, 2)]
                mutations = []
                for timer, marker in zip(timers, disabled):
                    mutations.extend([
                        {'tool': 'systemctl', 'argv_contains': ['disable', '--now', timer],
                         'write': {str(marker): 'disabled'}},
                        {'tool': 'systemctl', 'argv_contains': ['is-enabled', timer],
                         'if_exists': str(marker), 'stdout': 'disabled\n', 'exit': 1}])
                h.rules(*absent, *mutations, *scheduler)
                locked = helper.locked

                @contextlib.contextmanager
                def concurrent(ctx, key):
                    # A start publishes/enables timer 2 after stop's preflight.
                    failure = ([{'tool': 'systemctl', 'argv_contains': ['show'], 'exit': 1}]
                               if observation_fails else [])
                    h.rules(*failure, *absent[1:], *mutations, *scheduler)
                    with locked(ctx, key):
                        yield

                with mock.patch.object(helper, 'locked', concurrent):
                    code, doc, err = h.run('stop')
                if observation_fails:
                    self.assertNotEqual(code, 0, (doc, err))
                    self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
                    self.assertTrue(doc['error']['mutated'])
                    self.assertEqual(doc['steps'][-1]['step'], 'observe_scheduler')
                    self.assertEqual(doc['disabled_timers'], [])
                else:
                    self.assertEqual(code, 0, (doc, err))
                    # Actual disable subprocesses must change both fixture states.
                    self.assertTrue(all(marker.exists() for marker in disabled), doc)
                    self.assertEqual(doc['status'], 'stopped')
                    self.assertEqual(doc['disabled_timers'], timers)
                    self.assertEqual(doc['steps'][-1], {'step': 'verify_quiescent', 'status': 'ok'})
                    code, status, err = h.run('status')
                    self.assertEqual(code, 0, err)
                    self.assertFalse(any(item['enabled'] for item in
                                         status['scheduler']['timers'].values()))
                self.assertEqual(
                    [c['argv'] for c in h.calls() if c['tool'] == 'systemctl'
                     and set(c['argv']) & {'enable', 'disable', 'start', 'stop', 'kill', 'restart'}],
                    [] if observation_fails else
                    [['--user', 'disable', '--now', '--no-reload', timer] for timer in timers])
                self.assertEqual(snapshot(h.a['deploy']), h.a['snapshot'])

    def test_shared_templates_are_not_enabled_capacity(self):
        h = self.fresh()
        config = h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace('max_concurrency = 1',
                                                   'max_concurrency = 3'))
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        h.rules(*h.scheduler_rules(enabled={1: True, 2: True, 3: True}))
        before = snapshot(h.home)
        code, status, err = h.run('status')
        self.assertEqual(code, 0, err)
        code, preview, err = h.run('start', dry_run=True)
        self.assertEqual(code, 0, err)
        # Assert both public outputs before inspecting the additive schema.
        self.assertEqual(preview['steps'][2]['timers'],
                         [f'{prefix}@{i}.timer' for i in range(1, 4)])
        scheduler = status['scheduler']
        self.assertEqual(scheduler['inventory'], {
            'scope': 'local-target-prefix', 'scan_first': 1, 'scan_last': 5,
            'outside_scan': 'unobserved', 'configured_slots': 3,
            'configured_slots_covered': True,
            'counts': {'enabled_timers': {'state': 'ok', 'value': 3},
                       'active_timers': {'state': 'ok', 'value': 0},
                       'running_services': {'state': 'ok', 'value': 0}}})
        self.assertEqual(len(scheduler['services']), 5)
        for index in range(1, 6):
            for kind in ('timer', 'service'):
                record = scheduler[kind + 's'][f'{prefix}@{index}.{kind}']
                self.assertEqual(record['configured'], index <= 3)
                self.assertEqual(record['fragment_kind'], 'template')
                self.assertTrue(record['installed'])  # legacy availability only
                self.assertTrue(record['owned'])
        self.assertEqual(preview['scheduler'], scheduler)
        self.assertFalse(preview['activated'])
        self.assertEqual(snapshot(h.home), before)
        SetupBoundaryTests.assert_no_activation(self, h.calls())
        expected_reads = []
        for index in range(1, 6):
            timer, service = f'{prefix}@{index}.timer', f'{prefix}@{index}.service'
            expected_reads.extend([
                ['--user', 'show', timer, '-p', 'FragmentPath', '--value'],
                ['--user', 'show', service, '-p', 'FragmentPath', '--value'],
                ['--user', 'show', '-p', 'ActiveState', '--value', service],
                ['--user', 'is-enabled', timer],
                ['--user', 'show', '-p', 'ActiveState', '--value', timer]])
        self.assertEqual([c['argv'] for c in h.calls() if c['tool'] == 'systemctl'],
                         expected_reads + [
                             ['--user', 'show', f'{prefix}@{i}.timer', '-p', 'LastTriggerUSec',
                              '-p', 'NextElapseUSecRealtime'] for i in range(1, 6)] + expected_reads)

        # Exercise the actual CLI's text/JSON rendering, not just flatten().
        for json_mode in (False, True):
            result = subprocess.run(
                [sys.executable, '-B', str(HELPER), 'status', '--repo-dir', str(h.repo),
                 *(['--json'] if json_mode else [])], env=h.env,
                capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            if json_mode:
                self.assertEqual(json.loads(result.stdout)['scheduler'], scheduler)
            else:
                for line in ('scheduler.inventory.configured_slots=3',
                             'scheduler.inventory.scan_last=5',
                             'scheduler.inventory.counts.enabled_timers.value=3',
                             f'scheduler.services.{prefix}@4.service.configured=False',
                             f'scheduler.timers.{prefix}@5.timer.fragment_kind=template'):
                    self.assertIn(line + '\n', result.stdout)
        self.assertEqual(snapshot(h.home), before)

    def test_active_idle_status_and_setup_busy_preview_preserve_scheduling(self):
        # SalmaListApi offline shape: one active/owned timer, no observed worker.
        h = self.fresh()
        h.rules(*h.scheduler_rules(timers={1: 'active'}, enabled={1: True}))
        before = snapshot(h.home)
        for action, options, expected_exit in (
                ('status', [], 0), ('setup', ['--dry-run'], 1),
                ('start', ['--dry-run'], 0)):
            with self.subTest(action=action):
                result = subprocess.run(
                    [sys.executable, '-B', str(HELPER), action,
                     '--repo-dir', str(h.repo), '--json', *options], env=h.env,
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, expected_exit, result.stderr)
                doc = json.loads(result.stdout)
                scheduler = doc['scheduler']
                self.assertEqual(scheduler['inventory']['counts'], {
                    'enabled_timers': {'state': 'ok', 'value': 1},
                    'active_timers': {'state': 'ok', 'value': 1},
                    'running_services': {'state': 'ok', 'value': 0}})
                self.assertEqual(scheduler['inventory']['outside_scan'], 'unobserved')
                if action == 'status':
                    self.assertEqual(doc['deployment']['state'], 'prepared')
                elif action == 'setup':
                    self.assertEqual(doc['error']['code'], 'setup_busy')
                    self.assertFalse(doc['error']['mutated'])
                else:
                    self.assertEqual(doc['preparation']['state'], 'skipped')
                    self.assertFalse(doc['activated'])
                self.assertEqual(snapshot(h.home), before)
        SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_inventory_counts_independent_activity_runtime_and_surplus(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        cases = (
            ('enabled-only', {}, {}, {1: True}, [], (1, 0, 0)),
            ('timer-only', {}, {1: 'active'}, {}, [], (0, 1, 0)),
            ('service-only', {1: 'active'}, {}, {}, [], (0, 0, 1)),
            ('service-states', {1: 'active', 2: 'activating', 3: 'reloading',
                                4: 'deactivating'}, {1: 'activating', 2: 'active'},
             {}, [], (0, 1, 3)),
            ('surplus', {4: 'active'}, {5: 'active'}, {4: True}, [], (1, 1, 1)),
            ('runtime', {}, {}, {}, [{'tool': 'systemctl',
                'argv_contains': ['is-enabled', f'{prefix}@4.timer'],
                'stdout': 'enabled-runtime\n'}], (1, 0, 0)),
        )
        for name, services, timers, enabled, extra, expected in cases:
            with self.subTest(case=name):
                h.rules(*extra, *h.scheduler_rules(services=services, timers=timers,
                                                  enabled=enabled))
                before = snapshot(h.home)
                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                counts = doc['scheduler']['inventory']['counts']
                self.assertEqual(counts, dict(zip(
                    ('enabled_timers', 'active_timers', 'running_services'),
                    ({'state': 'ok', 'value': n} for n in expected))))
                self.assertFalse(doc['scheduler']['services'][f'{prefix}@4.service']['configured'])
                self.assertFalse(doc['scheduler']['timers'][f'{prefix}@5.timer']['configured'])
                self.assertEqual(snapshot(h.home), before)

    def test_inventory_incomplete_reads_are_not_zero(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        timer, service = f'{prefix}@1.timer', f'{prefix}@1.service'
        cases = (
            ('timer-fragment', ['show', timer, 'FragmentPath'], '', 1, (None, None, None)),
            ('service-fragment', ['show', service, 'FragmentPath'], '', 1, (None, None, None)),
            ('enablement', ['is-enabled', timer], '', 1, (None, None, None)),
            ('timer-state-failed', ['show', 'ActiveState', timer], 'inactive\n', 1, (0, None, 0)),
            ('timer-state-empty', ['show', 'ActiveState', timer], '', 0, (0, None, 0)),
            ('timer-state-unknown', ['show', 'ActiveState', timer], 'unexpected\n', 0, (0, None, 0)),
            ('service-state', ['show', 'ActiveState', service], '', 1, (0, 0, None)),
        )
        for name, argv, output, exit_code, expected in cases:
            with self.subTest(case=name):
                h.rules({'tool': 'systemctl', 'argv_contains': argv,
                         'stdout': output, 'exit': exit_code}, *h.scheduler_rules())
                before = snapshot(h.home)
                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                inventory = doc['scheduler']['inventory']
                self.assertEqual(inventory['configured_slots'], 1)
                self.assertEqual((inventory['scan_first'], inventory['scan_last']), (1, 5))
                for metric, value in zip(('enabled_timers', 'active_timers', 'running_services'),
                                         expected):
                    self.assertEqual(inventory['counts'][metric], {
                        'state': 'unavailable' if value is None else 'ok', 'value': value})
                self.assertEqual(snapshot(h.home), before)
                if name.startswith('timer-state'):
                    self.assertEqual(doc['scheduler']['state'], 'ok')  # legacy state unchanged
        out = io.StringIO()
        helper.render(helper.Context(stdout=out), doc, False)
        self.assertIn('scheduler.inventory.counts.running_services.state=unavailable\n', out.getvalue())
        self.assertIn('scheduler.inventory.counts.running_services.value=None\n', out.getvalue())

    def test_inventory_fragment_absence_ownership_and_instance_evidence(self):
        h = self.fresh()
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        h.rules(*h.scheduler_rules(installed=False))
        code, doc, err = h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['scheduler']['timers'], {})  # legacy emission rule
        for record in doc['scheduler']['services'].values():
            self.assertEqual(record['fragment_kind'], 'absent')
            self.assertFalse(record['installed'])
            self.assertFalse(record['owned'])
        for count in doc['scheduler']['inventory']['counts'].values():
            self.assertEqual(count, {'state': 'ok', 'value': 0})

        # Observe an instance-specific fragment, not the shared template.
        service, timer = f'{prefix}@1.service', f'{prefix}@1.timer'
        service_path, timer_path = h.root / service, h.root / timer
        timer_path.write_text('[Timer]\n')
        service_path.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={h.deploy}/orbi.toml"\n')
        instance_rules = [
            {'tool': 'systemctl', 'argv_contains': ['show', service, 'FragmentPath'],
             'stdout': str(service_path)},
            {'tool': 'systemctl', 'argv_contains': ['show', timer, 'FragmentPath'],
             'stdout': str(timer_path)}]
        h.rules(*instance_rules, *h.scheduler_rules())
        code, doc, err = h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['scheduler']['services'][service]['fragment_kind'], 'instance')
        self.assertEqual(doc['scheduler']['timers'][timer]['fragment_kind'], 'instance')
        timer_path.unlink()
        code, doc, err = h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['scheduler']['timers'][timer]['fragment_kind'], 'unknown')
        counts = doc['scheduler']['inventory']['counts']
        for metric in ('enabled_timers', 'active_timers'):
            self.assertEqual(counts[metric], {'state': 'unavailable', 'value': None})
        self.assertEqual(counts['running_services'], {'state': 'ok', 'value': 0})
        timer_path.write_text('[Timer]\n')

        for name, content in (
                ('foreign', f'Environment="ORBI_CONFIG={h.a["config"]}"\n'),
                ('unattributed', '[Service]\n'),
                ('ambiguous', f'Environment="ORBI_CONFIG={h.deploy}/orbi.toml"\n'
                              f'Environment="ORBI_CONFIG={h.a["config"]}"\n'),
                ('invalid-encoding', b'\xff'),
                ('unreadable', None)):
            with self.subTest(case=name):
                if content is None:
                    service_path.unlink()
                elif isinstance(content, bytes):
                    service_path.write_bytes(content)
                else:
                    service_path.write_text(content)
                before = snapshot(h.home)
                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                for count in doc['scheduler']['inventory']['counts'].values():
                    self.assertEqual(count, {'state': 'unavailable', 'value': None})
                if name in {'foreign', 'unattributed'}:
                    self.assertFalse(doc['scheduler']['services'][service]['owned'])
                self.assertEqual(snapshot(h.home), before)
        self.assertEqual(helper.fragment_kind(str(service_path), service), 'unknown')
        timer_path.rename(h.root / 'unexpected.timer')
        self.assertEqual(helper.fragment_kind(str(h.root / 'unexpected.timer'), timer), 'unknown')

    def test_inventory_exception_capacity_and_preview_coverage(self):
        h = self.fresh()
        config = h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace('max_concurrency = 1',
                                                   'max_concurrency = 6'))
        prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        rules = h.scheduler_rules(services={6: 'active'}, timers={6: 'active'})
        h.rules(*rules)
        before = snapshot(h.home)
        for action, flags in (('status', []), ('start', ['--dry-run'])):
            with self.subTest(action=action):
                result = subprocess.run(
                    [sys.executable, '-B', str(HELPER), action, '--repo-dir', str(h.repo),
                     '--json', *flags], env=h.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
                doc = json.loads(result.stdout)
                if action == 'status':
                    self.assertEqual(doc['deployment']['state'], 'running')
                else:
                    self.assertEqual(doc['first_tick'], 'already-active')
                    self.assertEqual(doc['steps'][2]['timers'],
                                     [f'{prefix}@{i}.timer' for i in range(1, 6)])
                inventory = doc['scheduler']['inventory']
                self.assertEqual(inventory['configured_slots'], 6)
                self.assertTrue(inventory['configured_slots_covered'])
                self.assertEqual(inventory['outside_scan'], 'unobserved')
                self.assertEqual(doc['scheduler']['services'][f'{prefix}@6.service']['state'],
                                 'active')
        h.rules({'tool': 'systemctl', 'argv_contains': ['show', f'{prefix}@6.timer', 'FragmentPath'],
                 'exit': 1}, *rules)
        code, doc, err = h.run('start', dry_run=True)
        self.assertEqual(code, 1, (doc, err))
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertEqual(doc['error']['message'],
                         'cannot read the target scheduler: the systemd user session is not readable')
        self.assertIn('verify the systemd user session, then rerun', doc['error']['fix'])
        for error in (helper.ControlError('scheduler_unavailable', 'read failed'),
                      PermissionError('private details'), UnicodeError('private details'),
                      subprocess.SubprocessError('private details')):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(helper, 'scheduler_snapshot', side_effect=error):
                    code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['deployment']['state'], 'unavailable')
                inventory = doc['scheduler']['inventory']
                self.assertEqual(inventory['configured_slots'], 6)
                self.assertEqual(inventory['scan_last'], 6)
                self.assertTrue(inventory['configured_slots_covered'])
                for count in inventory['counts'].values():
                    self.assertEqual(count, {'state': 'unavailable', 'value': None})
                self.assertNotIn('private details', json.dumps(doc))
        self.assertEqual(snapshot(h.home), before)
        SetupBoundaryTests.assert_no_activation(self, h.calls())

    def test_absent_deployment_has_no_linux_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp))
            for platform in ('linux', 'darwin'):
                code, doc, err = h.run('status', platform=platform)
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['deployment']['state'], 'absent')
                self.assertNotIn('inventory', doc['scheduler'])

    def test_lifecycle_sequence(self):
        for name, services, timers, enabled, state, expect_tick in self.CASES:
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

                # Idempotent start: tick on activation, not when scheduling is already current.
                if expect_tick:
                    h.rules(*h.enable_timer_rules(f'{prefix}@1.timer'),
                            *h.scheduler_rules(services=services, timers=timers, enabled=enabled))
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

                # Stop disables timers, stops an owned non-idle worker and verifies inactivity.
                expected_stops = [f'{prefix}@1.service'] if services[1] != 'inactive' else []
                paused = str(h.root / 'paused')
                h.rules({'tool': 'systemctl', 'argv_contains': ['disable', '--now'],
                         'write': {paused: '1'}},
                        *(r for service in expected_stops for r in h.stop_service_rules(service)),
                        *[dict(r, if_exists=paused) for r in h.scheduler_rules(services=services)],
                        *h.scheduler_rules(services=services, timers=timers, enabled=enabled))
                h.clear_calls()
                code, doc, err = h.run('stop')
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(doc['status'], 'stopped')
                self.assertEqual(doc['stopped_services'], expected_stops)
                self.assertEqual(doc['pending_services'], [])
                self.assertEqual(doc['disabled_timers'],
                                 [f'{prefix}@{i}.timer' for i in range(1, helper.MAX_INSTANCES + 1)])
                calls = h.calls()
                self.assertFalse([c for c in calls if c['tool'] == 'systemctl'
                                  and set(c['argv']) & {'kill', 'restart'}])
                self.assertFalse([c for c in calls if c['tool'] == 'orbi'
                                  and (not c['argv'] or c['argv'][0] in {'setup', 'install-units'})])

                code, doc, err = h.run('status')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['deployment']['state'], 'stopped')

    def test_unsupported_platforms_change_nothing(self):
        h = self.fresh()
        h.rules(*h.scheduler_rules())
        before = snapshot(h.home)
        code, doc, err = h.run('status', platform='darwin')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['platform'], 'darwin')
        self.assertEqual(doc['scheduler']['state'], 'launchd')
        self.assertNotIn('inventory', doc['scheduler'])
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
        # partial mutation and uncertainty instead of claiming a successful stop.
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
        h.rules({'tool': 'gh', 'argv_contains': ['api', 'graphql'],
                 'stdout': '', 'stderr': 'auth unavailable\n', 'exit': 1},
                *h.scheduler_rules())
        code, doc, err = h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['state'], 'unavailable')
        self.assertNotIn('ready', doc['queue'])


class InstallerFleetTests(unittest.TestCase):
    def setUp(self):
        root = self.enterContext(tempfile.TemporaryDirectory())
        self.h = Harness(Path(root))

    @contextlib.contextmanager
    def other_account(self, *, active=False, linger=(), definitions=PermissionError):
        ctx = helper.Context(env=self.h.env, platform='linux')
        home = self.h.root / 'private-other-home'
        uid = 1001 if os.getuid() != 1001 else 1002
        passwd = f'other:x:{uid}:{uid}:Other:{home}:/bin/sh\n'
        original_iterdir = Path.iterdir

        def iterdir(path):
            if path == Path('/run/user'):
                return iter([path / str(uid)] if active else [])
            if path == Path('/var/lib/systemd/linger'):
                if isinstance(linger, type):
                    raise linger(13, SECRET, str(path))
                return iter(path / name for name in linger)
            if path == home / '.config/systemd/user.control' and definitions is not None:
                raise definitions(SECRET)
            return original_iterdir(path)

        with mock.patch.object(Path, 'iterdir', iterdir), mock.patch.object(
                ctx, 'run', return_value=subprocess.CompletedProcess([], 0, passwd, '')):
            yield ctx, home

    def test_fleet_excludes_and_discloses_unreadable_offline_account(self):
        with self.other_account() as (ctx, home):
            managers, not_checked = helper.fleet_managers(ctx)
            self.assertEqual([manager.name for manager in managers], ['system', 'user'])
            self.assertEqual(not_checked, ('other',))
            with mock.patch.object(helper, 'fleet_inventory', return_value=([], {}, {})):
                receipt = helper.installer_fleet(ctx)
        self.assertEqual(receipt['status'], 'no_deployments')
        self.assertEqual(receipt['not_checked'], ['other'])
        for private in (str(home), SECRET, 'PermissionError'):
            self.assertNotIn(private, json.dumps(receipt))

    def test_offline_account_continued_unrelated_unit_is_not_orbi_evidence(self):
        with self.other_account(definitions=None) as (ctx, home):
            directory = home / '.config/systemd/user'
            directory.mkdir(parents=True)
            unit = directory / 'vendor.service'
            unit.write_text('[Service]\nExecStart=/usr/bin/tmux unbind-key -a; \\\n  new-session\n')
            manager = helper.FleetManager('user:other', ('--user', '--machine=other@.host'), 1001, home)
            self.assertIs(helper.fleet_offline_user_evidence(ctx, manager, live=False), False)
            unit.write_text(f'[Service]\nExecStart=/bin/orbi --config "{SECRET}\n')
            with self.assertRaises(helper.ControlError) as caught:
                helper.fleet_offline_user_evidence(ctx, manager, live=False)
            self.assertEqual(caught.exception.message, 'user:other:vendor.service: unit definition is unparsable')
            self.assertNotIn(SECRET, str(caught.exception))

    def test_fleet_holds_when_unreadable_account_is_live_or_lingering(self):
        for options in ({'active': True}, {'linger': ('other',)}):
            with self.subTest(options=options), self.other_account(**options) as (ctx, home), \
                    mock.patch.object(helper, 'fleet_inventory') as inventory:
                receipt = helper.installer_fleet(ctx)
                self.assertEqual(receipt['status'], 'held')
                self.assertEqual(receipt['error']['message'],
                                 'user:other: cannot verify installed definitions (PermissionError)')
                self.assertFalse(receipt.get('not_checked'))
                self.assertNotIn(str(home), json.dumps(receipt))
                self.assertNotIn(SECRET, json.dumps(receipt))
                inventory.assert_not_called()

    def test_fleet_holds_when_linger_directory_cannot_be_listed(self):
        for error in (PermissionError, FileNotFoundError):
            with self.subTest(error=error), self.other_account(linger=error) as (ctx, home):
                receipt = helper.installer_fleet(ctx)
                self.assertEqual(receipt['status'], 'held')
                self.assertIn('cannot verify linger', receipt['error']['message'])
                for private in (str(home), '/var/lib/systemd/linger', SECRET):
                    self.assertNotIn(private, json.dumps(receipt))

    def test_fleet_holds_on_other_definition_errors(self):
        for error in (NotADirectoryError, ValueError):
            with self.subTest(error=error), self.other_account(definitions=error) as (ctx, home):
                receipt = helper.installer_fleet(ctx)
                self.assertEqual(receipt['status'], 'held')
                self.assertEqual(receipt['error']['message'],
                                 f'user:other: cannot verify installed definitions ({error.__name__})')
                self.assertNotIn(str(home), json.dumps(receipt))
                self.assertNotIn(SECRET, json.dumps(receipt))

    def test_fleet_holds_for_an_unreadable_unit_file_in_a_listable_folder(self):
        with self.other_account(definitions=None) as (ctx, home):
            directory = home / '.config/systemd/user'
            directory.mkdir(parents=True)
            unit = directory / 'private.service'
            unit.touch()
            with mock.patch.object(helper, 'host_definition', side_effect=PermissionError(13, SECRET, str(unit))):
                receipt = helper.installer_fleet(ctx)
        self.assertEqual(receipt['status'], 'held')
        self.assertEqual(receipt['error']['message'],
                         'user:other: cannot verify installed definitions (PermissionError)')
        self.assertNotIn('not_checked', receipt)
        self.assertNotIn(str(unit), json.dumps(receipt))
        self.assertNotIn(SECRET, json.dumps(receipt))

    def test_fleet_holds_if_a_folder_is_denied_but_other_readable_evidence_names_orbi(self):
        with self.other_account() as (ctx, home):
            directory = home / '.config/systemd/user'
            directory.mkdir(parents=True)
            orbi = directory / 'delivery.service'
            orbi.write_text('[Service]\nExecStart=/bin/orbi\n')
            dangling = directory / 'missing.service'
            dangling.symlink_to(directory / 'absent')
            iterdir = Path.iterdir
            with mock.patch.object(Path, 'iterdir', lambda path: (
                    iter((dangling, orbi)) if path == directory else iterdir(path))), \
                    mock.patch.object(helper, 'fleet_inventory', return_value=([], {}, {})) as inventory:
                receipt = helper.installer_fleet(ctx)
            inventory.assert_not_called()
        self.assertEqual(receipt['status'], 'held')
        self.assertEqual(receipt['error']['message'],
                         'user:other: cannot verify installed definitions (PermissionError)')
        self.assertNotIn('not_checked', receipt)

    def test_fleet_manager_bounds_reads_and_allows_time_for_service_transitions(self):
        ctx = helper.Context(env=self.h.env, platform='linux')
        manager = helper.FleetManager('system', ('--system',), 0, Path('/root'))
        with mock.patch.object(ctx, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            for verb, budget in (('show', helper.PROBE_TIMEOUT), ('list-jobs', helper.PROBE_TIMEOUT),
                                 ('stop', helper.MUTATION_TIMEOUT), ('start', helper.MUTATION_TIMEOUT),
                                 ('enable', helper.MUTATION_TIMEOUT), ('disable', helper.MUTATION_TIMEOUT)):
                with self.subTest(verb=verb):
                    manager.call(ctx, verb)
                    self.assertEqual(run.call_args.args[0], ['systemctl', '--system', '--no-ask-password', verb])
                    self.assertEqual(run.call_args.kwargs.get('timeout', helper.PROBE_TIMEOUT), budget)

    def test_system_preflight_uses_pkcheck_detail_and_a_process_bound_subject(self):
        ctx = helper.Context(env=self.h.env, platform='linux')
        manager = helper.FleetManager('system', ('--system',), 0, Path('/root'))
        unit = helper.FleetUnit(manager, 'worker.service', self.h.root / 'orbi.toml', (), 'active', 'static')
        with mock.patch.object(helper.os, 'geteuid', return_value=1001), mock.patch.object(
                ctx, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            helper.fleet_check_permissions(ctx, (unit,), {manager: {'42': ('unrelated.service', 'start')}})
        self.assertEqual(len(run.call_args_list), 2)
        for call, verb in zip(run.call_args_list, ('start', 'stop')):
            argv = call.args[0]
            self.assertEqual(argv[:4], ['pkcheck', '--action-id', 'org.freedesktop.systemd1.manage-units', '--process'])
            self.assertRegex(argv[4], rf'^{os.getpid()},[0-9]+,{os.getuid()}$')
            self.assertEqual(argv[5:], ['--detail', 'unit', unit.name, '--detail', 'verb', verb])

    def test_inventory_loads_configured_disabled_orbi_template_instances(self):
        ctx = helper.Context(env=self.h.env, platform='linux')
        manager = helper.FleetManager('user', ('--user',), os.getuid(), self.h.home)
        target = self.h.root / 'checkout'
        target.mkdir()
        config = target / 'orbi.toml'
        config.write_text('source_repos = ["example/repo"]\nmax_concurrency = 2\n')
        bootstrap = self.h.home / '.local/bin/orbi'
        service = self.h.unit_dir / 'project-delivery@.service'
        timer = self.h.unit_dir / 'project-schedule@.timer'
        service.write_text(f'[Service]\nWorkingDirectory={target}\n'
                           f'Environment="ORBI_CONFIG={config}"\nExecStart={bootstrap}\n')
        timer.write_text('[Timer]\nUnit=project-delivery@%i.service\n[Install]\nWantedBy=timers.target\n')
        dormant = self.h.unit_dir / 'dormant@.timer'
        dormant.write_text('[Timer]\nUnit=project-delivery@1.service\n[Install]\nWantedBy=timers.target\n')
        for path in (service, timer, dormant):
            path.chmod(0o644)
        properties = dict(LoadState='loaded', ActiveState='inactive', NeedDaemonReload='no',
                          CanStart='yes', CanStop='yes', KillMode='control-group', SendSIGKILL='yes',
                          DynamicUser='no', WorkingDirectory=target)

        def rule(name, **extra):
            values = {'Id': name, 'Names': name, **properties, **extra}
            return {'tool': 'systemctl', 'argv_contains': ['--user', 'show', name],
                    'stdout': '\n'.join(f'{k}={v}' for k, v in values.items())}

        rules = [
            {'tool': 'systemctl', 'argv_contains': ['--user', 'list-units'], 'stdout': ''},
            {'tool': 'systemctl', 'argv_contains': ['--user', 'list-unit-files'],
             'stdout': f'{service.name} static -\n{timer.name} disabled enabled\n{dormant.name} disabled -\n'},
            {'tool': 'systemctl', 'argv_contains': ['--user', 'show', 'UnitPath'], 'stdout': str(self.h.unit_dir)},
        ]
        for index in (1, 2):
            name = f'project-delivery@{index}.service'
            rules.extend([rule(name, FragmentPath=service, Type='oneshot', UnitFileState='static',
                               Environment=f'ORBI_CONFIG={config}',
                               ExecStart=f'{{ path={bootstrap} ; argv[]={bootstrap} ; }}'),
                          rule(f'project-schedule@{index}.timer', FragmentPath=timer,
                               Unit=name, Triggers=name, UnitFileState='disabled')])
        self.h.rules(*rules)
        units, targets, jobs = helper.fleet_inventory(ctx, [manager])
        self.assertEqual(list(targets), [config])
        self.assertEqual(jobs, {manager: {}})
        self.assertFalse(any(call['argv'][-1].startswith('dormant@') for call in self.h.calls()))
        self.assertEqual({unit.name: unit.triggers for unit in units}, {
            'project-delivery@1.service': '', 'project-delivery@2.service': '',
            'project-schedule@1.timer': 'project-delivery@1.service',
            'project-schedule@2.timer': 'project-delivery@2.service',
        })
        self.assertTrue(all(call['argv'][2] in {'list-unit-files', 'list-units', 'list-jobs', 'show'}
                            for call in self.h.calls()))

    def configured_inventory(self, *, unrelated=0, dropins='', extra_templates=()):
        """Two configured Orbi slots (four units) plus unrelated services."""
        manager = helper.FleetManager('user', ('--user',), os.getuid(), self.h.home)
        target = self.h.root / 'checkout'
        target.mkdir(exist_ok=True)
        config = target / 'orbi.toml'
        config.write_text('source_repos = ["example/repo"]\nmax_concurrency = 2\n')
        bootstrap = self.h.home / '.local/bin/orbi'
        service = self.h.unit_dir / 'project-delivery@.service'
        timer = self.h.unit_dir / 'project-schedule@.timer'
        service.write_text(f'[Service]\nWorkingDirectory={target}\n'
                           f'Environment="ORBI_CONFIG={config}"\nExecStart={bootstrap}\n')
        timer.write_text('[Timer]\nUnit=project-delivery@%i.service\n[Install]\nWantedBy=timers.target\n')
        # A vendor unit with a systemd continuation.
        other = self.h.unit_dir / 'vendor-shell.service'
        other.write_text('[Service]\nExecStart=/usr/bin/tmux unbind-key -a; \\\n  new-session\n')
        for path in (service, timer, other):
            path.chmod(0o644)
        properties = dict(LoadState='loaded', ActiveState='inactive', NeedDaemonReload='no',
                          CanStart='yes', CanStop='yes', KillMode='control-group', SendSIGKILL='yes',
                          DynamicUser='no')

        def rule(name, **extra):
            values = {'Id': name, 'Names': name, **properties, **extra}
            return {'tool': 'systemctl', 'argv_contains': ['--user', 'show', name],
                    'stdout': '\n'.join(f'{k}={v}' for k, v in values.items())}

        unrelated_names = [f'vendor-{index}.service' for index in range(unrelated)]
        rules = [
            {'tool': 'systemctl', 'argv_contains': ['--user', 'list-units'], 'stdout': ''},
            {'tool': 'systemctl', 'argv_contains': ['--user', 'list-unit-files'],
             'stdout': f'{service.name} static -\n{timer.name} disabled enabled\n'
                       + ''.join(f'{name} static -\n' for name in (*unrelated_names, *extra_templates))},
            {'tool': 'systemctl', 'argv_contains': ['--user', 'show', 'UnitPath'], 'stdout': str(self.h.unit_dir)},
            *[rule(name, FragmentPath=other, Type='simple', UnitFileState='static', WorkingDirectory='/',
                   ExecStart='{ path=/usr/bin/tmux ; argv[]=/usr/bin/tmux unbind-key -a ; }')
              for name in unrelated_names],
        ]
        for index in (1, 2):
            name = f'project-delivery@{index}.service'
            rules.extend([rule(name, FragmentPath=service, DropInPaths=dropins, Type='oneshot',
                               UnitFileState='static', WorkingDirectory=target,
                               Requires='"app-project\\x2ddelivery.slice" basic.target',
                               Environment=f'ORBI_CONFIG={config}',
                               ExecStart=f'{{ path={bootstrap} ; argv[]={bootstrap} ; }}'),
                          rule(f'project-schedule@{index}.timer', FragmentPath=timer, WorkingDirectory=target,
                               Unit=name, Triggers=name, UnitFileState='disabled')])
        self.h.rules(*rules)
        ctx = helper.Context(env=self.h.env, platform='linux')
        return ctx, manager, config

    def test_inventory_skips_unrelated_service_templates_before_parsing(self):
        continued = self.h.unit_dir / 'vendor-shell@.service'
        continued.write_text('[Service]\nExecStart=/usr/bin/tmux unbind-key -a; \\\n  new-session\n')
        malformed = self.h.unit_dir / 'vendor-quoted@.service'
        malformed.write_text(f'[Service]\nExecStart=/bin/true "{SECRET}\n')
        ctx, manager, config = self.configured_inventory(extra_templates=(continued.name, malformed.name))
        units, targets, _ = helper.fleet_inventory(ctx, [manager])
        self.assertEqual(list(targets), [config])
        self.assertEqual({unit.name for unit in units}, {
            'project-delivery@1.service', 'project-delivery@2.service',
            'project-schedule@1.timer', 'project-schedule@2.timer',
        })
        malformed.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={SECRET}\n')
        with self.assertRaises(helper.ControlError) as caught:
            helper.fleet_inventory(ctx, [manager])
        self.assertEqual(caught.exception.message, 'user:vendor-quoted@.service: unit definition is unparsable')
        self.assertNotIn(SECRET, str(caught.exception))

    def test_inventory_bounds_orbi_detail_not_unrelated_units(self):
        ctx, manager, config = self.configured_inventory(unrelated=6)
        with mock.patch.object(helper, 'HOST_DETAIL_LIMIT', 4):
            units, targets, _ = helper.fleet_inventory(ctx, [manager])
        self.assertEqual(list(targets), [config])
        self.assertEqual(len(units), 4)
        with mock.patch.object(helper, 'HOST_DETAIL_LIMIT', 3), self.assertRaises(helper.ControlError) as caught:
            helper.fleet_inventory(ctx, [manager])
        self.assertIn('user: Orbi unit detail exceeds 3', str(caught.exception))
        with mock.patch.object(helper, 'FLEET_CLASSIFY_LIMIT', 5), self.assertRaises(helper.ControlError) as caught:
            helper.fleet_inventory(ctx, [manager])
        self.assertIn('user: installed/loaded units exceed 5', str(caught.exception))

    def test_inventory_accepts_a_benign_vendor_dropin_and_quoted_slice(self):
        vendor = self.h.root / 'vendor/service.d'
        vendor.mkdir(parents=True)
        dropin = vendor / '10-timeout-abort.conf'
        dropin.write_text('[Service]\nTimeoutStopFailureMode=abort\n')
        dropin.chmod(0o644)
        ctx, manager, config = self.configured_inventory(dropins=str(dropin))
        with mock.patch.object(helper, 'VENDOR_DROPIN_DIRS', (vendor,)), root_owned(dropin):
            units, targets, _ = helper.fleet_inventory(ctx, [manager])
        self.assertEqual(list(targets), [config])
        self.assertEqual(len(units), 4)
        # Without the vendor directory it is an ordinary, ambiguous override.
        with root_owned(dropin), self.assertRaises(helper.ControlError) as caught:
            helper.fleet_inventory(ctx, [manager])
        self.assertIn('drop-in overrides are ambiguous', str(caught.exception))

    def test_bound_unit_parses_quoted_dependencies(self):
        manager = helper.FleetManager('user', ('--user',), os.getuid(), self.h.home)
        values = dict(Id='w@1.service', LoadState='loaded', NeedDaemonReload='no', ActiveState='inactive',
                      CanStart='yes', CanStop='yes', KillMode='control-group', SendSIGKILL='yes',
                      Conflicts='shutdown.target')
        for requires, allowed in (('"app-w\\x2d1.slice" basic.target', True),
                                  ('"unrelated\\x2dservice.service"', False)):
            with self.subTest(requires=requires):
                def call():
                    helper.fleet_bound_unit(manager, 'w@1.service', self.h.root / 'orbi.toml',
                                            dict(values, Requires=requires), [])
                if allowed:
                    call()
                else:
                    with self.assertRaises(helper.ControlError):
                        call()

    def test_bound_unit_binding_ignores_dependency_order_after_daemon_reload(self):
        manager = helper.FleetManager('user', ('--user',), os.getuid(), self.h.home)
        values = dict(Id='w@1.service', LoadState='loaded', NeedDaemonReload='no', ActiveState='inactive',
                      CanStart='yes', CanStop='yes', KillMode='control-group', SendSIGKILL='yes',
                      Conflicts='shutdown.target', Wants='network-online.target')

        def bind(**extra):
            return helper.fleet_bound_unit(manager, 'w@1.service', self.h.root / 'orbi.toml',
                                           dict(values, **extra), []).binding

        # Observed on Fedora: `systemctl disable` of the timer reloads and reorders Requires.
        before = bind(Requires='"app-w\\x2d1.slice" basic.target')
        self.assertEqual(bind(Requires='basic.target "app-w\\x2d1.slice"'), before)
        self.assertNotEqual(bind(Requires='"app-w\\x2d1.slice"'), before)
        self.assertNotEqual(bind(Requires='"app-w\\x2d1.slice" basic.target', Wants=''), before)

    def test_recheck_ignores_unrelated_jobs_and_oneshot_worker_activity_only(self):
        user = helper.FleetManager('user', ('--user',), os.getuid(), self.h.home)
        system = helper.FleetManager('system', ('--system',), 0, Path('/root'))
        config = self.h.root / 'orbi.toml'

        def unit(manager, name, active='inactive', service_type='oneshot', triggers='', runner=False):
            return helper.FleetUnit(manager, name, config, ('binding',), active, 'static', triggers,
                                    runner=runner, service_type=service_type)

        plan = (unit(user, 'w@1.service'), unit(user, 'w@1.timer', 'active', '', 'w@1.service'),
                unit(user, 'p.service', 'active', 'simple'), unit(system, 's@1.service'),
                unit(user, 'x@1.service', service_type='simple', runner=True),
                unit(user, 'x@1.timer', 'active', '', 'x@1.service'))
        targets = {config: object()}
        jobs = {user: {}, system: {}}
        key = helper.fleet_recheck_key(plan, targets, jobs)
        same = (
            # The workers' own timers started them; unrelated units queued jobs.
            ((unit(user, 'w@1.service', 'activating'), *plan[1:4],
              unit(user, 'x@1.service', 'active', 'simple', runner=True), plan[5]),
             {user: {'7': ('w@1.service', 'start'), '8': ('observer.service', 'start')},
              system: {'9': ('watchdog.service', 'start')}}),
        )
        for units, live_jobs in same:
            self.assertEqual(helper.fleet_recheck_key(units, targets, live_jobs), key)
        changed = (
            # Timer activity decides restored scheduling.
            ((*plan[:1], unit(user, 'w@1.timer', 'inactive', '', 'w@1.service'), *plan[2:]), jobs),
            # A persistent (not timer-started) service decides its own restore.
            ((*plan[:2], unit(user, 'p.service', 'inactive', 'simple'), *plan[3:]), jobs),
            ((*plan[:2], unit(user, 'p.service', 'activating', 'simple'), *plan[3:]), jobs),
            # A new system-manager Orbi job changes the cancel permission.
            (plan, {user: {}, system: {'9': ('s@1.service', 'start')}}),
            # Changed binding or a missing unit.
            ((*plan[:3], helper.FleetUnit(system, 's@1.service', config, ('other',), 'inactive', 'static',
                                         service_type='oneshot'), *plan[4:]), jobs),
            ((*plan[:3], *plan[4:]), jobs),
        )
        for units, live_jobs in changed:
            with self.subTest(units=[u.name for u in units], jobs=live_jobs):
                self.assertNotEqual(helper.fleet_recheck_key(units, targets, live_jobs), key)

    def test_preflight_accepts_official_origin_after_ssh_insteadof_rewrite(self):
        target = mock.Mock(source_repos=['example/repo'], repo_dir=None, deploy_home=self.h.root,
                           config_path=self.h.root / 'orbi.toml')
        ctx = helper.Context(env=self.h.env, platform='linux')
        for remote, allowed in (('https://github.com/orbi-build/orbi', True),
                                ('https://github.com/orbi-build/orbi.git', True),
                                ('git@github.com:orbi-build/orbi', True),
                                ('git@github.com:orbi-build/orbi.git', True),
                                ('git@github.com:someone/orbi', False),
                                ('https://github.com/orbi-build/orbi-fork', False)):
            with self.subTest(remote=remote), \
                    mock.patch.object(helper, 'validate_deployment_paths'), \
                    mock.patch.object(helper, 'setup_file_identities'), \
                    mock.patch.object(helper, 'require_engine_checkout'), \
                    mock.patch.object(helper.os, 'access', return_value=False), \
                    mock.patch.object(ctx, 'run', return_value=subprocess.CompletedProcess([], 0, remote + '\n', '')):
                with self.assertRaises(helper.ControlError) as caught:
                    helper.fleet_preflight_target(ctx, target)
                # Accepted origins continue to the next check (writability here).
                expected = 'deployment files are not writable' if allowed else 'engine origin is not official'
                self.assertIn(expected, str(caught.exception))

    def test_benign_vendor_dropin_rules(self):
        vendor = self.h.root / 'vendor/service.d'
        vendor.mkdir(parents=True)
        cases = {
            'timeout.conf': ('# c\n[Service]\nTimeoutStopFailureMode=abort\nTimeoutStartFailureMode=kill\n', True),
            'exec.conf': ('[Service]\nExecStart=/bin/true\n', False),
            'env.conf': ('[Service]\nEnvironment=ORBI_CONFIG=/x\n', False),
            'unit.conf': ('[Unit]\nTimeoutStopFailureMode=abort\n', False),
            'continued.conf': ('[Service]\nTimeoutStopFailureMode=abort \\\n', False),
            'empty-key.conf': ('[Service]\nnot a directive\n', False),
        }
        paths = []
        for name, (text, _) in cases.items():
            (vendor / name).write_text(text)
            (vendor / name).chmod(0o644)
            paths.append(vendor / name)
        elsewhere = self.h.root / 'timeout.conf'
        elsewhere.write_text(cases['timeout.conf'][0])
        with mock.patch.object(helper, 'VENDOR_DROPIN_DIRS', (vendor,)):
            with root_owned(*paths, elsewhere):
                for name, (_, expected) in cases.items():
                    with self.subTest(name=name):
                        self.assertIs(helper.benign_vendor_dropin(vendor / name), expected)
                self.assertFalse(helper.benign_vendor_dropin(elsewhere))
            self.assertFalse(helper.benign_vendor_dropin(vendor / 'timeout.conf'))  # not root-owned
            (vendor / 'timeout.conf').chmod(0o664)
            with root_owned(*paths):
                self.assertFalse(helper.benign_vendor_dropin(vendor / 'timeout.conf'))  # group-writable
            self.assertFalse(helper.benign_vendor_dropin(vendor / 'missing.conf'))

    def test_unsupported_manager_platform_is_held_without_mutation(self):
        ctx = helper.Context(env=self.h.env, platform='freebsd')
        receipt = helper.installer_fleet(ctx)
        self.assertEqual(receipt['status'], 'held')
        self.assertIn('freebsd: no supported Orbi deployment manager', receipt['error']['message'])
        self.assertEqual(self.h.calls(), [])

    def test_macos_deployment_is_held_without_mutation(self):
        ctx = helper.Context(env=self.h.env, platform='darwin')
        config = self.h.root / 'orbi.toml'
        for inventory, subject in (([{'unit': 'dev.orbi.worker'}], 'dev.orbi.worker'), ([], str(config))):
            with self.subTest(subject=subject), mock.patch.object(
                    helper, 'host_darwin', return_value=(inventory, set() if inventory else {config})):
                receipt = helper.installer_fleet(ctx)
                self.assertEqual(receipt['status'], 'held')
                self.assertIn(subject, receipt['error']['message'])
                self.assertIn('no deployment upgraded', receipt['error']['message'])
        self.assertEqual(self.h.calls(), [])


class HostStatusTests(unittest.TestCase):
    """The public CLI is local/read-only, including outside a Git checkout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(Path(self.tmp.name))
        self.cwd = self.h.root / 'not-git'
        self.cwd.mkdir()

    def invoke(self, *flags, platform='linux', json_mode=True):
        out, err = io.StringIO(), io.StringIO()
        code = helper.main(['status', 'all', *flags, *(['--json'] if json_mode else [])],
                           env=self.h.env, cwd=self.cwd, platform=platform,
                           stdout=out, stderr=err)
        return code, json.loads(out.getvalue()) if json_mode else out.getvalue(), err.getvalue()

    def lists(self, manager, units=(), files=(), error=False):
        return [
            {'tool': 'systemctl', 'argv_contains': [manager, 'list-units'],
             'stdout': json.dumps(list(units)), 'exit': int(error)},
            {'tool': 'systemctl', 'argv_contains': [manager, 'list-unit-files'],
             'stdout': json.dumps(list(files)), 'exit': int(error)},
        ]

    def unit(self, name, state='inactive'):
        return {'unit': name, 'load': 'loaded', 'active': state, 'sub': 'dead'}

    def detail(self, manager, name, **values):
        return {'tool': 'systemctl', 'argv_contains': [manager, 'show', name],
                'stdout': '\n'.join(f'{key}={value}' for key, value in {'Id': name, **values}.items()) + '\n'}

    def assert_read_only(self, before, *, platform='linux'):
        self.assertEqual(snapshot(self.h.home), before)
        allowed = ('launchctl', 'gh') if platform == 'darwin' else ('systemctl', 'git', 'journalctl', 'gh')
        for call in self.h.calls():
            tool, argv = call['tool'], call['argv']
            self.assertIn(tool, allowed)
            if tool == 'gh':
                self.assertEqual(argv, ['api', 'rate_limit'])
            elif tool == 'systemctl':
                self.assertIn(argv[1], ('list-units', 'list-unit-files', 'show'))
            elif tool == 'git':
                self.assertTrue(any(part in argv for part in ('rev-parse', 'show', 'diff', 'symbolic-ref')))
            elif tool == 'launchctl':
                self.assertEqual(argv[0], 'print')
            else:
                self.assertIn('-n', argv)
                self.assertIn('100', argv)

    def test_two_managers_deployments_surplus_templates_orphan_and_prepared(self):
        a = self.h.add_deployment_a()
        second = self.h.data_home / 'not-kit-named'
        second.mkdir()
        config = second / 'orbi.toml'
        config.write_text(f'source_repos = ["second/project"]\ndeploy_home = "{second}"\n')
        manifest = '[project]\nname = "orbi"\nversion = "0.7.56"\n'
        (a['deploy'] / 'pyproject.toml').write_text(manifest)
        a['config'].write_text(a['config'].read_text().replace(OLD_PIN, PIN))
        service = self.h.unit_dir / 'bespoke@.service'
        service.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={config}"\nExecStart=/bin/orbi\n')
        prepared = self.h.data_home / 'prepared'
        prepared.mkdir()
        (prepared / 'orbi.toml').write_text('source_repos = ["prepared/repo"]\n')
        self.h.rules(
            *self.lists('--user', [self.unit('orbi-a@1.service'), self.unit('orbi-a@9.service', 'failed'),
                                   self.unit('orbi-a@1.timer', 'active'), self.unit('orbi-orphan@8.service', 'active')],
                        [{'unit_file': 'orbi-a@.service', 'state': 'disabled'},
                         {'unit_file': 'orbi-exporter.service', 'state': 'disabled'}]),
            *self.lists('--system', [self.unit('bespoke@1.service')]),
            self.detail('--user', 'orbi-a@1.service', FragmentPath=self.h.unit_dir / 'orbi-a@.service'),
            self.detail('--user', 'orbi-a@9.service', FragmentPath=self.h.unit_dir / 'orbi-a@.service'),
            self.detail('--user', 'orbi-a@1.timer', Unit='orbi-a@1.service', UnitFileState='enabled',
                        NextElapseUSecRealtime='Mon 2026-11-23 08:00:00 UTC'),
            self.detail('--system', 'bespoke@1.service', FragmentPath=service),
            {'tool': 'git', 'argv_contains': ['show', 'HEAD:pyproject.toml'], 'stdout': manifest},
        )
        before = snapshot(self.h.home)
        code, doc, _ = self.invoke()
        self.assertEqual(code, 0)
        rows = {(r['manager'], r['unit']): r for r in doc['rows'] if r['unit']}
        self.assertEqual(rows['user', 'orbi-a@1.service']['repo'], 'other/repo-a')
        self.assertEqual(rows['system', 'bespoke@1.service']['repo'], 'second/project')
        self.assertEqual(rows['system', 'bespoke@1.service']['state'], 'stopped')
        self.assertEqual(rows['user', 'orbi-a@1.service']['state'], 'idle')
        self.assertEqual(rows['user', 'orbi-a@1.service']['engine']['version'], '0.7.56')
        self.assertEqual(rows['user', 'orbi-a@9.service']['scheduler'], 'failed')
        self.assertEqual(rows['user', 'orbi-a@9.service']['worker']['state'], 'idle')
        self.assertEqual(rows['user', 'orbi-a@1.service']['next_trigger'], 'Mon 2026-11-23 08:00:00 UTC')
        self.assertEqual(rows['user', 'orbi-orphan@8.service']['worker']['state'], 'active/issue unknown')
        self.assertIsNone(rows['user', 'orbi-orphan@8.service']['repo'])
        self.assertEqual(rows['user', 'orbi-a@.service']['kind'], 'template')
        self.assertEqual(rows['user', 'orbi-exporter.service']['kind'], 'nonrunner')
        self.assertTrue(any(r['kind'] == 'config-only' and r['repo'] == 'prepared/repo' for r in doc['rows']))
        self.assertEqual(doc['totals']['observed_workers'], 4)
        self.assert_read_only(before)
        self.h.clear_calls()
        code, text, _ = self.invoke('--verbose', json_mode=False)
        self.assertEqual(code, 0)
        for token in ('Host Orbi', 'orbi-a@9.service', 'second/project', 'unknown', 'observed'):
            self.assertIn(token, text)
        self.assert_read_only(before)

    def test_compact_status_groups_13_slots_by_config_and_counts_non_orbi_failures(self):
        units, files, details = [], [], {}
        for index in range(7):
            deploy = self.h.data_home / f'delivery-{index}'
            deploy.mkdir()
            config = deploy / 'orbi.toml'
            count = 2 if index < 6 else 1
            # Two distinct deployments can target the same repository.
            provider = {0: 'example', 1: 'openai-codex', 2: 'openrouter'}.get(index, 'example')
            config.write_text(f'source_repos = ["owner/repo-{max(1, index)}"]\n'
                              f'max_concurrency = {count}\npi_provider = "{provider}"\n'
                              'pi_model = "model-id"\npi_thinking = "high"\n')
            template = self.h.unit_dir / f'delivery-{index}@.service'
            template.write_text(f'[Service]\nExecStart=/bin/orbi --config {config}\n')
            files.append({'unit_file': str(template), 'state': 'disabled'})
            for slot in range(1, count + 1):
                name = template.name.replace('@.', f'@{slot}.')
                units.append(self.unit(name, 'active' if index == 0 and slot == 1 else 'inactive'))
                details[name] = dict(FragmentPath=template)
                if index < 2:
                    timer = name.replace('.service', '.timer')
                    units.append(self.unit(timer, 'active'))
                    details[timer] = dict(Unit=name, NextElapseUSecRealtime=(
                        'Sun 2026-11-22 08:00:00 UTC' if slot == 1 else 'Mon 2026-11-23 08:00:00 UTC'))
        for name in ('getty@.service', 'example@.timer'):
            path = self.h.unit_dir / name
            path.write_text('[Unit]\nDescription=Unrelated template\n')
            files.append({'unit_file': str(path), 'state': 'disabled'})
        units.extend(self.unit(f'vendor-{index}.service') for index in range(58))
        show = []
        budget_calls = []
        budget = {'resources': {'core': {'limit': 5000, 'remaining': 4711, 'reset': 1795672327},
                                'graphql': {'limit': 5000, 'remaining': 0, 'reset': 1795672553}}}

        def fake_run(ctx, argv, **kwargs):
            if argv[0] == 'gh':
                self.assertEqual(argv, ['gh', 'api', 'rate_limit'])
                budget_calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, json.dumps(budget), '')
            if argv[:2] == ['systemctl', '--user']:
                if argv[2] == 'list-units':
                    return subprocess.CompletedProcess(argv, 0, json.dumps(units), '')
                if argv[2] == 'list-unit-files':
                    return subprocess.CompletedProcess(argv, 0, json.dumps(files), '')
                self.assertEqual(argv[2], 'show')
                name = argv[3]
                show.append(name)
                if name in details:
                    return subprocess.CompletedProcess(argv, 0, self.detail('--user', name, **details[name])['stdout'], '')
                return subprocess.CompletedProcess(argv, 1, '', 'not readable ' + SECRET)
            self.assertIn(argv[:2], (['systemctl', '--system'], ['git', '-C']))
            return subprocess.CompletedProcess(argv, 0, '[]', '')

        with mock.patch.object(helper.Context, 'run', fake_run), mock.patch.object(
                helper, 'host_definition_dirs', return_value=[]):
            code, text, err = self.invoke(json_mode=False)
            self.assertEqual(code, 0, err)
            _, verbose, _ = self.invoke('--verbose', json_mode=False)
            _, doc, _ = self.invoke()
        data = [line for line in text.splitlines() if 'slots=' in line]
        self.assertEqual(len(data), 7)
        self.assertEqual(sum('owner/repo-1' in line for line in data), 2)
        self.assertLessEqual(len(text.splitlines()), 10)
        self.assertIn('openrouter/model-id/high (metered)', text)
        self.assertIn('openrouter/model-id (metered)', verbose)
        self.assertNotIn('openai-codex/model-id/high (metered)', text)
        self.assertFalse(next(r for r in doc['rows'] if r.get('provider') == 'openai-codex')['metered'])
        self.assertTrue(next(r for r in doc['rows'] if r.get('provider') == 'openrouter')['metered'])
        self.assertEqual(len(budget_calls), 3)  # one per invocation, never an issue list
        for output in (text, verbose):
            self.assertIn('GraphQL 0/5000 (resets 2026-11-26T05:55:53Z)', output)
            self.assertIn('REST 4711/5000 (resets 2026-11-26T05:52:07Z)', output)
        self.assertEqual(doc['github_budget']['rest']['remaining'], 4711)
        self.assertNotIn('work', doc)
        for token in ('slots=1/2', 'example/model-id/high', 'state=running', 'issues=unknown',
                      'next=Sun 2026-11-22 08:00:00 UTC', 'state=idle', 'state=stopped'):
            self.assertIn(token, text)
        self.assertIn('coverage partial: 58 non-Orbi units unreadable (--verbose to list)', text)
        self.assertNotIn('vendor-0.service', text)
        self.assertNotIn(SECRET, text + verbose + json.dumps(doc))
        self.assertIn('unit details failed: vendor-0.service', verbose)
        self.assertIn('delivery-0@.service', verbose)
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertEqual(len(doc['coverage']['problems']), 58)
        self.assertEqual(doc['totals']['observed_workers'], 13)
        self.assertEqual(sum(r['kind'] == 'template' for r in doc['rows']), 7)
        self.assertEqual(sum(r['kind'] == 'runner' for r in doc['rows']), 13)
        row = next(r for r in doc['rows'] if r['unit'] == 'delivery-0@1.service')
        self.assertEqual((row['provider'], row['model'], row['thinking'], row['max_concurrency']),
                         ('example', 'model-id', 'high', 2))
        self.assertFalse(any('@.' in name for name in show))

    def test_github_work_lists_each_repo_once_and_never_advises_on_unknown(self):
        units, details = [], []
        for name, repo, worker_state, timer_state in (
                ('idle', 'owner/empty', 'inactive', 'active'),
                ('stopped', 'Owner/Empty', 'inactive', 'inactive'),
                ('running', 'owner/ready', 'active', 'active'),
                ('unavailable', 'owner/denied', 'active', 'active')):
            folder = self.h.data_home / name
            folder.mkdir()
            config = folder / 'orbi.toml'
            config.write_text(f'source_repos = ["{repo}"]\n')
            template = self.h.unit_dir / f'orbi-{name}@.service'
            template.write_text(f'[Service]\nExecStart=/bin/orbi --config {config}\n')
            service, timer = f'orbi-{name}@1.service', f'orbi-{name}@1.timer'
            units.extend((self.unit(service, worker_state), self.unit(timer, timer_state)))
            details.extend((self.detail('--user', service, FragmentPath=template),
                            self.detail('--user', timer, Unit=service)))
        self.h.rules(*self.lists('--user', units), *self.lists('--system'), *details)
        original = helper.Context.run
        calls = []

        def fake_run(ctx, argv, *, timeout=helper.PROBE_TIMEOUT, **kwargs):
            if argv[0] != 'gh':
                return original(ctx, argv, timeout=timeout, **kwargs)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 20)
            calls.append(argv)
            if argv == ['gh', 'api', 'rate_limit']:
                raise helper.ControlError('command_timeout', SECRET, fix='')
            self.assertEqual(argv[:3], ['gh', 'issue', 'list'])
            for option, value in (('--state', 'open'), ('--json', 'number'),
                                  ('--search', 'label:ai-ready,ai-fix-needed')):
                self.assertEqual(argv[argv.index(option) + 1], value)
            repo = argv[argv.index('--repo') + 1]
            if repo == 'owner/denied':
                return subprocess.CompletedProcess(argv, 1, '[]', SECRET)
            numbers = [{'number': 41}, {'number': 42}] if repo == 'owner/ready' else []
            return subprocess.CompletedProcess(argv, 0, json.dumps(numbers), '')

        before = snapshot(self.h.home)
        suggestion = 'no work: consider /orbi stop owner/empty or set owner/empty slots 1'
        with mock.patch.object(helper.Context, 'run', fake_run):
            for flags, json_mode in (([], True), ([], False), (['--verbose'], False)):
                with self.subTest(flags=flags, json_mode=json_mode):
                    calls.clear()
                    code, result, err = self.invoke('--work', *flags, json_mode=json_mode)
                    self.assertEqual(code, 0, err)
                    self.assertNotIn(SECRET, str(result) + err)
                    self.assertEqual(sum(call[1:3] == ['api', 'rate_limit'] for call in calls), 1)
                    self.assertEqual(calls[-1], ['gh', 'api', 'rate_limit'])
                    self.assertCountEqual([call[call.index('--repo') + 1] for call in calls
                                           if call[1] == 'issue'],
                                          ['owner/empty', 'owner/ready', 'owner/denied'])
                    if json_mode:
                        self.assertEqual(result['github_budget'], {'graphql': None, 'rest': None})
                        self.assertEqual(result['work'], {'owner/empty': 0, 'Owner/Empty': 0,
                                                          'owner/ready': 2, 'owner/denied': None})
                        self.assertEqual(result['suggestions'], [suggestion])
                    else:
                        self.assertIn('GraphQL unknown; REST unknown', result)
                        self.assertIn('check gh auth status', result)
                        self.assertEqual([line for line in result.splitlines() if line.startswith('no work:')],
                                         [suggestion])
        self.assert_read_only(before)

    def test_github_work_cli_success_and_unavailable(self):
        self.h.add_deployment_a()
        unit = 'orbi-a@1.service'
        for failure in (False, True):
            with self.subTest(failure=failure):
                self.h.clear_calls()
                self.h.rules(*self.lists('--user', [self.unit(unit, 'active')]), *self.lists('--system'),
                             self.detail('--user', unit, FragmentPath=self.h.unit_dir / 'orbi-a@.service'),
                             {'tool': 'gh', 'argv_contains': ['api', 'rate_limit'],
                              'stdout': '{"resources":{"core":{"limit":60,"remaining":18,"reset":1795672327}}}'},
                             {'tool': 'gh', 'argv_contains': ['issue', 'list', 'other/repo-a'],
                              'stdout': SECRET if failure else '[]'})
                proc = subprocess.run([sys.executable, '-B', str(HELPER), 'status', 'all', '--work'],
                                      cwd=self.cwd, env=self.h.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn('GraphQL unknown; REST 18/60', proc.stdout)
                self.assertIn('other/repo-a slots=1/2', proc.stdout)
                self.assertIn('work=unknown' if failure else 'work=0', proc.stdout)
                self.assertEqual('no work: consider /orbi stop other/repo-a or set other/repo-a slots 1'
                                 in proc.stdout, not failure)
                self.assertNotIn(SECRET, proc.stdout + proc.stderr)

    def test_template_config_specifier_is_only_resolved_for_the_instance(self):
        config = self.h.root / 'worker-17' / 'native.toml'
        config.parent.mkdir()
        config.write_text('source_repos = ["native/repo"]\n')
        template = self.h.unit_dir / 'delivery@.service'
        unit = 'delivery@17.service'
        listings = {'list-units': [self.unit(unit)],
                    'list-unit-files': [{'unit_file': template.name, 'state': 'enabled'}]}

        def fake_run(ctx, argv, **kwargs):
            if argv[:3] == ['systemctl', '--user', 'show']:
                self.assertEqual(argv[3], unit)
                return subprocess.CompletedProcess(
                    argv, 0, f'Id={unit}\nFragmentPath={template}\nWorkingDirectory={config.parent}\n', '')
            if argv[:2] == ['systemctl', '--user']:
                return subprocess.CompletedProcess(argv, 0, json.dumps(listings[argv[2]]), '')
            return subprocess.CompletedProcess(argv, 0, '[]', '')

        for directive in (f'ExecStart=/bin/orbi --config {self.h.root}/worker-%i/native.toml',
                          f'WorkingDirectory={self.h.root}/worker-%i\nExecStart=/bin/orbi --config native.toml'):
            with self.subTest(directive=directive):
                template.write_text(f'[Service]\n{directive}\n')
                with (
                    mock.patch.object(helper.Context, 'run', fake_run),
                    mock.patch.object(helper, 'host_definition_dirs',
                                      side_effect=lambda ctx, manager: [self.h.unit_dir] if manager == 'user' else []),
                ):
                    _, doc, _ = self.invoke()
                rows = {row['unit']: row for row in doc['rows']}
                self.assertEqual(rows[unit]['repo'], 'native/repo')
                self.assertEqual(rows[template.name]['kind'], 'template')
                self.assertEqual(doc['coverage']['state'], 'ok', doc['coverage']['problems'])

    def test_missing_template_fragment_is_partial_without_querying_template_runtime(self):
        unit = 'vendor@.service'
        self.h.rules(*self.lists('--user', [], [{'unit_file': unit, 'state': 'disabled'},
                                               {'unit_file': 'masked@.timer', 'state': 'masked'}]),
                     *self.lists('--system'))
        with mock.patch.object(helper, 'host_definition_dirs', return_value=[]):
            code, doc, err = self.invoke()
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertEqual([p['reason'] for p in doc['coverage']['problems']],
                         [f'template fragment unreadable: {unit}'])
        self.assertFalse(any(call['argv'][1] == 'show' for call in self.h.calls()
                             if call['tool'] == 'systemctl'))

    def test_active_worker_falls_back_to_live_slot_then_worktree_branch(self):
        a = self.h.add_deployment_a()
        repo = self.h.root / 'repo-a'
        worktree = repo / '.worktrees' / 'live-branch-checkout'
        nested = worktree / 'src' / 'package'
        nested.mkdir(parents=True)
        (worktree / '.git').write_text('gitdir: ../linked-worktree-metadata\n')
        unit, pid = 'orbi-a@17.service', '222'
        proc = self.h.root / 'proc'
        main = proc / pid
        (main / 'fd').mkdir(parents=True)
        (main / 'fdinfo').mkdir()
        child = proc / '333'
        child.mkdir()
        (child / 'cwd').symlink_to(nested)
        slots = repo / '.orbi/slots'
        slots.mkdir(parents=True)
        slot = slots / 'slot-1'
        slot.write_text(f'{pid}\nother/repo-a#42\n')
        (main / 'fd/5').symlink_to(slot)
        fdinfo = main / 'fdinfo/5'
        fdinfo.write_text(f'lock:\t1: FLOCK ADVISORY WRITE {pid} 00:27:1234 0 EOF\n')
        cgroups = self.h.root / 'cgroups'
        group = cgroups / 'pool.slice' / unit
        group.mkdir(parents=True)
        (group / 'cgroup.procs').write_text(f'{pid}\n333\n')
        props = dict(ActiveState='active', MainPID=pid, InvocationID='c' * 32,
                     WorkingDirectory=a['deploy'], FragmentPath=self.h.unit_dir / 'orbi-a@.service',
                     ControlGroup=f'/pool.slice/{unit}')
        self.h.rules(*self.lists('--system'), *self.lists('--user', [self.unit(unit, 'active')]),
                     self.detail('--user', unit, **props),
                     {'tool': 'git', 'argv_contains': [str(worktree), 'symbolic-ref', '--quiet', 'HEAD'],
                      'stdout': 'refs/heads/orbi/other-repo-a-issue-308\n'})
        before = snapshot(self.h.home)
        with mock.patch.object(helper, 'HOST_PROC', proc), mock.patch.object(
                helper, 'HOST_CGROUP', cgroups):
            _, bound, _ = self.invoke()
            fdinfo.unlink()  # An unlocked record is not evidence, even with the same PID.
            _, text, _ = self.invoke(json_mode=False)
            _, branch, _ = self.invoke()
            # Losing the manager during the optional binding recheck must not
            # suppress the inventory or claim a now-unconfirmed issue.
            with mock.patch.object(helper, 'service_binding', side_effect=PermissionError):
                code, denied, err = self.invoke()
            self.assertEqual(code, 0, err)
            (group / 'cgroup.procs').write_text(f'{pid}\n')
            _, stale, _ = self.invoke()
        self.assertIn('issues=#308', text)
        for doc, number in ((bound, 42), (branch, 308), (denied, None), (stale, None)):
            worker = next(r['worker'] for r in doc['rows'] if r['unit'] == unit)
            self.assertEqual(worker.get('issue', {}).get('number'), number)
            self.assertEqual(worker['state'], 'active/issue unknown' if number is None else 'running')
        self.assert_read_only(before)

    def test_worker_kind_uses_execution_evidence_and_inactive_timer_is_stopped(self):
        config = self.h.root / 'native.toml'
        config.write_text('source_repos = ["native/repo"]\n')
        names = ('orbi-metrics@1.service', 'delivery.service', 'orbi@9.service', 'orbi@9.timer')
        commands = ('/usr/bin/python3 /opt/orbi-exporter.py', '/usr/bin/python3 -m orbi.runner', '/bin/orbi')
        for name, command in zip(names, commands):
            (self.h.unit_dir / name).write_text(
                f'[Service]\nEnvironment="ORBI_CONFIG={config}"\nExecStart={command}\n')
        self.h.rules(*self.lists('--user', [self.unit(n) for n in names]), *self.lists('--system'),
                     *(self.detail('--user', n, FragmentPath=self.h.unit_dir / n) for n in names[:3]),
                     self.detail('--user', names[3], ActiveState='inactive', Unit=names[2], UnitFileState='enabled'))
        before = snapshot(self.h.home)
        _, doc, _ = self.invoke()
        rows = {r['unit']: r for r in doc['rows'] if r['unit']}
        self.assertEqual(rows[names[0]]['kind'], 'nonrunner')
        self.assertEqual(rows[names[0]]['worker']['state'], 'not a worker')
        self.assertEqual(rows[names[1]]['kind'], 'runner')
        self.assertEqual(rows[names[2]]['state'], 'stopped')
        self.assertEqual(doc['totals']['observed_workers'], 2)
        self.assert_read_only(before)

    def test_unit_definition_continuations_match_single_line_directives(self):
        ctx = helper.Context(env=self.h.env, platform='linux')
        service = self.h.unit_dir / 'delivery.service'
        service.write_text(f'[Service]\nWorkingDirectory={self.h.root}\n'
                           'Environment="ORBI_CONFIG=env.toml" PRIVATE=hidden\n'
                           'ExecStart=/bin/orbi --config cli.toml\n')
        expected = helper.host_definition(ctx, service)
        self.assertEqual(expected['configs'], [str(self.h.root / name) for name in ('cli.toml', 'env.toml')])
        self.assertTrue(expected['orbi'] and expected['runner'])
        service.write_text(f'[Service]\r\nWorkingDirectory=\\\r\n  {self.h.root}\r\n'
                           'Environment=PRIVATE=hidden\\\r\n  "ORBI_CONFIG=env.toml"\r\n'
                           'ExecStart=/bin/orbi\\\r\n  # skipped comment\r\n; also skipped\r\n'
                           '  --config\\\r\n  cli.toml\r\n')
        self.assertEqual(helper.host_definition(ctx, service), expected)

    def test_unit_definition_doubled_backslash_does_not_continue_and_eof_can(self):
        ctx = helper.Context(env=self.h.env, platform='linux')
        service = self.h.unit_dir / 'delivery.service'
        config = self.h.root / 'delivery.toml'
        service.write_text('[Service]\nEnvironment=PRIVATE=path' + '\\' * 2 + '\n'
                           f'ExecStart=/bin/orbi --config {config} ' + '\\')
        definition = helper.host_definition(ctx, service)
        self.assertTrue(definition['orbi'] and definition['runner'])
        self.assertEqual(definition['configs'], [str(config)])

    def test_status_all_reports_unparsable_definition_without_private_text(self):
        service = self.h.unit_dir / 'delivery.service'
        service.write_text(f'[Service]\nExecStart=/bin/orbi \\\n  --config "{SECRET}\n')
        self.h.rules(*self.lists('--user', [self.unit(service.name)]), *self.lists('--system'),
                     self.detail('--user', service.name, FragmentPath=service))
        code, text, err = self.invoke(json_mode=False)
        self.assertEqual(code, 0, err)
        self.assertIn('coverage=partial', text)
        self.assertIn('coverage partial: user:delivery.service: unit definition is unparsable', text)
        self.assertNotIn(SECRET, text + err)
        self.assertNotIn('No closing quotation', text + err)

    def test_installed_arbitrary_name_outside_default_definition_roots_is_discovered(self):
        config = self.h.root / 'native.toml'
        config.write_text('source_repos = ["native/repo"]\n')
        definition = self.h.root / 'vendor-delivery.service'
        definition.write_text(f'[Service]\nExecStart=/bin/orbi \\\n  --config {config}\n')
        self.h.rules(*self.lists('--user', files=[{'unit_file': definition.name, 'state': 'disabled'}]),
                     *self.lists('--system'),
                     self.detail('--user', definition.name, FragmentPath=definition, LoadState='loaded'))
        before = snapshot(self.h.home)
        _, doc, _ = self.invoke()
        row = next(r for r in doc['rows'] if r['unit'] == definition.name)
        self.assertEqual(row['repo'], 'native/repo')
        self.assertEqual(row['kind'], 'runner')
        self.assertTrue(row['installed'])
        self.assertFalse(row['loaded'])
        self.assertEqual(doc['totals']['observed_workers'], 0)
        self.assert_read_only(before)

    def test_denied_arbitrary_unit_detail_keeps_healthy_rows_with_partial_coverage(self):
        self.h.rules(*self.lists('--user', [self.unit('orbi@1.service'), self.unit('vendor.service')]),
                     *self.lists('--system'), self.detail('--user', 'orbi@1.service'),
                     {'tool': 'systemctl', 'argv_contains': ['show', 'vendor.service'],
                      'exit': 1, 'stderr': 'Access denied ' + SECRET})
        before = snapshot(self.h.home)
        _, doc, _ = self.invoke()
        self.assertTrue(any(r['unit'] == 'orbi@1.service' for r in doc['rows']))
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertTrue(any('unit details denied: vendor.service' == p['reason']
                            for p in doc['coverage']['problems']))
        self.assertNotIn(SECRET, json.dumps(doc))
        self.assert_read_only(before)

    def test_compact_status_does_not_call_unattributed_active_deployment_stopped(self):
        self.h.add_deployment_a()
        unit = 'orbi-a@1.service'
        self.h.rules(*self.lists('--user', [self.unit(unit, 'active')]), *self.lists('--system'),
                     {'tool': 'systemctl', 'argv_contains': ['--user', 'show', unit], 'exit': 1})
        code, text, err = self.invoke(json_mode=False)
        self.assertEqual(code, 0, err)
        self.assertIn('workers without a config: 1 (--verbose to list)', text)
        row = next(line for line in text.splitlines() if line.startswith('other/repo-a '))
        self.assertIn('state=unknown', row)
        self.assertIn('unit details failed: orbi-a@1.service', text)

    def test_broken_config_resolution_does_not_discard_healthy_rows(self):
        config = self.h.root / 'loop.toml'
        config.symlink_to(config.name)
        definition = self.h.unit_dir / 'orbi@2.service'
        definition.write_text(f'[Service]\nExecStart=/bin/orbi --config {config}\n')
        self.h.rules(*self.lists('--user', [self.unit('orbi@1.service'), self.unit(definition.name)]),
                     *self.lists('--system'), self.detail('--user', 'orbi@1.service'),
                     self.detail('--user', definition.name, FragmentPath=definition))
        before = snapshot(self.h.home)
        code, doc, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertTrue(any(r['unit'] == 'orbi@1.service' for r in doc['rows']))
        row = next(r for r in doc['rows'] if r['unit'] == definition.name)
        self.assertEqual(row['binding']['state'], 'unreadable')
        self.assert_read_only(before)

    def test_config_directory_enumeration_denial_is_not_an_empty_discovery(self):
        self.h.rules(*self.lists('--user'), *self.lists('--system'))
        original = helper.Path.iterdir

        def denied(path):
            if path == self.h.data_home:
                raise PermissionError('private discovery detail')
            return original(path)

        with mock.patch.object(helper.Path, 'iterdir', denied):
            _, doc, _ = self.invoke()
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertTrue(any('deployment config discovery unreadable' in p['reason']
                            for p in doc['coverage']['problems']))
        self.assertNotIn('private discovery detail', json.dumps(doc))

    def test_system_home_specifier_does_not_bind_to_invoking_users_config(self):
        config = self.h.home / 'orbi.toml'
        config.write_text('source_repos = ["not/system"]\n')
        definition = self.h.unit_dir / 'orbi@30.service'
        definition.write_text('[Service]\nEnvironment="ORBI_CONFIG=%h/orbi.toml"\nExecStart=/bin/orbi\n')
        self.h.rules(*self.lists('--user'), *self.lists('--system', [self.unit(definition.name)]),
                     self.detail('--system', definition.name, FragmentPath=definition))
        _, doc, _ = self.invoke()
        row = next(r for r in doc['rows'] if r['unit'] == definition.name and r['manager'] == 'system')
        self.assertIsNone(row['repo'])
        self.assertNotEqual(row['binding']['state'], 'verified')

    def test_macos_custom_plist_config_selector_resolves_from_working_directory(self):
        import plistlib
        folder = self.h.home / 'Library/LaunchAgents'
        folder.mkdir(parents=True)
        config = self.h.root / 'native.toml'
        config.write_text('source_repos = ["native/repo"]\n')
        label = 'vendor.delivery'
        definition = folder / 'vendor.plist'
        definition.write_bytes(plistlib.dumps({'Label': label, 'WorkingDirectory': str(self.h.root),
            'ProgramArguments': ['/bin/orbi', '--config', 'native.toml']}))
        domain = f'gui/{os.getuid()}'
        for loaded in (False, True):
            with self.subTest(loaded=loaded):
                self.h.rules(
                    {'tool': 'launchctl', 'argv_contains': ['print', domain + '/' + label],
                     'exit': 0 if loaded else 113,
                     'stdout': f'path = {definition}\nstate = running\n' if loaded else ''},
                    {'tool': 'launchctl', 'argv_contains': ['print', domain],
                     'stdout': 'services = {\n' + (f'123 0 {label}\n' if loaded else '') + '}\n'},
                    {'tool': 'launchctl', 'argv_contains': ['print'], 'stdout': 'services = {\n}\n'})
                before = snapshot(self.h.home)
                _, doc, _ = self.invoke(platform='darwin')
                row = next(r for r in doc['rows'] if r['unit'] == label)
                self.assertEqual(row['binding']['config'], str(config))
                self.assertEqual(row['repo'], 'native/repo')
                self.assertEqual(row['kind'], 'runner')
                self.assertEqual(row['loaded'], loaded)
                self.assertEqual(snapshot(self.h.home), before)

    def test_partial_denied_manager_keeps_healthy_and_unreadable_config(self):
        bad = self.h.data_home / 'broken'
        bad.mkdir()
        (bad / 'orbi.toml').write_text('source_repos = [')
        self.h.rules(*self.lists('--user', [self.unit('orbi@12.service')]),
                     *self.lists('--system', error=True))
        before = snapshot(self.h.home)
        code, doc, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertEqual(doc['coverage']['managers']['system']['state'], 'unavailable')
        self.assertEqual(doc['totals']['observed_workers'], 1)
        self.assertTrue(any(r['binding']['state'] == 'unreadable' for r in doc['rows']))
        self.assertIn('read', doc['coverage']['managers']['system']['fix'])
        self.assert_read_only(before)
        self.h.rules(*self.lists('--user', [self.unit('orbi@12.service')]),
                     {'tool': 'systemctl', 'argv_contains': ['--system'], 'exit': 1,
                      'stderr': 'Access denied ' + SECRET})
        _, doc, _ = self.invoke()
        self.assertEqual(doc['coverage']['managers']['system']['state'], 'denied')
        self.assertNotIn(SECRET, json.dumps(doc))

    def test_successful_empty_is_zero_observed_not_absolute_host_total(self):
        self.h.rules(*self.lists('--user'), *self.lists('--system'))
        code, doc, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(doc['rows'], [])
        self.assertEqual(doc['totals']['observed_workers'], 0)
        self.assertEqual(doc['coverage']['state'], 'ok')
        self.assertIn('other users', doc['coverage']['scope'])
        self.assertNotIn('host_total', doc['totals'])

    def test_quoted_config_paths_do_not_require_orbi_unit_naming(self):
        deploy = self.h.root / 'deployment with spaces'
        deploy.mkdir()
        config = deploy / 'orbi.toml'
        config.write_text('source_repos = ["quoted/project"]\n')
        service = self.h.unit_dir / 'bespoke@1.service'
        for directive in (f'Environment="ORBI_CONFIG={config}"',
                          f'ExecStart="/bin/orbi" --config "{config}"'):
            with self.subTest(directive=directive):
                service.write_text('[Service]\n' + directive + '\n')
                self.h.rules(*self.lists('--user', [self.unit(service.name)]), *self.lists('--system'),
                             self.detail('--user', service.name, FragmentPath=service))
                _, doc, _ = self.invoke()
                row = next(r for r in doc['rows'] if r['unit'] == service.name)
                self.assertEqual(row['repo'], 'quoted/project')
                self.assertEqual(row['binding']['config'], str(config))

    def test_failed_config_discovery_does_not_discard_scheduler_rows(self):
        self.h.rules(*self.lists('--user', [self.unit('orbi@21.service')]), *self.lists('--system'))
        original = helper.Path.is_dir

        def denied(path):
            if path == self.h.data_home:
                raise PermissionError('do not echo private evidence')
            return original(path)

        with mock.patch.object(helper.Path, 'is_dir', denied):
            code, doc, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertTrue(any(r['unit'] == 'orbi@21.service' for r in doc['rows']))
        self.assertNotIn('do not echo', json.dumps(doc))

    def test_help_advertises_literal_host_mode_and_rejects_all_on_mutations(self):
        out = io.StringIO()
        helper.main(['help', '--json'], stdout=out)
        help_doc = json.loads(out.getvalue())
        self.assertTrue(any(e['command'] == '/orbi status all --json' for e in help_doc['examples']))
        self.assertIn('status all', help_doc['actions']['status']['effect'])
        self.assertEqual(help_doc['options']['--work']['applies_to'], ['status'])
        for action in ('setup', 'start', 'stop', 'update'):
            with self.subTest(action=action):
                out = io.StringIO()
                code = helper.main([action, 'all', '--json'], stdout=out, env=self.h.env)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(out.getvalue())['error']['code'], 'invalid_host_selection')
        self.assertEqual(self.h.calls(), [])

    def test_conflicting_selectors_refuse_before_any_probe(self):
        for flags in (['--repo-dir', str(self.cwd)], ['--config', '/missing'], ['--dry-run'],
                      ['--stop'], ['--resume-setup'], ['--harness', 'pi'], ['--pi-provider', 'secret']):
            with self.subTest(flags=flags):
                code, doc, _ = self.invoke(*flags)
                self.assertEqual(code, 2)
                self.assertEqual(doc['error']['code'], 'invalid_host_selection')
                self.assertIn('status all', doc['error']['fix'])
                self.assertEqual(self.h.calls(), [])

    def test_conflicting_config_bindings_never_attribute_repo(self):
        a = self.h.add_deployment_a()
        other = self.h.data_home / 'another.toml'
        other.write_text('source_repos = ["wrong/repo"]\n')
        definition = self.h.unit_dir / 'orbi-a@.service'
        definition.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={a["config"]}"\n'
                              f'Environment="ORBI_CONFIG={other}"\n')
        self.h.rules(*self.lists('--user', [self.unit('orbi-a@1.service', 'active')]),
                     *self.lists('--system'),
                     self.detail('--user', 'orbi-a@1.service', FragmentPath=definition))
        _, doc, _ = self.invoke()
        row = next(r for r in doc['rows'] if r['unit'] == 'orbi-a@1.service')
        self.assertEqual(row['binding']['state'], 'conflicting')
        self.assertIsNone(row['repo'])
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertNotIn(SECRET, json.dumps(doc))

    def test_real_cli_from_non_git_cwd_needs_no_github_or_global_checkout(self):
        self.h.rules(*self.lists('--user'), *self.lists('--system'))
        (self.cwd / 'orbi.toml').write_text('source_repos = ["prepared/project"]\nmax_concurrency = 3\n')
        before = snapshot(self.h.home)
        for flags in ([], ['--verbose'], ['--json']):
            with self.subTest(flags=flags):
                proc = subprocess.run([sys.executable, '-B', str(HELPER), 'status', 'all', *flags],
                                      cwd=self.cwd, env=self.h.env, capture_output=True, text=True, timeout=30)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                if not flags:
                    self.assertIn('prepared/project slots=0/3', proc.stdout)
                    self.assertIn('state=stopped issues=-', proc.stdout)
                elif flags == ['--verbose']:
                    self.assertIn('repo=prepared/project', proc.stdout)
                    self.assertIn('state=prepared-only', proc.stdout)
                else:
                    self.assertEqual(json.loads(proc.stdout)['totals']['observed_workers'], 0)
        calls_before = self.h.calls()
        failure = subprocess.run([sys.executable, '-B', str(HELPER), 'status', 'all', '--config', '/missing'],
                                 cwd=self.cwd, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(failure.returncode, 2)
        self.assertIn('error=invalid_host_selection', failure.stderr)
        self.assertIn('fix=use /orbi status all without selectors', failure.stderr)
        failure = subprocess.run([sys.executable, '-B', str(HELPER), 'status', '--verbose'],
                                 cwd=self.cwd, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(failure.returncode, 2)
        self.assertIn('--verbose requires status all', failure.stderr)
        failure = subprocess.run([sys.executable, '-B', str(HELPER), 'status', '--work'],
                                 cwd=self.cwd, env=self.h.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(failure.returncode, 2)
        self.assertIn('--work requires status all', failure.stderr)
        self.assertIn('fix=use /orbi status all --work', failure.stderr)
        self.assertEqual(self.h.calls(), calls_before)
        self.assert_read_only(before)

    def test_current_issue_binds_to_system_manager_invocation_without_issue_lookup(self):
        a = self.h.add_deployment_a()
        unit = 'orbi-a@17.service'
        invocation, pid, run = 'c' * 32, '222', '1234abcd'
        props = dict(ActiveState='active', MainPID=pid, InvocationID=invocation,
                     WorkingDirectory=a['deploy'], FragmentPath=self.h.unit_dir / 'orbi-a@.service')
        scene = {'MESSAGE': f'INFO [{run}] run_start issue=other/repo-a#42 run={run} phase=implement',
                 '_PID': pid, '_SYSTEMD_INVOCATION_ID': invocation}
        self.h.rules(*self.lists('--user'), *self.lists('--system', [self.unit(unit, 'active')]),
                     self.detail('--system', unit, **props),
                     {'tool': 'journalctl', 'argv_contains': ['--system', unit],
                      'stdout': json.dumps(scene) + '\n'})
        before = snapshot(self.h.home)
        reads = []
        original = helper.bounded_bytes

        def capture(path, *args):
            reads.append(str(path))
            return original(path, *args)

        with mock.patch.object(helper, 'bounded_bytes', side_effect=capture):
            code, doc, _ = self.invoke()
        self.assertEqual(code, 0)
        row = next(r for r in doc['rows'] if r['unit'] == unit)
        self.assertEqual(row['worker']['issue']['number'], 42)
        self.assertEqual(row['worker']['run_id'], run)
        self.assertEqual(row['repo'], 'other/repo-a')
        for path in reads:
            self.assertNotIn('/.orbi/', path)  # no env, provider files, sessions or auth
        self.assert_read_only(before)
        # Another manager/retained invocation must not be borrowed.
        self.h.rules(*self.lists('--user'), *self.lists('--system', [self.unit(unit, 'active')]),
                     self.detail('--system', unit, **props),
                     {'tool': 'journalctl', 'argv_contains': ['--system', unit],
                      'stdout': json.dumps({**scene, '_SYSTEMD_INVOCATION_ID': 'f' * 32}) + '\n'})
        _, doc, _ = self.invoke()
        row = next(r for r in doc['rows'] if r['unit'] == unit)
        self.assertEqual(row['worker']['state'], 'active/issue unknown')

    def test_timer_identity_follows_explicit_target_even_without_orbi_name(self):
        self.h.rules(*self.lists('--user', [self.unit('orbi@7.service'),
                                          self.unit('custom.timer', 'active'),
                                          self.unit('orbi-alternate.timer', 'active'),
                                          self.unit('orbi-invalid@2.timer', 'active')]),
                     *self.lists('--system'),
                     self.detail('--user', 'orbi@7.service'),
                     self.detail('--user', 'custom.timer', Unit='orbi@7.service'),
                     self.detail('--user', 'orbi-alternate.timer', Unit='orbi@7.service', ActiveState='inactive'),
                     self.detail('--user', 'orbi-invalid@2.timer', Unit='invalid target'))
        _, doc, _ = self.invoke()
        row = next(r for r in doc['rows'] if r['unit'] == 'orbi@7.service')
        self.assertEqual(set(row['timers']), {'custom.timer', 'orbi-alternate.timer'})
        self.assertEqual(row['state'], 'idle')
        self.assertEqual(row['timer'], 'custom.timer')
        self.assertEqual(doc['totals']['observed_workers'], 1)

    def test_unloaded_definitions_timer_target_and_detail_limit(self):
        self.h.rules(*self.lists('--user', [self.unit('orbi-alias@99.timer', 'active'),
                                          self.unit('orbi-target@99.service')],
                                [{'unit_file': 'orbi-unused@28.service', 'state': 'disabled'}]),
                     *self.lists('--system'),
                     self.detail('--user', 'orbi-alias@99.timer', Unit='orbi-target@99.service'),
                     self.detail('--user', 'orbi-target@99.service'),
                     self.detail('--user', 'orbi-unused@28.service', LoadState='loaded'))
        _, doc, _ = self.invoke()
        rows = {r['unit']: r for r in doc['rows'] if r['unit']}
        self.assertEqual(rows['orbi-target@99.service']['timer'], 'orbi-alias@99.timer')
        self.assertEqual(rows['orbi-unused@28.service']['scheduler'], 'unloaded')
        self.assertTrue(rows['orbi-unused@28.service']['installed'])
        self.assertFalse(rows['orbi-unused@28.service']['loaded'])
        self.assertEqual(doc['totals']['observed_workers'], 1)
        self.h.clear_calls()
        self.h.rules(*self.lists('--user', [self.unit(f'orbi@{i}.service') for i in range(4)]),
                     *self.lists('--system'))
        with mock.patch.object(helper, 'HOST_DETAIL_LIMIT', 2):
            _, doc, _ = self.invoke()
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertEqual(sum('show' in c['argv'] for c in self.h.calls()), 2)

    def test_config_permission_error_preserves_healthy_repo_and_engine_unknown_without_git(self):
        a = self.h.add_deployment_a()
        original = helper.bounded_bytes

        def denied(path, *args):
            if Path(path) == a['config']:
                raise PermissionError('private contents must not appear')
            return original(path, *args)

        self.h.rules(*self.lists('--user'), *self.lists('--system'))
        with mock.patch.object(helper, 'bounded_bytes', side_effect=denied):
            _, doc, _ = self.invoke()
        self.assertTrue(any(r['binding']['state'] == 'unreadable' for r in doc['rows']))
        self.assertNotIn('private contents', json.dumps(doc))
        original_run = helper.Context.run

        def no_git(ctx, argv, **kwargs):
            if argv[0] == 'git':
                raise helper.ControlError('prerequisite_missing', 'git missing')
            return original_run(ctx, argv, **kwargs)

        with mock.patch.object(helper.Context, 'run', no_git):
            _, doc, _ = self.invoke()
        row = next(r for r in doc['rows'] if r['binding']['config'] == str(a['config']))
        self.assertEqual(row['binding']['state'], 'verified')
        self.assertEqual(row['repo'], 'other/repo-a')
        self.assertIsNone(row['engine']['version'])

    def test_macos_custom_loaded_job_uses_observed_plist_and_denied_job_is_not_unloaded(self):
        import plistlib
        config = self.h.root / 'native.toml'
        config.write_text('source_repos = ["native/repo"]\n')
        label, denied = 'vendor.delivery', 'org.orbi.denied.runner.20'
        definition = self.h.root / 'observed.plist'
        definition.write_bytes(plistlib.dumps({'Label': label, 'ProgramArguments': ['/bin/orbi'],
            'EnvironmentVariables': {'ORBI_CONFIG': str(config)}}, fmt=plistlib.FMT_BINARY))
        domain = f'gui/{os.getuid()}'
        self.h.rules(
            {'tool': 'launchctl', 'argv_contains': ['print', domain + '/' + label],
             'stdout': f'path = {definition}\nstate = running\npid = 123\n'},
            {'tool': 'launchctl', 'argv_contains': ['print', domain + '/' + denied],
             'exit': 1, 'stderr': 'Access denied ' + SECRET},
            {'tool': 'launchctl', 'argv_contains': ['print', domain],
             'stdout': f'services = {{\n123 0 {label}\n234 0 {denied}\n}}\n'},
            {'tool': 'launchctl', 'argv_contains': ['print'], 'stdout': 'services = {\n}\n'})
        before = snapshot(self.h.home)
        _, doc, _ = self.invoke(platform='darwin')
        rows = {r['unit']: r for r in doc['rows'] if r['unit']}
        self.assertEqual(rows[label]['repo'], 'native/repo')
        self.assertEqual(rows[label]['kind'], 'runner')
        self.assertEqual(rows[label]['worker']['state'], 'active/issue unknown')
        self.assertTrue(rows[denied]['loaded'])
        self.assertEqual(rows[denied]['scheduler'], 'unknown')
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assertNotIn(SECRET, json.dumps(doc))
        self.assert_read_only(before, platform='darwin')
        self.assertEqual([c['argv'] for c in self.h.calls() if c['tool'] == 'gh'], [['api', 'rate_limit']])

    def test_macos_installed_is_not_loaded_and_loaded_orphans_are_observed(self):
        folder = self.h.home / 'Library/LaunchAgents'
        folder.mkdir(parents=True)
        import plistlib
        (folder / 'org.orbi.custom.runner.9.plist').write_bytes(plistlib.dumps({
            'Label': 'org.orbi.custom.runner.9', 'EnvironmentVariables': {'ORBI_CONFIG': '/missing'}},
            fmt=plistlib.FMT_BINARY))
        domain = f'gui/{os.getuid()}'
        self.h.rules(
            {'tool': 'launchctl', 'argv_contains': ['print', domain + '/org.orbi.custom.runner.9'], 'exit': 113},
            {'tool': 'launchctl', 'argv_contains': ['print', domain + '/org.orbi.orphan.runner.7'],
             'stdout': 'state = running\npid = 123\n'},
            {'tool': 'launchctl', 'argv_contains': ['print', domain],
             'stdout': 'services = {\n 123 0 org.orbi.orphan.runner.7\n}\n'},
            {'tool': 'launchctl', 'argv_contains': ['print', 'user/'], 'stdout': 'services = {\n}\n'},
            {'tool': 'launchctl', 'argv_contains': ['print', 'system'], 'exit': 1},
        )
        before = snapshot(self.h.home)
        code, doc, _ = self.invoke(platform='darwin')
        self.assertEqual(code, 0)
        rows = {r['unit']: r for r in doc['rows'] if r['unit']}
        self.assertFalse(rows['org.orbi.custom.runner.9']['loaded'])
        self.assertEqual(rows['org.orbi.custom.runner.9']['scheduler'], 'unloaded')
        self.assertEqual(rows['org.orbi.orphan.runner.7']['worker']['state'], 'active/issue unknown')
        self.assertEqual(doc['coverage']['state'], 'partial')
        self.assert_read_only(before, platform='darwin')
        self.assertEqual([c['argv'] for c in self.h.calls() if c['tool'] == 'gh'], [['api', 'rate_limit']])


class VersionActionTests(unittest.TestCase):
    """One read-only helper call, with deployment evidence rather than PATH CLI."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.h = Harness(Path(tmp.name))
        self.h.add_deployment_a()
        self.h.deploy.mkdir()
        self.config = self.h.deploy / 'orbi.toml'
        self.config.write_text(
            f'source_repos = ["{REPO}"]\nrepo_dir = "{self.h.repo}"\n'
            f'deploy_home = "{self.h.deploy}"\nunit_name = "version-test"\n'
            f'engine_source_track = "sha:{PIN}"\n')
        self.manifest = '[project]\nname = "orbi-cli"\nversion = "0.7.56"\n'
        (self.h.deploy / 'pyproject.toml').write_text(self.manifest)
        self.rules()

    def rules(self, *extra):
        self.h.rules(*extra, {'tool': 'git', 'argv_contains': ['show', 'HEAD:pyproject.toml'],
                              'stdout': self.manifest})

    def assert_read_only(self, before):
        self.assertEqual(snapshot(self.h.home), before)
        self.assertTrue(self.h.calls())
        for call in self.h.calls():
            self.assertEqual(call['tool'], 'git', call)
            argv = call['argv'][2:]
            self.assertIn(argv, [
                ['worktree', 'list', '--porcelain'],
                ['config', '--get', 'remote.origin.url'], ['rev-parse', 'HEAD'],
                ['show', 'HEAD:pyproject.toml'],
                ['diff', '--quiet', 'HEAD', '--', 'pyproject.toml', 'src/orbi']], call)
            if argv[0] == 'diff':
                self.assertEqual(call['env']['GIT_OPTIONAL_LOCKS'], '0')

    def test_verified_text_json_and_status_agree_on_linux_and_macos(self):
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform):
                code, status, err = self.h.run('status', platform=platform)
                self.assertEqual(code, 0, err)
                expected = status['deployment']['engine'].copy()
                self.assertEqual(expected.pop('bootstrap_cli')['version'], '0.7.41')
                for json_mode in (True, False):
                    self.h.clear_calls()
                    before = snapshot(self.h.home)
                    code, doc, err = self.h.run('version', platform=platform, json_mode=json_mode)
                    self.assertEqual(code, 0, err)
                    if json_mode:
                        self.assertEqual(doc['action'], 'version')
                        self.assertEqual(doc['repo'], REPO)
                        self.assertEqual(doc['repo_dir'], str(self.h.repo))
                        self.assertEqual(set(doc), {'action', 'platform', 'repo', 'repo_dir', 'deployment'})
                        deployment = doc['deployment']
                        self.assertEqual(deployment['config'], str(self.config))
                        self.assertEqual(deployment['deploy_home'], str(self.h.deploy))
                        self.assertEqual(deployment['unit_name'], 'version-test')
                        self.assertEqual(deployment['engine'], expected)
                        self.assertEqual(expected['state'], 'verified')
                        self.assertEqual(expected['version'], '0.7.56')
                        self.assertEqual(expected['revision'], PIN)
                    else:
                        for value in (REPO, str(self.config), str(self.h.deploy),
                                      'version-test', '0.7.56', PIN, 'verified', 'pyproject.toml'):
                            self.assertIn(value, doc)
                        self.assertNotIn('0.7.41', doc)
                    self.assert_read_only(before)

    def test_unknown_metadata_never_substitutes_observed_revision_for_release(self):
        for kind in ('missing', 'modified', 'dirty_source', 'unpinned', 'drift', 'unreadable_head'):
            with self.subTest(kind=kind):
                manifest = self.h.deploy / 'pyproject.toml'
                manifest.write_text(self.manifest)
                if kind == 'missing':
                    manifest.unlink()
                if kind == 'modified':
                    manifest.write_text(self.manifest.replace('0.7.56', '9.9.9'))
                self.config.write_text(self.config.read_text().replace('main', 'sha:' + PIN))
                if kind == 'unpinned':
                    self.config.write_text(self.config.read_text().replace('sha:' + PIN, 'main'))
                self.rules(*(
                    [{'tool': 'git', 'argv_contains': ['diff', '--quiet'], 'exit': 1}]
                    if kind == 'dirty_source' else
                    [{'tool': 'git', 'argv_contains': [str(self.h.deploy), 'rev-parse', 'HEAD'],
                      'stdout': OLD_PIN + '\n' if kind == 'drift' else '',
                      'exit': 0 if kind == 'drift' else 1}]
                    if kind in ('drift', 'unreadable_head') else []))
                self.h.clear_calls()
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('version')
                self.assertEqual(code, 0, err)
                engine = doc['deployment']['engine']
                self.assertEqual(engine['state'], 'unknown')
                self.assertIsNone(engine['version'])
                self.assertTrue(engine['reason'])
                self.assertEqual(engine['revision'], OLD_PIN if kind == 'drift' else
                                 None if kind in ('unpinned', 'unreadable_head') else PIN)
                self.assertNotIn('bootstrap_cli', engine)
                self.assert_read_only(before)

    def test_absent_is_unconfigured_on_both_platforms(self):
        self.config.unlink()
        for platform in ('linux', 'darwin'):
            self.h.clear_calls()
            before = snapshot(self.h.home)
            code, doc, err = self.h.run('version', platform=platform)
            self.assertEqual(code, 0, err)
            self.assertEqual(doc['deployment']['state'], 'absent')
            self.assertEqual(doc['deployment']['engine']['state'], 'unconfigured')
            self.assertIsNone(doc['deployment']['engine']['version'])
            code, text, err = self.h.run('version', platform=platform, json_mode=False)
            self.assertEqual(code, 0, err)
            self.assertIn('unconfigured', text)
            self.assert_read_only(before)

    def test_target_errors_preserve_binding_and_repair_without_fallback(self):
        original = self.config.read_text()
        duplicate = self.h.data_home / 'duplicate/orbi.toml'
        for kind, error in (('missing', 'config_missing'), ('foreign', 'config_mismatch'),
                            ('repo', 'repo_mismatch'), ('ambiguous', 'ambiguous_deployment'),
                            ('missing_repo', 'repo_missing')):
            with self.subTest(kind=kind):
                self.config.write_text(original.replace(str(self.h.repo), '/foreign/repo')
                                       if kind == 'repo' else original)
                if kind == 'ambiguous':
                    duplicate.parent.mkdir(exist_ok=True)
                    duplicate.write_text(original)
                self.h.clear_calls()
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('version', config=(
                    self.h.root / 'missing.toml' if kind == 'missing' else
                    self.h.a['config'] if kind == 'foreign' else self.config),
                    options=['--repo-dir', str(self.h.root / 'missing-repo')]
                            if kind == 'missing_repo' else [])
                self.assertNotEqual(code, 0)
                self.assertEqual(doc['error']['code'], error)
                self.assertTrue(doc['error']['fix'])
                self.assertFalse(doc['error']['mutated'])
                if kind != 'missing_repo':
                    self.assert_read_only(before)
                else:
                    self.assertEqual(self.h.calls(), [])
                duplicate.unlink(missing_ok=True)

    def test_invalid_version_selectors_refuse_before_probes(self):
        for options in (['all'], ['--dry-run'], ['--stop'], ['--harness', 'pi'],
                        ['--resume-setup'], ['--pi-providers', '/missing']):
            self.h.clear_calls()
            # Positional all precedes flags, as in the real helper interface.
            out = io.StringIO()
            code = helper.main(['version', *options, '--json'], env=self.h.env,
                               platform='linux', stdout=out)
            self.assertNotEqual(code, 0, options)
            self.assertTrue(json.loads(out.getvalue())['error']['fix'])
            self.assertEqual(self.h.calls(), [])

    def test_real_cli_single_call_and_missing_explicit_config_receipt(self):
        for config, expected_code in ((self.config, 0), (self.h.root / 'missing.toml', 1)):
            self.h.clear_calls()
            before, repo_before = snapshot(self.h.home), snapshot(self.h.repo)
            result = subprocess.run(
                [sys.executable, '-B', str(HELPER), 'version', '--repo-dir', str(self.h.repo),
                 '--config', str(config), '--json'],
                cwd=self.h.root, env=self.h.env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
            self.assertEqual(result.stderr, '')
            doc = json.loads(result.stdout)
            if expected_code == 0:
                self.assertEqual(doc['deployment']['engine']['version'], '0.7.56')
            else:
                self.assertEqual(doc['error']['code'], 'config_missing')
                self.assertEqual(doc['error']['fix'], 'pass an existing native Orbi config path')
            self.assertEqual(snapshot(self.h.repo), repo_before)
            self.assert_read_only(before)


class RunningStatusTests(unittest.TestCase):
    """Public helper journey; journal scenes follow upstream pi_activity's contract."""

    def setUp(self):
        self.h = LifecycleSequenceTests.fresh(self)
        self.prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        self.manifest = '[project]\nname = "orbi-cli"\nversion = "0.7.56"\n'
        (self.h.deploy / 'pyproject.toml').write_text(self.manifest)

    def binding(self, index, number, run_id, *, pid=None, invocation=None, message=None):
        pid = pid or 400 + index
        invocation = invocation or str(index) * 32
        unit = f'{self.prefix}@{index}.service'
        properties = (f'ActiveState=active\nMainPID={pid}\nInvocationID={invocation}\n'
                      f'WorkingDirectory={self.h.deploy}\n'
                      f'FragmentPath={self.h.unit_dir}/{self.prefix}@.service\n')
        # Verbatim run_start field grammar from orbi-build/orbi 080590b3
        # src/orbi/pi_activity.py:format_run_scene (private fields must not leak).
        scene = (f'INFO [{run_id}] run_start run={run_id} issue={REPO}#{number} '
                 'role=implement branch=private worktree=/private session=private '
                 'session_file=/private phase=session_pending '
                 'last_activity=2026-11-23T06:18:00Z action=private result=-')
        entry = {'MESSAGE': message or scene, '_PID': str(pid),
                 '_SYSTEMD_INVOCATION_ID': invocation}
        return [
            {'tool': 'systemctl', 'argv_contains': ['show', unit, 'MainPID'],
             'stdout': properties},
            {'tool': 'journalctl', 'argv_contains': [unit],
             'stdout': json.dumps(entry) + '\n'}]

    def rules(self, *extra, services=None, nodes=None):
        self.h.rules(*extra,
            {'tool': 'git', 'argv_contains': ['show', 'HEAD:pyproject.toml'],
             'stdout': self.manifest},
            {'tool': 'gh', 'argv_contains': ['api', 'graphql'],
             'stdout': PendingStatusTests.page(nodes or [PendingStatusTests.issue(43, ['ai-ready']),
                                                       PendingStatusTests.issue(42, ['ai-in-progress'])])},
            *self.h.scheduler_rules(services=services or {}, timers={1: 'active'}, enabled={1: True}))

    def assert_read_only(self, before):
        self.assertEqual(snapshot(self.h.home), before)
        for call in self.h.calls():
            argv, tool = call['argv'], call['tool']
            if tool == 'systemctl':
                self.assertIn(argv[1], ('show', 'is-enabled'), call)
                self.assertNotIn('Environment', argv)
            elif tool == 'journalctl':
                self.assertIn('-n', argv)
                self.assertEqual(argv[argv.index('-n') + 1], '100')
                self.assertTrue(any(a.startswith('_SYSTEMD_INVOCATION_ID=') for a in argv))
                self.assertNotIn('--follow', argv)
            elif tool == 'orbi':
                self.assertIn(argv[0], ('--version', 'doctor'), call)
            elif tool == 'git':
                self.assertIn(argv[2], ('worktree', 'config', 'rev-parse', 'show', 'diff'), call)
                if argv[2] == 'diff':
                    self.assertEqual(call['env']['GIT_OPTIONAL_LOCKS'], '0')
            elif tool == 'gh':
                self.assertIn(argv[:2], (['api', 'graphql'], ['api', '--method'], ['pr', 'view']))
            elif tool in ('pi', 'pi-bolt'):
                self.assertEqual(argv, ['--version'])
            else:
                self.fail(f'unexpected tool {tool}: {argv}')

    def test_running_is_not_queue_head_text_json_and_two_slots(self):
        self.rules(*self.binding(1, 42, '1234abcd'), *self.binding(2, 44, 'abcd1234'),
                   services={1: 'active', 2: 'active'},
                   nodes=[PendingStatusTests.issue(43, ['ai-ready']),
                          PendingStatusTests.issue(42, ['ai-in-progress']),
                          PendingStatusTests.issue(44, ['ai-in-progress'])])
        before = snapshot(self.h.home)
        for json_mode in (False, True):
            proc = subprocess.run([sys.executable, '-B', str(HELPER),
                '--repo-dir', str(self.h.repo), *(['--json'] if json_mode else [])],
                env=self.h.env, capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            if json_mode:
                doc = json.loads(proc.stdout)
                slots = doc['activity']['slots']
                self.assertEqual([slots[f'{self.prefix}@{i}.service']['issue']['number']
                                  for i in (1, 2)], [42, 44])
                self.assertEqual(slots[f'{self.prefix}@1.service']['run_id'], '1234abcd')
                self.assertEqual(slots[f'{self.prefix}@1.service']['phase'], 'session_pending')
                self.assertEqual(slots[f'{self.prefix}@1.service']['issue']['title'], 'Issue 42')
                self.assertEqual(doc['queue']['ready'], ['#43 Issue 43'])
                self.assertEqual(doc['activity']['working'], {'state': 'ok', 'value': 2})
                engine = doc['deployment']['engine']
                self.assertEqual(engine['state'], 'verified')
                self.assertEqual(engine['version'], '0.7.56')
                self.assertEqual(engine['revision'], PIN)
                self.assertEqual(engine['bootstrap_cli']['version'], '0.7.41')
                self.assertEqual(engine['bootstrap_cli']['comparison'], 'mismatch')
            else:
                self.assertTrue(proc.stdout.startswith(f'Repository: {REPO}\n'))
                self.assertIn('Orbi: 0.7.56', proc.stdout)
                self.assertIn('running #42 Issue 42', proc.stdout)
                self.assertIn('running #44 Issue 44', proc.stdout)
                self.assertIn('#43 Issue 43', proc.stdout)
            self.assertNotIn('/private', proc.stdout)
            self.assertNotIn('action=private', proc.stdout)
        self.assert_read_only(before)

    def test_active_unknown_never_borrows_retained_issue(self):
        for kind in ('missing', 'stale_invocation', 'wrong_pid', 'wrong_repo', 'ended', 'conflict'):
            with self.subTest(kind=kind):
                binding = self.binding(1, 42, '1234abcd')
                entry = json.loads(binding[1]['stdout'])
                if kind == 'missing':
                    binding = []
                elif kind == 'stale_invocation':
                    entry['_SYSTEMD_INVOCATION_ID'] = 'f' * 32
                elif kind == 'wrong_pid':
                    entry['_PID'] = '999'
                elif kind == 'wrong_repo':
                    entry['MESSAGE'] = entry['MESSAGE'].replace(REPO, 'other/repo')
                elif kind == 'ended':
                    binding[1]['stdout'] += json.dumps({**entry, 'MESSAGE':
                        'INFO [1234abcd] run_end run=1234abcd issue=example/kit#42 result=ok'}) + '\n'
                elif kind == 'conflict':
                    binding[1]['stdout'] += json.dumps({**entry, 'MESSAGE':
                        entry['MESSAGE'].replace('#42', '#99')}) + '\n'
                if kind not in ('missing', 'ended', 'conflict'):
                    binding[1]['stdout'] = json.dumps(entry) + '\n'
                self.rules(*binding, services={1: 'active'})
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('status')
                self.assertEqual(code, 0, err)
                slot = doc['activity']['slots'][f'{self.prefix}@1.service']
                self.assertEqual(slot['state'], 'active/issue unknown')
                self.assertNotIn('issue', slot)
                self.assertIn('next_action', slot)
                self.assertIsNone(doc['activity']['working']['value'])
                self.assert_read_only(before)

    def test_idle_and_transitions_and_unverifiable_version(self):
        self.rules(services={1: 'inactive', 2: 'activating', 3: 'deactivating'})
        (self.h.deploy / 'pyproject.toml').unlink()
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['deployment']['engine']['state'], 'unknown')
        self.assertIsNone(doc['deployment']['engine']['version'])
        slots = doc['activity']['slots']
        for i, state in ((1, 'idle'), (2, 'starting'), (3, 'draining')):
            self.assertEqual(slots[f'{self.prefix}@{i}.service']['state'], state)
            self.assertNotIn('issue', slots[f'{self.prefix}@{i}.service'])
        self.assertEqual(doc['queue']['ready'], ['#43 Issue 43'])
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'journalctl'])
        self.assert_read_only(before)

    def test_idle_with_queue_and_failed_health_and_tick_times(self):
        timer = f'{self.prefix}@1.timer'
        self.rules({'tool': 'systemctl', 'argv_contains': ['show', timer, 'LastTriggerUSec'],
                    'stdout': 'LastTriggerUSec=Mon 2026-11-23 06:00:00 UTC\n'
                              'NextElapseUSecRealtime=Mon 2026-11-23 06:05:00 UTC\n'
                              'Environment=DO_NOT_RETURN\n'}, services={2: 'failed'})
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['activity']['working'], {'state': 'ok', 'value': 0})
        self.assertEqual(doc['activity']['slots'][f'{self.prefix}@1.service']['state'], 'idle')
        self.assertEqual(doc['activity']['slots'][f'{self.prefix}@2.service']['health'], 'failed')
        self.assertEqual(doc['activity']['ticks'][timer], {
            'LastTriggerUSec': 'Mon 2026-11-23 06:00:00 UTC',
            'NextElapseUSecRealtime': 'Mon 2026-11-23 06:05:00 UTC'})
        self.assertNotIn('DO_NOT_RETURN', json.dumps(doc))
        code, text, err = self.h.run('status', json_mode=False)
        self.assertEqual(code, 0, err)
        self.assertIn('working=0', text)
        self.assertIn('Queue: ready=1 pending=2', text)
        self.assertNotIn('running #42', text)
        self.assert_read_only(before)

    def test_queue_unavailable_cannot_hide_a_verified_live_issue(self):
        self.rules({'tool': 'gh', 'argv_contains': ['api', 'graphql'], 'exit': 1},
                   *self.binding(1, 42, '1234abcd'), services={1: 'active'})
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['state'], 'unavailable')
        slot = doc['activity']['slots'][f'{self.prefix}@1.service']
        self.assertEqual(slot['state'], 'running')
        self.assertEqual(slot['issue']['number'], 42)
        self.assertNotIn('title', slot['issue'])
        self.assert_read_only(before)

    def test_version_unknown_for_modified_missing_or_unpinned_metadata(self):
        for kind in ('modified', 'dirty_source', 'unpinned', 'oversized'):
            with self.subTest(kind=kind):
                config = self.h.deploy / 'orbi.toml'
                original = config.read_text()
                (self.h.deploy / 'pyproject.toml').write_text(
                    self.manifest.replace('0.7.56', '9.9.9') if kind == 'modified' else
                    self.manifest + '# ' + 'x' * 65536 if kind == 'oversized' else self.manifest)
                if kind == 'unpinned':
                    config.write_text(original.replace(helper.PIN_TRACK, 'main'))
                self.rules(*([{'tool': 'git', 'argv_contains': ['diff', '--quiet'], 'exit': 1}]
                              if kind == 'dirty_source' else []))
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('status')
                self.assertEqual(code, 0, err)
                engine = doc['deployment']['engine']
                self.assertEqual(engine['state'], 'unknown')
                self.assertIsNone(engine['version'])
                self.assertEqual(engine['bootstrap_cli']['version'], '0.7.41')
                self.assertEqual(engine['bootstrap_cli']['comparison'], 'unknown')
                self.assert_read_only(before)
                config.write_text(original)

    def test_snapshot_restart_and_capped_journal_are_unknown(self):
        self.rules(*self.binding(1, 42, '1234abcd'), services={1: 'active'})
        original = helper.service_binding
        calls = []

        def restarted(*args):
            binding = original(*args)
            calls.append(binding)
            return {**binding, 'InvocationID': 'f' * 32} if len(calls) > 1 else binding

        with mock.patch.object(helper, 'service_binding', restarted):
            code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(len(calls), 2)
        self.assertEqual(doc['activity']['slots'][f'{self.prefix}@1.service']['state'],
                         'active/issue unknown')
        # A heartbeat within the current invocation cannot substitute for the
        # run_start that fell outside the bounded tail. No newest-run fallback.
        self.rules(*self.binding(1, 42, '1234abcd', message=
            f'INFO [1234abcd] heartbeat issue={REPO}#42 role=implement phase=working'),
            services={1: 'active'})
        code, text, err = self.h.run('status', json_mode=False)
        self.assertEqual(code, 0, err)
        self.assertIn('active/issue unknown', text)
        self.assertNotIn('running #42', text)

    def test_macos_owned_jobs_idle_active_and_foreign_remain_read_only(self):
        import plistlib
        folder = self.h.home / 'Library/LaunchAgents'
        folder.mkdir(parents=True)
        labels = [f'org.orbi.{helper.derive_unit_name(REPO)}.runner.{i}' for i in (1, 2, 3)]
        rules = []
        for index, label in enumerate(labels, 1):
            (folder / (label + '.plist')).write_bytes(plistlib.dumps({
                'Label': label, 'WorkingDirectory': str(self.h.deploy),
                'EnvironmentVariables': {'ORBI_CONFIG': str(self.h.deploy / 'orbi.toml')
                                         if index != 3 else '/foreign/orbi.toml', 'TOKEN': SECRET}}))
            rules.append({'tool': 'launchctl', 'argv_contains': ['print', label],
                'stdout': 'state = not running\n' if index == 1 else 'state = running\npid = 902\n'})
        self.rules(*rules)
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('status', platform='darwin')
        self.assertEqual(code, 0, err)
        slots = doc['activity']['slots']
        self.assertEqual([slots[label]['state'] for label in labels],
                         ['idle', 'active/issue unknown', 'unknown'])
        self.assertEqual(doc['deployment']['engine']['version'], '0.7.56')
        self.assertFalse([c for c in self.h.calls() if c['tool'] in {'systemctl', 'journalctl'}])
        self.assertEqual([c['argv'] for c in self.h.calls() if c['tool'] == 'launchctl'],
                         [['print', f'gui/{os.getuid()}/{label}'] for label in labels[:2]])
        self.assertNotIn(SECRET, json.dumps(doc))
        self.assertEqual(snapshot(self.h.home), before)

    def test_macos_torn_plist_keeps_partial_status(self):
        folder = self.h.home / 'Library/LaunchAgents'
        folder.mkdir(parents=True)
        label = f'org.orbi.{helper.derive_unit_name(REPO)}.runner.1'
        (folder / (label + '.plist')).write_text('<?xml version="1.0"?><plist><dict>')
        self.rules()
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('status', platform='darwin')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['activity']['slots'][label]['state'], 'unknown')
        self.assertEqual(doc['queue']['ready'], ['#43 Issue 43'])
        self.assertIsNone(doc['activity']['working']['value'])
        self.assertEqual(snapshot(self.h.home), before)

    def test_long_running_issue_survives_noisy_journal_tail(self):
        binding = self.binding(1, 42, '1234abcd')
        entry = json.loads(binding[1]['stdout'])
        heartbeat = {**entry, 'MESSAGE':
            f'INFO [1234abcd] heartbeat issue={REPO}#42 role=review '
            'phase=read state=- elapsed=14m idle=1s'}
        # journalctl applies --grep before -n. A normal task produces many
        # command/activity lines; its run_start still exists outside that tail.
        for ended in (False, True):
            with self.subTest(ended=ended):
                # --grep with -n implies --reverse (journalctl(1)); lifecycle
                # results are newest first, unlike the ordinary recent tail.
                lifecycle = binding[1]['stdout']
                if ended:
                    lifecycle = json.dumps({**entry, 'MESSAGE':
                        f'INFO [1234abcd] run_end run=1234abcd issue={REPO}#42 '
                        'role=review result=ok elapsed=14m pr=- commit=-'}) + '\n' + lifecycle
                self.rules(binding[0],
                    {**binding[1], 'stdout': lifecycle,
                     'argv_contains': [binding[0]['argv_contains'][1],
                        '--grep=^(INFO|WARNING|ERROR) \\[([0-9a-f]{8})\\] (run_start|run_end|run_failed) ']},
                    {**binding[1], 'stdout': (json.dumps(heartbeat) + '\n') * 100},
                    services={1: 'active'})
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('status')
                self.assertEqual(code, 0, err)
                slot = doc['activity']['slots'][f'{self.prefix}@1.service']
                self.assertEqual(slot['state'], 'active/issue unknown' if ended else 'running')
                if not ended:
                    self.assertEqual(slot['issue']['number'], 42)
                    self.assertEqual(slot['phase'], 'read')
                else:
                    self.assertNotIn('issue', slot)
                self.assert_read_only(before)


class PendingStatusTests(unittest.TestCase):
    """Historical acceptance snapshot, not current remote deployment state."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(Path(self.tmp.name))

    @staticmethod
    def issue(number, labels=(), *, deps=(), owner=None, **extra):
        return {'__typename': 'Issue', 'number': number, 'title': f'Issue {number}',
                'url': f'https://github.com/{REPO}/issues/{number}', 'state': 'OPEN',
                'labels': {'nodes': [{'name': name} for name in labels],
                           'pageInfo': {'hasNextPage': False}},
                'assignees': {'nodes': [{'login': owner}] if owner else [],
                              'pageInfo': {'hasNextPage': False}},
                'blockedBy': {'nodes': list(deps), 'pageInfo': {'hasNextPage': False}},
                **extra}

    @staticmethod
    def page(nodes, more=False, cursor=None):
        return json.dumps({'data': {'repository': {'issues': {
            'nodes': nodes, 'pageInfo': {'hasNextPage': more, 'endCursor': cursor}}}}})

    def rules(self, nodes, *extra):
        self.h.rules(*extra, {'tool': 'gh', 'argv_contains': ['api', 'graphql'],
                              'stdout': self.page(nodes)})

    def assert_reads_only(self):
        for call in self.h.calls():
            if call['tool'] == 'gh':
                self.assertTrue(call['argv'][:2] in (['api', 'graphql'], ['api', '--method'],
                                                    ['pr', 'view']), call)
            if call['tool'] == 'systemctl':
                self.assertFalse(set(call['argv']) & {'enable', 'disable', 'start', 'stop',
                                                      'restart', 'kill', 'daemon-reload'})
            if call['tool'] == 'git':
                self.assertFalse(set(call['argv']) & {'fetch', 'checkout', 'merge', 'push'})
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'uv'])

    def test_six_pending_activating_and_unsafe_branch_recovery(self):
        self.h.add_deployment_a()
        code, _, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.h.clear_calls()
        comments = [{'body': '<!-- orbi:run=existing --> ' +
                     '<!-- orbi:failure:v1 {"retry_safe":false,"reason_code":"human_decision_required"} -->' +
                     ' The delivery branch changed on GitHub; retained work conflicts. ' +
                     f'https://github.com/{REPO}/pull/64',
                     'html_url': f'https://github.com/{REPO}/issues/62#issuecomment-1'},
                    # Orbi also emits a terse duplicate receipt after the diagnosis.
                    {'body': '<!-- orbi:failure:v1 {"retry_safe":false} --> Orbi: blocked'}]
        self.rules([self.issue(62, ['ai-ready', 'ai-blocked']),
                    *[self.issue(n, ['ai-planning']) for n in (51, 32, 31, 23)],
                    self.issue(28, ['ai-ready', 'ai-epic']),
                    self.issue(61, ['ai-ready'], state='CLOSED')],
                   {'tool': 'gh', 'argv_contains': ['issues/62/comments'],
                    'stdout': json.dumps(comments)},
                   {'tool': 'gh', 'argv_contains': ['pr', 'view', '64'],
                    'stdout': json.dumps({'number': 64, 'state': 'OPEN',
                                         'url': f'https://github.com/{REPO}/pull/64',
                                         'headRefName': 'delivery', 'headRefOid': 'a' * 40})},
                   *self.h.scheduler_rules(services={1: 'activating'}))
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['deployment']['state'], 'transitional')
        queue = doc['queue']
        self.assertEqual(queue['ready'], [])
        self.assertEqual(queue['pending_count'], 6)
        groups = queue['pending']
        blocked = groups['actionable_blocker'][0]
        self.assertEqual(blocked['number'], 62)
        self.assertFalse(blocked['retry_safe'])
        self.assertIn('remote head', blocked['next_action'])
        self.assertIn('retained work', blocked['next_action'])
        self.assertIn('existing owner', blocked['next_action'])
        self.assertIn('/unblock', blocked['next_action'])
        self.assertEqual(blocked['pull_requests'][0]['state'], 'OPEN')
        self.assertIn('not successful delivery', blocked['pull_requests'][0]['meaning'])
        self.assertEqual([i['number'] for i in groups['planning_paused']], [51, 32, 31, 23])
        self.assertTrue(all('unknown' in i['next_action'] for i in groups['planning_paused']))
        self.assertEqual(groups['epic'][0]['number'], 28)
        self.assertIn('coordination', groups['epic'][0]['reason'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertEqual(len([c for c in self.h.calls() if c['tool'] == 'gh']), 3)
        self.assert_reads_only()

    def test_idle_ready_mixed_labels_native_dependency_and_unknown(self):
        self.h.add_deployment_a()
        code, _, err = self.h.run('setup')
        self.assertEqual(code, 0, err)
        self.h.clear_calls()
        deps = [{'number': 10, 'url': f'https://github.com/{REPO}/issues/10',
                 'title': 'Prerequisite', 'state': 'OPEN'}]
        self.rules([self.issue(1, ['ai-ready']), self.issue(2, ['ai-ready', 'ai-paused']),
                    self.issue(3, ['ai-ready'], deps=deps), self.issue(4, owner='operator'),
                    self.issue(5), self.issue(6, ['ai-ready', 'ai-in-progress']),
                    self.issue(7, ['ai-ready'], blockedBy={'nodes': [],
                               'pageInfo': {'hasNextPage': True}})],
                   {'tool': 'gh', 'argv_contains': ['comments'], 'stdout': '[]'})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        queue = doc['queue']
        self.assertEqual(doc['deployment']['state'], 'stopped')
        self.assertEqual(queue['ready'], ['#1 Issue 1'])
        self.assertEqual(queue['pending']['native_dependency'][0]['prerequisites'], deps)
        self.assertEqual([i['number'] for i in queue['pending']['active_owned']], [4, 6])
        self.assertEqual([i['number'] for i in queue['pending']['unknown']], [5, 7])
        self.assertEqual(queue['state'], 'partial')
        self.assert_reads_only()

    def test_pagination_filters_closed_and_pr_nodes_and_discloses_failure(self):
        first = self.page([self.issue(1, ['ai-ready']),
                           self.issue(2, __typename='PullRequest'),
                           self.issue(3, state='CLOSED')], True, 'next')
        self.h.rules({'tool': 'gh', 'argv_contains': ['cursor=next'],
                      'stdout': self.page([self.issue(4, ['ai-planning'])])},
                     {'tool': 'gh', 'argv_contains': ['api', 'graphql'], 'stdout': first})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['pending_count'], 2)
        self.assertTrue(doc['queue']['coverage']['complete'])
        self.h.clear_calls()
        self.h.rules({'tool': 'gh', 'argv_contains': ['cursor=next'], 'exit': 1},
                     {'tool': 'gh', 'argv_contains': ['api', 'graphql'], 'stdout': first})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['state'], 'partial')
        self.assertFalse(doc['queue']['coverage']['complete'])
        self.assertEqual(doc['queue']['ready'], ['#1 Issue 1'])
        self.assertIn('Restore', doc['queue']['next_action'])
        self.assert_reads_only()

    def test_empty_repository_and_graphql_errors_are_not_conflated(self):
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['pending_count'], 0)
        self.assertTrue(doc['queue']['coverage']['complete'])
        for output in ('invalid', '{}', '{"errors":[{"message":"private error"}]}'):
            with self.subTest(output=output):
                self.h.rules({'tool': 'gh', 'argv_contains': ['api', 'graphql'], 'stdout': output})
                code, doc, err = self.h.run('status')
                self.assertEqual(code, 0, err)
                self.assertEqual(doc['queue']['state'], 'unavailable')
                self.assertNotIn('ready', doc['queue'])
                self.assertNotIn('private error', json.dumps(doc))

    def test_partial_graphql_data_and_pr_details_are_retained_and_deduplicated(self):
        payload = json.loads(self.page([self.issue(1, ['ai-blocked']),
                                       self.issue(2, ['ai-pr-opened'])]))
        payload['errors'] = [{'message': 'sensitive API failure'}]
        self.h.rules({'tool': 'gh', 'argv_contains': ['api', 'graphql'],
                      # gh exits 1 on GraphQL errors even with usable partial data.
                      'stdout': json.dumps(payload), 'exit': 1},
                     {'tool': 'gh', 'argv_contains': ['comments'],
                      'stdout': json.dumps([{'body': f'https://github.com/{REPO}/pull/64'}])},
                     {'tool': 'gh', 'argv_contains': ['pr', 'view', '64'],
                      'stdout': json.dumps({'number': 64, 'state': 'OPEN',
                                           'url': f'https://github.com/{REPO}/pull/64'})})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['state'], 'partial')
        self.assertEqual(doc['queue']['pending_count'], 2)
        self.assertNotIn('sensitive', json.dumps(doc))
        self.assertEqual(len([c for c in self.h.calls() if c['argv'][:2] == ['pr', 'view']]), 1)
        self.assertNotIn('retry_safe', doc['queue']['pending']['actionable_blocker'][0])
        self.assert_reads_only()

    def test_comment_pagination_and_issue_page_cap(self):
        self.rules([self.issue(1, ['ai-blocked'])],
                   {'tool': 'gh', 'argv_contains': ['comments?per_page=100&page=1'],
                    'stdout': json.dumps([{'body': ''}] * 100)},
                   {'tool': 'gh', 'argv_contains': ['comments?per_page=100&page=2'],
                    'stdout': '[{"body":"<!-- orbi:failure:v1 {\\"retry_safe\\":false} -->"}]'})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertFalse(doc['queue']['pending']['actionable_blocker'][0]['retry_safe'])
        self.assertEqual(doc['queue']['coverage']['details_read'], 2)
        self.h.clear_calls()
        self.h.rules(*[{'tool': 'gh', 'argv_contains': [f'cursor=page{n}'],
                        'stdout': self.page([self.issue(n)], True, f'page{n+1}')}
                       for n in (2, 3)],
                     {'tool': 'gh', 'argv_contains': ['api', 'graphql'],
                      'stdout': self.page([self.issue(1)], True, 'page2')})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['queue']['coverage']['pages_read'], 3)
        self.assertFalse(doc['queue']['coverage']['complete'])
        self.assertIn('page limit', doc['queue']['reason'])
        self.assertEqual(len([c for c in self.h.calls() if c['tool'] == 'gh']), 3)

    def test_bounded_pages_details_and_text_cli(self):
        self.h.rules({'tool': 'gh', 'argv_contains': ['api', 'graphql'],
                      'stdout': self.page([self.issue(1, ['ai-planning'])], True, 'repeat')})
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertFalse(doc['queue']['coverage']['complete'])
        self.assertLessEqual(len([c for c in self.h.calls() if c['tool'] == 'gh']), 3)
        self.rules([self.issue(n, ['ai-blocked']) for n in range(1, 16)],
                   {'tool': 'gh', 'argv_contains': ['comments'], 'exit': 1})
        self.h.clear_calls()
        before = snapshot(self.h.home)
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'status',
                                 '--repo-dir', str(self.h.repo)], env=self.h.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('queue.pending.actionable_blocker=', result.stdout)
        self.assertIn('/unblock', result.stdout)
        self.assertIn('queue.state=partial', result.stdout)
        self.assertLessEqual(len([c for c in self.h.calls() if c['tool'] == 'gh']), 11)
        self.assertEqual(snapshot(self.h.home), before)
        self.assert_reads_only()


class UpdateTests(unittest.TestCase):
    """`/orbi update`: newest official release after stopping workers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = self.fresh(self.tmp.name)
        self.prefix = helper.unit_prefix(helper.derive_unit_name(REPO))
        self.config_before = (self.h.deploy / 'orbi.toml').read_text()

    def fresh(self, name):
        harness = Harness(Path(self.tmp.name) / name)
        self.a = harness.add_deployment_a()
        code, doc, err = harness.run('setup')
        self.assertEqual(code, 0, err)
        harness.clear_calls()
        return harness

    def a_units(self):
        return {name: data for name, data in snapshot(self.h.unit_dir).items()
                if name in {'.'} or name.startswith('orbi-a')}

    def assert_a_unchanged(self):
        self.assertEqual(snapshot(self.a['deploy']), self.a['snapshot'])
        self.assertEqual(self.a_units(), self.a['unit_snapshot'])

    def release_rules(self, *, move=True, units_enabled=True, worker=None, installed=True):
        PauseUpdateTests.pause_rules(self, move=move, installed=installed,
                                    services={1: worker} if worker else {})

    def test_update_with_stop_locks_newest_release_and_keeps_scheduling_inactive(self):
        self.release_rules()
        code, doc, err = self.h.run('update', options=['--stop'])
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['action'], 'update')
        self.assertEqual(doc['status'], 'updated')
        self.assertEqual(doc['previous'], {'track': helper.PIN_TRACK, 'head': PIN})
        self.assertEqual(doc['deployment']['pin'], 'sha:' + NEW_PIN)
        self.assertEqual(doc['deployment']['source'], 'verified')
        self.assertEqual(doc['deployment']['deployed_commit'], NEW_PIN)
        self.assertFalse(doc['activated'])
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + NEW_PIN)
        text = (self.h.deploy / 'orbi.toml').read_text()
        self.assertIn('# Verified retention-capable source; a change is a deliberate operation.', text)
        self.assertEqual(text.replace('sha:' + NEW_PIN, helper.PIN_TRACK), self.config_before)
        self.assertEqual([step['step'] for step in doc['steps']], [
            'preflight_target', 'lock', *(['disable_timer'] * helper.MAX_INSTANCES),
            'verify_quiescent', 'recheck_target', 'set_release_track',
            'sync_engine_source', 'pin_release', 'validate_non_activating',
            'refresh_units'])
        self.assertEqual([c['argv'][0] for c in self.h.calls()
                          if c['tool'] == 'orbi' and c['argv']],
                         ['--version', '--version', 'sync-engine-source', 'check'])
        self.assertEqual(doc['disabled_timers'],
                         [f'{self.prefix}@{i}.timer' for i in range(1, helper.MAX_INSTANCES + 1)])
        for call in self.h.calls():
            if call['tool'] == 'systemctl' and 'disable' in call['argv']:
                self.assertIn('--now', call['argv'])
                self.assertTrue(call['argv'][-1].endswith('.timer'), call)
            for forbidden in ('stop', 'restart', 'kill'):
                self.assertNotIn(forbidden, call['argv'], call)
        self.assert_a_unchanged()

    def test_update_reports_up_to_date_when_the_release_commit_did_not_move(self):
        self.release_rules(move=False)
        code, doc, err = self.h.run('update', options=['--stop'])
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['status'], 'up_to_date')
        self.assertEqual(doc['previous'], {'track': helper.PIN_TRACK, 'head': PIN})
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + PIN)
        self.assertEqual(doc['deployment']['source'], 'verified')
        self.assertNotIn('install-units', [c['argv'][0] for c in self.h.calls()
                                        if c['tool'] == 'orbi' and c['argv']])

    def test_update_refuses_tracked_checkout_changes_before_writes(self):
        dirty = self.fresh('dirty')
        dirty.rules({'tool': 'git', 'argv_contains': ['status', '--porcelain'],
                     'stdout': ' M src/orbi/runner.py\n'})
        before = snapshot(dirty.deploy)
        code, doc, err = dirty.run('update')
        self.assertEqual(code, 2, err)
        self.assertEqual(doc['error']['code'], 'source_dirty')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(dirty.deploy), before)
        self.assertNotIn('sync-engine-source', [c['argv'][0] for c in dirty.calls()
                                                if c['tool'] == 'orbi' and c['argv']])

    def test_update_preview_is_write_free_and_names_the_plan(self):
        self.release_rules()
        before = snapshot(self.h.deploy)
        code, doc, err = self.h.run('update', dry_run=True)
        self.assertEqual(code, 0, err)
        self.assertTrue(doc['dry_run'])
        self.assertEqual(doc['status'], 'planned')
        self.assertEqual(doc['previous'], {'track': helper.PIN_TRACK, 'head': PIN})
        self.assertEqual([step['step'] for step in doc['steps']], [
            'pause_owned_timers', 'cancel_start', 'stop_service', 'verify_quiescent', 'sync_engine_source',
            'refresh_units', 'observe_scheduler', 'activate_deployment'])
        self.assertEqual(snapshot(self.h.deploy), before)
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'orbi'
                          and c['argv'][:1] in (['sync-engine-source'], ['install-units'])])
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'git'
                          and 'fetch' in c['argv']])
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'systemctl'
                          and set(c['argv']) & {'enable', 'disable', 'start', 'stop'}])

    def test_update_failure_after_sync_keeps_partial_receipt_and_no_unit_change(self):
        self.release_rules()
        failure = helper.ControlError('validation_failed', 'fixture check failure')
        with mock.patch.object(helper, 'run_orbi_check', side_effect=failure):
            code, doc, err = self.h.run('update')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'validation_failed')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['original_error'], 'validation_failed')
        self.assertEqual(doc['steps'][-1]['step'], 'validate_non_activating')
        self.assertEqual(doc['steps'][-1]['status'], 'failed')
        completed = [step['step'] for step in doc['steps'] if step['status'] != 'failed']
        self.assertEqual(completed[-2:], ['sync_engine_source', 'pin_release'])
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + NEW_PIN)
        self.assertNotIn('install-units', [c['argv'][0] for c in self.h.calls()
                                           if c['tool'] == 'orbi' and c['argv']])
        self.assertEqual(doc['disabled_timers'],
                         [f'{self.prefix}@{i}.timer' for i in range(1, helper.MAX_INSTANCES + 1)])
        PauseUpdateTests.assert_safe_trace(self)

    def test_update_with_stop_defers_unit_install_for_a_deployment_without_units(self):
        self.release_rules(installed=False)
        code, doc, err = self.h.run('update', options=['--stop'])
        self.assertEqual(code, 0, err)
        self.assertEqual(doc['status'], 'updated')
        steps = {step['step']: step for step in doc['steps']}
        self.assertEqual(steps['refresh_units']['status'], 'deferred')
        self.assertEqual(doc['disabled_timers'], [])
        self.assertIn('next authorized start installs', steps['refresh_units']['reason'])
        self.assertNotIn('install-units', [c['argv'][0] for c in self.h.calls()
                                           if c['tool'] == 'orbi' and c['argv']])
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'systemctl'
                          and 'disable' in c['argv']])
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + NEW_PIN)

    def test_plain_and_explicit_stop_both_refuse_without_sync_on_disable_failure(self):
        for flags in ([], ['--stop']):
            with self.subTest(flags=flags):
                self.h = self.fresh('disable-failure' + str(bool(flags)))
                PauseUpdateTests.pause_rules(self, services={1: 'active'}, extra=[
                    {'tool': 'systemctl', 'argv_contains': ['disable'], 'exit': 1}])
                code, doc, err = self.h.run('update', options=flags)
                self.assertNotEqual(code, 0, doc)
                self.assertEqual(doc['error']['code'], 'command_failed')
                self.assertFalse(any(set(c['argv']) & {'stop', 'sync-engine-source'}
                                     for c in self.h.calls() if c['tool'] in {'orbi', 'systemctl'}))
                PauseUpdateTests.assert_safe_trace(self)

    def test_update_refuses_selection_selectors(self):
        before = snapshot(self.h.deploy)
        code, doc, err = self.h.run('update', options=['--harness', 'pi'])
        self.assertEqual(code, 2, err)
        self.assertEqual(doc['error']['code'], 'invalid_harness_selection')
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.deploy), before)
        self.assertEqual(self.h.config()['engine_source_track'], helper.PIN_TRACK)


class PauseUpdateTests(unittest.TestCase):
    """Explicit pause/update compatibility, with no live host changes."""

    update_flags = ['--stop']

    setUp = UpdateTests.setUp
    a_units = UpdateTests.a_units
    assert_a_unchanged = UpdateTests.assert_a_unchanged

    def fresh(self, name):
        harness = UpdateTests.fresh(self, name)
        self.config_before = (harness.deploy / 'orbi.toml').read_text()
        return harness

    def pause_rules(self, *, timers=None, enabled=None, services=None, jobs='', extra=(),
                    move=True, installed=True):
        paused = self.h.root / 'paused'
        synced = self.h.root / 'synced'
        rules = [*extra,
                 *(r for i in (services or {}) for r in self.h.stop_service_rules(f'{self.prefix}@{i}.service')),
                 {'tool': 'systemctl', 'argv_contains': ['list-units'],
                  'stdout': ''.join(f'{self.prefix}@{i}.service loaded active running Worker\n'
                                    for i in (services or {}))},
                 {'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'stdout': jobs},
                 {'tool': 'systemctl', 'argv_contains': ['disable'],
                  'write': {str(paused): '1'}},
                 {'tool': 'orbi', 'argv_contains': ['sync-engine-source'],
                  'write': {str(synced): '1'} if move else {}},
                 {'tool': 'git', 'argv_contains': ['rev-parse', 'HEAD'],
                  'if_exists': str(synced), 'stdout': NEW_PIN + '\n'}]
        rules += [dict(r, if_exists=str(paused)) for r in self.h.scheduler_rules(
            timers={i: 'inactive' for i in set(timers or {}) | set(enabled or {})},
            services=services, installed=installed)]
        self.h.rules(*rules, *self.h.scheduler_rules(
            timers=timers, enabled=enabled, services=services, installed=installed))

    def update(self, **kwargs):
        return self.h.run('update', options=self.update_flags, **kwargs)

    def assert_safe_trace(self, *, owned_services=()):
        for call in self.h.calls():
            if call['tool'] == 'systemctl':
                self.assertFalse(set(call['argv']) & {'enable', 'start', 'restart', 'kill'}, call)
                if 'stop' in call['argv']:
                    self.assertIn(call['argv'], [['--user', 'stop', unit] for unit in owned_services])
                if 'disable' in call['argv']:
                    self.assertIn(call['argv'][:-1], (['--user', 'disable', '--now', '--no-reload'],
                                                      ['--user', 'disable', '--runtime', '--no-reload']))
                    self.assertTrue(call['argv'][-1].endswith('.timer'), call)
            if call['tool'] == 'orbi':
                self.assertNotIn(call['argv'][:1], (['setup'], ['install-units']), call)
        self.assert_a_unchanged()

    def test_inactive_enabled_and_active_timers_pause_under_lock_before_source_changes(self):
        for state in ('inactive', 'active'):
            with self.subTest(state=state):
                self.h = self.fresh('pause-' + state)
                self.pause_rules(timers={1: state}, enabled={1: True})
                original = helper.rewrite_engine_track
                def rewrite(target, track):
                    self.assertTrue((self.h.root / 'paused').exists())
                    locks = list((self.h.home / '.cache/orbi-control').glob('*.lock'))
                    with locks[0].open('a+') as handle:
                        with self.assertRaises(BlockingIOError):
                            helper.fcntl.flock(handle, helper.fcntl.LOCK_EX | helper.fcntl.LOCK_NB)
                    return original(target, track)
                with mock.patch.object(helper, 'rewrite_engine_track', side_effect=rewrite):
                    code, doc, err = self.update()
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(doc['status'], 'updated')
                self.assertEqual(doc['engine_update'], 'updated')
                self.assertEqual(doc['scheduler_confirmation'], 'stopped')
                self.assertEqual(doc['unit_refresh'], 'deferred')
                self.assertIn('next authorized start', doc['unit_refresh_reason'])
                self.assertFalse(doc['activated'])
                self.assertEqual(doc['previous'], {'track': helper.PIN_TRACK, 'head': PIN})
                self.assertEqual(doc['deployment']['source'], 'verified')
                self.assertEqual(doc['deployment']['deployed_commit'], NEW_PIN)
                self.assertTrue(all(not t['enabled'] and t['active'] == 'inactive'
                                    for t in doc['scheduler']['timers'].values()))
                calls = self.h.calls()
                positions = [next(i for i, c in enumerate(calls) if c['tool'] in ('systemctl', 'orbi')
                                  and word in c['argv']) for word in ('disable', 'sync-engine-source', 'check')]
                self.assertEqual(positions, sorted(positions))
                text = (self.h.deploy / 'orbi.toml').read_text()
                self.assertEqual(text.replace('sha:' + NEW_PIN, helper.PIN_TRACK), self.config_before)
                self.assert_safe_trace()

    def test_already_stopped_updated_or_up_to_date_without_unit_install(self):
        for move, installed in ((True, True), (False, True), (True, False)):
            with self.subTest(move=move, installed=installed):
                self.h = self.fresh('stopped-' + str(move) + str(installed))
                self.pause_rules(move=move, installed=installed)
                code, doc, err = self.update()
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(doc['status'], 'updated' if move else 'up_to_date')
                self.assertEqual(doc['engine_update'], doc['status'])
                self.assertEqual(doc['scheduler_confirmation'], 'stopped')
                self.assertEqual(doc['unit_refresh'], 'deferred')
                self.assert_safe_trace()

    def test_installed_surplus_timer_outside_fixed_scan_is_disabled(self):
        timer = f'{self.prefix}@12.timer'
        self.pause_rules(timers={12: 'active'}, enabled={12: True}, extra=[
            {'tool': 'systemctl', 'argv_contains': ['list-unit-files'],
             'stdout': f'{timer} enabled enabled\n'}])
        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertIn(timer, doc['disabled_timers'])
        self.assertFalse(doc['scheduler']['timers'][timer]['enabled'])
        self.assertEqual(doc['scheduler']['timers'][timer]['active'], 'inactive')
        self.assert_safe_trace()

    def test_workers_and_pending_starts_beyond_scan_quiesce_before_sync(self):
        service = f'{self.prefix}@12.service'
        queued = f'{self.prefix}@13.service'
        cancelled = str(self.h.root / 'cancelled')
        other_job = '73 orbi-a@1.service start waiting\n'
        self.pause_rules(services={12: 'active', 13: 'inactive'}, extra=[
            {'tool': 'systemctl', 'argv_contains': ['cancel', '42'], 'write': {cancelled: '1'}},
            {'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'if_exists': cancelled,
             'stdout': other_job},
            {'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'if_exists': str(self.h.root / 'paused'),
             'stdout': f'42 {queued} start waiting\n' + other_job}], jobs=other_job)
        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['status'], 'updated')
        self.assertEqual(doc['stopped_services'], [service])
        self.assertEqual(doc['pending_services'], [])
        mutations = [c['argv'] for c in self.h.calls() if c['tool'] == 'systemctl'
                     and set(c['argv']) & {'disable', 'cancel', 'stop'}]
        self.assertTrue(mutations[:-2])
        self.assertTrue(all(a[:3] == ['--user', 'disable', '--now'] for a in mutations[:-2]))
        self.assertEqual(mutations[-2:], [['--user', 'cancel', '42'], ['--user', 'stop', service]])
        self.assert_safe_trace(owned_services=[service])

    def test_preview_busy_is_conditional_without_writes_fetch_locks_or_unit_actions(self):
        self.pause_rules(timers={1: 'active'}, enabled={1: True}, services={5: 'active'})
        before = snapshot(self.h.home)
        with mock.patch.object(helper, 'locked', side_effect=AssertionError('preview lock')):
            code, doc, err = self.update(dry_run=True)
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['status'], 'planned')
        self.assertEqual(doc['steps'][0]['step'], 'pause_owned_timers')
        self.assertIn('conditional', [s['status'] for s in doc['steps']])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertFalse([c for c in self.h.calls() if set(c['argv']) &
                          {'disable', 'fetch', 'sync-engine-source', 'install-units'}])
        self.assert_safe_trace()

    def test_unknown_foreign_incomplete_inventory_refuses_before_disable(self):
        service = f'{self.prefix}@5.service'
        for name, rules, error in [
                ('jobs', [{'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'exit': 1}],
                 'scheduler_unavailable'),
                ('bad-job', [{'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'stdout': '???\n'}],
                 'scheduler_unavailable'),
                ('inventory', [{'tool': 'systemctl', 'argv_contains': ['list-units'], 'exit': 1}],
                 'scheduler_unavailable'),
                ('bad-inventory', [{'tool': 'systemctl', 'argv_contains': ['list-unit-files'],
                                    'stdout': 'unreadable\n'}], 'scheduler_unavailable'),
                ('installed-inventory', [{'tool': 'systemctl', 'argv_contains': ['list-unit-files'], 'exit': 1}],
                 'scheduler_unavailable'),
                ('unowned-loaded', [{'tool': 'systemctl', 'argv_contains': ['list-units'],
                                    'stdout': f'{self.prefix}@12.service loaded active running Worker\n'}],
                 'unit_conflict'),
                ('state', [{'tool': 'systemctl', 'argv_contains': ['ActiveState', service],
                            'stdout': 'unknown\n'}], 'scheduler_unavailable'),
                ('timer', [{'tool': 'systemctl', 'argv_contains': ['is-enabled'],
                            'stdout': '', 'exit': 1}], 'scheduler_unavailable')]:
            with self.subTest(name=name):
                self.pause_rules(extra=rules)
                before = snapshot(self.h.home)
                code, doc, err = self.update()
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], error)
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse([c for c in self.h.calls() if 'disable' in c['argv']])
                self.h.clear_calls()
        self.h.rules(*self.h.scheduler_rules(service_config=self.a['config']))
        code, doc, err = self.update()
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'unit_conflict')
        self.assertFalse([c for c in self.h.calls() if 'disable' in c['argv']])

    def test_disable_readback_sync_validation_failures_preserve_partial_evidence(self):
        for name, rules, error in [
                ('disable', [{'tool': 'systemctl', 'argv_contains': ['disable'], 'exit': 1}],
                 'command_failed'),
                ('partial-disable', [{'tool': 'systemctl', 'argv_contains': ['disable', f'{self.prefix}@2.timer'], 'exit': 1}],
                 'command_failed'),
                ('readback', [{'tool': 'systemctl', 'argv_contains': ['is-enabled'],
                              'if_exists': 'PAUSED', 'stdout': '', 'exit': 1}], 'scheduler_unavailable'),
                ('jobs-readback', [{'tool': 'systemctl', 'argv_contains': ['list-jobs'],
                                   'if_exists': 'PAUSED', 'exit': 1}], 'scheduler_unavailable'),
                ('still-enabled', [{'tool': 'systemctl', 'argv_contains': ['is-enabled'],
                                    'stdout': 'enabled\n'}], 'scheduler_unavailable'),
                ('sync', [{'tool': 'orbi', 'argv_contains': ['sync-engine-source'], 'exit': 1}],
                 'sync_engine_source_failed'),
                ('validation', [{'tool': 'orbi', 'argv_contains': ['check'], 'exit': 1}],
                 'validation_failed')]:
            with self.subTest(name=name):
                self.h = self.fresh('fail-' + name)
                for rule in rules:
                    if rule.get('if_exists') == 'PAUSED':
                        rule['if_exists'] = str(self.h.root / 'paused')
                if name == 'sync':
                    rules[0]['write'] = {str(self.h.root / 'synced'): '1'}
                self.pause_rules(enabled={1: True}, extra=rules)
                code, doc, err = self.update()
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], error)
                self.assertTrue(doc['error']['mutated'])
                self.assertEqual(doc['steps'][-1]['status'], 'failed')
                self.assertEqual(bool(doc['disabled_timers']), name != 'disable')
                if name == 'partial-disable':
                    self.assertEqual(doc['disabled_timers'], [f'{self.prefix}@1.timer'])
                    self.assertEqual(doc['steps'][-1]['unit'], f'{self.prefix}@2.timer')
                if name == 'sync':
                    # A failed sync may already have moved HEAD; it is not proof of no change.
                    self.assertTrue((self.h.root / 'synced').exists())
                    self.assertEqual(doc['engine_update'], 'sync_unverified')
                if name not in ('sync', 'validation'):
                    self.assertFalse([c for c in self.h.calls() if 'sync-engine-source' in c['argv']])
                    self.assertEqual(self.h.config()['engine_source_track'], helper.PIN_TRACK)
                self.assertIn('scheduler', doc)
                self.assertIn('resume_command', doc)
                self.assertNotIn('scheduler_confirmation', doc)
                self.assert_safe_trace()

    def test_final_readback_missing_never_claims_stopped(self):
        self.pause_rules(extra=[{'tool': 'systemctl', 'argv_contains': ['list-jobs'],
                                'if_exists': str(self.h.root / 'synced'), 'exit': 1}])
        code, doc, err = self.update()
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['steps'][-1]['step'], 'observe_scheduler')
        self.assertEqual(doc['scheduler']['state'], 'unavailable')
        self.assertNotIn('scheduler_confirmation', doc)
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + NEW_PIN)
        self.assertEqual(shlex.split(doc['repair_command']), ['/orbi', 'update',
                         '--repo-dir', str(self.h.repo), '--config',
                         str(self.h.deploy / 'orbi.toml'), '--stop'])
        self.assert_safe_trace()

    def test_revalidation_under_lock_precedes_disable(self):
        self.pause_rules(enabled={1: True})
        original = helper.locked
        @contextlib.contextmanager
        def changed_after_preflight(ctx, config):
            with original(ctx, config):
                self.pause_rules(enabled={1: True}, extra=[
                    {'tool': 'systemctl', 'argv_contains': ['list-jobs'], 'exit': 1}])
                yield
        with mock.patch.object(helper, 'locked', changed_after_preflight):
            code, doc, err = self.update()
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'scheduler_unavailable')
        self.assertFalse([c for c in self.h.calls() if 'disable' in c['argv']])
        self.assertEqual(self.h.config()['engine_source_track'], helper.PIN_TRACK)

    def test_prerequisite_and_dirty_source_refusals_do_not_pause(self):
        for action, rules in (
                ('dirty', [{'tool': 'git', 'argv_contains': ['status', '--porcelain'],
                            'stdout': ' M src/orbi/runner.py\n'}]),
                ('auth', [{'tool': 'gh', 'argv_contains': ['auth', 'status'], 'exit': 1}])):
            with self.subTest(action=action):
                self.pause_rules(enabled={1: True}, extra=rules)
                before = snapshot(self.h.home)
                code, doc, err = self.update()
                self.assertNotEqual(code, 0, (doc, err))
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse([c for c in self.h.calls() if 'disable' in c['argv']])

    def test_stop_flag_only_update_and_selectors_remain_rejected(self):
        for action in ('status', 'setup', 'start', 'stop'):
            code, doc, err = self.h.run(action, options=['--stop'])
            self.assertNotEqual(code, 0, (doc, err))
            self.assertEqual(doc['error']['code'], 'invalid_stop_selection')
            self.assertFalse(doc['error']['mutated'])
        code, doc, err = self.h.run('update', options=['--stop', '--harness', 'pi'])
        self.assertEqual(doc['error']['code'], 'invalid_harness_selection')
        code, doc, err = self.h.run('update', options=['--stop', '--pi-provider', 'other'])
        self.assertEqual(doc['error']['code'], 'invalid_provider_selection')
        code, doc, err = self.h.run('help', options=['--stop'])
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['options']['--stop']['applies_to'], ['update'])

    def test_public_cli_update_success_preview_and_failure_receipts(self):
        for scenario in ('idle', 'active', 'stop-failure', 'preview', 'dirty'):
            with self.subTest(scenario=scenario):
                self.h = self.fresh('cli-' + scenario)
                # Literal selectors must survive the returned shell-quoted repair command.
                self.h.repo = self.h.repo.rename(self.h.root / 'space $(literal); target')
                config = self.h.deploy / 'orbi.toml'
                config.write_text(config.read_text().replace(str(self.h.root / 'repo'), str(self.h.repo)))
                service = f'{self.prefix}@1.service'
                extra = []
                if scenario == 'dirty':
                    extra.append({'tool': 'git', 'argv_contains': ['status', '--porcelain'],
                                  'stdout': ' M src/orbi/runner.py\n'})
                elif scenario == 'stop-failure':
                    extra.append({'tool': 'systemctl', 'argv_contains': ['stop', service],
                                  'exit': 7, 'stderr': SECRET})
                self.pause_rules(enabled={1: True}, extra=extra,
                                 services={1: 'active'} if scenario in {'active', 'stop-failure'} else {})
                recovery = self.h.deploy / '.orbi/attempt.json'
                recovery.write_text('retained attempt fixture')
                before = snapshot(self.h.home)
                result = subprocess.run([sys.executable, '-B', str(HELPER), 'update', *self.update_flags,
                                         '--repo-dir', str(self.h.repo), '--config', str(config), '--json',
                                         *(['--dry-run'] if scenario == 'preview' else [])],
                                        env=dict(self.h.env), capture_output=True, text=True, timeout=60)
                doc = json.loads(result.stdout)
                self.assertNotIn(SECRET, result.stdout + result.stderr)
                if scenario == 'dirty':
                    self.assertEqual(result.returncode, 2, doc)
                    self.assertEqual(doc['error']['code'], 'source_dirty')
                    self.assertIn('preserve', doc['error']['fix'])
                    self.assertFalse(doc['error']['mutated'])
                    self.assertEqual(snapshot(self.h.home), before)
                elif scenario == 'stop-failure':
                    self.assertNotEqual(result.returncode, 0, doc)
                    self.assertEqual(doc['error']['code'], 'command_failed')
                    self.assertEqual(doc['steps'][-1]['step'], 'stop_service')
                    self.assertEqual(doc['steps'][-1]['unit'], service)
                    self.assertEqual(doc['disabled_timers'],
                                     [f'{self.prefix}@{i}.timer' for i in range(1, helper.MAX_INSTANCES + 1)])
                    self.assertEqual(doc['stopped_services'], [])
                    self.assertEqual(doc['engine_update'], 'not_applied')
                    self.assertEqual(shlex.split(doc['repair_command']), ['/orbi', 'update', '--repo-dir',
                                     str(self.h.repo), '--config', str(config), *self.update_flags])
                    self.assertFalse(any('sync-engine-source' in c['argv'] for c in self.h.calls()))
                    self.assertEqual(self.h.config()['engine_source_track'], helper.PIN_TRACK)
                else:
                    self.assertEqual(result.returncode, 0, (doc, result.stderr))
                    self.assertEqual(doc['status'], 'planned' if scenario == 'preview' else 'updated')
                    if scenario == 'preview':
                        self.assertEqual(snapshot(self.h.home), before)
                        self.assertFalse(any('disable' in c['argv'] for c in self.h.calls()))
                    else:
                        self.assertEqual(doc['scheduler_confirmation'], 'stopped')
                        self.assertEqual(doc['unit_refresh'], 'deferred')
                        self.assertEqual(doc['stopped_services'], [service] if scenario == 'active' else [])
                        self.assertEqual(doc['scheduler']['services'][service]['state'], 'inactive')
                        if scenario == 'active':
                            words = [c['argv'] for c in self.h.calls()]
                            self.assertLess(words.index(['--user', 'stop', service]),
                                            next(i for i, a in enumerate(words) if 'sync-engine-source' in a))
                self.assertEqual(recovery.read_text(), 'retained attempt fixture')
                self.assert_safe_trace(owned_services=[service] if scenario in {'active', 'stop-failure'} else [])


class ExplicitStopUpdateTests(PauseUpdateTests):
    """The compatible spelling must satisfy every default-update safety regression."""

    update_flags = ['--stop']


class SchedulingUpdateTests(unittest.TestCase):
    """Plain command regression: same verified invocation resumes scheduling."""

    setUp = UpdateTests.setUp
    fresh = PauseUpdateTests.fresh
    a_units = UpdateTests.a_units
    assert_a_unchanged = UpdateTests.assert_a_unchanged
    pause_rules = PauseUpdateTests.pause_rules
    assert_safe_trace = PauseUpdateTests.assert_safe_trace
    update = PauseUpdateTests.update
    update_flags = []

    test_unknown_foreign_incomplete_inventory_refuses_before_disable = PauseUpdateTests.test_unknown_foreign_incomplete_inventory_refuses_before_disable
    test_disable_readback_sync_validation_failures_preserve_partial_evidence = PauseUpdateTests.test_disable_readback_sync_validation_failures_preserve_partial_evidence
    test_revalidation_under_lock_precedes_disable = PauseUpdateTests.test_revalidation_under_lock_precedes_disable
    test_prerequisite_and_dirty_source_refusals_do_not_pause = PauseUpdateTests.test_prerequisite_and_dirty_source_refusals_do_not_pause

    def active_rules(self, *, initially_active=True, **kwargs):
        activated = self.h.root / 'activated'
        extra = [*kwargs.pop('extra', []),
            {'tool': 'systemctl', 'argv_contains': ['enable', '--now'],
             'write': {str(activated): '1'}},
            *[dict(r, if_exists=str(activated)) for r in self.h.scheduler_rules(
                timers={1: 'active'}, enabled={1: True})]]
        PauseUpdateTests.pause_rules(self, timers={1: 'active'} if initially_active else None,
                                     enabled={1: True} if initially_active else None, extra=extra, **kwargs)

    latest_release = {'tool': 'git', 'argv_contains': ['ls-remote', '--tags', OFFICIAL, 'refs/tags/v*'],
                      'stdout': (f'{PIN}\trefs/tags/v0.7.41\n'
                                 f'{OLD_PIN}\trefs/tags/v0.7.42\n'
                                 f'{NEW_PIN}\trefs/tags/v0.7.42^{{}}\n')}

    def test_cli_start_updates_stopped_deployment_before_activation(self):
        self.active_rules(initially_active=False, extra=[self.latest_release])
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'start', '--json'],
                                cwd=self.h.repo, env=self.h.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['action'], 'start')
        self.assertEqual(doc['status'], 'started')
        selected = next(s for s in doc['steps'] if s['step'] == 'set_release_track')
        self.assertEqual(selected['track'], 'tag:v0.7.42')
        self.assertEqual(self.h.config()['engine_source_track'], 'sha:' + NEW_PIN)
        timer = doc['scheduler']['timers'][f'{self.prefix}@1.timer']
        self.assertTrue(timer['enabled'])
        self.assertEqual(timer['active'], 'active')
        self.assert_start_order()
        self.assert_a_unchanged()

    def assert_start_order(self, *, running=False):
        calls = self.h.calls()
        operations = [(c['tool'], c['argv'][0] if c['tool'] == 'orbi' else c['argv'][1])
                      for c in calls if c['tool'] in {'orbi', 'systemctl'}]
        expected = ([('systemctl', 'disable'), ('systemctl', 'stop')] if running else []) + [
            ('orbi', 'sync-engine-source'), ('orbi', 'check'), ('orbi', 'setup'),
            ('orbi', 'install-units'), ('systemctl', 'enable')]
        positions = [operations.index(operation) for operation in expected]
        self.assertEqual(positions, sorted(positions))

    def test_start_current_enabled_active_deployment_does_not_mutate(self):
        for services in ({}, {1: 'active'}):
            with self.subTest(services=services):
                self.active_rules(move=False, services=services)
                before = snapshot(self.h.home)
                self.h.clear_calls()
                code, doc, err = self.h.run('start')
                self.assertEqual(code, 0, (doc, err))
                self.assertEqual(doc['status'], 'already-running')
                self.assertFalse(doc['activated'])
                self.assertEqual(snapshot(self.h.home), before)
                calls = self.h.calls()
                self.assertTrue(any(c['tool'] == 'git' and 'ls-remote' in c['argv'] for c in calls))
                self.assertFalse([c for c in calls if
                                  c['tool'] == 'orbi' and c['argv'][:1] != ['--version']
                                  or c['tool'] == 'systemctl' and c['argv'][1] in {
                                      'enable', 'disable', 'start', 'stop', 'cancel', 'restart', 'kill'}])

    def test_start_does_not_report_current_with_redirected_engine_git_state(self):
        self.active_rules(move=False, services={1: 'active'})
        env_file = self.h.deploy / '.orbi/env'
        with env_file.open('a') as stream:
            stream.write(f'\nGIT_DIR={self.h.repo}/.git\n')
        before = snapshot(self.h.home)
        self.h.clear_calls()

        code, doc, err = self.h.run('start')

        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'source_unavailable')
        self.assertIn('Git environment redirects checkout state', doc['error']['message'])
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assert_safe_trace()

    def test_start_newer_release_stops_workers_before_sync_and_restores_scheduling(self):
        self.active_rules(services={1: 'active'}, extra=[self.latest_release])
        code, doc, err = self.h.run('start')
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['stopped_services'], [f'{self.prefix}@1.service'])
        self.assertEqual(doc['deployment']['pin'], 'sha:' + NEW_PIN)
        self.assertEqual(doc['activation'], 'started')
        self.assert_start_order(running=True)
        self.assert_a_unchanged()

    def test_start_reports_started_when_refreshed_timer_ticks_before_readback(self):
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace('max_concurrency = 1', 'max_concurrency = 6'))
        installed = str(self.h.root / 'installed')
        service = f'{self.prefix}@6.service'
        timers = [f'{self.prefix}@{i}.timer' for i in range(1, 7)]
        self.pause_rules(timers={6: 'inactive'}, extra=[self.latest_release,
            *self.h.enable_timer_rules(*timers),
            {'tool': 'orbi', 'argv_contains': ['install-units'], 'write': {installed: '1'}},
            {'tool': 'systemctl', 'argv_contains': ['show', 'ActiveState', service],
             'if_exists': installed, 'stdout': 'active\n'},
        ])
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'start', '--json'],
                                cwd=self.h.repo, env=self.h.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        doc = json.loads(result.stdout)
        self.assertEqual(doc['status'], 'started')
        self.assertTrue(doc['activated'])
        self.assertEqual(doc['scheduler']['services'][service]['state'], 'active')
        self.assertEqual(doc['first_tick'], 'already-active')
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'systemctl'
                          and c['argv'][:2] == ['--user', 'start']])

    def test_start_refuses_sync_from_a_parent_checkout_before_stopping_work(self):
        self.active_rules(services={1: 'active'}, extra=[self.latest_release,
            {'tool': 'git', 'argv_contains': [str(self.h.deploy), 'rev-parse', '--show-toplevel'],
             'stdout': str(self.h.deploy.parent) + '\n'},
        ])
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('start')
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'source_unavailable')
        self.assertIn('not its own Git checkout root', doc['error']['message'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assert_safe_trace()
        self.assertFalse(doc['disabled_timers'])
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'orbi'
                          and c['argv'][:1] == ['sync-engine-source']])

    def test_start_updates_a_literal_string_pin(self):
        config = self.h.deploy / 'orbi.toml'
        before = config.read_text().replace(f'"sha:{PIN}"', f"'sha:{PIN}'  # retain comment")
        config.write_text(before)
        self.active_rules(initially_active=False, extra=[self.latest_release])

        code, doc, err = self.h.run('start')

        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['status'], 'started')
        self.assertEqual(config.read_text(), before.replace(f'sha:{PIN}', f'sha:{NEW_PIN}'))
        self.assert_start_order()

    def test_start_refuses_unwritable_track_before_stopping_workers(self):
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace(f'engine_source_track = "sha:{PIN}"\n', ''))
        self.active_rules(services={1: 'active'}, extra=[self.latest_release])
        before = snapshot(self.h.home)

        code, doc, err = self.h.run('start')

        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'config_invalid')
        self.assertEqual(doc['activation'], 'none')
        self.assertEqual(snapshot(self.h.home), before)
        self.assertFalse([c for c in self.h.calls() if c['tool'] == 'systemctl'
                          and c['argv'][1] in {'disable', 'stop', 'cancel'}])
        self.assert_safe_trace()

    def test_start_refuses_to_validate_a_different_config_than_the_units_will_run(self):
        for override in ('alternate-config', 'environment-file'):
            with self.subTest(override=override):
                self.h = self.fresh(override)
                config = self.h.deploy / 'orbi.toml'
                alternate = self.h.deploy / 'other.toml'
                if override == 'alternate-config':
                    config = config.rename(alternate)
                    self.pause_rules(installed=False, extra=[self.latest_release])
                else:
                    env_file = self.h.deploy / '.orbi/env'
                    with env_file.open('a') as stream:
                        stream.write(f'\nORBI_CONFIG={alternate}\n')
                    self.active_rules(initially_active=False, extra=[self.latest_release])
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('start', config=config)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], 'config_mismatch')
                self.assertEqual(doc['activation'], 'none')
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse([c for c in self.h.calls() if c['tool'] == 'orbi'
                                  and c['argv'][:1] != ['--version']])
                self.assert_safe_trace()

    def test_start_failed_release_transaction_does_not_activate_and_names_bound_repair(self):
        for command, error in (('sync-engine-source', 'sync_engine_source_failed'),
                               ('check', 'validation_failed'),
                               (None, 'release_unverified')):
            with self.subTest(error=error):
                self.h = self.fresh(error.replace('check', 'validation'))
                failed = [{'tool': 'orbi', 'argv_contains': [command + ' --config'],
                           'exit': 1, 'stderr': SECRET}] if command else []
                self.active_rules(initially_active=False, move=bool(command),
                                  extra=[self.latest_release, *failed])
                config = self.h.deploy / 'orbi.toml'
                repair = f'/orbi start --repo-dir {shlex.quote(str(self.h.repo))} --config {shlex.quote(str(config))}'
                result = subprocess.run([sys.executable, '-B', str(HELPER), 'start', '--json'],
                                        cwd=self.h.repo, env=self.h.env,
                                        capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                doc = json.loads(result.stdout)
                self.assertEqual(doc['error']['code'], error)
                self.assertEqual(doc['activation'], 'none')
                self.assertEqual(doc['repair_command'], repair)
                self.assertIn(repair, doc['error']['fix'])
                self.assertNotIn(SECRET, result.stdout + result.stderr)
                self.assert_safe_trace()

                if command == 'sync-engine-source':
                    self.active_rules(initially_active=False, extra=[self.latest_release])
                    _, *args = shlex.split(doc['repair_command'])
                    restored = subprocess.run([sys.executable, '-B', str(HELPER), *args, '--json'],
                                              cwd=self.h.root, env=self.h.env,
                                              capture_output=True, text=True, timeout=45)
                    self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
                    recovered = json.loads(restored.stdout)
                    self.assertEqual(recovered['deployment']['pin'], 'sha:' + NEW_PIN)
                    self.assertEqual(recovered['activation'], 'started')

    def test_plain_enabled_active_idle_updates_validates_and_restores_in_one_invocation(self):
        self.active_rules()
        self.assertFalse((self.h.repo / 'orbi.toml').exists())
        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['engine_update'], 'updated')
        self.assertEqual(doc['activation'], 'started')
        self.assertTrue(doc['activated'])
        self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')
        timer = doc['scheduler']['timers'][f'{self.prefix}@1.timer']
        self.assertTrue(timer['enabled'])
        self.assertEqual(timer['active'], 'active')
        self.assertEqual(doc['scheduler']['inventory']['counts']['running_services']['value'], 0)
        calls = self.h.calls()
        words = [c['argv'] for c in calls]
        check = next(i for i, a in enumerate(words) if 'check' in a)
        enable = next(i for i, a in enumerate(words) if 'enable' in a)
        self.assertLess(check, enable)
        self.assertEqual(sum('sync-engine-source' in a for a in words), 1)
        self.assertEqual(sum(c['tool'] == 'orbi' and 'check' in c['argv'] for c in calls), 1)
        self.assertFalse(any(set(a) & {'stop', 'restart', 'kill', 'start'} for a in words))
        self.assertNotIn('resume_command', doc)
        self.assert_a_unchanged()

    def test_active_worker_stops_then_same_invocation_activates(self):
        self.active_rules(services={1: 'active'})
        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['activation'], 'started')
        self.assertEqual(doc['stopped_services'], [f'{self.prefix}@1.service'])
        self.assertEqual(doc['pending_services'], [])
        self.assert_a_unchanged()

    def test_already_current_active_release_also_restores_scheduling(self):
        self.active_rules(move=False)
        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['engine_update'], 'up_to_date')
        self.assertEqual(doc['activation'], 'started')
        self.assertEqual(doc['deployment']['deployed_commit'], PIN)

    def test_plain_cli_update_restarts_scheduling_after_stop(self):
        self.active_rules(services={1: 'active'})
        command = [sys.executable, '-B', str(HELPER)]
        stop = subprocess.run([*command, 'stop', '--json'], cwd=self.h.repo, env=self.h.env,
                              capture_output=True, text=True, timeout=45)
        self.assertEqual(stop.returncode, 0, stop.stdout + stop.stderr)
        stopped = json.loads(stop.stdout)
        self.assertEqual(stopped['status'], 'stopped')
        timer = f'{self.prefix}@1.timer'
        self.assertIn(timer, stopped['disabled_timers'])
        self.assertEqual(stopped['stopped_services'], [f'{self.prefix}@1.service'])
        result = subprocess.run([*command, 'update', '--json'], cwd=self.h.repo, env=self.h.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['engine_update'], 'updated')
        self.assertEqual(doc['activation'], 'started')
        self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')
        self.assertTrue(doc['scheduler']['timers'][timer]['enabled'])
        self.assertEqual(doc['scheduler']['timers'][timer]['active'], 'active')
        self.assert_a_unchanged()

    def test_plain_cli_update_restarts_scheduling_after_failed_sync(self):
        self.active_rules(extra=[{'tool': 'orbi', 'argv_contains': ['sync-engine-source'], 'exit': 1}])
        command = [sys.executable, '-B', str(HELPER), 'update']
        failed = subprocess.run(command, cwd=self.h.repo, env=self.h.env,
                                capture_output=True, text=True, timeout=45)
        self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
        self.assertIn('Error sync_engine_source_failed:', failed.stderr)
        self.assertIn('Engine: sync_unverified', failed.stderr)
        self.assertIn('after repairing the cause, run /orbi update --repo-dir', failed.stderr)
        self.assertEqual(self.h.config()['engine_source_track'], 'release')
        self.assert_safe_trace()

        self.active_rules()  # Restore sync; the timer stays paused until enabled.
        result = subprocess.run([*command, '--json'], cwd=self.h.repo, env=self.h.env,
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['deployment']['pin'], 'sha:' + NEW_PIN)
        self.assertEqual(doc['activation'], 'started')
        self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')

    def test_explicit_stop_retry_guidance_preserves_opt_out(self):
        service = f'{self.prefix}@1.service'
        self.active_rules(services={1: 'active'}, extra=[
            {'tool': 'systemctl', 'argv_contains': ['stop', service], 'exit': 1}])
        code, doc, err = self.h.run('update', options=['--stop'])
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(shlex.split(doc['repair_command'])[-1], '--stop')
        self.assert_safe_trace(owned_services=[service])
        self.active_rules(services={1: 'active'})
        code, doc, err = self.h.run('update', options=['--stop'])
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['activation'], 'held')
        self.assertEqual(doc['activation_reason'], 'explicit --stop')
        self.assertEqual(doc['next_action'], 'Leave scheduling stopped.')
        self.assertTrue(all(not timer['enabled'] and timer['active'] == 'inactive'
                            for timer in doc['scheduler']['timers'].values()))
        self.assert_safe_trace(owned_services=[service])

    def test_target_drift_while_quiescing_refuses_source_sync_and_releases_lock(self):
        config = self.h.deploy / 'orbi.toml'
        stopped = self.h.stop_service_rules(f'{self.prefix}@1.service')[0]
        stopped['write'][str(config)] = config.read_text().replace('max_concurrency = 1', 'max_concurrency = 2')
        self.active_rules(services={1: 'active'}, extra=[stopped])
        code, doc, err = self.update()
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['error']['code'], 'target_changed')
        self.assertFalse(any('sync-engine-source' in c['argv'] for c in self.h.calls()))
        for path in (self.h.home / '.cache/orbi-control').glob('*.lock'):
            with path.open('a+') as handle:
                helper.fcntl.flock(handle, helper.fcntl.LOCK_EX | helper.fcntl.LOCK_NB)
                helper.fcntl.flock(handle, helper.fcntl.LOCK_UN)

    def test_updated_but_partial_or_unknown_start_never_claims_success_or_stops_workers(self):
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                self.h = self.fresh('start-failure-' + str(unknown))
                config = self.h.deploy / 'orbi.toml'
                config.write_text(config.read_text().replace('max_concurrency = 1', 'max_concurrency = 2'))
                self.active_rules(extra=[{'tool': 'systemctl', 'argv_contains': ['enable --now', '@2.timer'], 'exit': 1}])
                if unknown:
                    self.active_rules(extra=[{'tool': 'systemctl', 'argv_contains': ['list-jobs'],
                                             'if_exists': str(self.h.root / 'activated'), 'exit': 1}])
                code, doc, err = self.update()
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['engine_update'], 'updated')
                self.assertEqual(doc['engine_revision'], NEW_PIN)
                self.assertEqual(doc['activation'], 'possible')
                self.assertEqual(doc['error']['code'], 'scheduler_unavailable' if unknown else 'command_failed')
                self.assertTrue(doc['error']['mutated'])
                self.assertIn('/orbi start --repo-dir', doc['repair_command'])
                self.assertEqual(doc['scheduler']['state'], 'unavailable' if unknown else 'ok')
                if not unknown:
                    self.assertTrue(doc['scheduler']['timers'][f'{self.prefix}@1.timer']['enabled'])
                    self.assertFalse(doc['scheduler']['timers'][f'{self.prefix}@2.timer']['enabled'])
                self.assertFalse(any(set(c['argv']) & {'start', 'stop', 'restart', 'kill'} for c in self.h.calls()))

    def test_plain_update_activates_initially_inactive_timers_but_preview_does_not(self):
        self.active_rules(initially_active=False)
        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['activation'], 'started')
        self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')
        self.h = self.fresh('preview-active')
        self.active_rules(services={1: 'active'})
        before = snapshot(self.h.home)
        with mock.patch.object(helper, 'quiesce_locked', side_effect=AssertionError('preview quiesced')):
            code, doc, err = self.h.run('update', dry_run=True)
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['activation'], 'conditional')
        self.assertEqual(snapshot(self.h.home), before)
        self.assert_safe_trace()

    def test_text_receipt_names_stopped_worker_and_applied_engine(self):
        self.active_rules(services={1: 'active'})
        code, text, err = self.h.run('update', json_mode=False)
        self.assertEqual(code, 0, err)
        self.assertIn(str(self.h.deploy / 'orbi.toml'), text.splitlines()[0])
        self.assertIn(f'Stopped workers: {self.prefix}@1.service', text)
        self.assertIn(NEW_PIN, text)
        self.assertIn('enabled_active', text)
        self.assertNotIn('scheduler.inventory', text)
        self.assertEqual(text.count('Next:'), 1)

    def test_public_bare_cli_unique_external_target_updates_then_verifies_timers(self):
        self.active_rules()
        # Real entry point, from the repository, without config or repo selectors.
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'update', '--json'],
                                cwd=self.h.repo, env=self.h.env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['deployment']['config'], str(self.h.deploy / 'orbi.toml'))
        self.assertEqual(doc['engine_update'], 'updated')
        self.assertEqual(doc['activation'], 'started')
        self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')
        self.assertNotIn('resume_command', doc)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_config_only_cli_update_uses_config_checkout_from_unrelated_directory(self):
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace(
            f'repo_dir = {json.dumps(str(self.h.repo))}',
            f'repo_dir = {json.dumps(os.path.relpath(self.h.repo, config.parent))}'))
        # A caller outside Git has no origin to use as a fallback.
        unrelated = self.h.root / 'unrelated'
        unrelated.mkdir()
        self.active_rules(extra=[{'tool': 'git', 'argv_contains': [str(unrelated)], 'exit': 1}])
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'update', '--config',
                                 os.path.relpath(config, unrelated), '--json'], cwd=unrelated,
                                env=self.h.env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['repo'], REPO)
        self.assertEqual(doc['deployment']['config'], str(config))
        self.assertEqual(doc['engine_update'], 'updated')
        self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')
        self.assert_a_unchanged()

    def test_wait_update_handles_natural_drain_deadline_and_preview(self):
        service = f'{self.prefix}@1.service'
        timer = f'{self.prefix}@1.timer'
        for scenario in ('finished', 'timeout', 'preview'):
            with self.subTest(scenario=scenario):
                self.h = self.fresh('wait-' + scenario)
                self.active_rules(services={1: 'active'})
                config = self.h.deploy / 'orbi.toml'
                log = self.h.deploy / 'lifecycle.log'
                prior_receipts = log.read_text().splitlines()
                before = snapshot(self.h.home)
                out, err = io.StringIO(), io.StringIO()
                elapsed, sleeps = 0, []

                def sleep(seconds):
                    nonlocal elapsed
                    self.assertLess(len(sleeps), 2, 'wait did not finish or honor its deadline')
                    self.assertTrue((self.h.root / 'paused').exists())
                    self.assertFalse((self.h.root / 'synced').exists())
                    lock, = (self.h.home / '.cache/orbi-control').glob('*.lock')
                    with lock.open('a+') as handle:
                        with self.assertRaises(BlockingIOError):
                            helper.fcntl.flock(handle, helper.fcntl.LOCK_EX | helper.fcntl.LOCK_NB)
                    sleeps.append(seconds)
                    # Model a slow wakeup so the last sleep must fit the remaining bound.
                    elapsed += 1790 if scenario == 'timeout' and len(sleeps) == 1 else seconds

                run = helper.Context.run

                def run_with_worker(ctx, argv, **kwargs):
                    if (scenario == 'finished' and len(sleeps) == 2 and argv[0] == 'systemctl'
                            and {'show', 'ActiveState', service} <= set(argv)):
                        return subprocess.CompletedProcess(argv, 0, 'inactive\n', '')
                    return run(ctx, argv, **kwargs)

                clock = mock.Mock(monotonic=lambda: elapsed, sleep=sleep)
                with mock.patch.object(helper, 'time', clock, create=True), \
                        mock.patch.object(helper.Context, 'run', run_with_worker):
                    code = helper.main(['update', '--config', str(config), '--wait', '--json',
                                        *(['--dry-run'] if scenario == 'preview' else [])],
                                       cwd=self.h.root, env=self.h.env, platform='linux',
                                       stdout=out, stderr=err)
                doc = json.loads(out.getvalue())
                calls = [c['argv'] for c in self.h.calls()]
                self.assertFalse(any({'stop', 'kill', 'restart'} & set(a) for a in calls))
                self.assert_a_unchanged()
                if scenario == 'preview':
                    self.assertEqual(code, 0, doc)
                    steps = [s['step'] for s in doc['steps']]
                    self.assertIn('wait_for_workers', steps)
                    self.assertNotIn('stop_service', steps)
                    self.assertEqual(sleeps, [])
                    self.assertEqual(snapshot(self.h.home), before)
                    continue
                self.assertGreaterEqual(err.getvalue().count('still finishing'), 2)
                self.assertIn(timer, doc['disabled_timers'])
                self.assertEqual(doc['stopped_services'], [])
                receipts = log.read_text().splitlines()
                self.assertEqual(receipts[:-1], prior_receipts)
                self.assertEqual(len(receipts), len(prior_receipts) + 1)
                entry = json.loads(receipts[-1])
                self.assertEqual(entry['action'], 'update')
                self.assertIn('--wait', entry['argv'])
                self.assertEqual(entry['result'], doc.get('status') or doc['error']['code'])
                if scenario == 'timeout':
                    self.assertNotEqual(code, 0, doc)
                    self.assertEqual(sleeps, [60, 10])
                    self.assertEqual(doc['error']['code'], 'update_busy')
                    self.assertIn('Update not applied: 1 worker(s)', doc['error']['message'])
                    self.assertIn('still finishing', doc['error']['message'])
                    self.assertIn('--wait', shlex.split(doc['repair_command']))
                    self.assertEqual(doc['engine_update'], 'not_applied')
                    self.assertEqual(doc['scheduler']['services'][service]['state'], 'active')
                    self.assertEqual(doc['scheduler']['timers'][timer]['active'], 'inactive')
                    self.assertFalse(doc['scheduler']['timers'][timer]['enabled'])
                    self.assertFalse(any({'sync-engine-source', 'enable'} & set(a) for a in calls))
                    self.assertEqual(self.h.config()['engine_source_track'], helper.PIN_TRACK)
                else:
                    self.assertEqual(code, 0, doc)
                    self.assertEqual(sleeps, [60, 60])
                    self.assertEqual(doc['engine_update'], 'updated')
                    self.assertEqual(doc['scheduler_confirmation'], 'enabled_active')
                    self.assertEqual(sum('sync-engine-source' in a for a in calls), 1)

    def test_missing_duplicate_and_conflicting_config_never_guess_or_pause(self):
        for kind in ('missing', 'duplicate', 'conflicting'):
            with self.subTest(kind=kind):
                self.h = self.fresh('selection-' + kind)
                self.active_rules()
                options = {}
                if kind == 'missing':
                    options['config'] = self.h.root / 'missing.toml'
                elif kind == 'conflicting':
                    options['config'] = self.a['config']
                else:
                    duplicate = self.h.data_home / 'orbi-duplicate'
                    duplicate.mkdir()
                    (duplicate / 'orbi.toml').write_bytes((self.h.deploy / 'orbi.toml').read_bytes())
                before = snapshot(self.h.home)
                code, doc, err = self.h.run('update', **options)
                self.assertNotEqual(code, 0, (doc, err))
                self.assertEqual(doc['error']['code'], {'missing': 'config_missing',
                                 'duplicate': 'ambiguous_deployment', 'conflicting': 'config_mismatch'}[kind])
                self.assertEqual(snapshot(self.h.home), before)
                self.assertFalse(any('disable' in c['argv'] for c in self.h.calls()))


    def test_unresolved_existing_start_gate_holds_activation_after_engine_validation(self):
        self.active_rules()
        with mock.patch.object(helper, 'start_plan', side_effect=helper.ControlError(
                'gate_unresolved', 'fixture existing start gate unresolved', fix='resolve the recorded gate')):
            code, doc, err = self.update()
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['engine_update'], 'updated')
        self.assertEqual(doc['error']['code'], 'gate_unresolved')
        self.assert_safe_trace()

    def test_update_removes_leftover_maintenance_file_without_reading_it(self):
        self.active_rules()
        ctx = helper.Context(env=self.h.env)
        target = helper.deployment_from(self.h.deploy / 'orbi.toml')
        with helper.locked(ctx, target.config_path):
            pass
        lock, = (self.h.home / '.cache/orbi-control').glob('*.lock')
        legacy = lock.with_suffix('.maintenance.json')
        legacy.write_bytes(b'\xff')
        code, doc, err = self.update(dry_run=True)
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(legacy.read_bytes(), b'\xff')

        code, doc, err = self.update()
        self.assertEqual(code, 0, (doc, err))
        self.assertEqual(doc['activation'], 'started')
        self.assertFalse(legacy.exists())

    def test_stop_post_validation_failure_text_preserves_pause_choice(self):
        self.pause_rules(extra=[{'tool': 'systemctl', 'argv_contains': ['list-jobs'],
                                'if_exists': str(self.h.root / 'synced'), 'exit': 1}])
        code, text, err = self.h.run('update', options=['--stop'], json_mode=False)
        self.assertNotEqual(code, 0, text + err)
        self.assertIn('Engine validated; scheduling remains stopped or unverified.', err)
        self.assertIn('/orbi update --repo-dir', err)
        self.assertIn('--stop', err)
        self.assertNotIn('/orbi start', err)
        self.assertNotIn('start failed', err)
        self.assertEqual(err.count('Next:'), 1)
        self.assert_safe_trace()

    def test_repair_command_preserves_literal_update_words_in_paths(self):
        original_repo = self.h.repo
        self.h.repo = self.h.repo.rename(self.h.root / 'orbi update --stop')
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace(str(original_repo), str(self.h.repo)))
        self.active_rules(extra=[{'tool': 'systemctl', 'argv_contains': ['enable --now'], 'exit': 1}])
        code, doc, err = self.update()
        self.assertNotEqual(code, 0, (doc, err))
        self.assertEqual(doc['engine_update'], 'updated')
        self.assertEqual(shlex.split(doc['repair_command']), ['/orbi', 'start',
                         '--repo-dir', str(self.h.repo), '--config', str(config)])
        self.assertFalse(any(set(c['argv']) & {'start', 'stop', 'restart', 'kill'}
                             for c in self.h.calls()))

    def test_start_failure_text_separates_validated_revision_and_bound_repair(self):
        self.active_rules(extra=[{'tool': 'systemctl', 'argv_contains': ['enable --now'], 'exit': 1}])
        code, text, err = self.h.run('update', json_mode=False)
        self.assertNotEqual(code, 0, text + err)
        self.assertIn(str(self.h.deploy / 'orbi.toml'), err.splitlines()[0])
        self.assertIn('Engine validated; start failed', err)
        self.assertIn(NEW_PIN, err)
        self.assertIn('activation: possible', err)
        self.assertIn('/orbi start --repo-dir', err)
        self.assertEqual(err.count('Next:'), 1)
        self.assertNotIn('scheduler.inventory', err)
        self.assertNotIn(SECRET, text + err)
        self.assertFalse(any(set(c['argv']) & {'start', 'stop', 'restart', 'kill'} for c in self.h.calls()))


class SetTests(unittest.TestCase):
    setUp = UpdateTests.setUp
    fresh = PauseUpdateTests.fresh
    a_units = UpdateTests.a_units
    assert_a_unchanged = UpdateTests.assert_a_unchanged

    def set_command(self, *args, json_mode=True):
        out, err = io.StringIO(), io.StringIO()
        code = helper.main(['set', *map(str, args), *(['--json'] if json_mode else [])],
                           env=self.h.env, platform='linux', cwd=self.h.root,
                           stdout=out, stderr=err)
        return code, json.loads(out.getvalue()) if json_mode else out.getvalue(), err.getvalue()

    def test_cli_shrinks_five_slots_to_one_with_backup_and_no_engine_sync(self):
        config = self.h.deploy / 'orbi.toml'
        before = config.read_text().replace('max_concurrency = 1', 'max_concurrency = 5 # keep this')
        config.write_text(before)
        config.chmod(0o640)
        slots = dict.fromkeys(range(1, 6), 'active')
        PauseUpdateTests.pause_rules(self, timers=slots, enabled=dict.fromkeys(slots, True),
                                     extra=self.h.enable_timer_rules(f'{self.prefix}@1.timer'))
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'set', 'kit', 'slots', '1', '--json'],
                                cwd=self.h.root, env=self.h.env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        doc = json.loads(result.stdout)
        self.assertEqual(doc['action'], 'set')
        self.assertEqual(doc['change']['old'], {'max_concurrency': 5})
        self.assertEqual(doc['change']['new'], {'max_concurrency': 1})
        backup = Path(doc['change']['backup'])
        self.assertEqual(backup.parent, config.parent)
        self.assertRegex(backup.name, r'^orbi\.toml\.bak-\d{8}T\d{6}\d*Z$')
        self.assertEqual(backup.read_text(), before)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(config.stat().st_mode & 0o777, 0o640)
        self.assertEqual(config.read_text(), before.replace('max_concurrency = 5', 'max_concurrency = 1'))
        timers = doc['scheduler']['timers']
        self.assertEqual({name for name, item in timers.items() if item['active'] == 'active' or item['enabled']},
                         {f'{self.prefix}@1.timer'})
        self.assertEqual(set(doc['disabled_timers']), {f'{self.prefix}@{i}.timer' for i in slots})
        calls = [call['argv'] for call in self.h.calls()]
        self.assertNotIn('sync-engine-source', [argv[0] for argv in calls if argv])
        self.assertIn(['check', '--config', str(config)], calls)
        self.assert_a_unchanged()

    def test_model_change_drains_under_lock_then_checks_the_saved_selection(self):
        config = self.h.deploy / 'orbi.toml'
        config.write_bytes(config.read_bytes() + b'\n[unrelated]\npi_model = "nested"\n')
        before = config.read_bytes()
        metadata = self.h.deploy / '.orbi/pi-providers.json'
        catalog = json.loads(metadata.read_text())
        model = 'vendor/another-model'
        provider = catalog['providers']['openrouter']
        catalog['providers']['alternate'] = {**provider, 'models': [{**provider['models'][0], 'id': model}]}
        metadata.write_text(json.dumps(catalog))
        service = f'{self.prefix}@1.service'
        PauseUpdateTests.pause_rules(self, timers={1: 'active'}, enabled={1: True}, services={1: 'active'},
                                     extra=self.h.enable_timer_rules(f'{self.prefix}@1.timer'))
        run = helper.Context.run
        sleeps = []

        def assert_locked():
            lock, = (self.h.home / '.cache/orbi-control').glob('*.lock')
            with lock.open('a+') as handle:
                with self.assertRaises(BlockingIOError):
                    helper.fcntl.flock(handle, helper.fcntl.LOCK_EX | helper.fcntl.LOCK_NB)

        def sleep(seconds):
            self.assertFalse(sleeps, 'workers did not drain')
            self.assertEqual(config.read_bytes(), before)
            self.assertTrue((self.h.root / 'paused').exists())
            self.assertFalse(list(config.parent.glob('orbi.toml.bak-*')))
            assert_locked()
            sleeps.append(seconds)

        def fake_run(ctx, argv, **kwargs):
            if sleeps and argv[0] == 'systemctl' and {'show', 'ActiveState', service} <= set(argv):
                return subprocess.CompletedProcess(argv, 0, 'inactive\n', '')
            if 'check' in argv and Path(argv[0]).name == 'orbi':
                assert_locked()
                self.assertEqual(self.h.config()['pi_model'], model)
                self.assertEqual(self.h.config()['pi_thinking'], 'high')
                backup, = config.parent.glob('orbi.toml.bak-*')
                self.assertEqual(backup.read_bytes(), before)
            if argv[0] == 'systemctl':
                self.assertFalse({'stop', 'restart', 'kill'} & set(argv))
            return run(ctx, argv, **kwargs)

        with mock.patch.object(helper, 'time', mock.Mock(sleep=sleep, monotonic=lambda: 0)), \
                mock.patch.object(helper.Context, 'run', fake_run):
            code, text, err = self.set_command(self.prefix, 'model', f'alternate/{model}', 'high', json_mode=False)
        self.assertEqual(code, 0, text + err)
        self.assertIn('pi_provider: "openrouter" -> "alternate"', text)
        self.assertIn('pi_model: "vendor/model-a" -> "vendor/another-model"', text)
        self.assertEqual(sleeps, [60])
        self.assertEqual(self.h.config()['unrelated'], {'pi_model': 'nested'})
        self.assertEqual(self.h.config()['engine_source_track'], helper.PIN_TRACK)

    def test_metered_model_change_requires_flag_and_obeys_allowlist(self):
        config = self.h.deploy / 'orbi.toml'
        subscription = config.read_text().replace('pi_provider = "openrouter"', 'pi_provider = "openai-codex"')
        config.write_text(subscription)
        metadata = self.h.deploy / '.orbi/pi-providers.json'
        catalog = json.loads(metadata.read_text())
        router = catalog['providers']['openrouter']
        catalog['providers']['openai-codex'] = {key: value for key, value in router.items() if key != 'apiKey'}
        router['models'] = [*router['models'], {**router['models'][0], 'id': 'x'}]
        metadata.write_text(json.dumps(catalog))
        PauseUpdateTests.pause_rules(self, extra=self.h.enable_timer_rules(f'{self.prefix}@1.timer'))
        argv = [sys.executable, '-B', str(HELPER), 'set', 'kit', 'model', 'openrouter/x']
        before = snapshot(self.h.home)
        result = subprocess.run(argv, cwd=self.h.root, env=self.h.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('metered_confirmation_required', result.stderr)
        self.assertIn('openrouter/x', result.stderr)
        self.assertIn('--allow-metered', result.stderr)
        self.assertEqual(snapshot(self.h.home), before)
        result = subprocess.run([*argv, '--allow'], cwd=self.h.root, env=self.h.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('unrecognized arguments: --allow', result.stderr)
        self.assertEqual(snapshot(self.h.home), before)

        config.write_text('allowed_providers = ["openai-codex"]\n' + subscription)
        before = snapshot(self.h.home)
        self.h.clear_calls()
        code, doc, err = self.set_command('kit', 'model', 'openrouter/x', '--allow-metered')
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'provider_not_allowed')
        self.assertIn('openrouter/x', doc['error']['message'])
        self.assertIn('allowed_providers', doc['error']['fix'])
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        self.assertFalse(any(set(call['argv']) & {'disable', 'enable', 'check'} for call in self.h.calls()))

        allowed = 'allowed_providers = ["openai-codex", "openrouter"]\n'
        config.write_text(allowed + subscription)
        result = subprocess.run([*argv[:-1], '--allow-metered', argv[-1]], cwd=self.h.root, env=self.h.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('pi_provider: "openai-codex" -> "openrouter"', result.stdout)
        self.assertIn('Backup:', result.stdout)
        self.assertEqual((self.h.config()['pi_provider'], self.h.config()['pi_model']), ('openrouter', 'x'))
        self.assertEqual(self.h.config()['allowed_providers'], ['openai-codex', 'openrouter'])
        code, text, err = self.h.run('status', json_mode=False)
        self.assertEqual(code, 0, err)
        self.assertIn('openrouter/x (metered)', text)

    def test_metered_allowlist_refuses_malformed_or_disallowed_explicit_selection(self):
        config = self.h.deploy / 'orbi.toml'
        original = config.read_text().replace('pi_provider = "openrouter"', 'pi_provider = "openai-codex"')
        catalog = config.parent / '.orbi/pi-providers.json'
        options = ['--pi-providers', str(catalog), '--pi-provider', 'openrouter', '--pi-model', 'vendor/model-a']
        config.write_text(original)
        before = snapshot(self.h.home)
        for action, override in (('setup', 'provider_override_refused'), ('start', 'bootstrap_override_refused')):
            with self.subTest(action=action):
                code, doc, err = self.h.run(action, options=options)
                self.assertEqual(code, 2, (doc, err))
                self.assertEqual(doc['error']['code'], 'metered_confirmation_required')
                self.assertIn('openrouter/vendor/model-a', doc['error']['message'])
                self.assertIn('/orbi set', doc['error']['fix'])
                code, doc, err = self.h.run(action, options=[*options, '--allow-metered'])
                self.assertEqual(code, 2, (doc, err))
                self.assertEqual(doc['error']['code'], override)
                self.assertEqual(snapshot(self.h.home), before)

        config.write_text('allowed_providers = [123]\n' + original)
        with mock.patch.object(helper.Context, 'run') as run:
            code, doc, err = self.set_command(config, 'model', 'openrouter/vendor/model-a', '--allow-metered')
        run.assert_not_called()
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'config_invalid')
        self.assertFalse(doc['error']['mutated'])

    def test_dual_auth_provider_requires_confirmation_for_api_keys_not_subscription(self):
        config = self.h.deploy / 'orbi.toml'
        saved = config.read_text()
        subscription = saved.replace('pi_provider = "openrouter"', 'pi_provider = "openai-codex"')
        metadata = config.parent / '.orbi/pi-providers.json'
        catalog = json.loads(metadata.read_text())
        router = catalog['providers']['openrouter']
        oauth = {key: value for key, value in router.items() if key != 'apiKey'}
        catalog['providers'].update({'openai-codex': oauth, 'anthropic': oauth})
        metadata.write_text(json.dumps(catalog))
        auth = self.h.home / '.pi/agent/auth.json'
        auth.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(subscription)
        auth.write_text(json.dumps({'anthropic': {'type': 'api_key', 'key': SECRET}}))
        before = snapshot(self.h.home)
        code, doc, err = self.set_command('kit', 'model', 'anthropic/vendor/model-a')
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'metered_confirmation_required')
        self.assertIn('anthropic/vendor/model-a is metered', doc['error']['message'])
        self.assertNotIn(SECRET, json.dumps(doc) + err)
        self.assertEqual(snapshot(self.h.home), before)

        config.write_text(subscription.replace('"openai-codex"', '"anthropic"'))
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertTrue(doc['deployment']['provider']['metered'])
        auth.write_text(json.dumps({'anthropic': {'type': 'oauth', 'access': SECRET}}))
        code, doc, err = self.h.run('status')
        self.assertEqual(code, 0, err)
        self.assertFalse(doc['deployment']['provider']['metered'])
        before = snapshot(self.h.home)
        code, doc, err = self.set_command('kit', 'model', 'openrouter/vendor/model-a')
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'metered_confirmation_required')
        self.assertEqual(snapshot(self.h.home), before)

    def test_allowlist_refuses_a_disallowed_review_provider_before_activation(self):
        config = self.h.deploy / 'orbi.toml'
        config.write_text('allowed_providers = ["openrouter"]\nreview_pi_provider = "anthropic"\n'
                          + config.read_text())
        before = snapshot(self.h.home)
        code, doc, err = self.h.run('start')
        self.assertEqual(code, 2, (doc, err))
        self.assertEqual(doc['error']['code'], 'provider_not_allowed')
        self.assertIn('anthropic/vendor/model-a', doc['error']['message'])
        self.assertFalse(doc['error']['mutated'])
        self.assertEqual(snapshot(self.h.home), before)

    def test_unknown_model_and_invalid_values_do_not_write(self):
        config = self.h.deploy / 'orbi.toml'
        before = snapshot(self.h.home)
        result = subprocess.run([sys.executable, '-B', str(HELPER), 'set', str(config),
                                 'model', 'openrouter/unknown', '--json'],
                                cwd=self.h.root, env=self.h.env, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        error = json.loads(result.stdout)['error']
        self.assertEqual(error['code'], 'provider_unavailable')
        self.assertIn('model unknown has no verified metadata', error['message'])
        self.assertIn('deployment catalog', error['fix'])
        self.assertFalse(error['mutated'])
        self.assertEqual(snapshot(self.h.home), before)
        for args, fix in ((('slots', '0'), 'from 1 to 5'),
                          (('slots', '6'), 'from 1 to 5'),
                          (('model', 'openrouter/vendor/model-a', 'invalid'), 'thinking level')):
            with self.subTest(args=args):
                code, doc, err = self.set_command(config, *args)
                self.assertNotEqual(code, 0, doc)
                self.assertEqual(doc['error']['code'], 'invalid_set_value')
                self.assertIn(fix, doc['error']['fix'])
                self.assertFalse(doc['error']['mutated'])
                self.assertEqual(snapshot(self.h.home), before)
        self.assertFalse(any(call['tool'] == 'systemctl' for call in self.h.calls()))

    def test_ambiguous_repo_name_refuses_but_literal_config_path_selects(self):
        other = self.a['deploy'] / 'orbi.toml'
        other.write_text(other.read_text().replace('other/repo-a', 'other/kit'))
        before = snapshot(self.h.home)
        code, doc, err = self.set_command('kit', 'slots', '1')
        self.assertNotEqual(code, 0, doc)
        self.assertEqual(doc['error']['code'], 'ambiguous_deployment')
        self.assertIn(str(other), doc['error']['message'])
        self.assertIn('config path', doc['error']['fix'])
        self.assertEqual(snapshot(self.h.home), before)
        PauseUpdateTests.pause_rules(self, extra=self.h.enable_timer_rules(f'{self.prefix}@1.timer'))
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text() + 'pi_thinking = "low"\n')
        code, doc, err = self.set_command(os.path.relpath(config, self.h.root), 'model', 'openrouter/vendor/model-a')
        self.assertEqual(code, 0, doc)
        self.assertEqual(doc['deployment']['config'], str(config))
        self.assertEqual(self.h.config()['pi_thinking'], 'low')
        self.assertIsNone(doc['change']['backup'])

    def test_repo_basename_ending_in_toml_resolves_as_a_name(self):
        config = self.h.deploy / 'orbi.toml'
        config.write_text(config.read_text().replace(f'"{REPO}"', f'"{REPO}.toml"'))
        ctx = helper.Context(env=self.h.env, platform='linux', cwd=self.h.root)
        self.assertEqual(helper.resolve_set_target(ctx, 'kit.toml').config_path, config)

    def test_drain_timeout_leaves_config_unchanged_and_timers_paused(self):
        config = self.h.deploy / 'orbi.toml'
        before = config.read_bytes()
        PauseUpdateTests.pause_rules(self, timers={1: 'active'}, enabled={1: True}, services={1: 'active'})
        with mock.patch.object(helper, 'time', mock.Mock(
                monotonic=mock.Mock(side_effect=[0, helper.UPDATE_WAIT_MINUTES * 60]),
                sleep=mock.Mock(side_effect=AssertionError('max wait exceeded')))):
            code, text, err = self.set_command(config, 'slots', '2', json_mode=False)
        self.assertNotEqual(code, 0, text + err)
        self.assertIn('Failed step: wait_for_workers.', err)
        self.assertIn('Scheduling remains paused.', err)
        self.assertIn('before rerunning /orbi set', err)
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse(list(config.parent.glob('orbi.toml.bak-*')))
        self.assertFalse(any({'enable', 'stop', 'restart', 'kill'} & set(call['argv'])
                             for call in self.h.calls() if call['tool'] == 'systemctl'))

    def test_failed_atomic_replace_retains_original_and_backup_without_activating(self):
        config = self.h.deploy / 'orbi.toml'
        before = config.read_bytes()
        PauseUpdateTests.pause_rules(self, timers={1: 'active'}, enabled={1: True})
        real_replace = os.replace
        failed = mock.Mock(side_effect=OSError('private file error'))

        def replace(source, destination):
            return (failed if destination == config else real_replace)(source, destination)

        with mock.patch.object(helper.os, 'replace', side_effect=replace):
            code, doc, err = self.set_command(config, 'slots', '2')
        self.assertNotEqual(code, 0, doc)
        self.assertEqual(doc['error']['code'], 'filesystem_error')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['steps'][-1]['step'], 'write_config')
        self.assertEqual(doc['repair_command'], '/orbi set ' + shlex.quote(str(config)) + ' slots 2')
        failed.assert_called_once()
        temp, destination = failed.call_args.args
        self.assertEqual(temp.parent, config.parent)
        self.assertEqual(destination, config)
        self.assertFalse(temp.exists())
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(Path(doc['change']['backup']).read_bytes(), before)
        self.assertFalse(any('enable' in call['argv'] or (call['tool'] == 'orbi' and
                             call['argv'][:1] in (['check'], ['sync-engine-source'])) for call in self.h.calls()))
        self.assertNotIn('private file error', json.dumps(doc) + err)

    def test_set_check_failure_reports_saved_change_and_leaves_timers_paused(self):
        config = self.h.deploy / 'orbi.toml'
        before = config.read_bytes()
        PauseUpdateTests.pause_rules(self, timers={1: 'active'}, enabled={1: True}, extra=[
            {'tool': 'orbi', 'argv_contains': ['check'], 'exit': 1, 'stderr': SECRET}])
        code, doc, err = self.set_command(config, 'slots', '2')
        self.assertNotEqual(code, 0, doc)
        self.assertEqual(doc['error']['code'], 'validation_failed')
        self.assertTrue(doc['error']['mutated'])
        self.assertEqual(doc['steps'][-1]['step'], 'validate_non_activating')
        self.assertEqual(doc['activation'], 'none')
        self.assertEqual(doc['change']['new'], {'max_concurrency': 2})
        self.assertEqual(Path(doc['change']['backup']).read_bytes(), before)
        self.assertEqual(self.h.config()['max_concurrency'], 2)
        self.assertFalse(doc['scheduler']['timers'][f'{self.prefix}@1.timer']['enabled'])
        self.assertFalse(any('enable' in call['argv'] for call in self.h.calls()))
        self.assertNotIn(SECRET, json.dumps(doc) + err)


class LifecycleRecordAndPruneTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.h = Harness(Path(tmp.name))

    def cli(self, *args, json_mode=True):
        if json_mode:
            args += ('--json',)
        return subprocess.run([sys.executable, '-B', str(HELPER), *args],
                              cwd=self.h.root, env=self.h.env, capture_output=True,
                              text=True, timeout=30)

    def test_stop_start_status_and_retention_through_cli(self):
        import pwd

        h = self.h
        h.add_deployment_a()
        h.env['LOGNAME'] = SECRET  # host identity must not come from injected env
        setup = self.cli('setup', '--repo-dir', str(h.repo))
        self.assertEqual(setup.returncode, 0, setup.stdout + setup.stderr)
        log = h.deploy / 'lifecycle.log'
        setup_record, = log.read_text().splitlines()
        self.assertEqual(json.loads(setup_record)['action'], 'setup')
        no_change = self.cli('setup', '--repo-dir', str(h.repo))
        self.assertEqual(no_change.returncode, 0, no_change.stdout + no_change.stderr)
        self.assertEqual(log.read_text().splitlines(), [setup_record])
        log.write_text('\n'.join([setup_record] * 200) + '\n')
        h.rules(*h.scheduler_rules())
        stopped = self.cli('stop', '--repo-dir', str(h.repo))
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertEqual(json.loads(log.read_text().splitlines()[-1])['action'], 'stop')
        timer = f'{helper.unit_prefix(helper.derive_unit_name(REPO))}@1.timer'
        h.rules(*h.enable_timer_rules(timer), *h.scheduler_rules())
        started = self.cli('start', '--repo-dir', str(h.repo))
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        records = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(len(records), 200)
        self.assertEqual([record['action'] for record in records[-2:]], ['stop', 'start'])
        latest = records[-1]
        self.assertEqual(latest['user'], pwd.getpwuid(os.getuid()).pw_name)
        self.assertEqual(latest['argv'], ['start', '--repo-dir', '--json'])
        self.assertEqual(latest['result'], 'started')
        self.assertRegex(latest['timestamp'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*\+00:00$')
        self.assertNotIn(SECRET, log.read_text())
        status = self.cli('status', '--repo-dir', str(h.repo))
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        self.assertEqual(json.loads(status.stdout)['deployment']['last_lifecycle'], latest)
        text = self.cli('status', '--repo-dir', str(h.repo), json_mode=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn(f"Last lifecycle: {latest['timestamp']} /orbi start", text.stdout)
        host = self.cli('status', 'all')
        self.assertEqual(host.returncode, 0, host.stdout + host.stderr)
        rows = json.loads(host.stdout)['rows']
        self.assertTrue(any(row.get('last_lifecycle') == latest for row in rows if row['repo'] == REPO))
        verbose = self.cli('status', 'all', '--verbose', json_mode=False)
        self.assertEqual(verbose.returncode, 0, verbose.stderr)
        self.assertIn(f"Last lifecycle: {latest['timestamp']} /orbi start", verbose.stdout)
        before = log.read_bytes()
        for args in (('stop', '--dry-run'), ('start',)):
            result = self.cli(*args, '--repo-dir', str(h.repo))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(log.read_bytes(), before)
        h.rules(*h.scheduler_rules())
        updated = self.cli('update', '--stop', '--repo-dir', str(h.repo))
        self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
        update_record = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual(update_record['argv'], ['update', '--repo-dir', '--json', '--stop'])
        self.assertEqual(update_record['result'], json.loads(updated.stdout)['status'])

    def test_concurrent_lifecycle_appends_keep_all_results(self):
        from concurrent.futures import ThreadPoolExecutor

        h = self.h
        h.deploy.mkdir()
        ctx = helper.Context(env=h.env, stderr=io.StringIO())
        args = helper.parse_args(['stop'])
        results = [f'result-{index}' for index in range(16)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda result: helper.record_lifecycle(ctx, h.deploy, args, result), results))
        rows = [json.loads(line) for line in (h.deploy / 'lifecycle.log').read_text().splitlines()]
        self.assertCountEqual([row['result'] for row in rows], results)
        self.assertEqual(ctx.err.getvalue(), '')

    def templates(self, prefix, config):
        service = self.h.unit_dir / (prefix + '@.service')
        timer = service.with_suffix('.timer')
        service.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={config}"\nExecStart=%h/.local/bin/orbi\n')
        timer.write_text(f'[Timer]\nUnit={prefix}@%i.service\n')
        for path in (service, timer):
            path.chmod(0o600)
        return service, timer

    def prune_rules(self, *rules, search=None):
        self.h.rules({'tool': 'systemctl', 'argv_contains': ['show', 'UnitPath'],
                      'stdout': str(search or self.h.unit_dir)}, *rules)

    def test_prune_cli_previews_then_removes_only_stale_templates(self):
        h = self.h
        h.deploy.mkdir()
        missing_config = h.deploy / 'missing.toml'
        missing = self.templates('orbi-missing', missing_config)
        config = h.deploy / 'orbi.toml'
        text = 'source_repos = ["example/kit"]\nunit_name = "repo-gone"\nrepo_dir = "../gone"\n'
        config.write_text(text)
        repo_gone = self.templates('orbi-repo-gone', config)
        for name in ('loaded', 'worker', 'queued', 'installed'):
            self.templates(f'orbi-{name}', h.deploy / f'{name}.toml')
        healthy = h.deploy / 'healthy.toml'
        healthy.write_text(text.replace('repo-gone', 'healthy').replace('../gone', str(h.repo))
                           + 'engine_source_track = "sha:' + OLD_PIN + '"\n')
        self.templates('orbi-healthy', healthy)
        foreign = self.templates('orbi-mismatch', missing_config)
        foreign[1].write_text('[Timer]\nUnit=unrelated@%i.service\n')
        overridden, _ = self.templates('orbi-overridden', missing_config)
        env_file = h.deploy / 'unit.env'
        env_file.write_text(f'ORBI_CONFIG={healthy}\n')
        with overridden.open('a') as fh:
            fh.write(f'EnvironmentFile=-{env_file}\n')
        preserved = h.deploy / '.worktrees/retained'
        preserved.mkdir(parents=True)
        self.prune_rules({'tool': 'systemctl', 'argv_contains': ['list-units', 'orbi-loaded@*'],
                          'stdout': 'orbi-loaded@95.timer loaded inactive dead unloaded-test\n'},
                {'tool': 'systemctl', 'argv_contains': ['list-units', 'orbi-worker@*'],
                 'stdout': 'orbi-worker@8.service loaded active running worker-test\n'},
                {'tool': 'systemctl', 'argv_contains': ['list-jobs'],
                 'stdout': '12 orbi-queued@9.service start waiting\n'},
                {'tool': 'systemctl', 'argv_contains': ['list-unit-files', '--type=service,timer'],
                 'stdout': 'orbi-installed@10.timer enabled enabled\n'})
        before = snapshot(h.home)
        preview = self.cli('prune')
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertEqual({row['reason'] for row in json.loads(preview.stdout)['candidates']},
                         {'config_missing', 'repo_missing'})
        self.assertTrue(json.loads(preview.stdout)['dry_run'])
        self.assertEqual(snapshot(h.home), before)
        applied = self.cli('prune', '--apply')
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertFalse(json.loads(applied.stdout)['dry_run'])
        self.assertTrue(all(not path.exists() for path in (*missing, *repo_gone)))
        for name in ('loaded', 'worker', 'queued', 'installed', 'healthy', 'mismatch', 'overridden'):
            self.assertTrue((h.unit_dir / f'orbi-{name}@.service').is_file())
            self.assertTrue((h.unit_dir / f'orbi-{name}@.timer').is_file())
        self.assertEqual(config.read_text(), text)
        audit, = [json.loads(line) for line in (h.deploy / 'lifecycle.log').read_text().splitlines()]
        self.assertEqual((audit['action'], audit['argv'], audit['result']),
                         ('prune', ['prune', '--json', '--apply'], 'pruned'))
        self.assertTrue(preserved.is_dir())
        self.assertEqual([c['argv'] for c in h.calls() if c['tool'] == 'systemctl'
                          and set(c['argv']) & {'stop', 'disable', 'daemon-reload'}],
                         [['--user', 'daemon-reload']])
        self.assertFalse([c for c in h.calls() if c['tool'] != 'systemctl'])

    def test_prune_revalidates_and_fails_closed(self):
        h = self.h
        paths = self.templates('orbi-stale', h.deploy / 'absent.toml')
        marker = h.root / 'inventoried'
        self.prune_rules({'tool': 'systemctl', 'argv_contains': ['list-units'],
                          'if_exists': str(marker), 'exit': 1, 'stderr': SECRET},
                         {'tool': 'systemctl', 'argv_contains': ['list-units'], 'write': {str(marker): '1'}})
        applied = self.cli('prune', '--apply')
        self.assertNotEqual(applied.returncode, 0)
        error = json.loads(applied.stdout)['error']
        self.assertEqual(error['code'], 'scheduler_unavailable')
        self.assertIn('restore', error['fix'])
        self.assertFalse(error['mutated'])
        self.assertNotIn(SECRET, applied.stdout + applied.stderr)
        self.assertTrue(all(path.is_file() for path in paths))
        self.assertFalse([c for c in h.calls() if 'daemon-reload' in c['argv']])

    def test_prune_reports_removed_files_when_reload_fails(self):
        h = self.h
        paths = self.templates('orbi-stale', h.deploy / 'absent.toml')
        self.prune_rules({'tool': 'systemctl', 'argv_contains': ['daemon-reload'],
                          'exit': 1, 'stderr': SECRET})
        applied = self.cli('prune', '--apply')
        self.assertNotEqual(applied.returncode, 0)
        self.assertNotIn(SECRET, applied.stdout + applied.stderr)
        receipt = json.loads(applied.stdout)
        error = receipt['error']
        self.assertEqual(error['code'], 'daemon_reload_unverified')
        self.assertTrue(error['mutated'])
        self.assertIn('systemctl --user daemon-reload', error['fix'])
        self.assertCountEqual(receipt['removed'], [str(path) for path in paths])
        self.assertTrue(all(not path.exists() for path in paths))

    def test_prune_keeps_instance_loaded_during_apply(self):
        h = self.h
        paths = self.templates('orbi-stale', h.deploy / 'absent.toml')
        out = io.StringIO()
        inventories = iter(['', 'orbi-stale@9.timer loaded active waiting Timer\n'])

        def run(_ctx, argv, **_kwargs):
            self.assertIn(argv[2], {'list-units', 'list-unit-files', 'list-jobs', 'show'})
            if argv[2] == 'show':
                self.assertEqual(argv[3:], ['-p', 'UnitPath', '--value'])
                return subprocess.CompletedProcess(argv, 0, str(h.unit_dir), '')
            return subprocess.CompletedProcess(argv, 0, next(inventories) if argv[2] == 'list-units' else '', '')

        with mock.patch.object(helper.Context, 'run', run):
            code = helper.main(['prune', '--apply', '--json'], env=h.env, stdout=out)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['error']['code'], 'prune_target_changed')
        self.assertTrue(all(path.is_file() for path in paths))

    def test_prune_refuses_effective_config_overrides(self):
        h = self.h
        h.deploy.mkdir()
        config = h.deploy / 'healthy.toml'
        config.write_text('source_repos = ["example/kit"]\n')
        missing = h.deploy / 'absent.toml'
        inline, _ = self.templates('orbi-inline', missing)
        with inline.open('a') as stream:
            stream.write(f'  Environment = "ORBI_CONFIG={config}"\n')
        continued, _ = self.templates('orbi-continued', missing)
        with continued.open('a') as stream:
            stream.write('Environment= \\\n' + f'  "ORBI_CONFIG={config}"\n')
        self.templates('orbi-overridden', missing)
        search = h.root / 'runtime-unit-path'
        dropin = search / 'orbi-.service.d' / 'override.conf'
        dropin.parent.mkdir(parents=True)
        dropin.write_text(f'[Service]\nEnvironment="ORBI_CONFIG={config}"\n')
        # Keep the cases separate so the shared drop-in cannot mask a parser regression.
        before = snapshot(h.home)
        for unit_path in (h.unit_dir, search):
            with self.subTest(unit_path=unit_path):
                self.prune_rules(search=unit_path)
                preview = self.cli('prune')
                self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
                self.assertEqual([row['prefix'] for row in json.loads(preview.stdout)['candidates']],
                                 ['orbi-overridden'] if unit_path == h.unit_dir else [])
        self.assertEqual(snapshot(h.home), before)
        applied = self.cli('prune', '--apply')
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual(json.loads(applied.stdout)['removed'], [])
        self.assertEqual(snapshot(h.home), before)

    def test_busy_lifecycle_log_warns_without_waiting_indefinitely(self):
        h = self.h
        h.add_deployment_a()
        setup = self.cli('setup', '--repo-dir', str(h.repo))
        self.assertEqual(setup.returncode, 0, setup.stdout + setup.stderr)
        log = h.deploy / 'lifecycle.log'
        before = log.read_bytes()
        h.rules(*h.scheduler_rules())
        fd = os.open(h.deploy, os.O_RDONLY | os.O_DIRECTORY)
        try:
            helper.fcntl.flock(fd, helper.fcntl.LOCK_EX | helper.fcntl.LOCK_NB)
            stopped = self.cli('stop', '--repo-dir', str(h.repo))
        finally:
            os.close(fd)
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertIn('warning=lifecycle_log_unavailable', stopped.stderr)
        self.assertEqual(log.read_bytes(), before)

    def test_partial_stop_records_error_and_unwritable_log_does_not_change_result(self):
        h = self.h
        h.add_deployment_a()
        setup = self.cli('setup', '--repo-dir', str(h.repo))
        self.assertEqual(setup.returncode, 0, setup.stdout + setup.stderr)
        log = h.deploy / 'lifecycle.log'
        h.rules({'tool': 'systemctl', 'argv_contains': ['disable'], 'exit': 1, 'stderr': SECRET},
                *h.scheduler_rules())
        stopped = self.cli('stop', '--repo-dir', str(h.repo))
        self.assertNotEqual(stopped.returncode, 0)
        error = json.loads(stopped.stdout)['error']
        self.assertTrue(error['mutated'])
        entry = json.loads(log.read_text().splitlines()[-1])
        self.assertEqual((entry['action'], entry['result']), ('stop', error['code']))
        self.assertNotIn(SECRET, log.read_text())

        log.unlink()
        other = h.root / 'preserve'
        other.write_text('original')
        log.symlink_to(other)
        h.rules(*h.scheduler_rules())
        stopped = self.cli('stop', '--repo-dir', str(h.repo))
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertIn('warning=lifecycle_log_unavailable', stopped.stderr)
        self.assertEqual(other.read_text(), 'original')
        status = self.cli('status', '--repo-dir', str(h.repo))
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        self.assertIsNone(json.loads(status.stdout)['deployment']['last_lifecycle'])


class InterfaceAndSkillTests(unittest.TestCase):
    def test_routine_cli_receipts_need_no_followup_command_or_retry(self):
        # Public caller evidence, not an LLM simulation: each request launches the
        # real CLI once, with fake external tools and literal shell metacharacters.
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp))
            h.repo = h.repo.rename(h.root / 'space $(literal); target')
            h.add_deployment_a()
            h.rules()
            code, _, err = h.run('setup')
            self.assertEqual(code, 0, err)
            h.rules(*h.scheduler_rules())
            before = snapshot(h.home)
            cases = [([], 'status'), (['status'], 'status'), (['version'], 'version'), (['help'], 'help'),
                     *[([action, '--dry-run'], action)
                       for action in ('setup', 'start', 'stop', 'update')]]
            for request, action in cases:
                with self.subTest(request=request):
                    h.clear_calls()
                    result = subprocess.run(
                        [sys.executable, '-B', str(HELPER), *request,
                         '--repo-dir', str(h.repo), '--json'],
                        cwd=h.root, env=h.env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(result.stderr, '')
                    receipt = json.loads(result.stdout)
                    self.assertEqual(receipt['action'], action)
                    if '--dry-run' in request:
                        self.assertEqual(receipt['status'], 'planned')
                    if action == 'start':
                        self.assertEqual(receipt['preparation']['state'], 'skipped')
                    if action == 'help':
                        self.assertEqual(h.calls(), [])
                    else:
                        self.assertTrue(any(str(h.repo) in call['argv'] for call in h.calls()))
                    self.assertNotIn(SECRET, result.stdout + result.stderr)
                    # Stop/update additionally inventory loaded/installed units and pending jobs.
                    # These read-only commands are not part of setup's narrower read contract.
                    inventory_reads = {('--user', name) for name in
                                       ('list-units', 'list-unit-files', 'list-jobs')}
                    SetupBoundaryTests.assert_no_activation(self, [
                        call for call in h.calls() if not (
                            action in {'stop', 'update'} and call['tool'] == 'systemctl'
                            and tuple(call['argv'][:2]) in inventory_reads)])
                    self.assertEqual(snapshot(h.home), before)

            # A refused update is already a complete, safe user-facing answer.
            # Dirty-source refusal must precede any pause, setup, retry or checkout write.
            h.rules({'tool': 'git', 'argv_contains': ['status', '--porcelain'],
                     'stdout': ' M src/orbi/runner.py\n'},
                    *h.scheduler_rules(services={1: 'active'}, enabled={1: True}))
            before = snapshot(h.home)
            h.clear_calls()
            result = subprocess.run(
                [sys.executable, '-B', str(HELPER), 'update', '--repo-dir', str(h.repo), '--json'],
                cwd=h.root, env=h.env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['action'], 'update')
            self.assertEqual(receipt['error']['code'], 'source_dirty')
            self.assertFalse(receipt['error']['mutated'])
            self.assertTrue(receipt['error']['fix'])
            self.assertNotIn(SECRET, result.stdout + result.stderr)
            SetupBoundaryTests.assert_no_activation(self, h.calls())
            self.assertFalse(any(call['tool'] == 'orbi' and
                                 set(call['argv']) & {'setup', 'install-units', 'sync-engine-source'}
                                 for call in h.calls()))
            self.assertEqual(snapshot(h.home), before)

    def test_help_is_read_only_and_names_every_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Harness(Path(tmp))
            scratch = h.root / 'scratch'
            scratch.mkdir()
            before = snapshot(h.home)
            expected = {'status': 'none', 'version': 'none', 'setup': 'staging', 'start': 'scheduler',
                        'update': 'scheduler', 'set': 'scheduler', 'stop': 'scheduler', 'prune': 'scheduler with --apply', 'help': 'none'}
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
                                'options', 'errors', 'boundaries', 'quickstart', 'examples', 'recovery'})
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
                                '--repo-dir': ['status', 'version', 'setup', 'start', 'update', 'stop'],
                                '--config': ['status', 'version', 'setup', 'start', 'update', 'stop'],
                                '--dry-run': ['setup', 'start', 'update', 'stop', 'prune'],
                                '--stop': ['update'],
                                '--wait': ['update'],
                                '--apply': ['prune'],
                                '--json': list(expected),
                                '--pi-providers': ['setup', 'start'],
                                '--pi-provider': ['setup', 'start'],
                                '--pi-model': ['setup', 'start'],
                                '--pi-thinking': ['setup', 'start'],
                                '--allow-metered': ['setup', 'start', 'set'],
                                '--harness': ['setup', 'start'],
                                '--resume-setup': ['setup'],
                            }.items():
                                self.assertEqual(document['options'][flag]['applies_to'],
                                                 actions)
                            for action in ('stop', 'update'):
                                for effect in ('Disable owned timers', 'cancel', 'stop owned workers'):
                                    self.assertIn(effect, document['actions'][action]['effect'])
                            self.assertIn('--stop leaves stopped', document['actions']['update']['effect'])
                            self.assertIn('compatibility opt-out', document['options']['--stop']['effect'])
                            self.assertEqual(set(document['errors']),
                                             {'exit', 'mutated', 'code', 'fix'})
                            self.assertIn('Exit 0 means success or help',
                                          document['errors']['exit'])
                            self.assertIn('error.mutated, not the exit code',
                                          document['errors']['mutated'])
                            for boundary in ('no repository or deployment',
                                             'Status is read-only',
                                             'Setup (including absent-start preparation) stages source/config',
                                             'start, update and stop touch the scheduler',
                                             'Not an executor or scheduler',
                                             '/unblock', '/git-commit-push',
                                             'Local visibility only'):
                                self.assertIn(boundary, ' '.join(document['boundaries']))
                            self.assertNotIn(SECRET, result.stdout)
                        else:
                            self.assertIn('[status|version|setup|start|update|stop|prune|help]', result.stdout)
                            for action, mutation in expected.items():
                                lines = [line for line in result.stdout.splitlines()
                                         if line.startswith(f'  {action} [')]
                                self.assertEqual(len(lines), 1)
                                self.assertIn(f'[{mutation}]', lines[0])
                        self.assertEqual(h.calls(), [])
                        self.assertEqual(snapshot(h.home), before)

    def test_help_examples_parse_without_effects_and_explain_recovery(self):
        out = io.StringIO()
        self.assertEqual(helper.main(['help', '--json'], stdout=out), 0)
        doc = json.loads(out.getvalue())
        self.assertEqual(set(doc['recovery']), {'harness', 'provider', 'config_missing',
                                              'partial_setup', 'setup_busy', 'update',
                                              'platform', 'stale_helper', 'activation'})
        for example in doc['examples']:
            words = shlex.split(example['command'])
            self.assertEqual(words.pop(0), '/orbi')
            # Follow the canonical skill's public mapping, not helper setup semantics.
            if words[0] == 'setup':
                if '--prepare-only' in words:
                    words.remove('--prepare-only')
                else:
                    words[0] = 'start'
            args = helper.parse_args(words)
            self.assertIn(args.action, helper.ACTIONS)
            with mock.patch.dict(helper.ACTIONS[args.action], handler=lambda ctx, args: {}):
                self.assertEqual(helper.main(words, platform='linux', stdout=io.StringIO()), 0)
        text = io.StringIO()
        self.assertEqual(helper.main(['help'], stdout=text), 0)
        self.assertLess(text.getvalue().index('Quickstart:'), text.getvalue().index('Options:'))
        self.assertLess(text.getvalue().index('Examples:'), text.getvalue().index('Limits and next steps:'))
        for term in ('Pi-Bolt', '--harness pi', 'configured slots', 'running-process',
                     'live-qualified', 'authorize activation', 'Loaded helper:',
                     'no explicit --config', 'one invocation', 'no worker was observed',
                     'outside the scan is unknown'):
            self.assertIn(term, text.getvalue())
        self.assertIn('Public skill syntax', text.getvalue())
        self.assertIn('Direct Python helper syntax', text.getvalue())
        self.assertIn('/orbi setup --prepare-only', text.getvalue())
        self.assertIn('setup --prepare-only --resume-setup', doc['recovery']['partial_setup'])
        activation = doc['recovery']['activation']
        for term in ('failed technical check', 'read-only check or exact repair',
                     'unprotected main', 'HTTP 403',
                     'informational, not scheduling blockers', 'PR-only',
                     'repository access', 'ownership', 'live qualification'):
            self.assertIn(term, activation)
        for term in ('/orbi start', 'plain /orbi update', 'install.sh with Orbi selected',
                     'verified unit and file ownership', 'a validated release pin',
                     'a passing orbi check', 'pin and run orbi check under the config lock',
                     'orbi check --config PATH', 'deployment bootstrap and scoped environment',
                     'Do not start if validation fails or is unknown'):
            self.assertIn(term, ' '.join(doc['quickstart']))
        for term in ('cutover checklist', 'resolved gates', 'existing record',
                     'human-only gates', 'resolved explicit pauses'):
            self.assertNotIn(term, text.getvalue())
        busy = doc['recovery']['setup_busy']
        for term in ('observed timer/worker state', 'status', 'only when',
                     're-preparing or pausing'):
            self.assertIn(term, busy)

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
                self.assertEqual(doc['actions']['version']['platforms'], ['linux', 'darwin'])
                self.assertEqual(doc['actions']['help']['platforms'], ['all'])
                for action in ('setup', 'start', 'update', 'stop', 'prune'):
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
            self.assertIn('[status|version|setup|start|update|stop|prune|help]', result.stdout)
            for action in ('status', 'setup', 'start', 'update', 'stop', 'help'):
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

    def test_public_setup_mapping_is_shared_and_recovery_is_explicit(self):
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        # This is an instruction contract, not a second executable router or proof
        # of model adherence. The fake-host start/setup tests prove delegated effects.
        for public, action in (
                ('setup', 'start'),
                ('setup --dry-run', 'start --dry-run'),
                ('setup --prepare-only', 'setup'),
                ('setup --prepare-only --dry-run', 'setup --dry-run'),
                ('setup --prepare-only --resume-setup', 'setup --resume-setup')):
            self.assertIn(f'| `{public}` | `{action}` |', skill)
        for rule in ('Reject `setup --resume-setup` before invoking the helper',
                     '`setup --prepare-only --resume-setup`',
                     'Remove only `--prepare-only`',
                     'Do not silently fall back to preparation',
                     'Public `setup` has the same authority as `start`'):
            self.assertIn(rule, skill)
        for path in ('adapters/skills/orbi/SKILL.md',):
            adapter = (ROOT / path).read_text()
            self.assertIn('../../../skills/orbi/SKILL.md', adapter)
            self.assertNotIn('orbi_control.py', adapter)
        reference = (ROOT / 'skills/orbi/references/lifecycle.md').read_text()
        self.assertIn('fecim-lattice-tools', reference)
        self.assertIn('openai-codex/gpt-6.2-sol', reference)

    def test_common_path_has_four_ordered_steps_and_conditional_help(self):
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        common = skill.split('## Common path', 1)[1].split('\n## ', 1)[0]
        self.assertEqual(re.findall(r'^\d+\. \*\*([^*]+)\*\*', common, re.M),
                         ['Resolve intent.', 'Authorize.', 'Invoke once.', 'Relay receipt.'])
        text = ' '.join(common.split())
        self.assertIn('**Help first.** For help requests, run only help. '
                      'For lifecycle commands, go directly to the requested action.', text)
        self.assertIn('no separate check or dry-run validation call is needed', text)
        for rule in ('No routine pre-status', 'Build argv', 'literal `--dry-run`',
                     'No separate model', 'No blind retry'):
            self.assertIn(rule, common)
        # The helper owns action semantics; the public mapping above is still inline.
        self.assertNotIn('| Action | Single-call result and guard |', common)

    def test_status_detail_is_disclosed_without_losing_answer_distinctions(self):
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        reference = (ROOT / 'skills/orbi/references/lifecycle.md').read_text()
        text = ' '.join(skill.split())
        for rule in ('configured slots', 'enabled/active timers', 'running services',
                     'active/issue unknown', 'unavailable counts', 'observed lower bounds',
                     'Ready order', 'never prove pickup or liveness',
                     'Unavailable counts are unknown, not zero', 'Ready issues are not claimed'):
            self.assertIn(rule, text)
        status = reference.split('## Stop, status and drain', 1)[1].split(
            '### Pending issues and read coverage', 1)[0]
        for evidence in ('InvocationID/MainPID', 'journal `run_start`',
                         'retained or conflicting attempts', 'On macOS',
                         'retained logs cannot bind a current run'):
            self.assertIn(evidence, status)
            self.assertNotIn(evidence, skill)
        queue = reference.split('### Pending issues and read coverage', 1)[1].split(
            '### Interpreting Linux scheduler inventory', 1)[0]
        for rule in ('three cursor pages', 'observed lower bounds',
                     'Comment/PR detail is limited to blocked/owned issues'):
            self.assertIn(rule, queue)
        for trigger, anchor in (
                ('For slot attribution', 'stop-status-and-drain'),
                ('For incomplete queue coverage', 'pending-issues-and-read-coverage'),
                ('For Linux inventory interpretation', 'interpreting-linux-scheduler-inventory')):
            self.assertIn(trigger, skill)
            self.assertIn(f'references/lifecycle.md#{anchor}', skill)
        # Bare status/version need neither setup nor recovery internals.
        self.assertIn('Do not preload it for routine commands', text)

    def test_instruction_links_and_completion_targets_resolve(self):
        spec = importlib.util.spec_from_file_location(
            'orbi_docs_check', ROOT / 'skills/docs-sync/scripts/docs.py')
        docs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs)
        repo = docs.Repo(ROOT)
        for name in ('skills/orbi/SKILL.md', 'skills/orbi/references/lifecycle.md',
                     'adapters/skills/orbi/SKILL.md'):
            with self.subTest(path=name):
                self.assertEqual(docs.check_document(repo, 'orbi', Path(name)), [])

    def test_receipt_guidance_keeps_partial_mutation_and_exact_recovery(self):
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        receipt = ' '.join(skill.split('4. **Relay receipt.**', 1)[1].split('\n## ', 1)[0].split())
        for rule in ('Lead with target and outcome', 'next action only when needed',
                     'exact `repair_command`', 'never guess selectors',
                     'Failed quiesce blocks engine sync', 'disabled timers alone do not prove',
                     'stopped workers', 'partial mutation',
                     '`error.fix`', '`error.mutated`', 'completed/failed `steps`',
                     '`preparation`', '`activation`', '`first_tick_evidence`',
                     'scheduler uncertainty', 'No blind retry'):
            self.assertIn(rule, receipt)
        self.assertIn('references/lifecycle.md#partial-failure-and-recovery', receipt)

    def test_portable_adapter_owns_host_mechanics_not_runtime_semantics(self):
        adapter = (ROOT / 'adapters/skills/orbi/SKILL.md').read_text()
        text = ' '.join(adapter.split())
        for rule in ('disable-model-invocation: true', 'Explicit invocation only',
                     '../../../skills/shared/PONYTAIL.md',
                     '../../../skills/shared/COMMUNICATION.md', '../COMMON.md',
                     '../../../skills/orbi/SKILL.md', 'Pi supplies both',
                     'use that supplied text without reloading it',
                     "canonical workflow's directory", 'not this adapter'):
            self.assertIn(rule, text)
        for duplicate in ('Forward `version', '`update --stop`', 'unit refresh',
                          'resume command'):
            self.assertNotIn(duplicate, adapter)
        self.assertEqual(adapter.count('**Done when:**'), 1)

    def test_first_start_guidance_keeps_fast_path_and_conditional_recovery(self):
        skill = (ROOT / 'skills/orbi/SKILL.md').read_text()
        self.assertLess(skill.index('## Intent and state: fast path'),
                        skill.index('## Common path'))
        for anchor in ('activation-evidence', 'offline-guidance-examples'):
            self.assertIn(f'references/lifecycle.md#{anchor}', skill)
        reference = (ROOT / 'skills/orbi/references/lifecycle.md').read_text()
        examples = reference.split('### Offline guidance examples', 1)[1].split('## Start', 1)[0]
        for observation in ('Arenaton', 'SalmaListApi', 'scheduler unavailable',
                            'main unprotected', 'HTTP 403', 'no worker was',
                            'not current host observations or live qualification'):
            self.assertIn(observation, examples)
        recovery = reference.split('## Partial failure and recovery', 1)[1]
        busy = recovery.split('- `setup_busy`:', 1)[1].split('\n- ', 1)[0]
        self.assertIn('observed timer/worker state', busy)
        self.assertIn('status', busy)
        self.assertIn('only when deliberately re-preparing or pausing', busy)

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
        self.assertIn('`/orbi [status|version|setup|start|update|stop|prune|help]`', skill)
        self.assertIn('**Help first.**', skill)
        self.assertIn("helper's `help`", skill)
        self.assertIn('observed output', skill)
        self.assertIn('macOS', skill)
        self.assertIn('do not ask for a cutover record or separate approval', ' '.join(skill.split()))
        router = (ROOT / 'skills/ask-kit/SKILL.md').read_text()
        self.assertIn('`/orbi`', router)
        reference = (ROOT / 'skills/orbi/references/lifecycle.md').read_text()
        self.assertIn('[status|version|setup|start|update|stop|prune|help]', reference)
        self.assertIn('for lifecycle actions; `help` prints a compact human block', reference)
        for topic in ('PYTHONPATH', 'UV_TOOL_DIR', 'UV_TOOL_BIN_DIR',
                      f'sha:{PIN}', 'five', 'draining', 'is read-only', 'help'):
            self.assertIn(topic, reference)


if __name__ == '__main__':
    unittest.main()
