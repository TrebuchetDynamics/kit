#!/usr/bin/env python3
"""Orbi repository lifecycle controls, read-only host inventory and local user template maintenance.

`python3 -B orbi_control.py [status|version|setup|start|update|stop|prune|help] [all] [--repo-dir PATH]
[--config PATH] [--dry-run] [--wait] [--apply] [--json] [--verbose] [--work]`
`python3 -B orbi_control.py set DEPLOYMENT {slots N | model PROVIDER/MODEL [THINKING]} [--json]`

- `status` (the default) is read-only: local reads, read-only `orbi doctor`
  and explicit `gh`/`systemctl` reads. It never fetches, installs, locks or
  creates a receipt.
- `version` reads one deployment identity and engine release/revision without bootstrap, scheduler or network probes.
- `status all` inventories accessible local managers/configs without repo binding,
  provider/env/session reads or scheduler actions; partial coverage is explicit.
  Reports GitHub API budget and, with `--work`, per-repo labeled issue counts.
- `setup` prepares one repository deployment without activating a timer:
  repository identity, native config, `.orbi/env` isolation, provider metadata
  reuse and a non-activating `orbi check`.
- `start` prepares an absent target or updates and validates an existing one,
  then repairs and activates scoped scheduling. A current deployment with all
  configured timers enabled and active is unchanged.
- `update` disables owned timers, cancels queued starts and stops owned workers
  (or waits for them to finish with `--wait`), then
  advances to the newest official release through `sync-engine-source`, locks
  the resolved commit as `sha:<commit>` and validates non-activating. It starts
  scheduling after validation, even after an earlier `stop`, unless `--stop`
  was requested. It never selects a provider or harness.
- `set` drains like `update --wait` and applies a backed-up config change without moving the engine pin.
- `stop` quiesces the same owned units under lock and reports `stopped` only
  after idle readback. Neither action kills or restarts a worker directly.
- `prune` lists stale unloaded user unit templates. `--apply` removes the
  verified templates and reloads the user manager, without deleting configs.

Linux owns the mutations; macOS also supports status/version; help works on every platform.
All subprocesses use an argv list (no shell). Secrets are never printed: the
helper never copies credentials and never echoes environment values or child
stderr. Minimum compatible Python: 3.11 (stdlib only, `tomllib` included).
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
from datetime import datetime, timezone
try:
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - Windows is unsupported and refused
    fcntl = None
import hashlib
from itertools import islice
import json
import os
import plistlib
import re
import shutil
import shlex
import subprocess
import sys
import stat
import tempfile
import time
from pathlib import Path
from xml.parsers.expat import ExpatError

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
# `git remote get-url` applies url.<base>.insteadOf, so a common
# `git@github.com:` rewrite reports the official HTTPS clone over SSH.
OFFICIAL_ORIGINS = frozenset({OFFICIAL_ORIGIN, OFFICIAL_ORIGIN + '.git',
                              f'git@github.com:{OFFICIAL_REPO}', f'git@github.com:{OFFICIAL_REPO}.git'})
# Pi subscription OAuth providers and whether the same ID also supports API keys.
# Unlisted IDs, including OpenRouter and custom gateways, are treated as metered.
SUBSCRIPTION_PROVIDERS = {
    'openai-codex': 'oauth',
    'google-gemini-cli': 'oauth',
    'google-antigravity': 'oauth',
    'anthropic': 'dual',
    'github-copilot': 'dual',
    'kimi-coding': 'dual',
    'meta': 'dual',
    'xai': 'dual',
}
MAX_INSTANCES = 5
NODE_FLOOR = (22, 19)
PROBE_TIMEOUT = 20
HOST_WORK_LIMIT = 1000  # GitHub search result ceiling
MUTATION_TIMEOUT = 600
CHECK_TIMEOUT = 300
START_JOB_TYPES = frozenset({'start', 'restart', 'reload-or-start'})
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
    def __init__(self, *, env=None, platform=None, cwd=None, stdout=None, stderr=None, noninteractive=False):
        self.env = dict(os.environ if env is None else env)
        self.platform = normalize_platform(platform or sys.platform)
        self.cwd = Path(cwd or os.getcwd())
        self.out = stdout if stdout is not None else sys.stdout
        self.err = stderr if stderr is not None else sys.stderr
        self.noninteractive = noninteractive
        self.lifecycle_home = None

    def which(self, name):
        return shutil.which(name, path=self.env.get('PATH'))

    def run(self, argv, *, env=None, timeout=PROBE_TIMEOUT, allow_failure=False,
            cwd=None):
        child = dict(self.env if env is None else env)
        child.setdefault('PYTHONDONTWRITEBYTECODE', '1')
        stdin = {}
        if self.noninteractive:
            child.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0',
                         GIT_ASKPASS='/bin/false', SSH_ASKPASS_REQUIRE='never')
            stdin['stdin'] = subprocess.DEVNULL
        command = [str(part) for part in argv]
        try:
            proc = subprocess.run(command, env=child, capture_output=True,
                                  text=True, timeout=timeout,
                                  cwd=str(cwd) if cwd else None, **stdin)
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
    if 'allowed_providers' in data:
        allowed = data['allowed_providers']
        if not isinstance(allowed, list) or not all(isinstance(item, str) and item.strip() for item in allowed):
            raise ControlError('config_invalid', f'{path} has an invalid allowed_providers',
                               fix='set allowed_providers to an array of provider IDs', exit_code=2)
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


def explicit_config_file(value):
    path = checked_path(value, 'config').resolve()
    if not path.is_file():
        raise ControlError('config_missing', f'explicit config {path} does not exist',
                           fix='pass an existing native Orbi config path')
    return path


def load_deployments(ctx, repo_path, explicit_config=None, *, repo_full=None):
    paths = []
    if explicit_config:
        paths.append(explicit_config_file(explicit_config))
    paths.append(repo_path / 'orbi.toml')
    strict_paths = set(paths)
    share = data_home(ctx)
    if share.is_dir():
        paths.extend(sorted(share.glob('*/orbi.toml')))
    units = user_unit_dir(ctx)
    if units.is_dir():
        for service in sorted(units.glob('orbi*.service')):
            config = installed_config(service, home_dir(ctx))
            if config is not None:
                paths.append(config)
    deployments, invalid, seen = [], [], set()
    for candidate in paths:
        resolved = checked_path(candidate, 'config').resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if not resolved.is_file():
            continue
        try:
            deployments.append(deployment_from(resolved))
        except ControlError as exc:
            if candidate in strict_paths or repo_full is None:
                raise
            invalid.append((resolved, exc))
    if invalid:
        if not any(repo_full in item.source_repos for item in deployments):
            raise invalid[0][1]
        # A broken TOML file can still name the repo. Do not confuse it with a longer name.
        repo_name = re.compile(rf'(?<![\w.-]){re.escape(repo_full)}(?![\w.-])', re.ASCII)
        for path, exc in invalid:
            try:
                raw = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                raw = ''
            if repo_name.search(raw):
                raise exc
            warning = f'warning=invalid_discovered_config path={path} fix=repair or remove the config\n'
            with contextlib.suppress(OSError, ValueError):
                if ctx.err is sys.__stderr__:
                    # A failed buffered write could also fail on interpreter exit.
                    os.write(ctx.err.fileno(), warning.encode(ctx.err.encoding or 'utf-8', 'backslashreplace'))
                else:
                    ctx.err.write(warning)
    return deployments


def select_target(ctx, repo, explicit_config=None, *, require=False):
    deployments = load_deployments(ctx, repo.path, explicit_config, repo_full=repo.full)
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
                           fix='run `/orbi setup --prepare-only` to prepare this repository without activation first')
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
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in '\u2028\u2029' for c in value)
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
            if stored is not None:
                try:
                    for part in stored.split(':'):
                        env_literal(part, path=True)
                except ControlError:
                    return {**evidence, 'resolution': 'stored PATH is not reliably interpretable; '
                            'service resolution unverified'}
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
        planned = selection is deployment.harness_selection and not deployment.config_path.exists()
        if planned and not any(fields):
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
        if planned:
            return {**evidence, 'state': 'unknown', 'reason': 'config publication planned; saved routing verified'}
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
    """Publish complete bytes without clobbering new targets; return whether bytes changed."""
    path = checked_path(path, 'publication path')
    before = file_identity(path)
    payload = text.encode('utf-8')
    if before is not None:
        if not path.is_file():
            raise ControlError('unknown_target', 'publication target is not a regular file',
                               fix='inspect the target and preserve recovery evidence', exit_code=2)
        if before[-1] == payload:
            return False
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
    return True


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
    return atomic_publish(deployment.env_path, render_env(ctx, deployment), reuse_only=reuse_only)


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


def require_allowed_provider(deployment, provider, model):
    allowed = deployment.data.get('allowed_providers')
    if allowed is not None and provider not in allowed:
        raise ControlError('provider_not_allowed',
                           f'{provider}/{model} is not permitted by allowed_providers in {deployment.config_path}',
                           fix='select an allowed provider or deliberately update allowed_providers in orbi.toml; '
                               '--allow-metered does not override this policy', exit_code=2)


def provider_metered(ctx, deployment, provider, model):
    """Classify the configured route; None means a dual-mode provider lacks auth evidence."""
    mode = SUBSCRIPTION_PROVIDERS.get(provider)
    if mode is None:
        return True
    # A model catalog can provide explicit credentials even for a built-in ID.
    # Use a bounded read here: host inventory must not block on deployment files.
    try:
        path = provider_path(deployment)
        entry = json.loads(bounded_text(path, limit=1024 * 1024))['providers'][provider] if path else {}
        overrides = entry.get('modelOverrides', {})
        selected = [item for item in entry.get('models', []) if isinstance(item, dict) and item.get('id') == model]
        for item in (entry, *selected, overrides.get(model)):
            if isinstance(item, dict) and (item.get('apiKey') or (
                    isinstance(headers := item.get('headers'), dict)
                    and any(key.lower() in ('authorization', 'x-api-key') for key in headers))):
                return True
    except (ControlError, OSError, ValueError, AttributeError, KeyError, TypeError, RecursionError):
        return None
    if mode == 'oauth':
        return False
    # The pinned Runner links this auth store into its per-run profile. Read only
    # the credential type; do not execute key commands, refresh, or disclose credentials.
    try:
        auth = json.loads(bounded_text(home_dir(ctx) / '.pi/agent/auth.json', limit=1024 * 1024))
    except (OSError, ValueError, RecursionError):
        return None
    credential = auth.get(provider) if isinstance(auth, dict) else None
    kind = credential.get('type') if isinstance(credential, dict) else None
    return False if kind == 'oauth' else True if kind in ('api_key', 'apiKey') else None


def guard_provider_selection(ctx, deployment, candidate, *, allow_metered, bootstrap=False):
    provider, model = candidate.data['pi_provider'], candidate.data['pi_model']
    require_allowed_provider(deployment, provider, model)
    saved = deployment.data.get('pi_provider'), deployment.data.get('pi_model')
    if (not allow_metered and (provider, model) != saved
            and (metered := provider_metered(ctx, candidate, provider, model)) is not False
            and (not saved[0] or provider_metered(ctx, deployment, *saved) is not True)):
        retry = ('use `/orbi set DEPLOYMENT model PROVIDER/MODEL --allow-metered` to change the saved selection'
                 if bootstrap else 'rerun with --allow-metered to confirm')
        pricing = 'is metered' if metered else 'may incur metered charges (subscription auth not verified)'
        raise ControlError('metered_confirmation_required', f'{provider}/{model} {pricing}',
                           fix=f'keep a subscription provider or {retry}', exit_code=2)


def require_provider(deployment):
    if provider := deployment.data.get('pi_provider'):
        require_allowed_provider(deployment, provider, deployment.data.get('pi_model'))
    if review := deployment.data.get('review_pi_provider'):
        require_allowed_provider(deployment, review,
                                 deployment.data.get('review_pi_model') or deployment.data.get('pi_model'))
    evidence = provider_evidence(deployment)
    if evidence['state'] != 'ok':
        raise ControlError(
            'provider_unavailable',
            f'deployment {deployment.config_path} has no verified model provider: '
            + evidence.get('reason', 'unknown reason'),
            fix='configure pi_providers/pi_provider/pi_model with published model metadata, '
                'then run `/orbi setup --prepare-only` for non-activating validation')
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
            fix='run `/orbi setup --prepare-only --pi-providers PATH --pi-provider ID --pi-model ID '
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
        try:
            sanitized_metadata({'providers': {identity: entry}})
        except ControlError as exc:
            raise ControlError('auth_unverified', f'provider {identity} has invalid credential metadata',
                               fix=exc.fix) from exc
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
            fix='run `/orbi setup --prepare-only` to install it without activation, or uv tool install --editable '
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


def require_unit_ownership(ctx, deployment, *, symlink_error='unknown_target'):
    units = user_unit_dir(ctx)
    if not units.is_dir():
        return
    prefix = deployment.prefix
    service = units / f'{prefix}@.service'
    timer = units / f'{prefix}@.timer'
    for path in (service, timer):
        if path.is_symlink():
            raise ControlError(symlink_error,
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
        guard_provider_selection(ctx, deployment, selection, allow_metered=args.allow_metered)
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
def locked(ctx, key, *, nonblocking=False):
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
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        except BlockingIOError as error:
            raise ControlError('deployment_locked', f'deployment lock busy: {key}',
                               fix='wait for the other lifecycle operation to finish') from error
        # Remove the old scheduling record under its deployment lock; never read it.
        path.with_suffix('.maintenance.json').unlink(missing_ok=True)
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
                'rerun `/orbi setup --prepare-only` without bootstrap inputs for non-activating validation '
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


def scheduler_inventory(deployment, *, scan_last=MAX_INSTANCES):
    """The scan describes local evidence, not total deployment capacity/activity."""
    return {'scope': 'local-target-prefix', 'scan_first': 1, 'scan_last': scan_last,
            'outside_scan': 'unobserved', 'configured_slots': deployment.max_concurrency,
            'configured_slots_covered': deployment.max_concurrency <= scan_last,
            'counts': {name: {'state': 'unavailable', 'value': None}
                       for name in ('enabled_timers', 'active_timers', 'running_services')}}


def unavailable_scheduler(deployment, reason, *, scan_last=MAX_INSTANCES):
    return {'state': 'unavailable', 'reason': reason, 'timers': {}, 'services': {},
            'inventory': scheduler_inventory(deployment, scan_last=scan_last)}


def fragment_kind(fragment, unit):
    if not fragment:
        return 'absent'
    path = Path(fragment)
    try:
        path.read_text()
    except (OSError, UnicodeError):
        return 'unknown'
    if path.name == unit:
        return 'instance'
    if path.name == re.sub(r'@\d+\.', '@.', unit):
        return 'template'
    return 'unknown'


def scheduler_snapshot(ctx, deployment, *, indices=None, scan_last=MAX_INSTANCES):
    timers, services = {}, {}
    inventory = scheduler_inventory(deployment, scan_last=scan_last)
    ownership_complete = True
    for index in (indices if indices is not None else range(1, scan_last + 1)):
        timer = f'{deployment.prefix}@{index}.timer'
        service = f'{deployment.prefix}@{index}.service'
        fragment = systemctl_show(ctx, timer, 'FragmentPath')
        if fragment.returncode != 0:
            return unavailable_scheduler(deployment, 'the systemd user session is not readable',
                                         scan_last=scan_last)
        timer_fragment = fragment.stdout.strip()
        installed = bool(timer_fragment)
        service_fragment = systemctl_show(ctx, service, 'FragmentPath')
        if service_fragment.returncode != 0:
            return unavailable_scheduler(deployment, 'loaded service ownership could not be verified',
                                         scan_last=scan_last)
        service_path = service_fragment.stdout.strip()
        owned = False
        if service_path:
            owned = installed_config(Path(service_path), home_dir(ctx)) == deployment.config_path
            # Legacy owned remains unchanged. Ambiguous/foreign fragments cannot
            # support numeric target counts, even if the first binding matches.
            if not owned or len(re.findall(r'\bORBI_CONFIG=', Path(service_path).read_text())) != 1:
                ownership_complete = False
        if installed and not owned:
            ownership_complete = False
        state = systemctl_state(ctx, service)
        services[service] = {'state': state, 'owned': owned,
                             'installed': bool(service_path),
                             'configured': index <= deployment.max_concurrency,
                             'fragment_kind': fragment_kind(service_path, service)}
        if installed:
            try:
                enabled = timer_enabled(ctx, timer)
            except ControlError as exc:
                exc.evidence['scheduler'] = unavailable_scheduler(deployment, exc.message,
                                                                  scan_last=scan_last)
                raise
            timers[timer] = {'installed': True, 'owned': owned, 'enabled': enabled,
                             'active': systemctl_state(ctx, timer),
                             'configured': index <= deployment.max_concurrency,
                             'fragment_kind': fragment_kind(timer_fragment, timer)}
    known_states = DRAIN_STATES | INACTIVE_STATES
    values = dict.fromkeys(inventory['counts'])
    if ownership_complete:
        timer_fragments_known = all(item['fragment_kind'] != 'unknown' for item in timers.values())
        if timer_fragments_known:
            values['enabled_timers'] = sum(item['enabled'] for item in timers.values())
            if all(item['active'] in known_states for item in timers.values()):
                values['active_timers'] = sum(item['active'] == 'active' for item in timers.values())
        if all(item['fragment_kind'] != 'unknown'
               and (not item['installed'] or item['state'] in known_states)
               for item in services.values()):
            values['running_services'] = sum(item['installed'] and item['owned']
                                             and item['state'] in ACTIVE_STATES
                                             for item in services.values())
    inventory['counts'] = {name: {'state': 'ok' if value is not None else 'unavailable',
                                 'value': value} for name, value in values.items()}
    if any(item['state'] not in known_states for item in services.values()):
        return {'state': 'unavailable', 'reason': 'some service states could not be verified',
                'timers': timers, 'services': services, 'inventory': inventory}
    return {'state': 'ok', 'timers': timers, 'services': services, 'inventory': inventory}


def safe_scheduler_snapshot(ctx, deployment):
    scan_last = max(MAX_INSTANCES, deployment.max_concurrency)
    try:
        return scheduler_snapshot(ctx, deployment, scan_last=scan_last)
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError):
        return unavailable_scheduler(deployment, 'scheduler evidence could not be read',
                                     scan_last=scan_last)


def deployment_state(snapshot):
    if snapshot.get('state') != 'ok':
        return 'unavailable'
    states = [item['state'] for item in snapshot['services'].values()]
    if any(state not in DRAIN_STATES | INACTIVE_STATES for state in states):
        return 'unavailable'
    if 'active' in states:
        return 'running'
    if any(state in {'activating', 'reloading'} for state in states):
        return 'transitional'
    if any(state in DRAIN_STATES for state in states):
        return 'draining'
    if any(item['owned'] and (item['enabled'] or item['active'] == 'active')
           for item in snapshot['timers'].values()):
        return 'prepared'
    return 'stopped'


# Batch native dependency evidence rather than one detail/LLM call per issue.
QUEUE_PAGE_LIMIT = 3
QUEUE_DETAIL_LIMIT = 10
QUEUE_QUERY = '''query($owner:String!, $name:String!, $cursor:String) {
  repository(owner:$owner, name:$name) {
    issues(first:100, after:$cursor, states:OPEN,
           orderBy:{field:CREATED_AT,direction:ASC}) {
      nodes {
        __typename number title url state
        labels(first:100) { nodes { name } pageInfo { hasNextPage } }
        assignees(first:10) { nodes { login } pageInfo { hasNextPage } }
        blockedBy(first:20) {
          nodes { number title url state } pageInfo { hasNextPage }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}'''


def github_read(ctx, argv):
    """Read JSON without leaking child output (including GraphQL error text)."""
    try:
        proc = ctx.run(['gh', *argv], allow_failure=True)
        value = json.loads(proc.stdout)
        # gh exits nonzero for GraphQL errors even when data is partially usable.
        # Let the queue validator retain valid rows and disclose the errors.
        if proc.returncode and not (argv[:2] == ['api', 'graphql']
                                    and isinstance(value, dict) and value.get('errors')):
            return None
        return value
    except (ControlError, OSError, ValueError):
        return None


def pending_classification(issue):
    labels = {node['name'] for node in issue['labels']['nodes']}
    owners = [node['login'] for node in issue['assignees']['nodes']]
    deps = [node for node in issue['blockedBy']['nodes'] if node['state'] == 'OPEN']
    incomplete = any(issue[field]['pageInfo']['hasNextPage']
                     for field in ('labels', 'assignees', 'blockedBy'))
    item = {key: issue[key] for key in ('number', 'title', 'url')}
    item.update(labels=sorted(labels), owners=owners, prerequisites=deps)
    if 'ai-blocked' in labels:
        group, reason, action = ('actionable_blocker', 'ai-blocked; recovery diagnosis required',
                                'Use /unblock deliberately with the existing owner; preserve retained work, '
                                'inspect the blocker before any retry; do not blindly requeue.')
    elif labels & {'ai-in-progress', 'ai-pr-opened', 'ai-fix-needed',
                   'ai-awaiting-merge'} or owners:
        group, reason, action = ('active_owned', 'ownership/active label or assignee; worker activity unverified',
                                'Consult the existing owner and linked PR/checks; do not start a competing attempt.')
    elif 'ai-epic' in labels:
        group, reason, action = ('epic', 'ai-epic coordination; not executable',
                                'Inspect child issue outcomes with the planning owner; do not dispatch the epic.')
    elif labels & {'ai-planning', 'ai-paused', 'ai-needs-detail'}:
        group, reason, action = ('planning_paused', 'planning/paused label; not dispatchable',
                                'Next required input is unknown from status evidence; consult the issue and '
                                'planning owner for the recorded decision or pause gate.')
    elif deps:
        group, reason, action = ('native_dependency', 'open native blockedBy prerequisite',
                                'Follow the linked prerequisites to verified completion; issue ordering is not a dependency.')
    elif 'ai-ready' in labels and not incomplete:
        group, reason, action = ('ready', 'ai-ready with no observed ownership, hold or open native prerequisite',
                                'Ready is not pickup: inspect scheduler/owner evidence and existing pauses; '
                                'only separately authorized /orbi start may activate scheduling.')
    else:
        group, reason, action = ('unknown', 'readiness not evidenced or nested evidence incomplete',
                                'Inspect the issue with its owner; resolve missing readiness/dependency evidence without guessing.')
    item.update(reason=reason, next_action=action)
    return group, item, incomplete


def queue_evidence(ctx, repo):
    issues, gaps, cursor, seen_cursors = {}, [], None, set()
    pages = 0
    listing_complete = False
    for _ in range(QUEUE_PAGE_LIMIT):
        argv = ['api', 'graphql', '-f', 'query=' + QUEUE_QUERY,
                '-F', 'owner=' + repo.owner, '-F', 'name=' + repo.name]
        if cursor:
            argv += ['-F', 'cursor=' + cursor]
        value = github_read(ctx, argv)
        try:
            if isinstance(value, dict) and value.get('errors'):
                gaps.append('GitHub reported GraphQL errors; coverage incomplete')
            connection = value['data']['repository']['issues']
            nodes, info = connection['nodes'], connection['pageInfo']
            if not isinstance(nodes, list) or not isinstance(info['hasNextPage'], bool):
                raise ValueError
            for issue in nodes:
                if issue.get('__typename') != 'Issue' or issue.get('state') != 'OPEN':
                    continue  # Never count PR records or closed issues as pending.
                # Validate the contract before retaining a row as evidence.
                if not isinstance(issue['number'], int):
                    raise ValueError
                pending_classification(issue)
                issues[issue['number']] = issue
            pages += 1
            if not info['hasNextPage']:
                listing_complete = True
                break
            cursor = info['endCursor']
            if not cursor or cursor in seen_cursors:
                gaps.append('issue pagination cursor missing or repeated')
                break
            seen_cursors.add(cursor)
        except (KeyError, TypeError, ValueError, AttributeError):
            gaps.append('GitHub issue read failed or returned incomplete/unreadable data')
            break
    if not listing_complete and not gaps:
        gaps.append('issue page limit reached; more open issues may exist')

    groups = {name: [] for name in ('actionable_blocker', 'active_owned', 'native_dependency',
                                   'planning_paused', 'epic', 'ready', 'unknown')}
    details_left, pr_cache = QUEUE_DETAIL_LIMIT, {}
    # Prioritize blockers for the bounded detail budget, retaining list order within groups.
    classified = [pending_classification(issue) for issue in issues.values()]
    classified.sort(key=lambda row: list(groups).index(row[0]))
    for group, item, incomplete in classified:
        groups[group].append(item)
        if incomplete:
            gaps.append(f"#{item['number']} nested label/owner/dependency coverage incomplete")
        if group not in {'actionable_blocker', 'active_owned'}:
            continue
        comments, comments_complete = [], False
        for page in range(1, QUEUE_PAGE_LIMIT + 1):
            if not details_left:
                break
            details_left -= 1
            value = github_read(ctx, ['api', '--method', 'GET',
                f'repos/{repo.full}/issues/{item["number"]}/comments?per_page=100&page={page}'])
            if not isinstance(value, list) or any(not isinstance(row, dict) or
                                                     not isinstance(row.get('body'), str)
                                                     for row in value):
                break
            comments.extend(value)
            if len(value) < 100:
                comments_complete = True
                break
        item['detail_coverage'] = 'complete' if comments_complete else 'partial'
        if not comments_complete:
            gaps.append(f"#{item['number']} comment detail unavailable or capped")
        pr_numbers = set()
        retry_unsafe, branch_changed = False, False
        for comment in comments:
            body = comment['body']
            # Only structured failure receipts establish retry safety; never infer safe retry.
            if group == 'actionable_blocker':
                for match in re.finditer(r'<!-- orbi:failure:v1 (\{.*?\}) -->', body):
                    try:
                        failure = json.loads(match.group(1))
                    except ValueError:
                        continue
                    if failure.get('retry_safe') is False:
                        retry_unsafe = True
                        if re.search(r'(?:branch|remote).{0,120}(?:chang|conflict)', body, re.I):
                            branch_changed = True
            pr_numbers.update(int(number) for number in re.findall(
                rf'https://github\.com/{re.escape(repo.full)}/pull/(\d+)\b', body))
        # A later terse duplicate receipt must not erase the concrete diagnosis.
        if retry_unsafe:
            item['retry_safe'] = False
            item['reason'] = 'ai-blocked; failure receipt forbids blind retry (retry_safe=false)'
            item['next_action'] = ('Use /unblock deliberately with the existing owner; '
                'inspect the failure and retained work before any retry; '
                'retry_safe=false forbids blind retry or requeue.')
            if branch_changed:
                item['reason'] += '; reported branch change/conflict'
                item['next_action'] = ('Use /unblock deliberately: compare the current remote head '
                    'and retained work with the existing owner before any retry; '
                    'retry_safe=false forbids blind retry or requeue. Preserve both candidates.')
        item['pull_request_scope'] = 'observed comment links only; unlinked PRs unknown'
        item['pull_requests'] = []
        for number in sorted(pr_numbers):
            if number not in pr_cache:
                if not details_left:
                    gaps.append(f'PR #{number} detail budget exhausted')
                    continue
                details_left -= 1
                pr_cache[number] = github_read(ctx, ['pr', 'view', str(number), '--repo', repo.full,
                    '--json', 'number,url,state,headRefName,headRefOid'])
            value = pr_cache[number]
            if not isinstance(value, dict) or value.get('state') not in {'OPEN', 'CLOSED', 'MERGED'}:
                gaps.append(f'PR #{number} state unavailable')
                item['pull_requests'].append({'number': number,
                    'url': f'https://github.com/{repo.full}/pull/{number}', 'state': 'unavailable'})
                continue
            item['pull_requests'].append({key: value.get(key) for key in
                                         ('number', 'url', 'state', 'headRefName', 'headRefOid')})
            item['pull_requests'][-1]['meaning'] = (
                'open PR, not successful delivery' if value['state'] == 'OPEN' else
                'merged PR; issue acceptance/live qualification not established by status' if value['state'] == 'MERGED' else
                'closed PR, not evidence of successful delivery')

    coverage = {'complete': listing_complete and not gaps, 'listing_complete': listing_complete,
                'pages_read': pages, 'page_limit': QUEUE_PAGE_LIMIT, 'page_size': 100,
                'detail_limit': QUEUE_DETAIL_LIMIT, 'details_read': QUEUE_DETAIL_LIMIT - details_left,
                'gaps': gaps}
    result = {'state': 'ok' if coverage['complete'] else 'partial' if issues else 'unavailable',
              'coverage': coverage,
              'next_action': ('Inspect the evidenced next actions; zero ready does not mean zero pending. '
                              'Status authorizes no recovery or scheduler writes.' if coverage['complete'] else
                              'Restore GitHub auth/read access or inspect the disclosed coverage limits; '
                              'rerun read-only status. Counts are observed lower bounds, not an empty repository.')}
    if issues or listing_complete:
        result.update(ready=[f"#{item['number']} {item['title']}" for item in groups['ready']],
                      pending_count=len(issues), pending=groups)
    if gaps:
        result['reason'] = '; '.join(gaps)
    return result

def doctor_evidence(ctx, deployment):
    state, _ = bootstrap_evidence(ctx, deployment)
    if state != 'compatible':
        return {'state': 'unavailable', 'reason': f'bootstrap is {state}'}
    proc = orbi(ctx, deployment, 'doctor', '--config', str(deployment.config_path),
                timeout=120, allow_failure=True)
    return {'state': 'ok' if proc.returncode == 0 else 'failed'}


def bounded_bytes(path, limit=65536):
    """Read regular metadata, never sessions/env/journals, with a hard byte limit."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('metadata is not a regular file')
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('metadata exceeds read limit')
    return raw


def bounded_text(path, limit=65536):
    return bounded_bytes(path, limit).decode('utf-8')


LIFECYCLE_LIMIT = 200


def lifecycle_lines(path):
    try:
        return bounded_text(checked_path(path, 'lifecycle log'), limit=1024 * 1024).splitlines()
    except FileNotFoundError:
        return []


def last_lifecycle(target):
    try:
        line = lifecycle_lines(target.deploy_home / 'lifecycle.log')[-1:]
        entry = json.loads(line[0]) if line else None
        fields = ('timestamp', 'action', 'user', 'result')
        if (isinstance(entry, dict) and all(isinstance(entry.get(key), str) for key in fields)
                and isinstance(entry.get('argv'), list) and all(isinstance(flag, str) for flag in entry['argv'])):
            return {key: entry[key] for key in (*fields, 'argv')}
    except (ControlError, OSError, ValueError, RecursionError):
        pass  # Missing or unreadable audit evidence must not break status.
    return None


