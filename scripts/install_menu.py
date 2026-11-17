#!/usr/bin/env python3
"""Install the full Kit suite with verbose output by default.

    install.sh                every available component, live output and exact commands
    install.sh --menu         a checkbox menu on a terminal (arrows, Space, Enter)
    install.sh --full          the full suite for available hosts, no menu (--all also works)
    install.sh update          the same refresh as the default (same items as --full)
    install.sh --only pi-bolt,pi,tx  just these; --skip hermes leaves those out
    install.sh --list          the items and whether each host is available
    install.sh --dry-run ...   print each command instead of running it
    install.sh --no-pull       install this checkout as it is

There is no keep-on-install mode: `install` and `update` run the same items and
refresh them, and differ only in the report wording. Both first bring this checkout
up to date (`git pull --ff-only` of its upstream) and then run the pulled installer; a
checkout with local changes, no upstream or a detached HEAD is installed as it is,
and says so.

Each host item runs its own supported install command; a host whose CLI is not
installed is skipped and says so, and fails when named with --only. Pi-Bolt is
the only Pi harness Kit installs; its destination executable manages the Kit package. Every selected component is
refreshed on both `install` and `update`: the Pi package and Pi-Bolt are updated
even when a previous copy looks current, because a kept copy silently goes stale.
Orbi installs the CLI only via uv; existing CLIs and deployments are kept so a
pinned deployment is never replaced. Pi-Bolt bootstraps or refreshes the upstream
native Pi build and never installs its optional extensions. Hermes options
(--hermes-home, --bundle-only, --no-reload, --yes-deps) apply to the Hermes item.
Standard library only.
"""
import argparse
import codecs
import json
from dataclasses import dataclass, field
import os
from pathlib import Path
import platform
import re
import selectors
import signal
import shutil
import shlex
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'TrebuchetDynamics/kit'
PI_SOURCE = 'git:github.com/TrebuchetDynamics/kit'
ORBI_SOURCE = ('git+https://github.com/XelHaku/orbi.git@'
               '1a8b2f9603f6258cb105293f238a8d3f775f3393')
HOME = Path(os.environ.get('HOME', str(Path.home())))
BIN = Path(os.environ.get('AUTOWORK_BIN_DIR') or HOME / '.local' / 'bin')

def manifest_name(relative, key='name'):
    """A plugin or marketplace name declared by a manifest in this checkout."""
    try:
        data = json.loads((ROOT / relative).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ''
    return str(data.get(key) or '')


CLAUDE_PLUGIN = manifest_name('.claude-plugin/plugin.json') or 'kit'
CLAUDE_MARKETPLACE = manifest_name('.claude-plugin/marketplace.json') or 'kit'
CODEX_PLUGIN = manifest_name('.codex-plugin/plugin.json') or CLAUDE_PLUGIN
CODEX_MARKETPLACE = manifest_name('.agents/plugins/marketplace.json') or 'kit-marketplace'


class Output:
    """Flush progress immediately; color only where requested or supported."""
    COLORS = {'heading': '1;36', 'installed': '32', 'failed': '31',
              'skipped': '33', 'planned': '36', 'command': '2'}

    def __init__(self, color='auto', verbosity=2):
        self.verbosity = verbosity
        self.color = color == 'always' or (color == 'auto' and sys.stdout.isatty()
                      and os.environ.get('TERM') != 'dumb' and not os.environ.get('NO_COLOR'))

    def line(self, message='', style=''):
        if self.color and style in self.COLORS:
            message = f'\033[{self.COLORS[style]}m{message}\033[0m'
        print(message, flush=True)

    def raw(self, message):
        print(message, end='', flush=True)


def run_command(argv, output, extra_env=None, timeout=None):
    """Stream both child channels, including prompts without a trailing newline.

    Keep a bounded diagnostic tail for quiet failures; stdin remains inherited.
    Quiet mode still shows native prompts/output when input is a terminal.
    """
    env = dict(os.environ, PYTHONUNBUFFERED='1', **(extra_env or {}))
    if not output.color:
        env['NO_COLOR'] = '1'
    stream = output.verbosity > 0 or sys.stdin.isatty()
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    tail = ''
    terminal = None
    previous_ttou = None
    if timeout is not None:
        try:
            terminal = os.open('/dev/tty', os.O_RDWR)
            if os.tcgetpgrp(terminal) != os.getpgrp():
                os.close(terminal)
                terminal = None
        except OSError:
            if terminal is not None:
                os.close(terminal)
            terminal = None
        if terminal is not None:
            previous_ttou = signal.signal(signal.SIGTTOU, signal.SIG_IGN)

    def prepare_child():
        os.setpgrp()
        if terminal is not None:
            # Keep native /dev/tty reads in the foreground, not SIGTTIN-stopped.
            os.tcsetpgrp(terminal, os.getpgrp())

    try:
        deadline = time.monotonic() + timeout if timeout is not None else None
        # A process group bounds descendants too, without detaching /dev/tty prompts.
        with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                              preexec_fn=prepare_child if timeout is not None else None,
                              pass_fds=(terminal,) if terminal is not None else ()) as child:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    while True:
                        remaining = None if deadline is None else max(0, deadline - time.monotonic())
                        if remaining == 0 or not selector.select(remaining):
                            raise subprocess.TimeoutExpired(argv, timeout)
                        chunk = child.stdout.read1(4096)
                        if not chunk:
                            break
                        text = decoder.decode(chunk)
                        tail = (tail + text)[-16384:]
                        if stream:
                            output.raw(text)
                text = decoder.decode(b'', final=True)
                tail = (tail + text)[-16384:]
                if stream:
                    output.raw(text)
                code = child.wait(timeout=None if deadline is None else max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
                code = 124
                tail += f'\ncommand timed out after {timeout} seconds; stopped command and descendants'
            except BaseException:
                if timeout is not None:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                raise
    finally:
        if terminal is not None:
            try:
                os.tcsetpgrp(terminal, os.getpgrp())
            finally:
                os.close(terminal)
                signal.signal(signal.SIGTTOU, previous_ttou)
    if stream and tail and not tail.endswith('\n'):
        output.line()
    if code and not stream and tail:
        output.line(tail.rstrip(), 'failed')
    return code, tail.strip()


def failure_summary(text):
    """Extract a final structured receipt, not its closing brace, from native logs."""
    text = text[-16384:]
    decoder = json.JSONDecoder()
    receipt = None
    for index, character in enumerate(text):
        if character != '{':
            continue
        try:
            value, end = decoder.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get('status'), str) and not text[end:].strip():
            receipt = value
            break
    if receipt is not None:
        parts = [receipt.get(key) for key in ('status', 'error')]
        # Scoped/recovery receipts keep per-profile diagnostics.
        diagnostics = [receipt]
        if isinstance(receipt.get('recovery'), dict):
            diagnostics.append(receipt['recovery'])
        for diagnostic in diagnostics:
            rows = diagnostic.get('profiles')
            for row in rows.values() if isinstance(rows, dict) else ():
                if isinstance(row, dict) and row.get('error'):
                    parts.append(row['error'])
        useful = list(dict.fromkeys(part for part in parts if isinstance(part, str) and part.strip()))
        if useful:
            cause = ' '.join('; '.join(useful).split())[:750]
            action = receipt.get('action') or receipt.get('note')
            return cause + ('; ' + ' '.join(action.split())[:400] if isinstance(action, str) else '')
    lines = [line.strip() for line in text.splitlines() if line.strip()
             and line.strip() not in ('{', '}', '[', ']', '},', '],')
             and not line.lstrip().startswith(('"status"', '"pid"', '"started_ns"'))]
    return ' '.join(' | '.join(lines[-3:]).split())[-1200:] or 'command failed; inspect the native output'


