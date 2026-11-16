#!/usr/bin/env python3
"""Repository-scoped Orbi lifecycle controls (Issue #18).

`python3 -B orbi_control.py [status|setup|start|stop|help] [--repo-dir PATH]
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

Linux owns the mutations; macOS also supports status; help works on every platform.
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
import shlex
import subprocess
import sys
import stat
import tempfile
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
INACTIVE_STATES = frozenset({'inactive', 'failed'})
OWNED_ENV_KEYS = ('HOME', 'PATH', 'PYTHONPATH', 'UV_TOOL_DIR', 'UV_TOOL_BIN_DIR',
                  'PYTHONDONTWRITEBYTECODE')
HARNESS_KEYS = ('KIT_ORBI_HARNESS', 'KIT_ORBI_HARNESS_EXECUTABLE',
                'KIT_ORBI_HARNESS_SOURCE')
ENV_HEADER = '# Managed by /orbi lifecycle controls; unrelated entries are preserved.'


class ControlError(Exception):
    """One honest, actionable failure. `message`/`fix` never carry a secret."""

    def __init__(self, code, message, *, fix='', exit_code=1, mutated=False,
                 evidence=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.exit_code = exit_code
        self.mutated = mutated
        self.evidence = evidence or {}


@dataclasses.dataclass
class Repo:
    path: Path
    full: str
    owner: str
    name: str
    git_transport: str | None


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
    harness_selection: dict | None = None  # unpublished setup intent, never native TOML

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


def checked_path(path, label):
    """Reject symlinks, including parents, before resolving or writing a path."""
    raw = Path(path).expanduser().absolute()
    for component in (raw, *raw.parents):
        if component.is_symlink():
            raise ControlError(
                'unknown_target', f'the {label} {raw} traverses symlink {component}',
                fix='use a regular path owned by this deployment, without symlink parents',
                exit_code=2)
    return raw


def installed_config(path, home=None):
    path = Path(path)
    if not path.is_file():
        return None
    match = re.search(r'\bORBI_CONFIG=(?:"([^"]+)"|([^\s"]+))', path.read_text())
    if not match:
        return None
    value = (match.group(1) or match.group(2)).replace('%h', str(home or Path.home()))
    return checked_path(value, 'installed config').resolve()


def read_toml(path):
    if tomllib is None:
        raise ControlError('python_unsupported',
                           'reading native Orbi configs requires Python 3.11 or newer',
                           fix='run the helper with a compatible Python')
    try:
        return tomllib.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ControlError('config_invalid',
                           f'cannot read the native Orbi config {path}: {exc.__class__.__name__}',
                           fix='repair or remove the config, then rerun status') from exc


def deployment_from(config_path, data=None):
    path = checked_path(config_path, 'config')
    data = read_toml(path) if data is None else data
    for key in ('deploy_home', 'repo_dir', 'pi_providers', 'pi_provider', 'pi_model',
                'pi_thinking', 'git_transport', 'engine_source_track'):
        if key in data and not isinstance(data[key], str):
            raise ControlError('config_invalid', f'{path} has a non-string {key}',
                               fix='repair the native config deliberately; preserve recovery inputs',
                               exit_code=2)
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
    deploy_home = checked_path(deploy_home, 'deploy home')
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
        resolved = checked_path(candidate, 'config').resolve()
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
    if len(matching) > 1:
        paths = ', '.join(str(item.config_path) for item in matching)
        raise ControlError(
            'ambiguous_deployment',
            f'multiple deployments claim {repo.full}: {paths}',
            fix='keep one task pool per repository, remove or repoint the duplicate, then rerun',
            exit_code=2)
    if explicit_config:
        explicit = Path(explicit_config).expanduser().resolve()
        for item in matching:
            if item.config_path == explicit:
                return item
        raise ControlError('config_mismatch',
                           f'config {explicit} does not own repository {repo.full}',
                           fix='pass the config whose source_repos names this repository',
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
                           fix='use a canonical GitHub checkout with a supported SSH or HTTPS origin',
                           exit_code=2)
    owner, _, name = full.partition('/')
    url = origin.stdout.strip()
    transport = ('ssh' if url.startswith(('git@github.com:', 'ssh://git@github.com/'))
                 else 'https' if url.startswith('https://github.com/') else None)
    return Repo(path=canonical, full=full, owner=owner, name=name,
                git_transport=transport)


def persisted_env(deployment):
    """Pinned config._load_deploy_env_file literal parsing; never evaluate a shell."""
    path = checked_path(deployment.env_path, 'env file')
    values = {}
    if path.is_file():
        for line in path.read_bytes().decode('utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            line = line.removeprefix('export ')
            if '=' not in line:
                raise ControlError('env_invalid', 'deployment .orbi/env requires KEY=VALUE lines',
                                   fix='repair the env file privately; preserve credential bytes', exit_code=2)
            key, value = line.split('=', 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            values[key.strip()] = value
    return values


def env_literal(value, *, path=False):
    """Common native-loader/systemd single-quoted EnvironmentFile subset."""
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(c in value for c in "'\"\\")
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or (path and (not Path(value).is_absolute() or ':' in value))):
        raise ControlError('env_value_unsupported',
                           'a managed env value/path cannot round-trip through native Orbi and systemd',
                           fix='use absolute colon-free paths without quotes, backslashes, controls or '
                               'edge whitespace; interior spaces are supported')
    return "'" + value + "'"


def launcher_path(deployment):
    return deployment.deploy_home / '.orbi/harness-bin/pi'


def launcher_text(executable):
    return '#!/bin/sh\nexec ' + shlex.quote(executable) + ' "$@"\n'


def harness_evidence(ctx, deployment):
    if deployment is None:
        return {'management': 'legacy', 'requested_kind': None,
                'selection_source': 'legacy', 'launcher': None, 'executable': None,
                'state': 'unknown', 'reason': 'unconfigured; new setup defaults to pi-bolt'}
    evidence = {'management': 'legacy', 'requested_kind': None, 'selection_source': 'legacy',
                'launcher': None, 'executable': None, 'state': 'unknown'}
    try:
        values = persisted_env(deployment)
        fields = [key in values for key in HARNESS_KEYS]
        launcher = launcher_path(deployment)
        if not any(fields) and not deployment.harness_selection and not launcher.exists() and not launcher.is_symlink():
            stored = values.get('PATH')
            found = shutil.which('pi', path=stored if stored is not None else ctx.env.get('PATH'))
            evidence.update(executable=str(Path(found).resolve()) if found else None,
                            state=('verified' if found else 'unavailable') if stored else 'unknown',
                            resolution='stored PATH' if stored is not None else
                                       'ambient helper only; service resolution unverified')
            return evidence
        evidence.update(management='managed', launcher=str(launcher), state='drift')
        selection = deployment.harness_selection
        if selection is None:
            if not all(fields):
                return {**evidence, 'reason': 'missing or partial harness metadata'}
            selection = dict(zip(('kind', 'executable', 'source'), (values[k] for k in HARNESS_KEYS)))
        if selection['kind'] not in ('pi-bolt', 'pi') or selection['source'] not in ('default', 'explicit'):
            return {**evidence, 'reason': 'invalid harness metadata'}
        env_literal(selection['executable'], path=True)
        evidence.update(requested_kind=selection['kind'], executable=selection['executable'],
                        selection_source=selection['source'])
        file_identity(deployment.env_path)
        file_identity(launcher)
        executable = Path(selection['executable'])
        if (not executable.is_file() or not os.access(executable, os.X_OK)
                or str(executable.resolve()) != str(executable)):
            return {**evidence, 'state': 'unavailable', 'reason': 'selected executable unavailable or redirected'}
        if selection is deployment.harness_selection and not deployment.config_path.exists():
            return {**evidence, 'state': 'unknown', 'reason': 'launcher/env publication planned'}
        if not all(fields):
            return {**evidence, 'reason': 'missing harness metadata'}
        if tuple(values[k] for k in HARNESS_KEYS) != tuple(selection[k] for k in ('kind', 'executable', 'source')):
            return {**evidence, 'reason': 'persisted selection differs from setup intent'}
        for key, expected in (('PYTHONPATH', str(deployment.deploy_home / 'src')),
                              ('UV_TOOL_DIR', str(deployment.deploy_home / '.orbi/uv-tools')),
                              ('UV_TOOL_BIN_DIR', str(deployment.deploy_home / '.orbi/bin')),
                              ('PYTHONDONTWRITEBYTECODE', '1')):
            if values.get(key) != expected:
                return {**evidence, 'reason': 'deployment isolation env drift'}
        # Managed values have one exact literal representation; duplicates cannot hide drift.
        lines = deployment.env_path.read_bytes().decode('utf-8').splitlines()
        for key in (*HARNESS_KEYS, *OWNED_ENV_KEYS):
            matching = [line for line in lines if re.match(r'^(?:export\s+)?' + key + r'\s*=', line.strip())]
            if key not in values or matching != [key + '=' + env_literal(values[key])]:
                return {**evidence, 'reason': 'managed env metadata/serialization drift'}
        env_literal(values['HOME'], path=True)
        for part in values['PATH'].split(':'):
            env_literal(part, path=True)
        if values['PATH'].split(':')[0] != str(launcher.parent):
            return {**evidence, 'reason': 'PATH does not begin with the owned harness directory'}
        if (not launcher.is_file() or not os.access(launcher, os.X_OK)
                or launcher.read_bytes() != launcher_text(selection['executable']).encode('utf-8')):
            return {**evidence, 'reason': 'launcher missing, altered or not executable'}
        if shutil.which('pi', path=values['PATH']) != str(launcher):
            return {**evidence, 'reason': 'scoped pi does not resolve through the owned launcher'}
        return {**evidence, 'state': 'verified'}
    except (ControlError, OSError, UnicodeError):
        return {**evidence, 'management': 'managed' if launcher_path(deployment).exists() else evidence['management'],
                'state': 'drift', 'reason': 'harness/env identity cannot be verified'}


def require_harness(ctx, deployment):
    evidence = harness_evidence(ctx, deployment)
    if evidence['management'] == 'managed' and evidence['state'] != 'verified':
        # A fresh setup may probe the absolute target before publishing anything.
        if deployment.harness_selection and not deployment.config_path.exists() and evidence['state'] == 'unknown':
            return evidence
        raise ControlError('harness_' + evidence['state'],
                           evidence.get('reason', 'harness cannot be verified'),
                           fix='inspect persisted harness fields, owned launcher and selected executable; '
                               'repair deliberately, never regenerate from the current default',
                           evidence={'deployment': {'harness': evidence}})
    return evidence


def select_harness(ctx, deployment, requested, *, new):
    if not new:
        evidence = require_harness(ctx, deployment)
        if requested and evidence['management'] == 'legacy':
            raise ControlError('harness_migration_required', 'legacy deployment is unmanaged',
                               fix='omit --harness to preserve routing; migrate deliberately in a separately '
                                   'authorized deployment operation, not setup')
        if requested and requested != evidence['requested_kind']:
            raise ControlError('harness_conflict', 'selector conflicts with the persisted harness',
                               fix='omit --harness or use the saved kind; changing it requires deliberate migration')
        return
    stored = persisted_env(deployment)
    if any(k in stored for k in HARNESS_KEYS):
        if (not all(k in stored for k in HARNESS_KEYS) or stored[HARNESS_KEYS[0]] not in ('pi-bolt', 'pi')
                or stored[HARNESS_KEYS[2]] not in ('default', 'explicit')):
            raise ControlError('harness_drift', 'partial or malformed unpublished harness fields',
                               fix='preserve preparation evidence and repair deliberately')
        kind = stored[HARNESS_KEYS[0]]
        if requested and requested != kind:
            raise ControlError('harness_conflict', 'selector conflicts with unpublished saved harness',
                               fix='reuse saved selection; preserve preparation evidence')
        executable = stored[HARNESS_KEYS[1]]
        source = stored[HARNESS_KEYS[2]]
        found = executable
    else:
        kind = requested or 'pi-bolt'
        found = ctx.which(kind)
        source = 'explicit' if requested else 'default'
        executable = str(Path(found).resolve()) if found else None
    if not found or not Path(found).is_file() or not os.access(found, os.X_OK):
        raise ControlError('prerequisite_missing', f"required harness '{kind}' is not executable on caller PATH",
                           fix=f'install {kind} separately and retry; no fallback or automatic harness installation')
    env_literal(executable, path=True)
    if str(Path(executable).resolve()) != executable:
        raise ControlError('harness_drift', 'saved harness executable redirected',
                           fix='repair selected target deliberately; no fallback')
    deployment.harness_selection = {'kind': kind, 'executable': executable,
                                    'source': source}
    # Validate all generated managed values/paths before locks or writes.
    for value in (str(deployment.deploy_home), str(home_dir(ctx))):
        env_literal(value, path=True)
    env_values(ctx, deployment)


def service_path(ctx, deployment):
    values = persisted_env(deployment)
    if 'PATH' in values and (not deployment.harness_selection or all(k in values for k in HARNESS_KEYS)):
        return values['PATH']  # Managed and legacy deployments retain stored routing.
    deploy_home = deployment.deploy_home
    entries = [str(deploy_home / '.orbi/bin'), str(home_dir(ctx) / '.local/bin')]
    for command in ('node', 'pi'):
        found = ctx.which(command)
        if found:
            entries.append(str(Path(found).parent))
    entries.extend(['/usr/local/bin', '/usr/bin', '/bin'])
    entries.extend(ctx.env.get('PATH', '').split(':'))
    if deployment.harness_selection:
        entries.insert(0, str(launcher_path(deployment).parent))
    unique = []
    for entry in entries:
        if entry not in unique:
            unique.append(entry)
    return ':'.join(unique)


def scoped_env(ctx, deployment):
    env = dict(ctx.env)
    env.update(persisted_env(deployment))  # file, not ambient shell, owns service credentials/routing
    env.update(env_values(ctx, deployment))
    return env


def env_values(ctx, deployment):
    deploy_home = deployment.deploy_home
    values = {
        'PATH': service_path(ctx, deployment),
        'PYTHONPATH': str(deploy_home / 'src'),
        'UV_TOOL_DIR': str(deploy_home / '.orbi/uv-tools'),
        'UV_TOOL_BIN_DIR': str(deploy_home / '.orbi/bin'),
        'PYTHONDONTWRITEBYTECODE': '1',
    }
    selection = deployment.harness_selection
    stored = persisted_env(deployment)
    if selection or any(k in stored for k in HARNESS_KEYS):
        values['HOME'] = stored.get('HOME', str(home_dir(ctx)))
    if selection:
        values.update(zip(HARNESS_KEYS, (selection[k] for k in ('kind', 'executable', 'source'))))
    else:
        stored = persisted_env(deployment)
        values.update((k, stored[k]) for k in HARNESS_KEYS if k in stored)
    if selection or any(k in values for k in HARNESS_KEYS):
        for key, value in values.items():
            env_literal(value, path=key in ('HOME', 'PYTHONPATH', 'UV_TOOL_DIR', 'UV_TOOL_BIN_DIR'))
        for part in values['PATH'].split(':'):
            env_literal(part, path=True)
    return values


def file_identity(path):
    """Private comparison only: never render file contents/digests in a receipt."""
    path = checked_path(path, 'setup path')
    for component in (path, *path.parents):
        if component.exists() and component.stat().st_uid != os.getuid():
            raise ControlError('foreign_owner', 'a setup path is not owned by the current user',
                               fix='have the owner repair deployment-local ownership deliberately',
                               exit_code=2)
        if component.exists():
            break
    if not path.exists():
        return None
    info = path.stat()
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise ControlError('unknown_target', 'setup requires regular files and directories',
                           fix='inspect the deployment-local path without removing recovery inputs',
                           exit_code=2)
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode,
            path.read_bytes() if path.is_file() else None)


def atomic_publish(path, text, *, mode=0o600, reuse_only=False):
    """Publish complete bytes in the same directory; never clobber new targets."""
    path = checked_path(path, 'publication path')
    before = file_identity(path)
    payload = text.encode('utf-8')
    if before is not None:
        if not path.is_file():
            raise ControlError('unknown_target', 'publication target is not a regular file',
                               fix='inspect the target and preserve recovery evidence', exit_code=2)
        if before[-1] == payload:
            return
        if reuse_only:
            raise ControlError('publication_conflict', 'existing setup file differs from intended bytes',
                               fix='inspect the conflicting deployment-local file; repair deliberately '
                                   'or choose a fresh deployment path; never overwrite recovery inputs',
                               exit_code=2)
        mode = stat.S_IMODE(before[3])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name + '.',
                                         delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), mode)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if file_identity(path) != before:
            raise ControlError('target_changed', 'publication target changed during setup',
                               fix='inspect the concurrent change and rerun preflight deliberately',
                               exit_code=2)
        if before is None:
            os.link(temporary, path)  # atomic create-if-absent, not replacement
        else:
            os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def render_env(ctx, deployment):
    path = checked_path(deployment.env_path, 'env file')
    # Preserve unrelated bytes, including CRLF, whitespace, quotes and missing final LF.
    existing = path.read_bytes().decode('utf-8') if path.is_file() else ''
    values = env_values(ctx, deployment)
    rendered, seen = [], set()
    for line in existing.splitlines(keepends=True):
        match = re.match(r'^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
        if match and match.group(1) in values:
            key = match.group(1)
            if key not in seen:
                legacy_path = key == 'PATH' and not any(k in values for k in HARNESS_KEYS)
                rendered.append(line if legacy_path else f'{key}={env_literal(values[key])}\n')
                seen.add(key)
        else:
            rendered.append(line)
    if not existing:
        rendered = [ENV_HEADER + '\n']
    missing = [key for key in values if key not in seen]
    additions = [f'{key}={env_literal(values[key])}\n' for key in missing]
    if missing and rendered and not rendered[-1].endswith(('\n', '\r')):
        # Prepend, rather than adding a terminator to an unrelated final line.
        rendered = additions + rendered
    else:
        rendered.extend(additions)
    return ''.join(rendered)


def has_managed_env_fields(deployment):
    return any(k in persisted_env(deployment) for k in (*OWNED_ENV_KEYS, *HARNESS_KEYS))


def write_env(ctx, deployment, *, reuse_only=False):
    # A pre-provisioned credential-only file is not partial Kit preparation.
    # Preserve its bytes/mode while appending managed fields. Once any owned
    # field exists, config-last retry requires byte-identical intended content.
    reuse_only = reuse_only and has_managed_env_fields(deployment)
    atomic_publish(deployment.env_path, render_env(ctx, deployment), reuse_only=reuse_only)


def write_launcher(deployment):
    if deployment.harness_selection:
        atomic_publish(launcher_path(deployment),
                       launcher_text(deployment.harness_selection['executable']),
                       mode=0o755, reuse_only=True)


def provider_path(deployment):
    value = deployment.data.get('pi_providers')
    if not value:
        return None
    if not isinstance(value, str):
        raise ControlError('config_invalid', 'pi_providers must name a regular metadata file',
                           fix='repair the native provider path deliberately, preserving recovery inputs',
                           exit_code=2)
    candidate = Path(value)
    if not candidate.is_absolute():
        for base in (deployment.config_path.parent, deployment.deploy_home):
            resolved = checked_path(base / candidate, 'provider file').resolve()
            if resolved.is_file():
                return resolved
        return checked_path(deployment.config_path.parent / candidate, 'provider file').resolve()
    return checked_path(candidate, 'provider file').resolve()


def load_provider_metadata(deployment):
    path = provider_path(deployment)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    # Pi models.json structure, also required by the pinned upstream loader.
    providers = data.get('providers') if isinstance(data, dict) else None
    if not isinstance(providers, dict) or not providers:
        return None
    for entry in providers.values():
        if not isinstance(entry, dict):
            return None
        models = entry.get('models')
        if models is not None:
            if (not isinstance(models, list) or not models
                    or not isinstance(entry.get('baseUrl'), str) or not entry['baseUrl']
                    or not all(isinstance(item, dict) and item.get('id') for item in models)):
                return None
            if not (isinstance(entry.get('api'), str) and entry['api']):
                if not all(isinstance(item.get('api'), str) and item['api'] for item in models):
                    return None
    return data


def provider_evidence(deployment):
    provider = deployment.data.get('pi_provider')
    model = deployment.data.get('pi_model')
    if not provider or not model:
        return {'state': 'unavailable', 'reason': 'no explicit pi_provider/pi_model selection'}
    metadata = load_provider_metadata(deployment)
    if not metadata:
        return {'state': 'unavailable', 'reason': 'pi_providers metadata is missing or invalid'}
    providers = metadata.get('providers')
    if not isinstance(providers, dict):
        return {'state': 'unavailable', 'reason': 'pi_providers must contain a providers object'}
    entry = providers.get(provider)
    if not isinstance(entry, dict):
        return {'state': 'unavailable', 'reason': f'provider {provider} is not in pi_providers'}
    models = entry.get('models')
    if not isinstance(models, list):
        return {'state': 'unavailable', 'reason': f'provider {provider} declares no models'}
    for item in models:
        if (isinstance(item, dict) and item.get('id') == model
                and type(item.get('contextWindow')) is int and item['contextWindow'] > 0
                and type(item.get('maxTokens')) is int and item['maxTokens'] > 0):
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
            fix='run `/orbi setup --pi-providers PATH --pi-provider ID --pi-model ID '
                '[--pi-thinking LEVEL]` with published Pi model metadata; '
                'credentials are never copied')
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
    for entry in data['providers'].values():
        overrides = entry.get('modelOverrides', {})
        if not isinstance(overrides, dict) or not all(
                isinstance(item, dict) for item in overrides.values()):
            raise ControlError('provider_unavailable', 'Pi modelOverrides must map IDs to objects',
                               fix='repair the published metadata and preview setup again')
        for item in (entry, *(entry.get('models') or []), *overrides.values()):
            # Pi supports credentials in provider/model/override headers as well as apiKey.
            # Require references for all headers: arbitrary names can carry secrets.
            headers = item.get('headers', {})
            if not isinstance(headers, dict):
                raise ControlError('provider_unavailable', 'Pi metadata headers must be an object',
                                   fix='repair the published metadata and preview setup again')
            values = list(headers.values())
            if 'apiKey' in item:
                values.append(item['apiKey'])
            for value in values:
                if not (isinstance(value, str) and re.fullmatch(
                        r'\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})', value)):
                    raise ControlError(
                        'credential_copy_refused',
                        'pi_providers stores a literal credential or invalid credential reference',
                        fix='use only $VARIABLE or ${VARIABLE} references for apiKey and headers; '
                            '/orbi never copies credentials')
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
    proc = ctx.run([str(path), '--version'], env=scoped_env(ctx, deployment),
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


def final_extension_env(ctx, deployment):
    """Mirror pinned pi_session.pi_extension_env + pi_process's final child merge.

    prepare_pi_agent_dir later supplies the per-run PI_CODING_AGENT_DIR and links
    HOME/.pi/agent/auth.json. We never create that profile during preflight.
    """
    env = scoped_env(ctx, deployment)
    values = persisted_env(deployment)
    expected_home = values.get('HOME', str(home_dir(ctx)))
    expected_agent = str(Path(expected_home) / '.pi/agent')
    if (ctx.env.get('HOME', str(home_dir(ctx))) != expected_home or env.get('HOME') != expected_home or
            env.get('PI_CODING_AGENT_DIR', expected_agent) != expected_agent):
        raise ControlError('auth_home_mismatch', 'inherited HOME/PI_CODING_AGENT_DIR differs from pinned auth home',
                           fix='remove incompatible inherited or persisted overrides; pinned runs link HOME/.pi/agent/auth.json')
    extensions = {}
    entries = deployment.data.get('pi_extensions', [])
    if not isinstance(entries, list):
        raise ControlError('config_invalid', 'pi_extensions must be an array of tables',
                           fix='repair native extension configuration deliberately')
    for item in entries:
        if (not isinstance(item, dict) or type(item.get('enabled', True)) is not bool
                or not isinstance(item.get('env', {}), dict)
                or not all(isinstance(k, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k)
                           and isinstance(v, str) for k, v in item.get('env', {}).items())):
            raise ControlError('config_invalid', 'invalid pi_extensions environment',
                               fix='repair native extension configuration deliberately')
        if item.get('enabled', True):
            extensions.update(item.get('env', {}))
    managed = require_harness(ctx, deployment)['management'] == 'managed'
    for key in ('PATH', 'HOME', 'PI_CODING_AGENT_DIR'):
        if key in extensions and (key == 'PI_CODING_AGENT_DIR' or extensions[key] != env.get(key)):
            if managed or key != 'PATH':
                raise ControlError('extension_env_mismatch', f'enabled extension overrides {key} incompatibly',
                                   fix=f'repair enabled extension {key} deliberately; do not bypass routing/auth home')
    return values, extensions


def pi_auth(ctx, deployment, provider, *, metadata=None):
    metadata = metadata or load_provider_metadata(deployment)
    stored, extensions = final_extension_env(ctx, deployment)
    providers = [provider['provider']]
    review = deployment.data.get('review_pi_provider') or provider['provider']
    if review not in providers:
        providers.append(review)
    evidence = []
    env = scoped_env(ctx, deployment)
    selected = require_harness(ctx, deployment)
    pi = ((selected['launcher'] if selected['state'] == 'verified' else selected['executable'])
          if selected['management'] == 'managed' else
          shutil.which('pi', path=env['PATH']))
    if not pi:
        raise ControlError('prerequisite_missing', "required command 'pi' is unavailable in deployment PATH",
                           fix='repair deployment routing and configure its provider; no fallback')
    for identity in providers:
        entry = (metadata or {}).get('providers', {}).get(identity)
        if not isinstance(entry, dict):
            raise ControlError('auth_unverified', f'provider {identity} missing from deployment catalog',
                               fix=f'provision published metadata/auth input for provider {identity}')
        refs = set()
        for item in (entry, *(entry.get('models') or []),
                     *entry.get('modelOverrides', {}).values()):
            for value in ([item['apiKey']] if 'apiKey' in item else []) + list(item.get('headers', {}).values()):
                match = re.fullmatch(r'\$(?:([A-Za-z_][A-Za-z0-9_]*)|\{([A-Za-z_][A-Za-z0-9_]*)\})', value) if isinstance(value, str) else None
                if not match:
                    raise ControlError('auth_unverified', f'provider {identity} has unsupported credential input',
                                       fix='use declared $VARIABLE or ${VARIABLE} references, never literal credentials')
                refs.add(match.group(1) or match.group(2))
        if refs:
            for name in sorted(refs):
                # Native config validates references before extension env is merged;
                # require both service config-load and final-child availability.
                if not stored.get(name) or not extensions.get(name, stored.get(name)):
                    raise ControlError('credential_reference_missing',
                                       f'provider {identity} requires {name} in deployment .orbi/env and final child environment',
                                       fix=f'provision nonempty {name} separately in {deployment.env_path}; '
                                           'shell-only variables are not service-ready; values are never copied')
            evidence.append({'provider': identity, 'state': 'references_available', 'references': sorted(refs)})
            continue
        # Use the real user catalog/auth home, not a temporary per-run profile.
        # A deployment-only custom provider with no references cannot be proven by
        # upstream schema validation; the selected executable must support it here.
        auth_env = {**stored, **env_values(ctx, deployment), 'HOME': str(home_dir(ctx)),
                    'PI_CODING_AGENT_DIR': str(home_dir(ctx) / '.pi/agent')}
        proc = ctx.run([pi, 'auth', 'check', '--provider', identity, '--no-refresh'],
                       env=auth_env, allow_failure=True, timeout=60)
        if proc.returncode != 0:
            raise ControlError('auth_unverified', f'stored authentication/catalog check unavailable for provider {identity}',
                               fix=f'configure provider {identity} in the existing user catalog/auth home, '
                                   'or declare complete service credential references in deployment metadata')
        evidence.append({'state': 'stored_auth_checked', 'provider': identity})
    return evidence


def prerequisites(ctx, deployment, *, action, provider=None, metadata=None, allow_bootstrap_install):
    names = [('git', 'https://git-scm.com'), ('gh', 'https://cli.github.com')]
    if action in ('setup', 'start'):
        names.append(('uv', 'https://docs.astral.sh/uv/'))
    require_commands(ctx, names)
    node_evidence(ctx)
    gh_auth(ctx)
    final_extension_env(ctx, deployment)
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
    harness = require_harness(ctx, deployment)
    auth = pi_auth(ctx, deployment, provider, metadata=metadata) if provider else []
    env = scoped_env(ctx, deployment)
    executable = (harness['launcher'] if harness['management'] == 'managed' and harness['state'] == 'verified'
                  else harness['executable'] or shutil.which('pi', path=env['PATH']))
    version = ctx.run([executable, '--version'], env=env, allow_failure=True) if executable else None
    if version is None or version.returncode != 0:
        raise ControlError('harness_unavailable', 'selected harness --version probe failed',
                           fix='repair the selected executable; no fallback or installation')
    evidence = {'bootstrap': state, 'bootstrap_path': str(path), 'auth': auth,
                'harness': {**harness, 'observed_version': version.stdout.strip()[:200]}}
    if state == 'missing':
        evidence['python'] = bootstrap_preflight(ctx)
    return evidence


def bootstrap_preflight(ctx):
    selected = select_python(ctx)
    uv = ctx.which('uv')
    try:
        listing = ctx.run([uv, 'tool', 'list'], allow_failure=True)
    except ControlError as exc:
        raise ControlError(exc.code, 'uv tool list evidence is unavailable',
                           fix='inspect uv tool list manually; do not retry a timeout unchanged') from exc
    if listing.returncode != 0:
        raise ControlError('bootstrap_unverified', 'uv tool list evidence is unavailable',
                           fix='repair uv tool list before preparation; no conflict-free claim is possible')
    if 'orbi-cli' in listing.stdout:
        raise ControlError(
            'bootstrap_conflict',
            'the user-local orbi tool environment exists but its launcher is missing',
            fix='inspect `uv tool list` and repair or remove the conflicting installation '
                'manually; /orbi never force-reinstalls shared tools')
    return selected


def install_bootstrap(ctx, deployment, selected):
    uv = ctx.which('uv')
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
    path = checked_path(deployment.config_path, 'config')
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
        '# Optional human-label gate disabled; required CI and independent AI review remain.',
        'human_review_gate = false',
        'base_branch = "main"',
        f'git_transport = {json.dumps(repo.git_transport)}',
        'pi_providers = ".orbi/pi-providers.json"',
        f'pi_provider = {json.dumps(provider["provider"])}',
        f'pi_model = {json.dumps(provider["model"])}',
    ]
    if provider.get('thinking'):
        lines.append(f'pi_thinking = {json.dumps(provider["thinking"])}')
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_publish(path, '\n'.join(lines) + '\n', mode=0o644, reuse_only=True)


def provider_text(metadata):
    return json.dumps(sanitized_metadata(metadata), indent=2) + '\n'


def write_provider_metadata(deployment, metadata):
    path = deployment.deploy_home / '.orbi/pi-providers.json'
    atomic_publish(path, provider_text(metadata), reuse_only=True)


def validate_deployment_paths(deployment):
    for path, label in ((deployment.config_path, 'config'),
                        (deployment.deploy_home, 'deploy home'),
                        (deployment.env_path, 'env file'),
                        (deployment.deploy_home / '.orbi/pi-providers.json', 'provider file'),
                        (deployment.deploy_home / '.orbi/uv-tools', 'uv tool directory'),
                        (deployment.deploy_home / '.orbi/bin', 'uv bin directory'),
                        (deployment.provider_file, 'provider file')):
        if path is not None:
            checked_path(path, label)


def validate_target(deployment, repo):
    validate_deployment_paths(deployment)
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
    checked_path(deploy_home, 'staging path')
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


def plan_new_deployment(ctx, repo, deployments, args):
    if repo.git_transport is None:
        raise ControlError(
            'transport_unsupported', 'the repository origin is not supported SSH or HTTPS',
            fix='use a canonical GitHub checkout with a supported SSH or HTTPS origin; '
                '/orbi never rewrites remotes', exit_code=2)
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
    deploy_home = checked_path(data_home(ctx) / f'orbi-{unit_name}', 'staging path').resolve()
    ensure_staging_path(ctx, deploy_home, SUPPORTED_PIN)
    deployment = Deployment(
        config_path=deploy_home / 'orbi.toml',
        data={'source_repos': [repo.full], 'unit_name': unit_name,
              'engine_source_track': PIN_TRACK, 'max_concurrency': 1,
              'git_transport': repo.git_transport},
        source_repos=(repo.full,), unit_name=unit_name, deploy_home=deploy_home,
        repo_dir=repo.path, pin=PIN_TRACK, max_concurrency=1)
    validate_deployment_paths(deployment)
    select_harness(ctx, deployment, args.harness, new=True)
    if args.pi_providers is not None:
        selection = dataclasses.replace(deployment, data={
            **deployment.data, 'pi_providers': str(checked_path(args.pi_providers, 'provider file')),
            'pi_provider': args.pi_provider, 'pi_model': args.pi_model})
        provider = require_provider(selection)
        provider['thinking'] = args.pi_thinking
        metadata = load_provider_metadata(selection)
    else:
        source, evidence, metadata = find_provider_source(ctx, deployments)
        provider = dict(evidence)
        provider['thinking'] = source.data.get('pi_thinking')
    # Validate credentials before staging, locking or writing the native config.
    metadata = sanitized_metadata(metadata)
    return deployment, provider, metadata


@contextlib.contextmanager
def locked(ctx, key):
    if fcntl is None:
        raise ControlError('unsupported_platform',
                           'serialized lifecycle mutation needs a POSIX file lock',
                           fix='run mutations on Linux', exit_code=2)
    folder = checked_path(cache_home(ctx) / 'orbi-control', 'lock directory')
    file_identity(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(str(key).encode('utf-8')).hexdigest()[:16] + '.lock')
    checked_path(path, 'lock file')
    file_identity(path)
    handle = path.open('a+')
    failed = True
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
        failed = False
    finally:
        try:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            finally:
                handle.close()
        except OSError:
            # Cleanup must not replace the original lifecycle failure. Closing
            # the handle is still attempted even when explicit unlock fails.
            if not failed:
                raise


def orbi(ctx, deployment, *argv, timeout=CHECK_TIMEOUT, allow_failure=False):
    require_harness(ctx, deployment)
    bootstrap = home_dir(ctx) / '.local/bin/orbi'
    return ctx.run([str(bootstrap), *argv], env=scoped_env(ctx, deployment),
                   timeout=timeout, allow_failure=allow_failure)


def run_orbi_check(ctx, deployment):
    proc = orbi(ctx, deployment, 'check', '--config', str(deployment.config_path),
                allow_failure=True)
    if proc.returncode != 0:
        message = f'orbi check failed with exit {proc.returncode}; inspect diagnostics privately'
        raise ControlError(
            'validation_failed', message,
            fix='inspect and repair the partially prepared native config/provider metadata; '
                'rerun `/orbi setup` without bootstrap inputs for non-activating validation '
                '(or run orbi check --config ' + str(deployment.config_path) + '); '
                'use `/orbi status` to inspect scheduler state; upstream setup/install-units '
                'are activating and are not preparation repairs', mutated=True)
    return {'step': 'validate', 'status': 'ok'}


def systemctl_show(ctx, unit, prop):
    if prop == 'FragmentPath':
        argv = ['systemctl', '--user', 'show', unit, '-p', 'FragmentPath', '--value']
    else:
        argv = ['systemctl', '--user', 'show', '-p', prop, '--value', unit]
    return ctx.run(argv, allow_failure=True)


def systemctl_state(ctx, unit):
    try:
        proc = systemctl_show(ctx, unit, 'ActiveState')
    except ControlError:
        return 'unavailable'
    if proc.returncode != 0:
        return 'unavailable'
    return proc.stdout.strip() or 'unknown'


def timer_enabled(ctx, unit):
    proc = ctx.run(['systemctl', '--user', 'is-enabled', unit], allow_failure=True)
    state = proc.stdout.strip()
    # systemctl(1)'s is-enabled table: runtime enablement is still enablement;
    # failed/unknown evidence must never be interpreted as disabled scheduling.
    if proc.returncode == 0:
        if state in {'enabled', 'enabled-runtime', 'alias'}:
            return True
        if state in {'static', 'indirect', 'generated', 'transient'}:
            return False
    elif proc.returncode > 0 and state in {'disabled', 'masked', 'masked-runtime',
                                          'linked', 'linked-runtime'}:
        return False
    raise ControlError('scheduler_unavailable', 'timer enablement could not be verified',
                       fix='restore readable systemctl --user is-enabled evidence before preparation',
                       evidence={'scheduler': {'state': 'unavailable',
                                               'reason': 'timer enablement could not be verified'}})


def scheduler_snapshot(ctx, deployment):
    timers, services = {}, {}
    for index in range(1, MAX_INSTANCES + 1):
        timer = f'{deployment.prefix}@{index}.timer'
        service = f'{deployment.prefix}@{index}.service'
        fragment = systemctl_show(ctx, timer, 'FragmentPath')
        if fragment.returncode != 0:
            return {'state': 'unavailable',
                    'reason': 'the systemd user session is not readable'}
        installed = bool(fragment.stdout.strip())
        service_fragment = systemctl_show(ctx, service, 'FragmentPath')
        if service_fragment.returncode != 0:
            return {'state': 'unavailable',
                    'reason': 'loaded service ownership could not be verified'}
        owned = False
        if service_fragment.stdout.strip():
            owned = installed_config(Path(service_fragment.stdout.strip()),
                                     home_dir(ctx)) == deployment.config_path
        state = systemctl_state(ctx, service)
        services[service] = {'state': state, 'owned': owned,
                             'installed': bool(service_fragment.stdout.strip())}
        if installed:
            timers[timer] = {'installed': True, 'owned': owned,
                             'enabled': timer_enabled(ctx, timer),
                             'active': systemctl_state(ctx, timer)}
    if any(item['state'] not in DRAIN_STATES | INACTIVE_STATES
           for item in services.values()):
        return {'state': 'unavailable', 'reason': 'some service states could not be verified',
                'timers': timers, 'services': services}
    return {'state': 'ok', 'timers': timers, 'services': services}


def safe_scheduler_snapshot(ctx, deployment):
    try:
        return scheduler_snapshot(ctx, deployment)
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError):
        return {'state': 'unavailable', 'reason': 'scheduler evidence could not be read',
                'timers': {}, 'services': {}}


def deployment_state(snapshot):
    if snapshot.get('state') != 'ok':
        return 'unavailable'
    states = [item['state'] for item in snapshot['services'].values()]
    if any(state not in DRAIN_STATES | INACTIVE_STATES for state in states):
        return 'unavailable'
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
                'deployment': {'state': 'absent', 'harness': harness_evidence(ctx, None)},
                'scheduler': {'state': 'unavailable',
                              'reason': 'no deployment config owns this repository',
                              'timers': {}, 'services': {}},
                'queue': queue, 'doctor': {'state': 'skipped'}}
    validate_target(target, repo)
    source = source_evidence(ctx, target)
    harness = harness_evidence(ctx, target)
    bootstrap = (bootstrap_evidence(ctx, target)[0] if (harness['state'] == 'verified' or harness['management'] == 'legacy' and harness['state'] == 'unknown')
                 else 'unavailable')
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
            'harness': harness,
        },
        'scheduler': snapshot,
        'queue': queue,
        'doctor': (doctor_evidence(ctx, target) if (harness['state'] == 'verified' or harness['management'] == 'legacy' and harness['state'] == 'unknown')
                   else {'state': 'skipped', 'reason': 'harness unavailable/drifted'}),
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
                'deployment': {'state': 'absent', 'harness': harness_evidence(ctx, None)},
                'scheduler': {'state': 'launchd', 'labels': [],
                              'active': 'unavailable',
                              'reason': 'no deployment config owns this repository'},
                'queue': queue, 'doctor': {'state': 'skipped'}}
    validate_target(target, repo)
    source = source_evidence(ctx, target)
    harness = harness_evidence(ctx, target)
    bootstrap = (bootstrap_evidence(ctx, target)[0] if (harness['state'] == 'verified' or harness['management'] == 'legacy' and harness['state'] == 'unknown')
                 else 'unavailable')
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
            'harness': harness,
        },
        'scheduler': {'state': 'launchd', 'labels': plist_labels(ctx, target),
                      'active': 'unavailable',
                      'reason': 'macOS is status-only; active state needs launchctl'},
        'queue': queue,
        'doctor': (doctor_evidence(ctx, target) if (harness['state'] == 'verified' or harness['management'] == 'legacy' and harness['state'] == 'unknown')
                   else {'state': 'skipped', 'reason': 'harness unavailable/drifted'}),
    }


def new_deployment_report(ctx, deployment, provider):
    return {'harness': harness_evidence(ctx, deployment),
            'config': str(deployment.config_path),
            'deploy_home': str(deployment.deploy_home),
            'unit_name': deployment.unit_name,
            'pin': deployment.pin,
            'source': 'verified',
            'provider': provider,
            'slots': deployment.max_concurrency,
            'git_transport': deployment.data.get('git_transport')}


def require_setup_transport(repo, target):
    if repo.git_transport is None:
        raise ControlError('transport_unsupported', 'the origin is not supported SSH or HTTPS',
                           fix='use a supported canonical checkout; never rewrite origin as a setup repair',
                           exit_code=2)
    configured = target.data.get('git_transport')
    if configured is not None and configured != repo.git_transport:
        raise ControlError('transport_mismatch', 'origin and native config transport disagree',
                           fix='inspect origin and deliberately repair deployment-local git_transport; '
                               'never run git remote set-url or activating upstream setup', exit_code=2)


def require_setup_idle(ctx, target):
    snapshot = scheduler_snapshot(ctx, target)
    if snapshot.get('state') != 'ok':
        raise ControlError('scheduler_unavailable', 'setup cannot verify inactive/no-worker evidence',
                           fix='restore read-only systemd user-session evidence; do not repair while '
                               'worker activity is unknown', evidence={'scheduler': snapshot})
    if (any(item.get('installed') and not item['owned']
            for item in snapshot['services'].values())
            or any(not item['owned'] for item in snapshot['timers'].values())):
        raise ControlError('unit_conflict', 'loaded scheduler units have unverifiable target ownership',
                           fix='inspect loaded unit fragments and repair deployment-local ownership '
                               'deliberately; never adopt foreign units', exit_code=2,
                           evidence={'scheduler': snapshot})
    if (any(item['state'] not in INACTIVE_STATES for item in snapshot['services'].values())
            or any(item['enabled'] or item['active'] not in INACTIVE_STATES
                   for item in snapshot['timers'].values())):
        raise ControlError('setup_busy', 'setup requires inactive scheduling and no live workers',
                           fix='request a separately authorized stop/drain and verify inactivity; '
                               'preserve workers and recovery inputs', evidence={'scheduler': snapshot})
    return snapshot


def resume_inputs(ctx, target, repo, args):
    fix = ('inspect and deliberately repair the deployment-local config/provider evidence; '
           'preserve all files, pin and origin; bounded --resume-setup cannot adopt this state')
    for valid, reason, repair in (
            (target.config_path == target.deploy_home / 'orbi.toml',
             'resume config is not deployment-local orbi.toml',
             'inspect config placement and use the owned deployment-local config'),
            (target.repo_dir == repo.path,
             'resume config does not name the canonical repo_dir',
             'deliberately repair the native repo_dir after verifying canonical ownership'),
            (target.pin == PIN_TRACK,
             'resume config does not retain the supported source pin',
             'inspect the saved pin; restoring or changing it requires deliberate owner repair'),
            (target.provider_file == target.deploy_home / '.orbi/pi-providers.json',
             'resume provider path is not deployment-local .orbi/pi-providers.json',
             'inspect the saved pi_providers path; external provider paths require deliberate repair')):
        if not valid:
            raise ControlError('resume_refused', reason,
                               fix=repair + '; preserve all evidence, selections and origin', exit_code=2)
    if (args.pi_provider != target.data.get('pi_provider')
            or args.pi_model != target.data.get('pi_model')
            or (args.pi_thinking is not None
                and args.pi_thinking != target.data.get('pi_thinking'))):
        raise ControlError('resume_refused', 'resume provider/model/reasoning differs from saved selection',
                           fix='supply the exact saved IDs and reasoning (or omit thinking to inherit); '
                               'never change the saved selection through resume', exit_code=2)
    if ensure_staging_path(ctx, target.deploy_home, SUPPORTED_PIN) != 'reused':
        raise ControlError('resume_refused', 'resume needs an existing official pinned staged checkout',
                           fix=fix, exit_code=2)
    selection = dataclasses.replace(target, data={**target.data,
        'pi_providers': str(checked_path(args.pi_providers, 'provider source'))})
    provider = require_provider(selection)
    provider['thinking'] = target.data.get('pi_thinking')
    metadata = sanitized_metadata(load_provider_metadata(selection))
    path = target.provider_file
    if path.exists() and path.read_bytes() != provider_text(metadata).encode('utf-8'):
        raise ControlError('resume_refused', 'present provider file differs from verified intended bytes',
                           fix='preserve the present provider file; inspect and repair it deliberately; '
                               '--resume-setup only fills an absent file or reuses identical bytes',
                           exit_code=2)
    return provider, metadata


def setup_file_identities(target):
    return {path: file_identity(path) for path in (
        target.deploy_home, target.config_path, target.deploy_home / '.orbi',
        target.env_path, launcher_path(target).parent, launcher_path(target),
        target.deploy_home / '.orbi/pi-providers.json',
        *([target.provider_file] if target.provider_file else []))}


def require_intended_files(ctx, target, metadata):
    intended = [(target.deploy_home / '.orbi/pi-providers.json', provider_text(metadata)),
                (target.env_path, render_env(ctx, target))]
    if target.harness_selection:
        intended.append((launcher_path(target), launcher_text(target.harness_selection['executable'])))
    for path, text in intended:
        if path == launcher_path(target) and path.exists() and not os.access(path, os.X_OK):
            raise ControlError('publication_conflict', 'unpublished launcher is not executable',
                               fix='preserve evidence and repair its mode deliberately', exit_code=2)
        if path == target.env_path and not has_managed_env_fields(target):
            continue
        if path.exists() and path.read_bytes() != text.encode('utf-8'):
            raise ControlError('publication_conflict', 'unpublished setup file differs from intended bytes',
                               fix='preserve the conflicting provider/env file and inspect it; '
                                   'repair deliberately or choose a fresh deployment path', exit_code=2)


def command_setup(ctx, args):
    steps = []
    target = None
    target_path = args.config
    mutated = False
    current = 'resolve_repository'
    possible = False
    snapshot = {'state': 'unavailable', 'reason': 'scheduler not yet observed'}

    def step(name, operation, *, mutating=False):
        nonlocal current, possible, mutated
        current, possible = name, mutating
        mutated = mutated or mutating
        value = operation()
        steps.append({'step': name, 'status': 'ok',
                      **({'mutation': 'completed'} if mutating else {})})
        possible = False
        return value

    try:
        repo = step('resolve_repository', lambda: repo_identity(ctx, args.repo_dir or ctx.cwd))
        current = 'preflight_target'
        target_path = args.config or str(data_home(ctx) / f'orbi-{derive_unit_name(repo.full)}' / 'orbi.toml')
        deployments = load_deployments(ctx, repo, args.config)
        target = select_target(ctx, repo, args.config)
        new = target is None
        if not new:
            if not args.resume_setup and any(getattr(args, key) is not None for key in
                   ('pi_providers', 'pi_provider', 'pi_model', 'pi_thinking')):
                raise ControlError(
                    'provider_override_refused', 'bootstrap inputs cannot replace an existing selection',
                    fix='omit --pi-* bootstrap inputs to reuse the existing deployment; '
                        'for a legacy missing local provider use explicit --config --resume-setup '
                        'with the complete matching selectors; otherwise repair deliberately', exit_code=2)
            validate_target(target, repo)
            select_harness(ctx, target, args.harness, new=False)
            require_setup_transport(repo, target)
            require_unit_ownership(ctx, target)
            if args.resume_setup:
                provider, metadata = resume_inputs(ctx, target, repo, args)
            else:
                provider, metadata = require_provider(target), None
            source = require_source(ctx, target)
        else:
            if args.resume_setup:
                raise ControlError('resume_refused', 'resume requires an existing explicit native config',
                                   fix='use new setup without --resume-setup', exit_code=2)
            target, provider, metadata = plan_new_deployment(ctx, repo, deployments, args)
            source = {'state': 'unverified'}  # staging/verification has not run yet
            require_intended_files(ctx, target, metadata)
        identities = setup_file_identities(target)
        steps.append({'step': 'preflight_target', 'status': 'ok'})
        evidence = step('preflight_prerequisites', lambda: prerequisites(
            ctx, target, action='setup', provider=provider, metadata=metadata, allow_bootstrap_install=True))
        snapshot = step('preflight_activity', lambda: require_setup_idle(ctx, target))
        report = new_deployment_report(ctx, target, provider)
        report['source'] = source['state']
        planned = ['stage_checkout'] if new else ['reuse_existing_deployment']
        if new or args.resume_setup:
            planned.append('write_provider_metadata')
        if new:
            planned.append('write_harness_launcher')
        planned += ['write_isolation_env']
        if new:
            planned.append('write_config')
        if evidence['bootstrap'] == 'missing':
            planned.append('install_bootstrap')
        planned.append('validate_non_activating')
        if args.dry_run:
            return {'action': 'setup', 'platform': ctx.platform, 'status': 'planned',
                    'dry_run': True, 'repo': repo.full, 'deployment': report,
                    'prerequisites': evidence, 'scheduler': snapshot,
                    'steps': steps + [{'step': name, 'status': 'planned'} for name in planned],
                    'activated': False, 'warnings': []}
        current, possible, mutated = 'lock', True, True
        with locked(ctx, target.config_path):
            steps.append({'step': 'lock', 'status': 'ok', 'mutation': 'completed'})
            current, possible = 'recheck_target', False
            # Compare private file identities/bytes and rediscover ownership under lock.
            if setup_file_identities(target) != identities:
                raise ControlError('target_changed', 'deployment files changed after preflight',
                                   fix='inspect the concurrent changes; rerun preflight deliberately',
                                   exit_code=2)
            if repo_identity(ctx, repo.path) != repo:
                raise ControlError('target_changed', 'canonical repository identity changed after preflight',
                                   fix='inspect the canonical checkout and origin; never rewrite remotes',
                                   exit_code=2)
            selected = select_target(ctx, repo, args.config)
            if (new and selected is not None) or (not new and selected != target):
                raise ControlError('target_changed', 'deployment ownership changed after preflight',
                                   fix='inspect duplicate/concurrent deployment ownership', exit_code=2)
            if new:
                # Repeat all unit/ownership checks, without silently adopting new selectors.
                rechecked, _, _ = plan_new_deployment(ctx, repo, load_deployments(ctx, repo), args)
                if rechecked != target:
                    raise ControlError('target_changed', 'new deployment target changed',
                                       fix='inspect concurrent setup changes', exit_code=2)
                require_intended_files(ctx, target, metadata)
            else:
                validate_target(target, repo)
                require_unit_ownership(ctx, target)
                require_source(ctx, target)
                if args.resume_setup:
                    resume_inputs(ctx, target, repo, args)
                else:
                    require_provider(target)
            snapshot = require_setup_idle(ctx, target)
            bootstrap_state, _ = bootstrap_evidence(ctx, target)
            if bootstrap_state != evidence['bootstrap']:
                raise ControlError('target_changed', 'shared bootstrap changed after preflight',
                                   fix='inspect the shared launcher and rerun preflight deliberately; '
                                       'never replace another deployment launcher', exit_code=2)
            if bootstrap_state == 'missing':
                bootstrap_preflight(ctx)
            steps.append({'step': 'recheck_target', 'status': 'ok'})
            if new:
                step('stage_checkout', lambda: stage_checkout(ctx, target.deploy_home, SUPPORTED_PIN),
                     mutating=True)
                report['source'] = 'verified'
            if new or args.resume_setup:
                step('write_provider_metadata', lambda: write_provider_metadata(target, metadata),
                     mutating=True)
            if new:
                step('write_harness_launcher', lambda: write_launcher(target), mutating=True)
            step('write_isolation_env', lambda: write_env(ctx, target, reuse_only=new), mutating=True)
            if new:
                step('write_config', lambda: write_config(target, repo, provider), mutating=True)
            if evidence['bootstrap'] == 'missing':
                # Recheck conflict evidence before the later mutation-possible install.
                step('recheck_bootstrap', lambda: bootstrap_preflight(ctx))
                step('install_bootstrap', lambda: install_bootstrap(ctx, target, evidence['python']),
                     mutating=True)
            require_harness(ctx, target)
            report['harness'] = harness_evidence(ctx, target)
            report['harness']['observed_version'] = evidence['harness']['observed_version']
            step('validate_non_activating', lambda: run_orbi_check(ctx, target), mutating=True)
            current, possible = 'release_lock', True
        return {'action': 'setup', 'platform': ctx.platform, 'status': 'prepared',
                'dry_run': False, 'repo': repo.full, 'deployment': report,
                'prerequisites': evidence, 'scheduler': snapshot,
                'steps': steps, 'activated': False, 'warnings': []}
    except (ControlError, OSError, UnicodeError) as error:
        if isinstance(error, ControlError):
            exc = error
        elif isinstance(error, UnicodeError):
            exc = ControlError(
                'file_encoding_invalid', 'setup input is not valid UTF-8 (details withheld)',
                fix='inspect the failed step and repair file encoding privately; '
                    'preserve original bytes and all recovery inputs')
        else:
            exc = ControlError(
                'filesystem_error', 'setup filesystem operation failed (details withheld)',
                fix='inspect deployment-local permissions and files privately; preserve recovery inputs '
                    'and repair the cause before rerunning setup')
        exc.mutated = exc.mutated or mutated
        exc.evidence = {**exc.evidence,
                        'deployment': {'harness': harness_evidence(ctx, target)} if target else None,
                        'target': str(target.config_path) if target else target_path,
                        'original_error': exc.code, 'activated': False,
                        'scheduler': exc.evidence.get('scheduler', snapshot),
                        'steps': [*steps, {'step': current, 'status': 'failed', 'error': exc.code,
                                          'mutation': 'possible' if possible else 'none'}]}
        if exc.code == 'config_invalid':
            exc.fix = 'inspect and deliberately repair the native config; preserve all recovery inputs '
        if not exc.fix:
            exc.fix = 'inspect the failed setup step and actual files; preserve all recovery inputs'
        raise exc from (error if exc is not error else None)


def start_plan(ctx, target):
    require_harness(ctx, target)
    source = require_source(ctx, target)
    provider = require_provider(target)
    prerequisites(ctx, target, action='start', provider=provider,
                  allow_bootstrap_install=False)
    return source, provider


def lifecycle_failure(ctx, target, error, *, target_path, steps, current, mutated, evidence):
    """Retain completed work; recovery is observation only, never compensation."""
    if isinstance(error, ControlError):
        exc = error
    elif isinstance(error, UnicodeError):
        exc = ControlError('file_encoding_invalid',
                           'lifecycle input is not valid UTF-8 (details withheld)',
                           fix='inspect and repair file encoding privately; preserve recovery inputs')
    elif isinstance(error, OSError):
        exc = ControlError('filesystem_error',
                           'lifecycle filesystem operation failed (details withheld)',
                           fix='inspect deployment-local permissions and files privately; '
                               'preserve recovery inputs and repair the cause')
    else:
        exc = ControlError('command_failed', 'lifecycle subprocess failed (details withheld)',
                           fix='inspect the failed command privately and repair the cause')
    exc.mutated = exc.mutated or mutated
    snapshot = (safe_scheduler_snapshot(ctx, target) if mutated and target else
                exc.evidence.get('scheduler', {'state': 'unavailable'}))
    exc.evidence = {**exc.evidence, **evidence,
                    'target': str(target.config_path) if target else target_path,
                    'deployment': ({'config': str(target.config_path),
                                    'unit_name': target.unit_name, 'pin': target.pin,
                                    'harness': harness_evidence(ctx, target)}
                                   if target else None),
                    'original_error': exc.code, 'scheduler': snapshot,
                    'steps': [*steps, {**current, 'status': 'failed', 'error': exc.code}]}
    if evidence.get('activation') == 'possible':
        exc.message += '; timers may already be activated and workers may be running'
    exc.fix = (exc.fix + '; ' if exc.fix else '') + (
        'inspect `/orbi status` and the failed step before deliberate recovery; '
        'do not repeat activation or a timeout unchanged, or stop active workers')
    return exc


def run_start_step(ctx, target, command, *args, timeout=CHECK_TIMEOUT):
    proc = orbi(ctx, target, command, '--config', str(target.config_path),
                *args, timeout=timeout, allow_failure=True)
    if proc.returncode != 0:
        raise ControlError(command.replace('-', '_') + '_failed',
                           f'upstream `orbi {command}` failed',
                           fix=f'inspect the failed {command} privately')


def command_start(ctx, args):
    target = None
    steps, activated = [], []
    mutated, activation = False, 'none'
    current = {'step': 'preflight', 'mutation': 'none'}
    try:
        repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
        target = select_target(ctx, repo, args.config, require=True)
        validate_target(target, repo)
        require_unit_ownership(ctx, target)
        _source, provider = start_plan(ctx, target)
        report = new_deployment_report(ctx, target, provider)
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
        current, mutated = {'step': 'lock', 'mutation': 'possible'}, True
        with locked(ctx, target.config_path):
            steps.append({'step': 'lock', 'status': 'ok', 'mutation': 'completed'})
            current = {'step': 'recheck_paths', 'mutation': 'none'}
            validate_deployment_paths(target)
            require_harness(ctx, target)
            final_extension_env(ctx, target)
            current, activation = {'step': 'setup', 'mutation': 'possible'}, 'possible'
            run_start_step(ctx, target, 'setup', '--repo', repo.full)
            steps.append({'step': 'upstream_setup', 'status': 'ok'})
            current = {'step': 'install-units', 'mutation': 'possible'}
            run_start_step(ctx, target, 'install-units', timeout=MUTATION_TIMEOUT)
            steps.append({'step': 'install_units', 'status': 'ok'})
            current = {'step': 'observe_scheduler', 'mutation': 'none'}
            snapshot = scheduler_snapshot(ctx, target)
            if snapshot['state'] != 'ok':
                raise ControlError('scheduler_unavailable',
                                   f"cannot read the target scheduler: {snapshot.get('reason')}",
                                   fix='verify the systemd user session')
            for index in range(1, target.max_concurrency + 1):
                timer = f'{target.prefix}@{index}.timer'
                item = snapshot['timers'].get(timer)
                if item and item['active'] == 'active':
                    steps.append({'step': 'activate_timer', 'unit': timer,
                                  'status': 'already-active'})
                    continue
                current = {'step': 'activate_timer', 'unit': timer, 'mutation': 'possible'}
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
                service = f'{target.prefix}@1.service'
                current = {'step': 'first_tick', 'unit': service, 'mutation': 'possible'}
                ctx.run(['systemctl', '--user', 'start', service], timeout=MUTATION_TIMEOUT)
                first_tick = 'requested'
                state = 'started'
                steps.append({'step': 'first_tick', 'status': 'requested'})
            current = {'step': 'release_lock', 'mutation': 'possible'}
        return {'action': 'start', 'platform': ctx.platform, 'status': state,
                'dry_run': False, 'repo': repo.full, 'deployment': report,
                'steps': steps, 'activated': bool(activated) or state == 'started',
                'first_tick': first_tick}
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        exc = lifecycle_failure(ctx, target, error, target_path=args.config, steps=steps,
                                current=current, mutated=mutated,
                                evidence={'activation': activation, 'activated_timers': activated})
        raise exc from (error if exc is not error else None)


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
        if state not in INACTIVE_STATES:
            pending.append({'unit': service, 'state': state})
    return pending


def command_stop(ctx, args):
    target = None
    steps, disabled, pending = [], [], []
    mutated = False
    current = {'step': 'preflight', 'mutation': 'none'}
    try:
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
                                   'unit_name': target.unit_name, 'pin': target.pin,
                                    'harness': harness_evidence(ctx, target)},
                    'disabled_timers': names, 'pending_services': pending,
                    'steps': [{'step': 'disable_target_timers', 'status': 'planned',
                               'timers': names}]}
        current, mutated = {'step': 'lock', 'mutation': 'possible'}, True
        with locked(ctx, target.config_path):
            steps.append({'step': 'lock', 'status': 'ok', 'mutation': 'completed'})
            for timer, item in owned:
                current = {'step': 'disable_timer', 'unit': timer, 'mutation': 'possible'}
                ctx.run(['systemctl', '--user', 'disable', '--now', timer],
                        timeout=MUTATION_TIMEOUT)
                disabled.append(timer)
                steps.append({'step': 'disable_timer', 'unit': timer, 'status': 'disabled'})
            current = {'step': 'observe_drain', 'mutation': 'none'}
            pending = pending_services(ctx, target)
            if any(item['state'] not in DRAIN_STATES for item in pending):
                raise ControlError(
                    'scheduler_unavailable', 'timers were disabled but worker drain is unverified',
                    fix='inspect service states with `/orbi status`; do not stop active workers')
            current = {'step': 'release_lock', 'mutation': 'possible'}
        state = 'draining' if pending else 'stopped'
        return {'action': 'stop', 'platform': ctx.platform, 'status': state,
                'dry_run': False, 'repo': repo.full,
                'deployment': {'config': str(target.config_path),
                               'unit_name': target.unit_name, 'pin': target.pin,
                                    'harness': harness_evidence(ctx, target)},
                'disabled_timers': disabled, 'pending_services': pending,
                'steps': [{'step': 'disable_target_timers', 'status': 'ok',
                           'timers': disabled}]}
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        exc = lifecycle_failure(ctx, target, error, target_path=args.config, steps=steps,
                                current=current, mutated=mutated,
                                evidence={'disabled_timers': disabled, 'pending_services': pending})
        raise exc from (error if exc is not error else None)


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
                          'fix': exc.fix, 'mutated': exc.mutated}, **exc.evidence}
    if json_mode:
        ctx.out.write(json.dumps(document, indent=2) + '\n')
    else:
        ctx.err.write(f'error={exc.code} message={exc.message} fix={exc.fix} '
                      f'mutated={exc.mutated}\n')
        for line in flatten(exc.evidence):
            ctx.err.write(line + '\n')


def command_status(ctx, args):
    repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
    if ctx.platform == 'linux':
        return status_linux(ctx, repo, args.config)
    return status_darwin(ctx, repo, args.config)


def action_usage():
    return ('python3 -B orbi_control.py [' + '|'.join(ACTIONS) + '] '
            '[--repo-dir PATH] [--config PATH] [--dry-run] [--json] '
            '[--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL]] '
            '[--resume-setup] [--harness {pi-bolt,pi}]')


def command_help(ctx, args):
    options = {
        '--harness': 'setup only: pi-bolt (new default) or pi; existing managed selection is reused; legacy is not migrated',
        '--repo-dir': 'canonical repository checkout (default: current directory)',
        '--config': 'explicit native Orbi config for this deployment',
        '--dry-run': 'preview without locking, writing, installing or activating',
        '--json': 'print one JSON document',
        '--resume-setup': 'setup only: fill a legacy missing local provider; requires explicit '
                          '--config and complete matching --pi-* inputs; never overwrite',
        '--pi-providers': 'regular Pi metadata JSON for new setup or explicit bounded resume (no credentials)',
        '--pi-provider': 'explicit provider ID; requires --pi-providers and --pi-model',
        '--pi-model': 'model ID with verified metadata; requires --pi-providers and --pi-provider',
        '--pi-thinking': 'reasoning for new setup; resume must match saved value (omission inherits)',
    }
    return {
        'action': 'help',
        'platform': ctx.platform,
        'mutations_supported': ctx.platform == 'linux',
        'actions': {name: {key: entry[key] for key in
                           ('effect', 'mutates', 'platforms', 'when')}
                    for name, entry in ACTIONS.items()},
        'options': {flag: {'effect': effect,
                           'applies_to': [name for name, entry in ACTIONS.items()
                                          if flag in entry['applies']]}
                    for flag, effect in options.items()},
        'errors': {
            'exit': 'Exit 0 means success or help; a nonzero exit reports an error, '
                    'not whether a write occurred.',
            'mutated': 'error.mutated, not the exit code, reports actual or possible writes, '
                       'including locks (text: mutated=True/False). Start/stop errors retain '
                       'completed/failed steps, target units and a read-only scheduler snapshot '
                       '(or unavailable); inspect status and actual files before deliberate recovery.',
            'code': 'error.code classifies the failure; codes are owned by the raising code.',
            'fix': 'error.fix gives the repair action; unknown actions point to /orbi help.',
        },
        'boundaries': [
            'Usage: ' + action_usage(),
            'Minimum Python 3.11; the Python floor guard also applies to help.',
            'Linux supports mutations; macOS supports status and help; other platforms '
            'support help only.',
            'Help needs no repository or deployment and reads no deployment, config, '
            'environment values or scheduler; it runs no subprocess and performs no writes.',
            'Help accepts and ignores --repo-dir, --config, --dry-run and all setup inputs.',
            'Loaded helper: ' + str(Path(__file__).resolve()) + '. If flags are missing in an '
            'older installed helper, report its path and available Kit revision, then request '
            'a separately authorized Kit update/reload; never rewrite project origin.',
            'Setup supports new preparation, existing valid reuse without selectors, or explicit '
            'bounded --resume-setup for a legacy missing local provider with matching selectors. '
            'Other incomplete/changed states require deliberate repair preserving evidence.',
            'Setup activated=false means no activation invoked here, not proof an existing '
            'scheduler is inactive. Scheduler observations are separate. A killed process cannot '
            'emit a receipt; infer retry safety from actual files. Never retry a timeout unchanged.',
            'Start/stop can fail after partial application. A failed mutation is possible, '
            'not completed; confirmed timer lists exclude failed attempts. Start activation=possible '
            'means timers or workers may already run; activation=none can still include lock writes. '
            'Never retry unchanged, compensate with enable/disable, or stop workers after failure.',
            'Status is read-only. Only setup stages source/config; only start/stop touch '
            'the scheduler. Dry-run performs no writes.',
            'Not an executor or scheduler: no tick, issue claim, review or merge.',
            'Not /unblock, /git-commit-push, /plan-with-me, /plan-for-me.',
            'Local visibility only: no cross-machine lock or capacity guarantee.',
            'Next steps: use status to inspect; setup to prepare; start only after an '
            'owner scheduling request and resolved pauses, cutover and human-only gates; '
            'stop to disable owned timers while preserving active workers.',
        ],
    }


# One ordered inventory owns dispatch, argparse action names and help metadata.
ACTIONS = {
    'status': {
        'handler': command_status,
        'effect': 'Inspect local deployment, source, providers, timers, services and queue.',
        'mutates': 'none',
        'platforms': ['linux', 'darwin'],
        'applies': ['--repo-dir', '--config', '--json'],
        'when': 'Run by default to inspect a canonical GitHub checkout; no deployment is required '
                '(an absent deployment is reported as absent).',
    },
    'setup': {
        'handler': command_setup,
        'effect': 'Stage pinned source/config and provider metadata; validate without activation.',
        'mutates': 'staging',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json',
                    '--pi-providers', '--pi-provider', '--pi-model', '--pi-thinking', '--resume-setup', '--harness'],
        'when': 'Run to prepare one unambiguous repository deployment with verified '
                'prerequisites, preserving existing pins and active workers.',
    },
    'start': {
        'handler': command_start,
        'effect': 'Install scoped units, enable owned timers and request a first tick if idle.',
        'mutates': 'scheduler',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json'],
        'when': 'Run for a prepared deployment after an owner scheduling request and '
                'resolution of explicit pauses, cutover requirements and human-only gates.',
    },
    'stop': {
        'handler': command_stop,
        'effect': 'Disable owned timers; preserve active services and report draining.',
        'mutates': 'scheduler',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json'],
        'when': 'Run to pause scheduling for a prepared, unambiguous deployment with '
                'verified unit ownership; workers may finish.',
    },
    'help': {
        'handler': command_help,
        'effect': 'Print this authoritative command reference without deployment reads.',
        'mutates': 'none',
        'platforms': ['all'],
        'applies': ['--json'],
        'when': 'Run first for help or an action inventory; no repository or deployment needed.',
    },
}


def render_help(ctx, document, json_mode):
    if json_mode:
        render(ctx, document, True)
        return
    ctx.out.write(document['boundaries'][0] + '\n')
    ctx.out.write(f"Platform: {document['platform']}; "
                  f"mutations_supported={document['mutations_supported']}\nActions:\n")
    for name, entry in document['actions'].items():
        ctx.out.write(f"  {name} [{entry['mutates']}] {entry['effect']} "
                      f"Platforms: {', '.join(entry['platforms'])}. {entry['when']}\n")
    ctx.out.write('Options:\n')
    for flag, entry in document['options'].items():
        ctx.out.write(f"  {flag}: {entry['effect']}; "
                      f"applies to {', '.join(entry['applies_to'])}.\n")
    ctx.out.write('Errors:\n')
    for text in document['errors'].values():
        ctx.out.write('  ' + text + '\n')
    ctx.out.write('Limits and next steps:\n')
    for text in document['boundaries'][1:]:
        ctx.out.write('  ' + text + '\n')


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='orbi_control.py',
        usage=action_usage() + ' [-h]',
        description='Repository-scoped Orbi lifecycle controls: '
                    + '; '.join(f"{name} [{entry['mutates']}]: {entry['effect']}"
                                for name, entry in ACTIONS.items())
                    + ' Default: status. Linux mutates; macOS also supports status; '
                    'help works everywhere; minimum Python 3.11.')
    parser.add_argument('action', nargs='?', default='status',
                        metavar='[' + '|'.join(ACTIONS) + ']')
    parser.add_argument('--repo-dir', default=None,
                        help='canonical repository checkout (default: current directory)')
    parser.add_argument('--config', default=None,
                        help='explicit native Orbi config for this deployment')
    parser.add_argument('--dry-run', action='store_true',
                        help='show the plan without locking, writing, installing or activating')
    parser.add_argument('--json', action='store_true', help='print one JSON document')
    parser.add_argument('--resume-setup', action='store_true',
                        help='setup only: resume legacy missing provider with explicit --config '
                             'and complete matching --pi-* inputs')
    parser.add_argument('--harness', choices=('pi-bolt', 'pi'), help='setup only: new default pi-bolt; explicit stock pi supported; no legacy migration')
    parser.add_argument('--pi-providers', help='setup only: Pi metadata JSON for new setup or bounded resume')
    parser.add_argument('--pi-provider', help='setup only: explicit provider ID')
    parser.add_argument('--pi-model', help='setup only: explicit model ID with verified metadata')
    parser.add_argument('--pi-thinking', help='setup only: new reasoning level, or exact saved resume value; '
                        'omitted resume thinking inherits the saved value')
    return parser.parse_args(argv)


def main(argv=None, *, env=None, platform=None, cwd=None, stdout=None, stderr=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    # Help binds nothing, including the caller's environment and working directory.
    ctx = Context(env={} if args.action == 'help' else env, platform=platform,
                  cwd='.' if args.action == 'help' else cwd, stdout=stdout, stderr=stderr)
    if sys.version_info < MIN_PYTHON:
        exc = ControlError(
            'python_unsupported',
            f'orbi_control.py requires Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer',
            fix='run it with the documented compatible Python before any mutation')
        if args.action == 'setup':
            exc.evidence = {'target': args.config, 'original_error': exc.code, 'activated': False,
                            'scheduler': {'state': 'unavailable'},
                            'steps': [{'step': 'validate_request', 'status': 'failed',
                                       'error': exc.code, 'mutation': 'none'}]}
        render_error(ctx, args.action, exc, args.json)
        return exc.exit_code
    try:
        if args.action not in ACTIONS:
            raise ControlError(
                'unknown_action', f"unknown action '{args.action}'", exit_code=2,
                fix='run /orbi help for the supported actions and their effects')
        if args.harness and args.action not in ('setup', 'help'):
            raise ControlError('invalid_harness_selection', '--harness is setup-only',
                               fix='omit the selector; status/start use persisted selection', exit_code=2)
        selectors = (args.pi_providers, args.pi_provider, args.pi_model, args.pi_thinking)
        if args.action != 'help' and args.resume_setup and (
                args.action != 'setup' or not args.config or not all(selectors[:3])):
            raise ControlError('invalid_resume_selection',
                               '--resume-setup requires setup, explicit --config and complete --pi-* inputs',
                               fix='use setup --config PATH --resume-setup --pi-providers PATH '
                                   '--pi-provider ID --pi-model ID, matching the saved selection', exit_code=2)

        if args.action != 'help' and any(value is not None for value in selectors):
            if (args.action != 'setup' or not all(selectors[:3])
                    or any(value is not None and not value.strip() for value in selectors)):
                raise ControlError(
                    'invalid_provider_selection',
                    'bootstrap requires setup with --pi-providers, --pi-provider and --pi-model',
                    fix='supply all three selectors and optionally --pi-thinking for a new '
                        'deployment, or omit all bootstrap inputs to reuse existing metadata',
                    exit_code=2)
        entry = ACTIONS[args.action]
        if 'all' not in entry['platforms'] and ctx.platform not in entry['platforms']:
            if ctx.platform == 'darwin':
                raise ControlError(
                    'unsupported_platform',
                    'macOS supports status only; setup/start/stop is refused before any '
                    'side effect',
                    fix='run `/orbi status`; operate a macOS deployment with upstream orbi',
                    exit_code=2)
            raise ControlError(
                'unsupported_platform',
                f'platform {ctx.platform} is unsupported; Linux mutates and macOS is '
                'status-only',
                fix='run status on a supported host', exit_code=2)
        document = entry['handler'](ctx, args)
        if args.action == 'help':
            render_help(ctx, document, args.json)
        else:
            render(ctx, document, args.json)
        return 0
    except ControlError as exc:
        if args.action == 'setup' and 'steps' not in exc.evidence:
            exc.evidence = {**exc.evidence, 'target': args.config, 'original_error': exc.code,
                            'activated': False, 'scheduler': {'state': 'unavailable'},
                            'steps': [{'step': 'validate_request', 'status': 'failed',
                                       'error': exc.code, 'mutation': 'none'}]}
        render_error(ctx, args.action, exc, args.json)
        return exc.exit_code


if __name__ == '__main__':
    sys.exit(main())
