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
up to date (`git pull --ff-only` of its upstream) and then run the on-disk installer.
Local staged, unstaged and non-ignored untracked changes are stashed first and kept
for manual recovery; the stash ID and restore command are always printed, even in
quiet mode. A missing upstream or status/stash/pull failure aborts before installing
or restarting services. Unpacked non-Git releases remain supported. --no-pull or
KIT_INSTALL_NO_PULL bypasses stashing and pulling; --help, --list and --dry-run do neither.

Each host item runs its own supported install command; a host whose CLI is not
installed is skipped and says so, and fails when named with --only. Pi-Bolt is
the only Pi harness Kit installs; its destination executable manages the Kit package.
The Pi package is refreshed on both `install` and `update` even when its files look
complete; Pi-Bolt checks release metadata and skips a proven current native build.
Orbi selection authorizes stopping, updating and restarting verified local Linux
deployments, including paused deployments. Use --skip orbi to leave them alone.
With no deployment, bootstrap/reuse the pinned CLI. Pi-Bolt bootstraps or refreshes the upstream
native Pi build and never installs its optional extensions. Hermes options
(--hermes-home, --bundle-only, --no-reload, --yes-deps) apply to the Hermes item.
Refresh success alone is not a change: compare installed identity, content, links and settings.
Only complete changed payloads with proven active consumers are eligible for one restart;
Hermes owns its native gateway decisions. Unknown evidence holds with a manual next action.
Standard library only.
"""
import argparse
import codecs
from contextlib import contextmanager, nullcontext
import fcntl
import hashlib
import importlib.util
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
BIN = Path(os.environ.get('KIT_BIN_DIR') or HOME / '.local' / 'bin')
ITEM_KEYS = ('pi-bolt', 'pi', 'tx', 'hermes', 'claude', 'codex', 'orbi')

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
              'skipped': '33', 'warning': '33', 'planned': '36', 'command': '2'}

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


def run_command(argv, output, extra_env=None, timeout=None, receipt=None):
    """Stream both child channels, including prompts without a trailing newline.

    Keep a bounded diagnostic tail for quiet failures; stdin remains inherited.
    Quiet mode still shows native prompts/output when input is a terminal.
    """
    env = dict(os.environ, PYTHONUNBUFFERED='1', **(extra_env or {}))
    if not extra_env or 'KIT_INSTALL_LOCK_FD' not in extra_env:
        env.pop('KIT_INSTALL_LOCK_FD', None)
    if not output.color:
        env['NO_COLOR'] = '1'
    stream = output.verbosity > 0 or sys.stdin.isatty()
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    tail = ''
    # Native receipts can exceed the diagnostic tail (many profiles/commands).
    # Spool only when requested; ordinary commands retain bounded diagnostics.
    captured = tempfile.TemporaryFile(mode='w+', encoding='utf-8') if receipt is not None else None
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
                              pass_fds=tuple(fd for fd in (terminal,
                                  int(env['KIT_INSTALL_LOCK_FD']) if env.get('KIT_INSTALL_LOCK_FD') else None)
                                  if fd is not None)) as child:
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
                        if captured is not None:
                            captured.write(text)
                        tail = (tail + text)[-16384:]
                        if stream:
                            output.raw(text)
                text = decoder.decode(b'', final=True)
                if captured is not None:
                    captured.write(text)
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
        if captured is not None:
            try:
                captured.seek(0)
                receipt.update(terminal_receipt(captured.read()) or {})
            finally:
                captured.close()
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


def terminal_receipt(text):
    """Read a final JSON receipt, never infer a native decision from log wording."""
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
    return receipt


def failure_summary(text):
    """Extract a final structured receipt, not its closing brace, from native logs."""
    receipt = terminal_receipt(text)
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
    refusal_warning: bool = False
    refuse: str = ''                # why the selected options cannot be honored
    inputs: object = None           # read service-consumed installed paths, never refresh them

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
    resource of that type. An empty filter survives ``pi install`` and
    ``pi update``, so the package stays installed but filtered: no commands and no ``/skill:<name>``.
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


def pi_package(source=PI_SOURCE, binary=None, strict=False):
    """The directory Pi installed this package source in, or None."""
    binary = binary or BIN.absolute() / 'pi-bolt'
    try:
        listed = subprocess.run([str(binary), 'list'], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=60)
        if strict and listed.returncode:
            raise OSError(f'{binary} list failed (exit {listed.returncode}); installed package path unverified')
        lines = listed.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        if strict:
            raise
        return None
    for i, line in enumerate(lines):
        # Pi marks a package with a filter as `<source> (filtered)`.
        if line.split()[:1] == [source] and i + 1 < len(lines):
            package = Path(lines[i + 1].strip())
            if package.is_dir():
                return package
    return None


def set_aside(path, *, backup_dir=None):
    """Move a file or symlink to .bak/.bak.N. With a separate backup_dir,
    use increasing numbers and keep only the newest five; otherwise keep all."""
    previous = []
    if backup_dir is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
        pattern = re.compile(re.escape(path.name) + r'\.bak(?:\.(\d+))?')
        for candidate in backup_dir.iterdir():
            match = pattern.fullmatch(candidate.name)
            if match:
                previous.append((int(match[1] or 0), candidate))
        previous.sort()
        number = previous[-1][0] + 1 if previous else 0
        backup = backup_dir / (path.name + '.bak' + (f'.{number}' if number else ''))
    else:
        backup, n = path.with_name(path.name + '.bak'), 1
        while backup.exists() or backup.is_symlink():
            backup, n = path.with_name(f'{path.name}.bak.{n}'), n + 1
    if backup_dir is not None:
        # KIT_BIN_DIR may be on another filesystem. shutil.move copies
        # files or recreates symlinks before unlinking the original on EXDEV.
        shutil.move(path, backup)
    else:
        os.replace(path, backup)
    for _, old in previous[:-4]:
        old.unlink()
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
        note = ''
        if target.exists() or target.is_symlink():
            backup = set_aside(target, backup_dir=HOME / '.local/state/kit/backups')
            note = f' (the old one is {backup})'
        shutil.copy2(source, target)
        target.chmod(0o755)
        done.append(f'{target} written{note}')  # the summary row already says "installed"

    for shell, folder, name in (('bash', HOME / '.local/share/bash-completion/completions', 'tx'),
                                ('zsh', HOME / '.zsh/completions', '_tx'),
                                ('fish', HOME / '.config/fish/completions', 'tx.fish')):
        dest = folder / name
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):
            done.append(f'{shell} completion kept')
            continue
        text = subprocess.run(['bash', str(target), 'completion', shell],
                              capture_output=True, check=True, timeout=30).stdout
        if dest.is_file() and dest.read_bytes() == text:
            done.append(f'{shell} completion kept')
            continue
        note, status = '', 'written'
        if dest.is_file():
            note, status = f' (the old one is {set_aside(dest)})', 'replaced'
        folder.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(text)
        done.append(f'{shell} completion {status}{note}')
    kept = []
    for src, dest in ((ROOT / 'tmux/tmux.conf', HOME / '.tmux.conf'),
                      (ROOT / 'tmux/style.tmux', HOME / '.tmux/style.tmux'),
                      (ROOT / 'tmux/git-status.sh', HOME / '.tmux/git-status.sh'),
                      (ROOT / 'tmux/short-path.sh', HOME / '.tmux/short-path.sh'),
                      (ROOT / 'tmux/copy.sh', HOME / '.tmux/copy.sh')):
        if dest.exists() or dest.is_symlink():
            kept.append(dest.name)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text()
        if dest.name == '.tmux.conf':  # point at the installed helpers
            # copy-command is a shell command inside a tmux double-quoted string.
            copy_command = shlex.quote(str(HOME / '.tmux/copy.sh'))
            copy_command = re.sub(r'([\\"$])', r'\\\1', copy_command)
            text = text.replace('~/.tmux/copy.sh', copy_command)
            text = text.replace('~/.tmux/', f'{HOME}/.tmux/')
        dest.write_text(text)
        if dest.suffix == '.sh':
            dest.chmod(0o755)
        done.append(f'installed {dest}')
    if kept:
        done.append('kept your existing ' + ', '.join(kept))
    return '; '.join(done)


def hermes_home(hermes_args):
    """(home, given): the Hermes home the item works on, and whether it was named."""
    given = hermes_args[hermes_args.index('--hermes-home') + 1] if '--hermes-home' in hermes_args else ''
    named = given or os.environ.get('HERMES_HOME')
    return Path(named or HOME / '.hermes'), bool(named)


def hermes_identity_reader():
    import importlib.util
    spec = importlib.util.spec_from_file_location('install_identity', ROOT / 'scripts/update_bundle.py')
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    return updater


def hermes_installed(hermes_args, updater):
    """Discover managed clones under either identity without duplicating installation."""
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
        updater = hermes_identity_reader()
    except (ValueError, OSError) as error:
        return Item('hermes', label, needs='hermes', refuse=str(error))
    try:
        home = hermes_installed(hermes_args, updater)
    except updater.MissingManifestPyYAML:
        retry = ['./install.sh', '--only', 'hermes']
        if '--hermes-home' in hermes_args:
            index = hermes_args.index('--hermes-home')
            retry.append('--hermes-home=' + hermes_args[index + 1])
        return Item('hermes', label, needs='hermes', refusal_warning=True,
                    refuse="Hermes was not updated. The installer's python3 could not load PyYAML, "
                           "so Kit stopped before changing the plugin. Make PyYAML available to that "
                           "interpreter, verify with python3 -c 'import yaml', then retry "
                           + shlex.join(retry))
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
    """Inspect Kit settings scopes and installed IDs; never rewrite registries ourselves.

    Reject conflicting records rather than guessing which source the host will use.
    Installed project records outside this invocation's context are not update targets.
    """
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR') or HOME / '.claude')
    sources, scopes, installed = [], [], []
    records, declarations = {}, {}
    enabled_records = []
    payload_paths, identities = [], []
    settings_paths = {}
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
        for name, entry in entries.items():
            records.setdefault(name, []).append(entry.get('source') if isinstance(entry, dict) else None)
            declarations.setdefault(name, []).append(scope)
            settings_paths.setdefault(name, []).append(path)
        enabled_records.extend((identity, scope) for identity in enabled)
        if CLAUDE_MARKETPLACE in entries:
            entry = entries[CLAUDE_MARKETPLACE]
            sources.append(entry.get('source') if isinstance(entry, dict) else None)
        if 'kit' in enabled:
            marketplace_hold('Claude', f'unresolved installed Kit identity in {path}')
        if f'kit@{CLAUDE_MARKETPLACE}' in enabled:
            scopes.append(scope)
    known = registry_json(config / 'plugins/known_marketplaces.json')
    for name, entry in known.items():
        records.setdefault(name, []).append(entry.get('source') if isinstance(entry, dict) else None)
    candidates = [name for name, entries in records.items() if name != CLAUDE_MARKETPLACE
                  and any(claude_git(source) for source in entries)]
    if len(candidates) > 1:
        marketplace_hold('Claude', 'ambiguous official Git registrations')
    mismatch = candidates[0] if candidates else None
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
        identities.append({key: row.get(key) for key in ('id', 'scope', 'enabled', 'version', 'projectPath')})
        install_path = row.get('installPath')
        if isinstance(install_path, str) and Path(install_path).is_absolute():
            payload_paths.append(Path(install_path))
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
    replacement = []
    if mismatch:
        if not all(claude_git(source) and source == records[mismatch][0] for source in records[mismatch]):
            marketplace_hold('Claude', 'conflicting mismatched marketplace source records')
        paths = [config / 'plugins/known_marketplaces.json', *settings_paths.get(mismatch, [])]
        if (len(declarations.get(mismatch, [])) > 1
                or any(path.exists() and (not os.access(path, os.W_OK)
                                          or not os.access(path.parent, os.W_OK)) for path in paths)):
            marketplace_hold('Claude', 'ambiguous or unwritable replacement registration')
        affected_scopes = declarations.get(mismatch, [])[:]
        for identity, declared_scope in enabled_records:
            if identity.endswith('@' + mismatch):
                if identity != f'{CLAUDE_PLUGIN}@{mismatch}':
                    marketplace_hold('Claude', 'replacement could remove another plugin declaration')
                affected_scopes.append(declared_scope)
        for row in rows:
            if not row['id'].endswith('@' + mismatch):
                continue
            if row['id'] != f'{CLAUDE_PLUGIN}@{mismatch}':
                marketplace_hold('Claude', 'replacement could uninstall another plugin')
            installed_scope = row.get('scope')
            if installed_scope not in ('user', 'project', 'local') or not isinstance(row.get('enabled'), bool):
                marketplace_hold('Claude', 'unknown or managed replacement plugin scope')
            if installed_scope in ('project', 'local') and row.get('projectPath') != str(cwd):
                marketplace_hold('Claude', 'replacement affects a plugin outside the current project')
            affected_scopes.append(installed_scope)
        affected_scopes = set(affected_scopes or ['user'])
        if len(affected_scopes) != 1 or not affected_scopes <= {'user', 'project', 'local'}:
            marketplace_hold('Claude', 'ambiguous or managed replacement scope')
        replacement_scope = affected_scopes.pop()
        replacement = [['claude', 'plugin', 'marketplace', 'remove', mismatch, '--scope', replacement_scope]]
        if not installed and not scopes:
            scope = replacement_scope
    return MarketplaceState(bool(sources), scope in installed, scope=scope,
                            mismatch=mismatch, replacement=replacement, paths=payload_paths,
                            identity=[identities, records, enabled_records])


def host_commands(commands, output):
    for argv in commands:
        if output.verbosity > 1:
            output.line('  $ ' + shlex.join(argv), 'command')
        code, text = run_command(argv, output, timeout=120)
        if code:
            raise subprocess.CalledProcessError(code, argv, output=text)


@dataclass
class MarketplaceState:
    registered: bool
    installed: bool
    scope: str = 'user'
    kind: str = 'git'
    mismatch: str | None = None
    replacement: list = field(default_factory=list)
    paths: list = field(default_factory=list)
    identity: object = None


def claude_git(source):
    return isinstance(source, dict) and (
        (source.get('source') == 'github' and source.get('repo') == SOURCE)
        or (source.get('source') == 'git' and owned_git(source.get('url'))))


def host_changes(commands, read, output, before=None):
    host = commands[0][0]
    try:
        host_commands(commands, output)
    except (OSError, subprocess.SubprocessError) as exc:
        if before is not None:
            exc.installed_evidence = before
        try:
            observed = read(output)
            evidence = marketplace_evidence(observed)
            if before:
                evidence['inputs'] = {**before['inputs'], **evidence['inputs']}
                evidence['directories'] = sorted(set(before.get('directories', []))
                                                  | set(evidence.get('directories', [])))
            exc.installed_evidence = evidence
            detail = (f'canonical={observed.registered}, mismatched={observed.mismatch}, '
                      f'installed={observed.installed}')
        except (OSError, subprocess.SubprocessError) as probe:
            detail = f'readback held: {probe}'
        message = (f'{host}: partial state after {shlex.join(commands[-1])}: {detail}; '
                   f'{getattr(exc, "output", None) or exc}; repair the cause and rerun '
                   f'./install.sh --only {host}')
        if isinstance(exc, subprocess.CalledProcessError):
            raise subprocess.CalledProcessError(exc.returncode, exc.cmd, output=message) from exc
        raise OSError(message) from exc


def marketplace_readback(host, read, output, before=None):
    try:
        return read(output)
    except (OSError, subprocess.SubprocessError) as exc:
        if before is not None:
            exc.installed_evidence = before
        message = (f'{host}: partial state: post-change readback failed; '
                   f'{getattr(exc, "output", None) or exc}; observed state is unknown; '
                   f'repair the cause and rerun ./install.sh --only {host}')
        if isinstance(exc, subprocess.CalledProcessError):
            raise subprocess.CalledProcessError(exc.returncode, exc.cmd, output=message) from exc
        raise OSError(message) from exc


def reconcile_marketplace(host, read, add, output):
    """One replacement at most; qualify readback before update/upgrade."""
    state = read(output)
    before = marketplace_evidence(state)
    scope = state.scope

    if not state.registered and not state.mismatch:
        # A nonzero add is not identity evidence either. Read before deciding
        # whether this is an already-present source or an actual add failure.
        try:
            host_commands([add], output)
        except subprocess.CalledProcessError as exc:
            state = marketplace_readback(host, read, output, before=before)
            if not state.registered and not state.mismatch:
                raise subprocess.CalledProcessError(exc.returncode, exc.cmd,
                    output=f'{host}: partial state: canonical absent; {exc.output}; repair and rerun') from exc
        else:
            state = marketplace_readback(host, read, output, before=before)
        scope = state.scope
    if state.mismatch:
        scope = state.scope
        previous_name = state.mismatch
        host_changes(state.replacement, read, output, before=before)
        state = marketplace_readback(host, read, output, before=before)
        if state.mismatch:
            marketplace_hold(host, f'partial state: mismatched registration {state.mismatch} remains; '
                             'replacement attempted once; reconcile ownership and rerun')
        if host == 'claude':
            remaining = host_registry_json(['claude', 'plugin', 'list', '--json'], output)
            removed = isinstance(remaining, list) and all(isinstance(row, dict)
                and isinstance(row.get('id'), str) and not row['id'].endswith('@' + previous_name)
                for row in remaining)
        else:
            remaining = codex_list(['codex', 'plugin', 'list', '--marketplace', previous_name, '--json'],
                                   'installed', output)
            removed = remaining['installed'] == []
        if not removed:
            marketplace_hold(host, f'partial state: plugins remain for {previous_name}; repair and rerun')
        if not state.registered:
            host_changes([add + (['--scope', scope] if host == 'claude' and scope != 'user' else [])], read, output, before=before)
            state = marketplace_readback(host, read, output, before=before)
    if not state.registered or state.mismatch:
        marketplace_hold(host, 'partial state: canonical source/name absent after add/readback; '
                         'repair host source registration and rerun')
    state.scope = scope
    state.before = before
    return state


def install_claude(output):
    state = reconcile_marketplace('claude', claude_registration,
        ['claude', 'plugin', 'marketplace', 'add', SOURCE], output)
    host_changes([['claude', 'plugin', 'marketplace', 'update', CLAUDE_MARKETPLACE]],
                 claude_registration, output, before=state.before)
    command = ['claude', 'plugin', 'update' if state.installed else 'install',
               f'{CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE}']
    if state.scope != 'user' or state.installed:
        command += ['--scope', state.scope]
    host_changes([command], claude_registration, output, before=state.before)
    final = marketplace_readback('claude', claude_registration, output, before=state.before)
    if not final.registered or not final.installed or final.mismatch or final.scope != state.scope:
        marketplace_hold('Claude', 'partial state: expected installed ID/scope not verified; repair and rerun')
    return Refresh(f'{CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE} verified; source and {state.scope} scope preserved',
                   state.before, marketplace_evidence(final))


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


def codex_registration(output):
    rows = codex_list(['codex', 'plugin', 'marketplace', 'list', '--json'],
                     'marketplaces', output)['marketplaces']
    candidates = [row['name'] for row in rows if isinstance(row, dict)
                  and isinstance(row.get('name'), str) and row['name'] != CODEX_MARKETPLACE
                  and isinstance(row.get('marketplaceSource'), dict)
                  and row['marketplaceSource'].get('sourceType') == 'git'
                  and owned_git(row['marketplaceSource'].get('source'))]
    if len(candidates) > 1:
        marketplace_hold('Codex', 'ambiguous official Git registrations')
    mismatch = candidates[0] if candidates else None
    names = (CODEX_MARKETPLACE, *candidates)
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
    replacement = []
    if mismatch:
        if any(p['name'] != CODEX_PLUGIN for p in plugins[mismatch]):
            marketplace_hold('Codex', 'replacement could remove another plugin')
        codex_writable_registration(mismatch, registrations[mismatch], output)
        if plugins[mismatch]:
            replacement.append(['codex', 'plugin', 'remove', f'{CODEX_PLUGIN}@{mismatch}'])
        replacement.append(['codex', 'plugin', 'marketplace', 'remove', mismatch])
    return MarketplaceState(bool(canonical),
        any(p['name'] == CODEX_PLUGIN for p in plugins[CODEX_MARKETPLACE]),
        kind=kind or 'git', mismatch=mismatch, replacement=replacement,
        paths=[Path(canonical['root'])] if canonical else [],
        identity=[{key: canonical.get(key) for key in ('name', 'root', 'marketplaceSource')} if canonical else None,
                  [{key: row.get(key) for key in ('pluginId', 'installed', 'enabled', 'source', 'marketplaceSource')}
                   for row in plugins[CODEX_MARKETPLACE]]])


def codex_config_layers(output):
    """Native config/read supplies provenance missing from marketplace list JSON.

    No model/session is started. Bound all reads and always reap the stdio server.
    """
    if output.verbosity > 1:
        output.line('  $ codex app-server (config/read includeLayers, current cwd)', 'command')
    with tempfile.TemporaryFile() as errors:
        with subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=errors) as process:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    pending = b''
                    def request(identity, method, params):
                        nonlocal pending
                        process.stdin.write((json.dumps({'id': identity, 'method': method,
                                                        'params': params}) + '\n').encode())
                        process.stdin.flush()
                        deadline = time.monotonic() + 30
                        while time.monotonic() < deadline:
                            if b'\n' not in pending:
                                if not selector.select(max(0, deadline - time.monotonic())):
                                    break
                                chunk = os.read(process.stdout.fileno(), 65536)
                                if not chunk:
                                    break
                                pending += chunk
                                continue
                            line, pending = pending.split(b'\n', 1)
                            row = json.loads(line)
                            if not isinstance(row, dict):
                                raise ValueError('unknown app-server response')
                            if row.get('id') == identity:
                                if not isinstance(row.get('result'), dict):
                                    raise ValueError(f'{method} failed: {row.get("error")}')
                                return row['result']
                        raise ValueError(f'{method} timed out or closed')
                    init = request(1, 'initialize', {'clientInfo': {'name': 'kit-installer', 'version': '1'},
                                                   'capabilities': {'experimentalApi': True}})
                    result = request(2, 'config/read', {'includeLayers': True, 'cwd': str(Path.cwd())})
                    return init, result
            except (OSError, ValueError) as exc:
                marketplace_hold('Codex', f'cannot qualify writable config layers: {exc}')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def codex_writable_registration(name, registration, output):
    init, result = codex_config_layers(output)
    home = init.get('codexHome')
    layers = result.get('layers')
    if not isinstance(home, str) or not Path(home).is_absolute() or not isinstance(layers, list):
        marketplace_hold('Codex', 'missing config layer provenance')
    expected = {'type': 'user', 'file': str(Path(home) / 'config.toml'), 'profile': None}
    config = result.get('config')
    effective = config.get('marketplaces', {}) if isinstance(config, dict) else {}
    effective = effective.get(name) if isinstance(effective, dict) else None
    if (not isinstance(effective, dict) or effective.get('source_type') != 'git'
            or effective.get('source') != registration['marketplaceSource']['source']):
        marketplace_hold('Codex', 'effective configuration and marketplace source disagree')
    matches = []
    for layer in layers:
        if not isinstance(layer, dict) or not isinstance(layer.get('config'), dict):
            marketplace_hold('Codex', 'unknown config layer')
        if layer.get('disabledReason'):
            continue
        plugins = layer['config'].get('plugins', {})
        if not isinstance(plugins, dict):
            marketplace_hold('Codex', 'unknown plugin config layer')
        for identity in plugins:
            if identity.endswith('@' + name) and (identity != f'{CODEX_PLUGIN}@{name}'
                                                  or layer.get('name') != expected):
                marketplace_hold('Codex', 'replacement affects another plugin or non-user plugin scope')
        entries = layer['config'].get('marketplaces', {})
        if not isinstance(entries, dict):
            marketplace_hold('Codex', 'unknown marketplace config layer')
        for key, entry in entries.items():
            if key.casefold() == name.casefold():
                matches.append((key, entry, layer.get('name')))
    source = registration['marketplaceSource']
    if (len(matches) != 1 or matches[0][0] != name or matches[0][2] != expected
            or not isinstance(matches[0][1], dict)
            or matches[0][1].get('source_type') != 'git'
            or matches[0][1].get('source') != source['source']
            or not os.access(Path(home), os.W_OK)
            or (Path(home, 'config.toml').exists() and not os.access(Path(home, 'config.toml'), os.W_OK))):
        marketplace_hold('Codex', 'replacement is not an unambiguous writable base-user Git registration')


def install_codex(output):
    state = reconcile_marketplace('codex', codex_registration,
        ['codex', 'plugin', 'marketplace', 'add', SOURCE, '--ref', 'main'], output)
    commands = []
    if state.kind != 'local':
        commands.append(['codex', 'plugin', 'marketplace', 'upgrade', CODEX_MARKETPLACE])
    if not state.installed:
        commands.append(['codex', 'plugin', 'add', f'{CODEX_PLUGIN}@{CODEX_MARKETPLACE}'])
    if commands:
        host_changes(commands, codex_registration, output, before=state.before)
    final = marketplace_readback('codex', codex_registration, output, before=state.before)
    if not final.registered or not final.installed or final.mismatch:
        marketplace_hold('Codex', 'partial state: expected installed ID not verified; repair and rerun')
    return Refresh(f'{CODEX_PLUGIN}@{CODEX_MARKETPLACE} verified; existing source/context preserved',
                   state.before, marketplace_evidence(final))


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
            return f'{candidate}: {orbi_version(candidate)} (already installed; kept)'
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


def refresh_orbi_fleet(*, report_progress=None):
    path = ROOT / 'skills/orbi/scripts/orbi_control.py'
    spec = importlib.util.spec_from_file_location('kit_installer_orbi_control', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    try:
        # Match the lifecycle helper's regular `python -B` entry point.
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
        del sys.modules[spec.name]
    return module.installer_fleet(module.Context(noninteractive=True), report_progress=report_progress)


def orbi_fleet_summary(receipt):
    if receipt['status'] == 'no_deployments':
        return 'No installed Orbi deployment verified; CLI only'
    lines = [f"Orbi fleet {receipt['status']}"]
    if 'error' in receipt:
        error = receipt['error']
        where = ' '.join(error[key] for key in ('config', 'unit', 'step') if error.get(key))
        lines[0] += f": {where + ': ' if where else ''}{error['message']}"
        if error.get('fix'):
            lines.append(error['fix'])
    for row in receipt['deployments']:
        steps = ', '.join(step['step'] + (' ' + step['unit'] if 'unit' in step else '')
                          for step in row['steps'])
        lines.append(f"{row['config']}: {row['status']} ({row.get('engine_update', 'not applied')})"
                     + (f'; completed: {steps}' if steps else '')
                     + (f"; {row['recovery']}" if receipt['status'] != 'completed' else ''))
    if 'recovery' in receipt:
        lines.append(receipt['recovery'])
    return '\n  '.join(lines)


def orbi_item(output=None):
    return Item('orbi', 'Orbi host deployment refresh / CLI bootstrap',
                note='stop, update and restart verified local Linux deployments, including paused ones; --skip orbi opts out',
                missing='unsupported Orbi platform: Windows' if platform.system() == 'Windows' else '',
                steps=[Step('verify local managers and ownership; stop deployments without natural drain, '
                            'pin and validate the newest official stable release, then restart scheduling '
                            'and authorized services (even if paused or already current); '
                            'macOS has no lifecycle mutations; with no deployment, keep the CLI or run '
                            f'uv tool install --python 3.14 {ORBI_SOURCE}', run=refresh_orbi_fleet)],
                inputs=lambda: installed_evidence([Path(shutil.which('orbi') or
                    Path(os.environ.get('UV_TOOL_BIN_DIR') or BIN).absolute() / 'orbi')]))


PI_BOLT_INSTALLER = 'https://pi-bolt.opensec.in/install.sh'


def pi_bolt_version(destination):
    """Verify the linked destination executable, never another pi-bolt on PATH."""
    version = subprocess.run([str(destination / 'pi-bolt'), '--version'],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             errors='replace', timeout=30)
    if version.returncode or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+[^\n]*\n?', version.stdout):
        raise OSError('Pi-Bolt destination version verification failed')
    return version.stdout.strip()


PI_BOLT_RELEASES = 'https://api.github.com/repos/opensec-git/Pi-Bolt/releases'
PI_BOLT_TAG = r'bolt-v([0-9]+\.[0-9]+\.[0-9]+)'


def pi_bolt_release(output):
    """Upstream stable latest / explicit tag / highest numeric tag in 30 beta releases."""
    requested = os.environ.get('PIBOLT_VERSION') or 'latest'
    channel = os.environ.get('PIBOLT_CHANNEL') or 'stable'
    source = os.environ.get('PIBOLT_SOURCE') or 'auto'
    prefix = os.environ.get('PREFIX', '')
    termux = platform.system() == 'Linux' and prefix and (
        os.environ.get('TERMUX_VERSION') or prefix.endswith('/com.termux/files/usr'))
    # Leave alternate payload sources, install actions and invalid overrides to upstream.
    if (termux or os.environ.get('PIBOLT_DOWNLOAD_BASE')
            or os.environ.get('PIBOLT_NO_PATH') == '1' or os.environ.get('PIBOLT_LAUNCHER') == '1'
            or os.environ.get('PIBOLT_PASEO') not in (None, '', 'no')
            or source not in ('auto', 'npm', 'github') or channel not in ('stable', 'beta')
            or (requested != 'latest' and not re.fullmatch(PI_BOLT_TAG, requested))):
        return None
    beta_list = requested == 'latest' and channel == 'beta'
    if requested != 'latest':
        url = f'{PI_BOLT_RELEASES}/tags/{requested}'
    elif beta_list:
        url = f'{PI_BOLT_RELEASES}?per_page=30'
    else:
        url = f'{PI_BOLT_RELEASES}/latest'
    # GitHub includes asset metadata for every row; the 30-release listing can exceed 1 MiB.
    max_bytes = (8 if beta_list else 1) * 1024 * 1024
    # Curl before 8.4 cannot enforce --max-filesize during an unknown-length transfer.
    # Rate and time bound that transfer too; the size check rejects any oversized result.
    rate = '512K' if beta_list else '64K'
    try:
        with tempfile.TemporaryDirectory(prefix='kit-pi-bolt-check-') as directory:
            metadata = Path(directory) / 'release.json'
            metadata.touch(mode=0o600)
            argv = ['curl', '--disable', '--proto', '=https', '--proto-redir', '=https',
                    '--tlsv1.2', '--location', '--max-redirs', '5', '--connect-timeout', '10',
                    '--max-time', '30', '--max-filesize', str(max_bytes), '--limit-rate', rate,
                    '--fail', '--silent', '--show-error', '--header', 'Accept: application/vnd.github+json',
                    '--output', str(metadata), url]
            if output.verbosity > 1:
                output.line('  $ ' + shlex.join(argv), 'command')
            code, text = run_command(argv, output, timeout=40)
            if code:
                raise OSError(f'{failure_summary(text)} (exit {code})')
            if not 0 < metadata.stat().st_size <= max_bytes:
                raise ValueError('empty or oversized release metadata')
            data = json.loads(metadata.read_text(encoding='utf-8'))
        rows = data if beta_list else [data]
        if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
            raise ValueError('malformed release metadata')
        tags = []
        for row in rows:
            tag = row.get('tag_name')
            if not isinstance(tag, str) or not isinstance(row.get('draft'), bool) or not isinstance(row.get('prerelease'), bool):
                raise ValueError('malformed release metadata')
            match = re.fullmatch(PI_BOLT_TAG, tag)
            if match and not row['draft']:
                if requested != 'latest' and tag != requested:
                    raise ValueError('release tag does not match request')
                if requested == 'latest' and not beta_list and row['prerelease']:
                    raise ValueError('stable metadata selects a prerelease')
                tags.append(match.group(1))
        if not tags:
            raise ValueError('no Pi-Bolt release tag in metadata')
        return max(tags, key=lambda version: tuple(map(int, version.split('.'))))
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError) as exc:
        raise OSError(f'Pi-Bolt release check failed: {exc}; installation preserved; '
                      'retry ./install.sh --only pi-bolt') from exc


def pi_bolt_current(destination, release):
    """Conservative proof of an upstream build/link; unknown layouts use official repair.

    Selection and manifest/banner formats follow upstream install.sh, build-pi.sh
    and version-fast-path.ts. Special launch/Termux modes are left to upstream.
    """
    if not release:
        return None
    try:
        system = platform.system().lower()
        arm = platform.machine().lower() in ('arm64', 'aarch64')
        if system not in ('linux', 'darwin') or (system == 'darwin' and not arm):
            return None
        musl = ''
        if system == 'linux' and not arm:
            try:
                libc = subprocess.run(['ldd', '--version'], capture_output=True, text=True,
                                      errors='replace', timeout=5)
            except FileNotFoundError:
                pass  # upstream's is_musl finds no musl marker when ldd is absent
            else:
                musl = '-musl' if 'musl' in libc.stdout + libc.stderr else ''
        variant = os.environ.get('PIBOLT_VARIANT') or ''
        if variant == 'jit':
            variant = 'arm64-jit' if arm else f'x64{musl}-jit'
        elif not variant:
            if arm:
                variant = 'arm64'
            else:
                try:
                    avx2 = re.search(r'\bavx2\b', Path('/proc/cpuinfo').read_text(errors='replace'))
                except OSError:
                    avx2 = None  # upstream's grep selects baseline if cpuinfo is unavailable
                variant = f'x64{musl}' + ('' if avx2 else '-baseline')
        allowed = ('arm64', 'arm64-jit') if arm else tuple(
            f'x64{musl}{suffix}' for suffix in ('', '-baseline', '-jit'))
        if variant not in allowed:
            return None
        install_root = os.environ.get('PIBOLT_INSTALL') or str(HOME / '.pi-bolt')
        if not install_root.startswith('/'):
            pwd = os.environ.get('PWD') or os.getcwd()
            if not os.path.isabs(pwd) or not Path(pwd).is_dir() or not os.path.samefile(pwd, '.'):
                pwd = os.getcwd()
            install_root = f'{pwd}/{install_root}'
        root = Path(install_root)
        name = f'pi-bolt-{system}-{variant}'
        build = root / name
        if build.is_symlink() or (build / 'pi').is_symlink():
            return None
        jit = 'on' if variant.endswith('-jit') else 'off'
        channel_file = root / 'channel'
        if channel_file.is_symlink() or (channel_file.exists() and not channel_file.is_file()):
            return None
        channel = channel_file.read_text().strip() if channel_file.is_file() else 'stable'
        # Upstream selects stable latest when the override is unset, but preserves
        # the stored channel for future native updates. Only an explicit override
        # requests a channel change during this install.
        requested_channel = os.environ.get('PIBOLT_CHANNEL')
        if channel not in ('stable', 'beta') or (requested_channel and channel != requested_channel):
            return None
        target = build / 'pi'
        start = build / 'pi-start'
        launcher = root / f'{name}.start'
        if system == 'linux' and variant == 'x64' and (os.path.lexists(start) or launcher.is_file()):
            if (not launcher.is_file() or launcher.is_symlink() or (os.path.lexists(start) and
                    (not start.is_file() or start.is_symlink() or not os.access(start, os.X_OK)))):
                return None
            target = launcher
            # The generated script embeds upstream's literal install path.
            quoted = f'{install_root}/{name}'.replace("'", "'\\''")
            expected = (f"#!/bin/sh\ndir='{quoted}'\n"
                        'if [ -x "$dir/pi-start" ]; then exec "$dir/pi-start" "$@"; fi\n'
                        'exec "$dir/pi" "$@"\n')
            if target.read_text() != expected:
                return None
        binary = destination / 'pi-bolt'
        if not binary.is_symlink() or binary.resolve(strict=True) != target.resolve(strict=True):
            return None
        # --version bypasses the normal CLI, including export's mandatory sibling assets.
        required = ['pi', 'pi-bolt.txt', 'package.json', 'README.md', 'photon_rs_bg.wasm',
                    'export-html/template.html', 'export-html/template.css', 'export-html/template.js',
                    'export-html/vendor/highlight.min.js', 'export-html/vendor/marked.min.js',
                    'export-html/vendor/marked-cjk-friendly.min.js']
        native_platform = f'{system}-{"arm64" if arm else "x64"}'
        helper = 'darwin-platform.node' if system == 'darwin' else 'linux-platform-x11.node'
        required += [f'native/{system}/prebuilds/{native_platform}/{helper}']
        if system == 'darwin':
            required += ['pi-bin', 'pi-spawn']
        if any(not (build / file).is_file() or not (build / file).stat().st_size for file in required):
            return None
        executables = [target, build / 'pi']
        if system == 'darwin':
            executables += [build / 'pi-bin', build / 'pi-spawn']
        if any(not os.access(binary, os.X_OK) for binary in executables):
            return None
        if any(not (build / folder).is_dir() or not any((build / folder).iterdir())
               for folder in ('docs', 'examples', 'theme', 'assets')):
            return None
        banner = pi_bolt_version(destination)
        match = re.fullmatch(r'([0-9]+\.[0-9]+\.[0-9]+) \(Pi-Bolt '
                             + re.escape(f'{release}, {system}-{variant}, JIT {jit}') + r'\)', banner)
        if not match:
            return None
        manifest = (build / 'pi-bolt.txt').read_text().splitlines()
        expected = f'Pi-Bolt {release} (Pi {match.group(1)}), {system}-{variant}, JIT {jit}, built '
        if not (len(manifest) == 1 and re.fullmatch(re.escape(expected) + r'[0-9]{4}-[0-9]{2}-[0-9]{2}', manifest[0])):
            return None
        if json.loads((build / 'package.json').read_text()).get('version') != match.group(1):
            return None
        return banner
    except (OSError, ValueError, IndexError, AttributeError, RuntimeError, subprocess.SubprocessError):
        return None


def install_pi_bolt(output=None):
    """Check freshness before downloading; only a proven current build skips upstream."""
    output = output or Output()
    destination = BIN.absolute()
    for command in ('curl', 'sh'):
        if not shutil.which(command):
            raise OSError(f'Pi-Bolt requires {command}; install it and retry --only pi-bolt')

    if os.path.lexists(destination / 'pi-bolt'):
        release = pi_bolt_release(output)
        current = pi_bolt_current(destination, release)
        if current:
            return f'{destination / "pi-bolt"}: {current}; current (release checked; native install skipped)'

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
                steps=[Step('check Pi-Bolt release selection for existing builds; skip a proven match; '
                            f'otherwise bootstrap/repair: download {PI_BOLT_INSTALLER} privately and run the unmodified sh installer '
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
    probe_error = None
    try:
        package = pi_package(binary=binary, strict=True)
    except (OSError, subprocess.SubprocessError) as exc:
        package, probe_error = None, str(exc)
    before = installed_evidence(([package] if package else []) + [pi_settings_path()],
                                identity=str(package) if package else None)
    if probe_error:
        before['error'] = probe_error
    try:
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
        return Refresh(f'{binary}: {action} {PI_SOURCE}', before,
                       installed_evidence([package, pi_settings_path()], identity=str(package)))
    except (OSError, subprocess.SubprocessError) as exc:
        exc.installed_evidence = before
        raise


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
    bolt.inputs = lambda: installed_evidence([BIN.absolute() / 'pi-bolt'])
    return [
        bolt,
        pi,
        Item('tx', 'tx tmux session launcher', note='keeps your existing ~/.tmux.conf',
             steps=[Step(f'install {BIN}/tx and completions', run=install_tx)],
             inputs=lambda: installed_evidence([BIN.absolute() / 'tx'])),
        hermes_item(hermes_args),
        Item('claude', 'Claude Code plugin and full suite + bundled Ponytail', needs='claude',
             steps=[Step('registry status: NOT_CHECKED until actual install; validate official Git source, '
                         'settings scopes and installed IDs via claude plugin list --json; automatically remove '
                         'one writable wrong-name Kit-only registration (including its plugin); '
                         f'claude plugin marketplace add {SOURCE} if canonical is absent; read back source/name before '
                         f'claude plugin marketplace update {CLAUDE_MARKETPLACE}; '
                         f'claude plugin install {CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE} or scoped plugin update; verify installed ID',
                         run=lambda: install_claude(output or Output()))]),
        Item('codex', 'Codex plugin and full suite + bundled Ponytail', needs='codex',
             steps=[Step('registry status: NOT_CHECKED until actual install; validate '
                         'codex plugin marketplace list --json and codex plugin list --marketplace NAME --json; '
                         'qualify wrong-name official Git ownership with codex app-server config/read layers; '
                         'automatically remove one writable wrong-name Kit-only plugin/registration '
                         '(CLI initialization may write cache/auth state); '
                         f'codex plugin marketplace add {SOURCE} --ref main if canonical is absent; '
                         f'read back source/name before codex plugin marketplace upgrade {CODEX_MARKETPLACE} for Git; '
                         f'codex plugin add {CODEX_PLUGIN}@{CODEX_MARKETPLACE} only if not installed; verify installed ID',
                         run=lambda: install_codex(output or Output()))]),
        orbi_item(output),
    ]


def describe(item):
    return host_unavailable(item.needs) or item.missing or item.note


# Content evidence excludes incidental receipts/caches, never mtimes or success text.
def payload_digest(path, ancestors=(), *, settings=False):
    path = Path(path)
    if path.is_symlink():
        resolved = path.resolve(strict=True)
        if resolved in ancestors:
            raise OSError(f'cyclic installed input {path}')
        return ['link', os.readlink(path), str(resolved), payload_digest(resolved, (*ancestors, resolved), settings=settings)]
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return ['absent']
    if path.is_file():
        return ['file', stat.S_IMODE(mode), (json.loads(path.read_text(encoding='utf-8')) if settings
                else hashlib.sha256(path.read_bytes()).hexdigest())]
    if path.is_dir():
        return ['directory', [(child.name, payload_digest(child, ancestors))
                for child in sorted(path.iterdir())
                if child.name not in ('.git', '__pycache__', '.DS_Store')]]
    raise OSError(f'unsupported installed input {path}')


def installed_evidence(paths, identity=None):
    evidence = {'inputs': {}, 'identity': identity, 'directories': []}
    try:
        for path in paths:
            path = Path(path).absolute()
            value = payload_digest(path, settings=path == pi_settings_path())
            if path.is_dir():
                evidence['directories'].append(str(path))
            if path.is_dir() and (path / '.git').exists():
                revision = subprocess.run(['git', '-C', str(path), 'rev-parse', '--verify', 'HEAD'],
                                          capture_output=True, text=True, timeout=30, check=True).stdout.strip()
                value.append(['revision', revision])
            evidence['inputs'][str(path)] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        if not paths:
            evidence['error'] = 'installed payload path unavailable'
    except (OSError, UnicodeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        evidence['error'] = str(exc)
    return evidence


def read_evidence(item):
    try:
        return item.inputs() if item and item.inputs else {'inputs': {}, 'error': 'installed inputs unavailable'}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {'inputs': {}, 'error': str(exc)}


@dataclass
class Refresh:
    message: str
    before: dict
    after: dict


def evidence_change(before, after):
    if before.get('error') or after.get('error'):
        return 'unverified', []
    paths = sorted(set(before['inputs']) | set(after['inputs']))
    changed = [path for path in paths if before['inputs'].get(path) != after['inputs'].get(path)]
    if before.get('identity') != after.get('identity'):
        changed = paths
    return ('changed' if changed else 'unchanged'), changed


def marketplace_evidence(state):
    if not state.installed:
        return {'inputs': {}, 'identity': state.identity}
    evidence = installed_evidence(state.paths, state.identity)
    for path in state.paths:
        if not path.is_dir():
            evidence['error'] = f'installed payload unavailable: {path}'
    return evidence


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
class RestartStateError(RuntimeError):
    pass


def read_pending_restarts(path):
    try:
        pending = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(pending, dict) or any(
                not isinstance(row, dict) or not isinstance(row.get('delegated', False), bool) or any(
                    not isinstance(row.get(field), list) or
                    any(not isinstance(value, str) for value in row[field])
                    for field in ('changed_inputs', 'directories', 'restarted_units'))
                for row in pending.values()):
            raise ValueError('invalid pending restart record')
        return pending
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise RestartStateError(f'cannot read {path}: {exc}') from exc


def write_pending_restarts(path, pending):
    try:
        if not pending:
            path.unlink(missing_ok=True)
            return
        descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(pending, stream)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    except OSError as exc:
        raise RestartStateError(f'cannot save {path}: {exc}') from exc


def restart_services(output, observations=None, settled=None):
    """Restart proven consumers, updating any supplied restart progress sets.

    An item's restarted_units tracks its successful units; settled tracks items
    that no longer need a service decision.
    """
    observations = {key: row for key, row in (observations or {}).items() if key != 'orbi'}
    candidates = {key: row for key, row in observations.items()
                  if row['change'] in ('changed', 'unverified')}
    reasons = []
    for key, row in observations.items():
        if row['status'] == 'failed':
            reasons.append(f'{key}: held (incomplete payload); repair and rerun ./install.sh --only {key}')
        elif row['change'] == 'unchanged':
            reasons.append(f'{key}: skipped (effective installed contents unchanged)')
        if row['change'] == 'unverified':
            error = row['after'].get('error') or row['before'].get('error')
            inputs = ', '.join(sorted(set(row['before'].get('inputs', {})) | set(row['after'].get('inputs', {}))))
            reasons.append(f'{key}: held (unverified input{": " + inputs if inputs else ""}; {error})')
    if any(row['change'] == 'unverified' for row in observations.values()):
        reasons.append('Inspect named inputs; retry ./install.sh --only ITEM')
    if not candidates:
        return '; '.join(reasons) or 'no complete changed payloads; no service restart requests'
    if os.environ.get('KIT_INSTALL_DEFER_SERVICES'):
        return '; '.join(reasons + ['service decisions delegated to outer installer'])
    ctl = os.environ.get('KIT_SYSTEMCTL', 'systemctl')
    if platform.system() != 'Linux' or not shutil.which(ctl):
        return '; '.join(reasons + ['service restarts unavailable (requires Linux user systemd)'])
    listed = subprocess.run(
        [ctl, '--user', 'list-units', '--type=service', '--state=active',
         '--plain', '--no-legend', 'kit-*.service'], capture_output=True, text=True, timeout=30)
    if listed.returncode:
        raise RuntimeError('cannot discover Kit services: ' + failure_summary(listed.stderr))
    units = sorted({line.split()[0] for line in listed.stdout.splitlines() if line.split()
                    and len(line.split()) >= 3 and line.split()[2] == 'active'
                    and re.fullmatch(r'kit-[^/]+\.service', line.split()[0])})
    failed, matched, unsettled = [], set(), set()
    for unit in units:
        try:
            shown = subprocess.run([ctl, '--user', 'show', unit, '--property=ExecStart',
                                    '--property=EnvironmentFiles', '--property=Environment'],
                                   capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            # An unverified unit could still consume any of these changed inputs.
            unsettled.update(candidates)
            reasons.append(f'{unit}: held (cannot verify executable/config references: {exc}); '
                           f'inspect systemctl --user show {unit} and restart manually if affected')
            continue
        # Read executable/config references, not Description, name prefixes or checkout HEAD.
        consumed = '\n'.join(line for line in shown.stdout.splitlines()
                             if line.startswith(('ExecStart=', 'EnvironmentFiles=')))
        references = {Path(value) for value in re.findall(r'(?<![\w./-])(/[^\s;"{}]+)', consumed)}
        # An Orbi deployment can use an arbitrary unit name, including kit-*.
        # Never restart it through the payload-consumer path, even if the
        # installer skipped Orbi and the unit also uses a selected host input.
        if not shown.returncode and (re.search(r'(?:^|[\s"=])ORBI_CONFIG=', shown.stdout, re.M)
                                    or re.search(r'\s-m\s+orbi(?:\.runner)?(?:\s|;|$)', consumed)
                                    or any(p.name in {'orbi', 'orbi-exporter.py'}
                                           or p.parts[-2:] == ('.orbi', 'env') for p in references)):
            reasons.append(f'{unit}: skipped (Orbi lifecycle is separate)')
            continue
        if shown.returncode or not references:
            unsettled.update(candidates)
            reasons.append(f'{unit}: held (unverified executable/config references for '
                           f'{", ".join(candidates)}); inspect systemctl --user show {unit} and restart manually if affected')
            continue
        affected, blocked = set(), set()
        for key, row in observations.items():
            paths = set(row.get('changed_inputs', []))
            if row['status'] == 'failed' or row['change'] == 'unverified':
                paths.update(row['before'].get('inputs', {}))
                paths.update(row['after'].get('inputs', {}))
            # The executable alone does not prove which Pi profile/package it loads.
            if key == 'pi' and (paths or row['status'] == 'failed'):
                environment = next((line.removeprefix('Environment=') for line in shown.stdout.splitlines()
                                    if line.startswith('Environment=')), '')
                try:
                    profile = dict(value.split('=', 1) for value in shlex.split(environment)
                                   if '=' in value).get('PI_CODING_AGENT_DIR')
                except ValueError:
                    profile = None
                env_files = re.search(r'^EnvironmentFiles=\s*\S', shown.stdout, re.MULTILINE)
                if profile and not env_files and Path(profile) == pi_settings_path().parent:
                    paths.add(str(BIN.absolute() / 'pi-bolt'))
                elif (not profile or env_files) and BIN.absolute() / 'pi-bolt' in references:
                    blocked.add(key)
                    reasons.append(f'{unit}: held (unverified Pi profile for {pi_settings_path()}); '
                                   'inspect unit Environment/EnvironmentFiles and restart manually if it consumes this package')
            # A failed refresh may already have removed a payload directory.
            # Preserve its before/after type evidence instead of probing it now.
            directories = set(row['before'].get('directories', [])) | set(row['after'].get('directories', []))
            consumes = any(Path(path) == ref or (path in directories and ref.is_relative_to(path))
                           for path in paths for ref in references)
            if not consumes:
                continue
            if row['status'] == 'failed' or row['change'] == 'unverified':
                blocked.add(key)
            elif row['change'] == 'changed':
                matched.add(key)
                if unit not in row.get('restarted_units', ()):
                    affected.add(key)
        if blocked:
            unsettled.update(affected | blocked)
            reasons.append(f'{unit}: held (incomplete/unverified {", ".join(sorted(blocked))}); repair those inputs before manual restart')
        elif affected:
            argv = [ctl, '--user', 'try-restart', unit]
            output.line('  $ ' + shlex.join(argv), 'command')
            try:
                code, _ = run_command(argv, output, timeout=30)
            except (OSError, subprocess.SubprocessError) as exc:
                failed.append(unit)
                unsettled.update(affected)
                reasons.append(f'{unit}: restart failed ({exc})')
            else:
                if code:
                    failed.append(unit)
                    unsettled.update(affected)
                    reasons.append(f'{unit}: restart failed (exit {code})')
                else:
                    for key in affected:
                        completed = observations[key].get('restarted_units')
                        if completed is not None:
                            completed.add(unit)
                    reasons.append(f'{unit}: restarted ({", ".join(sorted(affected))} changed)')
        else:
            reasons.append(f'{unit}: skipped (no outstanding proven changed consumer input)')
    for key, row in candidates.items():
        if key not in matched | unsettled and row['status'] != 'failed' and row['change'] == 'changed':
            reasons.append(f'{key}: no proven active consumer for {", ".join(row["changed_inputs"])}; '
                           'no restart requested; inspect unit executable/config references if a service uses these inputs')
    if settled is not None:
        settled.update(key for key, row in candidates.items()
                       if key not in unsettled and row['change'] == 'changed' and row['status'] != 'failed')
    if failed:
        raise RuntimeError('service restart failed: ' + ', '.join(failed) + '; ' + '; '.join(reasons)
                           + '; resolve the named service errors and rerun ./install.sh with the same options')
    return '; '.join(reasons) or 'no active supported consumers; no service restart requests'


def install(all_items, chosen, dry_run=False, output=None, mode='install', baseline=None, *,
            skip_orbi=False, lock=None):
    output = output or Output()
    if dry_run or (not chosen and not os.environ.get('KIT_INSTALL_REPORT')):
        return _install(all_items, chosen, dry_run=dry_run, output=output, mode=mode)
    with (installer_lock(output) if lock is None else nullcontext(lock)) as held:
        if held is None:
            return 1
        binary_dir = BIN.resolve()
        state_path = binary_dir.with_name(binary_dir.name + '.kit-install-restarts.json')
        try:
            return _install(all_items, chosen, output=output, mode=mode, lock_fd=held.fileno(),
                            baseline=baseline, state_path=state_path, skip_orbi=skip_orbi)
        except RestartStateError as exc:
            output.line(f'  FAILED: pending service restarts: {exc}; repair the state file or its access and rerun ./install.sh with the same options', 'failed')
            return 1


@contextmanager
def installer_lock(output, before_pull=False):
    # Resolve aliases so checkouts targeting the same binary directory share one
    # persistent inode. Never unlink it: that would allow two independent locks.
    binary_dir = BIN.resolve()
    lock_path = binary_dir.with_name(binary_dir.name + '.kit-install.lock')
    lock = None
    placement_error = None
    try:
        if before_pull:
            # Git must not replace the lock entry or change which inode BIN selects.
            bin_alias = Path(os.path.abspath(BIN))
            if lock_path.is_relative_to(ROOT) or lock_path.resolve().is_relative_to(ROOT):
                placement_error = f'installer lock {lock_path} is inside the Git checkout'
            elif bin_alias.is_relative_to(ROOT) and not binary_dir.is_relative_to(ROOT):
                placement_error = f'KIT_BIN_DIR alias {bin_alias} is inside the Git checkout'
            if placement_error:
                placement_error += '; set KIT_BIN_DIR outside it or retry with --no-pull.'
        inherited = os.environ.get('KIT_INSTALL_LOCK_FD')
        if not placement_error:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
        if inherited:
            lock = os.fdopen(os.dup(int(inherited)), 'a+', encoding='utf-8')
        else:
            # If a lock already exists, preserve the usual contention diagnostic.
            lock = lock_path.open('r+' if placement_error else 'a+', encoding='utf-8')
        actual, expected = os.fstat(lock.fileno()), lock_path.stat()
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise OSError('inherited installer lock does not match the binary directory')
    except (OSError, RuntimeError, ValueError) as exc:
        if lock is not None:
            lock.close()
        detail = f'cannot open installer lock {lock_path}: {exc}'
        if placement_error and isinstance(exc, FileNotFoundError):
            detail = placement_error
        output.line(f'  FAILED: {detail}', 'failed')
        yield None
        return
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.seek(0)
            holder = lock.read(128).strip() or 'unknown (holder metadata unavailable)'
            output.line(f'  FAILED: installer lock {lock_path} held by PID {holder}; '
                        'let the holder finish, then retry; do not remove the lock file.', 'failed')
            yield None
            return
        except OSError as exc:
            output.line(f'  FAILED: cannot acquire installer lock {lock_path}: {exc}', 'failed')
            yield None
            return
        if placement_error:
            output.line(f'  FAILED: {placement_error}', 'failed')
            yield None
            return
        if not inherited:
            lock.seek(0)
            lock.truncate()
            lock.write(f'{os.getpid()}\n')
            lock.flush()
        yield lock


def _install(all_items, chosen, dry_run=False, output=None, mode='install', lock_fd=None,
             baseline=None, *, state_path=None, skip_orbi=False):
    results = []
    baseline = dict(baseline or {})
    pending = read_pending_restarts(state_path) if state_path else {}
    defer_services = bool(os.environ.get('KIT_INSTALL_DEFER_SERVICES'))
    observations = {}
    native_decisions = []
    delegated_orbi = None
    # Private machine-readable progress for update_bundle.py, separate from native output.
    report = None if dry_run else os.environ.get('KIT_INSTALL_REPORT')
    if report:
        Path(report).write_text('')

    def record(key, status, detail, code=None, **fields):
        results.append((key, status, detail))
        if report:
            with Path(report).open('a') as stream:
                stream.write(json.dumps({'item': key, 'status': status, 'exit': code, **fields}) + '\n')

    def report_orbi_progress(fleet):
        # The native delegate can enforce a suite-wide timeout. Persist the last
        # known fleet stages without adding a result to the live installer summary.
        try:
            with Path(report).open('a') as stream:
                stream.write(json.dumps({'item': 'orbi', 'status': 'failed', 'exit': 1, 'orbi_fleet': fleet}) + '\n')
        except OSError as exc:
            output.line(f'  Could not save intermediate Orbi receipt: {exc}')

    orbi_progress = report_orbi_progress if report and os.environ.get('KIT_INSTALL_ORBI_PROGRESS') == '1' else None

    def pending_key(key):
        # Only Pi infers a consumer from the settings profile as well as paths.
        return f'pi:{pi_settings_path().absolute()}' if key == 'pi' else key

    def observe(key, status, before, after, *, delegated=False):
        before = baseline.get(key, before)
        if key in observations:
            before = observations[key]['before']
            if observations[key]['status'] == 'failed':
                status = 'failed'
        change, paths = evidence_change(before, after)
        observations[key] = dict(status=status, before=before, after=after,
                                 change=change, changed_inputs=paths)
        # Orbi's separate lifecycle never uses the consumer restart pass.
        if not state_path or key == 'orbi':
            return
        state_key = pending_key(key)
        owed = pending.get(state_key, {})
        if change == 'changed':
            changed_inputs = set(paths) | set(owed.get('changed_inputs', []))
            directories = set(before.get('directories', [])) | set(after.get('directories', []))
            directories = (directories & set(paths)) | set(owed.get('directories', []))
            # New changes invalidate restart successes for the previous payload.
            row = dict(changed_inputs=sorted(changed_inputs), directories=sorted(directories), restarted_units=[])
        elif owed:
            row = dict(owed)
        else:
            return
        # A healthy delegated refresh can be retried by --only hermes even if
        # the next native update is up to date and does not refresh hosts again.
        row['delegated'] = (status == 'installed' and change != 'unverified' and
                            (delegated or defer_services or (change == 'unchanged' and owed.get('delegated', False))))
        if row != owed:
            # Save before the next component can interrupt or abort the run.
            pending[state_key] = row
            write_pending_restarts(state_path, pending)

    total = len(chosen)
    current = 0
    started = time.monotonic()
    if output.verbosity or dry_run:
        title = 'Kit suite update' if mode == 'update' else 'Kit full suite installer'
        output.line(title + (' — preview' if dry_run else ''), 'heading')
        output.line('Selected: ' + (', '.join(i.key for i in all_items if i.key in chosen) or 'none'))
    for item in all_items:
        if item.key not in chosen:
            if item.key == 'orbi' and delegated_orbi:
                record('orbi', delegated_orbi['status'], 'Hermes delegated: ' +
                       orbi_fleet_summary(delegated_orbi['orbi_fleet']), delegated_orbi['exit'],
                       orbi_fleet=delegated_orbi['orbi_fleet'])
            else:
                record(item.key, 'skipped', describe(item) if not item.available else 'not chosen')
            continue
        current += 1
        if output.verbosity or dry_run:
            output.line(f'\n[{current}/{total}] {item.label}', 'heading')
        if not item.available or item.refuse:
            if not dry_run:
                held = read_evidence(item)
                observe(item.key, 'failed', held, held)
            record(item.key, 'failed', item.refuse or describe(item), 1)
            if item.refuse:
                level = 'WARNING' if item.refusal_warning else 'FAILED'
                style = 'warning' if item.refusal_warning else 'failed'
                output.line(f'  {level}: {item.refuse}', style)
            continue
        if not item.steps:
            record(item.key, 'skipped', item.note)
            continue
        if not dry_run and item.key == 'hermes' and any(
                Path(arg).name == 'update_bundle.py' for step in item.steps for arg in (step.argv or [])):
            # Native apply can advance a source-linked host before launching its
            # nested installer. Keep that host's original inputs, even --no-pull.
            missing = {'pi-bolt', 'tx', 'claude', 'codex', 'orbi'} - baseline.keys() - observations.keys()
            baseline.update(installed_baseline(missing, output))
        before = read_evidence(item) if not dry_run and item.key != 'hermes' else None
        refresh = None
        native = fleet = None
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
                        message = step.run(report_progress=orbi_progress) if item.key == 'orbi' else step.run()
                        if isinstance(message, Refresh):
                            refresh, message = message, message.message
                        if item.key == 'orbi':
                            fleet = message
                            message = orbi_fleet_summary(fleet)
                            if fleet['status'] == 'no_deployments':
                                message = install_orbi(output)
                            elif fleet['status'] != 'completed':
                                outcome, exit_code = 'failed', 1
                                output.line('  FAILED: ' + message, 'failed')
                        detail.append(message)
                        if output.verbosity and outcome != 'failed':
                            output.line('  ' + message)
                        break
                    if item.key == 'hermes':
                        env = {'KIT_INSTALL_DEFER_SERVICES': '1'}
                        if skip_orbi or 'orbi' in chosen:
                            # Explicit opt-out or let the outer Orbi item own the one fleet refresh.
                            env['KIT_INSTALL_SKIP_ORBI'] = '1'
                        if lock_fd is not None:
                            env['KIT_INSTALL_LOCK_FD'] = str(lock_fd)
                        native = {}
                        code, text = run_command(step.argv, output, extra_env=env, receipt=native, timeout=1800)
                        native = native or terminal_receipt(text)
                    else:
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
                    observed = getattr(exc.__cause__ or exc, 'installed_evidence', None)
                    if observed:
                        before = observed
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
        fields = {}
        if not dry_run:
            if item.key == 'hermes':
                # A deferred nested installer can also save changes under this lock.
                if state_path:
                    pending = read_pending_restarts(state_path)
                if native:
                    fields = {k: v for k, v in native.items() if k.startswith('gateway_restart') or k in ('activation', 'hosts')}
                    disposition = native.get('gateway_restart', 'unverified')
                    native_decisions.append(f'Hermes: native gateway disposition {disposition}; no outer restart')
                    for row in native.get('hosts', []):
                        key = row['item']
                        if key == 'orbi' and not skip_orbi and 'orbi' not in chosen:
                            if 'orbi_fleet' in row:
                                delegated_orbi = row
                            elif row['status'] != 'skipped':
                                delegated_orbi = {'status': 'failed', 'exit': row['exit'] or 1,
                                    'orbi_fleet': {'status': 'unverified', 'deployments': [],
                                                   'error': {'message': 'delegated Orbi receipt unavailable; inspect host state before retrying'}}}
                        if key == 'services' or row['status'] == 'skipped':
                            continue
                        evidence = row.get('evidence', {})
                        if 'before' in evidence and 'after' in evidence:
                            observe(key, row['status'], evidence['before'], evidence['after'], delegated=True)
                        else:
                            # An interrupted/older nested installer may report no
                            # evidence. It must not leave an earlier success eligible.
                            previous = observations.get(key)
                            selected = next((i for i in all_items if i.key == key), None)
                            held = (previous['after'] if previous else read_evidence(selected))
                            after = {**held, 'error': f'{key}: nested refresh {row["status"]}; '
                                                     'installed payload evidence unavailable'}
                            observe(key, 'failed', held, after)
                    if outcome == 'installed' and native.get('status') == 'up_to_date' and 'hosts' not in native:
                        # An equal native revision has no host receipt. Recheck
                        # only previously completed delegated inputs, not other
                        # components that the current invocation did not select.
                        host_keys = {key for key in ('pi-bolt', 'tx', 'claude', 'codex')
                                     if key not in chosen and pending.get(key, {}).get('delegated')}
                        for key, current_inputs in installed_baseline(host_keys, output).items():
                            observe(key, 'installed', current_inputs, current_inputs, delegated=True)
                else:
                    for key, row in observations.items():
                        if key in ('pi-bolt', 'tx', 'claude', 'codex', 'orbi'):
                            row['after']['error'] = 'Hermes nested receipt unavailable'
                            row['change'] = 'unverified'
                    native_decisions.append('Hermes: held (native receipt unavailable); inspect setup/update receipt; retry ./install.sh --only hermes; no outer restart')
            else:
                after = read_evidence(item)
                if outcome == 'failed' and before.get('inputs') and not after.get('inputs'):
                    after = before
                if refresh:
                    before = refresh.before
                    after = installed_evidence(list(refresh.after['inputs']), refresh.after.get('identity'))
                    if refresh.after.get('error'):
                        after['error'] = refresh.after['error']
                observe(item.key, outcome, before, after)
                if outcome == 'installed' or os.environ.get('KIT_INSTALL_DEFER_SERVICES'):
                    row = observations[item.key]
                    fields = {'change': row['change'], 'changed_inputs': row['changed_inputs'],
                              'evidence': {'before': row['before'], 'after': row['after']}}
                    if outcome == 'installed' and row['change'] != 'unverified':
                        detail.append(f'checked; contents {row["change"]}')
        if fleet is not None:
            fields['orbi_fleet'] = fleet
        record(item.key, 'planned' if dry_run else outcome, '; '.join(d for d in detail if d),
               None if dry_run else exit_code, **fields)
    if chosen:
        output.line('\nService decisions (complete changed payloads and proven active consumers only)', 'heading')
        if dry_run:
            record('services', 'planned', 'check effective installed changes; restart only proven affected active consumers; Hermes owns gateway disposition')
        else:
            service_observations = dict(observations)
            if not defer_services:
                for key, row in observations.items():
                    owed = pending.get(pending_key(key))
                    if not owed:
                        continue
                    # Carry forward only paths proven changed. The current refresh
                    # still decides whether the payload is complete enough to use.
                    change = row['change']
                    if change == 'unchanged' and row['status'] == 'installed':
                        change = 'changed'
                    directories = set(row['before'].get('directories', [])) | set(owed['directories'])
                    service_observations[key] = dict(
                        row, change=change, before=dict(row['before'], directories=sorted(directories)),
                        changed_inputs=sorted(set(row['changed_inputs']) | set(owed['changed_inputs'])),
                        restarted_units=set(owed['restarted_units']))
            settled = set()
            try:
                detail = restart_services(output, service_observations, settled)
                detail = '; '.join([detail, *native_decisions])
                record('services', 'installed', detail, 0, decision=detail)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                record('services', 'failed', str(exc), 1, reason=str(exc))
            finally:
                # Retain successful restarts even if a later unit interrupted the pass.
                remaining = dict(pending)
                for key, row in service_observations.items():
                    if 'restarted_units' not in row:
                        continue
                    state_key = pending_key(key)
                    if key in settled:
                        del remaining[state_key]
                    else:
                        remaining[state_key] = dict(pending[state_key], restarted_units=sorted(row['restarted_units']))
                if remaining != pending:
                    write_pending_restarts(state_path, remaining)
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


def has_checkout(root):
    marker = root / '.git'
    return marker.exists() or marker.is_symlink()


def pull_checkout(root, write=print, run=subprocess.run, before_change=None):
    """Keep local edits in a stash, then require an upstream fast-forward.

    Return whether disk code must be re-executed (stash or HEAD change).
    Fail closed before component actions; never restore or remove a stash.
    """
    root = Path(root).resolve()
    if not has_checkout(root):
        return False  # unpacked release; do not discover a parent repository
    # -C alone does not override these (for example when called from a Git hook).
    # Refuse before even reading status rather than stash into a foreign repository
    # or reset this checkout using somebody else's index/object database.
    overrides = [name for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR',
                                  'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
                                  'GIT_NAMESPACE', 'GIT_SHALLOW_FILE') if name in os.environ]
    if overrides:
        raise RuntimeError('Git environment redirects checkout state; unset ' +
                           ', '.join(overrides) + ' before retrying')

    def checked(result, args):
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f'exit {result.returncode}'
            raise RuntimeError(f'git {shlex.join(args)} failed: {detail}')
        return result.stdout.strip()

    def git(*args):
        return run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=120)

    def read(*args):
        return checked(git(*args), args)

    if Path(read('rev-parse', '--show-toplevel')).resolve() != root:
        raise RuntimeError('installer path is not the Git checkout root; refusing to change another checkout')
    upstream = git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
    if upstream.returncode or not upstream.stdout.strip():
        raise RuntimeError('this checkout has no usable upstream branch (detached or local-only); '
                           'switch to a tracking branch or configure its upstream before retrying')
    read('rev-parse', '--verify', '@{u}^{commit}')
    before = read('rev-parse', '--verify', 'HEAD')
    stashed = False
    dirty = read('status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none')
    if before_change:
        before_change()  # installed links may consume this checkout before stash/pull
    if dirty:
        previous = read('stash', 'list', '--format=%H').splitlines()
        # Git can reuse the object (and not add a reflog entry) for identical
        # edits in the same second. A sub-second message makes this a new stash.
        message = f'Kit installer: local changes before pull ({time.time_ns()})'
        args = ('stash', 'push', '--include-untracked', '--message', message)
        saved = git(*args)
        current = read('stash', 'list', '--format=%H').splitlines()
        if current and current[1:] == previous:
            stash_id = current[0]
            # Print before any further operation can fail, including stash cleanup.
            write(f'Kept local changes in Kit installer stash {stash_id}. Manual recovery (also kept after success):')
            write(shlex.join(['git', '-C', str(root), 'stash', 'apply', '--index', stash_id]))
            stashed = True
        checked(saved, args)
        if not stashed:
            raise RuntimeError('git stash did not create a new stash; inspect git status and git stash list before retrying')
        if read('status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'):
            raise RuntimeError('checkout is still dirty after git stash; inspect git status before retrying; '
                               'the printed stash is kept for manual recovery')
    # Disable configured autostash: it would restore/drop edits behind our back.
    read('pull', '--ff-only', '--no-autostash', '--quiet')
    after = read('rev-parse', '--verify', 'HEAD')
    if after != before:
        write(f'Updated this checkout {before[:8]}..{after[:8]} ({upstream.stdout.strip()}); installing the new version.')
    return stashed or after != before


def installed_baseline(keys, output):
    """Read inputs before source mutation; never use this to skip a refresh."""
    keys = set(keys)
    if 'hermes' in keys:  # installed Hermes may refresh these hosts, even --only hermes
        keys.update(('pi-bolt', 'tx', 'claude', 'codex', 'orbi'))
    readers = {
        'pi-bolt': lambda: installed_evidence([BIN.absolute() / 'pi-bolt']),
        'tx': lambda: installed_evidence([BIN.absolute() / 'tx']),
        'orbi': lambda: installed_evidence([Path(shutil.which('orbi') or
            Path(os.environ.get('UV_TOOL_BIN_DIR') or BIN).absolute() / 'orbi')]),
        'claude': lambda: marketplace_evidence(claude_registration(output)),
        'codex': lambda: marketplace_evidence(codex_registration(output)),
    }
    def pi_inputs():
        binary = BIN.absolute() / 'pi-bolt'
        package = pi_package(binary=binary, strict=True) if binary.exists() else None
        return installed_evidence(([package] if package else []) + [pi_settings_path()],
                                  identity=str(package) if package else None)
    readers['pi'] = pi_inputs
    return {key: read_evidence(Item(key, key, inputs=read)) for key, read in readers.items()
            if key in keys and (key not in ('claude', 'codex') or shutil.which(key))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Claude/Codex: automatically replace one source-qualified writable wrong-name Kit-only '
               'Git marketplace and its affected plugin; refuse ambiguous/managed/foreign ownership. '
               'Dry-run performs no registry probes or mutations. See docs/cross-host.md.')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--all', '--full', action='store_true', help='install the full suite for every available host (default)')
    selection.add_argument('--only', help=f'comma-separated items to install ({",".join(ITEM_KEYS)})')
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
                        help="install this checkout as it is, without stashing or pulling (also KIT_INSTALL_NO_PULL=1)")
    parser.add_argument('command', nargs='?', choices=('install', 'update'), default='install',
                        help='install (default) or update the installed suite in place; both run the same items')
    args = parser.parse_args(argv)
    for given in (args.only, args.skip):
        unknown = [k for k in (given or '').split(',') if k and k not in ITEM_KEYS]
        if unknown:
            parser.error(f'unknown item(s): {", ".join(unknown)}; choose from {", ".join(ITEM_KEYS)}')

    output = Output(args.color, 0 if args.quiet else 2)
    if (args.no_pull or args.list or args.dry_run or os.environ.get('KIT_INSTALL_PULLED')
            or os.environ.get('KIT_INSTALL_NO_PULL') or not has_checkout(ROOT)):
        return run_suite(args, parser, output)
    with installer_lock(output, before_pull=True) as lock:
        if lock is None:
            return 1
        return run_suite(args, parser, output, lock=lock, argv=argv)


def run_suite(args, parser, output, lock=None, argv=None):
    baseline = {}
    inherited = os.environ.pop('KIT_INSTALL_BASELINE_FD', None)
    if inherited:
        try:
            with os.fdopen(int(inherited), encoding='utf-8') as stream:
                baseline = json.load(stream)
        except (OSError, ValueError) as exc:
            output.line(f'FAILED: installed baseline unavailable: {exc}; rerun ./install.sh with the same options', 'failed')
            return 1
    if lock is not None:  # checkout preparation is enabled and already owns the lock
        try:
            def snapshot():
                keys = set(args.only.split(',') if args.only and not args.menu else ITEM_KEYS)
                if not args.menu:  # menu selection may include initially skipped candidates
                    keys -= set((args.skip or '').split(','))
                baseline.update(installed_baseline(keys, output))
            changed = pull_checkout(ROOT, write=output.line, before_change=snapshot)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            output.line(f'FAILED: checkout preparation: {exc}', 'failed')
            output.line('Nothing installed or restarted. Resolve the Git error and retry; '
                        'any created stash is kept (inspect git stash list; use the printed recovery command).')
            return 1
        if changed:
            # Pull or stash may have replaced the running installer: run disk code once.
            # Preserve the flock across exec and carry the baseline separately, so
            # nested installers share the lock but capture their own baseline.
            with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as stream:
                json.dump(baseline, stream)
                stream.seek(0)
                os.set_inheritable(stream.fileno(), True)
                os.set_inheritable(lock.fileno(), True)
                os.execvpe('bash', ['bash', str(ROOT / 'install.sh'), *(sys.argv[1:] if argv is None else argv)],
                           dict(os.environ, KIT_INSTALL_PULLED='1', KIT_INSTALL_BASELINE_FD=str(stream.fileno()),
                                KIT_INSTALL_LOCK_FD=str(lock.fileno())))
    hermes = [f for f, on in (('--bundle-only', args.bundle_only), ('--no-reload', args.no_reload),
                              ('--yes-deps', args.yes_deps), ('--dry-run', args.dry_run)) if on]
    if args.hermes_home:
        hermes += ['--hermes-home', args.hermes_home]
    all_items = items(hermes, output, mode=args.command)
    if args.list:
        for item in all_items:
            output.line(f"  {item.key:<9} {'available' if item.available else 'unavailable':<12} {item.label}"
                  + (f' ({describe(item)})' if describe(item) else ''),
                        'installed' if item.available else 'skipped')
        return 0
    chosen = {i.key for i in all_items if i.available}
    if args.only:
        chosen = {k for k in args.only.split(',') if k}
    skipped = set((args.skip or '').split(','))
    chosen -= skipped
    menu = args.menu
    if menu and not (sys.stdin.isatty() and sys.stdout.isatty()) and os.environ.get('KIT_INSTALL_UI') != 'text':
        parser.error('no terminal for the menu; choose with --all, --only or --skip (see --list)')
    if menu:
        try:
            go = choose_curses(all_items, chosen) if os.environ.get('KIT_INSTALL_UI') != 'text' \
                else choose_text(all_items, chosen, write=output.line)
        except Exception:  # no usable terminal for curses: the numbered menu
            go = choose_text(all_items, chosen, write=output.line)
        if not go:
            print('Nothing installed.')
            return 0
    if 'orbi' in skipped:
        chosen.discard('orbi')
    return install(all_items, chosen, dry_run=args.dry_run, output=output, mode=args.command, baseline=baseline,
                   skip_orbi='orbi' in skipped or (menu and 'orbi' not in chosen), lock=lock)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\nInstallation interrupted; completed steps remain installed.', file=sys.stderr)
        raise SystemExit(130)