def host_unavailable(binary):
    """Detect absent CLIs and stale simple wrappers without executing host code."""
    if not binary:
        return ''
    executable = shutil.which(binary)
    if not executable:
        return f'{binary} not found'
    try:
        with open(executable) as stream:
            text = stream.read(4096)
        if text.startswith(('#!/bin/sh\n', '#!/usr/bin/env sh\n', '#!/bin/bash\n', '#!/usr/bin/env bash\n')):
            words = shlex.split(text.split('\n', 1)[1], comments=True)
            if (len(words) == 3 and words[0] == 'exec' and words[2] == '$@'
                    and not any(char in words[1] for char in '$`*?[{')):
                target = Path(words[1])
                if target.is_absolute() and (not target.is_file() or not os.access(target, os.X_OK)):
                    return f'{binary} launcher target is missing or not executable'
    except (OSError, UnicodeError, ValueError):
        pass  # Not a recognizable wrapper: leave host admission to its own installer.
    return ''


@dataclass
class Step:
    describe: str                   # what this step does, for --dry-run and the summary
    argv: list = None               # a command to run, or
    run: object = None              # a Python callable returning a message
    retry_on: str = ''              # transient failure text that is retried once (a concurrent writer)
    tolerate: tuple = ()            # failure text that means the step's goal already holds


@dataclass
class Item:
    key: str
    label: str
    needs: str = ''                 # the host CLI this item needs, '' for none
    note: str = ''                  # why it is unavailable or what is special
    steps: list = field(default_factory=list)
    missing: str = ''               # what else it needs that is absent, '' for nothing
    refuse: str = ''                # why the selected options cannot be honored

    @property
    def available(self):
        return not self.missing and not host_unavailable(self.needs)


def pi_settings_path():
    """The Pi settings file that stores package filters (PI_CODING_AGENT_DIR wins)."""
    return Path(os.environ.get('PI_CODING_AGENT_DIR') or HOME / '.pi/agent') / 'settings.json'


def same_pi_source(left, right):
    """Compare package sources the way Pi does, ignoring a trailing slash or .git."""
    def canonical(value):
        value = str(value).strip().rstrip('/')
        return value[:-4] if value.endswith('.git') else value
    return canonical(left) == canonical(right)


def enable_pi_package(source=PI_SOURCE, settings=None):
    """Let the installed package load its skills and commands.

    Pi records a package resource filter as an object such as
    ``{"source": ..., "skills": [], "extensions": []}``; an empty list hides every
    resource of that type. A filter written for the package's previous name
    (autowork -> kit) survives both ``pi install`` and ``pi update``, so the
    package stays installed but filtered: no commands and no ``/skill:<name>``.
    Remove only empty filters; keep deliberate partial filters untouched.
    """
    path = Path(settings) if settings else pi_settings_path()
    if not path.is_file():
        return f'no Pi settings at {path}; the package manifest applies'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f'cannot read {path}: {exc}') from exc
    packages = data.get('packages') if isinstance(data, dict) else None
    if not isinstance(packages, list):
        return f'no package filter in {path}; the package manifest applies'
    changed = False
    for index, entry in enumerate(packages):
        if not isinstance(entry, dict) or not same_pi_source(entry.get('source', ''), source):
            continue
        for key in ('skills', 'extensions'):
            if entry.get(key) == []:
                del entry[key]
                changed = True
        if set(entry) == {'source'}:
            packages[index] = entry['source']  # no filter left: the plain source form
            changed = True
    if not changed:
        return f'{path} already loads the {source} package resources'
    # Write beside the original and replace, so an interrupted install cannot truncate it.
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return f'enabled {source} package resources in {path}'


def pi_package(source=PI_SOURCE, binary=None):
    """The directory Pi installed this package source in, or None."""
    binary = binary or BIN.absolute() / 'pi-bolt'
    try:
        lines = subprocess.run([str(binary), 'list'], stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=60).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return None
    for i, line in enumerate(lines):
        # Pi marks a package with a filter as `<source> (filtered)`.
        if line.split()[:1] == [source] and i + 1 < len(lines):
            package = Path(lines[i + 1].strip())
            if package.is_dir():
                return package
    return None


def set_aside(path):
    """Move a file or symlink out of the way as <name>.bak, or .bak.N if that is taken,
    so an earlier backup is never overwritten. Return where it went."""
    backup, n = path.with_name(path.name + '.bak'), 1
    while backup.exists() or backup.is_symlink():
        backup, n = path.with_name(f'{path.name}.bak.{n}'), n + 1
    os.replace(path, backup)
    return backup


def link(target, name):
    """~/.local/bin/<name> -> target; an existing different file is kept as a backup."""
    BIN.mkdir(parents=True, exist_ok=True)
    path = BIN / name
    if path.is_symlink() and Path(os.readlink(path)) == target:
        return f'{path} already links to {target}'
    note = f' (the old one is {set_aside(path)})' if path.exists() or path.is_symlink() else ''
    path.symlink_to(target)
    return f'{path} -> {target}{note}'