def record_lifecycle(ctx, home, args, result):
    if home is None:
        return
    try:
        import pwd

        path = home / 'lifecycle.log'
        # Serialize appends across processes without leaving an extra lock file.
        # The directory must already exist; never create one just to log a failure.
        directory = os.open(checked_path(home, 'deploy home'), os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW)
        try:
            # Audit contention must not hang an already-completed command.
            for attempt in range(20):
                try:
                    fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if attempt == 19:
                        raise
                    time.sleep(0.05)
            # Record option names, not user-supplied paths, identifiers or values.
            argv = [args.action, *(flag for flag in ACTIONS[args.action]['applies']
                                   if getattr(args, flag[2:].replace('-', '_'), None))]
            entry = {'timestamp': datetime.now(timezone.utc).isoformat(), 'action': args.action,
                     'argv': argv, 'user': pwd.getpwuid(os.getuid()).pw_name, 'result': result}
            lines = lifecycle_lines(path)[1 - LIFECYCLE_LIMIT:] + [json.dumps(entry)]
            atomic_publish(path, '\n'.join(lines) + '\n')
        finally:
            os.close(directory)
    except (ControlError, OSError, ValueError, KeyError):
        with contextlib.suppress(OSError):
            ctx.err.write('warning=lifecycle_log_unavailable fix=inspect deploy-home log access and contention\n')


def engine_summary(ctx, target, source, *, include_bootstrap=True):
    """Deployment-bound package metadata is not the bootstrap CLI's version."""
    result = {'state': 'unknown', 'version': None, 'revision': source.get('head'),
              'provenance': str(target.deploy_home / 'pyproject.toml'),
              'selected_source': source,
              'reason': 'deployment package/revision metadata is not verified'}
    try:
        manifest = bounded_text(target.deploy_home / 'pyproject.toml')
        project = tomllib.loads(manifest)['project']
        committed = ctx.run(['git', '-C', str(target.deploy_home), 'show',
                             'HEAD:pyproject.toml'], allow_failure=True)
        # git diff's default autoRefreshIndex may otherwise write stat data.
        clean = ctx.run(['git', '-C', str(target.deploy_home), 'diff', '--quiet',
                         'HEAD', '--', 'pyproject.toml', 'src/orbi'],
                        env={**ctx.env, 'GIT_OPTIONAL_LOCKS': '0'}, allow_failure=True)
        if (source['state'] == 'verified' and clean.returncode == 0 and committed.returncode == 0
                and committed.stdout == manifest and project.get('name') in {'orbi', 'orbi-cli'}
                and isinstance(project.get('version'), str)
                and re.fullmatch(r'\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)', project['version'])):
            result.update(state='verified', version=project['version'])
            result.pop('reason')
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, ControlError):
        pass
    if not include_bootstrap:
        return result
    path = home_dir(ctx) / '.local/bin/orbi'
    cli = {'state': 'unavailable', 'path': str(path), 'version': None,
           'provenance': 'bootstrap --version (not deployment release proof)'}
    try:
        proc = ctx.run([str(path), '--version'], allow_failure=True)
        match = re.fullmatch(r'orbi (\d+\.\d+\.\d+[a-zA-Z0-9.+-]*)\s*', proc.stdout)
        if proc.returncode == 0 and match:
            cli.update(state='unverified', version=match[1])
    except ControlError:
        pass
    cli['comparison'] = ('unknown' if not result['version'] or not cli['version'] else
                         'match' if cli['version'] == result['version'] else 'mismatch')
    result['bootstrap_cli'] = cli
    return result


def service_binding(ctx, unit, manager='user'):
    proc = ctx.run(['systemctl', '--' + manager, 'show', unit,
                    '-p', 'ActiveState', '-p', 'MainPID', '-p', 'InvocationID',
                    '-p', 'WorkingDirectory', '-p', 'FragmentPath'], allow_failure=True)
    if proc.returncode or len(proc.stdout) > 16384:
        return {}
    return dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)


