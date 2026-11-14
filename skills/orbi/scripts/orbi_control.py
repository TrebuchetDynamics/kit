#!/usr/bin/env python3
"""Repository-scoped Orbi lifecycle controls (Issue #18).

`python3 -B orbi_control.py [status|setup|start|stop] [--repo-dir PATH]
[--config PATH] [--dry-run] [--json]`

- `status` (the default) is read-only: local reads, read-only `orbi doctor`
  and explicit `gh`/`systemctl` reads. It never fetches, installs, locks or
  creates a receipt.
- `setup` prepares one repository deployment without activating a timer:
  repository identity, native config, `.orbi/env` isolation, provider metadata
  reuse and a non-activating `orbi check`.
- `start` re-reads ownership/source/provider evidence, runs the supported
  upstream `setup`/`install-units` with the exact scoped environment, enables
  only target timers and requests one first tick only when no worker runs.
- `stop` disables only target-owned timer instances (including installed
  surplus instances); it never stops, kills or restarts a service and reports
  `draining` until active services finish.

Linux owns the mutations; macOS is status-only; other platforms fail clearly.
All subprocesses use an argv list (no shell). Secrets are never printed: the
helper never copies credentials and never echoes environment values or child
stderr. Minimum compatible Python: 3.11 (stdlib only, `tomllib` included).
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - Windows is unsupported and refused
    fcntl = None
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - the guard reports it before mutations
    tomllib = None

MIN_PYTHON = (3, 11)
UPSTREAM_PYTHON_FLOOR = (3, 14)
SUPPORTED_PIN = 'ce97e015ca433a9312e5bdf69353be58ab394fd9'
PIN_TRACK = 'sha:' + SUPPORTED_PIN
OFFICIAL_ORIGIN = 'https://github.com/orbi-build/orbi'
OFFICIAL_REPO = 'orbi-build/orbi'
MAX_INSTANCES = 5
NODE_FLOOR = (22, 19)
PROBE_TIMEOUT = 20
MUTATION_TIMEOUT = 600
CHECK_TIMEOUT = 300
ACTIVE_STATES = frozenset({'active', 'activating', 'reloading'})
DRAIN_STATES = frozenset({'active', 'activating', 'reloading', 'deactivating'})
OWNED_ENV_KEYS = ('PATH', 'PYTHONPATH', 'UV_TOOL_DIR', 'UV_TOOL_BIN_DIR',
                  'PYTHONDONTWRITEBYTECODE')
ENV_HEADER = '# Managed by /orbi lifecycle controls; unrelated entries are preserved.'


class ControlError(Exception):
    """One honest, actionable failure. `message`/`fix` never carry a secret."""

    def __init__(self, code, message, *, fix='', exit_code=1, mutated=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.exit_code = exit_code
        self.mutated = mutated


@dataclasses.dataclass
class Repo:
    path: Path
    full: str
    owner: str
    name: str


@dataclasses.dataclass
class Deployment:
    config_path: Path
    data: dict
    source_repos: tuple
    unit_name: str | None
    deploy_home: Path
    repo_dir: Path | None
    pin: str
    max_concurrency: int

    @property
    def prefix(self) -> str:
        return unit_prefix(self.unit_name)

    @property
    def env_path(self) -> Path:
        return self.deploy_home / '.orbi/env'

    @property
    def provider_file(self) -> Path | None:
        return provider_path(self)


class Context:
    def __init__(self, *, env=None, platform=None, cwd=None, stdout=None, stderr=None):
        self.env = dict(os.environ if env is None else env)
        self.platform = normalize_platform(platform or sys.platform)
        self.cwd = Path(cwd or os.getcwd())
        self.out = stdout if stdout is not None else sys.stdout
        self.err = stderr if stderr is not None else sys.stderr

    def which(self, name):
        return shutil.which(name, path=self.env.get('PATH'))

    def run(self, argv, *, env=None, timeout=PROBE_TIMEOUT, allow_failure=False,
            cwd=None):
        child = dict(self.env if env is None else env)
        child.setdefault('PYTHONDONTWRITEBYTECODE', '1')
        command = [str(part) for part in argv]
        try:
            proc = subprocess.run(command, env=child, capture_output=True,
                                  text=True, timeout=timeout,
                                  cwd=str(cwd) if cwd else None)
        except FileNotFoundError as exc:
            raise ControlError(
                'prerequisite_missing',
                f"required command '{command[0]}' is not available on PATH",
                fix=f'install {command[0]} and retry') from exc
        except subprocess.TimeoutExpired as exc:
            raise ControlError(
                'command_timeout',
                f"'{Path(command[0]).name}' did not finish within {timeout}s",
                fix='inspect the command manually; a timeout is never retried unchanged'
            ) from exc
        if proc.returncode and not allow_failure:
            action = command[1] if len(command) > 1 else ''
            raise ControlError(
                'command_failed',
                f"'{Path(command[0]).name} {action}' failed with exit {proc.returncode}".strip(),
                fix='inspect the command output manually')
        return proc


def normalize_platform(value):
    if str(value).startswith('linux'):
        return 'linux'
    return 'darwin' if value == 'darwin' else str(value)


def home_dir(ctx):
    return Path(ctx.env.get('HOME') or Path.home())


def data_home(ctx):
    return Path(ctx.env.get('XDG_DATA_HOME') or home_dir(ctx) / '.local/share')


def config_home(ctx):
    return Path(ctx.env.get('XDG_CONFIG_HOME') or home_dir(ctx) / '.config')


def cache_home(ctx):
    return Path(ctx.env.get('XDG_CACHE_HOME') or home_dir(ctx) / '.cache')


def user_unit_dir(ctx):
    override = ctx.env.get('ORBI_UNIT_DIR')
    if override:
        return Path(override).expanduser()
    return config_home(ctx) / 'systemd/user'


def derive_unit_name(full_repo):
    """Collision-resistant, repository-derived unit suffix."""
    owner, _, name = full_repo.partition('/')
    slug = re.sub(r'[^a-z0-9]+', '-', (name or owner).lower()).strip('-')[:20] or 'repo'
    digest = hashlib.sha256(full_repo.lower().encode('utf-8')).hexdigest()[:8]
    return f'{slug}-{digest}'


def unit_prefix(unit_name):
    return 'orbi' if unit_name is None else f'orbi-{unit_name}'


def parse_github_remote(value):
    match = re.search(r'github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$', value.strip())
    if not match:
        return None
    return f'{match.group(1)}/{match.group(2)}'


def installed_config(path, home=None):
    path = Path(path)
    if not path.is_file():
        return None
    match = re.search(r'\bORBI_CONFIG=(?:"([^"]+)"|([^\s"]+))', path.read_text())
    if not match:
        return None
    value = (match.group(1) or match.group(2)).replace('%h', str(home or Path.home()))
    return Path(value).expanduser().resolve()


def read_toml(path):
    if tomllib is None:
        raise ControlError('python_unsupported',
                           'reading native Orbi configs requires Python 3.11 or newer',
                           fix='run the helper with a compatible Python')
    try:
        return tomllib.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ControlError('config_invalid',
                           f'cannot read the native Orbi config {path}: {exc.__class__.__name__}',
                           fix='repair or remove the config, then rerun status') from exc


def deployment_from(config_path, data=None):
    path = Path(config_path)
    data = read_toml(path) if data is None else data
    source_repos = data.get('source_repos')
    if (not isinstance(source_repos, list) or not source_repos
            or not all(isinstance(item, str) and '/' in item for item in source_repos)):
        raise ControlError('config_invalid',
                           f'{path} does not declare a valid source_repos list',
                           fix='set source_repos to exactly one OWNER/REPO entry')
    unit_name = data.get('unit_name')
    if unit_name is not None and not isinstance(unit_name, str):
        raise ControlError('config_invalid', f'{path} has a non-string unit_name',
                           fix='remove unit_name or set a repository-derived string')
    deploy_home = Path(data['deploy_home']) if data.get('deploy_home') else path.parent
    if not deploy_home.is_absolute():
        deploy_home = path.parent / deploy_home
    repo_dir = data.get('repo_dir')
    if repo_dir:
        repo_dir = Path(repo_dir)
        if not repo_dir.is_absolute():
            repo_dir = path.parent / repo_dir
        repo_dir = repo_dir.resolve()
    max_concurrency = data.get('max_concurrency', 1)
    if not isinstance(max_concurrency, int) or max_concurrency < 1:
        raise ControlError('config_invalid', f'{path} has an invalid max_concurrency',
                           fix='set max_concurrency to a positive integer')
    pin = data.get('engine_source_track') or 'main'
    return Deployment(config_path=path.resolve(), data=data,
                      source_repos=tuple(source_repos), unit_name=unit_name,
                      deploy_home=deploy_home.resolve(), repo_dir=repo_dir,
                      pin=str(pin), max_concurrency=max_concurrency)


def load_deployments(ctx, repo, explicit_config=None):
    paths = []
    if explicit_config:
        paths.append(Path(explicit_config).expanduser())
    paths.append(repo.path / 'orbi.toml')
    share = data_home(ctx)
    if share.is_dir():
        paths.extend(sorted(share.glob('*/orbi.toml')))
    units = user_unit_dir(ctx)
    if units.is_dir():
        for service in sorted(units.glob('orbi*.service')):
            config = installed_config(service, home_dir(ctx))
            if config is not None:
                paths.append(config)
    deployments, seen = [], set()
    for candidate in paths:
        resolved = candidate.expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if not resolved.is_file():
            if explicit_config and resolved == Path(explicit_config).expanduser().resolve():
                raise ControlError('config_missing',
                                   f'explicit config {resolved} does not exist',
                                   fix='pass an existing native Orbi config path')
            continue
        deployments.append(deployment_from(resolved))
    return deployments


def select_target(ctx, repo, explicit_config=None, *, require=False):
    deployments = load_deployments(ctx, repo, explicit_config)
    matching = [item for item in deployments if repo.full in item.source_repos]
    if explicit_config:
        explicit = Path(explicit_config).expanduser().resolve()
        for item in matching:
            if item.config_path == explicit:
                return item
        raise ControlError('config_mismatch',
                           f'config {explicit} does not own repository {repo.full}',
                           fix='pass the config whose source_repos names this repository',
                           exit_code=2)
    if len(matching) > 1:
        paths = ', '.join(str(item.config_path) for item in matching)
        raise ControlError(
            'ambiguous_deployment',
            f'multiple deployments claim {repo.full}: {paths}',
            fix='keep one task pool per repository, remove or repoint the duplicate, then rerun',
            exit_code=2)
    if matching:
        return matching[0]
    if require:
        raise ControlError('not_prepared',
                           f'no Orbi deployment owns {repo.full}',
                           fix='run `/orbi setup` for this repository first')
    return None


def repo_identity(ctx, repo_dir):
    path = Path(repo_dir).expanduser()
    if not path.exists():
        raise ControlError('repo_missing', f'repository directory {path} does not exist',
                           fix='pass --repo-dir with an existing checkout', exit_code=2)
    canonical = None
    listing = ctx.run(['git', '-C', str(path), 'worktree', 'list', '--porcelain'],
                      allow_failure=True, cwd=path)
    if listing.returncode == 0:
        for line in listing.stdout.splitlines():
            if line.startswith('worktree '):
                canonical = Path(line[len('worktree '):]).resolve()
                break
    if canonical is None:
        top = ctx.run(['git', '-C', str(path), 'rev-parse', '--show-toplevel'],
                      allow_failure=True, cwd=path)
        if top.returncode != 0 or not top.stdout.strip():
            raise ControlError('repo_unavailable',
                               f'{path} is not a Git checkout with a readable worktree',
                               fix='pass the canonical repository checkout', exit_code=2)
        canonical = Path(top.stdout.strip()).resolve()
    origin = ctx.run(['git', '-C', str(canonical), 'config', '--get', 'remote.origin.url'],
                     allow_failure=True, cwd=canonical)
    full = parse_github_remote(origin.stdout) if origin.returncode == 0 else None
    if not full:
        raise ControlError('origin_unavailable',
                           f'{canonical} has no verifiable GitHub origin',
                           fix='set origin to https://github.com/OWNER/REPO.git and retry',
                           exit_code=2)
    owner, _, name = full.partition('/')
    return Repo(path=canonical, full=full, owner=owner, name=name)


def service_path(ctx, deploy_home):
    entries = [str(deploy_home / '.orbi/bin'), str(home_dir(ctx) / '.local/bin')]
    for command in ('node', 'pi'):
        found = ctx.which(command)
        if found:
            entries.append(str(Path(found).parent))
    entries.extend(['/usr/local/bin', '/usr/bin', '/bin'])
    entries.extend(part for part in ctx.env.get('PATH', '').split(os.pathsep) if part)
    unique = []
    for entry in entries:
        if entry not in unique:
            unique.append(entry)
    return os.pathsep.join(unique)


def scoped_env(ctx, deploy_home):
    env = dict(ctx.env)
    env['PATH'] = service_path(ctx, deploy_home)
    env['PYTHONPATH'] = str(deploy_home / 'src')
    env['UV_TOOL_DIR'] = str(deploy_home / '.orbi/uv-tools')
    env['UV_TOOL_BIN_DIR'] = str(deploy_home / '.orbi/bin')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def env_values(ctx, deploy_home):
    return {
        'PATH': service_path(ctx, deploy_home),
        'PYTHONPATH': str(deploy_home / 'src'),
        'UV_TOOL_DIR': str(deploy_home / '.orbi/uv-tools'),
        'UV_TOOL_BIN_DIR': str(deploy_home / '.orbi/bin'),
        'PYTHONDONTWRITEBYTECODE': '1',
    }


def write_env(ctx, deployment):
    path = deployment.env_path
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding='utf-8') if path.is_file() else ''
    values = env_values(ctx, deployment.deploy_home)
    lines = existing.splitlines()
    rendered, seen = [], set()
    for line in lines:
        match = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$', line)
        if match and match.group(1) in values:
            key = match.group(1)
            if key in seen:
                continue
            rendered.append(f'{key}={values[key]}')
            seen.add(key)
        else:
            rendered.append(line)
    if not existing:
        rendered = [ENV_HEADER, *rendered]
    for key in OWNED_ENV_KEYS:
        if key not in seen:
            rendered.append(f'{key}={values[key]}')
    text = '\n'.join(rendered).rstrip('\n') + '\n'
    if not existing or text != existing:
        path.write_text(text, encoding='utf-8')
    path.chmod(0o600)


def provider_path(deployment):
    value = deployment.data.get('pi_providers')
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        for base in (deployment.config_path.parent, deployment.deploy_home):
            resolved = (base / candidate).resolve()
            if resolved.is_file():
                return resolved
        return (deployment.config_path.parent / candidate).resolve()
    return candidate.resolve()


def load_provider_metadata(deployment):
    path = provider_path(deployment)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def provider_evidence(deployment):
    provider = deployment.data.get('pi_provider')
    model = deployment.data.get('pi_model')
    if not provider or not model:
        return {'state': 'unavailable', 'reason': 'no explicit pi_provider/pi_model selection'}
    metadata = load_provider_metadata(deployment)
    if not metadata:
        return {'state': 'unavailable', 'reason': 'pi_providers metadata is missing or invalid'}
    entry = (metadata.get('providers') or {}).get(provider)
    if not isinstance(entry, dict):
        return {'state': 'unavailable', 'reason': f'provider {provider} is not in pi_providers'}
    models = entry.get('models')
    if not isinstance(models, list):
        return {'state': 'unavailable', 'reason': f'provider {provider} declares no models'}
    for item in models:
        if (isinstance(item, dict) and item.get('id') == model
                and isinstance(item.get('contextWindow'), int)
                and isinstance(item.get('maxTokens'), int)):
            return {'state': 'ok', 'provider': provider, 'model': model,
                    'provider_file': str(provider_path(deployment))}
    return {'state': 'unavailable',
            'reason': f'model {model} has no verified metadata for provider {provider}'}


def require_provider(deployment):
    evidence = provider_evidence(deployment)
    if evidence['state'] != 'ok':
        raise ControlError(
            'provider_unavailable',
            f'deployment {deployment.config_path} has no verified model provider: '
            + evidence.get('reason', 'unknown reason'),
            fix='configure pi_providers/pi_provider/pi_model with published model metadata, '
                'then run `/orbi setup`')
    return evidence


def find_provider_source(ctx, deployments):
    sources = []
    for deployment in sorted(deployments, key=lambda item: str(item.config_path)):
        evidence = provider_evidence(deployment)
        if evidence['state'] == 'ok':
            metadata = load_provider_metadata(deployment)
            sources.append((deployment, evidence, metadata))
    if not sources:
        raise ControlError(
            'provider_unavailable',
            'no visible deployment has a verified pi_provider/pi_model selection to reuse',
            fix='configure a verified provider selection in an existing native Orbi config, '
                'then run `/orbi setup` again; credentials are never copied')
    distinct = {(evidence['provider'], evidence['model'])
                for _, evidence, _ in sources}
    if len(distinct) > 1:
        raise ControlError('provider_ambiguous',
                           f'visible deployments disagree on the model provider: {sorted(distinct)}',
                           fix='keep one verified provider selection for this host', exit_code=2)
    source, evidence, metadata = sources[0]
    return source, evidence, metadata


def sanitized_metadata(metadata):
    data = json.loads(json.dumps(metadata))
    for name, entry in (data.get('providers') or {}).items():
        if isinstance(entry, dict) and 'apiKey' in entry:
            value = entry['apiKey']
            if not (isinstance(value, str) and value.strip().startswith('$')):
                raise ControlError(
                    'credential_copy_refused',
                    f'provider {name} stores a literal credential in pi_providers',
                    fix='reference the credential as $VARIABLE in pi_providers and keep its '
                        'value in the target .orbi/env; /orbi never copies credentials')
    return data


def source_evidence(ctx, deployment):
    track = deployment.pin
    if not track.startswith('sha:'):
        return {'state': 'unverified', 'track': track, 'reason': 'track is not an exact sha lock'}
    expected = track[len('sha:'):]
    proc = ctx.run(['git', '-C', str(deployment.deploy_home), 'rev-parse', 'HEAD'],
                   allow_failure=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {'state': 'unavailable', 'track': track, 'expected': expected}
    head = proc.stdout.strip()
    return {'state': 'verified' if head == expected else 'drift',
            'track': track, 'expected': expected, 'head': head}


def require_source(ctx, deployment):
    evidence = source_evidence(ctx, deployment)
    if evidence['state'] == 'drift':
        raise ControlError(
            'source_drift',
            f'{deployment.deploy_home} HEAD {evidence["head"]} does not match pinned '
            f'{evidence["expected"]}',
            fix=f'git -C {deployment.deploy_home} checkout --detach {evidence["expected"]}')
    if evidence['state'] == 'unavailable':
        raise ControlError('source_unavailable',
                           f'cannot read the checkout at {deployment.deploy_home}',
                           fix='repair the deployment checkout, then rerun')
    return evidence


def bootstrap_evidence(ctx, deployment):
    path = home_dir(ctx) / '.local/bin/orbi'
    if path.is_symlink() and not path.exists():
        return 'incompatible', path
    if not path.exists():
        return 'missing', path
    proc = ctx.run([str(path), '--version'], env=scoped_env(ctx, deployment.deploy_home),
                   allow_failure=True)
    return ('compatible' if proc.returncode == 0 else 'incompatible'), path


def select_python(ctx):
    exe = ctx.which('python3')
    if exe:
        probe = ctx.run([exe, '-S', '-c',
                         'import sys; raise SystemExit(0 if sys.version_info[:2] >= '
                         f'{UPSTREAM_PYTHON_FLOOR} else 1)'],
                        allow_failure=True, timeout=15)
        if probe.returncode == 0:
            return 'python3'
    return f'{UPSTREAM_PYTHON_FLOOR[0]}.{UPSTREAM_PYTHON_FLOOR[1]}'


def require_commands(ctx, names):
    for name, windows in names:
        found = ctx.which(name)
        if not found:
            raise ControlError(
                'prerequisite_missing',
                f"required command '{name}' is not available on PATH",
                fix=f'install {name} ({windows}) and retry; /orbi never runs sudo')


def node_evidence(ctx):
    node = ctx.which('node')
    if not node:
        raise ControlError('prerequisite_missing',
                           "required command 'node' is not available on PATH",
                           fix='install Node 22.19 or newer and retry')
    proc = ctx.run([node, '--version'], allow_failure=True)
    match = re.search(r'v(\d+)\.(\d+)', proc.stdout)
    if proc.returncode != 0 or not match:
        raise ControlError('node_unsupported', 'cannot verify the Node version',
                           fix='install Node 22.19 or newer and retry')
    version = (int(match.group(1)), int(match.group(2)))
    if version < NODE_FLOOR:
        raise ControlError(
            'node_unsupported',
            f'Node {match.group(0)} is older than the supported {NODE_FLOOR[0]}.{NODE_FLOOR[1]}',
            fix='install Node 22.19 or newer and retry')
    return {'state': 'ok', 'version': match.group(0), 'path': node}


def gh_auth(ctx):
    if not ctx.which('gh'):
        raise ControlError('prerequisite_missing',
                           "required command 'gh' is not available on PATH",
                           fix='install the GitHub CLI and run gh auth login')
    proc = ctx.run(['gh', 'auth', 'status'], allow_failure=True)
    if proc.returncode != 0:
        raise ControlError('gh_auth_unavailable',
                           'GitHub CLI authentication is not ready',
                           fix='run gh auth login as the deployment user')
    return {'state': 'ok'}


def pi_auth(ctx, provider):
    pi = ctx.which('pi')
    if not pi:
        raise ControlError('prerequisite_missing',
                           "required command 'pi' is not available on PATH",
                           fix='install Pi and configure its model provider')
    proc = ctx.run([pi, 'auth', 'check', '--provider', provider, '--no-refresh'],
                   allow_failure=True, timeout=60)
    if proc.returncode != 0:
        raise ControlError(
            'pi_auth_unavailable',
            f"Pi authentication is not ready for provider '{provider}'",
            fix=f'run pi auth login {provider}; /orbi never copies or prints credentials')
    return {'state': 'ok', 'provider': provider}


def prerequisites(ctx, deployment, *, action, provider=None, allow_bootstrap_install):
    names = [('git', 'https://git-scm.com'), ('gh', 'https://cli.github.com')]
    if action in ('setup', 'start'):
        names.append(('uv', 'https://docs.astral.sh/uv/'))
    require_commands(ctx, names)
    node_evidence(ctx)
    gh_auth(ctx)
    state, path = bootstrap_evidence(ctx, deployment)
    if state == 'incompatible':
        raise ControlError(
            'bootstrap_incompatible',
            f'the shared user-local bootstrap {path} did not answer --version',
            fix='repair or install a compatible user-local Orbi bootstrap for this user; '
                '/orbi never replaces another deployment launcher')
    if state == 'missing' and not allow_bootstrap_install:
        raise ControlError(
            'bootstrap_missing',
            f'the shared user-local bootstrap {path} is missing',
            fix='run `/orbi setup` to install it, or uv tool install --editable '
                f'{deployment.deploy_home}')
    if provider:
        pi_auth(ctx, provider['provider'])
    return {'bootstrap': state, 'bootstrap_path': str(path)}


def install_bootstrap(ctx, deployment):
    selected = select_python(ctx)
    uv = ctx.which('uv')
    listing = ctx.run([uv, 'tool', 'list'], allow_failure=True)
    if listing.returncode == 0 and 'orbi-cli' in listing.stdout:
        raise ControlError(
            'bootstrap_conflict',
            'the user-local orbi tool environment exists but its launcher is missing',
            fix='inspect `uv tool list` and repair or remove the conflicting installation '
                'manually; /orbi never force-reinstalls shared tools')
    env = dict(ctx.env)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    ctx.run([uv, 'tool', 'install', '--editable', '--python', selected,
             str(deployment.deploy_home)], env=env, timeout=MUTATION_TIMEOUT)
    state, path = bootstrap_evidence(ctx, deployment)
    if state != 'compatible':
        raise ControlError(
            'bootstrap_incompatible',
            f'the installed bootstrap {path} still does not answer --version',
            fix='inspect the uv tool install output and repair the bootstrap manually',
            mutated=True)
    return {'step': 'install_bootstrap', 'status': 'installed', 'python': selected}


def write_config(deployment, repo, provider):
    path = deployment.config_path
    if path.exists() or path.is_symlink():
        raise ControlError('unknown_target',
                           f'{path} already exists; refusing to overwrite a native config',
                           fix='inspect the existing deployment and rerun status',
                           exit_code=2)
    lines = [
        '# Prepared by /orbi lifecycle controls (Issue #18).',
        '# One repository per deployment; never edit a pin in place.',
        f'source_repos = [{json.dumps(repo.full)}]',
        f'repo_dir = {json.dumps(str(repo.path))}',
        f'deploy_home = {json.dumps(str(deployment.deploy_home))}',
        f'workspace_root = {json.dumps(str(repo.path.parent))}',
        f'unit_name = {json.dumps(deployment.unit_name)}',
        '# Verified retention-capable source; a change is a deliberate operation.',
        f'engine_source_track = {json.dumps(PIN_TRACK)}',
        'keep_failed_worktrees = true',
        'max_concurrency = 1',
        '# Preserve machine-unverifiable acceptance; agents never apply the human label.',
        'human_review_gate = true',
        'base_branch = "main"',
        'git_transport = "https"',
        'pi_providers = ".orbi/pi-providers.json"',
        f'pi_provider = {json.dumps(provider["provider"])}',
        f'pi_model = {json.dumps(provider["model"])}',
    ]
    if provider.get('thinking'):
        lines.append(f'pi_thinking = {json.dumps(provider["thinking"])}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_provider_metadata(deployment, metadata):
    path = deployment.deploy_home / '.orbi/pi-providers.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitized_metadata(metadata), indent=2) + '\n',
                    encoding='utf-8')
    path.chmod(0o600)


def validate_target(deployment, repo):
    for path, label in ((deployment.config_path, 'config'),
                        (deployment.deploy_home, 'deploy home'),
                        (deployment.env_path, 'env file'),
                        (deployment.provider_file, 'provider file')):
        if path is None:
            continue
        if path.is_symlink():
            raise ControlError('unknown_target',
                               f'the {label} {path} is a symlink',
                               fix='replace the symlink with a regular file owned by this '
                                   'deployment', exit_code=2)
    if not deployment.deploy_home.is_dir():
        raise ControlError('unknown_target',
                           f'the deploy home {deployment.deploy_home} is not a directory',
                           fix='repair the deployment before starting it', exit_code=2)
    if len(deployment.source_repos) != 1 or deployment.source_repos[0] != repo.full:
        raise ControlError(
            'config_conflict',
            f'{deployment.config_path} declares {list(deployment.source_repos)}, not exactly '
            f'{repo.full}',
            fix='keep one repository per deployment config', exit_code=2)
    if deployment.repo_dir is not None and deployment.repo_dir != repo.path:
        raise ControlError(
            'repo_mismatch',
            f'{deployment.config_path} repo_dir {deployment.repo_dir} is not the canonical '
            f'checkout {repo.path}',
            fix='point repo_dir at the canonical checkout or run the helper from that checkout',
            exit_code=2)


def require_unit_ownership(ctx, deployment):
    units = user_unit_dir(ctx)
    if not units.is_dir():
        return
    prefix = deployment.prefix
    service = units / f'{prefix}@.service'
    timer = units / f'{prefix}@.timer'
    for path in (service, timer):
        if path.is_symlink():
            raise ControlError('unknown_target',
                               f'installed unit {path} is a symlink',
                               fix='inspect the unit ownership manually; /orbi never adopts '
                                   'unknown units', exit_code=2)
    if service.exists():
        config = installed_config(service, home_dir(ctx))
        if config != deployment.config_path:
            raise ControlError(
                'unit_conflict',
                f'unit {service.name} belongs to {config}, not {deployment.config_path}',
                fix='keep one deployment per unit name and remove the foreign unit',
                exit_code=2)
    if timer.exists() and not service.exists():
        raise ControlError(
            'unit_conflict',
            f'timer {timer.name} exists without a service owned by this deployment',
            fix='inspect the unit ownership manually; /orbi never adopts unknown units',
            exit_code=2)


def ensure_staging_path(ctx, deploy_home, pin):

    if deploy_home.is_symlink():
        raise ControlError('unknown_target', f'staging path {deploy_home} is a symlink',
                           fix='remove the symlink; /orbi refuses unknown existing files',
                           exit_code=2)
    if not deploy_home.exists():
        return 'absent'
    if not deploy_home.is_dir():
        raise ControlError('unknown_target', f'staging path {deploy_home} is not a directory',
                           fix='remove or relocate the unrelated file', exit_code=2)
    if not any(deploy_home.iterdir()):
        return 'empty'
    origin = ctx.run(['git', '-C', str(deploy_home), 'config', '--get', 'remote.origin.url'],
                     allow_failure=True)
    if origin.returncode != 0 or parse_github_remote(origin.stdout) != OFFICIAL_REPO:
        raise ControlError(
            'unknown_target',
            f'{deploy_home} exists with unknown files or a non-official origin',
            fix='choose a new deployment path; /orbi never adopts an unknown directory',
            exit_code=2)
    head = ctx.run(['git', '-C', str(deploy_home), 'rev-parse', 'HEAD'], allow_failure=True)
    if head.returncode != 0 or head.stdout.strip() != pin:
        raise ControlError(
            'pin_mismatch',
            f'{deploy_home} HEAD {head.stdout.strip() or "unreadable"} is not the pinned {pin}',
            fix=f'git -C {deploy_home} checkout --detach {pin}; /orbi never silently moves a pin',
            exit_code=2)
    return 'reused'


def stage_checkout(ctx, deploy_home, pin):
    state = ensure_staging_path(ctx, deploy_home, pin)
    if state == 'reused':
        return {'step': 'stage_checkout', 'status': 'reused'}
    deploy_home.parent.mkdir(parents=True, exist_ok=True)
    ctx.run(['git', 'clone', '--quiet', OFFICIAL_ORIGIN, str(deploy_home)],
            timeout=MUTATION_TIMEOUT)
    origin = ctx.run(['git', '-C', str(deploy_home), 'config', '--get', 'remote.origin.url'],
                     allow_failure=True)
    if origin.returncode != 0 or parse_github_remote(origin.stdout) != OFFICIAL_REPO:
        raise ControlError('staging_failed',
                           f'the staged checkout {deploy_home} is not the official Orbi source',
                           fix='remove the staged directory and retry', mutated=True)
    head = ctx.run(['git', '-C', str(deploy_home), 'rev-parse', 'HEAD'], allow_failure=True)
    if head.returncode != 0 or head.stdout.strip() != pin:
        ctx.run(['git', '-C', str(deploy_home), 'fetch', '--quiet', 'origin', pin],
                allow_failure=True, timeout=MUTATION_TIMEOUT)
        ctx.run(['git', '-C', str(deploy_home), 'checkout', '--quiet', '--detach', pin],
                timeout=MUTATION_TIMEOUT)
        head = ctx.run(['git', '-C', str(deploy_home), 'rev-parse', 'HEAD'],
                       allow_failure=True)
    if head.returncode != 0 or head.stdout.strip() != pin:
        raise ControlError(
            'pin_mismatch',
            f'the staged checkout is at {head.stdout.strip() or "unreadable"}, expected {pin}',
            fix=f'git -C {deploy_home} fetch origin {pin} and checkout --detach {pin}',
            mutated=True)
    return {'step': 'stage_checkout', 'status': 'staged'}


def plan_new_deployment(ctx, repo, deployments):
    unit_name = derive_unit_name(repo.full)
    for item in deployments:
        if item.unit_name == unit_name:
            raise ControlError(
                'unit_conflict',
                f'unit name {unit_prefix(unit_name)} is already owned by {item.config_path} '
                f'for {list(item.source_repos)}',
                fix='keep one deployment per repository and do not duplicate unit ownership',
                exit_code=2)
    units = user_unit_dir(ctx)
    prefix = unit_prefix(unit_name)
    if units.is_dir():
        for name in (f'{prefix}@.service', f'{prefix}@.timer'):
            if (units / name).exists() or (units / name).is_symlink():
                raise ControlError(
                    'unit_conflict',
                    f'installed unit {name} already exists without a matching deployment config',
                    fix='inspect the unit ownership manually; /orbi never adopts unknown units',
                    exit_code=2)
    deploy_home = (data_home(ctx) / f'orbi-{unit_name}').resolve()
    ensure_staging_path(ctx, deploy_home, SUPPORTED_PIN)
    source, evidence, metadata = find_provider_source(ctx, deployments)
    deployment = Deployment(
        config_path=deploy_home / 'orbi.toml',
        data={'source_repos': [repo.full], 'unit_name': unit_name,
              'engine_source_track': PIN_TRACK, 'max_concurrency': 1},
        source_repos=(repo.full,), unit_name=unit_name, deploy_home=deploy_home,
        repo_dir=repo.path, pin=PIN_TRACK, max_concurrency=1)
    provider = dict(evidence)
    provider['thinking'] = source.data.get('pi_thinking')
    return deployment, provider, metadata, source


@contextlib.contextmanager
def locked(ctx, key):
    if fcntl is None:
        raise ControlError('unsupported_platform',
                           'serialized lifecycle mutation needs a POSIX file lock',
                           fix='run mutations on Linux', exit_code=2)
    folder = cache_home(ctx) / 'orbi-control'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(str(key).encode('utf-8')).hexdigest()[:16] + '.lock')
    handle = path.open('a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def orbi(ctx, deployment, *argv, timeout=CHECK_TIMEOUT, allow_failure=False):
    bootstrap = home_dir(ctx) / '.local/bin/orbi'
    return ctx.run([str(bootstrap), *argv], env=scoped_env(ctx, deployment.deploy_home),
                   timeout=timeout, allow_failure=allow_failure)


def parse_check_failure(stderr):
    fields = {}
    for key in ('check', 'reason', 'fix', 'docs'):
        match = re.search(rf'\b{key}=("(?:[^"\\]|\\.)*"|\S+)', stderr)
        if match:
            value = match.group(1)
            if value.startswith('"'):
                value = value[1:-1].replace('\\"', '"')
            fields[key] = value
    return fields


def run_orbi_check(ctx, deployment):
    proc = orbi(ctx, deployment, 'check', '--config', str(deployment.config_path),
                allow_failure=True)
    if proc.returncode != 0:
        fields = parse_check_failure(proc.stderr)
        reason = fields.get('reason') or f'exit {proc.returncode}'
        check = fields.get('check')
        message = f'orbi check failed at {check}: {reason}' if check else f'orbi check failed: {reason}'
        raise ControlError(
            'validation_failed', message,
            fix=fields.get('fix') or (
                f'{home_dir(ctx)}/.local/bin/orbi check --config '
                f'{deployment.config_path}'), mutated=True)
    return {'step': 'validate', 'status': 'ok'}


def systemctl_show(ctx, unit, prop):
    if prop == 'FragmentPath':
        argv = ['systemctl', '--user', 'show', unit, '-p', 'FragmentPath', '--value']
    else:
        argv = ['systemctl', '--user', 'show', '-p', prop, '--value', unit]
    return ctx.run(argv, allow_failure=True)


def systemctl_state(ctx, unit):
    proc = systemctl_show(ctx, unit, 'ActiveState')
    return proc.stdout.strip() or ('unknown' if proc.returncode == 0 else 'unavailable')


def timer_enabled(ctx, unit):
    proc = ctx.run(['systemctl', '--user', 'is-enabled', unit], allow_failure=True)
    return proc.stdout.strip() == 'enabled'


def scheduler_snapshot(ctx, deployment):
    timers, services = {}, {}
    for index in range(1, MAX_INSTANCES + 1):
        timer = f'{deployment.prefix}@{index}.timer'
        service = f'{deployment.prefix}@{index}.service'
        fragment = systemctl_show(ctx, timer, 'FragmentPath')
        if fragment.returncode != 0 and not fragment.stdout.strip():
            return {'state': 'unavailable',
                    'reason': 'the systemd user session is not readable'}
        installed = bool(fragment.stdout.strip())
        service_fragment = systemctl_show(ctx, service, 'FragmentPath')
        owned = False
        if service_fragment.stdout.strip():
            owned = installed_config(Path(service_fragment.stdout.strip()),
                                     home_dir(ctx)) == deployment.config_path
        state = systemctl_state(ctx, service)
        services[service] = {'state': state, 'owned': owned}
        if installed:
            timers[timer] = {'installed': True, 'owned': owned,
                             'enabled': timer_enabled(ctx, timer),
                             'active': systemctl_state(ctx, timer)}
    return {'state': 'ok', 'timers': timers, 'services': services}


def deployment_state(snapshot):
    if snapshot.get('state') != 'ok':
        return 'unavailable'
    states = [item['state'] for item in snapshot['services'].values()]
    if any(state in ACTIVE_STATES for state in states):
        return 'running'
    if any(state in DRAIN_STATES for state in states):
        return 'draining'
    if any(item['owned'] and (item['enabled'] or item['active'] == 'active')
           for item in snapshot['timers'].values()):
        return 'prepared'
    return 'stopped'


def queue_evidence(ctx, repo):
    try:
        proc = ctx.run(['gh', 'issue', 'list', '--repo', repo.full, '--state', 'open',
                        '--label', 'ai-ready', '--limit', '100',
                        '--json', 'number,title'], allow_failure=True, timeout=60)
    except ControlError:
        return {'state': 'unavailable', 'reason': 'gh issue list is not available'}
    if proc.returncode != 0:
        return {'state': 'unavailable', 'reason': 'gh issue list failed'}
    try:
        issues = json.loads(proc.stdout or '[]')
    except ValueError:
        return {'state': 'unavailable', 'reason': 'gh issue list returned unreadable JSON'}
    if not isinstance(issues, list):
        return {'state': 'unavailable', 'reason': 'gh issue list returned an unexpected shape'}
    return {'state': 'ok',
            'ready': [f"#{item.get('number')} {item.get('title')}" for item in issues
                      if isinstance(item, dict)]}


def doctor_evidence(ctx, deployment):
    state, _ = bootstrap_evidence(ctx, deployment)
    if state != 'compatible':
        return {'state': 'unavailable', 'reason': f'bootstrap is {state}'}
    proc = orbi(ctx, deployment, 'doctor', '--config', str(deployment.config_path),
                timeout=120, allow_failure=True)
    return {'state': 'ok' if proc.returncode == 0 else 'failed'}


def status_linux(ctx, repo, explicit_config):
    target = select_target(ctx, repo, explicit_config)
    queue = queue_evidence(ctx, repo)
    if target is None:
        return {'action': 'status', 'platform': 'linux', 'repo': repo.full,
                'repo_dir': str(repo.path),
                'deployment': {'state': 'absent'},
                'scheduler': {'state': 'unavailable',
                              'reason': 'no deployment config owns this repository',
                              'timers': {}, 'services': {}},
                'queue': queue, 'doctor': {'state': 'skipped'}}
    validate_target(target, repo)
    source = source_evidence(ctx, target)
    bootstrap, _ = bootstrap_evidence(ctx, target)
    provider = provider_evidence(target)
    try:
        snapshot = scheduler_snapshot(ctx, target)
    except ControlError as exc:
        snapshot = {'state': 'unavailable', 'reason': exc.message,
                    'timers': {}, 'services': {}}
    document = {
        'action': 'status', 'platform': 'linux', 'repo': repo.full,
        'repo_dir': str(repo.path),
        'deployment': {
            'state': deployment_state(snapshot),
            'config': str(target.config_path),
            'deploy_home': str(target.deploy_home),
            'unit_name': target.unit_name,
            'pin': target.pin,
            'source': source['state'],
            'bootstrap': bootstrap,
            'provider': provider,
            'slots': target.max_concurrency,
        },
        'scheduler': snapshot,
        'queue': queue,
        'doctor': doctor_evidence(ctx, target),
    }
    return document


def plist_labels(ctx, deployment):
    folder = home_dir(ctx) / 'Library/LaunchAgents'
    if not folder.is_dir():
        return []
    relative = f'org.orbi.{deployment.unit_name}.runner.' if deployment.unit_name else 'org.orbi.runner.'
    return sorted(path.stem for path in folder.glob('*.plist')
                  if path.stem.startswith(relative))


def status_darwin(ctx, repo, explicit_config):
    target = select_target(ctx, repo, explicit_config)
    queue = queue_evidence(ctx, repo)
    if target is None:
        return {'action': 'status', 'platform': 'darwin', 'repo': repo.full,
                'repo_dir': str(repo.path),
                'deployment': {'state': 'absent'},
                'scheduler': {'state': 'launchd', 'labels': [],
                              'active': 'unavailable',
                              'reason': 'no deployment config owns this repository'},
                'queue': queue, 'doctor': {'state': 'skipped'}}
    validate_target(target, repo)
    source = source_evidence(ctx, target)
    bootstrap, _ = bootstrap_evidence(ctx, target)
    provider = provider_evidence(target)
    return {
        'action': 'status', 'platform': 'darwin', 'repo': repo.full,
        'repo_dir': str(repo.path),
        'deployment': {
            'state': 'prepared', 'config': str(target.config_path),
            'deploy_home': str(target.deploy_home), 'unit_name': target.unit_name,
            'pin': target.pin, 'source': source['state'],
            'bootstrap': bootstrap, 'provider': provider,
            'slots': target.max_concurrency,
        },
        'scheduler': {'state': 'launchd', 'labels': plist_labels(ctx, target),
                      'active': 'unavailable',
                      'reason': 'macOS is status-only; active state needs launchctl'},
        'queue': queue,
        'doctor': doctor_evidence(ctx, target),
    }


def new_deployment_report(deployment, provider):
    return {'config': str(deployment.config_path),
            'deploy_home': str(deployment.deploy_home),
            'unit_name': deployment.unit_name,
            'pin': deployment.pin,
            'source': 'verified',
            'provider': provider,
            'slots': deployment.max_concurrency}


def command_setup(ctx, args):
    repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
    explicit = args.config
    deployments = load_deployments(ctx, repo, explicit)
    target = select_target(ctx, repo, explicit)
    if target is not None:
        validate_target(target, repo)
        require_unit_ownership(ctx, target)
        provider = require_provider(target)
        source = require_source(ctx, target)
        metadata = None
        new = False
    else:
        target, provider, metadata, _source = plan_new_deployment(
            ctx, repo, deployments)
        source = {'state': 'verified', 'expected': SUPPORTED_PIN, 'head': SUPPORTED_PIN}
        new = True
    evidence = prerequisites(ctx, target, action='setup', provider=provider,
                             allow_bootstrap_install=True)
    report = new_deployment_report(target, provider)
    report['source'] = source['state']
    if args.dry_run:
        steps = [{'step': 'resolve_repository', 'status': 'ok'},
                 {'step': 'reuse_existing_deployment' if not new else 'stage_checkout',
                  'status': 'planned'},
                 {'step': 'write_isolation_env', 'status': 'planned'},
                 {'step': 'validate_non_activating', 'status': 'planned'}]
        return {'action': 'setup', 'platform': ctx.platform, 'status': 'planned',
                'dry_run': True, 'repo': repo.full, 'deployment': report,
                'steps': steps, 'activated': False, 'warnings': []}
    steps = [{'step': 'resolve_repository', 'status': 'ok'}]
    with locked(ctx, target.config_path):
        if new:
            steps.append(stage_checkout(ctx, target.deploy_home, SUPPORTED_PIN))
            write_config(target, repo, provider)
            steps.append({'step': 'write_config', 'status': 'created'})
            write_provider_metadata(target, metadata)
            steps.append({'step': 'write_provider_metadata', 'status': 'created'})
        else:
            steps.append({'step': 'reuse_existing_deployment', 'status': 'reused'})
        write_env(ctx, target)
        steps.append({'step': 'write_isolation_env', 'status': 'ok'})
        if evidence['bootstrap'] == 'missing':
            steps.append(install_bootstrap(ctx, target))
        steps.append(run_orbi_check(ctx, target))
    return {'action': 'setup', 'platform': ctx.platform, 'status': 'prepared',
            'dry_run': False, 'repo': repo.full, 'deployment': report,
            'steps': steps, 'activated': False, 'warnings': []}


def start_plan(ctx, target):
    source = require_source(ctx, target)
    provider = require_provider(target)
    prerequisites(ctx, target, action='start', provider=provider,
                  allow_bootstrap_install=False)
    return source, provider


def command_start(ctx, args):
    repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
    target = select_target(ctx, repo, args.config, require=True)
    validate_target(target, repo)
    require_unit_ownership(ctx, target)
    _source, provider = start_plan(ctx, target)
    report = new_deployment_report(target, provider)
    report['source'] = _source['state']
    if args.dry_run:
        snapshot = scheduler_snapshot(ctx, target)
        if snapshot['state'] != 'ok':
            raise ControlError('scheduler_unavailable',
                               f"cannot read the target scheduler: {snapshot.get('reason')}",
                               fix='verify the systemd user session, then rerun')
        pending = [timer for timer, item in snapshot['timers'].items()
                   if item['owned'] and not item['active'] == 'active']
        live = [name for name, item in snapshot['services'].items()
                if item['state'] in ACTIVE_STATES]
        steps = [{'step': 'reuse_existing_deployment', 'status': 'ok'},
                 {'step': 'activate_timers', 'status': 'planned',
                  'timers': pending},
                 {'step': 'first_tick', 'status': 'planned',
                  'mode': 'already-active' if live else 'requested'}]
        return {'action': 'start', 'platform': ctx.platform, 'status': 'planned',
                'dry_run': True, 'repo': repo.full, 'deployment': report,
                'steps': steps, 'activated': False,
                'first_tick': 'already-active' if live else 'planned'}
    steps = [{'step': 'reuse_existing_deployment', 'status': 'ok'}]
    with locked(ctx, target.config_path):
        proc = orbi(ctx, target, 'setup', '--config', str(target.config_path),
                    '--repo', repo.full, allow_failure=True)
        if proc.returncode != 0:
            raise ControlError(
                'setup_failed', 'upstream `orbi setup` failed; scheduling is untouched',
                fix=f'{home_dir(ctx)}/.local/bin/orbi setup --config '
                    f'{target.config_path} --repo {repo.full}', mutated=True)
        steps.append({'step': 'upstream_setup', 'status': 'ok'})
        proc = orbi(ctx, target, 'install-units', '--config', str(target.config_path),
                    timeout=MUTATION_TIMEOUT, allow_failure=True)
        if proc.returncode != 0:
            raise ControlError(
                'install_units_failed',
                'upstream `orbi install-units` failed; no timer was activated',
                fix=f'{home_dir(ctx)}/.local/bin/orbi install-units --config '
                    f'{target.config_path}', mutated=True)
        steps.append({'step': 'install_units', 'status': 'ok'})
        snapshot = scheduler_snapshot(ctx, target)
        if snapshot['state'] != 'ok':
            raise ControlError('scheduler_unavailable',
                               f"cannot read the target scheduler: {snapshot.get('reason')}",
                               fix='verify the systemd user session, then rerun',
                               mutated=True)
        activated = []
        for index in range(1, target.max_concurrency + 1):
            timer = f'{target.prefix}@{index}.timer'
            item = snapshot['timers'].get(timer)
            if item and item['active'] == 'active':
                steps.append({'step': 'activate_timer', 'unit': timer,
                              'status': 'already-active'})
                continue
            ctx.run(['systemctl', '--user', 'enable', '--now', timer],
                    timeout=MUTATION_TIMEOUT)
            activated.append(timer)
            steps.append({'step': 'activate_timer', 'unit': timer, 'status': 'enabled'})
        live = [name for name, item in snapshot['services'].items()
                if item['state'] in ACTIVE_STATES]
        if live:
            first_tick = 'already-active'
            state = 'already-running'
            steps.append({'step': 'first_tick', 'status': 'already-active'})
        else:
            ctx.run(['systemctl', '--user', 'start',
                     f'{target.prefix}@1.service'], timeout=MUTATION_TIMEOUT)
            first_tick = 'requested'
            state = 'started'
            steps.append({'step': 'first_tick', 'status': 'requested'})
    return {'action': 'start', 'platform': ctx.platform, 'status': state,
            'dry_run': False, 'repo': repo.full, 'deployment': report,
            'steps': steps, 'activated': bool(activated) or state == 'started',
            'first_tick': first_tick}


def owned_timers(ctx, target, snapshot):
    owned = []
    for timer, item in sorted(snapshot['timers'].items()):
        if item['installed'] and item['owned']:
            owned.append((timer, item))
    return owned


def pending_services(ctx, target):
    pending = []
    for index in range(1, MAX_INSTANCES + 1):
        service = f'{target.prefix}@{index}.service'
        state = systemctl_state(ctx, service)
        if state in DRAIN_STATES:
            pending.append({'unit': service, 'state': state})
    return pending


def command_stop(ctx, args):
    repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
    target = select_target(ctx, repo, args.config, require=True)
    validate_target(target, repo)
    require_unit_ownership(ctx, target)
    snapshot = scheduler_snapshot(ctx, target)
    if snapshot['state'] != 'ok':
        raise ControlError('scheduler_unavailable',
                           f"cannot read the target scheduler: {snapshot.get('reason')}",
                           fix='verify the systemd user session, then rerun')
    owned = owned_timers(ctx, target, snapshot)
    if args.dry_run:
        names = [timer for timer, _ in owned]
        pending = pending_services(ctx, target)
        return {'action': 'stop', 'platform': ctx.platform, 'status': 'planned',
                'dry_run': True, 'repo': repo.full,
                'deployment': {'config': str(target.config_path),
                               'unit_name': target.unit_name, 'pin': target.pin},
                'disabled_timers': names, 'pending_services': pending,
                'steps': [{'step': 'disable_target_timers', 'status': 'planned',
                           'timers': names}]}
    disabled = []
    with locked(ctx, target.config_path):
        for timer, item in owned:
            ctx.run(['systemctl', '--user', 'disable', '--now', timer],
                    timeout=MUTATION_TIMEOUT)
            disabled.append(timer)
        pending = pending_services(ctx, target)
    state = 'draining' if pending else 'stopped'
    return {'action': 'stop', 'platform': ctx.platform, 'status': state,
            'dry_run': False, 'repo': repo.full,
            'deployment': {'config': str(target.config_path),
                           'unit_name': target.unit_name, 'pin': target.pin},
            'disabled_timers': disabled, 'pending_services': pending,
            'steps': [{'step': 'disable_target_timers', 'status': 'ok',
                       'timers': disabled}]}


def flatten(value, prefix=''):
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            lines.extend(flatten(item, f'{prefix}{key}.'))
    elif isinstance(value, (list, tuple)):
        if value and isinstance(value[0], dict):
            rendered = ','.join(
                '|'.join(f'{key}={item}' for key, item in entry.items())
                for entry in value)
            lines.append(f'{prefix.rstrip(".")}={rendered}')
        else:
            lines.append(f'{prefix.rstrip(".")}={",".join(str(item) for item in value)}')
    else:
        lines.append(f'{prefix.rstrip(".")}={value}')
    return lines


def render(ctx, document, json_mode):
    if json_mode:
        ctx.out.write(json.dumps(document, indent=2) + '\n')
        return
    for line in flatten(document):
        ctx.out.write(line + '\n')


def render_error(ctx, action, exc, json_mode):
    document = {'action': action,
                'error': {'code': exc.code, 'message': exc.message,
                          'fix': exc.fix, 'mutated': exc.mutated}}
    if json_mode:
        ctx.out.write(json.dumps(document, indent=2) + '\n')
    else:
        ctx.err.write(f'error={exc.code} message={exc.message} fix={exc.fix}\n')


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='orbi_control.py',
        description='Repository-scoped Orbi lifecycle controls: status (default), setup, '
                    'start, stop. Linux mutates; macOS is status-only; minimum Python 3.11.')
    parser.add_argument('action', nargs='?', default='status',
                        choices=('status', 'setup', 'start', 'stop'))
    parser.add_argument('--repo-dir', default=None,
                        help='canonical repository checkout (default: current directory)')
    parser.add_argument('--config', default=None,
                        help='explicit native Orbi config for this deployment')
    parser.add_argument('--dry-run', action='store_true',
                        help='show the plan without locking, writing, installing or activating')
    parser.add_argument('--json', action='store_true', help='print one JSON document')
    return parser.parse_args(argv)


def main(argv=None, *, env=None, platform=None, cwd=None, stdout=None, stderr=None):
    ctx = Context(env=env, platform=platform, cwd=cwd, stdout=stdout, stderr=stderr)
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if sys.version_info < MIN_PYTHON:
        exc = ControlError(
            'python_unsupported',
            f'orbi_control.py requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer',
            fix='run it with the documented compatible Python before any mutation')
        render_error(ctx, args.action, exc, args.json)
        return exc.exit_code
    try:
        if args.action == 'status':
            if ctx.platform not in ('linux', 'darwin'):
                raise ControlError(
                    'unsupported_platform',
                    f'platform {ctx.platform} is unsupported; Linux mutates and macOS is '
                    'status-only',
                    fix='run status on a supported host', exit_code=2)
            repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
            if ctx.platform == 'linux':
                document = status_linux(ctx, repo, args.config)
            elif ctx.platform == 'darwin':
                document = status_darwin(ctx, repo, args.config)
            else:
                raise ControlError(
                    'unsupported_platform',
                    f'platform {ctx.platform} is unsupported; Linux mutates and macOS is '
                    'status-only',
                    fix='run status on a supported host', exit_code=2)
        else:
            if ctx.platform == 'darwin':
                raise ControlError(
                    'unsupported_platform',
                    'macOS supports status only; setup/start/stop is refused before any '
                    'side effect',
                    fix='run `/orbi status`; operate a macOS deployment with upstream orbi',
                    exit_code=2)
            if ctx.platform != 'linux':
                raise ControlError(
                    'unsupported_platform',
                    f'platform {ctx.platform} is unsupported; Linux mutates and macOS is '
                    'status-only',
                    fix='run status on a supported host', exit_code=2)
            command = {'setup': command_setup, 'start': command_start,
                       'stop': command_stop}[args.action]
            document = command(ctx, args)
        render(ctx, document, args.json)
        return 0
    except ControlError as exc:
        render_error(ctx, args.action, exc, args.json)
        return exc.exit_code


if __name__ == '__main__':
    sys.exit(main())