def install_tx():
    """tx and its completions; tmux config and helpers only where none exist yet."""
    BIN.mkdir(parents=True, exist_ok=True)
    done = []
    target = BIN / 'tx'
    source = ROOT / 'tmux' / 'tx'
    if target.is_file() and target.read_bytes() == source.read_bytes():
        done.append(f'{target} is current')
    else:
        # Move the old one, a symlink included, rather than write through it: a link
        # may point into another checkout.
        note = f' (the old one is {set_aside(target)})' if target.exists() or target.is_symlink() else ''
        shutil.copy2(source, target)
        target.chmod(0o755)
        done.append(f'{target} written{note}')  # the summary row already says "installed"
    written, kept_completions = [], []
    for shell, folder, name in (('bash', HOME / '.local/share/bash-completion/completions', 'tx'),
                                ('zsh', HOME / '.zsh/completions', '_tx'),
                                ('fish', HOME / '.config/fish/completions', 'tx.fish')):
        dest = folder / name
        if dest.exists() or dest.is_symlink():
            kept_completions.append(f'{shell} completion')
            continue
        text = subprocess.run(['bash', str(source), 'completion', shell], capture_output=True, text=True).stdout
        if text:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(text)
            written.append(shell)
    # Name only what was written: a kept completion can be older than this tx.
    if written:
        done.append('wrote completions for ' + ', '.join(written))
    kept = []
    for src, dest in ((ROOT / 'tmux/tmux.conf', HOME / '.tmux.conf'),
                      (ROOT / 'tmux/style.tmux', HOME / '.tmux/style.tmux'),
                      (ROOT / 'tmux/git-status.sh', HOME / '.tmux/git-status.sh'),
                      (ROOT / 'tmux/short-path.sh', HOME / '.tmux/short-path.sh')):
        if dest.exists() or dest.is_symlink():
            kept.append(dest.name)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text()
        if dest.name == '.tmux.conf':  # point the status bar at the installed helpers
            text = text.replace('~/.tmux/', f'{HOME}/.tmux/')
        dest.write_text(text)
        if dest.suffix == '.sh':
            dest.chmod(0o755)
        done.append(f'installed {dest}')
    if kept or kept_completions:
        done.append('kept your existing ' + ', '.join(kept + kept_completions))
    return '; '.join(done)


def hermes_home(hermes_args):
    """(home, given): the Hermes home the item works on, and whether it was named."""
    given = hermes_args[hermes_args.index('--hermes-home') + 1] if '--hermes-home' in hermes_args else ''
    named = given or os.environ.get('HERMES_HOME')
    return Path(named or HOME / '.hermes'), bool(named)


def hermes_installed(hermes_args):
    """Discover managed clones under either identity without duplicating installation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('install_identity', ROOT / 'scripts/update_bundle.py')
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    home, _ = hermes_home(hermes_args)
    installed = False
    for profile in (home, *home.glob('profiles/*')):
        plugin = updater.plugin_dir(profile)
        if (plugin / '.git').exists() and plugin.resolve() != ROOT.resolve():
            installed = True
    return home if installed else None


SETUP_ONLY = ('--bundle-only', '--no-reload', '--yes-deps')


def hermes_item(hermes_args):
    label = 'Hermes plugin + bundled Ponytail (every live profile)'
    try:
        home = hermes_installed(hermes_args)
    except (ValueError, OSError) as error:
        return Item('hermes', label, needs='hermes', refuse=str(error))
    if home:
        argv = [sys.executable, str(ROOT / 'scripts/update_bundle.py'), '--hermes-home', str(home)]
        # A Hermes profile that rewrites a skill file while the bundle writes it fails the
        # destination recheck; update_bundle re-plans every run, so retry that one race once.
        item = Item('hermes', label, needs='hermes',
                    steps=[Step(f'update_bundle.py --hermes-home {home} (the profiles\' installed plugin)', argv,
                                retry_on='changed since preflight')])
        # update_bundle.py has none of these and restarts gateways, so it cannot honor them.
        unsupported = [flag for flag in SETUP_ONLY if flag in hermes_args]
        if unsupported:
            item.refuse = (f'{", ".join(unsupported)} cannot apply: profiles here have their own plugin clone, '
                           f'which update_bundle.py updates; rerun without them')
        return item
    item = Item('hermes', label, needs='hermes',
                steps=[Step('setup_bundle.py ' + ' '.join(hermes_args),
                            [sys.executable, str(ROOT / 'scripts/setup_bundle.py'), *hermes_args])])
    home, named = hermes_home(hermes_args)
    if not named and not home.is_dir():  # a named home is checked by setup_bundle.py itself
        item.missing = f'no Hermes home at {home}; start hermes once first'
    return item


LEGACY_CLAUDE_MARKETPLACE = 'autowork'
LEGACY_CODEX_MARKETPLACE = 'autowork-marketplace'
MIGRATION_GUIDE = 'docs/cross-host.md#legacy-marketplace-migration'


def marketplace_hold(host, reason, code=None):
    message = (f'{host}: {reason}; manual migration required or host qualification needed. '
               f'Marketplace/plugin modification steps held. See {MIGRATION_GUIDE}')
    if code is not None:
        raise subprocess.CalledProcessError(code, host, output=message)
    raise OSError(message)


def registry_json(path):
    """Absent is fresh; unreadable or unknown registry data is not fresh."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        marketplace_hold('Claude', f'cannot read {path}: {exc}')
    if not isinstance(data, dict):
        marketplace_hold('Claude', f'unsupported registry object in {path}')
    return data


def owned_git(source):
    return source in (SOURCE, f'https://github.com/{SOURCE}',
                      f'https://github.com/{SOURCE}.git', f'git@github.com:{SOURCE}.git',
                      f'ssh://git@github.com/{SOURCE}.git')


def owned_directory(path, manifest, name):
    """A local source must still identify the Kit marketplace and plugin."""
    if not isinstance(path, str) or not Path(path).is_absolute():
        return False
    try:
        data = json.loads((Path(path) / manifest).read_text(encoding='utf-8'))
        return (isinstance(data, dict) and data.get('name') == name
                and any(isinstance(p, dict) and p.get('name') == 'kit'
                        for p in data.get('plugins', [])))
    except (OSError, ValueError, TypeError):
        return False


