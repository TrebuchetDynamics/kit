#!/usr/bin/env python3
"""Install the full Autowork suite with verbose output by default.

    install.sh                every available component, live output and exact commands
    install.sh --menu         a checkbox menu on a terminal (arrows, Space, Enter)
    install.sh --full          the full suite for available hosts, no menu (--all also works)
    install.sh update          explicitly refresh the installed suite (same items as --full)
    install.sh --only tx,pi    just these; --skip hermes leaves those out
    install.sh --list          the items and whether each host is available
    install.sh --dry-run ...   print each command instead of running it
    install.sh --no-pull       install this checkout as it is

Install and update first bring this checkout up to date (`git pull --ff-only` of its
upstream) and then run the pulled installer; a checkout with local changes, no upstream
or a detached HEAD is installed as it is, and says so.

Each host item runs its own supported install command; a host whose CLI is not
installed is skipped and says so, and fails when named with --only. Octet instead
bootstraps official stable native binaries and Kit skills on supported platforms. Hermes options
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
HOME = Path(os.environ.get('HOME', str(Path.home())))
BIN = Path(os.environ.get('AUTOWORK_BIN_DIR') or HOME / '.local' / 'bin')
# Claude Code's refusal when settings name this marketplace from another source.
TOLERATE_CLAUDE_SOURCE = "its source doesn't match its extraKnownMarketplaces entry"


def manifest_name(relative, key='name'):
    """A plugin or marketplace name declared by a manifest in this checkout."""
    try:
        data = json.loads((ROOT / relative).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ''
    return str(data.get(key) or '')


CLAUDE_PLUGIN = manifest_name('.claude-plugin/plugin.json') or 'kit'
CLAUDE_MARKETPLACE = manifest_name('.claude-plugin/marketplace.json') or 'autowork'
CODEX_PLUGIN = manifest_name('.codex-plugin/plugin.json') or CLAUDE_PLUGIN
CODEX_MARKETPLACE = manifest_name('.agents/plugins/marketplace.json') or 'autowork-marketplace'


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


def run_command(argv, output, extra_env=None):
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
    with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env) as child:
        try:
            while chunk := child.stdout.read1(4096):
                text = decoder.decode(chunk)
                tail = (tail + text)[-16384:]
                if stream:
                    output.raw(text)
            text = decoder.decode(b'', final=True)
            tail = (tail + text)[-16384:]
            if stream:
                output.raw(text)
            code = child.wait()
        except BaseException:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            raise
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


def pi_package(source=PI_SOURCE):
    """The directory Pi installed this package source in, or None."""
    if not shutil.which('pi'):
        return None
    try:
        lines = subprocess.run(['pi', 'list'], capture_output=True, text=True, timeout=60).stdout.splitlines()
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
        done.append(f'installed {target}{note}')
    for shell, folder, name in (('bash', HOME / '.local/share/bash-completion/completions', 'tx'),
                                ('zsh', HOME / '.zsh/completions', '_tx'),
                                ('fish', HOME / '.config/fish/completions', 'tx.fish')):
        dest = folder / name
        if dest.exists() or dest.is_symlink():
            continue
        text = subprocess.run(['bash', str(source), 'completion', shell], capture_output=True, text=True).stdout
        if text:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(text)
    done.append('completions for bash, zsh and fish')
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
    if kept:
        done.append('kept your existing ' + ', '.join(kept))
    return '; '.join(done)


def hermes_home(hermes_args):
    """(home, given): the Hermes home the item works on, and whether it was named."""
    given = hermes_args[hermes_args.index('--hermes-home') + 1] if '--hermes-home' in hermes_args else ''
    named = given or os.environ.get('HERMES_HOME')
    return Path(named or HOME / '.hermes'), bool(named)


def hermes_installed(hermes_args):
    """The Hermes home when a profile already has its own Autowork plugin checkout (a
    `hermes plugins install` clone): those are updated, not linked to this checkout."""
    home, _ = hermes_home(hermes_args)
    for plugin in [home / 'plugins/autowork', *home.glob('profiles/*/plugins/autowork')]:
        if (plugin / '.git').exists() and plugin.resolve() != ROOT.resolve():
            return home
    return None


SETUP_ONLY = ('--bundle-only', '--no-reload', '--yes-deps')


def hermes_item(hermes_args):
    label = 'Hermes plugin + bundled Ponytail (every live profile)'
    home = hermes_installed(hermes_args)
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


def claude_marketplace_folders():
    """The folders Claude Code's configuration records for this marketplace.

    A marketplace added from a checkout is recorded as a `directory` source in the user
    settings and in Claude Code's own known-marketplaces registry. A published Git source
    records a repository instead and yields nothing here.
    """
    for path, key in ((HOME / '.claude/settings.json', 'extraKnownMarketplaces'),
                      (HOME / '.claude/plugins/known_marketplaces.json', '')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        entries = data.get(key, {}) if key else data
        if not isinstance(entries, dict):
            continue
        source = (entries.get(CLAUDE_MARKETPLACE) or {}).get('source')
        if isinstance(source, dict) and source.get('source') == 'directory':
            yield Path(str(source.get('path') or ''))


def missing_claude_marketplace():
    """The folder a marketplace registration names when this host no longer has it.

    Settings follow their owner between machines and outlive a renamed checkout, so a
    registered folder is often gone. That path is not a source choice any more: it is a
    stale registration that breaks `claude plugin marketplace update` with ENOENT, which
    would stop the suite installing from the published source.
    """
    for folder in claude_marketplace_folders():
        if not str(folder):
            continue
        try:
            if not folder.is_dir():
                return folder
        except OSError:
            return folder
    return None


def drop_stale_claude_marketplace():
    """Re-register from the published source when the recorded folder is gone (see
    missing_claude_marketplace); the component's own add step then adds that source."""
    folder = missing_claude_marketplace()
    if folder is None:
        return ''
    done = subprocess.run(['claude', 'plugin', 'marketplace', 'remove', CLAUDE_MARKETPLACE],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    text = (done.stdout + done.stderr).strip()
    if done.returncode and 'not found' not in text.lower() and 'no marketplace' not in text.lower():
        raise OSError(f'claude plugin marketplace remove {CLAUDE_MARKETPLACE}: {failure_summary(text)}')
    return f'dropped the stale registration: {folder} is gone'


def claude_steps():
    steps = []
    if missing_claude_marketplace() is not None:
        steps.append(Step('drop the marketplace registration whose folder is gone',
                          run=drop_stale_claude_marketplace))
    return steps + [
        Step(f'claude plugin marketplace add {SOURCE}', ['claude', 'plugin', 'marketplace', 'add', SOURCE],
             tolerate=(TOLERATE_CLAUDE_SOURCE, 'already added', 'already exists')),
        Step(f'claude plugin marketplace update {CLAUDE_MARKETPLACE}',
             ['claude', 'plugin', 'marketplace', 'update', CLAUDE_MARKETPLACE]),
        Step('drop the cached plugin, keeping its data', run=drop_claude_plugin),
        Step(f'claude plugin install {CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE}',
             ['claude', 'plugin', 'install', f'{CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE}'])]


def drop_claude_plugin():
    """Claude Code caches a plugin by its version, which changes rarely: a reinstall of the same
    version kept the old workflows (sessions lacked two skills a release had added). Uninstalling
    first makes the install copy the current release; not being installed yet is fine."""
    done = subprocess.run(['claude', 'plugin', 'uninstall', '--keep-data',
                           f'{CLAUDE_PLUGIN}@{CLAUDE_MARKETPLACE}'], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=120)
    return 'dropped the cached plugin' if done.returncode == 0 else 'no cached plugin to drop'


def drop_codex_plugin():
    """Codex caches a plugin by its version too (see drop_claude_plugin)."""
    done = subprocess.run(['codex', 'plugin', 'remove',
                           f'{CODEX_PLUGIN}@{CODEX_MARKETPLACE}'], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=120)
    return 'dropped the cached plugin' if done.returncode == 0 else 'no cached plugin to drop'


OCTET_INSTALLER = 'https://octet.skaft.org/install'


def octet_version(destination):
    """Verify the selected destination, never a different executable on PATH."""
    version = subprocess.run([str(destination / 'octet'), '--version'],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True,
                             errors='replace', timeout=5)
    if version.returncode or not re.fullmatch(r'octet [0-9]+\.[0-9]+\.[0-9]+\n?', version.stdout):
        raise OSError('Octet destination version verification failed')
    return version.stdout.strip()


def install_octet(output=None, update=False):
    """Reuse a working binary on install; upstream owns explicit updates and repairs."""
    output = output or Output()
    destination = BIN.absolute()
    if not update and (destination / 'octet').is_file():
        try:
            return f'{destination / "octet"}: {octet_version(destination)} (already installed; kept)'
        except (OSError, subprocess.SubprocessError):
            pass  # Broken destination: retry the official installer, never force placement.
    for command in ('curl', 'sh', 'python3', 'uname'):
        if not shutil.which(command):
            raise OSError(f'Octet requires {command}; install it and retry --only octet')

    def run(argv, stage, env=None):
        if output.verbosity > 1:
            output.line('  $ ' + shlex.join(argv), 'command')
        code, text = run_command(argv, output, env)
        if code:
            raise OSError(f'{stage}: {failure_summary(text)} (exit {code})')

    with tempfile.TemporaryDirectory(prefix='kit-octet-') as directory:
        installer = Path(directory) / 'install.sh'
        installer.touch(mode=0o600)
        run(['curl', '--disable', '--proto', '=https', '--proto-redir', '=https',
             '--tlsv1.2', '--location', '--max-redirs', '5', '--connect-timeout', '15',
             '--max-time', '300', '--max-filesize', '1048576', '--fail', '--silent',
             '--show-error', '--output', str(installer), OCTET_INSTALLER], 'Octet installer download failed')
        if not 0 < installer.stat().st_size <= 1048576:
            raise OSError('Octet installer download is empty or exceeds its size limit')
        env = {'OCTET_INSTALL_DIR': str(destination), 'OCTET_NO_MODIFY_PATH': '1'}
        if output.verbosity > 1:
            output.line('  Environment: ' + shlex.join(f'{key}={value}' for key, value in env.items()), 'command')
        try:
            run(['sh', str(installer)], 'Octet upstream installer failed', env)
            # Upstream proves the exact release version before and after placement.
            # Read back the destination, never a different Octet earlier on PATH.
            version = octet_version(destination)
        except (OSError, subprocess.SubprocessError) as exc:
            raise OSError(f'{exc}; upstream may have left a partial installation; no rollback performed') from exc
    return f'{destination / "octet"}: {version}'


def install_octet_skills():
    """Native, non-symlink entrypoints; shared instructions stay in this checkout."""
    destination = HOME / '.octet' / 'skills'
    sources = sorted((ROOT / 'adapters/skills').glob('*/SKILL.md'))
    if not sources:
        raise OSError('No portable Kit skills found in this checkout')
    entries = []
    prompts = {}
    for source in sources:
        source = source.resolve()
        header, separator, _ = source.read_text(encoding='utf-8').partition('\n---\n')
        if not header.startswith('---\n') or not separator:
            raise OSError(f'Missing skill metadata: {source}')
        target = destination / source.parent.name / 'SKILL.md'
        body = (header + separator + '\n# Kit workflow for Octet\n\n'
                f'Read and follow the portable workflow at `{source}`.\n'
                f'Resolve its relative references from `{source.parent}`, not this directory.\n'
                'Use Octet\'s native tools and preserve the user\'s scope and restrictions.\n')
        entries.append((target, body))
        name = source.parent.name
        prompts[f'kit-{name}'] = (
            f'---\ndescription: {json.dumps("Kit " + name.replace("-", " ") + " workflow")}\n---\n\n'
            f'Read and follow the portable workflow at `{source}`.\n'
            f'Resolve its relative references from `{source.parent}`.\n'
            'Work in the current target repository, not the Kit source directory.\n'
            'Use /kit-NAME for referenced Kit /NAME commands; preserve caller restrictions.\n\n'
            'User request (preserve scope and restrictions):\n$@\n')
    for selector in json.loads((ROOT / 'skills/autoresearch/UPSTREAM.json').read_text())['commands']:
        prompts[f'kit-autoresearch-{selector}'] = prompts['kit-autoresearch'].replace(
            'User request (preserve scope and restrictions):',
            f'Selected subcommand: {selector}\n\nUser request (preserve scope and restrictions):')
    prompts['kit-grill-me'] = prompts['kit-plan-with-me'].replace(
        'User request (preserve scope and restrictions):',
        'Selected mode: challenge\n\nUser request (preserve scope and restrictions):')
    entries.extend((destination.parent / 'prompts' / f'{name}.md', body)
                   for name, body in sorted(prompts.items()))
    # Refuse redirected resource roots before writing any entrypoint.
    for folder in (destination.parent, destination, *(target.parent for target, _ in entries)):
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise OSError(f'Octet skills require a regular directory: {folder}')
    def identity(target):
        if target.is_symlink():
            return ('symlink', os.readlink(target))
        return ('file', target.read_bytes()) if target.exists() else None

    originals = {}
    for target, _ in entries:
        if target.exists() and not target.is_symlink() and not target.is_file():
            raise OSError(f'Octet skill entrypoint is not a file: {target}')
        originals[target] = identity(target)
    updated, backups = 0, []
    for target, body in entries:
        if not target.is_symlink() and target.is_file() and target.read_bytes() == body.encode('utf-8'):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(body)
                stream.close()
                if identity(target) != originals[target]:
                    raise OSError(f'Octet resource changed during installation: {target}; kept unchanged')
                if target.exists() or target.is_symlink():
                    backups.append(str(set_aside(target)))
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        updated += 1
    note = '; preserved previous files: ' + ', '.join(backups) if backups else ''
    return f'{len(sources)} Kit skills and {len(prompts)} prompts ready in {destination.parent} ({updated} updated){note}'


def octet_item(output=None, mode='install'):
    system, machine = platform.system(), platform.machine().lower()
    supported = ((system == 'Darwin' and machine in ('x86_64', 'arm64', 'aarch64'))
                 or (system == 'Linux' and machine in ('x86_64', 'amd64')
                     and platform.libc_ver()[0] == 'glibc'))
    destination = BIN.absolute()
    return Item('octet', 'Octet official stable native binaries + Kit skills',
                note='bootstraps the CLI and native skills; no optional extensions',
                missing='' if supported else f'unsupported Octet binary platform: {system} {machine} (needs GNU/Linux x86-64 or macOS x86-64/arm64)',
                steps=[Step(('refresh Octet; ' if mode == 'update' else 'reuse a working destination or bootstrap Octet; ')
                            + f'download {OCTET_INSTALLER} privately when needed; run unmodified sh installer in binary mode '
                            f'with OCTET_INSTALL_DIR={destination} OCTET_NO_MODIFY_PATH=1; '
                            f'verify {destination}/octet --version', run=lambda: install_octet(output, update=mode == 'update')),
                       Step(f'install Kit skills in {HOME / ".octet/skills"} from this checkout',
                            run=install_octet_skills)])


def items(hermes_args, output=None, mode='install'):
    package = pi_package()
    pi = Item('pi', 'Pi package + bundled Ponytail', needs='pi', note='needs Node 22+')
    if package:
        pi.note = f'installed at {package}; use install.sh update to refresh'
        if mode == 'update':
            pi.steps.append(Step(f'pi update {PI_SOURCE}', ['pi', 'update', PI_SOURCE]))
        else:
            pi.steps.append(Step(f'keep the installed Pi package at {package}',
                                 run=lambda: f'{PI_SOURCE} already installed at {package}; kept'))
    else:
        pi.steps.append(Step(f'pi install {PI_SOURCE}', ['pi', 'install', PI_SOURCE]))
    # `pi config` filters outlive the install, so enable the package resources here.
    pi.steps.append(Step('enable the package skills and commands in Pi settings',
                         run=enable_pi_package))
    # The command follows the package the runners update, once it is installed.
    def command():
        installed = pi_package()
        return installed / 'pi-autowork/bin/autowork' if installed else ROOT / 'pi-autowork/bin/autowork'
    return [
        pi,
        Item('autowork', 'autowork command and TUI', note='TUI and web view need uv',
             steps=[Step('install pinned Pi RPC Python runtime',
                         [sys.executable, str(ROOT / 'scripts/install-pi-rpc.py')]),
                    Step(f'link {BIN}/autowork to the autowork release', run=lambda: link(command(), 'autowork'))]),
        Item('tx', 'tx tmux session launcher', note='keeps your existing ~/.tmux.conf',
             steps=[Step(f'install {BIN}/tx and completions', run=install_tx)]),
        hermes_item(hermes_args),
        Item('claude', 'Claude Code plugin and full suite + bundled Ponytail', needs='claude',
             # Claude Code refuses `marketplace add` when the owner's settings list that
             # marketplace from another source, such as this repository's checkout. That
             # source is the owner's choice: install from it, and never rewrite it here.
             # A recorded folder that is gone is not a choice, and claude_steps drops it
             # first so the published source installs on a host that never had it.
             # The update step below proves the configured marketplace is usable.
             steps=claude_steps()),
        Item('codex', 'Codex plugin and full suite + bundled Ponytail', needs='codex',
             # The registration carries the source URL, so a renamed repository is a
             # different source for the same marketplace id. Drop it before adding.
             steps=[Step(f'codex plugin marketplace remove {CODEX_MARKETPLACE}',
                         ['codex', 'plugin', 'marketplace', 'remove', CODEX_MARKETPLACE],
                         tolerate=('not found', 'no marketplace', 'not registered')),
                    Step(f'codex plugin marketplace add {SOURCE} --ref main',
                         ['codex', 'plugin', 'marketplace', 'add', SOURCE, '--ref', 'main']),
                    Step(f'codex plugin marketplace upgrade {CODEX_MARKETPLACE}',
                         ['codex', 'plugin', 'marketplace', 'upgrade', CODEX_MARKETPLACE]),
                    Step('drop the cached plugin', run=drop_codex_plugin),
                    Step(f'codex plugin add {CODEX_PLUGIN}@{CODEX_MARKETPLACE}',
                         ['codex', 'plugin', 'add', f'{CODEX_PLUGIN}@{CODEX_MARKETPLACE}'])]),
        octet_item(output, mode=mode),
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
            screen.addstr(0, 0, 'autowork installer: Space toggles, a all, n none, Enter installs, q quits')
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
        write('\nautowork installer (all available items are checked):')
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
    """Restart every active Kit service, including on unchanged/partial installs.

    Never revive stopped services or bypass the runner's merge-safe restart guard.
    Other host services are deliberately outside the installer's authority.
    """
    ctl = os.environ.get('PI_AUTOWORK_SYSTEMCTL', 'systemctl')
    if platform.system() != 'Linux' or not shutil.which(ctl):
        return 'service restarts unavailable (requires Linux user systemd)'
    listed = subprocess.run(
        [ctl, '--user', 'list-units', '--type=service', '--state=active',
         '--plain', '--no-legend', 'pi-autowork@*.service', 'hermes-gateway*.service',
         'kit-*.service'], capture_output=True, text=True)
    if listed.returncode:
        raise RuntimeError('cannot discover Kit services: ' + failure_summary(listed.stderr))
    units = sorted({line.split()[0] for line in listed.stdout.splitlines() if line.split()
                    and re.fullmatch(r'(?:pi-autowork@.+|hermes-gateway[^/]*|kit-[^/]+)\.service',
                                     line.split()[0])})
    failed = []
    for unit in units:
        if unit.startswith('pi-autowork@'):
            # Use the checkout entrypoint even if the autowork component was skipped.
            argv = ['bash', str(ROOT / 'pi-autowork/bin/autowork'), 'restart',
                    '--stop-workers', '--if-active', unit[len('pi-autowork@'):-len('.service')]]
        else:
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
    report = os.environ.get('AUTOWORK_INSTALL_REPORT')
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
        title = 'Autowork suite update' if mode == 'update' else 'Autowork full suite installer'
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
                    outcome, exit_code = 'failed', 1
                    detail.append(str(exc))
                    output.line(f'  FAILED: {exc}', 'failed')
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
            record('services', 'planned', 'discover and restart all active Autowork, Hermes gateway and kit-* user services')
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
    if any(key in ('claude', 'codex', 'pi', 'octet') and outcome == 'installed' for key, outcome, _ in results):
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
    selection.add_argument('--only', help='comma-separated items to install (pi,autowork,tx,hermes,claude,codex,octet)')
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