def current_run(ctx, target, repo, unit, *, manager='user'):
    """Only this live service invocation can establish identity, never newest files.

    Journal's PID + InvocationID bind a run_start scene to the current owned
    process. Read lifecycle scenes separately so normal command/activity volume
    cannot evict the start binding. Recheck after both bounded reads to reject
    exit/restart races. A start scene absent from retention remains unknown.
    """
    unknown = {'state': 'active/issue unknown',
               'reason': 'current invocation/deployment/run binding is missing or conflicting',
               'next_action': 'Inspect owned service invocation and deployment logs read-only; '
                              'restore readable bindings before attributing an issue. Do not requeue or restart.'}
    try:
        binding_args = (ctx, unit) if manager == 'user' else (ctx, unit, manager)
        binding = service_binding(*binding_args)
        invocation, pid = binding.get('InvocationID', ''), binding.get('MainPID', '')
        fragment = binding.get('FragmentPath', '')
        if (binding.get('ActiveState') != 'active' or not re.fullmatch(r'[0-9a-f]{32}', invocation)
                or not pid.isdecimal() or int(pid) <= 0
                or binding.get('WorkingDirectory') != str(target.deploy_home)
                or not fragment or installed_config(fragment, home_dir(ctx)) != target.config_path
                or len(re.findall(r'\bORBI_CONFIG=', bounded_text(fragment))) != 1):
            return unknown
        journal = ['journalctl', '--' + manager, '-u', unit,
                   '_SYSTEMD_INVOCATION_ID=' + invocation, '-n', '100', '-o', 'json',
                   '--output-fields=MESSAGE,_PID,_SYSTEMD_INVOCATION_ID', '--no-pager']
        lifecycle = ctx.run([*journal, '--grep=^(INFO|WARNING|ERROR) '
                             r'\[([0-9a-f]{8})\] (run_start|run_end|run_failed) '],
                            allow_failure=True)
        recent = ctx.run(journal, allow_failure=True)
        if any(proc.returncode or len(proc.stdout) > 524288 for proc in (lifecycle, recent)):
            return unknown
        identity, details, ended = None, {}, False
        # journalctl --grep with -n implies --reverse; the ordinary tail is
        # chronological. Reduce lifecycle boundaries oldest first as well.
        for line in [*reversed(lifecycle.stdout.splitlines()), *recent.stdout.splitlines()]:
            if not line.strip():
                continue
            row = json.loads(line)
            if (row.get('_PID') != pid or row.get('_SYSTEMD_INVOCATION_ID') != invocation
                    or not isinstance(row.get('MESSAGE'), str) or len(row['MESSAGE']) > 8192):
                continue
            # Upstream journal.RunIdFilter + pi_activity.format_run_scene.
            match = re.fullmatch(r'(?:INFO|WARNING|ERROR) \[([0-9a-f]{8})\] '
                                 r'(run_start|activity|heartbeat|run_end|run_failed) (.*)', row['MESSAGE'])
            if not match:
                continue
            fields = {}
            for token in shlex.split(match[3]):
                if '=' in token:
                    key, value = token.split('=', 1)
                    if key in fields:  # conflicting/torn scenes are not identity
                        return unknown
                    fields[key] = value
            reference = fields.get('issue', '')
            if not re.fullmatch(re.escape(repo.full) + r'#[1-9][0-9]*', reference):
                return unknown
            run = fields.get('run', match[1])
            if run != match[1]:
                return unknown
            candidate = (int(reference.rsplit('#', 1)[1]), run)
            if identity is not None and identity != candidate:
                return unknown
            if match[2] == 'run_start':
                identity = candidate
                ended = False
            elif identity is None:
                continue
            if match[2] in {'run_end', 'run_failed'}:
                ended = True
            for key, pattern in (('phase', r'[a-z_]{1,40}'),
                                 ('last_activity', r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z')):
                value = fields.get(key, '')
                if re.fullmatch(pattern, value):
                    details[key] = value
        if identity is None or ended or service_binding(*binding_args) != binding:
            return unknown
        number, run = identity
        return {'state': 'running', 'issue': {'number': number,
                'url': f'https://github.com/{repo.full}/issues/{number}'},
                'run_id': run, 'provenance': 'current owned service InvocationID + MainPID journal run_start',
                **details}
    except (ControlError, OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return unknown


def activity_linux(ctx, target, repo, snapshot):
    slots, ticks = {}, {}
    for unit, service in snapshot.get('services', {}).items():
        state = service['state']
        if not service['owned'] or not service['installed']:
            item = {'state': 'unknown', 'reason': 'no verified owned service binding'}
        elif state == 'active':
            item = current_run(ctx, target, repo, unit)
        elif state in {'activating', 'reloading', 'deactivating'}:
            item = {'state': 'draining' if state == 'deactivating' else 'starting'}
        elif state in INACTIVE_STATES:
            item = {'state': 'idle'}
        else:
            item = {'state': 'unknown', 'reason': 'service state unavailable'}
        item['health'] = 'failed' if state == 'failed' else 'unknown' if state == 'unavailable' else state
        slots[unit] = item
    for timer, item in snapshot.get('timers', {}).items():
        if not item['owned']:
            continue
        try:
            proc = ctx.run(['systemctl', '--user', 'show', timer, '-p', 'LastTriggerUSec',
                            '-p', 'NextElapseUSecRealtime'], allow_failure=True)
            values = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
            ticks[timer] = {key: value for key, value in values.items()
                            if key in {'LastTriggerUSec', 'NextElapseUSecRealtime'}
                            and len(value) <= 100} if proc.returncode == 0 else {}
        except (ControlError, ValueError):
            ticks[timer] = {}
    complete = (snapshot['state'] == 'ok' and bool(slots)
                and snapshot.get('inventory', {}).get('configured_slots_covered', False)) and all(
        item['state'] in {'running', 'idle'} for item in slots.values())
    return {'slots': slots, 'working': {'state': 'ok' if complete else 'unavailable',
             'value': sum(item['state'] == 'running' for item in slots.values()) if complete else None},
            'ticks': ticks, 'scope': 'local-target-prefix; outside scheduler scan unobserved'}


def local_deployment_summary(ctx, target, *, metadata_only=False):
    """Reusable local metadata; no queue, GitHub, doctor or repo-specific probes."""
    if metadata_only:
        try:
            source = source_evidence(ctx, target)
        except ControlError:
            source = {'state': 'unavailable'}
        return {'config': str(target.config_path),
                'engine': engine_summary(ctx, target, source, include_bootstrap=False)}
    source = source_evidence(ctx, target)
    harness = harness_evidence(ctx, target)
    usable = harness['state'] == 'verified' or (harness['management'] == 'legacy' and harness['state'] == 'unknown')
    provider = provider_evidence(target)
    if (provider_id := target.data.get('pi_provider')) and (model := target.data.get('pi_model')):
        provider.update(provider=provider_id, model=model,
                        metered=provider_metered(ctx, target, provider_id, model) is not False)
    return {'config': str(target.config_path), 'deploy_home': str(target.deploy_home),
            'unit_name': target.unit_name, 'pin': target.pin, 'source': source['state'],
            'bootstrap': bootstrap_evidence(ctx, target)[0] if usable else 'unavailable',
            'provider': provider, 'slots': target.max_concurrency,
            'harness': harness, 'engine': engine_summary(ctx, target, source),
            'last_lifecycle': last_lifecycle(target)}


def enrich_activity(activity, queue):
    # Queue listing enriches titles only AFTER local liveness/identity is proven.
    pending = {item['number']: item for group in queue.get('pending', {}).values() for item in group}
    for slot in activity['slots'].values():
        issue = slot.get('issue')
        if issue and issue['number'] in pending:
            issue['title'] = pending[issue['number']]['title']


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
    summary = local_deployment_summary(ctx, target)
    snapshot = safe_scheduler_snapshot(ctx, target)
    activity = activity_linux(ctx, target, repo, snapshot)
    enrich_activity(activity, queue)
    harness = summary['harness']
    document = {
        'action': 'status', 'platform': 'linux', 'repo': repo.full,
        'repo_dir': str(repo.path),
        'deployment': {'state': deployment_state(snapshot), **summary},
        'activity': activity,
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


def activity_darwin(ctx, target):
    # launchd logs do not carry an invocation token/PID. Retained log scenes
    # cannot safely identify a live attempt; report that limitation explicitly.
    slots = {}
    labels = plist_labels(ctx, target)
    base = f'org.orbi.{target.unit_name}.runner' if target.unit_name else 'org.orbi.runner'
    labels = sorted(set(labels) | {f'{base}.{i}' for i in range(1, min(target.max_concurrency, MAX_INSTANCES) + 1)})
    for label in labels[:MAX_INSTANCES]:
        item = {'state': 'unknown', 'reason': 'loaded job ownership/state unavailable'}
        try:
            path = home_dir(ctx) / 'Library/LaunchAgents' / (label + '.plist')
            definition = plistlib.loads(bounded_text(path).encode('utf-8'))
            if (definition.get('Label') == label
                    and definition.get('EnvironmentVariables', {}).get('ORBI_CONFIG') == str(target.config_path)
                    and definition.get('WorkingDirectory') == str(target.deploy_home)):
                proc = ctx.run(['launchctl', 'print', f'gui/{os.getuid()}/{label}'], allow_failure=True)
                states = re.findall(r'^\s*state = ([a-z ]+)$', proc.stdout, re.M)
                pids = re.findall(r'^\s*pid = ([0-9]+)$', proc.stdout, re.M)
                if proc.returncode == 0 and len(states) == 1:
                    if states[0] == 'running':
                        item = {'state': 'active/issue unknown',
                                'reason': 'launchd retained logs lack current invocation/run binding',
                                'next_action': 'Inspect current owned process and attempt read-only; '
                                               'do not attribute newest retained logs or queue head.'}
                    elif states[0] == 'not running' and not pids:
                        item = {'state': 'idle'}
        except (OSError, UnicodeError, ValueError, plistlib.InvalidFileException,
                ExpatError, ControlError, AttributeError):
            pass
        slots[label] = item
    complete = bool(slots) and all(item['state'] == 'idle' for item in slots.values())
    return {'slots': slots, 'working': {'state': 'ok' if complete else 'unavailable',
                                       'value': 0 if complete else None},
            'scope': f'local launchd jobs; at most {MAX_INSTANCES}; other slots unobserved',
            'ticks': {'state': 'unavailable', 'reason': 'launchd exposes no next-fire time'}}


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
    summary = local_deployment_summary(ctx, target)
    harness = summary['harness']
    return {
        'action': 'status', 'platform': 'darwin', 'repo': repo.full,
        'repo_dir': str(repo.path),
        'deployment': {'state': 'prepared', **summary},
        'activity': activity_darwin(ctx, target),
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


def require_setup_idle(ctx, target, *, action='setup'):
    snapshot = scheduler_snapshot(ctx, target, scan_last=max(MAX_INSTANCES, target.max_concurrency))
    if snapshot.get('state') != 'ok':
        raise ControlError('scheduler_unavailable', f'{action} cannot verify inactive/no-worker evidence',
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
        raise ControlError('setup_busy' if action == 'setup' else 'update_busy',
                           f'{action} requires inactive scheduling and no live workers',
                           fix='request a separately authorized `/orbi stop` if interruption is intended, '
                               'then verify inactivity; preserve recovery inputs', evidence={'scheduler': snapshot})
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


def guard_bootstrap_override(ctx, target, args):
    path = str(checked_path(args.pi_providers, 'provider file'))
    candidate = dataclasses.replace(target, data={**target.data, 'pi_providers': path,
                                                  'pi_provider': args.pi_provider, 'pi_model': args.pi_model})
    guard_provider_selection(ctx, target, candidate, allow_metered=args.allow_metered, bootstrap=True)


def command_setup(ctx, args, *, prepared_binding=None):
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
        deployments = load_deployments(ctx, repo.path, args.config)
        target = select_target(ctx, repo, args.config)
        new = target is None
        if not new:
            if not args.resume_setup and any(getattr(args, key) is not None for key in
                   ('pi_providers', 'pi_provider', 'pi_model', 'pi_thinking')):
                guard_bootstrap_override(ctx, target, args)
                raise ControlError(
                    'provider_override_refused', 'bootstrap inputs cannot replace an existing selection',
                    fix='omit --pi-* bootstrap inputs to reuse the existing deployment; use `/orbi set` to change models; '
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
                rechecked, _, _ = plan_new_deployment(ctx, repo, load_deployments(ctx, repo.path), args)
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
            if new or args.resume_setup:
                ctx.lifecycle_home = target.deploy_home
            if new:
                step('stage_checkout', lambda: stage_checkout(ctx, target.deploy_home, SUPPORTED_PIN),
                     mutating=True)
                report['source'] = 'verified'
            if new or args.resume_setup:
                step('write_provider_metadata', lambda: write_provider_metadata(target, metadata),
                     mutating=True)
            if new:
                step('write_harness_launcher', lambda: write_launcher(target), mutating=True)
            if step('write_isolation_env', lambda: write_env(ctx, target, reuse_only=new), mutating=True):
                ctx.lifecycle_home = target.deploy_home
            if new:
                step('write_config', lambda: write_config(target, repo, provider), mutating=True)
            if evidence['bootstrap'] == 'missing':
                # Recheck conflict evidence before the later mutation-possible install.
                step('recheck_bootstrap', lambda: bootstrap_preflight(ctx))
                ctx.lifecycle_home = target.deploy_home
                step('install_bootstrap', lambda: install_bootstrap(ctx, target, evidence['python']),
                     mutating=True)
            require_harness(ctx, target)
            report['harness'] = harness_evidence(ctx, target)
            report['harness']['observed_version'] = evidence['harness']['observed_version']
            if prepared_binding is not None:
                # Bind the inputs actually submitted to validation, not later changed bytes.
                validated_target = deployment_from(target.config_path)
                validated_identities = setup_file_identities(target)
            step('validate_non_activating', lambda: run_orbi_check(ctx, target), mutating=True)
            if prepared_binding is not None:
                current, possible = 'recheck_validated_target', False
                if (deployment_from(target.config_path) != validated_target
                        or setup_file_identities(target) != validated_identities):
                    raise ControlError('target_changed', 'deployment files changed during validation',
                                       fix='inspect concurrent changes; preserve prepared files', exit_code=2)
                # Private handoff retained through activation. Never render file bytes.
                prepared_binding.update(repo=repo, target=validated_target,
                                        identities=validated_identities)
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


def lifecycle_failure(ctx, target, error, *, target_path, steps, current, mutated, evidence,
                      snapshot_reader=safe_scheduler_snapshot):
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
    snapshot = exc.evidence.get('scheduler', {'state': 'unavailable'})
    if mutated and target:
        try:
            snapshot = snapshot_reader(ctx, target)
        except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as observation_error:
            snapshot = (observation_error.evidence.get('scheduler', unavailable_scheduler(
                target, 'scheduler evidence could not be read'))
                if isinstance(observation_error, ControlError) else
                unavailable_scheduler(target, 'scheduler evidence could not be read'))
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
        'do not repeat activation or a timeout unchanged, or stop workers outside the lifecycle helper')
    return exc


def run_upstream_step(ctx, target, command, *args, timeout=CHECK_TIMEOUT):
    proc = orbi(ctx, target, command, '--config', str(target.config_path),
                *args, timeout=timeout, allow_failure=True)
    if proc.returncode != 0:
        raise ControlError(command.replace('-', '_') + '_failed',
                           f'upstream `orbi {command}` failed',
                           fix=f'inspect the failed {command} privately')


def first_tick_after_timer_failure(ctx, args, repo, target, identities):
    """Called under the config lock only after a definite timer-enable exit.

    This is one normal systemd request, not a retry or a scheduling repair.
    Its receipt must never replace the original timer error.
    """
    service = f'{target.prefix}@1.service'
    evidence = {'unit': service, 'mutation': 'none',
                'scheduler': unavailable_scheduler(target, 'recovery not yet verified')}
    outcome = 'blocked'
    try:
        if (repo_identity(ctx, repo.path) != repo
                or select_target(ctx, repo, args.config, require=True) != target
                or setup_file_identities(target) != identities):
            raise ControlError('target_changed', 'activation target changed after timer failure')
        validate_target(target, repo)
        require_unit_ownership(ctx, target)
        require_harness(ctx, target)
        snapshot = update_observation(ctx, target)
        evidence['scheduler'] = snapshot
        # A missing configured unit or transitioning timer leaves the failed
        # enable unbounded. Active timers are allowed: a failed enable may have
        # partially applied, but workers and pending jobs must still be idle.
        if (any(f'{target.prefix}@{i}.timer' not in snapshot['timers']
                for i in range(1, target.max_concurrency + 1))
                or not snapshot['services'].get(service, {}).get('owned')
                or any(item['active'] not in INACTIVE_STATES | {'active'}
                       for item in snapshot['timers'].values())):
            raise ControlError('scheduler_unavailable', 'timer failure lacks stable owned unit evidence')
        if update_pending(snapshot):
            raise ControlError('scheduler_busy', 'workers or pending scheduler jobs are not idle')
        outcome = 'unverified'
        evidence['mutation'] = 'possible'
        proc = ctx.run(['systemctl', '--user', 'start', service], timeout=MUTATION_TIMEOUT,
                       allow_failure=True)
        if proc.returncode != 0:
            evidence['error'] = 'command_failed'
            evidence['reason'] = f'first-tick request exited with {proc.returncode}'
            outcome = 'failed' if proc.returncode > 0 else 'unverified'
        else:
            outcome = 'requested'
            evidence['mutation'] = 'completed'
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        evidence['error'] = error.code if isinstance(error, ControlError) else 'observation_failed'
        evidence['reason'] = (error.message if isinstance(error, ControlError)
                              else 'first-tick evidence or request could not be verified')
        if isinstance(error, ControlError) and 'scheduler' in error.evidence:
            evidence['scheduler'] = error.evidence['scheduler']
    return {'first_tick': outcome, 'first_tick_evidence': evidence}


def activate_existing_locked(ctx, args, repo, target, identities, steps, current, activated,
                             *, first_tick_request=True):
    """Reuse start's gates/actions with the caller already holding the target lock."""
    current.clear()
    current.update({'step': 'recheck_paths', 'mutation': 'none'})
    if (repo_identity(ctx, repo.path) != repo
            or select_target(ctx, repo, args.config, require=True) != target
            or setup_file_identities(target) != identities):
        raise ControlError('target_changed', 'activation target changed after preflight',
                           fix='inspect concurrent config, ownership and selection changes; '
                               'preserve all recovery inputs', exit_code=2)
    validate_target(target, repo)
    require_unit_ownership(ctx, target)
    start_plan(ctx, target)
    final_extension_env(ctx, target)
    ctx.lifecycle_home = target.deploy_home
    current.clear()
    current.update(step='setup', mutation='possible')
    run_upstream_step(ctx, target, 'setup', '--repo', repo.full)
    steps.append({'step': 'upstream_setup', 'status': 'ok'})
    current.clear()
    current.update({'step': 'install-units', 'mutation': 'possible'})
    run_upstream_step(ctx, target, 'install-units', timeout=MUTATION_TIMEOUT)
    steps.append({'step': 'install_units', 'status': 'ok'})
    current.clear()
    current.update({'step': 'observe_scheduler', 'mutation': 'none'})
    scan_last = max(MAX_INSTANCES, target.max_concurrency) if first_tick_request else MAX_INSTANCES
    snapshot = scheduler_snapshot(ctx, target, scan_last=scan_last)
    if snapshot['state'] != 'ok':
        raise ControlError('scheduler_unavailable',
                           f"cannot read the target scheduler: {snapshot.get('reason')}",
                           fix='verify the systemd user session')
    for index in range(1, target.max_concurrency + 1):
        timer = f'{target.prefix}@{index}.timer'
        item = snapshot['timers'].get(timer)
        if item and item['active'] == 'active' and item['enabled']:
            steps.append({'step': 'activate_timer', 'unit': timer,
                          'status': 'already-active'})
            continue
        current.clear()
        current.update({'step': 'activate_timer', 'unit': timer, 'mutation': 'possible'})
        try:
            proc = ctx.run(['systemctl', '--user', 'enable', '--now', timer],
                           timeout=MUTATION_TIMEOUT, allow_failure=True)
        except ControlError as error:
            error.evidence.update(first_tick='not-requested', recurring_scheduling='incomplete')
            raise
        if proc.returncode != 0:
            error = ControlError(
                'command_failed', f"'systemctl --user' failed with exit {proc.returncode}",
                fix='inspect the command output manually',
                evidence={'first_tick': 'not-requested', 'recurring_scheduling': 'incomplete'})
            if proc.returncode > 0 and first_tick_request:
                error.evidence.update(first_tick_after_timer_failure(
                    ctx, args, repo, target, identities))
            raise error
        activated.append(timer)
        steps.append({'step': 'activate_timer', 'unit': timer, 'status': 'enabled'})
    live = [name for name, item in snapshot['services'].items()
            if item['state'] in ACTIVE_STATES]
    if not first_tick_request:
        first_tick, state = 'not-requested', 'started'
    elif live:
        first_tick = 'already-active'
        state = 'already-running'
        steps.append({'step': 'first_tick', 'status': 'already-active'})
    else:
        service = f'{target.prefix}@1.service'
        current.clear()
        current.update({'step': 'first_tick', 'unit': service, 'mutation': 'possible'})
        ctx.run(['systemctl', '--user', 'start', service], timeout=MUTATION_TIMEOUT)
        first_tick = 'requested'
        state = 'started'
        steps.append({'step': 'first_tick', 'status': 'requested'})
    return snapshot, state, first_tick


def require_start_config_binding(target):
    # Upstream setup/install-units render deploy_home/orbi.toml into the service.
    # Its EnvironmentFile can override that value for the tick and its source sync.
    unit_config = target.deploy_home / 'orbi.toml'
    if (target.config_path != unit_config
            or persisted_env(target).get('ORBI_CONFIG', str(unit_config)) != str(unit_config)):
        raise ControlError('config_mismatch', 'the installed units would not run the selected config',
                           fix=f'verify that {unit_config} owns this deployment and remove any conflicting '
                               f'ORBI_CONFIG in {target.env_path} before starting', exit_code=2)


def command_start(ctx, args):
    target = None
    try:
        repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
        target = select_target(ctx, repo, args.config)
        selectors = any(getattr(args, key) is not None for key in
                        ('pi_providers', 'pi_provider', 'pi_model', 'pi_thinking', 'harness'))
        if target is not None and selectors:
            if args.pi_provider is not None:
                guard_bootstrap_override(ctx, target, args)
            raise ControlError('bootstrap_override_refused', 'start selectors are only for absent preparation',
                               fix='omit --pi-* and --harness to reuse the saved selection; use `/orbi set` to change models; '
                                   'use deliberate setup/repair for partial deployments', exit_code=2)
        if target is not None:
            require_start_config_binding(target)
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        exc = lifecycle_failure(ctx, target, error, target_path=args.config, steps=[],
                                current={'step': 'preflight', 'mutation': 'none'}, mutated=False,
                                evidence={'preparation': {'state': 'skipped'}, 'activation': 'none'})
        raise exc from (error if exc is not error else None)
    if target is not None and not args.dry_run:
        return maintain_existing(ctx, args, repo, target, start=True)
    return prepare_or_preview_start(ctx, args, repo, target)


def prepare_or_preview_start(ctx, args, repo, target):
    steps, activated = [], []
    mutated, activation = False, 'none'
    preparation = {'state': 'skipped'}
    binding = {}
    current = {'step': 'preflight', 'mutation': 'none'}
    try:
        if target is None:
            # A foreign config in either target location is not an absent deployment.
            for path in (repo.path / 'orbi.toml',
                         data_home(ctx) / f'orbi-{derive_unit_name(repo.full)}' / 'orbi.toml'):
                if path.exists():
                    raise ControlError('config_mismatch', 'an existing target config does not own this repository',
                                       fix='inspect the native config and repair ownership deliberately; '
                                           'preserve the config, pin and attempts', exit_code=2)
            current = {'step': 'prepare_deployment', 'mutation': 'none'}
            try:
                prepared = command_setup(ctx, args, prepared_binding=binding)
            except ControlError as exc:
                preparation = {'state': 'failed', **exc.evidence}
                raise
            preparation = {'state': 'planned' if args.dry_run else 'prepared',
                           'target': prepared['deployment']['config'],
                           **{key: prepared[key] for key in
                              ('deployment', 'steps', 'prerequisites', 'scheduler')}}
            if args.dry_run:
                return {**prepared, 'action': 'start', 'preparation': preparation,
                        'activation': 'planned', 'first_tick': 'deferred',
                        'steps': [*prepared['steps'],
                                  {'step': 'activation_preflight', 'status': 'deferred',
                                   'reason': 'requires staged source, published config/provider/harness and validation'},
                                  {'step': 'activate_deployment', 'status': 'planned'}]}
            mutated = True  # successful setup includes lock and publication writes
            current = {'step': 'rebind_prepared_target', 'mutation': 'none'}
            target = select_target(ctx, repo, args.config, require=True)
            if repo_identity(ctx, repo.path) != binding['repo'] or target != binding['target']:
                raise ControlError('target_changed', 'prepared repository or deployment binding changed',
                                   fix='inspect concurrent changes; preserve prepared files', exit_code=2)
            if setup_file_identities(target) != binding['identities']:
                raise ControlError('target_changed', 'prepared deployment files changed',
                                   fix='inspect concurrent changes; preserve prepared files', exit_code=2)
        validate_target(target, repo)
        require_unit_ownership(ctx, target)
        # A newly prepared target keeps its validated baseline across both preflights.
        identities = binding['identities'] if binding else setup_file_identities(target)
        _source, provider = start_plan(ctx, target)
        report = new_deployment_report(ctx, target, provider)
        report['source'] = _source['state']
        if args.dry_run:
            snapshot = scheduler_snapshot(ctx, target, scan_last=max(MAX_INSTANCES, target.max_concurrency))
            if snapshot['state'] != 'ok':
                raise ControlError('scheduler_unavailable',
                                   f"cannot read the target scheduler: {snapshot.get('reason')}",
                                   fix='verify the systemd user session, then rerun')
            pending = [f'{target.prefix}@{index}.timer'
                       for index in range(1, target.max_concurrency + 1)
                       if snapshot['timers'].get(f'{target.prefix}@{index}.timer', {}).get('active')
                       != 'active']
            live = [name for name, item in snapshot['services'].items()
                    if item['state'] in ACTIVE_STATES]
            steps = [{'step': 'reuse_existing_deployment', 'status': 'ok'},
                     {'step': 'release_update', 'status': 'conditional',
                      'reason': 'resolve the newest release on apply; no-op if current and scheduling active, '
                                'otherwise quiesce as needed, sync, pin and check'},
                     {'step': 'activate_timers', 'status': 'conditional',
                      'timers': pending},
                     {'step': 'first_tick', 'status': 'conditional',
                      'mode': 'only after activation if no worker is active'}]
            return {'action': 'start', 'platform': ctx.platform, 'status': 'planned',
                    'dry_run': True, 'repo': repo.full, 'deployment': report,
                    'steps': steps, 'activated': False, 'scheduler': snapshot,
                    'first_tick': 'already-active' if live else 'planned',
                    'preparation': preparation}
        steps = [{'step': 'reuse_existing_deployment', 'status': 'ok'}]
        current, mutated = {'step': 'lock', 'mutation': 'possible'}, True
        with locked(ctx, target.config_path):
            steps.append({'step': 'lock', 'status': 'ok', 'mutation': 'completed'})
            activation = 'possible'
            snapshot, state, first_tick = activate_existing_locked(
                ctx, args, repo, target, identities, steps, current, activated)
            current = {'step': 'release_lock', 'mutation': 'possible'}
        return {'action': 'start', 'platform': ctx.platform, 'status': state,
                'dry_run': False, 'repo': repo.full, 'deployment': report,
                'steps': steps, 'activated': bool(activated) or state == 'started',
                'first_tick': first_tick, 'preparation': preparation}
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        if current['step'] == 'recheck_paths':
            activation = 'none'  # shared preflight failed before any activation action
        if preparation['state'] == 'failed':
            # Keep setup's exact original failed operation, target and mutation evidence.
            error.evidence = {**error.evidence, 'preparation': preparation, 'activation': 'none'}
            raise
        exc = lifecycle_failure(ctx, target, error, target_path=preparation.get('target', args.config),
                                steps=steps, current=current, mutated=mutated,
                                evidence={'activation': activation, 'activated_timers': activated,
                                          'preparation': preparation})
        raise exc from (error if exc is not error else None)


def owned_timers(snapshot):
    return [name for name, item in sorted(snapshot['timers'].items())
            if item['installed'] and item['owned']]


def disable_owned_timers(ctx, target, snapshot, disabled, steps, current):
    for timer in owned_timers(snapshot):
        current.clear()
        current.update(step='verify_timer_ownership', unit=timer, mutation='none')
        require_quiesce_unit(ctx, target, timer)
        current.clear()
        current.update(step='disable_timer', unit=timer, mutation='possible')
        # Do not reload between verifying the loaded timer and --now stopping it.
        ctx.run(['systemctl', '--user', 'disable', '--now', '--no-reload', timer],
                timeout=MUTATION_TIMEOUT)
        if snapshot['timers'][timer]['enabled']:
            # A persistent disable does not remove runtime enablement links.
            enabled = ctx.run(['systemctl', '--user', 'is-enabled', timer], allow_failure=True)
            if enabled.returncode == 0 and enabled.stdout.strip() == 'enabled-runtime':
                current.update(step='disable_runtime_timer')
                ctx.run(['systemctl', '--user', 'disable', '--runtime', '--no-reload', timer],
                        timeout=MUTATION_TIMEOUT)
        disabled.append(timer)
        steps.append({'step': 'disable_timer', 'unit': timer, 'status': 'disabled'})


def command_stop(ctx, args):
    target = None
    steps, disabled, stopped = [], [], []
    current = {'step': 'preflight', 'mutation': 'none'}
    try:
        repo_dir = args.repo_dir or ctx.cwd
        repo = repo_identity(ctx, repo_dir)
        target = select_target(ctx, repo, args.config, require=True)
        validate_target(target, repo)
        require_unit_ownership(ctx, target, symlink_error='unit_conflict')
        snapshot = update_observation(ctx, target)
        if args.dry_run:
            names = owned_timers(snapshot)
            return {'action': 'stop', 'platform': ctx.platform, 'status': 'planned',
                    'dry_run': True, 'repo': repo.full,
                    'deployment': {'config': str(target.config_path),
                                   'unit_name': target.unit_name, 'pin': target.pin,
                                    'harness': harness_evidence(ctx, target)},
                    'disabled_timers': names, 'pending_services': update_pending(snapshot),
                    'steps': quiesce_plan_steps()}
        current = {'step': 'lock', 'mutation': 'possible'}
        with locked(ctx, target.config_path):
            steps.append({'step': 'lock', 'status': 'ok', 'mutation': 'completed'})
            current = {'step': 'revalidate_target', 'mutation': 'none'}
            fresh_repo = repo_identity(ctx, repo_dir)
            fresh_target = select_target(ctx, fresh_repo, args.config, require=True)
            # Update may republish the config; stop binds to ownership, not its contents.
            if ((fresh_repo.path, fresh_repo.full) != (repo.path, repo.full)
                    or (fresh_target.config_path, fresh_target.prefix) != (target.config_path, target.prefix)):
                raise ControlError('target_changed', 'stop target changed after preflight',
                                   fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
            validate_target(fresh_target, fresh_repo)
            require_unit_ownership(ctx, fresh_target, symlink_error='unit_conflict')
            target = fresh_target
            current = {'step': 'observe_scheduler', 'mutation': 'none'}
            snapshot = update_observation(ctx, target)
            ctx.lifecycle_home = target.deploy_home
            quiesce_locked(ctx, target, snapshot, disabled, stopped, steps, current)
            current = {'step': 'release_lock', 'mutation': 'possible'}
        return {'action': 'stop', 'platform': ctx.platform, 'status': 'stopped',
                'dry_run': False, 'repo': repo.full,
                'deployment': {'config': str(target.config_path),
                               'unit_name': target.unit_name, 'pin': target.pin,
                                    'harness': harness_evidence(ctx, target)},
                'disabled_timers': disabled, 'stopped_services': stopped,
                'pending_services': [], 'steps': steps}
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        # A successful lock alone does not count as a stop mutation.
        mutated = (current['mutation'] == 'possible' or bool(disabled or stopped)
                   or any(step['step'] == 'cancel_start' for step in steps))
        exc = lifecycle_failure(ctx, target, error, target_path=args.config, steps=steps,
                                current=current, mutated=mutated,
                                evidence={'disabled_timers': disabled, 'stopped_services': stopped},
                                snapshot_reader=update_observation)
        exc.evidence.setdefault('pending_services', update_pending(exc.evidence['scheduler']))
        raise exc from (error if exc is not error else None)


UPDATE_TRACK = 'release'
UPDATE_WAIT_MINUTES = 30


def quiesce_plan_steps(*, wait=False):
    return [{'step': step, 'status': 'planned'} for step in (
        'pause_owned_timers', 'cancel_start', 'wait_for_workers' if wait else 'stop_service',
        'verify_quiescent')]


def update_plan_steps(*, stop=False, wait=False):
    return [
        *quiesce_plan_steps(wait=wait),
        {'step': 'sync_engine_source', 'status': 'conditional',
         'reason': 'only after confirmed idle: sync release, pin exact commit and validate'},
        {'step': 'refresh_units', 'status': 'deferred' if stop else 'conditional',
         'reason': 'leave stopped' if stop else 'only after successful validation'},
        {'step': 'observe_scheduler', 'status': 'conditional'},
        {'step': 'activate_deployment', 'status': 'deferred' if stop else 'conditional',
         'reason': 'leave stopped' if stop else 'after engine validation and existing-target technical checks'},
    ]


def checkout_head(ctx, deployment):
    proc = ctx.run(['git', '-C', str(deployment.deploy_home), 'rev-parse', 'HEAD'],
                   allow_failure=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ControlError('source_unavailable',
                           f'cannot read the checkout at {deployment.deploy_home}',
                           fix='repair the deployment checkout, then rerun')
    return proc.stdout.strip()


def require_clean_checkout(ctx, deployment):
    """Tracked changes fail closed: update never discards or force-checks-out work."""
    proc = ctx.run(['git', '-C', str(deployment.deploy_home), 'status', '--porcelain',
                    '--untracked-files=no'], allow_failure=True,
                   env={**ctx.env, 'GIT_OPTIONAL_LOCKS': '0'})
    if proc.returncode != 0:
        raise ControlError('source_unavailable',
                           f'cannot read the tracked state of {deployment.deploy_home}',
                           fix='repair the deployment checkout, then rerun', exit_code=2)
    if proc.stdout.strip():
        raise ControlError(
            'source_dirty',
            'the deployment checkout has tracked changes; update never discards them',
            fix='inspect and preserve those changes in a separate operation; never force a '
                'checkout over them', exit_code=2)
    return {'step': 'require_clean_checkout', 'status': 'ok'}


def engine_track_replacement(path, track):
    """Render only the engine_source_track literal; preserve every other byte."""
    text = path.read_bytes().decode('utf-8')
    pattern = re.compile(r'''^([ \t]*engine_source_track[ \t]*=[ \t]*)(["'])[^"'\r\n]*\2(?=[ \t]*(?:#|\r?$))''',
                         re.MULTILINE)
    if len(pattern.findall(text)) == 1:
        replacement = pattern.sub(lambda match: match[1] + (
            json.dumps(track) if match[2] == '"' else "'" + track + "'"), text, count=1)
        try:
            previous = tomllib.loads(text).get('engine_source_track')
            # If the value is already right, do not change a lookalike elsewhere.
            if previous == track:
                return text, text
            if tomllib.loads(replacement).get('engine_source_track') == track:
                return text, replacement
        except tomllib.TOMLDecodeError:
            pass
    raise ControlError('config_invalid', f'{path}: engine_source_track is not writable at the top level',
                       fix='declare one unambiguous top-level engine_source_track line; preserve recovery inputs',
                       exit_code=2)


def rewrite_engine_track(deployment, track):
    path = checked_path(deployment.config_path, 'config')
    text, replacement = engine_track_replacement(path, track)
    if replacement == text:
        return 'unchanged'
    atomic_publish(path, replacement)
    return 'updated'


def scheduler_jobs(ctx):
    proc = ctx.run(['systemctl', '--user', 'list-jobs', '--no-legend', '--no-pager', '--full'],
                   allow_failure=True)
    if proc.returncode != 0:
        raise ControlError('scheduler_unavailable', 'cannot read scheduler list-jobs',
                           fix='restore complete systemd user-session inventory before retrying')
    jobs = {}
    for line in proc.stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        if (len(fields) < 4 or not re.fullmatch(r'[1-9][0-9]*', fields[0])
                or fields[0] in jobs):
            raise ControlError('scheduler_unavailable', 'pending scheduler jobs are unreadable',
                               fix='restore systemctl --user list-jobs evidence')
        jobs[fields[0]] = tuple(fields[1:3])
    return jobs


def update_observation(ctx, target, *, known_indices=()):
    """Discover all relevant loaded/installed instances and queued jobs, not just slots."""
    scan_last = max(MAX_INSTANCES, target.max_concurrency)
    indices = set(range(1, scan_last + 1)) | set(known_indices)
    pattern = re.compile(re.escape(target.prefix) + r'@([1-9][0-9]*)\.(?:timer|service)')
    discovered = set()
    for command in ('list-units', 'list-unit-files'):
        argv = ['systemctl', '--user', command, '--no-legend', '--no-pager', '--full',
                '--all', target.prefix + '@*']
        if command == 'list-units':
            argv.append('--plain')
        proc = ctx.run(argv, allow_failure=True)
        if proc.returncode != 0:
            raise ControlError('scheduler_unavailable', f'cannot read scheduler {command}',
                               fix='restore complete systemd user-session inventory before retrying')
        for line in proc.stdout.splitlines():
            fields = line.split()
            if not fields:
                continue
            if (len(fields) < (4 if command == 'list-units' else 2)
                    or not fields[0].startswith(target.prefix + '@')):
                raise ControlError('scheduler_unavailable', 'target scheduler inventory is unreadable',
                                   fix='restore complete systemctl unit inventory before retrying')
            if fields[0] not in {target.prefix + '@.timer', target.prefix + '@.service'}:
                discovered.add(fields[0])
    jobs = [{'id': job_id, 'unit': name, 'state': 'queued', 'job': verb}
            for job_id, (name, verb) in scheduler_jobs(ctx).items()
            if name.startswith(target.prefix + '@')]
    discovered.update(job['unit'] for job in jobs)
    for name in sorted(discovered):
        match = pattern.fullmatch(name)
        if not match:
            raise ControlError('scheduler_unavailable', 'unrecognized target scheduler instance',
                               fix='inspect target instance inventory; do not adopt unknown units')
        indices.add(int(match.group(1)))
    snapshot = scheduler_snapshot(ctx, target, indices=sorted(indices), scan_last=scan_last)
    snapshot['inventory']['additional_instances'] = sorted(i for i in indices if i > MAX_INSTANCES)
    snapshot['pending_jobs'] = jobs
    if snapshot['state'] != 'ok':
        raise ControlError('scheduler_unavailable', 'cannot verify target scheduler state',
                           fix='restore readable scheduler evidence before deliberately retrying',
                           evidence={'scheduler': snapshot})
    if (any((item['installed'] or item['state'] not in INACTIVE_STATES) and not item['owned']
            for item in snapshot['services'].values())
            or any(not item['owned'] for item in snapshot['timers'].values())):
        raise ControlError('unit_conflict', 'loaded units have unknown or foreign ownership',
                           fix='inspect loaded fragments; never adopt foreign units', exit_code=2,
                           evidence={'scheduler': snapshot})
    if (any(item['fragment_kind'] == 'unknown' for item in snapshot['services'].values())
            or any(item['fragment_kind'] == 'unknown' or item['active'] not in DRAIN_STATES | INACTIVE_STATES
                   for item in snapshot['timers'].values())):
        raise ControlError('scheduler_unavailable', 'target unit evidence is incomplete',
                           fix='restore complete target fragment/state evidence', evidence={'scheduler': snapshot})
    if any(item['state'] != 'ok' for item in snapshot['inventory']['counts'].values()):
        raise ControlError('scheduler_unavailable', 'target ownership/state counts are incomplete',
                           fix='inspect ambiguous fragments and scheduler evidence',
                           evidence={'scheduler': snapshot})
    # Enumerated instances need ownership evidence, including those outside the fixed scan.
    for name in discovered:
        item = (snapshot['timers'] if name.endswith('.timer') else
                snapshot['services']).get(name)
        if not item or not item['owned']:
            raise ControlError('unit_conflict', 'enumerated unit ownership is unverified',
                               fix='inspect pending jobs and loaded fragments before retrying',
                               evidence={'scheduler': snapshot})
    return snapshot


def paused_observation(ctx, target, *, known_indices=()):
    snapshot = update_observation(ctx, target, known_indices=known_indices)
    if any(item['enabled'] or item['active'] not in INACTIVE_STATES
           for item in snapshot['timers'].values()):
        raise ControlError('scheduler_unavailable', 'timer disable readback did not prove scheduling stopped',
                           fix='inspect disabled timers and user-session evidence before retrying',
                           evidence={'scheduler': snapshot})
    return snapshot


def update_pending(snapshot):
    return ([{'unit': name, 'state': item['state']} for name, item in snapshot.get('services', {}).items()
             if item['state'] not in INACTIVE_STATES] + snapshot.get('pending_jobs', []))


# Distribution-wide drop-ins that only change how a stop/start timeout fails
# (Fedora's systemd ships TimeoutStopFailureMode=abort for every service).
VENDOR_DROPIN_DIRS = (Path('/usr/lib/systemd/system/service.d'), Path('/usr/lib/systemd/user/service.d'))
VENDOR_DROPIN_KEYS = {'TimeoutStopFailureMode', 'TimeoutStartFailureMode'}


def benign_vendor_dropin(path):
    """True only for a root-owned vendor type-wide drop-in limited to timeout failure modes."""
    path = Path(path)
    if path.parent not in VENDOR_DROPIN_DIRS or path.suffix != '.conf':
        return False
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            return False
        lines = bounded_text(path).splitlines()
    except (OSError, ValueError):
        return False
    section = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('['):
            section = line
            continue
        key, sep, _ = line.partition('=')
        if raw.rstrip().endswith('\\') or section != '[Service]' or not sep or key.strip() not in VENDOR_DROPIN_KEYS:
            return False
    return True


def require_quiesce_unit(ctx, target, unit):
    """Verify the loaded target and refuse stop transactions with unowned effects."""
    side_effects = ('DropInPaths', 'ConsistsOf', 'BoundBy', 'RequiredBy', 'RequisiteOf',
                    'PropagatesStopTo', 'OnFailure', 'OnSuccess')
    timer = unit.endswith('.timer')
    # Verify effective properties, not NeedDaemonReload: disabling a timer's
    # links marks that flag for all units, even with no change to their bindings.
    props = ('Id', 'LoadState', 'FragmentPath', *side_effects)
    props += ('Triggers',) if timer else ('WorkingDirectory', 'Environment', 'EnvironmentFiles',
                                          'UnsetEnvironment', 'ExecStart', 'ExecStop', 'ExecStopPost',
                                          'KillMode')
    proc = ctx.run(['systemctl', '--user', 'show', '--all', *('-p' + p for p in props), unit],
                   allow_failure=True)
    values = {}
    for line in proc.stdout.splitlines():
        key, sep, value = line.partition('=')
        if sep:
            values[key] = values[key] + '\n' + value if key in values else value
    # systemctl omits empty arrays of structs even with show --all.
    optional = {'EnvironmentFiles', 'ExecStop', 'ExecStopPost'}
    if proc.returncode or set(props) - values.keys() - optional:
        raise ControlError('scheduler_unavailable', f'cannot verify loaded unit evidence for {unit}',
                           fix='restore readable systemd user-session evidence')
    conflict = ControlError('unit_conflict', f'cannot verify a scoped stop of {unit}',
                            fix='inspect the loaded unit binding, overrides and stop dependencies before retrying',
                            exit_code=2)
    fragment = values['FragmentPath']
    try:
        dropins = shlex.split(values['DropInPaths'])
    except ValueError:
        raise conflict from None
    if all(benign_vendor_dropin(path) for path in dropins):
        values['DropInPaths'] = ''
    if (values['Id'] != unit or values['LoadState'] != 'loaded'
            or any(values[p] for p in side_effects)
            or fragment_kind(fragment, unit) not in {'instance', 'template'}):
        raise conflict
    if timer:
        # disable --now reaches the timer and its [Install] links, not just ActiveState.
        if (values['Triggers'] != unit.removesuffix('.timer') + '.service'
                or re.search(r'^[ \t]*(Also|Alias)[ \t]*=', Path(fragment).read_text(), re.M)):
            raise conflict
        return
    if (installed_config(fragment, home_dir(ctx)) != target.config_path
            or len(re.findall(r'\bORBI_CONFIG=', Path(fragment).read_text())) != 1
            or any(values.get(p) for p in ('ExecStop', 'ExecStopPost'))
            or values['KillMode'] not in {'control-group', 'mixed'}):
        raise conflict
    try:
        configs = [entry.partition('=')[2] for entry in shlex.split(values['Environment'])
                   if entry.startswith('ORBI_CONFIG=')]
        unset = shlex.split(values['UnsetEnvironment'])
    except ValueError:
        raise conflict from None
    env_file = values.get('EnvironmentFiles')
    bootstrap = str(home_dir(ctx) / '.local/bin/orbi')
    if (configs != [str(target.config_path)]
            or values['WorkingDirectory'] != str(target.deploy_home)
            or fleet_exec(values) != ((bootstrap, bootstrap),)
            or any(entry.partition('=')[0] == 'ORBI_CONFIG' for entry in unset)
            or (env_file and (not re.fullmatch(re.escape(str(target.env_path)) +
                                               r' \(ignore_errors=(?:yes|no)\)', env_file)
                              or persisted_env(target).get('ORBI_CONFIG', str(target.config_path))
                              != str(target.config_path)))):
        raise conflict


def require_quiescent(ctx, target, *, known_indices=()):
    snapshot = paused_observation(ctx, target, known_indices=known_indices)
    pending = update_pending(snapshot)
    if pending:
        raise ControlError('scheduler_unavailable', 'target workers or jobs remain after quiescing',
                           fix='inspect systemd user-service states and pending jobs before retrying',
                           evidence={'scheduler': snapshot, 'pending_services': pending})


def wait_for_workers(ctx, target, snapshot, *, action='update'):
    deadline = time.monotonic() + UPDATE_WAIT_MINUTES * 60
    while pending := update_pending(snapshot):
        workers = sum(item['state'] not in INACTIVE_STATES for item in snapshot['services'].values())
        jobs = len(snapshot['pending_jobs'])
        finishing = f'{workers} worker(s)' + (f' and {jobs} scheduler job(s)' if jobs else '')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ControlError('update_busy',
                               f'{action.capitalize()} not applied: {finishing} still finishing after '
                               f'{UPDATE_WAIT_MINUTES} minutes. Scheduling remains paused.',
                               fix=f'wait for the remaining work to finish before rerunning /orbi {action}',
                               evidence={'scheduler': snapshot, 'pending_services': pending})
        # Progress is best-effort and must not corrupt a JSON receipt on stdout.
        with contextlib.suppress(OSError):
            print(f'Orbi {action}: Scheduling paused; {finishing} still finishing.', file=ctx.err, flush=True)
        snapshot_indices = snapshot['inventory']['additional_instances']
        time.sleep(min(60, remaining))
        snapshot = paused_observation(ctx, target, known_indices=snapshot_indices)


def quiesce_locked(ctx, target, snapshot, disabled, stopped, steps, current, *, wait=False, action='update'):
    """The caller holds the config lock and supplied fresh ownership evidence."""
    disable_owned_timers(ctx, target, snapshot, disabled, steps, current)
    current.clear()
    current.update(step='verify_timers_disabled', mutation='none')
    known_indices = snapshot['inventory']['additional_instances']
    snapshot = paused_observation(ctx, target, known_indices=known_indices)
    known_indices = snapshot['inventory']['additional_instances']
    starts = [job for job in snapshot['pending_jobs'] if job['job'] in START_JOB_TYPES]
    for job in starts:
        unit, job_id = job['unit'], job['id']
        current.update(step='verify_pending_start', unit=unit, job=job_id, mutation='none')
        require_quiesce_unit(ctx, target, unit)
        actual = scheduler_jobs(ctx).get(job_id)
        if actual is None:
            # A job may complete while we inspect it; read worker states again below.
            continue
        if actual != (unit, job['job']):
            raise ControlError('scheduler_unavailable', f'pending start changed for {unit}',
                               fix='inspect systemd user-session job evidence before retrying')
        current.update(step='cancel_start', mutation='possible')
        ctx.run(['systemctl', '--user', 'cancel', job_id], timeout=MUTATION_TIMEOUT)
        steps.append({'step': 'cancel_start', 'unit': unit, 'job': job_id, 'status': 'cancelled'})
    if starts:
        current.clear()
        current.update(step='observe_workers', mutation='none')
        snapshot = paused_observation(ctx, target, known_indices=known_indices)
        known_indices = snapshot['inventory']['additional_instances']
    if wait:
        current.clear()
        current.update(step='wait_for_workers', mutation='none')
        wait_for_workers(ctx, target, snapshot, action=action)
        steps.append({'step': 'wait_for_workers', 'status': 'ok'})
        return
    for unit, item in snapshot['services'].items():
        if not item['installed']:
            continue
        current.clear()
        current.update(step='verify_service_ownership', unit=unit, mutation='none')
        require_quiesce_unit(ctx, target, unit)
        if item['state'] not in DRAIN_STATES:
            continue
        current.update(step='stop_service', mutation='possible')
        ctx.run(['systemctl', '--user', 'stop', unit], timeout=MUTATION_TIMEOUT)
        stopped.append(unit)
        steps.append({'step': 'stop_service', 'unit': unit, 'status': 'stopped'})
    current.clear()
    current.update(step='verify_quiescent', mutation='none')
    require_quiescent(ctx, target, known_indices=known_indices)
    steps.append({'step': 'verify_quiescent', 'status': 'ok'})


def apply_release_locked(ctx, target, read_target, steps, current, progress, *,
                         repo=None, source_track=None, verify_head=None):
    """Shared release transaction; the caller owns the lock and idle checks."""
    def stage(name):
        current.update(step=name, mutation='possible')

    source_track = source_track or UPDATE_TRACK
    stage('set_release_track')
    track_state = rewrite_engine_track(target, source_track)
    steps.append({'step': 'set_release_track', 'status': track_state,
                  'track': source_track, 'mutation': 'completed'})
    release_target = deployment_from(target.config_path)
    if verify_head is not None and release_target.pin != source_track:
        raise ControlError('target_changed', 'release track was not applied to the top-level deployment config')
    release_identities = setup_file_identities(release_target)
    stage('sync_engine_source')
    # A nonzero exit or timeout can follow a partially applied source sync.
    progress['engine_update'] = 'sync_unverified'
    run_upstream_step(ctx, target, 'sync-engine-source', timeout=MUTATION_TIMEOUT)
    head = checkout_head(ctx, target)
    progress['engine_update'] = 'synced_unvalidated'
    steps.append({'step': 'sync_engine_source', 'status': 'synced', 'head': head,
                  'mutation': 'completed'})
    if ((repo is not None and repo_identity(ctx, repo.path) != repo)
            or read_target() != release_target
            or setup_file_identities(release_target) != release_identities):
        raise ControlError('target_changed', 'deployment changed during source sync',
                           fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
    stage('pin_release')
    if verify_head is not None:
        verify_head(head)
    pin_state = rewrite_engine_track(target, 'sha:' + head)
    target = read_target()
    progress['target'] = target
    steps.append({'step': 'pin_release', 'status': pin_state,
                  'track': 'sha:' + head, 'mutation': 'completed'})
    stage('validate_non_activating')
    if verify_head is not None and target.pin != 'sha:' + head:
        raise ControlError('target_changed', 'deployment config does not contain the verified exact release pin')
    validated_identities = setup_file_identities(target)
    run_orbi_check(ctx, target)
    if verify_head is not None:
        require_source(ctx, target)
    if (read_target() != target
            or setup_file_identities(target) != validated_identities):
        raise ControlError('target_changed', 'deployment files changed during update validation',
                           fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
    steps.append({'step': 'validate_non_activating', 'status': 'ok',
                  'mutation': 'completed'})
    return target, head, validated_identities


def configured_timers_active(target, snapshot):
    return all((item := snapshot['timers'].get(f'{target.prefix}@{i}.timer', {})).get('enabled')
               and item.get('active') == 'active' for i in range(1, target.max_concurrency + 1))


def command_update(ctx, args):
    return maintain_existing(ctx, args)


SET_USAGE = ('/orbi set DEPLOYMENT slots N', '/orbi set DEPLOYMENT model PROVIDER/MODEL [THINKING] [--allow-metered]')
THINKING_LEVELS = ('off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max')


def resolve_set_target(ctx, selector):
    path = ctx.cwd / Path(selector).expanduser()
    if path.is_file() or Path(selector).expanduser().is_absolute():
        return deployment_from(explicit_config_file(path))
    matches = [target for target in load_deployments(ctx, ctx.cwd)
               if selector and (target.prefix.startswith(selector)
                                or (target.unit_name or '').startswith(selector)
                                or any(selector.lower() in (repo.lower(), repo.split('/')[-1].lower())
                                       for repo in target.source_repos))]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ControlError('ambiguous_deployment', 'deployment matches multiple configs: '
                           + ', '.join(str(target.config_path) for target in matches),
                           fix='use the exact deployment config path', exit_code=2)
    if path.suffix == '.toml':
        return deployment_from(explicit_config_file(path))
    raise ControlError('not_prepared', 'no local deployment matches the selector',
                       fix='use a unit prefix or repository from `/orbi status all`, or pass its config path',
                       exit_code=2)


def command_set(ctx, args):
    if args.config is not None or args.repo_dir is not None or args.dry_run:
        raise ControlError('invalid_set_selection', 'set takes a positional deployment and does not support --dry-run',
                           fix='use ' + ' or '.join(SET_USAGE), exit_code=2)
    operands = args.operands
    if len(operands) not in (3, 4) or operands[1] not in ('slots', 'model'):
        raise ControlError('invalid_set_selection', 'set requires a deployment and either slots or model',
                           fix='use ' + ' or '.join(SET_USAGE), exit_code=2)
    selector, key, value, *thinking = operands
    if key == 'slots':
        if args.allow_metered:
            raise ControlError('invalid_metered_selection', '--allow-metered does not apply to slots',
                               fix='omit --allow-metered', exit_code=2)
        try:
            slots = int(value) if re.fullmatch(r'[+]?[0-9]+', value) else 0
        except ValueError:
            slots = 0
        # Supported Orbi engines reject counts above MAX_RUNNER_INSTANCES in
        # both config loading and unit installation. Refuse before pausing/writing.
        if not 1 <= slots <= MAX_INSTANCES or thinking:
            raise ControlError('invalid_set_value', f'slots requires one positive integer from 1 to {MAX_INSTANCES}',
                               fix=f'choose a slot count from 1 to {MAX_INSTANCES}: ' + SET_USAGE[0], exit_code=2)
        changes = {'max_concurrency': slots}
    else:
        provider, _, model = value.partition('/')
        if not provider.strip() or not model.strip():
            raise ControlError('invalid_set_value', 'model requires PROVIDER/MODEL',
                               fix='use a provider and model ID from the deployment catalog', exit_code=2)
        changes = {'pi_provider': provider, 'pi_model': model}
        if thinking:
            if thinking[0] not in THINKING_LEVELS:
                raise ControlError('invalid_set_value', 'unsupported Pi thinking level',
                                   fix='omit it to keep the saved value, or use a thinking level: '
                                       + ', '.join(THINKING_LEVELS), exit_code=2)
            changes['pi_thinking'] = thinking[0]
    try:
        target = resolve_set_target(ctx, selector)
        repo = repo_identity(ctx, target.repo_dir or target.config_path.parent)
        if select_target(ctx, repo, str(target.config_path), require=True) != target:
            raise ControlError('target_changed', 'set target changed during discovery',
                               fix='inspect the selected config and retry with its exact path', exit_code=2)
    except (OSError, UnicodeError) as error:
        raise ControlError('config_invalid', 'cannot read local deployment files (details withheld)',
                           fix='inspect the deployment files privately and use the exact config path') from error
    args.config, args.wait = str(target.config_path), True
    return maintain_existing(ctx, args, repo, target, changes=changes)


def setting_replacement(target, text, changes):
    """Edit single-line literals without reserializing unrelated TOML."""
    data = target.data.copy()
    newline = '\r\n' if '\r\n' in text else '\n'
    for key, value in changes.items():
        if type(data.get(key)) is type(value) and data[key] == value:
            continue
        literal = json.dumps(value, ensure_ascii=False).replace('\x7f', r'\u007f')
        if key not in data:
            text = f'{key} = {literal}{newline}' + text
            data[key] = value
            continue
        data[key] = value
        # Try only assignment values, preserving indent, comments and quotes on keys.
        # TOML readback distinguishes top-level assignments from lookalikes in tables
        # or multiline strings and proves no other setting was changed.
        pattern = re.compile(rf"""^[ \t]*(?:{key}|"{key}"|'{key}')[ \t]*=[ \t]*("(?:[^"\\\r\n]|\\[^\r\n])*"|'[^'\r\n]*'|[+\-\w]+)(?=[ \t]*(?:#|\r?$))""",
                             re.MULTILINE)
        for match in pattern.finditer(text):
            start, end = match.span(1)
            candidate = text[:start] + literal + text[end:]
            try:
                if tomllib.loads(candidate) == data:
                    text = candidate
                    break
            except tomllib.TOMLDecodeError:
                continue
        else:
            raise ControlError('config_invalid', f'{key} is not writable as a top-level literal',
                               fix=f'declare one top-level {key} assignment on a single line; preserve recovery inputs',
                               exit_code=2)
    return text


def maintain_existing(ctx, args, repo=None, target=None, *, start=False, changes=None):
    """Quiesce as needed, update, and activate only after validation."""
    setting = changes is not None
    action = 'set' if setting else ('start' if start else 'update')
    change = None
    symlink_error = 'unknown_target' if start else 'unit_conflict'
    steps, disabled, stopped = [], [], []
    mutated = False
    resume = None
    start_fields = {'preparation': {'state': 'skipped'}} if start else {}
    previous = {'track': None, 'head': None}
    engine_result, activation = 'not_applied', 'none'
    activated = []
    activation_reason = 'not evaluated'
    current = {'step': 'preflight', 'mutation': 'none'}
    try:
        if target is None:  # update requires a prepared target; start already resolved one
            repo_dir = args.repo_dir
            if args.config and repo_dir is None:
                config = deployment_from(explicit_config_file(args.config))
                if config.repo_dir is None:
                    raise ControlError('config_invalid', f'{config.config_path} does not name a repo_dir',
                                       fix='set repo_dir to the canonical checkout or pass --repo-dir', exit_code=2)
                repo_dir = config.repo_dir
            repo = repo_identity(ctx, repo_dir or ctx.cwd)
            target = select_target(ctx, repo, args.config, require=True)
        validate_target(target, repo)
        require_unit_ownership(ctx, target, symlink_error=symlink_error)
        require_setup_transport(repo, target)
        require_harness(ctx, target)
        if setting:
            require_start_config_binding(target)
            candidate = deployment_from(target.config_path, {**target.data, **changes})
            if 'pi_provider' in changes:
                guard_provider_selection(ctx, target, candidate, allow_metered=args.allow_metered)
            try:
                provider = require_provider(candidate)
            except ControlError as error:
                if 'pi_model' in changes and error.code == 'provider_unavailable':
                    error.fix = 'choose a provider/model with verified metadata in the deployment catalog, then retry set'
                raise
        else:
            candidate = target
            provider = require_provider(target)
        if start:
            current = {'step': 'verify_engine_checkout', 'mutation': 'none'}
            require_engine_checkout(ctx, target, source_repo=repo.path)
            current = {'step': 'preflight', 'mutation': 'none'}
        source = require_source(ctx, target)
        if setting and source['state'] != 'verified':
            raise ControlError('source_unverified', 'set requires a verified existing engine pin',
                               fix='pin the deployment in a separate operation; set never moves the engine pin')
        require_clean_checkout(ctx, target)
        previous = {'track': target.pin, 'head': source['head'] if setting else checkout_head(ctx, target)}
        identities = setup_file_identities(target)
        if setting:
            config_identity = identities[target.config_path]
            config_bytes = config_identity[-1] if config_identity else None
            original = config_bytes.decode('utf-8') if config_bytes is not None else None
            try:
                matches_config = original is not None and tomllib.loads(original) == target.data
            except tomllib.TOMLDecodeError:
                matches_config = False
            if not matches_config:
                raise ControlError('target_changed', 'deployment config changed during set preflight',
                                   fix='inspect concurrent changes before retrying')
            replacement = setting_replacement(target, original, changes)
            change = {'old': {key: (target.max_concurrency if key == 'max_concurrency' else target.data.get(key))
                              for key in changes}, 'new': changes, 'backup': None}
        evidence = prerequisites(ctx, candidate, action=action, provider=provider,
                                 allow_bootstrap_install=False)
        bound_selectors = (' --repo-dir ' + shlex.quote(str(repo.path))
                           + ' --config ' + shlex.quote(str(target.config_path)))
        start_command = '/orbi start' + bound_selectors
        resume = ('/orbi set ' + shlex.join([str(target.config_path), *args.operands[1:]])
                  + (' --allow-metered' if args.allow_metered else '') if setting else
                  '/orbi ' + action + bound_selectors + (' --stop' if args.stop else '')
                  + (' --wait' if args.wait else ''))
        report = new_deployment_report(ctx, target, provider)
        report['source'] = source_evidence(ctx, target)['state']
        if start:
            current = {'step': 'resolve_release', 'mutation': 'none'}
            tag, expected = official_latest_release(ctx)
            current = {'step': 'observe_scheduler', 'mutation': 'none'}
        snapshot = update_observation(ctx, target)
        if args.dry_run:
            return {'action': 'update', 'platform': ctx.platform, 'status': 'planned',
                    'dry_run': True, 'repo': repo.full, 'deployment': report,
                    'previous': previous, 'prerequisites': evidence,
                    'scheduler': snapshot, 'steps': update_plan_steps(stop=args.stop, wait=args.wait),
                    'activation': 'none' if args.stop else 'conditional',
                    'activated': False, 'warnings': []}
        source_track = verify_head = None
        if start:
            if (target.pin == 'sha:' + expected and previous['head'] == expected
                    and configured_timers_active(target, snapshot)):
                if (repo_identity(ctx, repo.path) != repo
                        or select_target(ctx, repo, args.config, require=True) != target
                        or setup_file_identities(target) != identities
                        or checkout_head(ctx, target) != expected):
                    raise ControlError('target_changed', 'start target changed during release discovery',
                                       fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
                live = any(item['state'] in ACTIVE_STATES for item in snapshot['services'].values())
                steps.append({'step': 'release_update', 'status': 'not-needed',
                              'reason': 'current release and configured timers enabled and active'})
                return {'action': action, 'platform': ctx.platform, 'status': 'already-running',
                        'dry_run': False, 'repo': repo.full,
                        'deployment': {**report, 'deployed_commit': expected}, 'steps': steps,
                        'activated': False, 'scheduler': snapshot, 'engine_update': 'up_to_date',
                        'first_tick': 'already-active' if live else 'not-requested', **start_fields}

            # The release channel also considers local tags. Sync the exact
            # official tag we resolved, then verify its peeled commit.
            source_track = 'tag:' + tag
            current = {'step': 'preflight_release_track', 'mutation': 'none'}
            engine_track_replacement(target.config_path, source_track)

            def verify_head(head):
                if head != expected:
                    raise ControlError('release_unverified',
                                       f'synced HEAD does not match the verified official release {tag}',
                                       fix='inspect the official release and deployment source before retrying')

        steps.append({'step': 'reuse_existing_deployment' if start else 'preflight_target',
                      'status': 'ok'})
        current, mutated = {'step': 'lock', 'mutation': 'possible'}, True
        with locked(ctx, target.config_path):
            steps.append({'step': 'lock', 'status': 'ok', 'mutation': 'completed'})
            current = {'step': 'recheck_target', 'mutation': 'none'}
            if (repo_identity(ctx, repo.path) != repo
                    or select_target(ctx, repo, args.config, require=True) != target
                    or setup_file_identities(target) != identities):
                raise ControlError('target_changed', f'{action} target changed after preflight',
                                   fix='inspect concurrent config, ownership and selection changes; '
                                       'preserve all recovery inputs', exit_code=2)
            validate_target(target, repo)
            require_unit_ownership(ctx, target, symlink_error=symlink_error)
            if start:
                require_start_config_binding(target)
                require_engine_checkout(ctx, target, source_repo=repo.path)
            require_source(ctx, target)
            require_clean_checkout(ctx, target)
            require_setup_transport(repo, target)
            require_harness(ctx, target)
            if setting and 'pi_provider' in changes:
                guard_provider_selection(ctx, target, candidate, allow_metered=args.allow_metered)
            provider = require_provider(candidate)
            evidence = prerequisites(ctx, candidate, action=action, provider=provider,
                                     allow_bootstrap_install=False)
            snapshot = update_observation(ctx, target)
            known_indices = snapshot['inventory']['additional_instances'] if setting else ()
            ctx.lifecycle_home = target.deploy_home
            activation = 'held' if args.stop else 'pending'
            activation_reason = 'explicit --stop' if args.stop else 'maintenance scheduling request'
            if (not start or update_pending(snapshot)
                    or any(item['enabled'] or item['active'] not in INACTIVE_STATES
                           for item in snapshot['timers'].values())):
                quiesce_locked(ctx, target, snapshot, disabled, stopped, steps, current,
                               wait=args.wait, action=action)
            current = {'step': 'recheck_target', 'mutation': 'none'}
            if (repo_identity(ctx, repo.path) != repo
                    or select_target(ctx, repo, args.config, require=True) != target
                    or setup_file_identities(target) != identities):
                raise ControlError('target_changed', f'{action} target changed while quiescing',
                                   fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
            validate_target(target, repo)
            require_unit_ownership(ctx, target, symlink_error=symlink_error)
            require_source(ctx, target)
            require_clean_checkout(ctx, target)
            require_quiescent(ctx, target, known_indices=known_indices)
            steps.append({'step': 'recheck_target', 'status': 'ok'})

            def read_target():
                return select_target(ctx, repo, args.config, require=True)

            if setting:
                if replacement != original:
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                    backup = target.config_path.with_name(target.config_path.name + '.bak-' + stamp)
                    current = {'step': 'backup_config', 'mutation': 'possible'}
                    atomic_publish(backup, original, reuse_only=True)
                    change['backup'] = str(backup)
                    steps.append({'step': 'backup_config', 'status': 'ok', 'mutation': 'completed'})
                    current = {'step': 'write_config', 'mutation': 'possible'}
                    if file_identity(target.config_path) != identities[target.config_path]:
                        raise ControlError('target_changed', 'deployment config changed during backup',
                                           fix='inspect concurrent changes; preserve the backup', exit_code=2)
                    atomic_publish(target.config_path, replacement)
                    steps.append({'step': 'write_config', 'status': 'ok', 'mutation': 'completed'})
                current = {'step': 'validate_non_activating', 'mutation': 'none'}
                target = read_target()
                validated_identities = setup_file_identities(target)
                if target != candidate:
                    raise ControlError('target_changed', 'deployment did not retain the requested setting',
                                       fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
                run_orbi_check(ctx, target)
                head = checkout_head(ctx, target)
                if (read_target() != target or head != previous['head']
                        or setup_file_identities(target) != validated_identities):
                    raise ControlError('target_changed', 'deployment changed during set validation',
                                       fix='inspect concurrent changes; preserve recovery inputs', exit_code=2)
                steps.append({'step': 'validate_non_activating', 'status': 'ok'})
                engine_result = 'unchanged'
            else:
                progress = {'engine_update': engine_result}
                current = {}
                try:
                    target, head, validated_identities = apply_release_locked(
                        ctx, target, read_target, steps, current, progress, repo=repo,
                        source_track=source_track, verify_head=verify_head)
                finally:
                    target = progress.get('target', target)
                    engine_result = progress['engine_update']
                engine_result = 'up_to_date' if head == previous['head'] else 'updated'
            current = {'step': 'refresh_units', 'mutation': 'none'}
            if args.stop:
                steps.append({'step': 'refresh_units', 'status': 'deferred',
                              'reason': 'next authorized start installs units; installer activates timers'})
            current = {'step': 'observe_scheduler', 'mutation': 'none'}
            after = paused_observation(ctx, target, known_indices=known_indices)
            if update_pending(after):
                raise ControlError('update_busy', f'work appeared during {action}',
                                   fix='inspect pending work and source state before retrying',
                                   evidence={'scheduler': after, 'pending_services': update_pending(after)})
            if after['state'] != 'ok':
                raise ControlError('scheduler_unavailable',
                                   f"cannot read the target scheduler: {after.get('reason')}",
                                   fix='verify the systemd user session, then rerun')
            if not args.stop:
                activation = 'possible'
                _, _, first_tick = activate_existing_locked(
                    ctx, args, repo, target, validated_identities, steps, current, activated,
                    first_tick_request=start)
                current = {'step': 'verify_activation', 'mutation': 'none'}
                after = update_observation(ctx, target, known_indices=known_indices)
                if not configured_timers_active(target, after):
                    raise ControlError('activation_unverified', 'engine validated but configured timers are not enabled/active',
                                       fix='inspect partial timer state before deliberate start recovery',
                                       evidence={'scheduler': after})
                if setting and any(not item['configured'] and
                                   (item['enabled'] or item['active'] not in INACTIVE_STATES)
                                   for item in after['timers'].values()):
                    raise ControlError('activation_unverified', 'surplus timers are still enabled or active',
                                       fix='inspect the scheduler and backup before deliberate recovery',
                                       evidence={'scheduler': after})
                activation = 'started'
            current = {'step': 'release_lock', 'mutation': 'possible'}
        report = new_deployment_report(ctx, target, provider)
        report['source'] = source_evidence(ctx, target)['state']
        report['deployed_commit'] = head
        if start:
            return {'action': action, 'platform': ctx.platform, 'status': 'started',
                    'dry_run': False, 'repo': repo.full, 'deployment': report,
                    'steps': steps, 'activated': True, 'activation': activation,
                    'first_tick': first_tick, 'scheduler': after, 'engine_update': engine_result,
                    'disabled_timers': disabled, 'stopped_services': stopped, **start_fields}
        return {'action': action, 'platform': ctx.platform,
                'status': 'applied' if setting else engine_result,
                **({'change': change} if setting else {}),
                'dry_run': False, 'repo': repo.full, 'deployment': report,
                'previous': previous, 'prerequisites': evidence,
                'scheduler': after, 'disabled_timers': disabled, 'stopped_services': stopped,
                'pending_services': update_pending(after),
                'engine_update': engine_result,
                'unit_refresh': 'deferred' if args.stop else 'refreshed',
                'unit_refresh_reason': 'next authorized start installs units' if args.stop else 'existing start actions',
                'scheduler_confirmation': 'stopped' if args.stop else 'enabled_active',
                'activation': activation, 'activation_reason': activation_reason,
                'next_action': 'Leave scheduling stopped.' if args.stop else 'None.',
                'steps': steps, 'activated': not args.stop,
                'warnings': []}
    except (ControlError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        if not start and not mutated and not steps and (not setting or isinstance(error, ControlError)):
            # A preflight refusal changed nothing; keep its own precise fix text.
            if isinstance(error, ControlError):
                error.evidence.setdefault('target', str(target.config_path) if target else args.config)
                error.evidence.setdefault('engine_update', engine_result)
                error.evidence.setdefault('activation', 'none')
            raise
        if activation == 'pending' or current['step'] == 'recheck_paths':
            activation = 'none'
        exc = lifecycle_failure(ctx, target, error, target_path=args.config, steps=steps,
                                current=current, mutated=mutated,
                                evidence={'previous': previous, 'disabled_timers': disabled,
                                          'stopped_services': stopped,
                                          'resume_command': resume, 'activation': activation,
                                          'activated_timers': activated, 'engine_update': engine_result,
                                          'activation_reason': activation_reason, **start_fields,
                                          **({'change': change} if setting and change else {})},
                                snapshot_reader=update_observation)
        if engine_result in {'updated', 'up_to_date'}:
            exc.evidence['engine_revision'] = head
        repair = (start_command if engine_result in {'updated', 'up_to_date'} and not args.stop
                  else resume)
        if repair:
            exc.fix += '; after repairing the cause, run ' + repair
            exc.evidence['repair_command'] = repair
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


def lifecycle_text(entry):
    return (f"Last lifecycle: {entry['timestamp']} /orbi {' '.join(entry['argv'])} "
            f"user={entry['user']} result={entry['result']}")


def work_count_text(count):
    if count is None:
        return 'unknown'
    return f'{count}+' if count == HOST_WORK_LIMIT else str(count)


def render(ctx, document, json_mode, *, verbose=False):
    if json_mode:
        ctx.out.write(json.dumps(document, indent=2) + '\n')
        return
    if document.get('action') == 'prune':
        if not document['candidates']:
            ctx.out.write('No verified stale user unit templates.\n')
        for row in document['candidates']:
            verb = 'Would remove' if document['dry_run'] else 'Removed'
            ctx.out.write(f"{verb} {', '.join(row['units'])} ({row['reason']}: {row['config']})\n")
        if document['dry_run'] and document['candidates']:
            ctx.out.write('Preview only. Use /orbi prune --apply to remove these templates.\n')
        return
    if document.get('action') in ('set', 'update'):
        target = document.get('deployment', {}).get('config', document.get('target', 'unknown'))
        ctx.out.write(f"{document.get('repo', 'Orbi')}: {target}\n")
        if document.get('dry_run'):
            workers = ('wait for workers to finish' if any(step['step'] == 'wait_for_workers'
                       for step in document['steps']) else 'stop workers')
            ctx.out.write(f'Engine unchanged (preview). Disable timers, cancel queued starts, '
                          f'{workers}, then conditional sync/validation.\n')
            ctx.out.write('Scheduling: ' + ('leave stopped.' if document['activation'] == 'none' else
                                          'conditional activation after engine validation and existing-target technical checks.') + '\n')
            ctx.out.write('Next: Run the requested update without --dry-run when ready.\n')
        else:
            if change := document.get('change'):
                for key, value in change['new'].items():
                    ctx.out.write(f'{key}: {json.dumps(change["old"][key])} -> {json.dumps(value)}\n')
                if change['backup']:
                    ctx.out.write(f"Backup: {change['backup']}\n")
            if document['stopped_services']:
                ctx.out.write("Stopped workers: " + ', '.join(document['stopped_services']) + '\n')
            ctx.out.write(f"Engine {document['engine_update']}: {document['deployment']['deployed_commit']}\n")
            ctx.out.write(f"Scheduling: {document['scheduler_confirmation']} (activation={document['activation']}).\n")
            ctx.out.write(f"Next: {document['next_action']}\n")
        return
    if document.get('scope') == 'host':
        if verbose:
            ctx.out.write(f"Host Orbi: coverage={document['coverage']['state']}; observed workers="
                          f"{document['totals']['observed_workers']} (not an absolute host total)\n")
            for row in document['rows']:
                model = (f" model={row['provider']}/{row['model']}" + (' (metered)' if row.get('metered') else '')
                         if row.get('provider') and row.get('model') else '')
                ctx.out.write(f"{row['manager'] or 'local-config'} {row['unit'] or row['binding']['config']} "
                              f"repo={row['repo'] or 'unknown'} Orbi={row['engine'].get('version') or 'unknown'} "
                              f"{row['kind']} timers={','.join(row.get('timers', {})) or 'none'} "
                              f"loaded={row['loaded']} installed={row['installed']} "
                              f"state={row['state']} scheduler={row['scheduler']} worker={row['worker']['state']} "
                              f"issue={row['worker'].get('issue', {}).get('url', 'unknown')} "
                              f"next={row['next_trigger'] or 'unknown'} binding={row['binding']['state']}{model}\n")
                if row.get('last_lifecycle'):
                    ctx.out.write(lifecycle_text(row['last_lifecycle']) + '\n')
            for line in flatten(document['coverage'], 'coverage.'):
                ctx.out.write(line + '\n')
            for repo, count in document.get('work', {}).items():
                ctx.out.write(f"Work {' '.join(repo.splitlines())}: {work_count_text(count)}\n")
        else:
            render_host_compact(ctx, document)
        budget = document['github_budget']
        parts = []
        for key in ('graphql', 'rest'):
            value = budget[key]
            name = 'GraphQL' if key == 'graphql' else 'REST'
            parts.append(f"{name} {value['remaining']}/{value['limit']} (resets {value['reset']})"
                         if value is not None else f'{name} unknown')
        ctx.out.write('GitHub API budget: ' + '; '.join(parts) + '\n')
        if None in budget.values() or None in document.get('work', {}).values():
            ctx.out.write('For unavailable GitHub data, check gh auth status, repository access and connectivity.\n')
        for suggestion in document.get('suggestions', ()):
            ctx.out.write(suggestion + '\n')
        return
    if document.get('action') == 'version':
        engine = document['deployment']['engine']
        ctx.out.write(f"Repository: {document['repo']}\n")
        ctx.out.write(f"Orbi: {engine.get('version') or 'unknown'} "
                      f"revision={engine.get('revision') or 'unknown'} "
                      f"({engine['state']}; {engine.get('reason', engine.get('provenance'))})\n")
    if document.get('action') == 'status' and 'repo' in document:
        engine = document.get('deployment', {}).get('engine', {})
        ctx.out.write(f"Repository: {document['repo']}\n")
        ctx.out.write(f"Orbi: {engine.get('version') or 'unknown'} "
                      f"revision={engine.get('revision') or 'unknown'} "
                      f"({engine.get('state', 'unknown')}; {engine.get('provenance', 'no deployment metadata')})\n")
        provider = document.get('deployment', {}).get('provider', {})
        if provider.get('metered'):
            ctx.out.write(f"Model: {provider['provider']}/{provider['model']} (metered)\n")
        cli = engine.get('bootstrap_cli', {})
        ctx.out.write(f"Bootstrap CLI: {cli.get('version') or 'unknown'} "
                      f"({cli.get('state', 'unavailable')}; {cli.get('comparison', 'unknown')})\n")
        inventory = document.get('scheduler', {}).get('inventory', {})
        counts = inventory.get('counts', {})
        working = document.get('activity', {}).get('working', {}).get('value')
        ctx.out.write(f"Scheduler: {document.get('deployment', {}).get('state', 'unavailable')} "
                      f"configured={document.get('deployment', {}).get('slots', 'unknown')} "
                      f"enabled={counts.get('enabled_timers', {}).get('value', 'unknown')} "
                      f"active={counts.get('active_timers', {}).get('value', 'unknown')} "
                      f"working={working if working is not None else 'unknown'}\n")
        if document.get('deployment', {}).get('last_lifecycle'):
            ctx.out.write(lifecycle_text(document['deployment']['last_lifecycle']) + '\n')
        for unit, slot in document.get('activity', {}).get('slots', {}).items():
            issue = slot.get('issue', {})
            identity = (f" #{issue['number']} {issue.get('title', '')} {issue['url']} "
                        f"run_id={slot['run_id']} phase={slot.get('phase', 'unknown')} "
                        f"last_activity={slot.get('last_activity', 'unknown')}" if issue else '')
            ctx.out.write(f"Slot {unit}: {slot['state']}{identity}\n")
        queue = document.get('queue', {})
        ctx.out.write(f"Queue: ready={len(queue['ready']) if 'ready' in queue else 'unknown'} "
                      f"pending={queue.get('pending_count', 'unknown')} "
                      f"({queue.get('state', 'unavailable')})\n")
    for line in flatten(document):
        ctx.out.write(line + '\n')


def render_host_compact(ctx, document):
    groups = {}
    unbound = []
    for row in document['rows']:
        if config := row['binding']['config']:
            groups.setdefault(config, []).append(row)
        elif row['kind'] == 'runner':
            unbound.append(row)
    coverage = document['coverage']
    manager_unavailable = any(item['state'] != 'ok' for item in coverage['managers'].values())
    unbound_busy = any(row['scheduler'] in DRAIN_STATES for row in unbound)
    header = (f"Host Orbi: coverage={coverage['state']}; "
              f"{len(groups)} deployments, {document['totals']['observed_workers']} observed workers")
    if unbound:
        header += f'; workers without a config: {len(unbound)} (--verbose to list)'
    ctx.out.write(header + '\n')
    for config, rows in sorted(groups.items()):
        first = rows[0]
        workers = [row for row in rows if row['kind'] == 'runner']
        busy = [row for row in workers if row['scheduler'] in DRAIN_STATES]
        timers = [timer for row in workers for timer in row.get('timers', {}).values()]
        scheduled = [timer for timer in timers if timer['state'] in ACTIVE_STATES]
        if busy:
            state = 'running'
        elif scheduled or any(row['state'] == 'idle' for row in workers):
            state = 'idle'
        elif (first['binding']['state'] != 'verified' or (not workers and (manager_unavailable or unbound_busy))
              or any(row['scheduler'] == 'unknown' for row in workers)
              or any(timer['state'] == 'unknown' for timer in timers)):
            state = 'unknown'
        else:
            state = 'stopped'
        issues = {row['worker'].get('issue', {}).get('number') for row in busy}
        numbers = [f'#{number}' for number in sorted(issues - {None})]
        if None in issues:
            numbers.append('unknown')
        # systemd's printed calendar timestamps start with a weekday; sort by date/time.
        next_run = min((timer['next_trigger'] for timer in scheduled
                        if re.match(r'^\S+ \d{4}-\d\d-\d\d ', timer['next_trigger'] or '')),
                       key=lambda stamp: stamp.split(' ', 1)[1], default='unknown')
        selection = '/'.join(first.get(key) or 'unknown' for key in ('provider', 'model', 'thinking'))
        if first.get('metered'):
            selection += ' (metered)'
        repos = first.get('repos', [])
        line = (f"{','.join(repos) or config} slots={len(busy)}/{first.get('max_concurrency', '?')} {selection} "
                f"state={state} issues={','.join(numbers) or '-'} next={next_run}")
        if 'work' in document:
            counts = ','.join(work_count_text(document['work'].get(repo)) for repo in repos)
            line += f" work={counts or 'unknown'}"
        ctx.out.write(' '.join(line.splitlines()) + '\n')
    problems = coverage['problems']
    other = [p for p in problems if not p.get('non_orbi')]
    if count := len(problems) - len(other):
        ctx.out.write(f"coverage {coverage['state']}: {count} non-Orbi units unreadable (--verbose to list)\n")
    if other:
        first = other[0]
        reason, manager = first['reason'], first['manager']
        subject = f'{manager}: ' if manager and not reason.startswith(f'{manager}:') else ''
        detail = ' '.join((subject + reason).splitlines())
        more = f' (+{len(other) - 1} more)' if len(other) > 1 else ''
        ctx.out.write(f"coverage {coverage['state']}: {detail}{more} (--verbose for details and repair)\n")


def render_error(ctx, action, exc, json_mode):
    document = {'action': action,
                'error': {'code': exc.code, 'message': exc.message,
                          'fix': exc.fix, 'mutated': exc.mutated}, **exc.evidence}
    if json_mode:
        ctx.out.write(json.dumps(document, indent=2) + '\n')
    elif action in ('set', 'update'):
        ctx.err.write(f"Orbi {action}: {exc.evidence.get('target', 'unbound target')}\n")
        if action == 'set' and (backup := exc.evidence.get('change', {}).get('backup')):
            ctx.err.write(f'Backup: {backup}\n')
        if exc.evidence.get('engine_update') in {'updated', 'up_to_date'}:
            ctx.err.write('Engine validated; ' + (
                'start failed or remains unverified.\n'
                if exc.evidence.get('activation') in {'possible', 'started'} else
                'scheduling remains stopped or unverified.\n'))
        ctx.err.write(f"Engine: {exc.evidence.get('engine_update', 'not_applied')} "
                      f"revision={exc.evidence.get('engine_revision', 'unverified')}; "
                      f"activation: {exc.evidence.get('activation', 'none')}.\n")
        if exc.evidence.get('disabled_timers'):
            ctx.err.write("Disabled timers: " + ', '.join(exc.evidence['disabled_timers']) + '\n')
        if exc.evidence.get('stopped_services'):
            ctx.err.write("Stopped workers: " + ', '.join(exc.evidence['stopped_services']) + '\n')
        failed = exc.evidence.get('steps', [{}])[-1]
        if failed.get('unit'):
            ctx.err.write(f"Failed step: {failed['step']} ({failed['unit']}).\n")
        elif action == 'set' and failed.get('step'):
            ctx.err.write(f"Failed step: {failed['step']}.\n")
        ctx.err.write(f"Error {exc.code}: {exc.message}\nNext: {exc.fix}\n")
    else:
        ctx.err.write(f'error={exc.code} message={exc.message} fix={exc.fix} '
                      f'mutated={exc.mutated}\n')
        for line in flatten(exc.evidence):
            ctx.err.write(line + '\n')


# Host inventory is deliberately separate from repository selection and mutations.
HOST_DETAIL_LIMIT = 256
# Every installed/loaded unit gets one bounded probe to decide whether it is
# Orbi's; ordinary hosts have hundreds of unrelated units in the system manager.
FLEET_CLASSIFY_LIMIT = 2048
HOST_LIST_LIMIT = 8192
HOST_PROC = Path('/proc')
HOST_CGROUP = Path('/sys/fs/cgroup')


def host_read_failure(proc):
    # Classify, never relay scheduler stderr (it may contain private commands).
    return 'denied' if re.search(r'permission denied|access denied|not permitted',
                                 proc.stderr or '', re.I) else 'failed'


def host_problem(coverage, manager, reason, *, non_orbi=False,
                 fix='restore read access to local scheduler/config evidence and rerun status all; no sudo'):
    coverage['state'] = 'partial'
    problem = {'manager': manager, 'reason': reason, 'fix': fix}
    if non_orbi:
        problem['non_orbi'] = True  # No observed Orbi evidence, not proof of absence.
    coverage['problems'].append(problem)


def host_definition_dirs(ctx, manager):
    if manager == 'user':
        return [user_unit_dir(ctx), data_home(ctx) / 'systemd/user',
                Path('/etc/systemd/user'), Path('/run/systemd/user'), Path('/usr/lib/systemd/user')]
    return [Path('/etc/systemd/system'), Path('/run/systemd/system'),
            Path('/usr/local/lib/systemd/system'), Path('/usr/lib/systemd/system')]


def host_orbi_command(args):
    """Identify direct CLI/module execution without executing or exposing argv."""
    if not isinstance(args, list) or not args or not all(isinstance(a, str) for a in args):
        return {'orbi': False, 'runner': False, 'configs': []}
    if Path(args[0].lstrip('-+!:@')).name == 'orbi':
        tail = args[1:]
    elif len(args) >= 3 and Path(args[0]).name.startswith('python') and args[1] == '-m' and args[2] in {'orbi', 'orbi.runner'}:
        tail = args[3:]
    else:
        return {'orbi': False, 'runner': False, 'configs': []}
    refs, positionals = [], []
    index = 0
    while index < len(tail):
        arg = tail[index]
        if arg == '--config' and index + 1 < len(tail):
            index += 1
            refs.append(tail[index])
        elif arg.startswith('--config='):
            refs.append(arg.split('=', 1)[1])
        elif not arg.startswith('-'):
            positionals.append(arg)
        index += 1
    # Bare orbi is the delivery tick. Subcommands are not workers.
    return {'orbi': True, 'runner': not positionals and not any(a in {'--help', '-h', '--version'} for a in tail), 'configs': refs}


def host_resolve_configs(references, cwd=None, *, verify_paths=False):
    resolved = set()
    for value in references:
        if not value or '%' in value or '$' in value:
            continue  # unsupported expansion is not a verified binding
        candidate = Path(value)
        if not candidate.is_absolute():
            if not cwd or not Path(cwd).is_absolute():
                continue
            candidate = Path(cwd) / candidate
        if verify_paths:
            candidate = checked_path(candidate, 'unit config')
        try:
            resolved.add(str(candidate.resolve()))
        except (OSError, RuntimeError):
            # Retain an unreadable identity for host_configs instead of losing
            # healthy rows to a denied parent or a broken symlink chain.
            resolved.add(str(candidate.absolute()))
    return sorted(resolved)


def systemd_logical_lines(text):
    """Fold systemd.syntax(7) continuations, ignoring intervening comments."""
    lines, pending = [], []
    for line in text.removesuffix('\n').split('\n'):
        line = line.removesuffix('\r')
        if line.lstrip().startswith(('#', ';')):
            continue
        if (len(line) - len(line.rstrip('\\'))) % 2:
            pending.append(line[:-1])
        else:
            lines.append(' '.join([*pending, line]))
            pending.clear()
    if pending:
        # systemd still replaces the continuation marker at EOF.
        lines.append(' '.join(pending) + ' ')
    return '\n'.join(lines)


class UnitParseError(ValueError):
    """A tokenization failure, distinct from an unreadable metadata file."""


def host_definition(ctx, path, *, working_directory=None, instance=None, manager='user', user_home=None,
                    verify_paths=False, template=False, text=None):
    """Extract config references only; never return commands or environment contents."""
    text = systemd_logical_lines(bounded_text(path) if text is None else text)
    references = []
    try:
        for assignment in re.findall(r'^Environment=(.*)$', text, re.M):
            references.extend(token.partition('=')[2] for token in shlex.split(assignment)
                              if token.startswith('ORBI_CONFIG='))
        commands = [host_orbi_command(shlex.split(command))
                    for command in re.findall(r'^ExecStart=(.+)$', text, re.M)]
    except ValueError:
        raise UnitParseError('unit definition is unparsable') from None
    for command in commands:
        references.extend(command['configs'])
    runner = any(command['runner'] for command in commands)
    orbi = any(command['orbi'] for command in commands)
    directories = re.findall(r'^WorkingDirectory=(.+)$', text, re.M)
    cwd = working_directory or (directories[0].strip().strip('"\x27') if len(directories) == 1 else None)
    if not references and orbi and cwd and (Path(cwd) / 'orbi.toml').is_file():
        references.append(str(Path(cwd) / 'orbi.toml'))
    expanded = []
    for value in references:
        if template and re.search(r'%[iI]', str(Path(cwd or '.') / value)):
            continue  # A bare template has no instance-specific config to verify.
        # %h belongs to the manager, not the invoking user. Do not attribute a
        # system unit to the caller's home when the manager home is unobserved.
        if manager == 'user':
            value = value.replace('%h', str(user_home or home_dir(ctx)))
        if instance is not None:
            value = value.replace('%i', instance)
        expanded.append(value)
    return {'configs': host_resolve_configs(expanded, cwd, verify_paths=verify_paths), 'referenced': bool(expanded),
            'runner': runner, 'orbi': orbi, 'command': bool(commands)}


def host_plist(data):
    """Use the same config/worker evidence for installed and observable jobs."""
    command = host_orbi_command(data.get('ProgramArguments', [data.get('Program', '')]))
    references = list(command['configs'])
    config = data.get('EnvironmentVariables', {}).get('ORBI_CONFIG')
    if isinstance(config, str):
        references.append(config)
    cwd = data.get('WorkingDirectory')
    if not references and command['orbi'] and cwd and (Path(cwd) / 'orbi.toml').is_file():
        references.append(str(Path(cwd) / 'orbi.toml'))
    refs = host_resolve_configs(references, cwd)
    binding = ('conflicting' if len(refs) > 1 else 'verified' if refs else
               'unreadable' if references else 'unknown')
    return {'config': refs[0] if binding == 'verified' else None, 'configs': refs,
            'binding': binding, 'runner': command['runner'], 'orbi': command['orbi'],
            'command': bool(data.get('ProgramArguments') or data.get('Program'))}


def host_config_paths(ctx, coverage):
    paths = set()
    for folder in (data_home(ctx), config_home(ctx) / 'orbi'):
        try:
            if folder.is_dir():
                for index, child in enumerate(folder.iterdir()):
                    if index >= HOST_LIST_LIMIT:
                        host_problem(coverage, None, 'deployment config discovery truncated')
                        break
                    try:
                        path = child / 'orbi.toml'
                        if child.is_dir() and path.is_file():
                            paths.add(path)
                    except OSError:
                        host_problem(coverage, None, 'deployment config discovery unreadable: ' + str(child))
        except OSError:
            host_problem(coverage, None, 'deployment config discovery unreadable: ' + str(folder))
    for path in (ctx.cwd / 'orbi.toml', config_home(ctx) / 'orbi/orbi.toml'):
        try:
            if path.is_file():
                paths.add(path)
        except OSError:
            host_problem(coverage, None, 'deployment config discovery unreadable: ' + str(path))
    if ctx.env.get('ORBI_CONFIG'):
        paths.add(Path(ctx.env['ORBI_CONFIG']))
    return paths


def host_configs(ctx, paths, coverage):
    deployments = {}
    for candidate in sorted({Path(p) for p in paths}, key=str):
        key = str(candidate.absolute())
        try:
            path = candidate.resolve()
            key = str(path)
            if key in deployments:
                continue
            target = deployment_from(path, tomllib.loads(bounded_text(path)))
            summary = local_deployment_summary(ctx, target, metadata_only=True)
            provider, model = target.data.get('pi_provider'), target.data.get('pi_model')
            deployments[key] = {'binding': {'state': 'verified', 'config': key},
                                'last_lifecycle': last_lifecycle(target),
                                'repo': target.source_repos[0] if len(target.source_repos) == 1 else None,
                                'repos': list(target.source_repos), 'target': target, 'engine': summary['engine'],
                                'provider': provider, 'model': model,
                                'metered': bool(provider and model and
                                                provider_metered(ctx, target, provider, model) is not False),
                                'thinking': target.data.get('pi_thinking'), 'max_concurrency': target.max_concurrency}
        except (OSError, ValueError, UnicodeError, RuntimeError, ControlError):
            deployments[key] = {'binding': {'state': 'unreadable', 'config': key},
                                'repo': None, 'engine': {'state': 'unknown', 'version': None}}
            host_problem(coverage, None, 'unreadable or invalid deployment config: ' + key)
    return deployments


def host_linux(ctx, coverage):
    records, paths, worker_bindings = [], host_config_paths(ctx, coverage), {}
    for manager in ('user', 'system'):
        flag = '--' + manager
        evidence = {'state': 'ok', 'lists': {}, 'failures': {},
                    'fix': 'restore read access to this local manager and rerun status all; no sudo'}
        coverage['managers'][manager] = evidence
        loaded, installed, definitions = {}, {}, {}
        for command, destination, key in (('list-units', loaded, 'unit'),
                                           ('list-unit-files', installed, 'unit_file')):
            failure = 'invalid'
            try:
                proc = ctx.run(['systemctl', flag, command, '--type=service', '--type=timer',
                                '--all', '--no-pager', '--output=json'], allow_failure=True)
                if proc.returncode:
                    failure = host_read_failure(proc)
                    raise ValueError('unavailable listing')
                if len(proc.stdout) > 4 * 1024 * 1024:
                    raise ValueError('oversized listing')
                items = json.loads(proc.stdout)
                if not isinstance(items, list):
                    raise ValueError('invalid listing')
                if len(items) > HOST_LIST_LIMIT:
                    host_problem(coverage, manager, f'{command} exceeds {HOST_LIST_LIMIT} entries; truncated')
                for item in items[:HOST_LIST_LIMIT]:
                    name = item[key]
                    if not isinstance(name, str) or not name.endswith(('.service', '.timer')):
                        raise ValueError('invalid unit identity')
                    destination[Path(name).name] = item
                    if command == 'list-unit-files' and Path(name).is_absolute():
                        definitions[Path(name).name] = Path(name)
                evidence['lists'][command] = 'ok'
            except (ControlError, ValueError, KeyError, TypeError) as exc:
                if isinstance(exc, ControlError):
                    failure = exc.code
                evidence['state'] = 'denied' if failure == 'denied' else 'unavailable'
                evidence['lists'][command] = 'unavailable'
                evidence['failures'][command] = failure
                host_problem(coverage, manager, command + ' ' + failure + '; inventory unavailable, not empty')
        # Installed definitions can exist even when a manager is inaccessible.
        count = 0
        for folder in host_definition_dirs(ctx, manager):
            try:
                if not folder.exists():
                    continue
                for path in sorted(folder.iterdir()):
                    if path.suffix not in ('.service', '.timer'):
                        continue
                    count += 1
                    if count > HOST_LIST_LIMIT:
                        break
                    definitions.setdefault(path.name, path)
            except OSError:
                host_problem(coverage, manager, 'installed definition directory unreadable: ' + str(folder))
        if count > HOST_LIST_LIMIT:
            host_problem(coverage, manager, 'installed definition scan truncated')
        masked_templates = {name for name, item in installed.items()
                            if name.endswith(('@.service', '@.timer')) and item.get('state') in {'masked', 'masked-runtime'}}
        metadata = {}
        unparsable = set()
        for name, path in definitions.items():
            if name in masked_templates:
                continue
            try:
                item = host_definition(ctx, path, manager=manager, template=name.endswith(('@.service', '@.timer')))
                if 'orbi' in name.lower() or item['configs'] or item['orbi']:
                    metadata[name] = item
                    installed.setdefault(name, {'state': 'unknown'})
                    paths.update(item['configs'])
            except (UnitParseError, UnicodeError):
                unparsable.add(name)
                if 'orbi' in name.lower():
                    metadata[name] = {'configs': [], 'unreadable': True}
            except (OSError, ValueError):
                if 'orbi' in name.lower():
                    metadata[name] = {'configs': [], 'unreadable': True}
                    if not name.endswith(('@.service', '@.timer')):
                        host_problem(coverage, manager, 'installed definition unreadable: ' + name)
        for name in definitions:
            if name.endswith('.timer') and name[:-6] + '.service' in metadata:
                metadata.setdefault(name, {'configs': [], 'runner': False})
        # Detail listed loaded/installed units (also arbitrary names), and local
        # definitions. Only Orbi/config-evidenced units survive the output filter.
        names = sorted(set(loaded) | set(installed) | set(metadata))
        templates = {n for n in names if n.endswith(('@.service', '@.timer'))}
        query_names = [n for n in names if n not in templates]
        if len(query_names) > HOST_DETAIL_LIMIT:
            host_problem(coverage, manager, f'unit detail limit {HOST_DETAIL_LIMIT}; remaining identities unobserved')
            query_names = sorted(query_names, key=lambda n: ('orbi' not in n.lower() and n not in metadata, n))[:HOST_DETAIL_LIMIT]
        # A bare template has no runtime properties; inspect its fragment instead.
        details = {name: {} for name in names if name in templates}
        failures = {}
        for name in query_names:
            values = {}
            failure = 'invalid'
            try:
                proc = ctx.run(['systemctl', flag, 'show', name,
                                *[arg for prop in ('Id', 'LoadState', 'ActiveState', 'SubState', 'Result',
                                                  'MainPID', 'InvocationID', 'ControlGroup', 'WorkingDirectory', 'FragmentPath',
                                                  'DropInPaths', 'UnitFileState', 'Unit', 'Triggers',
                                                  'LastTriggerUSec', 'NextElapseUSecRealtime') for arg in ('-p', prop)]],
                               allow_failure=True)
                if proc.returncode or len(proc.stdout) > 65536:
                    failure = host_read_failure(proc) if proc.returncode else 'oversized'
                    raise ValueError('unavailable details')
                values = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
                if values.get('Id') != name:
                    raise ValueError('missing unit identity')
            except (ControlError, ValueError) as exc:
                failures[name] = exc.code if isinstance(exc, ControlError) else failure
            details[name] = values
        names = sorted(details)
        for name, values in details.items():
            # Read actual fragments/drop-ins; do not trust basename or unit_name.
            refs, unreadable, runner, referenced, command, orbi = set(), False, False, False, False, False
            fragment = values.get('FragmentPath') or definitions.get(name)
            masked_template = name in masked_templates
            sources = [str(fragment)] if fragment and not masked_template else []
            try:
                sources.extend(shlex.split(values.get('DropInPaths', '')))
            except ValueError:
                unparsable.add(name)
                unreadable = True
            for source in sources:
                try:
                    instance = name.split('@', 1)[1].rsplit('.', 1)[0] if '@' in name and '@.' not in name else None
                    item = host_definition(ctx, source, working_directory=values.get('WorkingDirectory'),
                                           instance=instance, manager=manager, template=name in templates)
                    refs.update(item['configs'])
                    runner |= item['runner']
                    command |= item['command']
                    orbi |= item['orbi']
                    referenced |= item['referenced']
                except (UnitParseError, UnicodeError):
                    unparsable.add(name)
                    unreadable = True
                except (OSError, ValueError):
                    unreadable = True
            if not sources and name in metadata and not masked_template:
                refs.update(metadata[name]['configs'])
                unreadable = metadata[name].get('unreadable', False)
            if name in templates and not masked_template and (not sources or unreadable):
                if name not in unparsable:
                    failures[name] = 'template fragment unreadable'
                unreadable = True
            paths.update(refs)
            metadata[name] = {'configs': sorted(refs), 'unreadable': unreadable,
                              'runner': runner, 'referenced': referenced, 'command': command, 'orbi': orbi}
        for name in sorted(unparsable):
            host_problem(coverage, manager, f'{manager}:{name}: unit definition is unparsable',
                         fix='inspect and correct the named unit definition, then rerun status all')
        relevant = {n for n in names if 'orbi' in n.lower() or metadata[n]['configs'] or metadata[n]['orbi']}
        relevant.update(n for n in names if n.endswith('.timer') and
                        (details[n].get('Unit') or details[n].get('Triggers') or n[:-6] + '.service') in relevant)
        for name, failure in failures.items():
            # An unreadable arbitrary unit still cannot certify complete coverage.
            reason = failure if name in templates else 'unit details ' + failure
            host_problem(coverage, manager, reason + ': ' + name, non_orbi=name not in relevant)
        # Pair by exact service identity/explicit timer target, not slot number.
        pairs = {}
        for name in sorted(relevant):
            if name.endswith('.timer'):
                target = details[name].get('Unit') or details[name].get('Triggers') or name[:-6] + '.service'
                if not re.fullmatch(r'[^\s/]+\.service', target):
                    target = name
            else:
                target = name
            pairs.setdefault(target, []).append(name)
        for unit, members in pairs.items():
            service = details.get(unit, {})
            timer_names = [n for n in members if n.endswith('.timer')]
            timer = next((n for n in timer_names if
                          (details[n].get('ActiveState') or loaded.get(n, {}).get('active')) in ACTIVE_STATES),
                         next(iter(timer_names), None))
            timer_values = details.get(timer, {})
            refs = sorted({p for n in members for p in metadata[n]['configs']})
            unreadable = any(metadata[n].get('unreadable') for n in members)
            unresolved = any(metadata[n].get('referenced') and not metadata[n]['configs'] for n in members)
            binding = 'conflicting' if len(refs) > 1 else 'unreadable' if unreadable or unresolved else 'verified' if refs else 'unknown'
            # Template fragment failures already have a per-unit diagnostic above.
            if binding == 'conflicting' or unresolved or any(
                    metadata[n]['unreadable'] for n in members if n not in templates):
                host_problem(coverage, manager, binding + ' config binding: ' + unit)
            kind = ('template' if '@.' in unit else 'timer' if unit.endswith('.timer') else
                    'runner' if metadata.get(unit, {}).get('runner') or
                    (not metadata.get(unit, {}).get('command') and
                     re.fullmatch(r'orbi(?:-[^@]+)?@[^.]+\.service', unit)) else 'nonrunner')
            state = service.get('ActiveState') or loaded.get(unit, {}).get('active')
            # show can load an installed definition as a side effect of inspection.
            # The bulk snapshot, not LoadState from that later read, establishes presence.
            is_loaded = (unit in loaded if evidence['lists'].get('list-units') == 'ok' else
                         True if unit in loaded else None)
            if not state:
                state = 'unloaded' if evidence['lists'].get('list-units') == 'ok' else 'unknown'
            worker = {'state': ('active/issue unknown' if state == 'active' else
                                'starting' if state in {'activating', 'reloading'} else
                                'draining' if state == 'deactivating' else
                                'idle' if state in INACTIVE_STATES else 'unknown')}
            timer_state = timer_values.get('ActiveState') or loaded.get(timer, {}).get('active', 'unknown')
            scheduled = timer_state in ACTIVE_STATES
            observed_state = ('running' if state == 'active' else worker['state'] if state in {'activating', 'reloading', 'deactivating'}
                              else 'idle' if state == 'inactive' and scheduled else
                              'stopped' if state == 'inactive' and (not timer or timer_state == 'inactive') else state)
            if kind != 'runner':
                worker = {'state': 'not a worker'}
            elif state == 'active':
                worker_bindings[manager, unit] = service
            timers = {n: {'state': details[n].get('ActiveState') or loaded.get(n, {}).get('active', 'unknown'),
                          'enabled': details[n].get('UnitFileState', 'unknown'),
                          'next_trigger': details[n].get('NextElapseUSecRealtime') or None}
                      for n in members if n.endswith('.timer')}
            records.append({'manager': manager, 'unit': unit, 'timer': timer, 'timers': timers, 'kind': kind,
                            'state': observed_state,
                            'loaded': is_loaded, 'installed': any(n in installed or n in definitions for n in members),
                            'scheduler': state, 'timer_state': timer_state,
                            'timer_enabled': timer_values.get('UnitFileState', 'unknown'),
                            'next_trigger': timer_values.get('NextElapseUSecRealtime') or None,
                            'binding': {'state': binding, 'config': refs[0] if binding == 'verified' else None},
                            'worker': worker})
    return records, paths, worker_bindings


def host_darwin(ctx, coverage):
    rows, paths = [], host_config_paths(ctx, coverage)
    for manager, folders in ((f'gui/{os.getuid()}', [Path(ctx.env['ORBI_UNIT_DIR']) if ctx.env.get('ORBI_UNIT_DIR') else home_dir(ctx) / 'Library/LaunchAgents', Path('/Library/LaunchAgents')]),
                             (f'user/{os.getuid()}', []),
                             ('system', [Path('/Library/LaunchDaemons')])):
        evidence = {'state': 'ok', 'fix': 'restore read access to the local launchd domain and rerun status all; no sudo'}
        coverage['managers'][manager] = evidence
        labels, definitions, listed_labels = set(), {}, set()
        try:
            proc = ctx.run(['launchctl', 'print', manager], allow_failure=True)
            if proc.returncode:
                evidence['state'] = host_read_failure(proc)
                raise ValueError('domain unavailable')
            if len(proc.stdout) > 4 * 1024 * 1024:
                raise ValueError('oversized domain')
            # launchctl print is human output, not a stable machine schema. Only
            # accept label-shaped rows from its services table; malformed tables
            # leave coverage unknown rather than proving an empty manager.
            tables = re.findall(r'^\s*services = \{\n(.*?)^\s*\}', proc.stdout, re.M | re.S)
            if len(tables) != 1:
                raise ValueError('domain table unavailable')
            for line in tables[0].splitlines():
                fields = line.split()
                if fields and re.fullmatch(r'[\w.-]+', fields[-1]):
                    listed_labels.add(fields[-1])
                    if 'orbi' in fields[-1].lower():
                        labels.add(fields[-1])
        except (ControlError, ValueError):
            if evidence['state'] != 'denied':
                evidence['state'] = 'unavailable'
            host_problem(coverage, manager, 'launchd domain listing ' + evidence['state'])
        for folder in folders:
            try:
                if not folder.exists():
                    continue
                installed_paths = sorted(p for p in folder.iterdir() if p.suffix == '.plist')
                if len(installed_paths) > HOST_LIST_LIMIT:
                    host_problem(coverage, manager, 'installed plist discovery truncated')
                for path in installed_paths[:HOST_LIST_LIMIT]:
                    try:
                        data = plistlib.loads(bounded_bytes(path))
                        label = data.get('Label')
                        item = host_plist(data)
                        if not isinstance(label, str) or not ('orbi' in label.lower() or item['configs'] or item['orbi']):
                            continue
                        definitions[label] = item
                        labels.add(label)
                        paths.update(item['configs'])
                        if item['binding'] in {'conflicting', 'unreadable'}:
                            host_problem(coverage, manager, item['binding'] + ' plist config binding: ' + label)
                    except (OSError, ValueError, ExpatError, TypeError, AttributeError):
                        if 'orbi' in path.name.lower():
                            host_problem(coverage, manager, 'unreadable plist: ' + str(path))
                            rows.append({'manager': manager, 'unit': str(path), 'timer': None,
                                         'kind': 'definition', 'loaded': None, 'installed': True,
                                         'scheduler': 'unknown', 'state': 'unknown', 'next_trigger': None,
                                         'binding': {'state': 'unreadable', 'config': None},
                                         'worker': {'state': 'unknown'}})
            except OSError:
                host_problem(coverage, manager, 'installed plist directory unreadable: ' + str(folder))
        candidates = labels | listed_labels
        if len(candidates) > HOST_DETAIL_LIMIT:
            host_problem(coverage, manager, 'launchd detail limit; remaining jobs unobserved')
        for label in sorted(candidates, key=lambda label: (label not in labels, label))[:HOST_DETAIL_LIMIT]:
            state, loaded = 'unknown', True if label in listed_labels else None
            definition = definitions.get(label, {})
            config, binding = definition.get('config'), definition.get('binding', 'unknown')
            runner = definition.get('runner', False) or (not definition.get('command') and '.runner.' in label)
            try:
                proc = ctx.run(['launchctl', 'print', manager + '/' + label], allow_failure=True)
                if proc.returncode == 0 and len(proc.stdout) <= 65536:
                    loaded = True
                    # The loaded job can come from a different plist with the same
                    # label. Only its observed definition can bind the live repo.
                    job_paths = re.findall(r'^\s*path = (.+)$', proc.stdout, re.M)
                    if len(job_paths) != 1:
                        config, binding = None, 'unknown'
                    else:
                        try:
                            actual = plistlib.loads(bounded_bytes(job_paths[0]))
                            item = host_plist(actual)
                            runner = item['runner'] or (not item['command'] and '.runner.' in label)
                            paths.update(item['configs'])
                            if actual.get('Label') != label:
                                config, binding = None, 'unknown'
                            elif config and item['config'] and config != item['config']:
                                config, binding = None, 'conflicting'
                            else:
                                config, binding = item['config'], item['binding']
                            if binding in {'conflicting', 'unreadable'}:
                                host_problem(coverage, manager, binding + ' loaded/installed plist binding: ' + label)
                        except (OSError, ValueError, ExpatError, TypeError, AttributeError):
                            config, binding = None, 'unreadable'
                            host_problem(coverage, manager, 'loaded plist unreadable: ' + label)
                    states = re.findall(r'^\s*state = ([a-z ]+)$', proc.stdout, re.M)
                    if len(states) == 1:
                        state = ('active' if states[0] == 'running' else
                                 'inactive' if states[0] in {'not running', 'waiting'} else 'unknown')
                    exits = re.findall(r'^\s*last exit code = ([0-9]+)$', proc.stdout, re.M)
                    if state == 'inactive' and len(exits) == 1 and int(exits[0]) != 0:
                        state = 'failed'
                elif evidence['state'] == 'ok' and label not in listed_labels:
                    # Domain listing succeeded and this job is absent there.
                    loaded = False
                    state = 'unloaded'
                else:
                    host_problem(coverage, manager, 'job state unavailable: ' + label, non_orbi=label not in labels)
            except ControlError:
                host_problem(coverage, manager, 'job state unavailable: ' + label, non_orbi=label not in labels)
            if label not in labels and not config:
                continue
            if loaded is not False and state == 'unknown':
                host_problem(coverage, manager, 'job state unknown: ' + label)
            rows.append({'manager': manager, 'unit': label, 'timer': None,
                         'kind': 'runner' if runner else 'nonrunner',
                         'loaded': loaded, 'installed': label in definitions, 'scheduler': state,
                         'state': 'running' if state == 'active' else 'idle' if state == 'inactive' else state,
                         'next_trigger': None, 'binding': {'state': binding,
                                                         'config': str(Path(config).resolve()) if config else None},
                         'worker': {'state': 'not a worker' if not runner else 'active/issue unknown' if state == 'active' else
                                    'idle' if state in INACTIVE_STATES else 'unknown'}})
    return rows, paths


# Installer-only inventory is stricter than the observational `status all`.
# Never interpret incomplete evidence as an empty fleet; disclose any offline
# non-lingering accounts whose definition folders could not be read.
@dataclasses.dataclass(frozen=True)
class FleetManager:
    name: str
    flags: tuple
    uid: int
    home: Path

    def call(self, ctx, verb, *args):
        env = {key: value for key, value in ctx.env.items() if not key.startswith(
            ('DBUS_', 'SYSTEMD_'))}
        env.update(LC_ALL='C', XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}')
        # Unlike a probe, start waits for unit startup including Orbi's bounded
        # ExecStartPre steps; stop waits for the manager's termination sequence.
        timeout = MUTATION_TIMEOUT if verb in {'start', 'stop', 'enable', 'disable'} else PROBE_TIMEOUT
        proc = ctx.run(['systemctl', *self.flags, '--no-ask-password', verb, *args],
                       env=env, timeout=timeout, allow_failure=True)
        if proc.returncode:
            subject = ' '.join(str(arg) for arg in args if not str(arg).startswith('-'))
            fleet_refuse(f'{self.name}: {verb} {host_read_failure(proc)}'
                         + (f' ({subject})' if subject else ''))
        return proc.stdout


def fleet_refuse(message):
    raise ControlError('installer_fleet_hold', message)


def fleet_managers(ctx):
    uid, home = os.getuid(), home_dir(ctx)
    managers = [FleetManager('system', ('--system',), 0, Path('/root')),
                FleetManager('user', ('--user',), uid, home)]
    # The caller bus alone is not coverage. Check local accounts for installed
    # evidence and /run/user for live managers, including users with custom XDG paths.
    accounts = ctx.run(['getent', '-s', 'files', 'passwd']).stdout.splitlines()
    try:
        active = {int(p.name) for p in Path('/run/user').iterdir() if p.name.isdecimal()}
    except FileNotFoundError:
        active = set()
    except (OSError, ValueError) as error:
        fleet_refuse(f'cannot verify running user managers ({type(error).__name__})')
    if len(accounts) > HOST_LIST_LIMIT or len(active) > HOST_DETAIL_LIMIT:
        fleet_refuse('local account coverage exceeds the inventory limit')
    known = {uid}
    not_checked = []
    lingering = None
    for row in accounts:
        fields = row.split(':')
        if len(fields) != 7 or not fields[2].isdecimal() or not Path(fields[5]).is_absolute():
            fleet_refuse('local account inventory is unreadable')
        name, other_uid, other_home = fields[0], int(fields[2]), Path(fields[5])
        if other_uid == uid:
            continue
        if other_uid in known or not re.fullmatch(r'[a-zA-Z0-9_.-]+', name):
            fleet_refuse('ambiguous local account identity')
        known.add(other_uid)
        manager = FleetManager(f'user:{name}', ('--user', f'--machine={name}@.host'),
                               other_uid, other_home)
        live = other_uid in active
        evidence = fleet_offline_user_evidence(ctx, manager, live=live)
        if evidence is None:
            if not live:
                if lingering is None:
                    try:
                        lingering = {p.name for p in Path('/var/lib/systemd/linger').iterdir()}
                    except (OSError, ValueError) as error:
                        fleet_refuse(f'{manager.name}: cannot verify linger state ({type(error).__name__})')
                if name not in lingering:
                    not_checked.append(name)
                    continue
            fleet_refuse(f'{manager.name}: cannot verify installed definitions (PermissionError)')
        if live or evidence:
            managers.append(manager)
    if active - known:
        fleet_refuse('unidentified local user managers: ' + ', '.join(map(str, sorted(active - known))))
    return tuple(managers), tuple(sorted(not_checked))


def fleet_offline_user_evidence(ctx, manager, *, live):
    """True for Orbi evidence, False for none, None for denied folder listing."""
    unreadable = False
    for relative in ('.config/systemd/user.control', '.config/systemd/user', '.local/share/systemd/user'):
        folder = manager.home / relative
        try:
            paths = folder.iterdir()
            if live:
                next(paths, None)  # check directory access; read units only through the existing manager inventory
                continue
            for index, path in enumerate(paths):
                if index >= HOST_LIST_LIMIT:
                    fleet_refuse(f'{manager.name}: installed definitions exceed inventory limit')
                if path.suffix not in {'.timer', '.service'}:
                    continue
                try:
                    if path.is_symlink() and path.resolve() == Path('/dev/null'):
                        continue
                    item = host_definition(ctx, path, manager='user', user_home=manager.home)
                except ValueError:
                    fleet_refuse(f'{manager.name}:{path.name}: unit definition is unparsable')
                except FileNotFoundError:
                    continue  # missing unit or dangling symlink, not an empty folder
                except PermissionError:
                    fleet_refuse(f'{manager.name}: cannot verify installed definitions (PermissionError)')
                if item['orbi'] or item['referenced']:
                    if unreadable:
                        fleet_refuse(f'{manager.name}: cannot verify installed definitions (PermissionError)')
                    return True
        except FileNotFoundError:
            continue
        except PermissionError:
            unreadable = True  # still look for readable Orbi evidence in the other folders
        except (OSError, ValueError) as error:
            fleet_refuse(f'{manager.name}: cannot verify installed definitions ({type(error).__name__})')
    return None if unreadable else False


def fleet_jobs(ctx, manager):
    jobs = {}
    for line in manager.call(ctx, 'list-jobs', '--no-legend', '--no-pager', '--full').splitlines():
        fields = line.split()
        if len(fields) < 4 or not fields[0].isdecimal() or fields[0] in jobs or len(jobs) >= HOST_LIST_LIMIT:
            fleet_refuse(f'{manager.name}: pending jobs are unreadable or exceed the limit')
        jobs[fields[0]] = tuple(fields[1:3])
    return jobs


def fleet_listing(ctx, manager, verb):
    text = manager.call(ctx, verb, '--type=service,timer', '--all', '--no-pager',
                        '--no-legend', '--full', '--plain')
    # Use the full-width UNIT column; the rest of list-units includes a free-text
    # description. No legend or state glyphs are part of an inventory row.
    names = set()
    if len(text) > 4 * 1024 * 1024:
        fleet_refuse(f'{manager.name}: {verb} inventory exceeds the limit')
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if (len(fields) < (4 if verb == 'list-units' else 2) or len(names) >= HOST_LIST_LIMIT
                or not FLEET_UNIT_NAME.fullmatch(fields[0]) or fields[0] in names):
            fleet_refuse(f'{manager.name}: {verb} returned invalid or oversized inventory')
        names.add(fields[0])
    return names


FLEET_UNIT_NAME = re.compile(r'(?!-)[a-zA-Z0-9_.:@\\-]+\.(?:service|timer)')
FLEET_UNIT_PROPS = ('Id', 'Names', 'LoadState', 'ActiveState', 'SubState', 'FragmentPath', 'DropInPaths', 'NeedDaemonReload',
                    'WorkingDirectory', 'User', 'DynamicUser', 'Environment', 'EnvironmentFiles',
                    'UnsetEnvironment', 'PassEnvironment', 'ExecCondition', 'ExecStartPre', 'ExecStart', 'ExecStartPost',
                    'ExecStop', 'ExecStopPost',
                    'UnitFileState', 'Unit', 'Triggers', 'TriggeredBy', 'Type', 'Result',
                    'ExecMainStartTimestampMonotonic', 'ExecMainStatus', 'ConditionResult',
                    'CanStart', 'CanStop', 'KillMode', 'SendSIGKILL', 'PartOf', 'ConsistsOf', 'BoundBy', 'RequiredBy',
                    'PropagatesStopTo', 'OnFailure', 'OnSuccess', 'Upholds', 'UpheldBy',
                    'Requires', 'Requisite', 'Wants', 'WantedBy', 'BindsTo', 'Conflicts', 'ConflictedBy')


FLEET_UNIT_LIST_PROPS = frozenset({
    'PartOf', 'ConsistsOf', 'BoundBy', 'RequiredBy', 'PropagatesStopTo', 'OnFailure', 'OnSuccess',
    'Upholds', 'UpheldBy', 'Requires', 'Requisite', 'Wants', 'WantedBy', 'BindsTo', 'Conflicts',
    'ConflictedBy', 'DropInPaths', 'Names', 'TriggeredBy'})


def fleet_unit(ctx, manager, name):
    if not FLEET_UNIT_NAME.fullmatch(name):
        fleet_refuse(f'{manager.name}: invalid installed or queued unit identity')
    text = manager.call(ctx, 'show', '--all', *('-p' + prop for prop in FLEET_UNIT_PROPS), name)
    values = {}
    for line in text.splitlines():
        key, sep, value = line.partition('=')
        if sep:
            values[key] = values[key] + '\n' + value if key in values else value
    if (len(text) > 65536 or not FLEET_UNIT_NAME.fullmatch(values.get('Id', ''))
            or not values.get('LoadState')):
        fleet_refuse(f'{manager.name}: cannot verify identity of {name}')
    return values


def fleet_fragments(ctx, manager, name, values):
    label = f'{manager.name}:{name}'
    try:
        fragments = [values.get('FragmentPath'), *shlex.split(values.get('DropInPaths', ''))]
    except ValueError:
        fleet_refuse(f'{label}: unit definition is unparsable')
    if fragments == ['/dev/null'] and values.get('LoadState') == 'masked':
        return []
    items = []
    for fragment in filter(None, fragments):
        instance = name.split('@', 1)[1].rsplit('.', 1)[0] if '@' in name else None
        try:
            item = host_definition(ctx, fragment, working_directory=values.get('WorkingDirectory'),
                                   instance=instance or None, manager=manager.flags[0][2:],
                                   user_home=manager.home, verify_paths=True)
        except ValueError:
            fleet_refuse(f'{label}: unit definition is unparsable')
        except OSError as error:
            fleet_refuse(f'{label}: unit fragment is unreadable ({type(error).__name__})')
        items.append((Path(fragment), item))
    if not items and values.get('LoadState') != 'not-found':
        fleet_refuse(f'{label}: no readable unit fragment')
    return items


def fleet_owned_fragment(path, uid):
    info = checked_path(path, 'unit fragment').stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid not in {0, uid, os.getuid()} or info.st_mode & 0o022):
        fleet_refuse(f'unit fragment ownership is unverified: {path}')
    return (path, info.st_dev, info.st_ino, info.st_uid, info.st_mode, bounded_bytes(path))


def fleet_exec(values, prop='ExecStart'):
    return tuple(re.findall(r'\{ path=([^;]+?) ; argv\[\]=(.*?) ;', values.get(prop, '')))


# Manager-reported values that carry every form of Orbi evidence fleet_service
# accepts: the orbi executable or module, the exporter, ORBI_CONFIG and the
# fragment/drop-in/checkout paths. Values are the manager's parsed result.
FLEET_CANDIDATE_PROPS = ('ExecStart', 'ExecStartPre', 'Environment', 'EnvironmentFiles', 'PassEnvironment',
                         'UnsetEnvironment', 'WorkingDirectory', 'FragmentPath', 'DropInPaths')


def fleet_candidate(values):
    """Only units the manager reports with Orbi evidence get strict fragment checks."""
    return any('orbi' in values.get(prop, '').lower() for prop in FLEET_CANDIDATE_PROPS)


def fleet_service(ctx, manager, name, values, fragments):
    label = f'{manager.name}:{name}'
    refs = {config for _, item in fragments for config in item['configs']}
    commands = fleet_exec(values)
    # systemctl prints service argv for humans, not as an escaped argv vector.
    if not (any(Path(exe).name == 'orbi' or '/orbi-exporter.py' in argv or ' -m orbi' in argv
                for exe, argv in commands) or any(item['orbi'] or item['referenced'] for _, item in fragments)):
        return None
    argv = shlex.split(commands[0][1]) if len(commands) == 1 else []
    command = host_orbi_command(argv)
    cwd = Path(values.get('WorkingDirectory', ''))
    exporter = (cwd.is_absolute() and len(argv) == 2 and Path(argv[0]).name.startswith('python')
                and Path(argv[1]) == cwd / '3rd/monitoring/prometheus/orbi-exporter.py')
    if not (exporter or command['orbi'] or any(item['orbi'] or item['referenced'] for _, item in fragments)):
        return None  # A similar basename without Orbi evidence is not ownership.
    if (not (command['runner'] or exporter) or any(
            re.search(r'^\s*ExecStart\s*=\s*[-:@]*[+!]', systemd_logical_lines(bounded_text(path)), re.M)
            for path, _ in fragments)):
        fleet_refuse(f'{label}: effective worker/exporter command is unverified; refusing Orbi subcommands')
    if exporter and not refs:
        refs.add(str(cwd / 'orbi.toml'))
    if (len(refs) != 1 or any(item['referenced'] and not item['configs'] for _, item in fragments)
            or any(path.suffix == '.conf' and not benign_vendor_dropin(path) for path, _ in fragments)):
        fleet_refuse(f'{label}: config binding or drop-in overrides are ambiguous')
    config = Path(next(iter(refs)))
    # A config parsed from the fragment is not evidence that the manager's
    # loaded ExecStart points at the same deployment.
    effective_env = [token.partition('=')[2] for token in shlex.split(values.get('Environment', ''))
                     if token.startswith('ORBI_CONFIG=')]
    for ref in [*command['configs'], *effective_env]:
        if ('%' in ref or '$' in ref or not ref or not cwd.is_absolute()
                or checked_path(cwd / ref, 'effective config') != config):
            fleet_refuse(f'{label}: effective worker config disagrees with its unit fragment')
    if (any(token.partition('=')[0] == 'ORBI_CONFIG' for prop in ('PassEnvironment', 'UnsetEnvironment')
            for token in shlex.split(values.get(prop, '')))
            or any(values.get(prop) for prop in ('ExecCondition', 'ExecStartPost', 'ExecStop', 'ExecStopPost'))):
        fleet_refuse(f'{label}: unverified config environment or lifecycle hooks')
    user = values.get('User', '')
    expected_uid = manager.uid
    if manager.name == 'system' and user:
        import pwd
        try:
            expected_uid = int(user) if user.isdecimal() else pwd.getpwnam(user).pw_uid
        except KeyError:
            fleet_refuse(f'{label}: unverified service user')
    if expected_uid != os.getuid() or values.get('DynamicUser') != 'no' or (user and manager.name != 'system'):
        fleet_refuse(f'{label}: engine execution and file owner must match the installing account')
    file_identity(config)
    target = deployment_from(config)
    if cwd != target.deploy_home:
        fleet_refuse(f'{label}: working directory does not match deployment checkout')
    if exporter:
        file_identity(argv[1])
        if not Path(argv[1]).is_file():
            fleet_refuse(f'{label}: deployment exporter is missing')
    elif Path(commands[0][0]) != home_dir(ctx) / '.local/bin/orbi':
        fleet_refuse(f'{label}: executable is not the verified deployment bootstrap')
    env_files = values.get('EnvironmentFiles', '')
    if env_files and not re.fullmatch(re.escape(str(target.env_path)) + r' \(ignore_errors=(?:yes|no)\)', env_files):
        fleet_refuse(f'{label}: unverified service environment file')
    env_config = persisted_env(target).get('ORBI_CONFIG') if env_files else None
    if env_config is not None and env_config != str(config):
        fleet_refuse(f'{label}: the deployment env overrides its config binding')
    # Without an explicit config, an ambient service-manager environment could
    # redirect a bare worker to a different checkout.
    if command['runner'] and not (command['configs'] or effective_env or env_config):
        fleet_refuse(f'{label}: no effective worker config binding')
    if values.get('ExecStartPre'):
        # Native templates run bounded bootstrap/source checks before the tick.
        # Do not activate arbitrary local hooks (including an unrelated unit
        # start) just because the main command is a bound Orbi worker.
        pattern = r'^[ \t]*ExecStartPre[ \t]*=(.*)$'
        fragment_hooks = re.findall(pattern, bounded_text(fragments[0][0]), re.M)
        if not command['runner'] or not fragment_hooks:
            fleet_refuse(f'{label}: unverified ExecStartPre hooks')
        native = ctx.run(['git', '-C', target.deploy_home, 'show', 'HEAD:systemd/orbi@.service'],
                         allow_failure=True)
        native_hooks = re.findall(pattern, native.stdout.replace('{{ORBI_REPO_DIR}}', str(cwd)), re.M)
        if native.returncode or fragment_hooks != native_hooks or len(fleet_exec(values, 'ExecStartPre')) != len(native_hooks):
            fleet_refuse(f'{label}: ExecStartPre differs from the pinned engine template')
    return target, command['runner']


@dataclasses.dataclass(frozen=True)
class FleetUnit:
    manager: FleetManager
    name: str
    config: Path
    binding: tuple
    active: str
    enabled: str
    triggers: str = ''
    runner: bool = False
    service_type: str = ''
    triggered_by: frozenset = frozenset()

    @property
    def label(self):
        return f'{self.manager.name}:{self.name}'


def fleet_bound_unit(manager, name, target, values, fragments, *, triggers='', runner=False):
    label = f'{manager.name}:{name}'
    if (values['Id'] != name or values['LoadState'] != 'loaded' or values.get('NeedDaemonReload') != 'no'
            or values.get('ActiveState') not in DRAIN_STATES | INACTIVE_STATES
            or values.get('CanStart') != 'yes' or values.get('CanStop') != 'yes'):
        fleet_refuse(f'{label}: loaded unit identity/state cannot be verified; inspect daemon reload and unit state')
    if any(values.get(prop) for prop in ('PartOf', 'ConsistsOf', 'BoundBy', 'RequiredBy', 'PropagatesStopTo',
                                         'OnFailure', 'OnSuccess', 'Upholds', 'UpheldBy')):
        fleet_refuse(f'{label}: unit lifecycle could affect other units')
    # systemctl quotes escaped names, e.g. "app-orbi\x2dname.slice".
    try:
        dependencies = set(shlex.split(' '.join(values.get(prop, '') for prop in ('Requires', 'Requisite', 'Wants', 'BindsTo'))))
        conflicts = set(shlex.split(values.get('Conflicts', '') + ' ' + values.get('ConflictedBy', '')))
    except ValueError:
        fleet_refuse(f'{label}: unit dependencies are unreadable')
    default_targets = {'basic.target', 'sysinit.target', 'network-online.target', 'timers.target'}
    if (any(dep not in default_targets and not dep.endswith('.slice') for dep in dependencies)
            or conflicts - {'shutdown.target'}):
        fleet_refuse(f'{label}: start could affect unrelated units through dependencies')
    if name.endswith('.service') and (values.get('KillMode') not in {'control-group', 'mixed'}
                                      or values.get('SendSIGKILL') != 'yes'):
        fleet_refuse(f'{label}: service manager cannot verify a full worker stop')
    if name.endswith('.timer'):
        if values.get('UnitFileState') not in {'enabled', 'enabled-runtime', 'disabled'} or len(fragments) != 1:
            fleet_refuse(f'{label}: timer enablement or fragment binding is unverified')
        definition = bounded_text(fragments[0][0])
        install_targets = {target for line in re.findall(r'^[ \t]*WantedBy[ \t]*=(.*)$', definition, re.M)
                           for target in shlex.split(line)}
        if (values.get('Names', '').split() != [name] or set(values.get('WantedBy', '').split()) - {'timers.target'}
                or install_targets != {'timers.target'}
                or re.search(r'^\s*(Also|Alias|RequiredBy|UpheldBy)\s*=', definition, re.M)):
            fleet_refuse(f'{label}: timer enable/disable may change other unit bindings')
    def bound_value(prop):
        # A daemon reload (for example, from disabling a timer) may reorder
        # dependency lists; their membership, not their order, is the binding.
        value = values.get(prop)
        if prop in FLEET_UNIT_LIST_PROPS and value is not None:
            try:
                return tuple(sorted(set(shlex.split(value))))
            except ValueError:
                fleet_refuse(f'{label}: unit dependencies are unreadable')
        return value

    binding = (tuple(fleet_owned_fragment(path, manager.uid) for path, _ in fragments),
               tuple(bound_value(prop) for prop in FLEET_UNIT_PROPS if prop not in {
                   'ActiveState', 'SubState', 'UnitFileState', 'Result', 'ExecMainStartTimestampMonotonic',
                   'ExecMainStatus', 'ConditionResult', 'Names', 'TriggeredBy', 'WantedBy', 'ExecStart', 'ExecStartPre'}))
    # Execution status fields change when a service stops. Keep just the executable/argv.
    binding += (fleet_exec(values), fleet_exec(values, 'ExecStartPre')),
    return FleetUnit(manager, name, target, binding, values['ActiveState'], values.get('UnitFileState', ''),
                     triggers, runner, values.get('Type', ''), frozenset(values.get('TriggeredBy', '').split()))


def fleet_inventory(ctx, managers, *, known_units=()):
    units, targets, jobs = [], {}, {}
    for manager in managers:
        loaded = fleet_listing(ctx, manager, 'list-units')
        installed = fleet_listing(ctx, manager, 'list-unit-files')
        pending = fleet_jobs(ctx, manager)
        jobs[manager] = pending
        names = (installed | loaded | {name for name, _ in pending.values() if name.endswith(('.service', '.timer'))}
                 | {unit.name for unit in known_units if unit.manager == manager})
        if len(names) > FLEET_CLASSIFY_LIMIT:
            fleet_refuse(f'{manager.name}: installed/loaded units exceed {FLEET_CLASSIFY_LIMIT}')
        templates = {name for name in names if '@.' in name}
        names -= templates
        # A disabled configured timer instance may be absent from both lists.
        # Discover installable instances from the actual installed templates.
        if templates:
            search = shlex.split(manager.call(ctx, 'show', '-p', 'UnitPath', '--value'))
            if not search or any(not Path(path).is_absolute() for path in search):
                fleet_refuse(f'{manager.name}: installed template search path is unverified')
            def template_path(template):
                for folder in search:
                    path = Path(folder) / template
                    try:
                        mode = path.stat().st_mode
                    except FileNotFoundError:
                        continue
                    if path.resolve() == Path('/dev/null'):
                        return None  # masked at the highest-priority path
                    if stat.S_ISREG(mode):
                        return path
                    fleet_refuse(f'{manager.name}:{template}: installed template is not a regular file')
                fleet_refuse(f'{manager.name}:{template}: installed template not found')

            for template in sorted(t for t in templates if t.endswith('.service')):
                path = template_path(template)
                if path is None:
                    continue
                try:
                    definition = bounded_text(path)
                    if 'orbi' not in definition.lower():
                        continue
                    item = host_definition(ctx, path, instance='1', manager=manager.flags[0][2:],
                                           user_home=manager.home, verify_paths=True, text=definition)
                except ValueError:
                    fleet_refuse(f'{manager.name}:{template}: unit definition is unparsable')
                if not (item['orbi'] or item['referenced']):
                    continue
                if len(item['configs']) != 1:
                    fleet_refuse(f'{manager.name}:{template}: unverified template config')
                target = deployment_from(item['configs'][0])
                if target.max_concurrency > HOST_DETAIL_LIMIT:
                    fleet_refuse(f'{manager.name}:{template}: configured slots exceed inventory limit')
                for index in range(1, target.max_concurrency + 1):
                    names.add(template.replace('@.', f'@{index}.'))
            # Infer an unloaded timer instance only from an explicit one-to-one
            # template binding (or the same-name default). A fixed Unit= does
            # not configure a timer instance for every unrelated worker slot.
            service_instances = {name for name in names if '@' in name and name.endswith('.service')}
            for template in sorted(t for t in templates if t.endswith('.timer')):
                path = template_path(template)
                if path is None:
                    continue
                definition = bounded_text(path)
                target_units = re.findall(r'^[ \t]*Unit[ \t]*=[ \t]*(\S+)[ \t]*$', definition, re.M)
                default_instances = re.findall(r'^[ \t]*DefaultInstance[ \t]*=[ \t]*(\S+)[ \t]*$', definition, re.M)
                if len(default_instances) == 1:
                    names.add(template.replace('@.', f'@{default_instances[0]}.'))
                if len(target_units) > 1:
                    continue  # concrete installed/loaded instances still use the effective manager binding
                service_pattern = target_units[0] if target_units else template.removesuffix('.timer') + '%i.service'
                if not re.fullmatch(r'[A-Za-z0-9_.:\\-]+@%i\.service', service_pattern):
                    continue
                prefix = service_pattern.split('%i')[0]
                for name in service_instances:
                    if name.startswith(prefix):
                        slot = name[len(prefix):-len('.service')]
                        names.add(template.replace('@.', f'@{slot}.'))
                if len(names) > FLEET_CLASSIFY_LIMIT:
                    fleet_refuse(f'{manager.name}: configured units exceed {FLEET_CLASSIFY_LIMIT}')
        if len(names) > FLEET_CLASSIFY_LIMIT:
            fleet_refuse(f'{manager.name}: configured units exceed {FLEET_CLASSIFY_LIMIT}')
        services, timers, triggered_by = {}, {}, {}
        for name in sorted(names):
            values = fleet_unit(ctx, manager, name)
            if name.endswith('.timer'):
                timers[name] = values
                continue
            if not fleet_candidate(values):
                continue  # Unrelated unit: never parse or refuse on its fragments.
            fragments = fleet_fragments(ctx, manager, name, values)
            service = fleet_service(ctx, manager, name, values, fragments)
            if service is None:
                continue
            target, runner = service
            targets[target.config_path] = target
            unit = fleet_bound_unit(manager, values['Id'], target.config_path, values, fragments, runner=runner)
            services[unit.name] = unit  # canonical Id, not an alias
            triggered_by[unit.name] = values.get('TriggeredBy', '').split()
            if len(services) > HOST_DETAIL_LIMIT:
                fleet_refuse(f'{manager.name}: Orbi unit detail exceeds {HOST_DETAIL_LIMIT}')
        bound_timers = {}
        for name, values in timers.items():
            service = values.get('Unit') or values.get('Triggers')
            if service not in services:
                continue
            fragments = fleet_fragments(ctx, manager, name, values)
            unit = fleet_bound_unit(manager, values['Id'], services[service].config, values, fragments, triggers=service)
            bound_timers[unit.name] = unit
            if len(services) + len(bound_timers) > HOST_DETAIL_LIMIT:
                fleet_refuse(f'{manager.name}: Orbi unit detail exceeds {HOST_DETAIL_LIMIT}')
        for service in services.values():
            if any(name not in bound_timers or bound_timers[name].triggers != service.name
                   for name in triggered_by[service.name]):
                fleet_refuse(f'{service.label}: service has an unverified scheduler trigger')
        units.extend([*services.values(), *bound_timers.values()])
    return tuple(units), targets, jobs


def fleet_recheck_key(units, targets, jobs):
    """What must not change between the frozen plan and the first stop.

    The stop phase re-reads live jobs and worker states, and cancels or stops
    only Orbi units. Unrelated units' jobs and the activity of a oneshot service
    or a timer-started worker are therefore not plan changes. Activity of timers and persistent
    services decides what is restored, and system-manager Orbi jobs decide the
    cancel permission checked before the plan, so those stay compared.
    """
    names = {(unit.manager, unit.name) for unit in units}
    # A timer worker's restore uses the live interruption seen while stopping.
    worker_timers = {(unit.manager, unit.triggers) for unit in units if unit.triggers}

    def transient(unit):
        return not unit.triggers and (unit.service_type == 'oneshot'
                                      or ((unit.manager, unit.name) in worker_timers and unit.runner))

    return (
        tuple(dataclasses.replace(unit, active='') if transient(unit) else unit for unit in units),
        targets,
        {manager: {job: entry for job, entry in pending.items()
                   if manager.name == 'system' and (manager, entry[0]) in names}
         for manager, pending in jobs.items()},
    )


def fleet_check_permissions(ctx, units, jobs):
    user_timers = [unit for unit in units if unit.manager.flags == ('--user',) and unit.triggers]
    if user_timers:
        # Bus access allows the caller to start/stop in their own manager,
        # but enable/disable also need writable unit-file configuration.
        manager = user_timers[0].manager
        paths = set(shlex.split(manager.call(ctx, 'show', '-p', 'UnitPath', '--value')))
        config = config_home(ctx) / 'systemd/user'
        runtime = Path(f'/run/user/{manager.uid}/systemd/user')
        for directory in {runtime if unit.enabled == 'enabled-runtime' else config for unit in user_timers}:
            if str(directory) not in paths:
                fleet_refuse(f'{manager.name}: cannot verify enablement directory {directory} in the manager unit path')
            links = checked_path(directory / 'timers.target.wants', 'user manager enablement directory')
            parent = next(path for path in (links, *links.parents) if path.exists())
            if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
                fleet_refuse(f'{manager.name}: enablement directory is not writable: {parent}')
    systems = [unit for unit in units if unit.manager.name == 'system']
    if not systems or os.geteuid() == 0:
        return
    actions = set()
    if any(unit.triggers for unit in systems):
        actions.update({('manage-unit-files',), ('reload-daemon',)})
    system_names = {unit.name for unit in systems}
    if (any(unit.triggers for unit in systems) or
            any(name in system_names and verb in START_JOB_TYPES
                for name, verb in jobs[systems[0].manager].values())):
        actions.add(('manage-units',))  # CancelJob uses generic manage-units authorization.
    for unit in systems:
        actions.update(('manage-units', '--detail', 'unit', unit.name, '--detail', 'verb', verb)
                       for verb in ('start', 'stop'))
    # /proc stat field 22 is the start time; field 2 (comm) is parenthesized
    # and may contain spaces or parentheses. Bind the polkit subject to all
    # three identifiers instead of a bare, reusable process ID.
    start_time = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]
    subject = f'{os.getpid()},{start_time},{os.getuid()}'
    env = {key: value for key, value in ctx.env.items() if not key.startswith('DBUS_')}
    for action, *details in sorted(actions):
        proc = ctx.run(['pkcheck', '--action-id', 'org.freedesktop.systemd1.' + action,
                        '--process', subject, *details], env=env, allow_failure=True)
        if proc.returncode:
            fleet_refuse('system: noninteractive write access denied for ' + ' '.join((action, *details)))


def official_latest_release(ctx):
    # Resolve official tags independently of checkout Git config and URL rewrites.
    env = {key: value for key, value in ctx.env.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0')
    refs = ctx.run(['git', 'ls-remote', '--tags', OFFICIAL_ORIGIN, 'refs/tags/v*'], cwd='/', env=env).stdout
    tags = {}
    for line in refs.splitlines():
        match = re.fullmatch(r'([0-9a-f]{40})\trefs/tags/(v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\+[a-zA-Z0-9.-]+)?)(\^\{\})?', line)
        if match:
            head, tag, major, minor, patch, peeled = match.groups()
            tags.setdefault((int(major), int(minor), int(patch)), {})[tag, bool(peeled)] = head
    if not tags:
        raise ControlError('release_unverified', 'cannot resolve an official stable Orbi release')
    latest = tags[max(tags)]
    names = {tag for tag, _ in latest}
    if len(names) != 1:
        raise ControlError('release_unverified', 'latest official release tag is ambiguous')
    tag = next(iter(names))
    if '+' in tag:
        raise ControlError('release_unverified',
                           f'{tag}: newest official stable tag is not supported by the engine tag selector')
    return tag, latest.get((tag, True)) or latest[tag, False]


def require_engine_checkout(ctx, target, *, source_repo):
    def refuse(message):
        raise ControlError('source_unavailable', message,
                           fix='verify deploy_home names the separate deployment checkout and '
                               'remove Git checkout redirects before retrying', exit_code=2)

    # `git -C` by itself can discover the parent repository or operate on a
    # different worktree via ambient or deployment-persisted Git overrides.
    local_keys = set(ctx.run(['git', 'rev-parse', '--local-env-vars']).stdout.splitlines())
    if not {'GIT_DIR', 'GIT_WORK_TREE'} <= local_keys:
        refuse('cannot verify Git checkout-local environment keys')
    if local_keys & (ctx.env.keys() | persisted_env(target).keys()):
        refuse(f'{target.config_path}: Git environment redirects checkout state')
    root = ctx.run(['git', '-C', target.deploy_home, 'rev-parse', '--show-toplevel']).stdout.strip()
    if root != str(target.deploy_home):
        refuse(f'{target.deploy_home}: engine directory is not its own Git checkout root')
    if target.deploy_home == source_repo:
        refuse(f'{target.deploy_home}: engine checkout must be separate from the source repository')
    git_dir = Path(ctx.run(['git', '-C', target.deploy_home, 'rev-parse',
                            '--path-format=absolute', '--git-common-dir']).stdout.strip())
    if (not git_dir.is_absolute() or not checked_path(git_dir, 'engine Git directory').resolve().is_relative_to(target.deploy_home)
            or not git_dir.is_dir()):
        refuse(f'{target.deploy_home}: Git state is not contained in the engine checkout')
    file_identity(git_dir)


def fleet_preflight_target(ctx, target):
    validate_deployment_paths(target)
    identities = setup_file_identities(target)
    if len(target.source_repos) != 1 or not target.deploy_home.is_dir():
        fleet_refuse(f'{target.config_path}: deployment identity is unverified')
    require_engine_checkout(ctx, target, source_repo=target.repo_dir)
    if target.repo_dir is not None:
        repo = repo_identity(ctx, target.repo_dir)
        validate_target(target, repo)
    remote = ctx.run(['git', '-C', target.deploy_home, 'remote', 'get-url', 'origin']).stdout.strip()
    if remote not in OFFICIAL_ORIGINS:
        fleet_refuse(f'{target.deploy_home}: engine origin is not official')
    if not os.access(target.config_path.parent, os.W_OK) or not os.access(target.deploy_home, os.W_OK):
        fleet_refuse(f'{target.config_path}: deployment files are not writable')
    # Test the exact rewrite without touching the config.
    engine_track_replacement(target.config_path, 'tag:installer-preflight')
    source = require_source(ctx, target)
    if source['state'] != 'verified' or not re.fullmatch(r'[0-9a-f]{40}', source['head']):
        fleet_refuse(f'{target.config_path}: current engine is not pinned to its exact checkout commit')
    require_clean_checkout(ctx, target)
    require_harness(ctx, target)
    bootstrap = fleet_bootstrap_identity(ctx)
    state, _ = bootstrap_evidence(ctx, target)
    if state != 'compatible':
        fleet_refuse(f'{target.config_path}: deployment bootstrap is {state}')
    run_orbi_check(ctx, target)
    return identities, source['head'], bootstrap


def fleet_bootstrap_identity(ctx):
    path = home_dir(ctx) / '.local/bin/orbi'
    if not path.is_file():
        fleet_refuse(f'{path}: deployment bootstrap is missing or unverified')
    return fleet_owned_fragment(path.resolve(strict=True), os.getuid())


def fleet_verify_units(ctx, units, *, idle=False):
    states = {}
    for unit in units:
        values = fleet_unit(ctx, unit.manager, unit.name)
        fragments = fleet_fragments(ctx, unit.manager, unit.name, values)
        observed = fleet_bound_unit(unit.manager, unit.name, unit.config, values, fragments)
        if observed.binding != unit.binding or observed.triggered_by - unit.triggered_by:
            fleet_refuse(f'{unit.label}: unit identity or scheduler changed after preflight')
        states[unit.label] = observed.active
        if idle and (observed.active not in INACTIVE_STATES or (unit.triggers and observed.enabled != 'disabled')):
            fleet_refuse(f'{unit.label}: unit did not quiesce')
    return states


def fleet_no_jobs(ctx, units):
    for manager in {unit.manager for unit in units}:
        names = {unit.name for unit in units if unit.manager == manager}
        if any(name in names for name, _ in fleet_jobs(ctx, manager).values()):
            fleet_refuse(f'{manager.name}: owned units still have pending jobs')


def installer_fleet(ctx, *, report_progress=None):
    """Return a receipt even on partial failure; do not auto-retry or roll back."""
    receipt = {'status': 'no_deployments', 'deployments': []}
    rows, current = {}, {}

    def report_stage():
        if report_progress is not None:
            report_progress({**receipt, 'progress_only': True,
                             'error': {**current, 'message': 'fleet refresh did not return a terminal receipt'},
                             'recovery': 'The last request may have taken effect. Inspect the named units and configs; no rollback was attempted.'})

    try:
        if ctx.platform != 'linux':
            coverage = {'state': 'ok', 'managers': {}, 'problems': []}
            if ctx.platform != 'darwin':
                fleet_refuse(f'{ctx.platform}: no supported Orbi deployment manager')
            units, configs = host_darwin(ctx, coverage)
            if units or configs or coverage['problems']:
                subject = (str(min(configs)) if configs else units[0]['unit'] if units
                           else coverage['problems'][0]['reason'])
                fleet_refuse(f'macOS: deployment coverage or launchd mutation unsupported ({subject}); '
                             'no deployment upgraded')
            return receipt
        manager_coverage = fleet_managers(ctx)
        managers, not_checked = manager_coverage
        if not_checked:
            receipt['not_checked'] = list(not_checked)
        units, targets, jobs = fleet_inventory(ctx, managers)
        coverage = {'state': 'ok', 'problems': []}
        configs = host_config_paths(ctx, coverage)
        if coverage['problems']:
            fleet_refuse(coverage['problems'][0]['reason'])
        for config in sorted(configs):
            if checked_path(config, 'deployment config').resolve() not in targets:
                fleet_refuse(f'{config}: configured deployment has no verified service binding')
        if not targets:
            return receipt
        for config, target in sorted(targets.items()):
            owned = tuple(unit for unit in units if unit.config == config)
            row = {'config': str(config), 'repo': target.source_repos[0], 'slots': target.max_concurrency,
                   'units': [unit.label for unit in owned], 'status': 'untouched', 'steps': [],
                   'before': [{'unit': unit.label, 'active': unit.active, 'enablement': unit.enabled,
                               'trigger': unit.triggers or None,
                               'jobs': [{'id': job, 'verb': verb} for job, (name, verb) in jobs[unit.manager].items()
                                        if name == unit.name]} for unit in owned],
                   'recovery': 'Inspect ' + shlex.quote(str(config)) + ' and the named manager/units before deliberate repair; '
                               'after repair, use ./install.sh --only orbi to re-evaluate the fleet. '
                               'If a previously active persistent service is now stopped, check its exact release pin and '
                               'run orbi check --config ' + shlex.quote(str(config)) +
                               ' before deliberately restoring that service through its named manager.'}
            rows[config] = row
            receipt['deployments'].append(row)
        if (len({target.deploy_home for target in targets.values()}) != len(targets)
                or len({target.source_repos[0].casefold() for target in targets.values()}) != len(targets)):
            fleet_refuse('multiple configs claim the same deployment checkout or repository')
        fragments = {}
        for unit in units:
            path = unit.binding[0][0][0]
            if fragments.setdefault((unit.manager, path), unit.config) != unit.config:
                fleet_refuse(f'{unit.label}: a shared fragment binds different deployment configs')
        worker_timers = {(unit.manager, unit.triggers) for unit in units if unit.triggers}
        scheduled = {unit.config for unit in units if unit.triggers}
        standalone = {unit.label for unit in units if not unit.triggers and unit.config not in scheduled
                      and '@' not in unit.name and unit.runner and unit.service_type != 'oneshot'}
        for config in targets:
            if config not in scheduled and not any(u.config == config and
                    (u.label in standalone or (u.active in ACTIVE_STATES and u.service_type != 'oneshot'))
                    for u in units):
                fleet_refuse(f'{config}: no verified scheduling or persistent worker to restore')
        fleet_check_permissions(ctx, units, jobs)
        tag, expected = official_latest_release(ctx)
        receipt['release'] = {'tag': tag, 'head': expected}

        def verify_head(head):
            if head != expected:
                fleet_refuse(f'synced HEAD does not match the verified official release {tag}')

        with contextlib.ExitStack() as locks:
            for config in sorted(targets):
                locks.enter_context(locked(ctx, config, nonblocking=True))
            before = {}
            for config, target in sorted(targets.items()):
                current = {'step': 'preflight_deployment', 'config': str(config)}
                before[config] = fleet_preflight_target(ctx, target)
            current = {}
            if (fleet_managers(ctx) != manager_coverage
                    or fleet_recheck_key(*fleet_inventory(ctx, managers)) != fleet_recheck_key(units, targets, jobs)):
                fleet_refuse('fleet inventory or jobs changed after preflight')
            for config, target in targets.items():
                if (setup_file_identities(target) != before[config][0]
                        or checkout_head(ctx, target) != before[config][1]
                        or fleet_bootstrap_identity(ctx) != before[config][2]):
                    fleet_refuse(f'{config}: deployment files changed after preflight')
                require_engine_checkout(ctx, target, source_repo=target.repo_dir)
                require_clean_checkout(ctx, target)
            receipt['status'] = 'incomplete'

            def action(unit, step, verb, *args):
                nonlocal current
                row = rows[unit.config]
                current = {'step': step, 'unit': unit.label}
                row['status'] = 'in_progress'
                report_stage()
                unit.manager.call(ctx, verb, *args)
                row['steps'].append({**current, 'status': 'ok'})
                current = {}
                report_stage()

            for unit in units:
                if not unit.triggers:
                    continue
                current = {'step': 'recheck_trigger', 'unit': unit.label}
                fleet_verify_units(ctx, (unit,))
                if unit.enabled != 'disabled':
                    action(unit, 'disable_trigger', 'disable',
                           *(['--runtime'] if unit.enabled == 'enabled-runtime' else []), unit.name)
                current = {'step': 'recheck_trigger_before_stop', 'unit': unit.label}
                if fleet_verify_units(ctx, (unit,))[unit.label] not in INACTIVE_STATES:
                    action(unit, 'stop_trigger', 'stop', unit.name)
            current = {'step': 'verify_triggers_quiescent'}
            fleet_verify_units(ctx, (u for u in units if u.triggers), idle=True)

            # Discover newly queued jobs after quiescing triggers, rather than
            # cancelling by an id from the frozen plan. Other units are untouched.
            interrupted, previously_active = set(), set()
            for manager in managers:
                for job, (name, verb) in fleet_jobs(ctx, manager).items():
                    unit = next((u for u in units if u.manager == manager and u.name == name), None)
                    if unit and verb in START_JOB_TYPES:
                        current = {'step': 'recheck_pending_start', 'unit': unit.label}
                        fleet_verify_units(ctx, (unit,))
                        if fleet_jobs(ctx, manager).get(job) != (name, verb):
                            fleet_refuse(f'{unit.label}: pending start changed before cancellation')
                        action(unit, 'cancel_start', 'cancel', job)
                        interrupted.add(unit.label)
            for unit in units:
                if unit.triggers:
                    continue
                current = {'step': 'recheck_service', 'unit': unit.label}
                active = fleet_verify_units(ctx, (unit,))[unit.label]
                if active in ACTIVE_STATES or unit.active in ACTIVE_STATES:
                    previously_active.add(unit.label)
                if active in DRAIN_STATES or unit.label in interrupted:
                    action(unit, 'stop_service', 'stop', unit.name)
                    interrupted.add(unit.label)
                elif unit.label in previously_active:
                    interrupted.add(unit.label)  # ran at entry but finished during trigger shutdown
            current = {'step': 'verify_fleet_quiescent'}
            if fleet_managers(ctx) != manager_coverage:
                fleet_refuse('local manager coverage changed while stopping')
            stopped, bound, _ = fleet_inventory(ctx, managers, known_units=units)
            if ([(u.manager, u.name, u.config, u.binding) for u in stopped] !=
                    [(u.manager, u.name, u.config, u.binding) for u in units] or bound != targets):
                fleet_refuse('fleet bindings changed while stopping')
            fleet_verify_units(ctx, units, idle=True)
            fleet_no_jobs(ctx, units)
            for row in rows.values():
                row['status'] = 'stopped'

            # Do not activate a deployment until its exact stable release is
            # pinned and check has passed. Stop on the first failure; later
            # deployments remain quiescent rather than resuming speculatively.
            for config, target in sorted(targets.items()):
                row = rows[config]
                owned = tuple(unit for unit in units if unit.config == config)
                current = {'step': 'recheck_before_update', 'config': str(config)}
                fleet_verify_units(ctx, owned, idle=True)
                fleet_no_jobs(ctx, owned)
                if (setup_file_identities(target) != before[config][0]
                        or checkout_head(ctx, target) != before[config][1]
                        or fleet_bootstrap_identity(ctx) != before[config][2]):
                    fleet_refuse(f'{config}: deployment changed while stopping')
                require_engine_checkout(ctx, target, source_repo=target.repo_dir)
                require_clean_checkout(ctx, target)
                progress = {}
                current['step'] = 'apply_release'
                report_stage()
                try:
                    target, head, identities = apply_release_locked(
                        ctx, target, lambda: deployment_from(config), row['steps'], current, progress,
                        source_track='tag:' + tag, verify_head=verify_head)
                finally:
                    row['engine_update'] = progress.get('engine_update', 'not_applied')
                row['engine_update'] = 'up_to_date' if head == before[config][1] else 'updated'
                row['status'] = 'validated'
                current = {'step': 'recheck_before_start', 'config': str(config)}
                report_stage()
                fleet_verify_units(ctx, owned, idle=True)
                fleet_no_jobs(ctx, owned)
                if (setup_file_identities(target) != identities or checkout_head(ctx, target) != head
                        or fleet_bootstrap_identity(ctx) != before[config][2]):
                    fleet_refuse(f'{config}: validated pin or file identity changed before activation')
                worker_requested = False
                for unit in sorted((u for u in owned if not u.triggers),
                                   key=lambda u: (u.label not in previously_active, u.label)):
                    timer_worker = (unit.manager, unit.name) in worker_timers and unit.runner
                    if timer_worker:
                        if unit.label not in interrupted or worker_requested:
                            continue
                    elif (unit.label not in standalone and
                          (unit.label not in previously_active or unit.service_type == 'oneshot')):
                        continue  # only restore persistent services outside the timer-worker path
                    current = {'step': 'recheck_service_before_start', 'unit': unit.label}
                    fleet_verify_units(ctx, (unit,), idle=True)
                    baseline = fleet_unit(ctx, unit.manager, unit.name).get('ExecMainStartTimestampMonotonic', '')
                    action(unit, 'start_service_requested', 'start', unit.name)
                    current = {'step': 'verify_service_start', 'unit': unit.label}
                    values = fleet_unit(ctx, unit.manager, unit.name)
                    timestamp = values.get('ExecMainStartTimestampMonotonic', '')
                    if (values.get('Result') != 'success' or values.get('ConditionResult') != 'yes'
                            or not baseline.isdecimal() or not timestamp.isdecimal() or int(timestamp) <= int(baseline)
                            or not (values['ActiveState'] == 'active' or
                                    (timer_worker or unit.service_type == 'oneshot') and
                                    values['ActiveState'] == 'inactive' and values.get('ExecMainStatus') == '0')):
                        fleet_refuse(f'{unit.label}: requested service start not verified')
                    row['steps'].append({**current, 'status': 'ok'})
                    worker_requested |= timer_worker
                for unit in (u for u in owned if u.triggers):
                    current = {'step': 'recheck_trigger_before_enable', 'unit': unit.label}
                    fleet_verify_units(ctx, (unit,))
                    action(unit, 'enable_trigger', 'enable',
                           *(['--runtime'] if unit.enabled == 'enabled-runtime' else []), unit.name)
                    # Enable may reload the manager. Bind the loaded timer again
                    # before issuing a start, rather than starting with enable --now.
                    current = {'step': 'recheck_trigger_before_start', 'unit': unit.label}
                    fleet_verify_units(ctx, (unit,))
                    action(unit, 'start_trigger_requested', 'start', unit.name)
                    current = {'step': 'verify_scheduling', 'unit': unit.label}
                    values = fleet_unit(ctx, unit.manager, unit.name)
                    if (values.get('ActiveState') != 'active' or values.get('SubState') not in {'waiting', 'running'}
                            or values.get('UnitFileState') not in {'enabled', 'enabled-runtime'}):
                        fleet_refuse(f'{unit.label}: timer not confirmed enabled and scheduling')
                    row['steps'].append({**current, 'status': 'ok'})
                if any(s['step'] in {'verify_service_start', 'verify_scheduling'} for s in row['steps']):
                    row['status'] = 'started'
                current = {}
        receipt['status'] = 'completed'
    except (ControlError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        if receipt['status'] != 'incomplete':
            receipt['status'] = 'held'
        message = error.message if isinstance(error, ControlError) else type(error).__name__
        if isinstance(error, OSError) and error.filename:
            message += f': {error.filename}'
        receipt['error'] = {**current, 'message': message}
        if isinstance(error, ControlError) and error.fix:
            receipt['error']['fix'] = error.fix
        for row in rows.values():
            if (current.get('config') == row['config'] or current.get('unit') in row['units']):
                row['failed_step'] = current.get('step', 'preflight')
                row['status'] = 'failed'
        receipt['recovery'] = ('Restore complete manager and deployment ownership/control evidence; '
                               'or use ./install.sh --skip orbi to leave the fleet untouched.' if receipt['status'] == 'held'
                               else 'Inspect the named manager, unit and config states before deliberate repair. No rollback attempted.')
    return receipt


def host_slot_issue(main, pid, repo_dir):
    """Read only a slot record locked by this service PID, not a stale file."""
    try:
        for fd in islice((main / 'fd').iterdir(), HOST_DETAIL_LIMIT):
            try:
                path = fd.readlink()
                if path.parent != repo_dir / '.orbi/slots' or not re.fullmatch(r'slot-[1-9][0-9]*', path.name):
                    continue
                lock = bounded_text(main / 'fdinfo' / fd.name, 4096)
                if not re.search(rf'^lock:\s+[0-9]+: FLOCK\s+ADVISORY\s+WRITE\s+{pid}\s', lock, re.M):
                    continue
                owner, _, identity = bounded_text(fd, 1024).partition('\n')
                if owner == pid:
                    return identity.strip()
            except (OSError, ValueError):
                continue  # descriptors can close or become unreadable during inspection
    except OSError:
        pass
    return ''


def host_worktree_branches(ctx, repo_dir, group, pid):
    """Only worktrees in use by processes of this unit are candidate evidence."""
    try:
        pids = bounded_text(HOST_CGROUP / group.relative_to('/') / 'cgroup.procs', 4096).splitlines()
    except (OSError, ValueError):
        return set()
    if pid not in pids:
        return set()
    root = repo_dir / '.worktrees'
    worktrees = set()
    for child in pids:
        if not re.fullmatch(r'[1-9][0-9]*', child):
            continue
        try:
            parts = (HOST_PROC / child / 'cwd').readlink().relative_to(root).parts
            if parts:
                worktree = root / parts[0]
                if (worktree / '.git').is_file():
                    worktrees.add(worktree)
        except (OSError, ValueError):
            continue
    branches = set()
    for worktree in sorted(worktrees)[:HOST_DETAIL_LIMIT]:
        try:
            proc = ctx.run(['git', '-C', str(worktree), 'symbolic-ref', '--quiet', 'HEAD'],
                           env={k: v for k, v in ctx.env.items() if not k.startswith('GIT_')}, allow_failure=True)
        except (ControlError, OSError, UnicodeError):
            continue
        if not proc.returncode and len(proc.stdout) <= 1024 and proc.stdout.startswith('refs/heads/'):
            branches.add(proc.stdout.removeprefix('refs/heads/').rstrip('\n'))
    return branches


def host_worker_issue(ctx, row, target, binding):
    pid = binding.get('MainPID', '')
    invocation = binding.get('InvocationID', '')
    if not re.fullmatch(r'[1-9][0-9]*', pid) or not re.fullmatch(r'[0-9a-f]{32}', invocation):
        return None
    repo_dir = target.repo_dir or target.config_path.parent
    slot = host_slot_issue(HOST_PROC / pid, pid, repo_dir)
    identities = [(repo, m[1]) for repo in target.source_repos
                  if (m := re.fullmatch(re.escape(repo) + r'#([1-9][0-9]{0,19})', slot))]
    provenance = 'current service PID + locked Orbi slot'
    if not identities:
        group = Path(binding.get('ControlGroup', ''))
        if not group.is_absolute() or '..' in group.parts or group.name != row['unit']:
            return None
        branches = host_worktree_branches(ctx, repo_dir, group, pid)
        identities = [(repo, m[1]) for repo in target.source_repos for branch in branches
                      if (m := re.fullmatch(re.escape(f"orbi/{repo.replace('/', '-')}-issue-")
                                            + r'([1-9][0-9]{0,19})', branch))]
        provenance = 'current service cgroup + Orbi worktree branch'
    if len(identities) != 1:
        return None
    try:
        current = service_binding(ctx, row['unit'], row['manager'])
    except (ControlError, OSError, UnicodeError):
        return None
    if (current.get('ActiveState') != 'active'
            or any(current.get(key) != binding.get(key) for key in
                   ('MainPID', 'InvocationID', 'WorkingDirectory', 'FragmentPath'))):
        return None
    repo, number = identities[0]
    return {'state': 'running', 'issue': {'number': int(number),
            'url': f'https://github.com/{repo}/issues/{number}'}, 'provenance': provenance}


def prune_settings(raw, section, keys):
    """Accept simple generated directives, not ambiguous systemd quoting or continuations."""
    current, values = None, {key: [] for key in keys}
    for line in raw.decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.endswith('\\'):
            raise ValueError('continued directive')
        if line.startswith('['):
            current = line
        elif current == section:
            key, sep, value = line.partition('=')
            if sep and key.strip() in values:
                if '\\' in value:
                    raise ValueError('escaped directive')
                values[key.strip()].append(value.strip())
    return values


def prune_config_path(ctx, value):
    path = Path(value.replace('%h', str(home_dir(ctx))))
    if not path.is_absolute() or '%' in str(path) or '$' in str(path):
        raise ValueError('unverified config path')
    return checked_path(path, 'prune config').resolve()


def prune_candidate(ctx, service):
    """Use an explicit generated service binding, not its name or a pin mismatch."""
    prefix = service.name.removesuffix('@.service')
    timer = service.with_suffix('.timer')
    try:
        identities = []
        for path in (service, timer):
            checked_path(path, 'prune unit')
            try:
                info = path.stat()
            except FileNotFoundError:
                if path == timer:
                    continue
                return None
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o022):
                return None
            identities.append((path, info.st_dev, info.st_ino, bounded_bytes(path)))
        raw = identities[0][-1]
        settings = prune_settings(raw, '[Service]', ('ExecStart', 'Environment', 'EnvironmentFile',
                                                     'PassEnvironment', 'UnsetEnvironment'))
        if len(settings['ExecStart']) != 1 or '' in settings['Environment']:
            return None
        command = host_orbi_command(shlex.split(settings['ExecStart'][0]))
        if not command['runner']:
            return None
        refs = {prune_config_path(ctx, value) for value in command['configs']}
        refs.update(prune_config_path(ctx, token.partition('=')[2])
                    for raw_env in settings['Environment'] for token in shlex.split(raw_env)
                    if token.startswith('ORBI_CONFIG='))
        if len(refs) != 1 or any('ORBI_CONFIG' in raw_env for raw_env in
                                 settings['PassEnvironment'] + settings['UnsetEnvironment']):
            return None
        config, = refs
        for item in identities:
            install = prune_settings(item[-1], '[Install]', ('Alias', 'Also'))
            if install['Alias'] or install['Also']:
                return None
        if len(identities) == 2:
            targets = prune_settings(identities[1][-1], '[Timer]', ('Unit',))['Unit']
            if targets and targets != [prefix + '@%i.service']:
                return None
        for raw_env in settings['EnvironmentFile']:
            values = shlex.split(raw_env)
            if len(values) != 1 or re.search(r'[*?\[\]]', values[0]):
                return None
            value, = values
            env_file = prune_config_path(ctx, value.removeprefix('-'))
            try:
                if 'ORBI_CONFIG' in bounded_text(env_file):
                    return None  # The apparent config may not be the one this unit uses.
            except FileNotFoundError:
                if not value.startswith('-'):
                    return None
        try:
            mode = checked_path(config, 'prune config').stat().st_mode
        except FileNotFoundError:
            return ({'prefix': prefix, 'config': str(config), 'reason': 'config_missing',
                     'units': [str(item[0]) for item in identities]}, None, identities)
        if not stat.S_ISREG(mode):
            return None
        target = deployment_from(config, tomllib.loads(bounded_text(config)))
        if target.prefix != prefix or target.repo_dir is None or len(target.source_repos) != 1:
            return None
        try:
            target.repo_dir.stat()
        except FileNotFoundError:
            return ({'prefix': prefix, 'config': str(config), 'reason': 'repo_missing',
                     'units': [str(item[0]) for item in identities]}, target, identities)
    except (ControlError, OSError, ValueError, RuntimeError):
        pass  # No positive stale/ownership evidence: leave the files alone.
    return None


def prune_has_overrides(ctx, template):
    """Check the manager's actual search paths for systemd drop-ins."""
    try:
        proc = ctx.run(['systemctl', '--user', 'show', '-p', 'UnitPath', '--value'], allow_failure=True)
        search = [Path(path) for path in shlex.split(proc.stdout)]
        if proc.returncode or not search or any(not path.is_absolute() for path in search):
            raise ValueError('missing unit search path')
        for suffix in ('.service', '.timer'):
            prefix = template.name.removesuffix('@.service')
            dropins = [prefix + '@' + suffix + '.d', suffix[1:] + '.d']
            dropins.extend(prefix[:index + 1] + suffix + '.d'
                           for index, char in enumerate(prefix) if char == '-')
            for folder in {template.parent, *search}:
                for name in dropins:
                    try:
                        (folder / name).lstat()
                    except FileNotFoundError:
                        continue
                    return True
    except (OSError, ValueError) as exc:
        raise ControlError('scheduler_unavailable', 'cannot verify user unit search paths or overrides',
                           fix='restore systemctl --user UnitPath and read access before retrying prune') from exc
    return False


def prune_has_instances(ctx, prefix):
    """Do not probe names with `show`: that can load an otherwise unloaded unit."""
    if any(name.startswith(prefix + '@') for name, _ in scheduler_jobs(ctx).values()):
        return True
    for command in ('list-unit-files', 'list-units'):
        argv = ['systemctl', '--user', command, '--no-legend', '--no-pager', '--full', '--all']
        if command == 'list-units':
            argv.extend(('--plain', prefix + '@*'))
        else:
            # A pattern with no installed match can return nonzero; use the
            # full typed inventory to distinguish absence from a failed read.
            argv.append('--type=service,timer')
        proc = ctx.run(argv, allow_failure=True)
        if proc.returncode or len(proc.stdout) > 4 * 1024 * 1024:
            raise ControlError('scheduler_unavailable', f'cannot read scheduler {command}',
                               fix='restore complete systemd user-session inventory before retrying prune')
        for line in proc.stdout.splitlines():
            fields = line.split()
            if not fields:
                continue
            unit = fields[0]
            if len(fields) < (4 if command == 'list-units' else 2) or not FLEET_UNIT_NAME.fullmatch(unit):
                raise ControlError('scheduler_unavailable', f'invalid scheduler {command} inventory',
                                   fix='restore complete systemd user-session inventory before retrying prune')
            if unit.startswith(prefix + '@') and (command == 'list-units'
                    or unit not in {prefix + '@.timer', prefix + '@.service'}):
                return True
    return False


def command_prune(ctx, args):
    candidates, removed, audit = [], [], set()
    error = None
    try:
        folder = checked_path(user_unit_dir(ctx), 'user unit directory')
        try:
            files = sorted(folder.iterdir())
        except FileNotFoundError:
            files = []
        for service in files:
            if not re.fullmatch(r'orbi(?:-[a-zA-Z0-9_.-]+)?@\.service', service.name):
                continue
            entry = prune_candidate(ctx, service)
            if (entry is not None and not prune_has_overrides(ctx, service)
                    and not prune_has_instances(ctx, entry[0]['prefix'])):
                candidates.append(entry)
        if args.apply:
            for entry in candidates:
                row, target, identities = entry
                service = identities[0][0]
                with locked(ctx, row['config'], nonblocking=True):
                    if (prune_has_overrides(ctx, service)
                            or prune_candidate(ctx, service) != entry
                            or prune_has_instances(ctx, row['prefix'])):
                        raise ControlError('prune_target_changed', f"prune target changed: {row['prefix']}",
                                           fix='inspect the deployment and rerun /orbi prune without --apply')
                    if target:
                        audit.add(target.deploy_home)
                    # There is no concrete unit to stop. Stopping a template
                    # is invalid and stopping an instance could interrupt work.
                    for path, *_ in reversed(identities):
                        path.unlink()
                        removed.append(str(path))
    except ControlError as exc:
        error = exc
    except UnicodeError:
        error = ControlError('scheduler_unavailable', 'cannot decode the user manager inventory',
                             fix='restore readable systemd user-session inventory before retrying prune')
    except OSError:
        error = ControlError('filesystem_error', 'could not read or remove a user unit template',
                             fix='inspect user unit-directory access and rerun /orbi prune without --apply')
    if removed:
        try:
            ctx.run(['systemctl', '--user', 'daemon-reload'])
        except (ControlError, OSError, UnicodeError):
            fix = 'restore the user manager and run systemctl --user daemon-reload'
            if error:
                error.fix += '; ' + fix
            else:
                error = ControlError('daemon_reload_unverified', 'templates removed but user reload unverified',
                                     fix=fix)
    for home in sorted(audit):
        record_lifecycle(ctx, home, args, error.code if error else 'pruned')
    if error:
        error.mutated = bool(removed)
        error.evidence['removed'] = removed
        raise error
    return {'action': 'prune', 'platform': ctx.platform, 'dry_run': not args.apply,
            'candidates': [row for row, _, _ in candidates], 'removed': removed}


def github_budget(ctx):
    data = github_read(ctx, ['api', 'rate_limit'])
    budget = {}
    for name, resource in (('graphql', 'graphql'), ('rest', 'core')):
        budget[name] = None
        try:
            info = data['resources'][resource]
            remaining, limit, reset = (info[key] for key in ('remaining', 'limit', 'reset'))
            if not all(type(value) is int and value >= 0 for value in (remaining, limit, reset)):
                continue
            stamp = datetime.fromtimestamp(reset, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            budget[name] = {'remaining': remaining, 'limit': limit, 'reset': stamp}
        except (KeyError, TypeError, OverflowError, OSError, ValueError):
            continue  # A missing resource must not hide the other one or the inventory.
    return budget


def host_work_count(ctx, repo):
    if not re.fullmatch(r'[a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+', repo):
        return None
    # --label filters are ANDed. The comma in the search qualifier means OR.
    issues = github_read(ctx, ['issue', 'list', '--repo', repo, '--state', 'open',
                               '--search', 'label:ai-ready,ai-fix-needed',
                               '--limit', str(HOST_WORK_LIMIT), '--json', 'number'])
    if isinstance(issues, list) and all(isinstance(issue, dict) and
                                        type(issue.get('number')) is int and issue['number'] > 0
                                        for issue in issues):
        return len({issue['number'] for issue in issues})
    return None


def command_status_all(ctx, *, work):
    coverage = {'state': 'ok', 'managers': {}, 'problems': [],
                'scope': 'observed local managers only; other users, namespaces, containers and remote hosts unobserved'}
    worker_bindings = {}
    if ctx.platform == 'linux':
        rows, paths, worker_bindings = host_linux(ctx, coverage)
    else:
        rows, paths = host_darwin(ctx, coverage)
    deployments = host_configs(ctx, paths, coverage)
    config_fields = ('repos', 'provider', 'model', 'metered', 'thinking', 'max_concurrency')
    bound = set()
    for row in rows:
        config = row['binding']['config']
        deployment = deployments.get(config)
        row.update(repo=None, engine={'state': 'unknown', 'version': None})
        if deployment:
            bound.add(config)
            row.update(repo=deployment['repo'], engine=deployment['engine'],
                       last_lifecycle=deployment.get('last_lifecycle'))
            row['binding'] = deployment['binding']
            target = deployment.get('target')
            if target:
                row.update({key: deployment[key] for key in config_fields})
                binding = worker_bindings.get((row['manager'], row['unit']))
                if binding is not None:
                    if row['repo']:
                        repo = Repo(target.repo_dir or target.deploy_home, row['repo'], *row['repo'].split('/', 1), None)
                        row['worker'] = current_run(ctx, target, repo, row['unit'], manager=row['manager'])
                    if row['worker']['state'] == 'active/issue unknown':
                        if worker := host_worker_issue(ctx, row, target, binding):
                            row['worker'] = worker
    for config, item in deployments.items():
        if config not in bound:
            rows.append({'manager': None, 'unit': None, 'timer': None, 'kind': 'config-only',
                         'loaded': False, 'installed': False, 'scheduler': 'prepared-only', 'state': 'prepared-only',
                         'repo': item['repo'], 'engine': item['engine'], 'binding': item['binding'],
                         'last_lifecycle': item.get('last_lifecycle'),
                         'worker': {'state': 'not observed'}, 'next_trigger': None,
                         **{key: item[key] for key in config_fields if key in item}})
    document = {'action': 'status', 'scope': 'host', 'platform': ctx.platform, 'coverage': coverage,
                'totals': {'observed_workers': sum(r['kind'] == 'runner' and r['loaded'] is True for r in rows),
                           'observed_running_services': sum(r['kind'] == 'runner' and r['scheduler'] in ACTIVE_STATES for r in rows),
                           'discoverable_configs': len(deployments)}, 'rows': rows}
    if work:
        repos = sorted({repo for item in deployments.values() for repo in item.get('repos', [])})
        # GitHub repo names are case-insensitive; retain the config spelling in the receipt.
        repo_counts = {repo: host_work_count(ctx, repo) for repo in sorted({repo.lower() for repo in repos})}
        counts = {repo: repo_counts[repo.lower()] for repo in repos}
        scheduled_or_busy = {row['binding']['config'] for row in rows if row['kind'] == 'runner'
                             and (row['scheduler'] in ACTIVE_STATES or any(
                                 timer['state'] in ACTIVE_STATES for timer in row.get('timers', {}).values()))}
        document['work'] = counts
        document['suggestions'] = [f'no work: consider /orbi stop {repo} or set {repo} slots 1'
                                   for config, item in deployments.items() if config in scheduled_or_busy
                                   and (repo := item['repo']) and counts[repo] == 0]
    # Report what remains after any opt-in issue lookups have consumed budget.
    document['github_budget'] = github_budget(ctx)
    return document


def command_status(ctx, args):
    if args.scope == 'all':
        return command_status_all(ctx, work=args.work)
    repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
    if ctx.platform == 'linux':
        return status_linux(ctx, repo, args.config)
    return status_darwin(ctx, repo, args.config)


def command_version(ctx, args):
    """Bind one deployment and read its engine evidence, without full status."""
    repo = repo_identity(ctx, args.repo_dir or ctx.cwd)
    target = select_target(ctx, repo, args.config)
    if target is None:
        deployment = {'state': 'absent', 'engine': {
            'state': 'unconfigured', 'version': None, 'revision': None,
            'reason': 'no deployment config owns this repository'}}
    else:
        validate_target(target, repo)
        deployment = {'state': 'configured', 'deploy_home': str(target.deploy_home),
                      'unit_name': target.unit_name,
                      **local_deployment_summary(ctx, target, metadata_only=True)}
    return {'action': 'version', 'platform': ctx.platform, 'repo': repo.full,
            'repo_dir': str(repo.path), 'deployment': deployment}


def action_usage():
    prefix = 'python3 -B orbi_control.py '
    return (prefix + '[' + '|'.join(name for name in ACTIONS if name != 'set') + '] [all] '
            '[--repo-dir PATH] [--config PATH] [--dry-run] [--json] [--verbose] [--work] '
            '[--pi-providers PATH --pi-provider ID --pi-model ID [--pi-thinking LEVEL] [--allow-metered]] '
            '[--resume-setup] [--harness {pi-bolt,pi}] [--stop] [--wait] [--apply]\n'
            + '\n'.join('  ' + prefix + command.removeprefix('/orbi ') + ' [--json]' for command in SET_USAGE))


def command_help(ctx, args):
    options = {
        '--harness': 'new setup or absent start: pi-bolt (new default) or pi; existing start rejects selectors; no migration',
        '--repo-dir': 'canonical repository checkout (default: current directory)',
        '--config': 'explicit native Orbi config; update binds its repo_dir if --repo-dir is omitted',
        '--dry-run': 'preview without locking, writing, installing or activating',
        '--json': 'print one JSON document',
        '--verbose': 'status all only: print per-unit rows and full coverage details in text',
        '--work': 'status all only: count open ai-ready or ai-fix-needed issues per repo and suggest where to cut idle capacity',
        '--stop': 'update only: compatibility opt-out: quiesce, update and leave stopped',
        '--wait': f'update only: wait up to {UPDATE_WAIT_MINUTES} minutes for workers to finish; leave paused on timeout',
        '--apply': 'prune only: remove verified stale user unit templates and reload the user manager',
        '--resume-setup': 'setup only: fill a legacy missing local provider; requires explicit '
                          '--config and complete matching --pi-* inputs; never overwrite',
        '--pi-providers': 'regular Pi metadata JSON for new setup/absent start or explicit bounded setup resume (no credentials)',
        '--pi-provider': 'explicit provider ID; requires --pi-providers and --pi-model',
        '--pi-model': 'model ID with verified metadata; requires --pi-providers and --pi-provider',
        '--pi-thinking': 'reasoning for new setup/absent start; setup resume must match saved value (omission inherits)',
        '--allow-metered': 'confirm explicit metered bootstrap or a model switch from subscription to metered; '
                           'does not override allowed_providers or replace a saved selection during setup/start',
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
        'quickstart': [
            '/orbi status all shows local deployments and the GitHub CLI account API budget. '
            'No checkout required; local inventory survives unavailable GitHub data. '
            'Add --work for per-repo labeled issue counts; use --verbose for per-unit text or --json for structured inventory. '
            'Preserve literal status all in one helper call; never inject --repo-dir or --config. '
            'Other lifecycle/mutation selectors conflict and are refused before probes. Coverage and totals are observed, not an absolute host census.',
            'Bare /orbi or status inspects only. For a genuinely absent deployment with no explicit --config, '
            'authorized start prepares, validates non-activating, then activates in one invocation; '
            'no separate setup or repeated approval. Missing explicit configs, partial and foreign targets are not absent.',
            'Existing-target start is unchanged if the exact pin is the newest official release and all '
            'configured timers are enabled and active. Otherwise, quiesce owned units as needed, sync, '
            'pin and run orbi check under the config lock before repairing units and starting scheduling. '
            'The helper runs orbi check --config PATH with the bound deployment bootstrap and scoped environment. '
            'Saved provider and harness stay selected. On sync or validation failure, start nothing and report '
            'the bound recovery command. Dry-run defers release resolution and makes no changes.',
            'Explicit /orbi start, plain /orbi update, and install.sh with Orbi selected authorize activation. '
            'Require verified unit and file ownership, a validated release pin and a passing orbi check. '
            'Do not start if validation fails or is unknown. No separate approval is required.',
            'Public skill syntax: /orbi setup starts by default (maps to helper start). /orbi setup --prepare-only '
            'maps to non-activating helper setup. The skill consumes --prepare-only; it is not a Python flag. '
            'Public setup --resume-setup requires --prepare-only; otherwise reject before invocation and '
            'show setup --prepare-only --resume-setup with the original arguments. '
            'Default setup --dry-run previews start; prepare-only --dry-run previews preparation only.',
            'Direct Python helper syntax: setup prepares without scheduling. New preparation defaults to Pi-Bolt; --harness pi '
            'selects stock Pi. Existing selections stay unchanged. A missing binary is a prerequisite, '
            'not an automatic installation or fallback.',
            'Use published provider/model IDs and a credential-free metadata path; omitted selectors '
            'reuse verified donor metadata, or report the exact missing input. No donor creation needed.',
            'Planned is a write-free preview; prepared is non-activating validation; activated is '
            'scheduling requested, not live-qualified delivery. Absent-start preview defers source, '
            'published-file validation and activation checks until preparation; it does not pass them.',
            'Status separates configured harness from running-process evidence (not observed), and '
            'configured slots from enabled/active observed units. With an enabled/active owned timer, '
            'scheduling is active but no worker was observed if running-service reads show none; '
            'not stopped or setup needed. Missing evidence or activity outside the scan is unknown, not zero. '
            'Template rows are not enabled capacity.',
            'Plain update starts scheduling after validation, even after an earlier stop; --stop leaves stopped. '
            'Bind the unique matching deployment, disable owned timers and cancel verified queued starts. '
            'Use update --wait to let workers finish instead of stopping them. '
            'After idle readback, sync-engine-source, pin sha:<commit> and check. No separate status, stop or start command. '
            'No direct kill, restart or background continuation.',
        ],
        'examples': [
            {'command': '/orbi status all --json',
             'outcome': 'Read-only host overview: distinct deployments/services, installed and loaded evidence, partial coverage; no queue or doctor fan-out.'},
            {'command': '/orbi version --json',
             'outcome': 'Identify one deployment engine read-only; no bootstrap, scheduler or network probes.'},
            {'command': '/orbi status --json', 'outcome': 'Inspect only; bare /orbi is equivalent.'},
            {'command': '/orbi setup --dry-run --pi-providers /path/to/models.json '
                        '--pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID',
             'outcome': 'Preview default start without writes; staged validation/activation checks remain deferred. '
                        'Replace paths/IDs with verified published metadata.'},
            {'command': '/orbi setup --harness pi --pi-providers /path/to/models.json '
                        '--pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID',
             'outcome': 'Prepare a new stock Pi target, then activate if technical checks pass.'},
            {'command': '/orbi setup --prepare-only --dry-run --pi-providers /path/to/models.json '
                        '--pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID',
             'outcome': 'Preview preparation only; remove --dry-run to prepare without scheduling.'},
            {'command': '/orbi setup --prepare-only --resume-setup --config /path/to/orbi.toml '
                        '--pi-providers /path/to/models.json --pi-provider SAVED_PROVIDER_ID '
                        '--pi-model SAVED_MODEL_ID --dry-run',
             'outcome': 'Preview bounded missing-local-provider recovery with exact saved selectors; '
                        'never activate.'},
            {'command': '/orbi start --pi-providers /path/to/models.json '
                        '--pi-provider PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID',
             'outcome': 'Prepare absent target with Pi-Bolt, then activate if technical checks pass. '
                        'Omit selectors on subsequent starts.'},
            {'command': '/orbi start --dry-run',
             'outcome': 'Preview existing activation, or absent preparation using donor metadata; '
                        'without a donor, add the complete first-deployment selectors above.'},
            {'command': '/orbi stop', 'outcome': 'Disable owned timers, cancel verified queued starts and stop owned workers through systemd; verify stopped.'},
            {'command': '/orbi update --dry-run',
             'outcome': 'Preview timer disable, queued-start cancellation, worker stop, release update and conditional scheduling; no writes or lock.'},
            {'command': '/orbi update --config /path/to/orbi.toml --wait',
             'outcome': 'Use the configured checkout from any directory and wait for workers to finish before syncing.'},
            {'command': '/orbi set my-repo slots 1',
             'outcome': 'Wait for workers, back up the config and apply one slot without changing the engine pin.'},
            {'command': '/orbi set my-repo model PUBLISHED_PROVIDER_ID/PUBLISHED_MODEL_ID high',
             'outcome': 'Select an existing catalog model and optional thinking level; omission keeps saved thinking.'},
            {'command': '/orbi update --stop',
             'outcome': 'Quiesce owned units and update after idle readback; leave stopped. Unit refresh waits for authorized start.'},
            {'command': '/orbi update',
             'outcome': 'Quiesce owned units, sync/pin/check the release, then start configured scheduling; no separate start.'},
        ],
        'recovery': {
            'harness': 'prerequisite_missing/harness_unavailable: provision the exact selected pi-bolt or pi '
                       'separately; inspect saved routing/launcher drift deliberately. No install/fallback here.',
            'provider': 'provider_unavailable/auth_unverified: supply --pi-providers PATH --pi-provider ID '
                        '--pi-model ID for absent preparation, or provision the exact named existing catalog/auth '
                        'or service reference separately; never invent capabilities or copy credentials. '
                        'metered_confirmation_required: keep a subscription provider or explicitly pass --allow-metered. '
                        'provider_not_allowed: choose a provider permitted by allowed_providers in orbi.toml.',
            'config_missing': '--config must name an existing native config. Correct the path; omit --config '
                              'only for genuinely absent preparation, not to bypass partial/foreign state.',
            'partial_setup': 'Preserve config, pin, provider, env, launcher and attempts. Inspect the failed step; '
                             'repair deliberately and use public setup --prepare-only (direct helper setup) without bootstrap selectors. Only a legacy missing '
                             'local provider permits public setup --prepare-only --resume-setup --config PATH '
                             '(direct helper setup --resume-setup) with complete matching '
                             'selectors. Start never performs legacy repair or changes a saved harness.',
            'activation': 'Name the failed technical check and the next safe read-only check or exact repair. '
                          'GitHub unprotected main is an observed branch state; protection/rules HTTP 403 means '
                          'access denied for that endpoint and unknown details, not absent rules. Both can coexist; '
                          'they are informational, not scheduling blockers. Branch protection is not a Kit '
                          'setup/start prerequisite. Do not require a protection read/repair, PR-only mode, special '
                          'opt-in, no-base-write engine proof, paid GitHub plan, engine release or second approval '
                          'on that basis. Authentication, repository access and ownership still apply. '
                          'Status doctor.state=failed is diagnostic, not itself a scheduling gate. '
                          'Existing protections, CI, review and merge requirements remain unchanged; startup is '
                          'not successful merge or live qualification. A preview is not approval. '
                          'See skills/orbi/references/lifecycle.md#activation-evidence.',
            'setup_busy': 'Preparation requires verified inactivity. Cite observed timer/worker state from '
                          'status or the error scheduler evidence. Offer authorized stop only when '
                          'deliberately re-preparing or pausing; do not stop workers to pass a preview. '
                          'Existing valid start skips preparation.',
            'platform': 'unsupported_platform: use Linux for authorized mutations; macOS supports status/version/help; '
                        'other platforms support help only.',
            'update': 'update_busy/source_dirty/sync_engine_source_failed: inspect concurrent work, preserve tracked '
                      'checkout changes, and inspect the failed fetch or channel privately. Update never '
                      'discards work or rewrites origin. Failed timer disable, job cancellation, worker stop or scheduler '
                      'readback blocks sync. Inspect the failed step and scheduler, repair the cause and deliberately '
                      'retry; no timer re-enable rollback.',
            'stale_helper': 'Report the Loaded helper path and available Kit revision; request a separately '
                            'authorized Kit update/reload. Do not change origin, upgrade an engine pin, run bare '
                            'upstream Orbi or stop workers as a workaround.',
        },
        'errors': {
            'exit': 'Exit 0 means success or help; a nonzero exit reports an error, '
                    'not whether a write occurred.',
            'mutated': 'error.mutated, not the exit code, reports actual or possible writes, '
                       'including locks (text: mutated=True/False). Start/update/stop errors retain '
                       'completed/failed steps, target units and a read-only scheduler snapshot '
                       '(or unavailable); inspect status and actual files before deliberate recovery.',
            'code': 'error.code classifies the failure; codes are owned by the raising code.',
            'fix': 'error.fix gives the repair action; unknown actions point to /orbi help.',
        },
        'boundaries': [
            'Direct Python helper syntax (not public skill syntax): ' + action_usage(),
            'Minimum Python 3.11; the Python floor guard also applies to help.',
            'Linux supports mutations; macOS supports status, version and help; other platforms '
            'support help only.',
            'Help needs no repository or deployment and reads no deployment, config, '
            'environment values or scheduler; it runs no subprocess and performs no writes.',
            'Help accepts and ignores --repo-dir, --config, --dry-run and all setup inputs.',
            'Loaded helper: ' + str(Path(__file__).resolve()) + '. If flags are missing in an '
            'older installed helper, report its path and available Kit revision, then request '
            'a separately authorized Kit update/reload; never rewrite project origin.',
            'Direct helper setup supports new preparation, existing valid reuse without selectors, or explicit '
            'bounded --resume-setup for a legacy missing local provider with matching selectors. '
            'Other incomplete/changed states require deliberate repair preserving evidence.',
            'Setup activated=false means no activation invoked here, not proof an existing '
            'scheduler is inactive. Scheduler observations are separate. A killed process cannot '
            'emit a receipt; infer retry safety from actual files. Never retry a timeout unchanged.',
            'Start/update/stop can fail after partial application. A failed mutation is possible, '
            'not completed; confirmed timer lists exclude failed attempts. Start activation=possible '
            'means timers or workers may already run; activation=none can still include lock writes. '
            'Never retry unchanged, compensate with enable/disable, or stop workers after failure.',
            'Start (also public default setup) may request one first tick after a definite timer-enable '
            'nonzero exit, only after successful upstream setup/install and scheduler readback. Under '
            'the config lock it revalidates target identity and fresh owned units, stable timer states, '
            'all workers idle and no pending target jobs. No later timer configuration or enable retry. '
            'Timeout, unavailable/unknown evidence, ownership drift or active/draining workers block '
            'this recovery. The original timer error and nonzero exit remain: recurring_scheduling=incomplete; '
            'first_tick is requested, blocked, failed, unverified or not-requested. first_tick_evidence '
            'separates the decision snapshot/request mutation from the later scheduler observation. '
            'Requested means only systemd accepted the request, not worker completion or live delivery.',
            'Status is read-only. Setup (including absent-start preparation) stages source/config; '
            'start, update and stop touch the scheduler. Update and stop report disabled timers and stopped workers. '
            'Update separately reports engine and '
            'verified enabled/active scheduling; --stop leaves stopped. Dry-run performs no writes or wait.',
            'Not an executor or scheduler: no tick, issue claim, review or merge.',
            'Not /unblock, /git-commit-push, /plan-with-me, /plan-for-me.',
            'Local visibility only: no cross-machine lock or capacity guarantee.',
            'Next steps: use status to inspect; public setup --prepare-only (helper setup) to prepare; '
            'public setup or start authorizes activation after technical checks. Update quiesces before '
            'sync and starts scheduling after validation (--stop leaves stopped); stop quiesces without updating.',
        ],
    }


# One ordered inventory owns dispatch, argparse action names and help metadata.
ACTIONS = {
    'status': {
        'handler': command_status,
        'effect': 'Inspect deployment release/revision with provenance, scheduler and per-slot running issues; '
                  'queue order is not pickup. Missing live bindings mean active/issue unknown, not idle. '
                  'Literal status all inspects accessible local host services and GitHub API budget without repository binding.',
        'mutates': 'none',
        'platforms': ['linux', 'darwin'],
        'applies': ['--repo-dir', '--config', '--json', '--verbose', '--work'],
        'when': 'Run by default to inspect a canonical GitHub checkout; no deployment is required '
                '(an absent deployment is reported as absent). Use status all for host inventory from any directory; '
                'only --json, --verbose and --work may accompany all.',
    },
    'version': {
        'handler': command_version,
        'effect': 'Inspect one deployment identity, verified engine release and observed revision, '
                  'with verification state and provenance or reason; no bootstrap or full status probes.',
        'mutates': 'none',
        'platforms': ['linux', 'darwin'],
        'applies': ['--repo-dir', '--config', '--json'],
        'when': 'Run to identify the selected deployment without scheduler, queue, authentication or network reads. '
                'Absent is unconfigured; unverifiable release metadata is unknown, never the global CLI version.',
    },
    'setup': {
        'handler': command_setup,
        'effect': 'Stage pinned source/config and provider metadata; validate without activation.',
        'mutates': 'staging',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json',
                    '--pi-providers', '--pi-provider', '--pi-model', '--pi-thinking', '--allow-metered', '--resume-setup', '--harness'],
        'when': 'Run to prepare one unambiguous repository deployment with verified '
                'prerequisites, preserving existing pins and active workers.',
    },
    'start': {
        'handler': command_start,
        'effect': 'Prepare if absent or update an existing target, then repair and start scoped scheduling.',
        'mutates': 'scheduler',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json',
                    '--pi-providers', '--pi-provider', '--pi-model', '--pi-thinking', '--allow-metered', '--harness'],
        'when': 'Prepare only if genuinely absent with no explicit --config. Existing targets quiesce as needed '
                'and sync, pin and validate before activation. No changes if current with configured timers enabled '
                'and active. On failure report the specific check and next safe action.',
    },
    'update': {
        'handler': command_update,
        'effect': 'Disable owned timers, cancel queued starts, stop owned workers (or wait with --wait), update and start scheduling; --stop leaves stopped.',
        'mutates': 'scheduler',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json', '--stop', '--wait'],
        'when': 'Run for a prepared deployment: quiesce owned units under lock, then pin the newest official '
                'release as sha:<commit> after fresh idle evidence. Plain update authorizes starting configured scheduling '
                'after engine validation, even after an earlier stop. Explicit --stop leaves stopped. '
                'No direct kill, restart or background continuation.',
    },
    'set': {
        'handler': command_set,
        'effect': 'Change slots or catalog model, back up the config and apply with the update --wait behavior; do not move the engine pin.',
        'mutates': 'scheduler',
        'platforms': ['linux'],
        'applies': ['--json', '--allow-metered'],
        'when': 'Use a unique local unit prefix, repository name, or config path. '
                f'Slots must be a positive integer from 1 to {MAX_INSTANCES}. '
                'An unknown provider/model is refused before writes.',
    },
    'stop': {
        'handler': command_stop,
        'effect': 'Disable owned timers, cancel verified queued starts, stop owned workers and verify inactivity.',
        'mutates': 'scheduler',
        'platforms': ['linux'],
        'applies': ['--repo-dir', '--config', '--dry-run', '--json'],
        'when': 'Run to stop scheduling and interrupt workers for a prepared, unambiguous deployment with '
                'verified unit ownership; recovery inputs are preserved. An explicit start, plain update or an installer refresh '
                'that selects Orbi can start scheduling again.',
    },
    'prune': {
        'handler': command_prune,
        'effect': 'List stale unloaded user unit templates; --apply removes them and reloads the user manager.',
        'mutates': 'scheduler with --apply',
        'platforms': ['linux'],
        'applies': ['--dry-run', '--json', '--apply'],
        'when': 'No checkout needed. Requires an explicit missing configuration or repository directory. '
                'Keeps loaded or installed instances, queued jobs, configs and deployment data.',
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
                  f"mutations_supported={document['mutations_supported']}\nQuickstart:\n")
    for text in document['quickstart']:
        ctx.out.write('  ' + text + '\n')
    ctx.out.write('Actions (direct Python helper syntax):\n')
    for name, entry in document['actions'].items():
        ctx.out.write(f"  {name} [{entry['mutates']}] {entry['effect']} "
                      f"Platforms: {', '.join(entry['platforms'])}. {entry['when']}\n")
    ctx.out.write('Examples:\n')
    for example in document['examples']:
        ctx.out.write(f"  {example['command']}\n    {example['outcome']}\n")
    ctx.out.write('Recovery:\n')
    for code, text in document['recovery'].items():
        ctx.out.write(f'  {code}: {text}\n')
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
        prog='orbi_control.py', allow_abbrev=False,
        usage=action_usage() + ' [-h]',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Direct Python helper syntax (setup is non-activating). Public /orbi setup maps to start; '
                    '/orbi setup --prepare-only maps to helper setup.\nOrbi lifecycle controls:\n'
                    + '\n'.join(f"{name} [{entry['mutates']}]: {entry['effect']}"
                                for name, entry in ACTIONS.items())
                    + ' Default: status. Linux mutates; macOS also supports status/version; '
                    'help works everywhere; minimum Python 3.11.')
    parser.add_argument('action', nargs='?', default='status',
                        metavar='[' + '|'.join(ACTIONS) + ']')
    parser.add_argument('operands', nargs='*', help='status all or set deployment and values')
    parser.add_argument('--repo-dir', default=None,
                        help='canonical repository checkout (default: current directory)')
    parser.add_argument('--config', default=None,
                        help='explicit native Orbi config; update uses its repo_dir if --repo-dir is omitted')
    parser.add_argument('--dry-run', action='store_true',
                        help='show the plan without locking, writing, installing or activating')
    parser.add_argument('--json', action='store_true', help='print one JSON document')
    parser.add_argument('--verbose', action='store_true', help='status all only: show per-unit text and coverage details')
    parser.add_argument('--work', action='store_true', help='status all only: count open ai-ready or ai-fix-needed issues')
    parser.add_argument('--apply', action='store_true', help='prune only: remove stale unit templates')
    parser.add_argument('--stop', action='store_true',
                        help='update only: compatibility opt-out: quiesce, update and leave stopped')
    parser.add_argument('--wait', action='store_true',
                        help=f'update only: wait up to {UPDATE_WAIT_MINUTES} minutes for workers to finish; '
                             'leave paused on timeout')
    parser.add_argument('--resume-setup', action='store_true',
                        help='setup only: resume legacy missing provider with explicit --config '
                             'and complete matching --pi-* inputs')
    parser.add_argument('--harness', choices=('pi-bolt', 'pi'), help='new setup or absent start: default pi-bolt; explicit stock pi supported; no legacy migration')
    parser.add_argument('--pi-providers', help='new setup/absent start or bounded setup resume: Pi metadata JSON')
    parser.add_argument('--pi-provider', help='new setup/absent start or bounded setup resume: explicit provider ID')
    parser.add_argument('--pi-model', help='new setup/absent start or bounded setup resume: model ID with verified metadata')
    parser.add_argument('--pi-thinking', help='new setup/absent start reasoning level, or exact saved setup resume value; '
                        'omitted resume thinking inherits the saved value')
    parser.add_argument('--allow-metered', action='store_true',
                        help='confirm an explicit metered provider selection for model set or new setup/start')
    args = parser.parse_intermixed_args(argv)
    args.scope = None
    if args.action != 'set' and args.operands:
        if args.operands != ['all']:
            parser.error('expected literal all for host inventory; see help')
        args.scope = 'all'
    return args


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
        if args.action == 'start':
            exc.evidence = {'preparation': {'state': 'skipped'}, 'activation': 'none',
                            'target': args.config, 'original_error': exc.code,
                            'steps': [{'step': 'validate_request', 'status': 'failed',
                                       'error': exc.code, 'mutation': 'none'}]}
        render_error(ctx, args.action, exc, args.json)
        return exc.exit_code
    try:
        if args.action not in ACTIONS:
            raise ControlError(
                'unknown_action', f"unknown action '{args.action}'", exit_code=2,
                fix='run /orbi help for the supported actions and their effects')
        if args.scope is not None and (args.action != 'status' or any(
                (args.repo_dir is not None, args.config is not None, args.dry_run, args.stop, args.wait, args.apply,
                 args.resume_setup, args.harness is not None, args.pi_providers is not None,
                 args.pi_provider is not None, args.pi_model is not None, args.pi_thinking is not None,
                 args.allow_metered))):
            raise ControlError('invalid_host_selection',
                               'literal all requires status with no repo/config or mutation selectors',
                               fix='use /orbi status all without selectors', exit_code=2)
        if args.verbose and args.scope != 'all':
            raise ControlError('invalid_host_selection', '--verbose requires status all',
                               fix='use /orbi status all --verbose, or omit --verbose', exit_code=2)
        if args.work and args.scope != 'all':
            raise ControlError('invalid_host_selection', '--work requires status all',
                               fix='use /orbi status all --work, or omit --work', exit_code=2)
        if args.apply and args.action != 'prune':
            raise ControlError('invalid_apply_selection', '--apply requires prune',
                               fix='use /orbi prune to preview before applying', exit_code=2)
        if args.action == 'prune' and (args.repo_dir is not None or args.config is not None
                                       or (args.dry_run and args.apply)):
            raise ControlError('invalid_prune_selection', 'prune is host-scoped and --apply conflicts with --dry-run',
                               fix='use /orbi prune to preview or /orbi prune --apply without selectors', exit_code=2)
        if args.action == 'version' and args.dry_run:
            raise ControlError('invalid_version_selection', '--dry-run does not apply to read-only version',
                               fix='use /orbi version [--repo-dir PATH] [--config PATH] [--json]', exit_code=2)
        if args.stop and args.action not in ('update', 'help'):
            raise ControlError('invalid_stop_selection', '--stop requires update',
                               fix='omit --stop or explicitly invoke update --stop', exit_code=2)
        if args.wait and args.action not in ('update', 'help'):
            raise ControlError('invalid_wait_selection', '--wait requires update',
                               fix='omit --wait or explicitly invoke update --wait', exit_code=2)
        if args.harness and '--harness' not in ACTIONS[args.action]['applies'] and args.action != 'help':
            raise ControlError('invalid_harness_selection', '--harness requires setup or absent start',
                               fix='omit the selector to inspect the persisted selection', exit_code=2)
        selectors = (args.pi_providers, args.pi_provider, args.pi_model, args.pi_thinking)
        if args.action != 'help' and args.resume_setup and (
                args.action != 'setup' or not args.config or not all(selectors[:3])):
            raise ControlError('invalid_resume_selection',
                               '--resume-setup requires setup, explicit --config and complete --pi-* inputs',
                               fix='use public `/orbi setup --prepare-only --resume-setup --config PATH '
                                   '--pi-providers PATH --pi-provider ID --pi-model ID`, matching the saved selection '
                                   '(direct Python helper: setup --resume-setup with the same inputs)', exit_code=2)

        if args.action != 'help' and any(value is not None for value in selectors):
            if ('--pi-providers' not in ACTIONS[args.action]['applies'] or not all(selectors[:3])
                    or any(value is not None and not value.strip() for value in selectors)):
                raise ControlError(
                    'invalid_provider_selection',
                    'bootstrap requires setup or absent start with --pi-providers, --pi-provider and --pi-model',
                    fix='supply all three selectors and optionally --pi-thinking for a new '
                        'deployment, or omit all bootstrap inputs to reuse existing metadata',
                    exit_code=2)
        if args.allow_metered and args.action not in ('set', 'help') and (
                args.action not in ('setup', 'start') or args.pi_provider is None):
            raise ControlError('invalid_metered_selection',
                               '--allow-metered requires set model or explicit setup/start provider inputs',
                               fix='omit --allow-metered unless selecting a model or bootstrap provider', exit_code=2)
        entry = ACTIONS[args.action]
        if 'all' not in entry['platforms'] and ctx.platform not in entry['platforms']:
            if ctx.platform == 'darwin':
                raise ControlError(
                    'unsupported_platform',
                    'macOS supports status/version only; setup/start/update/set/stop/prune is refused before any '
                    'side effect',
                    fix='run `/orbi status` on macOS; use Linux for authorized lifecycle mutations',
                    exit_code=2)
            raise ControlError(
                'unsupported_platform',
                f'platform {ctx.platform} is unsupported; Linux mutates and macOS is '
                'read-only (status/version)',
                fix='run status on a supported host', exit_code=2)
        document = entry['handler'](ctx, args)
        record_lifecycle(ctx, ctx.lifecycle_home, args, document.get('status'))
        if args.action == 'help':
            render_help(ctx, document, args.json)
        else:
            render(ctx, document, args.json, verbose=args.verbose)
        return 0
    except ControlError as exc:
        record_lifecycle(ctx, ctx.lifecycle_home, args, exc.code)
        if args.action in ('setup', 'start') and 'steps' not in exc.evidence:
            exc.evidence = {**exc.evidence, 'target': args.config, 'original_error': exc.code,
                            'activated': False, 'scheduler': {'state': 'unavailable'},
                            'steps': [{'step': 'validate_request', 'status': 'failed',
                                       'error': exc.code, 'mutation': 'none'}]}
            if args.action == 'start':
                exc.evidence.update(preparation={'state': 'skipped'}, activation='none')
        render_error(ctx, args.action, exc, args.json)
        return exc.exit_code


if __name__ == '__main__':
    sys.exit(main())