def claude_registration(output):
    """Inspect both names, settings scopes and installed IDs; never rewrite registries ourselves.

    Reject conflicting records rather than guessing which source the host will use.
    Installed project records outside this invocation's context are not update targets.
    """
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR') or HOME / '.claude')
    sources, scopes, installed = [], [], []
    cwd = Path.cwd().resolve()
    contexts = [cwd]
    if not (cwd / '.git').exists():
        for parent in cwd.parents:
            contexts.append(parent)
            if (parent / '.git').exists():
                break
        else:
            contexts = [cwd]
    settings = [(config / 'settings.json', 'user')]
    for parent in reversed(contexts):
        settings.extend([(parent / '.claude/settings.json', 'project'),
                         (parent / '.claude/settings.local.json', 'local')])
    managed = (Path('/Library/Application Support/ClaudeCode/managed-settings.json')
               if platform.system() == 'Darwin' else Path('/etc/claude-code/managed-settings.json'))
    settings.append((managed, 'managed'))
    for path, scope in settings:
        data = registry_json(path)
        entries = data.get('extraKnownMarketplaces', {})
        enabled = data.get('enabledPlugins', {})
        if not isinstance(entries, dict) or not isinstance(enabled, dict):
            marketplace_hold('Claude', f'unsupported marketplace/plugin settings in {path}')
        if LEGACY_CLAUDE_MARKETPLACE in entries or f'kit@{LEGACY_CLAUDE_MARKETPLACE}' in enabled:
            marketplace_hold('Claude', 'legacy kit@autowork registration (including stale entries)')
        if CLAUDE_MARKETPLACE in entries:
            entry = entries[CLAUDE_MARKETPLACE]
            sources.append(entry.get('source') if isinstance(entry, dict) else None)
        if 'kit' in enabled:
            marketplace_hold('Claude', f'unresolved installed Kit identity in {path}')
        if f'kit@{CLAUDE_MARKETPLACE}' in enabled:
            scopes.append(scope)
    known = registry_json(config / 'plugins/known_marketplaces.json')
    if LEGACY_CLAUDE_MARKETPLACE in known:
        marketplace_hold('Claude', 'legacy autowork marketplace registration (including stale entries)')
    if CLAUDE_MARKETPLACE in known:
        entry = known[CLAUDE_MARKETPLACE]
        sources.append(entry.get('source') if isinstance(entry, dict) else None)
    # Use the documented installed-plugin interface, not a private registry schema.
    rows = host_registry_json(['claude', 'plugin', 'list', '--json'], output)
    if not isinstance(rows, list):
        marketplace_hold('Claude', 'unsupported plugin list --json output')
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            marketplace_hold('Claude', 'unknown installed plugin identity')
        identity = row['id']
        if identity == f'kit@{LEGACY_CLAUDE_MARKETPLACE}':
            marketplace_hold('Claude', 'legacy installed kit@autowork identity')
        if identity == 'kit':
            marketplace_hold('Claude', 'unresolved installed Kit identity')
        if identity != f'kit@{CLAUDE_MARKETPLACE}':
            continue
        scope = row.get('scope')
        if scope not in ('user', 'project', 'local', 'managed') or not isinstance(row.get('enabled'), bool):
            marketplace_hold('Claude', 'unknown installed Kit scope or enabled state')
        if scope in ('project', 'local'):
            project = row.get('projectPath')
            if not isinstance(project, str) or not Path(project).is_absolute():
                marketplace_hold('Claude', 'missing installed Kit projectPath')
            if Path(project).resolve() not in contexts:
                continue
        installed.append(scope)
    if not sources and (scopes or installed):
        marketplace_hold('Claude', 'installed Kit has no known marketplace source')
    for source in sources:
        if not isinstance(source, dict):
            marketplace_hold('Claude', 'missing canonical marketplace source metadata')
        kind = source.get('source')
        owned = ((kind == 'github' and source.get('repo') == SOURCE)
                 or (kind == 'git' and owned_git(source.get('url')))
                 or (kind == 'directory' and owned_directory(source.get('path'),
                     '.claude-plugin/marketplace.json', CLAUDE_MARKETPLACE)))
        if not owned:
            marketplace_hold('Claude', 'canonical marketplace has foreign, unknown or stale source')
    if sources and any(source != sources[0] for source in sources[1:]):
        marketplace_hold('Claude', 'conflicting canonical marketplace source records')
    priority = {'managed': 0, 'user': 1, 'project': 2, 'local': 3}
    scope = max(installed or scopes, key=priority.get, default='user')
    if scope == 'managed' and not installed:
        marketplace_hold('Claude', 'managed Kit declaration requires an administrator-installed plugin')
    return bool(sources), scope, scope in installed


def host_commands(commands, output):
    for argv in commands:
        if output.verbosity > 1:
            output.line('  $ ' + shlex.join(argv), 'command')
        code, text = run_command(argv, output, timeout=120)
        if code:
            raise subprocess.CalledProcessError(code, argv, output=text)


def install_claude(output):
    registered, scope, installed = claude_registration(output)
    commands = []
    if not registered:
        commands.append(['claude', 'plugin', 'marketplace', 'add', SOURCE])
    commands.append(['claude', 'plugin', 'marketplace', 'update', CLAUDE_MARKETPLACE])
    command = ['claude', 'plugin', 'update' if installed else 'install',
               f'{CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE}']
    if scope != 'user' or installed:
        command += ['--scope', scope]
    commands.append(command)
    host_commands(commands, output)
    return f'Kit marketplace qualified; source and {scope} scope preserved'


def host_registry_json(argv, output):
    """Actual-install-only probes: CLI initialization may write cache/auth state."""
    host = argv[0].capitalize()
    if output.verbosity > 1:
        output.line('  $ ' + shlex.join(argv), 'command')
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        marketplace_hold(host, f'required capability {shlex.join(argv)} failed: {exc}')
    if done.returncode:
        marketplace_hold(host, f'required capability {shlex.join(argv)} failed: '
                         f'{failure_summary(done.stdout + done.stderr)} (exit {done.returncode})', done.returncode)
    try:
        return json.loads(done.stdout)
    except ValueError:
        marketplace_hold(host, f'{shlex.join(argv)} returned malformed JSON')


def codex_list(argv, key, output):
    data = host_registry_json(argv, output)
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        marketplace_hold('Codex', f'{shlex.join(argv)} returned unsupported {key} output')
    return data


def install_codex(output):
    names = (LEGACY_CODEX_MARKETPLACE, CODEX_MARKETPLACE)
    rows = codex_list(['codex', 'plugin', 'marketplace', 'list', '--json'],
                     'marketplaces', output)['marketplaces']
    registrations = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name']:
            marketplace_hold('Codex', 'unknown marketplace identity in list output')
        name = row['name']
        if name not in names:
            continue
        if (name in registrations or not isinstance(row.get('root'), str)
                or not row['root'] or not Path(row['root']).is_absolute()):
            marketplace_hold('Codex', f'ambiguous or missing marketplace root for {name}')
        registrations[name] = row
    plugins = {}
    for name in names:
        data = codex_list(['codex', 'plugin', 'list', '--marketplace', name, '--json'],
                          'installed', output)
        if not isinstance(data.get('available'), list) or data['available']:
            marketplace_hold('Codex', f'unsupported filtered plugin list for {name}')
        plugins[name] = data['installed']
        seen = set()
        for plugin in data['installed']:
            if (not isinstance(plugin, dict) or not isinstance(plugin.get('name'), str) or not plugin['name']
                    or plugin.get('marketplaceName') != name
                    or plugin.get('pluginId') != f"{plugin.get('name')}@{name}"
                    or plugin.get('installed') is not True
                    or not isinstance(plugin.get('enabled'), bool)):
                marketplace_hold('Codex', f'unresolved installed identity in {name}')
            if plugin['pluginId'] in seen:
                marketplace_hold('Codex', f'ambiguous installed identity in {name}')
            seen.add(plugin['pluginId'])
            if plugin['name'] != CODEX_PLUGIN:
                continue
            registration = registrations.get(name)
            if (not registration or not plugin.get('marketplaceSource')
                    or plugin['marketplaceSource'] != registration.get('marketplaceSource')
                    or not isinstance(plugin.get('source'), dict)
                    or plugin['source'].get('source') != 'local'
                    or plugin['source'].get('path') != registration['root']):
                marketplace_hold('Codex', f'missing or mismatched installed Kit source in {name}')
    if LEGACY_CODEX_MARKETPLACE in registrations or plugins[LEGACY_CODEX_MARKETPLACE]:
        marketplace_hold('Codex', 'legacy autowork-marketplace effective registration or installed identity')
    canonical = registrations.get(CODEX_MARKETPLACE)
    kind = None
    if canonical:
        source = canonical.get('marketplaceSource')
        if not isinstance(source, dict):
            marketplace_hold('Codex', 'missing canonical marketplaceSource metadata')
        kind = source.get('sourceType')
        owned = ((kind == 'git' and owned_git(source.get('source')))
                 or (kind == 'local' and source.get('source') == canonical['root']
                     and owned_directory(source.get('source'), '.agents/plugins/marketplace.json',
                                         CODEX_MARKETPLACE)))
        if not owned:
            marketplace_hold('Codex', 'canonical marketplace has foreign, unknown or stale source')
    commands = []
    if not canonical:
        commands.append(['codex', 'plugin', 'marketplace', 'add', SOURCE, '--ref', 'main'])
    if kind != 'local':
        commands.append(['codex', 'plugin', 'marketplace', 'upgrade', CODEX_MARKETPLACE])
    # An installed plugin's effective enablement/scope is not ours to rewrite.
    if not any(p['name'] == CODEX_PLUGIN for p in plugins[CODEX_MARKETPLACE]):
        commands.append(['codex', 'plugin', 'add', f'{CODEX_PLUGIN}@{CODEX_MARKETPLACE}'])
    host_commands(commands, output)
    return 'Kit effective marketplace qualified; existing source/context preserved (not all persisted scopes)'


def orbi_version(binary):
    result = subprocess.run([str(binary), '--version'], capture_output=True,
                            text=True, timeout=30)
    version = result.stdout.strip()
    if result.returncode or not re.fullmatch(r'orbi [0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.+-]*', version):
        raise OSError(f'{binary}: Orbi version verification failed; existing installation left untouched')
    return version


def install_orbi(output=None):
    """Install the pinned fork CLI, never setup/tick or replace a deployment bootstrap."""
    output = output or Output()
    destination = Path(os.environ.get('UV_TOOL_BIN_DIR') or BIN).absolute()
    candidates = [shutil.which('orbi'), destination / 'orbi', HOME / '.local/bin/orbi']
    for candidate in candidates:
        if candidate and os.path.lexists(candidate):
            # Even update must not replace an editable CLI serving a pinned deployment.
            return f'{candidate}: {orbi_version(candidate)} (already installed; kept; deployment updates are separate)'
    uv = shutil.which('uv')
    if not uv:
        raise OSError('Orbi requires uv; install uv and retry ./install.sh --only orbi')
    if not shutil.which('git'):
        raise OSError('Orbi requires git to install the pinned fork; install git and retry ./install.sh --only orbi')
    argv = [uv, 'tool', 'install', '--python', '3.14', ORBI_SOURCE]
    output.line('  $ ' + shlex.join(argv), 'command')
    code, text = run_command(argv, output, extra_env={'UV_TOOL_BIN_DIR': str(destination)})
    if code:
        raise OSError(f'Orbi CLI installation failed (exit {code}): {failure_summary(text)}')
    binary = destination / 'orbi'
    return f'{binary}: {orbi_version(binary)}; CLI only, no deployment configured or started'


def orbi_item(output=None):
    system = platform.system()
    return Item('orbi', 'Orbi CLI (no deployment activation)',
                note='requires uv and git for the pinned XelHaku fork; preserves existing installations and source pins',
                missing='' if system in ('Linux', 'Darwin') else f'unsupported Orbi platform: {system}',
                steps=[Step('reuse existing orbi --version, or install a missing CLI with '
                            f'uv tool install --python 3.14 {ORBI_SOURCE}; verify the installed version; '
                            'no setup, scheduler changes or deployment upgrades',
                            run=lambda: install_orbi(output))])


PI_BOLT_INSTALLER = 'https://pi-bolt.opensec.in/install.sh'


def pi_bolt_version(destination):
    """Verify the linked destination executable, never another pi-bolt on PATH."""
    version = subprocess.run([str(destination / 'pi-bolt'), '--version'],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             errors='replace', timeout=30)
    if version.returncode or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+[^\n]*\n?', version.stdout):
        raise OSError('Pi-Bolt destination version verification failed')
    return version.stdout.strip()


def install_pi_bolt(output=None):
    """Always run the official installer; a kept executable silently goes stale."""
    output = output or Output()
    destination = BIN.absolute()
    for command in ('curl', 'sh'):
        if not shutil.which(command):
            raise OSError(f'Pi-Bolt requires {command}; install it and retry --only pi-bolt')

    def run(argv, stage, env=None):
        if output.verbosity > 1:
            output.line('  $ ' + shlex.join(argv), 'command')
        code, text = run_command(argv, output, env)
        if code:
            raise OSError(f'{stage}: {failure_summary(text)} (exit {code})')

    with tempfile.TemporaryDirectory(prefix='kit-pi-bolt-') as directory:
        installer = Path(directory) / 'install.sh'
        installer.touch(mode=0o600)
        run(['curl', '--disable', '--proto', '=https', '--proto-redir', '=https',
             '--tlsv1.2', '--location', '--max-redirs', '5', '--connect-timeout', '15',
             '--max-time', '300', '--max-filesize', '1048576', '--fail', '--silent',
             '--show-error', '--output', str(installer), PI_BOLT_INSTALLER], 'Pi-Bolt installer download failed')
        if not 0 < installer.stat().st_size <= 1048576:
            raise OSError('Pi-Bolt installer download is empty or exceeds its size limit')
        # A non-interactive run takes the default action and never installs OpenSec's
        # optional extensions; the payload keeps upstream's default location.
        env = {'PIBOLT_BIN_DIR': str(destination), 'PIBOLT_YES': '1', 'PIBOLT_EXTENSIONS': 'no'}
        if output.verbosity > 1:
            output.line('  Environment: ' + shlex.join(f'{key}={value}' for key, value in env.items()), 'command')
        try:
            run(['sh', str(installer)], 'Pi-Bolt upstream installer failed', env)
            version = pi_bolt_version(destination)
        except (OSError, subprocess.SubprocessError) as exc:
            raise OSError(f'{exc}; upstream may have left a partial installation; no rollback performed') from exc
    return f'{destination / "pi-bolt"}: {version}'


def pi_bolt_item(output=None):
    system, machine = platform.system(), platform.machine().lower()
    supported = ((system == 'Darwin' and machine in ('arm64', 'aarch64'))
                 or (system == 'Linux' and machine in ('x86_64', 'amd64', 'aarch64', 'arm64')))
    destination = BIN.absolute()
    return Item('pi-bolt', 'Pi-Bolt native Pi executable',
                note='native Pi build; reuses ~/.pi/agent; optional extensions stay off',
                missing='' if supported else f'unsupported Pi-Bolt platform: {system} {machine} (needs GNU/Linux x86-64/ARM64 or macOS Apple silicon)',
                steps=[Step('refresh Pi-Bolt or bootstrap it when absent; '
                            f'download {PI_BOLT_INSTALLER} privately; run unmodified sh installer '
                            f'with PIBOLT_BIN_DIR={destination} PIBOLT_YES=1 PIBOLT_EXTENSIONS=no; '
                            f'verify {destination}/pi-bolt --version',
                            run=lambda: install_pi_bolt(output))])


def skill_folders(folder):
    """Names of the skill folders in ``folder``; None when it exists but cannot be read."""
    try:
        return {p.name for p in folder.iterdir() if (p / 'SKILL.md').is_file()}
    except FileNotFoundError:
        return set()  # no such folder: this side ships nothing, or an older layout
    except OSError:
        return None   # unreadable: cannot prove what it ships


def missing_package_skills(package):
    """Skill folders this checkout ships that the installed package checkout lacks.

    Every install runs `pi-bolt update`, so this is the post-refresh proof: a package that
    still lacks a shipped folder has not reached Pi, and the skill has no
    `/skill:<name>` and no command. It stays the only local freshness signal, so an
    unreadable package directory is never treated as stale.
    """
    shipped, present = skill_folders(ROOT / 'adapters/skills'), skill_folders(package / 'adapters/skills')
    if not shipped or present is None:
        return []
    return sorted(shipped - present)


def install_pi_package(output=None, mode='install'):
    """Refresh the package on every install and update; a kept copy goes stale.

    Keeping a package whose skill folders merely exist leaves edited and removed
    skills live forever, so `install` no longer short-circuits to `kept`: it runs the
    same `pi-bolt update` as `update` and proves the result afterwards. The reason line
    still names what made a copy out of date. A refresh that cannot reach the source
    fails this item with its cause instead of claiming a complete install.
    """
    output = output or Output()
    destination = BIN.absolute()
    binary = destination / 'pi-bolt'
    try:
        pi_bolt_version(destination)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OSError(f'{binary}: usable destination Pi-Bolt required: {exc}; '
                      'run ./install.sh --only pi-bolt,pi') from exc
    package = pi_package(binary=binary)
    action = 'update' if package else 'install'
    reason = ''
    if package:
        stale = missing_package_skills(package)
        if mode == 'update':
            reason = 'update requested'
        elif stale:
            reason = f'skills missing: {", ".join(stale)}'
        else:
            reason = 'every install refreshes the installed package'
    if reason and output.verbosity:
        output.line(f'  refreshing {package} ({reason})')
    argv = [str(binary), action, PI_SOURCE]
    if output.verbosity > 1:
        output.line('  $ ' + shlex.join(argv), 'command')
    code, text = run_command(argv, output, timeout=600)
    if code:
        raise OSError(f'Pi package {action} failed (exit {code}): {failure_summary(text)}; '
                      'repair the reported cause and retry ./install.sh --only pi')
    package = pi_package(binary=binary)
    missing = missing_package_skills(package) if package else []
    if not package or missing:
        detail = f'skills still missing: {", ".join(missing)}' if package else 'package is not registered at an existing directory'
        raise OSError(f'Pi package {action} did not complete: {detail}; '
                      'check Pi-Bolt output and PI_OFFLINE (offline mode skips package updates), '
                      'then retry ./install.sh --only pi')
    return f'{binary}: {action} {PI_SOURCE}'


def items(hermes_args, output=None, mode='install'):
    bolt = pi_bolt_item(output)
    binary = BIN.absolute() / 'pi-bolt'
    pi = Item('pi', 'Kit package for Pi (through Pi-Bolt) + bundled Ponytail',
              note='requires usable Pi-Bolt in the Kit binary directory; never runs stock Pi',
              missing=bolt.missing,
              steps=[Step(f'verify {binary} --version; if unusable run ./install.sh --only pi-bolt,pi; '
                          f'{binary} install {PI_SOURCE} when absent, otherwise always '
                          f'{binary} update {PI_SOURCE} '
                          'so a shipped, edited or removed skill reaches Pi; no kept copy',
                          run=lambda: install_pi_package(output, mode)),
                     Step('enable the package skills and commands in Pi settings', run=enable_pi_package)])
    return [
        bolt,
        pi,
        Item('tx', 'tx tmux session launcher', note='keeps your existing ~/.tmux.conf',
             steps=[Step(f'install {BIN}/tx and completions', run=install_tx)]),
        hermes_item(hermes_args),
        Item('claude', 'Claude Code plugin and full suite + bundled Ponytail', needs='claude',
             steps=[Step('registry/migration status: NOT_CHECKED until actual install; validate both names, '
                         'installed IDs via claude plugin list --json, source and scope; then claude plugin marketplace add '
                         f'{SOURCE} only if fresh; claude plugin marketplace update {CLAUDE_MARKETPLACE}; '
                         f'claude plugin install {CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE} or scoped plugin update',
                         run=lambda: install_claude(output or Output()))]),
        Item('codex', 'Codex plugin and full suite + bundled Ponytail', needs='codex',
             steps=[Step('registry/migration status: NOT_CHECKED until actual install; validate '
                         'codex plugin marketplace list --json and codex plugin list --marketplace NAME --json '
                         'for both names (CLI initialization may write cache/auth state); then '
                         f'codex plugin marketplace add {SOURCE} --ref main only if fresh; '
                         f'codex plugin marketplace upgrade {CODEX_MARKETPLACE} for Git; '
                         f'codex plugin add {CODEX_PLUGIN}@{CODEX_MARKETPLACE} only if not installed',
                         run=lambda: install_codex(output or Output()))]),
        orbi_item(output),
    ]


def describe(item):
    return host_unavailable(item.needs) or item.missing or item.note


# -- choosing ---------------------------------------------------------------------
def choose_curses(all_items, chosen):
    import curses

    def ui(screen):
        curses.curs_set(0)
        row = 0
        while True:
            screen.erase()
            screen.addstr(0, 0, 'Kit installer: Space toggles, a all, n none, Enter installs, q quits')
            for i, item in enumerate(all_items):
                box = '[x]' if item.key in chosen else '[ ]'
                text = f' {box} {item.label:<44} {describe(item)}'
                screen.addstr(2 + i, 0, text[:curses.COLS - 1], curses.A_REVERSE if i == row else 0)
            key = screen.getch()
            if key in (curses.KEY_UP, ord('k')):
                row = (row - 1) % len(all_items)
            elif key in (curses.KEY_DOWN, ord('j')):
                row = (row + 1) % len(all_items)
            elif key == ord(' '):
                item = all_items[row]
                if item.available:
                    chosen.symmetric_difference_update({item.key})
            elif key == ord('a'):
                chosen.update(i.key for i in all_items if i.available)
            elif key == ord('n'):
                chosen.clear()
            elif key in (10, 13, curses.KEY_ENTER):
                return True
            elif key in (ord('q'), 27):
                return False
    return curses.wrapper(ui)


def choose_text(all_items, chosen, read=input, write=print):
    while True:
        write('\nKit installer (all available items are checked):')
        for i, item in enumerate(all_items, 1):
            write(f"  [{'x' if item.key in chosen else ' '}] {i} {item.label:<44} {describe(item)}")
        answer = read('Toggle numbers (e.g. 4 5), a = all, n = none, Enter = install, q = quit: ').strip().lower()
        if answer == '':
            return True
        if answer == 'q':
            return False
        if answer == 'a':
            chosen.update(i.key for i in all_items if i.available)
            continue
        if answer == 'n':
            chosen.clear()
            continue
        for part in answer.replace(',', ' ').split():
            if part.isdigit() and 1 <= int(part) <= len(all_items) and all_items[int(part) - 1].available:
                chosen.symmetric_difference_update({all_items[int(part) - 1].key})


# -- installing -------------------------------------------------------------------
def restart_services(output):
    """Restart active host integrations, never the retired Autowork executor."""
    ctl = os.environ.get('PI_AUTOWORK_SYSTEMCTL', 'systemctl')
    if platform.system() != 'Linux' or not shutil.which(ctl):
        return 'service restarts unavailable (requires Linux user systemd)'
    listed = subprocess.run(
        [ctl, '--user', 'list-units', '--type=service', '--state=active',
         '--plain', '--no-legend', 'hermes-gateway*.service',
         'kit-*.service'], capture_output=True, text=True)
    if listed.returncode:
        raise RuntimeError('cannot discover Kit services: ' + failure_summary(listed.stderr))
    units = sorted({line.split()[0] for line in listed.stdout.splitlines() if line.split()
                    and re.fullmatch(r'(?:hermes-gateway[^/]*|kit-[^/]+)\.service',
                                     line.split()[0])})
    failed = []
    for unit in units:
        argv = [ctl, '--user', 'try-restart', unit]
        output.line('  $ ' + shlex.join(argv), 'command')
        try:
            code, _ = run_command(argv, output)
            if code:
                failed.append(unit)
        except (OSError, subprocess.SubprocessError) as exc:
            output.line(f'  FAILED: {unit}: {exc}', 'failed')
            failed.append(unit)
    if failed:
        raise RuntimeError('service restart failed: ' + ', '.join(failed))
    return 'restarted: ' + ', '.join(units) if units else 'no active Kit services'


def install(all_items, chosen, dry_run=False, output=None, mode='install'):
    output = output or Output()
    results = []
    # Private machine-readable progress for update_bundle.py, separate from native output.
    report = None if dry_run else os.environ.get('AUTOWORK_INSTALL_REPORT')
    if report:
        Path(report).write_text('')

    def record(key, status, detail, code=None):
        results.append((key, status, detail))
        if report:
            with Path(report).open('a') as stream:
                stream.write(json.dumps({'item': key, 'status': status, 'exit': code}) + '\n')

    total = len(chosen)
    current = 0
    started = time.monotonic()
    if output.verbosity or dry_run:
        title = 'Kit suite update' if mode == 'update' else 'Kit full suite installer'
        output.line(title + (' — preview' if dry_run else ''), 'heading')
        output.line('Selected: ' + (', '.join(i.key for i in all_items if i.key in chosen) or 'none'))
    for item in all_items:
        if item.key not in chosen:
            record(item.key, 'skipped', describe(item) if not item.available else 'not chosen')
            continue
        current += 1
        if output.verbosity or dry_run:
            output.line(f'\n[{current}/{total}] {item.label}', 'heading')
        if not item.available or item.refuse:
            record(item.key, 'failed', item.refuse or describe(item), 1)
            if item.refuse:
                output.line(f'  FAILED: {item.refuse}', 'failed')
            continue
        if not item.steps:
            record(item.key, 'skipped', item.note)
            continue
        outcome, detail, exit_code = 'installed', [], 0
        for index, step in enumerate(item.steps, 1):
            if output.verbosity or dry_run:
                output.line(f'  ({index}/{len(item.steps)}) {step.describe}')
            if step.argv and (output.verbosity > 1 or dry_run):
                output.line('  $ ' + shlex.join(step.argv), 'command')
            if dry_run:
                detail.append('dry run')
                continue
            step_started = time.monotonic()
            attempt = 0
            while True:
                attempt += 1
                try:
                    if step.run:
                        message = step.run()
                        detail.append(message)
                        if output.verbosity:
                            output.line('  ' + message)
                        break
                    code, text = run_command(step.argv, output)
                    if code and attempt == 1 and step.retry_on and step.retry_on in text:
                        output.line('  Retrying once: a concurrent writer changed a destination after preflight',
                                    'failed')
                        continue
                    if code:
                        if any(marker in text for marker in step.tolerate):
                            message = 'the goal already holds; kept the existing configuration'
                            detail.append(message)
                            output.line('  ' + message)
                            break
                        outcome, exit_code = 'failed', code
                        cause = failure_summary(text)
                        detail.append(f'{cause} (exit {code})')
                        output.line(f'  FAILED: {step.describe} (exit {code})', 'failed')
                        break
                    detail.append('ok')
                    break
                except (OSError, subprocess.SubprocessError) as exc:
                    outcome = 'failed'
                    exit_code = exc.returncode if isinstance(exc, subprocess.CalledProcessError) else 1
                    cause = (failure_summary(exc.output) if isinstance(exc, subprocess.CalledProcessError)
                             and exc.output else str(exc))
                    if isinstance(exc, subprocess.CalledProcessError):
                        cause += f' (exit {exit_code})'
                    detail.append(cause)
                    output.line(f'  FAILED: {cause}', 'failed')
                    break
            if outcome == 'failed':
                break  # skip this component's dependent steps, not independent items
            if output.verbosity:
                output.line(f'  Done in {time.monotonic() - step_started:.1f}s', 'installed')
        record(item.key, 'planned' if dry_run else outcome, '; '.join(d for d in detail if d),
               None if dry_run else exit_code)
    if chosen:
        output.line('\nRestart active Kit services (always, including unchanged installs)', 'heading')
        if dry_run:
            record('services', 'planned', 'restart active Hermes gateway and kit-* host services; never legacy Autowork runners')
        else:
            try:
                record('services', 'installed', restart_services(output), 0)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                record('services', 'failed', str(exc), 1)
    output.line('\nSummary:', 'heading')
    for key, outcome, detail in results:
        output.line(f'  {key:<9} {outcome:<9} {detail}', outcome)
    counts = {state: sum(outcome == state for _, outcome, _ in results)
              for state in ('installed', 'planned', 'skipped', 'failed')}
    output.line('\n' + ', '.join(f'{count} {state}' for state, count in counts.items())
                + f' — {time.monotonic() - started:.1f}s', 'failed' if counts['failed'] else 'heading')
    if any(key in ('claude', 'codex', 'pi', 'pi-bolt', 'orbi') and outcome == 'installed' for key, outcome, _ in results):
        output.line('Open a new host session to discover the installed skills.')
    return int(bool(counts['failed']))


def pull_checkout(root, write=print, run=subprocess.run):
    """Bring this installer's own Git checkout up to date before installing from it (owner
    request 2026-10-21: `./install.sh` should not install a stale checkout). Fast-forward only;
    a checkout with local changes to tracked files, no upstream, or a detached HEAD is left as
    it is, with a line saying why. Returns True when new commits arrived."""
    def git(*args):
        return run(['git', '-C', str(root), *args], capture_output=True, text=True)
    if git('rev-parse', '--is-inside-work-tree').returncode != 0:
        return False  # not a Git checkout (an unpacked release): nothing to pull
    upstream = git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
    if upstream.returncode != 0 or not upstream.stdout.strip():
        write('Not pulling: this checkout has no upstream branch (detached or local-only); installing it as it is.')
        return False
    if git('status', '--porcelain', '--untracked-files=no').stdout.strip():
        write('Not pulling: this checkout has local changes to tracked files; installing it as it is.')
        return False
    before = git('rev-parse', 'HEAD').stdout.strip()
    pulled = git('pull', '--ff-only', '--quiet')
    if pulled.returncode != 0:
        write('Not pulled: ' + (pulled.stderr.strip().splitlines() or ['git pull --ff-only failed'])[-1]
              + '; installing the checkout as it is.')
        return False
    after = git('rev-parse', 'HEAD').stdout.strip()
    if after == before:
        return False
    write(f'Updated this checkout {before[:8]}..{after[:8]} ({upstream.stdout.strip()}); installing the new version.')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--all', '--full', action='store_true', help='install the full suite for every available host (default)')
    selection.add_argument('--only', help='comma-separated items to install (pi-bolt,pi,tx,hermes,claude,codex,orbi)')
    parser.add_argument('--skip', help='comma-separated items to leave out')
    parser.add_argument('--list', action='store_true', help='show the items and whether each is available')
    parser.add_argument('--dry-run', action='store_true', help='print each command instead of running it')
    parser.add_argument('--menu', action='store_true', help='choose components using the checkbox menu')
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument('-v', '--verbose', action='store_true', help='show exact commands as well as live output (default)')
    verbosity.add_argument('-q', '--quiet', action='store_true', help='show summary and failures only (native terminal prompts remain visible)')
    parser.add_argument('--color', choices=('auto', 'always', 'never'), default='auto',
                        help='color output (default: auto; respects NO_COLOR)')
    for flag in ('--bundle-only', '--no-reload', '--yes-deps'):
        parser.add_argument(flag, action='store_true', help='passed to the Hermes item')
    parser.add_argument('--hermes-home', help='passed to the Hermes item')
    parser.add_argument('--no-pull', action='store_true',
                        help="install this checkout as it is, without first pulling its upstream (git pull --ff-only)")
    parser.add_argument('command', nargs='?', choices=('install', 'update'), default='install',
                        help='install (default) or update the installed suite in place; both run the same items')
    args = parser.parse_args(argv)
    output = Output(args.color, 0 if args.quiet else 2)
    if not (args.no_pull or args.list or args.dry_run or os.environ.get('AUTOWORK_INSTALL_PULLED')
            or os.environ.get('AUTOWORK_INSTALL_NO_PULL')):
        if pull_checkout(ROOT, write=output.line):
            # The pulled installer may differ from this one: run it, once.
            os.execvpe('bash', ['bash', str(ROOT / 'install.sh'), *(sys.argv[1:] if argv is None else argv)],
                       dict(os.environ, AUTOWORK_INSTALL_PULLED='1'))
    hermes = [f for f, on in (('--bundle-only', args.bundle_only), ('--no-reload', args.no_reload),
                              ('--yes-deps', args.yes_deps), ('--dry-run', args.dry_run)) if on]
    if args.hermes_home:
        hermes += ['--hermes-home', args.hermes_home]
    all_items = items(hermes, output, mode=args.command)
    keys = [i.key for i in all_items]
    for given in (args.only, args.skip):
        unknown = [k for k in (given or '').split(',') if k and k not in keys]
        if unknown:
            parser.error(f'unknown item(s): {", ".join(unknown)}; choose from {", ".join(keys)}')
    if args.list:
        for item in all_items:
            output.line(f"  {item.key:<9} {'available' if item.available else 'unavailable':<12} {item.label}"
                  + (f' ({describe(item)})' if describe(item) else ''),
                        'installed' if item.available else 'skipped')
        return 0
    chosen = {i.key for i in all_items if i.available}
    if args.only:
        chosen = {k for k in args.only.split(',') if k}
    if args.skip:
        chosen -= set(args.skip.split(','))
    menu = args.menu
    if menu and not (sys.stdin.isatty() and sys.stdout.isatty()) and os.environ.get('AUTOWORK_INSTALL_UI') != 'text':
        parser.error('no terminal for the menu; choose with --all, --only or --skip (see --list)')
    if menu:
        try:
            go = choose_curses(all_items, chosen) if os.environ.get('AUTOWORK_INSTALL_UI') != 'text' \
                else choose_text(all_items, chosen, write=output.line)
        except Exception:  # no usable terminal for curses: the numbered menu
            go = choose_text(all_items, chosen, write=output.line)
        if not go:
            print('Nothing installed.')
            return 0
    return install(all_items, chosen, dry_run=args.dry_run, output=output, mode=args.command)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nInstallation interrupted; completed steps remain installed.', file=sys.stderr)
        raise SystemExit(130)
