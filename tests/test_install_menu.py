"""install.sh's component menu against fake host CLIs in a throwaway HOME.

The Hermes item runs only as a dry run here: the real setup changes live profiles.
"""
import contextlib
import errno
import fcntl
import io
import json
import os
import pty
import shutil
import shlex
import time
import stat
from types import SimpleNamespace
import selectors
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / 'install.sh'
sys.path.insert(0, str(ROOT / "scripts"))
import install_menu  # noqa: E402
NEW = 'git:github.com/TrebuchetDynamics/kit'
ORBI_SOURCE = ('git+https://github.com/XelHaku/orbi.git@'
               '1a8b2f9603f6258cb105293f238a8d3f775f3393')

# A fake Pi-Bolt: `pi-bolt list` reads installed sources from a file; install, update and remove edit it,
# and install and update materialise the skill folders the checkout under test ships.
PI = r'''#!/usr/bin/env bash
echo "pi-bolt $*" >> "$FAKE_LOG"
db=$FAKE_HOME/pi-installed
touch "$db"
materialise() {
  pkg=$FAKE_HOME/pkg/${1##*/}
  mkdir -p "$pkg/adapters/skills"
  for skill in "$FAKE_KIT_CHECKOUT"/adapters/skills/*/; do
    [[ -f $skill/SKILL.md ]] || continue
    mkdir -p "$pkg/adapters/skills/$(basename "$skill")"
    cp "$skill/SKILL.md" "$pkg/adapters/skills/$(basename "$skill")/SKILL.md"
  done
}
case $1 in
  --version) echo 1.4.0 ;;
  list) echo "User packages:"; while read -r src; do [[ -n $src ]] && { echo "  $src"; echo "    $FAKE_HOME/pkg/${src##*/}"; }; done < "$db" ;;
  install|update) if [[ -n $FAKE_PI_UPDATE_FAIL && $1 = update ]]; then
      echo "fatal: unable to access the source: network is unreachable" >&2; exit 3; fi
    if [[ $1 = install ]]; then echo "$2" >> "$db"; fi
    pkg=$FAKE_HOME/pkg/${2##*/}; mkdir -p "$pkg/adapters/skills"
    for skill in "$FAKE_KIT_CHECKOUT"/adapters/skills/*/; do
      [[ -f $skill/SKILL.md ]] && mkdir -p "$pkg/adapters/skills/$(basename "$skill")" \
        && cp "$skill/SKILL.md" "$pkg/adapters/skills/$(basename "$skill")/SKILL.md"
    done ;;
  remove) grep -vxF "$2" "$db" > "$db.new"; mv "$db.new" "$db" ;;
esac
'''
LOGGING = '#!/usr/bin/env bash\necho "$(basename "$0") $*" >> "$FAKE_LOG"\n'


# Native mutations, persisted across installer invocations. List schemas match the
# documented CLI contracts; Codex config/read shape is from an isolated real call.
HOST_MUTATIONS = 'python3 -c ' + shlex.quote(r'''
import json, os, pathlib, sys
home = pathlib.Path(os.environ['FAKE_HOME'])
host = pathlib.Path(sys.argv[1]).name
args = sys.argv[2:]
def read(path, default):
    return json.loads(path.read_text()) if path.exists() else default
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
if host == 'claude':
    path = pathlib.Path(os.environ.get('CLAUDE_CONFIG_DIR', home / '.claude')) / 'plugins/known_marketplaces.json'
    registry = read(path, {})
    plugins_path = home / 'claude-installed.json'
    plugins = read(plugins_path, [])
    scope = args[args.index('--scope') + 1] if '--scope' in args else 'user'
    if args[:3] == ['plugin', 'marketplace', 'add']:
        if any(r.get('source', {}).get('repo') == 'TrebuchetDynamics/kit' for r in registry.values()):
            print('marketplace already present')
        else:
            registry['kit'] = {'source': {'source': 'github', 'repo': 'TrebuchetDynamics/kit'}}
    elif args[:3] == ['plugin', 'marketplace', 'remove']:
        name = args[3]
        registry.pop(name, None)
        plugins = [p for p in plugins if not p['id'].endswith('@' + name)]
        for settings in (home / '.claude/settings.json', pathlib.Path.cwd() / '.claude/settings.json', pathlib.Path.cwd() / '.claude/settings.local.json'):
            if settings.exists():
                data = read(settings, {})
                data.get('extraKnownMarketplaces', {}).pop(name, None)
                data['enabledPlugins'] = {k:v for k,v in data.get('enabledPlugins', {}).items() if not k.endswith('@' + name)}
                write(settings, data)
    elif args[:2] == ['plugin', 'install']:
        plugins.append({'id': args[2], 'scope': scope, 'enabled': True, 'projectPath': str(pathlib.Path.cwd())})
    write(path, registry)
    write(plugins_path, plugins)
else:
    path = home / 'codex-marketplaces.json'
    registry = read(path, {'marketplaces': []})
    plugins_path = home / 'codex-plugins.json'
    plugins = read(plugins_path, {})
    if args == ['app-server']:
        effective_home = pathlib.Path(os.environ.get('CODEX_HOME', home / '.codex'))
        layers_path = home / 'codex-layers.json'
        entries = {r['name']: {'source_type': r['marketplaceSource']['sourceType'], 'source': r['marketplaceSource']['source']} for r in registry['marketplaces']}
        layers = read(layers_path, [{'name': {'type': 'user', 'file': str(effective_home / 'config.toml'), 'profile': None}, 'config': {'marketplaces': entries}}])
        for line in sys.stdin:
            req = json.loads(line)
            result = {'codexHome': str(effective_home)} if req['method'] == 'initialize' else {'config': {'marketplaces': entries}, 'origins': {}, 'layers': layers}
            print(json.dumps({'id': req['id'], 'result': result}), flush=True)
        sys.exit()
    if args[:3] == ['plugin', 'marketplace', 'add']:
        if any(r['marketplaceSource']['source'].endswith('/kit.git') for r in registry['marketplaces']):
            print('marketplace already present')
        else:
            registry['marketplaces'].append({'name': 'kit-marketplace', 'root': str(home / 'kit-marketplace'), 'marketplaceSource': {'sourceType': 'git', 'source': 'https://github.com/TrebuchetDynamics/kit.git'}})
    elif args[:3] == ['plugin', 'marketplace', 'remove']:
        registry['marketplaces'] = [r for r in registry['marketplaces'] if r['name'] != args[3]]
    elif args[:2] == ['plugin', 'remove']:
        name = args[2].split('@')[1]
        plugins[name]['installed'] = [p for p in plugins[name]['installed'] if p['pluginId'] != args[2]]
    elif args[:2] == ['plugin', 'add']:
        plugin, name = args[2].split('@')
        row = next(r for r in registry['marketplaces'] if r['name'] == name)
        plugins[name] = {'installed': [{'name': plugin, 'pluginId': args[2], 'marketplaceName': name, 'installed': True, 'enabled': True, 'source': {'source': 'local', 'path': row['root']}, 'marketplaceSource': row['marketplaceSource']}], 'available': []}
    write(path, registry)
    write(plugins_path, plugins)
''') + ' \"$0\" \"$@\"\n'


class InstallMenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        (self.home / '.codex').mkdir()
        self.project = self.home / 'project'
        self.project.mkdir()
        self.bin = self.home / 'fakebin'
        self.bin.mkdir()
        self.log = self.home / 'calls.log'
        self.log.touch()
        self.bolt = self.home / '.local/bin/pi-bolt'
        self.fake_bolt(PI)
        (self.home / 'pi-bolt-fixture').write_text(PI)
        self.fake('uv', LOGGING + f'''
if [[ "$*" != "tool install --python 3.14 {ORBI_SOURCE}" ]]; then exit 91; fi
if [[ -n "$ORBI_INSTALL_FAIL" ]]; then exit 17; fi
mkdir -p "$UV_TOOL_BIN_DIR"
printf '#!/bin/sh\\necho "orbi $*" >> "$FAKE_LOG"\\necho orbi 0.7.41\\n' > "$UV_TOOL_BIN_DIR/orbi"
chmod 755 "$UV_TOOL_BIN_DIR/orbi"
''')
        self.upstream = self.home / 'upstream-pi-bolt-install.sh'
        self.upstream.write_text('''#!/bin/sh
set -eu
printf 'pi-bolt-installer %s|%s|%s\n' "$PIBOLT_BIN_DIR" "$PIBOLT_YES" "$PIBOLT_EXTENSIONS" >> "$FAKE_LOG"
case "${PI_BOLT_FIXTURE_STAGE:-}" in
  install) echo 'release signature verification failed' >&2; exit 9 ;;
esac
mkdir -p "$PIBOLT_BIN_DIR"
cp "$FAKE_HOME/pi-bolt-fixture" "$PIBOLT_BIN_DIR/pi-bolt"
chmod 755 "$PIBOLT_BIN_DIR/pi-bolt"
''')
        self.fake('curl', '''#!/usr/bin/env python3
import os, pathlib, shutil, stat, sys
args = sys.argv[1:]
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write('curl ' + ' '.join(args) + '\\n')
if args[-1].startswith('https://api.github.com/repos/opensec-git/Pi-Bolt/releases'):
    if os.environ.get('FAKE_RELEASE_FAIL'):
        print('release API unavailable', file=sys.stderr)
        raise SystemExit(22)
    dest = pathlib.Path(args[args.index('--output') + 1])
    dest.write_text((pathlib.Path(os.environ['FAKE_HOME']) / 'release.json').read_text())
    raise SystemExit(0)
if args[-1] != 'https://pi-bolt.opensec.in/install.sh':
    raise SystemExit('unexpected network request (stock Pi downloads forbidden)')
dest = pathlib.Path(args[args.index('--output') + 1])
assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
assert stat.S_IMODE(dest.stat().st_mode) == 0o600
shutil.copyfile(pathlib.Path(os.environ['FAKE_HOME']) / 'upstream-pi-bolt-install.sh', dest)
if os.environ.get('PI_BOLT_FIXTURE_STAGE') == 'download-empty':
    dest.write_bytes(b'')
''')
        (self.home / 'release.json').write_text(json.dumps({'tag_name': 'bolt-v1.4.0', 'draft': False, 'prerelease': False}))
        self.fake('systemctl', LOGGING)
        self.claude_host()
        self.codex_registry()
        self.env = {'PATH': f'{self.bin}:/usr/bin:/bin', 'HOME': str(self.home), 'FAKE_LOG': str(self.log),
                    'FAKE_HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config'),
                    'KIT_SYSTEMCTL': str(self.bin / 'systemctl'), 'LANG': 'C.UTF-8',
                    'FAKE_KIT_CHECKOUT': str(ROOT),
                    'TMPDIR': str(self.home), 'KIT_INSTALL_NO_PULL': '1'}  # never pull the checkout under test
        # In-process installer tests must also never discover the real host fleet.
        self.environment = patch.dict(os.environ, self.env)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        # Module constants were loaded before this throwaway HOME was selected.
        destination = patch.object(install_menu, 'BIN', self.home / '.local/bin')
        destination.start()
        self.addCleanup(destination.stop)

    def fake(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o755)

    def install(self, *args, stdin=None, env=None):
        return subprocess.run(['bash', str(INSTALL), *args], env={**self.env, **(env or {})}, input=stdin,
                              capture_output=True, text=True, timeout=120, cwd=self.project)

    def calls(self, prefix=''):
        return [c for c in self.log.read_text().splitlines() if c.startswith(prefix)]

    def installed_package(self, only=None):
        """A package directory Pi reports as installed, shipping the named skill folders.

        ``only=None`` copies every skill folder this checkout ships; a subset stands
        for a checkout older than this one.
        """
        shipped = sorted(p.name for p in (ROOT / 'adapters/skills').iterdir()
                         if (p / 'SKILL.md').is_file())
        package = self.home / 'pkg/kit'
        for name in shipped if only is None else only:
            skill = package / 'adapters/skills' / name
            skill.mkdir(parents=True, exist_ok=True)
            (skill / 'SKILL.md').write_text(f'---\nname: {name}\n---\n')
        (self.home / 'pi-installed').write_text(NEW + '\n')  # what the fake `pi-bolt list` reports
        return package

    def fake_bolt(self, body):
        self.bolt.parent.mkdir(parents=True, exist_ok=True)
        self.bolt.write_text(body)
        self.bolt.chmod(0o755)

    def claude_host(self, installed=(), mutation=''):
        (self.home / 'claude-installed.json').write_text(json.dumps(installed))
        self.fake('claude', LOGGING + '''
if [[ "$*" == "plugin list --json" ]]; then
  cat "$FAKE_HOME/claude-installed.json"
else
  :
''' + mutation + '\n' + HOST_MUTATIONS + '\nfi\n')

    def codex_registry(self, marketplaces=(), installed=None, mutation=''):
        """Pinned Codex CLI JSON contract, not private config emulation."""
        (self.home / 'codex-marketplaces.json').write_text(json.dumps({'marketplaces': list(marketplaces)}))
        (self.home / 'codex-plugins.json').write_text(json.dumps(installed or {}))
        self.fake('codex', LOGGING + r'''
if [[ "$*" == "plugin marketplace list --json" ]]; then
  cat "$FAKE_HOME/codex-marketplaces.json"
elif [[ "$1 $2" == "plugin list" ]]; then
  python3 -c 'import json,os,sys; print(json.dumps(json.load(open(os.environ["FAKE_HOME"]+"/codex-plugins.json")).get(sys.argv[1], {"installed":[],"available":[]})))' "$4"
else
  :
''' + mutation + '\n' + HOST_MUTATIONS + '\nfi\n')

    def marketplace(self, name):
        return {'name': name, 'root': str(self.home / name),
                'marketplaceSource': {'sourceType': 'git',
                                      'source': 'https://github.com/TrebuchetDynamics/kit.git'}}

    def claude_registry(self, names, source=None):
        folder = self.home / '.claude/plugins'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'known_marketplaces.json').write_text(json.dumps({
            name: {'source': source or {'source': 'github', 'repo': 'TrebuchetDynamics/kit'}}
            for name in names}))

    def test_wrong_name_source_replacement_converges_and_repeat_is_nondestructive(self):
        for host, canonical in (('claude', 'kit'), ('codex', 'kit-marketplace')):
            with self.subTest(host=host):
                self.log.write_text('')
                self.wrong_source(host)
                result = self.install('--only', host)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                calls = self.calls(host)
                remove = next(i for i,c in enumerate(calls) if 'marketplace remove neutral-source' in c)
                add = next(i for i,c in enumerate(calls) if 'marketplace add TrebuchetDynamics/kit' in c)
                self.assertLess(remove, add)
                self.assert_canonical(host)
                self.log.write_text('')
                repeated = self.install('update', '--only', host)
                self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
                self.assertFalse(any(' remove ' in c or ' uninstall ' in c for c in self.calls(host)))

    def test_add_success_without_canonical_readback_never_updates_missing_name(self):
        for host in ('claude', 'codex'):
            with self.subTest(host=host):
                self.log.write_text('')
                if host == 'claude':
                    self.claude_registry([])
                    self.claude_host(mutation='echo "added successfully"; exit 0')
                else:
                    self.codex_registry(mutation='echo "already present"; exit 0')
                result = self.install('--only', host)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse(any('marketplace update' in c or 'marketplace upgrade' in c for c in self.calls(host)))
                self.assertIn('partial state', result.stdout)

    def wrong_source(self, host, names=('neutral-source',), plugin='kit', scope='user', mutation=''):
        if host == 'claude':
            self.claude_registry(names)
            self.claude_host([{'id': f'{plugin}@{names[0]}', 'scope': scope, 'enabled': False,
                               'projectPath': str(self.project)}] if plugin else [], mutation)
        else:
            rows = [self.marketplace(name) for name in names]
            row = rows[0]
            self.codex_registry(rows, {names[0]: {'installed': [{
                'name': plugin, 'pluginId': f'{plugin}@{names[0]}', 'marketplaceName': names[0],
                'installed': True, 'enabled': False, 'source': {'source': 'local', 'path': row['root']},
                'marketplaceSource': row['marketplaceSource']}] if plugin else [], 'available': []}}, mutation)

    def assert_canonical(self, host):
        if host == 'claude':
            registry = json.loads((self.home / '.claude/plugins/known_marketplaces.json').read_text())
            self.assertEqual(list(registry), ['kit'])
            self.assertEqual(registry['kit']['source'], {'source': 'github', 'repo': 'TrebuchetDynamics/kit'})
            plugins = json.loads((self.home / 'claude-installed.json').read_text())
            self.assertEqual([p['id'] for p in plugins], ['kit@kit'])
        else:
            registry = json.loads((self.home / 'codex-marketplaces.json').read_text())
            self.assertEqual(registry['marketplaces'], [self.marketplace('kit-marketplace')])
            plugins = json.loads((self.home / 'codex-plugins.json').read_text())
            self.assertEqual([p['pluginId'] for p in plugins['kit-marketplace']['installed']], ['kit@kit-marketplace'])
            self.assertEqual(plugins.get('neutral-source', {}).get('installed', []), [])

    def test_add_discovers_wrong_name_success_or_already_present_then_replaces(self):
        for host in ('claude', 'codex'):
            for code in (0, 4):
                with self.subTest(host=host, add_exit=code):
                    self.log.write_text('')
                    marker = self.home / 'first-add'
                    marker.unlink(missing_ok=True)
                    if host == 'claude':
                        self.claude_registry([])
                        destination = self.home / '.claude/plugins/known_marketplaces.json'
                        observed = {'neutral-source': {'source': {'source': 'github', 'repo': 'TrebuchetDynamics/kit'}}}
                    else:
                        destination = self.home / 'codex-marketplaces.json'
                        observed = {'marketplaces': [self.marketplace('neutral-source')]}
                    fixture = self.home / 'discovered.json'
                    fixture.write_text(json.dumps(observed))
                    mutation = f'''if [[ "$2 $3" == "marketplace add" && ! -e "$FAKE_HOME/first-add" ]]; then
  touch "$FAKE_HOME/first-add"
  cp "$FAKE_HOME/discovered.json" {shlex.quote(str(destination))}
  echo 'source already registered (not identity evidence)'
  exit {code}
fi'''
                    if host == 'claude':
                        self.claude_host(mutation=mutation)
                    else:
                        self.codex_registry(mutation=mutation)
                    result = self.install('--only', host)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    calls = self.calls(host)
                    first_add = next(i for i,c in enumerate(calls) if 'marketplace add' in c)
                    remove = next(i for i,c in enumerate(calls) if 'marketplace remove neutral-source' in c)
                    last_add = max(i for i,c in enumerate(calls) if 'marketplace add' in c)
                    update = next(i for i,c in enumerate(calls) if 'marketplace update' in c or 'marketplace upgrade' in c)
                    self.assertLess(first_add, remove)
                    self.assertLess(remove, last_add)
                    self.assertLess(last_add, update)
                    self.assertTrue(any(' list ' in c for c in calls[last_add+1:update]))
                    self.assert_canonical(host)

    def test_replacement_interrupted_after_remove_resumes_from_observed_state(self):
        for host in ('claude', 'codex'):
            with self.subTest(host=host):
                self.log.write_text('')
                mutation = 'if [[ "$2 $3" == "marketplace add" ]]; then echo "fixture network unavailable"; exit 23; fi'
                self.wrong_source(host, mutation=mutation)
                result = self.install('--only', host)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('partial state', result.stdout)
                self.assertIn('canonical=False', result.stdout)
                self.assertIn('rerun', result.stdout)
                self.assertFalse(any('marketplace update' in c or 'marketplace upgrade' in c for c in self.calls(host)))
                # Keep persisted state; remove only the injected transient failure.
                path = self.bin / host
                path.write_text(path.read_text().replace(mutation, ':'))
                self.log.write_text('')
                retry = self.install('--only', host)
                self.assertEqual(retry.returncode, 0, retry.stdout)
                self.assertFalse(any(' remove ' in c or ' uninstall ' in c for c in self.calls(host)))
                self.assert_canonical(host)

    def test_replacement_unsafe_source_or_effects_holds_before_any_mutation(self):
        for host in ('claude', 'codex'):
            for case in ('other-plugin', 'duplicate-source', 'foreign-canonical', 'unknown-installed'):
                with self.subTest(host=host, case=case):
                    self.log.write_text('')
                    names = ('neutral-source', 'second-source') if case == 'duplicate-source' else ('neutral-source',)
                    self.wrong_source(host, names, plugin='other' if case == 'other-plugin' else 'kit')
                    if case == 'foreign-canonical':
                        if host == 'claude':
                            path = self.home / '.claude/plugins/known_marketplaces.json'
                            data = json.loads(path.read_text())
                            data['kit'] = {'source': {'source': 'github', 'repo': 'foreign/kit'}}
                        else:
                            path = self.home / 'codex-marketplaces.json'
                            data = json.loads(path.read_text())
                            row = self.marketplace('kit-marketplace')
                            row['marketplaceSource']['source'] = 'foreign/kit'
                            data['marketplaces'].append(row)
                        path.write_text(json.dumps(data))
                    if case == 'unknown-installed':
                        path = self.home / ('claude-installed.json' if host == 'claude' else 'codex-plugins.json')
                        path.write_text('[null]' if host == 'claude' else '{"neutral-source":{"installed":[null],"available":[]}}')
                    result = self.install('--only', host)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertTrue(all(' list ' in c for c in self.calls(host)), self.calls(host))

    def test_claude_replacement_preserves_single_scope_and_holds_cross_scope(self):
        for scope in ('project', 'local', 'managed', 'multiple'):
            with self.subTest(scope=scope):
                self.log.write_text('')
                self.wrong_source('claude', scope='user' if scope == 'multiple' else scope)
                settings = self.project / '.claude/settings.json'
                settings.parent.mkdir(exist_ok=True)
                if scope == 'multiple':
                    settings.write_text(json.dumps({'extraKnownMarketplaces': {'neutral-source': {
                        'source': {'source': 'github', 'repo': 'TrebuchetDynamics/kit'}}}}))
                result = self.install('--only', 'claude')
                if scope in ('managed', 'multiple'):
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse(any(' remove ' in c for c in self.calls('claude')))
                else:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn(f'claude plugin marketplace remove neutral-source --scope {scope}', self.calls())
                    self.assertIn(f'claude plugin marketplace add TrebuchetDynamics/kit --scope {scope}', self.calls())
                    self.assertIn(f'claude plugin install kit@kit --scope {scope}', self.calls())

    def test_codex_replacement_requires_base_user_layer_and_kit_only_config(self):
        for kind in ('system', 'project', 'profile', 'shadowed', 'other-plugin', 'managed-plugin', 'missing'):
            with self.subTest(kind=kind):
                self.log.write_text('')
                self.wrong_source('codex')
                entry = {'source_type': 'git', 'source': self.marketplace('neutral-source')['marketplaceSource']['source']}
                user = {'name': {'type': 'user', 'file': str(self.home / '.codex/config.toml'), 'profile': None},
                        'config': {'marketplaces': {'neutral-source': entry}}}
                layers = [user]
                if kind in ('system', 'project'):
                    user['name']['type'] = kind
                elif kind == 'profile':
                    user['name']['profile'] = 'work'
                elif kind == 'shadowed':
                    layers.append({'name': {'type': 'system', 'file': '/etc/codex/config.toml'},
                                   'config': {'marketplaces': {'neutral-source': entry}}})
                elif kind == 'other-plugin':
                    user['config']['plugins'] = {'other@neutral-source': {'enabled': False}}
                elif kind == 'managed-plugin':
                    layers.append({'name': {'type': 'system', 'file': '/etc/codex/config.toml'},
                                   'config': {'plugins': {'kit@neutral-source': {'enabled': True}}}})
                else:
                    layers = []
                path = self.home / 'codex-layers.json'
                path.write_text(json.dumps(layers))
                result = self.install('--only', 'codex')
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse(any(' remove ' in c for c in self.calls('codex')), self.calls())
                path.unlink()

    def test_final_installed_id_must_be_read_back(self):
        for host in ('claude', 'codex'):
            with self.subTest(host=host):
                self.log.write_text('')
                mutation = 'if [[ "$1 $2" == "plugin install" || "$1 $2" == "plugin add" ]]; then echo "installed"; exit 0; fi'
                if host == 'claude':
                    self.claude_registry(['kit'])
                    self.claude_host(mutation=mutation)
                else:
                    self.codex_registry([self.marketplace('kit-marketplace')], mutation=mutation)
                result = self.install('--only', host)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('expected installed ID', result.stdout)

    def test_replacement_attempt_is_bounded_and_checks_removed_plugin(self):
        for host in ('claude', 'codex'):
            for case in ('remove-noop', 'plugin-remains', 'add-wrong-again', 'remove-fails'):
                with self.subTest(host=host, case=case):
                    self.log.write_text('')
                    if case == 'remove-noop':
                        mutation = 'if [[ "$2 $3" == "marketplace remove" ]]; then exit 0; fi'
                    elif case == 'plugin-remains':
                        if host == 'claude':
                            mutation = 'if [[ "$2 $3" == "marketplace remove" ]]; then echo "{}" > "$FAKE_HOME/.claude/plugins/known_marketplaces.json"; exit 0; fi'
                        else:
                            mutation = 'if [[ "$1 $2" == "plugin remove" ]]; then exit 0; fi'
                    elif case == 'remove-fails':
                        mutation = 'if [[ "$2 $3" == "marketplace remove" ]]; then echo "fixture remove denied"; exit 27; fi'
                    else:
                        mutation = 'if [[ "$2 $3" == "marketplace add" ]]; then cp "$FAKE_HOME/again.json" "$FAKE_HOME/' + ('.claude/plugins/known_marketplaces.json' if host == 'claude' else 'codex-marketplaces.json') + '"; exit 0; fi'
                    self.wrong_source(host, mutation=mutation)
                    registry_path = self.home / ('.claude/plugins/known_marketplaces.json' if host == 'claude' else 'codex-marketplaces.json')
                    (self.home / 'again.json').write_bytes(registry_path.read_bytes())
                    result = self.install('--only', host)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('partial state', result.stdout)
                    self.assertEqual(sum('marketplace remove neutral-source' in c for c in self.calls(host)), 1)
                    self.assertFalse(any('marketplace update' in c or 'marketplace upgrade' in c for c in self.calls(host)))

    def test_replacement_preserves_unrelated_marketplaces_and_canonical_plugin(self):
        for host in ('claude', 'codex'):
            with self.subTest(host=host):
                self.log.write_text('')
                self.wrong_source(host, plugin='')
                if host == 'claude':
                    path = self.home / '.claude/plugins/known_marketplaces.json'
                    data = json.loads(path.read_text())
                    other = {'source': {'source': 'github', 'repo': 'other/plugins'}}
                    data.update(kit={'source': {'source': 'github', 'repo': 'TrebuchetDynamics/kit'}}, unrelated=other)
                    path.write_text(json.dumps(data))
                    self.claude_host([{'id': 'kit@kit', 'scope': 'user', 'enabled': False},
                                      {'id': 'other@unrelated', 'scope': 'user', 'enabled': True}])
                else:
                    path = self.home / 'codex-marketplaces.json'
                    data = json.loads(path.read_text())
                    other = {**self.marketplace('unrelated'), 'marketplaceSource': {'sourceType': 'git', 'source': 'other/plugins'}}
                    data['marketplaces'].extend([self.marketplace('kit-marketplace'), other])
                    path.write_text(json.dumps(data))
                result = self.install('--only', host)
                self.assertEqual(result.returncode, 0, result.stdout)
                calls = self.calls(host)
                self.assertFalse(any('marketplace add' in c for c in calls))
                self.assertFalse(any('unrelated' in c for c in calls))
                after = json.loads(path.read_text())
                self.assertEqual(after['unrelated'] if host == 'claude' else next(r for r in after['marketplaces'] if r['name'] == 'unrelated'), other)

    def test_replacement_uses_effective_host_config_home(self):
        for host, key in (('claude', 'CLAUDE_CONFIG_DIR'), ('codex', 'CODEX_HOME')):
            with self.subTest(host=host):
                self.log.write_text('')
                self.wrong_source(host)
                effective = self.home / (host + '-alternate')
                effective.mkdir()
                if host == 'claude':
                    shutil.move(str(self.home / '.claude/plugins'), str(effective / 'plugins'))
                    self.claude_registry(['kit'], {'source': 'github', 'repo': 'foreign/kit'})
                    untouched = (self.home / '.claude/plugins/known_marketplaces.json').read_bytes()
                result = self.install('--only', host, env={key: str(effective)})
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertTrue(any('marketplace remove neutral-source' in c for c in self.calls(host)))
                if host == 'claude':
                    self.assertEqual((self.home / '.claude/plugins/known_marketplaces.json').read_bytes(), untouched)
                    self.assertEqual(list(json.loads((effective / 'plugins/known_marketplaces.json').read_text())), ['kit'])

    def test_codex_config_probe_failure_holds_and_timeout_is_bounded(self):
        for output in ('malformed', '{"id":1,"error":{"message":"unsupported"}}'):
            with self.subTest(output=output):
                self.wrong_source('codex')
                path = self.bin / 'codex'
                body = path.read_text()
                path.write_text(body.replace('else\n  :', 'elif [[ "$1" == "app-server" ]]; then\n  echo ' + shlex.quote(output) + '\nelse\n  :'))
                result = self.install('--only', 'codex')
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('cannot qualify writable config layers', result.stdout)
                self.assertFalse(any(' remove ' in c for c in self.calls('codex')))
        # The unresponsive stdio path has a termination guard: never actually wait
        # for the 30-second deadline in a test, and require one bounded select.
        self.codex_registry()
        from unittest.mock import MagicMock
        selector = MagicMock()
        selector.__enter__.return_value = selector
        selector.select.return_value = []
        with patch.object(install_menu.selectors, 'DefaultSelector', return_value=selector):
            with self.assertRaisesRegex(OSError, 'timed out or closed'):
                install_menu.codex_config_layers(install_menu.Output(verbosity=0))
        selector.select.assert_called_once()
        self.assertLessEqual(selector.select.call_args.args[0], 30)

    def test_claude_replacement_requires_writable_registry_parent(self):
        self.wrong_source('claude')
        folder = self.home / '.claude/plugins'
        folder.chmod(0o555)
        try:
            result = self.install('--only', 'claude')
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn('unwritable', result.stdout)
            self.assertFalse(any(' remove ' in c for c in self.calls('claude')))
        finally:
            folder.chmod(0o755)

    def test_replacement_readback_failure_reports_partial_state(self):
        for host in ('claude', 'codex'):
            with self.subTest(host=host):
                target = '.claude/plugins/known_marketplaces.json' if host == 'claude' else 'codex-marketplaces.json'
                mutation = 'if [[ "$2 $3" == "marketplace remove" ]]; then echo "{" > "$FAKE_HOME/' + target + '"; exit 0; fi'
                self.wrong_source(host, mutation=mutation)
                result = self.install('--only', host)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('partial state', result.stdout)
                self.assertIn('readback failed', result.stdout)
                self.assertIn('rerun', result.stdout)

    def test_marketplace_fresh_and_canonical_traces(self):
        for canonical in (False, True):
            with self.subTest(canonical=canonical):
                self.log.write_text('')
                self.codex_registry([self.marketplace('kit-marketplace')] if canonical else [])
                self.claude_registry(['kit'] if canonical else [])
                self.claude_host()
                result = self.install('--only', 'claude,codex')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                calls = self.calls()
                self.assertIn('claude plugin install kit@kit', calls)
                self.assertIn('codex plugin add kit@kit-marketplace', calls)
                self.assertFalse(any(' remove ' in c or ' uninstall ' in c for c in calls))
                self.assertEqual('claude plugin marketplace add TrebuchetDynamics/kit' in calls,
                                 not canonical)
                self.assertEqual('codex plugin marketplace add TrebuchetDynamics/kit --ref main' in calls,
                                 not canonical)

    def test_canonical_installed_updates_preserve_scope_source_and_disabled_state(self):
        for scope in ('user', 'project', 'local'):
            with self.subTest(scope=scope):
                self.log.write_text('')
                self.claude_registry(['kit'], {'source': 'directory', 'path': str(ROOT)})
                plugin = {'id': 'kit@kit', 'scope': scope, 'enabled': False,
                          'version': '1.0', 'installPath': str(self.home / 'cache'),
                          'projectPath': str(self.project)}
                self.claude_host([plugin])
                registration = self.marketplace('kit-marketplace')
                codex_plugin = {'pluginId': 'kit@kit-marketplace', 'name': 'kit',
                                'marketplaceName': 'kit-marketplace', 'installed': True,
                                'enabled': False, 'source': {'source': 'local', 'path': registration['root']},
                                'marketplaceSource': registration['marketplaceSource']}
                self.codex_registry([registration], {'kit-marketplace': {
                    'installed': [codex_plugin], 'available': []}})
                settings = self.home / '.claude/settings.json'
                settings.write_text(json.dumps({'enabledPlugins': {'other@elsewhere': True},
                                                'permissions': {'deny': ['keep-me']}}))
                snapshot = {p: p.read_bytes() for p in (settings,
                    self.home / '.claude/plugins/known_marketplaces.json',
                    self.home / 'codex-marketplaces.json', self.home / 'codex-plugins.json')}
                result = self.install('update', '--only', 'claude,codex')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.calls('claude'), ['claude plugin list --json',
                    'claude plugin marketplace update kit', f'claude plugin update kit@kit --scope {scope}',
                    'claude plugin list --json'])
                self.assertEqual(self.calls('codex'), ['codex plugin marketplace list --json',
                    'codex plugin list --marketplace kit-marketplace --json',
                    'codex plugin marketplace upgrade kit-marketplace',
                    'codex plugin marketplace list --json',
                    'codex plugin list --marketplace kit-marketplace --json'])
                self.assertEqual({p: p.read_bytes() for p in snapshot}, snapshot)

    def test_claude_settings_scope_selection(self):
        self.claude_registry(['kit'])
        settings = self.project / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'enabledPlugins': {'kit@kit': True, 'other@elsewhere': False}}))
        before = settings.read_bytes()
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('claude plugin install kit@kit --scope project', self.calls('claude'))
        self.assertEqual(settings.read_bytes(), before)
    def test_claude_foreign_unknown_conflicting_and_failed_reads_hold(self):
        cases = (
            ({'source': 'github', 'repo': 'foreign/kit'}, 'foreign'),
            ({'source': 'git', 'url': 'https://example.com/kit.git'}, 'foreign'),
            ({'source': 'url', 'url': 'https://example.com/catalog'}, 'unknown'),
            ({}, 'source'),
            (None, 'metadata'),
        )
        for source, reason in cases:
            with self.subTest(source=source):
                self.claude_registry(['kit'])
                registry = self.home / '.claude/plugins/known_marketplaces.json'
                registry.write_text(json.dumps({'kit': {'source': source}}))
                self.log.write_text('')
                result = self.install('--only', 'claude')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(reason, result.stdout)
                self.assertEqual(self.calls('claude'), ['claude plugin list --json'])
        self.claude_registry(['kit'])
        settings = self.home / '.claude/settings.json'
        settings.write_text(json.dumps({'extraKnownMarketplaces': {'kit': {
            'source': {'source': 'git', 'url': 'https://github.com/TrebuchetDynamics/kit.git'}}}}))
        self.log.write_text('')
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('conflicting', result.stdout)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json'])
        for content in ('{', '[]', '{"extraKnownMarketplaces":[]}'):
            with self.subTest(content=content):
                settings.write_text(content)
                self.log.write_text('')
                result = self.install('--only', 'claude')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(self.calls('claude'), [])
        settings.unlink()
        for installed in ({}, [None], [{'id': 'kit'}], [{'id': 'kit@kit', 'scope': 'unknown'}]):
            with self.subTest(installed=installed):
                self.claude_host(installed)
                self.log.write_text('')
                result = self.install('--only', 'claude')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(self.calls('claude'), ['claude plugin list --json'])

    def test_claude_malformed_installed_list_holds(self):
        (self.home / 'claude-installed.json').write_text('{')
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('malformed JSON', result.stdout)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json'])

    def test_codex_unknown_marketplace_and_plugin_output_refuses_all_modification(self):
        canonical = self.marketplace('kit-marketplace')
        plugin = {'pluginId': 'kit@kit-marketplace', 'name': 'kit',
                  'marketplaceName': 'kit-marketplace', 'installed': True, 'enabled': True,
                  'source': {'source': 'local', 'path': canonical['root']},
                  'marketplaceSource': canonical['marketplaceSource']}
        cases = [
            ('malformed', '{', None, 'malformed JSON'),
            ('unknown', json.dumps([]), None, 'unsupported marketplaces'),
            ('wrong rows', json.dumps({'marketplaces': {}}), None, 'unsupported marketplaces'),
            ('unknown identity', json.dumps({'marketplaces': [None]}), None, 'identity'),
            ('duplicate name', json.dumps({'marketplaces': [canonical, canonical]}), None, 'ambiguous'),
            ('missing source', {'name': 'kit-marketplace', 'root': canonical['root']}, None, 'metadata'),
            ('missing root', {'name': 'kit-marketplace', 'marketplaceSource': canonical['marketplaceSource']}, None, 'root'),
            ('foreign', {**canonical, 'marketplaceSource': {'sourceType': 'git', 'source': 'foreign/kit'}}, None, 'foreign'),
            ('unknown source kind', {**canonical, 'marketplaceSource': {'sourceType': 'remote', 'source': 'kit'}}, None, 'unknown'),
            ('stale directory', {**canonical, 'marketplaceSource': {'sourceType': 'local', 'source': canonical['root']}}, None, 'stale'),
            ('unknown plugin output', canonical, [], 'unsupported installed'),
            ('missing available', canonical, {'installed': []}, 'unsupported filtered'),
            ('duplicate plugin', canonical, {'installed': [plugin, plugin], 'available': []}, 'ambiguous'),
            ('malformed plugin JSON', canonical, 'invalid-json', 'unsupported installed'),
            ('unresolved plugin', canonical, {'installed': [{**plugin, 'pluginId': 'kit'}], 'available': []}, 'identity'),
            ('missing enabled', canonical, {'installed': [{**plugin, 'enabled': None}], 'available': []}, 'identity'),
            ('missing plugin source', canonical, {'installed': [{**plugin, 'source': {}}], 'available': []}, 'source'),
            ('missing plugin marketplace source', canonical, {'installed': [{**plugin, 'marketplaceSource': None}], 'available': []}, 'source'),
            ('mismatched plugin marketplace source', canonical, {'installed': [{**plugin, 'marketplaceSource': {'sourceType': 'local', 'source': '/elsewhere'}}], 'available': []}, 'source'),
            ('mismatched plugin path', canonical, {'installed': [{**plugin, 'source': {'source': 'local', 'path': '/elsewhere'}}], 'available': []}, 'source'),
            ('installed without registry', None, {'installed': [plugin], 'available': []}, 'source'),
        ]
        for label, registration, output, reason in cases:
            with self.subTest(case=label):
                self.codex_registry([registration] if isinstance(registration, dict) else [],
                                    {'kit-marketplace': output} if output is not None else {})
                if isinstance(registration, str):
                    (self.home / 'codex-marketplaces.json').write_text(registration)
                self.log.write_text('')
                before = (self.home / 'codex-marketplaces.json').read_bytes()
                result = self.install('--only', 'codex,tx', '--quiet')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(reason, result.stdout)
                self.assertIn('manual migration required', result.stdout)
                self.assertRegex(result.stdout, r'tx\s+installed')
                self.assertTrue(all(' list ' in call for call in self.calls('codex')))
                self.assertNotIn('codex plugin list --json', self.calls('codex'))
                self.assertEqual((self.home / 'codex-marketplaces.json').read_bytes(), before)
        self.codex_registry([canonical])
        self.fake('codex', (self.bin / 'codex').read_text().replace(
            '  python3 -c', '  echo "filtered list unavailable" >&2; exit 3\n  python3 -c'))
        self.log.write_text('')
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('filtered list unavailable', result.stdout)
        self.assertTrue(all(' list ' in call for call in self.calls('codex')))

    def test_codex_local_source_reused(self):
        canonical = self.marketplace('kit-marketplace')
        canonical.update(root=str(ROOT), marketplaceSource={'sourceType': 'local', 'source': str(ROOT)})
        self.codex_registry([canonical])
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('codex')[-3:], ['codex plugin add kit@kit-marketplace',
            'codex plugin marketplace list --json', 'codex plugin list --marketplace kit-marketplace --json'])
        self.assertFalse(self.calls('codex plugin marketplace upgrade'))
        self.assertFalse(self.calls('codex plugin marketplace add'))
    def test_marketplace_dry_run_is_not_checked_and_invokes_no_hosts(self):
        self.claude_registry(['kit'])
        self.codex_registry([self.marketplace('kit-marketplace')])
        before = {p: p.read_bytes() for p in self.home.rglob('*.json')}
        self.log.write_text('')
        result = self.install('--only', 'claude,codex', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NOT_CHECKED', result.stdout)
        self.assertIn('codex plugin marketplace list --json', result.stdout)
        self.assertEqual(self.calls(), [])
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_missing_pi_bolt_installs_and_enables_package_then_refreshes(self):
        self.bolt.unlink()
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        original = {'packages': [{'source': NEW, 'skills': [], 'extensions': []},
                                 {'source': 'npm:other', 'skills': []}], 'model': 'keep-me'}
        settings.write_text(json.dumps(original))
        profile = self.home / '.profile'
        profile.write_text('# keep my profile\n')
        result = self.install('--no-pull', '--only', 'pi-bolt,pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi-bolt\s+installed')
        self.assertRegex(result.stdout, r'pi\s+installed')
        calls = self.calls()
        self.assertLess(next(i for i, c in enumerate(calls) if c.startswith('pi-bolt-installer')),
                        calls.index(f'pi-bolt install {NEW}'))
        self.assertEqual(self.calls('pi-bolt install'), [f'pi-bolt install {NEW}'])
        self.assertEqual(len(self.calls('curl')), 1)
        original['packages'][0] = NEW
        self.assertEqual(json.loads(settings.read_text()), original)
        self.log.write_text('')
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'refreshing {self.home / "pkg/kit"}', result.stdout)
        self.assertEqual(self.calls('pi-bolt '), ['pi-bolt --version', 'pi-bolt list',
                                              f'pi-bolt update {NEW}', 'pi-bolt list'])
        self.assertEqual(self.calls('curl'), [])
        self.assertEqual(json.loads(settings.read_text()), original)
        self.assertEqual(profile.read_text(), '# keep my profile\n')
        self.assertFalse(self.calls('systemctl --user try-restart'))

    def test_pi_requires_usable_destination_pi_bolt_without_download_or_path_fallback(self):
        self.fake('pi', LOGGING + 'exit 97\n')
        self.fake('pi-bolt', LOGGING + 'exit 98\n')
        for state in ('missing', 'nonexec', 'wrong-version', 'failed'):
            with self.subTest(state=state):
                self.fake_bolt(PI)
                if state == 'missing':
                    self.bolt.unlink()
                elif state == 'nonexec':
                    self.bolt.chmod(0o644)
                else:
                    self.fake_bolt('#!/bin/sh\necho wrong-tool\n' + ('exit 3\n' if state == 'failed' else ''))
                self.log.write_text('')
                result = self.install('--only', 'pi', '--quiet')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertRegex(result.stdout, r'pi\s+failed')
                self.assertIn('./install.sh --only pi-bolt,pi', result.stdout)
                self.assertIn(str(self.bolt), result.stdout)
                self.assertEqual(self.calls('curl'), [])
                self.assertEqual(self.calls('pi '), [])
                self.assertEqual(self.calls('pi-bolt '), [])
                self.assertFalse((self.home / '.pi/agent/settings.json').exists())
        result = self.install('--full', '--skip', 'pi-bolt')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi\s+failed')
        self.assertFalse(self.calls('curl'))

    def test_pi_package_uses_only_selected_destination_and_never_stock_pi(self):
        self.fake('pi', LOGGING + 'echo "stock Pi must not run" >&2; exit 97\n')
        self.fake('pi-bolt', LOGGING + 'echo "PATH Pi-Bolt must not run" >&2; exit 98\n')
        destination = self.home / 'custom bin'
        for args in ((), ('update',), ('--dry-run',)):
            result = self.install(*args, env={'KIT_BIN_DIR': str(destination)})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(str(destination / 'pi-bolt'), result.stdout)
            self.assertEqual(self.calls('pi '), [])
        self.assertEqual(self.calls('pi-bolt install'), [f'pi-bolt install {NEW}'])
        self.assertEqual(self.calls('pi-bolt update'), [f'pi-bolt update {NEW}'])

    def test_pi_destination_version_probe_is_bounded_and_actionable(self):
        with patch.object(install_menu.subprocess, 'run',
                          side_effect=subprocess.TimeoutExpired('/fake/pi-bolt', 30)) as run:
            with self.assertRaisesRegex(OSError, r'timed out.*--only pi-bolt,pi'):
                install_menu.install_pi_package(install_menu.Output(verbosity=0))
        self.assertEqual(run.call_args.args[0], [str(install_menu.BIN.absolute() / 'pi-bolt'), '--version'])
        self.assertEqual(run.call_args.kwargs['timeout'], 30)
        self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)

    def test_pi_command_timeouts_stop_descendants_and_bound_silent_or_busy_hosts(self):
        marker = self.home / 'orphan-write'
        for script in ('sleep 30', 'exec 1>&- 2>&-; sleep 30',
                       'while :; do printf busy; done',
                       f'(sleep 0.5; touch "{marker}") & wait'):
            with self.subTest(script=script):
                # The outer timeout guards this regression even if the inner bound breaks.
                probe = subprocess.run([sys.executable, '-c',
                    'import json, sys; sys.path.insert(0, sys.argv[1]); import install_menu; '
                    'print(json.dumps(install_menu.run_command(["sh", "-c", sys.argv[2]], '
                    'install_menu.Output(verbosity=0), timeout=0.1)))',
                    str(ROOT / 'scripts'), script], capture_output=True, text=True,
                    env=self.env, timeout=5)
                self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
                self.assertIn('124,', probe.stdout)
                self.assertIn('timed out after 0.1 seconds', probe.stdout)
        time.sleep(0.6)
        self.assertFalse(marker.exists(), 'timed-out installer left a running descendant')

    def test_pi_timeout_failure_names_stage_and_repair(self):
        output = install_menu.Output(verbosity=0)
        with patch.object(install_menu, 'pi_bolt_version', return_value='1.4.0'), \
             patch.object(install_menu, 'pi_package', return_value=None), \
             patch.object(install_menu, 'run_command', return_value=(124, 'command timed out')) as run:
            with self.assertRaisesRegex(OSError, r'package install failed.*timed out.*--only pi'):
                install_menu.install_pi_package(output)
            self.assertEqual(run.call_args.kwargs['timeout'], 600)

    def test_pi_package_failure_does_not_enable_or_claim_success(self):
        self.fake_bolt(PI.replace('  install|update)',
            '  install|update) echo "Git transport denied" >&2; exit 23 ;;\n  unused)'))
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': []}]}))
        before = settings.read_bytes()
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi\s+failed.*Git transport denied')
        self.assertIn('exit 23', result.stdout)
        self.assertIn('--only pi', result.stdout)
        self.assertEqual(settings.read_bytes(), before)
        self.assertNotIn('Open a new host session', result.stdout)

    def test_missing_pi_bolt_preview_skip_and_menu_do_not_execute_or_write(self):
        self.bolt.unlink()
        report = self.home / 'preview.jsonl'
        for args, stdin, env in (
            (('--no-pull', '--dry-run'), None, {'KIT_INSTALL_REPORT': str(report)}),
            (('--list',), None, {}),
            (('--only', 'pi', '--skip', 'pi'), None, {}),
            (('--menu', '--dry-run'), '\n', {'KIT_INSTALL_UI': 'text'}),
            (('--menu',), 'q\n', {'KIT_INSTALL_UI': 'text'}),
        ):
            with self.subTest(args=args):
                before = sorted(str(p) for p in self.home.rglob('*'))
                result = self.install(*args, stdin=stdin, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(sorted(str(p) for p in self.home.rglob('*')), before)
                self.assertEqual(self.calls(), [])
                self.assertNotIn('pi.dev', result.stdout)
                if '--dry-run' in args or '--list' in args:
                    self.assertLess(result.stdout.index('Pi-Bolt native'), result.stdout.index('Kit package for Pi'))
                if '--menu' in args:
                    self.assertIn('[x] 1 Pi-Bolt native', result.stdout)
                    self.assertIn('[x] 2 Kit package for Pi', result.stdout)
        self.assertNotIn('pi.dev', (ROOT / 'scripts/install_menu.py').read_text())

    def test_nested_hermes_refresh_skips_pi_package(self):
        result = self.install('--full', '--skip', 'hermes,pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi-bolt-installer'),
                         [f'pi-bolt-installer {self.bolt.parent}|1|no'])
        self.assertEqual(self.calls('pi-bolt install'), [])
        self.assertEqual(self.calls('pi-bolt update'), [])
        self.assertEqual(self.calls('pi-bolt list'), [])

    def recording_services(self):
        self.fake('systemctl', LOGGING + r'''
case "$*" in
  *list-units*)
    printf '%s\n' 'kit-bolt.service loaded active running Bolt' 'kit-other.service loaded active running Other' 'kit-stopped.service loaded inactive dead Stopped' 'orbi-kit@1.service loaded active running Paused' 'hermes-gateway.service loaded active running Hermes' ;;
  *show*kit-bolt.service*)
    printf 'ExecStart={ path=%s ; argv[]=%s ; }\n' "$FAKE_HOME/.local/bin/pi-bolt" "$FAKE_HOME/.local/bin/pi-bolt"
    printf 'Environment=PI_CODING_AGENT_DIR=%s/.pi/agent\n' "$FAKE_HOME" ;;
  *show*kit-other.service*) echo 'ExecStart={ path=/unrelated/bin/server ; argv[]=/unrelated/bin/server ; }' ;;
esac
''')

    def test_paired_entrypoints_check_every_time_restart_only_changed_consumer(self):
        self.recording_services()
        for command in ((), ('update',)):
            with self.subTest(command=command):
                self.log.write_text('')
                self.bolt.write_text(PI + '# previous release\n')
                first = self.install(*command, '--only', 'pi-bolt')
                second = self.install(*command, '--only', 'pi-bolt')
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                self.assertEqual(len(self.calls('pi-bolt-installer')), 2)
                self.assertEqual(self.calls('systemctl --user try-restart'),
                                 ['systemctl --user try-restart kit-bolt.service'])
                self.assertIn('unchanged', second.stdout)

    def test_tx_without_consumer_and_failed_or_preview_payloads_never_restart(self):
        self.recording_services()
        for args, env, code in ((('--only', 'tx'), {}, 0),
                                (('--only', 'pi-bolt'), {'PI_BOLT_FIXTURE_STAGE': 'install'}, 1),
                                (('--only', 'pi-bolt', '--dry-run'), {}, 0)):
            with self.subTest(args=args, env=env):
                result = self.install(*args, env=env)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_restart_failure_makes_install_fail(self):
        self.recording_services()
        original = (self.bin / 'systemctl').read_text()
        self.fake('systemctl', original + '\nif [[ "$*" == *try-restart* ]]; then exit 17; fi\n')
        self.bolt.write_text(PI + '# previous release\n')
        result = self.install('--only', 'pi-bolt')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('kit-bolt.service', result.stdout)

    def test_restart_timeout_does_not_drop_independent_changed_consumer(self):
        path = str(self.bolt)
        observation = {'pi-bolt': {'status': 'installed', 'change': 'changed',
                                  'changed_inputs': [path],
                                  'before': {'inputs': {path: 'old'}},
                                  'after': {'inputs': {path: 'new'}}}}
        listed = subprocess.CompletedProcess([], 0,
            'kit-first.service loaded active running First\n'
            'kit-next.service loaded active running Next\n', '')
        shown = subprocess.CompletedProcess([], 0, f'ExecStart={{ path={path} ; }}\n', '')
        with patch.object(install_menu.platform, 'system', return_value='Linux'), \
                patch.object(install_menu.shutil, 'which', return_value='/bin/systemctl'), \
                patch.object(install_menu.subprocess, 'run', side_effect=[listed, shown, shown]), \
                patch.object(install_menu, 'run_command', side_effect=[
                    subprocess.TimeoutExpired(['systemctl'], 30), (0, '')]) as run:
            with self.assertRaisesRegex(RuntimeError, 'kit-first.service'):
                install_menu.restart_services(install_menu.Output(verbosity=0), observation)
        self.assertEqual([call.args[0][-1] for call in run.call_args_list],
                         ['kit-first.service', 'kit-next.service'])
        with patch.object(install_menu.platform, 'system', return_value='Linux'), \
                patch.object(install_menu.shutil, 'which', return_value='/bin/systemctl'), \
                patch.object(install_menu.subprocess, 'run', side_effect=[
                    listed, subprocess.TimeoutExpired(['systemctl'], 30), shown]), \
                patch.object(install_menu, 'run_command', return_value=(0, '')) as run:
            decision = install_menu.restart_services(install_menu.Output(verbosity=0), observation)
        self.assertIn('kit-first.service: held', decision)
        self.assertIn('inspect systemctl --user show kit-first.service', decision)
        self.assertIn('kit-next.service: restarted', decision)
        self.assertEqual([call.args[0][-1] for call in run.call_args_list], ['kit-next.service'])

    def test_same_version_package_and_settings_repairs_restart_once_then_skip(self):
        self.recording_services()
        package = self.installed_package()
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': []}]}))
        report = self.home / 'report.jsonl'
        for command in ((), ('update',)):
            with self.subTest(command=command):
                (package / 'adapters/skills/update-kit/SKILL.md').write_text('damaged same-version skill')
                self.log.write_text('')
                first = self.install(*command, '--only', 'pi', env={'KIT_INSTALL_REPORT': str(report)})
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
                self.assertEqual(rows['pi']['change'], 'changed')
                self.assertNotEqual(rows['pi']['evidence']['before']['inputs'][str(package)],
                                    rows['pi']['evidence']['after']['inputs'][str(package)])
                settings.write_text(json.dumps(json.loads(settings.read_text()), indent=4))
                second = self.install(*command, '--only', 'pi', env={'KIT_INSTALL_REPORT': str(report)})
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                self.assertEqual(len(self.calls('pi-bolt update')), 2)
                rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
                self.assertEqual(rows['pi']['change'], 'unchanged')
                self.assertEqual(self.calls('systemctl --user try-restart'),
                                 ['systemctl --user try-restart kit-bolt.service'])

    def test_failed_payload_holds_shared_consumer_but_not_independent_success(self):
        self.recording_services()
        self.installed_package()
        self.bolt.write_text(PI + '# previous release\n')
        failed = self.install('--only', 'pi-bolt,pi', env={'FAKE_PI_UPDATE_FAIL': '1'})
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])
        self.assertIn('kit-bolt.service: held (incomplete/unverified pi)', failed.stdout)
        self.bolt.write_text(PI + '# previous release\n')
        self.claude_host(mutation='exit 23')
        independent = self.install('--only', 'pi-bolt,claude')
        self.assertEqual(independent.returncode, 1, independent.stdout + independent.stderr)
        self.assertEqual(self.calls('systemctl --user try-restart'),
                         ['systemctl --user try-restart kit-bolt.service'])

    def test_failed_pi_package_does_not_hold_a_proven_different_profile(self):
        self.recording_services()
        self.installed_package()
        body = (self.bin / 'systemctl').read_text().replace(
            'PI_CODING_AGENT_DIR=%s/.pi/agent', 'PI_CODING_AGENT_DIR=%s/other-profile')
        self.fake('systemctl', body)
        self.bolt.write_text(PI + '# previous release\n')
        result = self.install('--only', 'pi-bolt,pi', env={'FAKE_PI_UPDATE_FAIL': '1'})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.calls('systemctl --user try-restart'),
                         ['systemctl --user try-restart kit-bolt.service'])

    def test_unknown_pi_profile_holds_even_with_a_changed_executable(self):
        self.recording_services()
        package = self.installed_package()
        original = (self.bin / 'systemctl').read_text()
        for replacement in ('', 'OTHER_PI_CODING_AGENT_DIR'):
            with self.subTest(environment=replacement):
                self.log.write_text('')
                body = original.replace('PI_CODING_AGENT_DIR', replacement) if replacement else original.replace(
                    "    printf 'Environment=PI_CODING_AGENT_DIR=%s/.pi/agent\\n' \"$FAKE_HOME\"", ':')
                self.fake('systemctl', body)
                (package / 'adapters/skills/update-kit/SKILL.md').write_text('damaged package')
                self.bolt.write_text(PI + '# previous release\n')
                result = self.install('--only', 'pi-bolt,pi')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.calls('systemctl --user try-restart'), [])
                self.assertIn('kit-bolt.service: held (unverified Pi profile', result.stdout)

    def test_unverified_service_references_hold_with_manual_action(self):
        self.fake('systemctl', LOGGING + r'''
if [[ "$*" == *list-units* ]]; then echo 'kit-unknown.service loaded active running Unknown'; fi
''')
        self.bolt.write_text(PI + '# previous release\n')
        result = self.install('--only', 'pi-bolt')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('kit-unknown.service: held (unverified executable/config references for pi-bolt)', result.stdout)
        self.assertIn('inspect systemctl --user show kit-unknown.service', result.stdout)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_symlink_target_repair_is_change_even_when_version_and_bytes_match(self):
        self.recording_services()
        old = self.home / 'old-bolt'
        old.write_text(PI)
        old.chmod(0o755)
        self.bolt.unlink()
        self.bolt.symlink_to(old)
        self.upstream.write_text(self.upstream.read_text().replace(
            'cp "$FAKE_HOME', 'rm -f "$PIBOLT_BIN_DIR/pi-bolt"\ncp "$FAKE_HOME'))
        result = self.install('--only', 'pi-bolt')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.bolt.is_symlink())
        self.assertEqual(self.calls('systemctl --user try-restart'),
                         ['systemctl --user try-restart kit-bolt.service'])

    def test_outer_and_real_nested_installer_preserve_native_gateway_decisions(self):
        self.recording_services()
        source = self.home / 'nested-source'
        (source / 'scripts').mkdir(parents=True)
        shutil.copy2(INSTALL, source / 'install.sh')
        shutil.copy2(ROOT / 'scripts/install_menu.py', source / 'scripts/install_menu.py')
        shutil.copytree(ROOT / 'tmux', source / 'tmux')
        clone = self.home / '.hermes/plugins/kit'
        (clone / '.git').mkdir(parents=True)
        self.fake('hermes', LOGGING)
        (source / 'scripts/update_bundle.py').write_text(f'''
from pathlib import Path
import importlib.util, json, os

def plugin_dir(home): return home / 'plugins/kit'
if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('native_fixture', {str(ROOT / 'scripts/update_bundle.py')!r})
    updater = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(updater)
    if os.environ.get('NATIVE_HOST_FAIL'): os.environ['PI_BOLT_FIXTURE_STAGE'] = 'install'
    if os.environ.get('NATIVE_PAYLOAD'): Path(os.environ['NATIVE_PAYLOAD']).write_text('native-current')
    print(json.dumps({{'status': 'updated', 'gateway_restart': os.environ['NATIVE_DISPOSITION'],
                       'hosts': updater.refresh_hosts(Path(__file__).resolve().parents[1])}}))
''')
        report = self.home / 'report.jsonl'
        for command in ((), ('update',)):
            for disposition in ('deferred', 'pending', 'not_needed'):
                with self.subTest(command=command, disposition=disposition):
                    self.log.write_text('')
                    self.bolt.write_text(PI + '# previous release\n')
                    env = {**self.env, 'KIT_INSTALL_REPORT': str(report), 'NATIVE_DISPOSITION': disposition}
                    for _ in range(2):
                        result = subprocess.run(['bash', str(source / 'install.sh'), *command,
                                                 '--only', 'pi-bolt,hermes'], env=env,
                                                capture_output=True, text=True, timeout=30, cwd=self.project)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
                        self.assertEqual(rows['hermes']['gateway_restart'], disposition)
                        nested = {r['item']: r for r in rows['hermes']['hosts']}
                        self.assertIn('evidence', nested['pi-bolt'])
                        self.assertIn('delegated to outer installer', nested['services']['decision'])
                    self.assertEqual(len(self.calls('pi-bolt-installer')), 4)
                    self.assertEqual(self.calls('systemctl --user try-restart'),
                                     ['systemctl --user try-restart kit-bolt.service'])
        self.log.write_text('')
        self.bolt.write_text(PI + '# previous release\n')
        env['NATIVE_HOST_FAIL'] = '1'
        failed = subprocess.run(['bash', str(source / 'install.sh'), '--only', 'pi-bolt,hermes'],
                                env=env, capture_output=True, text=True, timeout=30, cwd=self.project)
        self.assertEqual(failed.returncode, 0, failed.stdout + failed.stderr)  # native host refresh remains best effort
        self.assertIn('kit-bolt.service: held (incomplete/unverified pi-bolt)', failed.stdout)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])
        # Native apply may change a source-linked host before refresh_hosts takes
        # its own baseline. This must work even when only Hermes is selected.
        payload = self.home / 'native-payload'
        payload.mkdir()
        skill = payload / 'SKILL.md'
        registration = {**self.marketplace('kit-marketplace'), 'root': str(payload)}
        self.codex_registry([registration], {'kit-marketplace': {'available': [], 'installed': [{
            'pluginId': 'kit@kit-marketplace', 'name': 'kit', 'marketplaceName': 'kit-marketplace',
            'installed': True, 'enabled': True, 'source': {'source': 'local', 'path': str(payload)},
            'marketplaceSource': registration['marketplaceSource']}]}})
        self.fake('systemctl', LOGGING + f'''
if [[ "$*" == *list-units* ]]; then echo 'kit-codex.service loaded active running Codex';
elif [[ "$*" == *show* ]]; then echo 'ExecStart={{ path=/usr/bin/codex ; argv[]=/usr/bin/codex --plugin {payload}/SKILL.md ; }}'; fi
''')
        env.pop('NATIVE_HOST_FAIL')
        env['NATIVE_PAYLOAD'] = str(skill)
        for command in ((), ('update',)):
            with self.subTest(native_source_change=command):
                self.log.write_text('')
                skill.write_text('previous-native-payload')
                for _ in range(2):
                    updated = subprocess.run(['bash', str(source / 'install.sh'), *command,
                                              '--no-pull', '--only', 'hermes'], env=env,
                                             capture_output=True, text=True, timeout=30, cwd=self.project)
                    self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
                self.assertEqual(skill.read_text(), 'native-current')
                self.assertEqual(self.calls('systemctl --user try-restart'),
                                 ['systemctl --user try-restart kit-codex.service'])

    def test_nested_missing_evidence_holds_an_earlier_changed_consumer(self):
        self.recording_services()
        before = (PI + '# old release\n').encode()
        bolt = install_menu.Item('pi-bolt', 'Bolt', inputs=lambda:
            install_menu.installed_evidence([self.bolt]), steps=[install_menu.Step(
                'refresh', run=lambda: (self.bolt.write_text(PI) and 'refreshed'))])
        hermes = install_menu.Item('hermes', 'Hermes', steps=[install_menu.Step('native', ['native'])])
        for state in ('failed', 'timeout', 'unavailable', 'installed'):
            with self.subTest(state=state):
                self.bolt.write_bytes(before)
                self.log.write_text('')
                receipt = {'status': 'updated', 'gateway_restart': 'deferred',
                           'hosts': [{'item': 'pi-bolt', 'status': state, 'exit': 1}]}
                original = install_menu.run_command
                def native(argv, output, **kwargs):
                    if argv == ['native']:
                        return 0, json.dumps(receipt)
                    return original(argv, output, **kwargs)
                with patch.object(install_menu, 'BIN', self.bolt.parent), \
                        patch.object(install_menu, 'run_command', side_effect=native), \
                        patch.dict(os.environ, self.env), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(install_menu.install([bolt, hermes], {'pi-bolt', 'hermes'}), 0)
                self.assertEqual(self.calls('systemctl --user try-restart'), [])
                self.assertIn('kit-bolt.service: held (incomplete/unverified pi-bolt)', out.getvalue())
                self.assertIn('repair those inputs before manual restart', out.getvalue())

    def test_large_native_receipt_keeps_gateway_and_nested_evidence(self):
        report = self.home / 'large-native-report.jsonl'
        evidence = install_menu.installed_evidence([self.bolt])
        receipt = {'status': 'updated', 'gateway_restart': 'pending',
                   'activation': [{'status': 'ready', 'commands': ['command'] * 5000}],
                   'hosts': [{'item': 'pi-bolt', 'status': 'installed', 'exit': 0,
                              'evidence': {'before': evidence, 'after': evidence}}]}
        item = install_menu.Item('hermes', 'Hermes', steps=[install_menu.Step('native',
            [sys.executable, '-c', 'import json; print(json.dumps(' + repr(receipt) + '))'])])
        original = install_menu.run_command
        def bounded(argv, output, **kwargs):
            kwargs['timeout'] = 5
            return original(argv, output, **kwargs)
        with patch.dict(os.environ, {'KIT_INSTALL_REPORT': str(report)}), \
                patch.object(install_menu, 'run_command', side_effect=bounded), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_menu.install([item], {'hermes'}), 0)
        row = next(r for r in map(json.loads, report.read_text().splitlines()) if r['item'] == 'hermes')
        self.assertEqual(row['gateway_restart'], 'pending')
        self.assertEqual(row['activation'], receipt['activation'])
        self.assertEqual(row['hosts'], receipt['hosts'])

    def test_marketplace_payload_repairs_at_same_identity_restart_only_own_consumer(self):
        for host, command in (('claude', ()), ('codex', ('update',))):
            with self.subTest(host=host):
                self.log.write_text('')
                payload = self.home / ('payload-' + host)
                payload.mkdir()
                skill = payload / 'SKILL.md'
                skill.write_text('stale')
                self.fake('systemctl', LOGGING + f'''
if [[ "$*" == *list-units* ]]; then
  echo 'kit-{host}.service loaded active running Host'
  echo 'kit-unrelated.service loaded active running Other'
elif [[ "$*" == *show*kit-{host}.service* ]]; then
  echo 'ExecStart={{ path=/usr/bin/host ; argv[]=/usr/bin/host --plugin {payload} ; }}'
elif [[ "$*" == *show* ]]; then echo 'ExecStart={{ path=/unrelated ; }}'; fi
''')
                mutation = f'printf current > {shlex.quote(str(skill))}'
                if host == 'claude':
                    self.claude_registry(['kit'])
                    self.claude_host([{'id': 'kit@kit', 'scope': 'user', 'enabled': True,
                                       'version': 'same', 'installPath': str(payload)}], mutation=mutation)
                else:
                    registration = {**self.marketplace('kit-marketplace'), 'root': str(payload)}
                    self.codex_registry([registration], {'kit-marketplace': {'available': [], 'installed': [{
                        'pluginId': 'kit@kit-marketplace', 'name': 'kit', 'marketplaceName': 'kit-marketplace',
                        'installed': True, 'enabled': True, 'source': {'source': 'local', 'path': str(payload)},
                        'marketplaceSource': registration['marketplaceSource']}]}}, mutation=mutation)
                first = self.install(*command, '--only', host)
                second = self.install(*command, '--only', host)
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                self.assertEqual(skill.read_text(), 'current')
                self.assertIn('unchanged', second.stdout)
                freshness = ('claude plugin marketplace update' if host == 'claude'
                             else 'codex plugin marketplace upgrade')
                self.assertEqual(len(self.calls(freshness)), 2)
                self.assertEqual(self.calls('systemctl --user try-restart'),
                                 [f'systemctl --user try-restart kit-{host}.service'])

    def test_missing_installed_payload_is_unverified_not_unchanged(self):
        self.recording_services()
        self.claude_registry(['kit'])
        self.claude_host([{'id': 'kit@kit', 'scope': 'user', 'enabled': True, 'version': 'same',
                           'installPath': str(self.home / 'unavailable-payload')}])
        report = self.home / 'report.jsonl'
        result = self.install('--only', 'claude', env={'KIT_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = next(r for r in map(json.loads, report.read_text().splitlines()) if r['item'] == 'claude')
        self.assertEqual(row['change'], 'unverified')
        self.assertIn(str(self.home / 'unavailable-payload'), result.stdout)
        self.assertIn('Inspect named inputs', result.stdout)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_partial_marketplace_removal_blocks_shared_changed_consumer(self):
        self.recording_services()
        self.claude_registry(['kit'])
        payload = self.home / 'claude-payload'
        payload.mkdir()
        (payload / 'SKILL.md').write_text('installed')
        self.claude_host([{'id': 'kit@kit', 'scope': 'user', 'enabled': True,
                           'version': 'same', 'installPath': str(payload)}], mutation=f'''
printf '[]' > "$FAKE_HOME/claude-installed.json"
rm -r {shlex.quote(str(payload))}
exit 23
''')
        body = (self.bin / 'systemctl').read_text().replace(
            'argv[]=%s ; }', f'argv[]=%s --plugin {payload}/SKILL.md ; }}')
        self.fake('systemctl', body)
        self.bolt.write_text(PI + '# previous release\n')
        result = self.install('--only', 'pi-bolt,claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('kit-bolt.service: held (incomplete/unverified claude)', result.stdout)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_unverified_pi_profile_does_not_infer_package_consumer_from_executable(self):
        self.recording_services()
        self.installed_package()
        body = (self.bin / 'systemctl').read_text().replace(
            "    printf 'Environment=PI_CODING_AGENT_DIR=%s/.pi/agent\\n' \"$FAKE_HOME\"", ':')
        self.fake('systemctl', body)
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('kit-bolt.service: held (unverified Pi profile', result.stdout)
        self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_every_host_includes_bundled_ponytail_without_a_second_plugin(self):
        self.fake('hermes', LOGGING)
        result = self.install('--only', 'pi,claude,codex,hermes', '--dry-run',
                              '--hermes-home', str(self.home))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('bundled Ponytail'), 4)
        self.assertNotIn('DietrichGebert/ponytail', result.stdout)
        self.assertFalse(self.calls('pi-bolt install'))
        self.assertFalse(self.calls('claude plugin install'))
        self.assertFalse(self.calls('codex plugin add'))

    def test_list_marks_missing_hosts(self):
        out = self.install('--list').stdout
        for key in ('pi', 'pi-bolt', 'tx', 'claude', 'codex'):
            self.assertRegex(out, rf'{key}\s+available')
        self.assertRegex(out, r'hermes\s+unavailable.*hermes not found')

    def test_full_skips_a_stale_optional_host_launcher(self):
        self.fake('hermes', f'#!/bin/sh\nexec {self.home}/missing-hermes "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--full')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+skipped.*launcher target')
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))
        self.assertRegex(self.install('--list').stdout, r'hermes\s+unavailable.*launcher target')

    def test_an_explicit_stale_host_fails_without_stopping_other_components(self):
        self.fake('hermes', f'#!/bin/sh\nexec {self.home}/missing-hermes "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--only', 'hermes,tx')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+failed.*launcher target')
        self.assertTrue((self.home / '.local/bin/tx').is_file())

    def test_dynamic_shell_targets_are_left_to_native_host_admission(self):
        self.fake('hermes', '#!/bin/sh\nexec "/bin/${KIT_HOST:-sh}" "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+planned')

    def test_a_working_shell_wrapper_is_available_without_executing_it(self):
        target = self.home / 'real hermes'
        marker = self.home / 'executed'
        target.write_text(f'#!/bin/sh\ntouch {marker}\n')
        target.chmod(0o755)
        self.fake('hermes', f'#!/bin/sh\nexec "{target}" "$@"\n')
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+planned')
        self.assertFalse(marker.exists())

    def test_orbi_installs_cli_only_and_verifies_version(self):
        result = self.install('--only', 'orbi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('uv'), [f'uv tool install --python 3.14 {ORBI_SOURCE}'])
        self.assertEqual(self.calls('orbi'), ['orbi --version'])
        self.assertTrue((self.home / '.local/bin/orbi').is_file())
        self.assertIn('orbi 0.7.41', result.stdout)
        self.assertFalse(any('orbi-' in call for call in self.calls('systemctl')))
        self.assertFalse((self.home / 'orbi.toml').exists())

    def test_orbi_full_update_and_selection(self):
        for args in (('--dry-run',), ('update', '--dry-run'), ('--only', 'orbi', '--dry-run')):
            with self.subTest(args=args):
                result = self.install(*args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertRegex(result.stdout, r'orbi\s+planned')
                self.assertIn(f'uv tool install --python 3.14 {ORBI_SOURCE}', result.stdout)
        self.assertRegex(self.install('--list').stdout, r'orbi\s+available')
        self.assertEqual(self.calls('orbi'), [])
        self.assertEqual(self.calls('uv'), [])
        self.assertEqual(self.calls('systemctl'), [])
        result = self.install('--skip', 'orbi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('uv'), [])
        self.assertEqual(self.calls('orbi'), [])

    def test_orbi_missing_git_refuses_fork_install_without_side_effects(self):
        with patch.object(install_menu, 'HOME', self.home), \
                patch.object(install_menu, 'BIN', self.home / '.local/bin'), \
                patch.object(install_menu.shutil, 'which',
                             side_effect=lambda name: str(self.bin / 'uv') if name == 'uv' else None), \
                patch.object(install_menu, 'run_command') as run:
            with self.assertRaisesRegex(OSError, 'requires git'):
                install_menu.install_orbi()
        run.assert_not_called()
        self.assertFalse((self.home / '.local/bin/orbi').exists())

    def test_orbi_preserves_existing_cli_even_on_update(self):
        self.fake('orbi', LOGGING + 'echo orbi 0.7.41\n')
        before = (self.bin / 'orbi').read_bytes()
        for args in (('--only', 'orbi'), ('update', '--only', 'orbi')):
            result = self.install(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('kept', result.stdout)
        self.assertEqual((self.bin / 'orbi').read_bytes(), before)
        self.assertEqual(self.calls('uv'), [])
        self.assertEqual(self.calls('orbi'), ['orbi --version', 'orbi --version'])

    def test_orbi_reuses_user_local_cli_off_path_without_uv(self):
        self.assertEqual(self.install('--only', 'orbi').returncode, 0)
        (self.bin / 'uv').unlink()
        self.log.write_text('')
        result = self.install('--only', 'orbi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('uv'), [])
        self.assertEqual(self.calls('orbi'), ['orbi --version'])

    def test_orbi_verification_failure_after_install_is_reported(self):
        self.fake('uv', LOGGING + '''
mkdir -p "$UV_TOOL_BIN_DIR"
printf '#!/bin/sh\\necho invalid-version\\n' > "$UV_TOOL_BIN_DIR/orbi"
chmod 755 "$UV_TOOL_BIN_DIR/orbi"
''')
        result = self.install('--only', 'orbi')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('version verification failed', result.stdout)
        self.assertTrue((self.home / '.local/bin/orbi').is_file())

    def test_orbi_version_probe_is_bounded_and_unsupported_hosts_fail_closed(self):
        with patch.object(install_menu.subprocess, 'run',
                          side_effect=subprocess.TimeoutExpired('orbi', 30)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                install_menu.orbi_version('/fake/orbi')
        self.assertEqual(run.call_args.args[0], ['/fake/orbi', '--version'])
        self.assertEqual(run.call_args.kwargs['timeout'], 30)
        with patch.object(install_menu.platform, 'system', return_value='Windows'):
            item = install_menu.orbi_item()
        self.assertFalse(item.available)
        self.assertIn('unsupported Orbi platform', item.missing)

    def test_orbi_failures_do_not_force_reinstall_or_stop_other_items(self):
        for body in ('exit 4\n', 'echo wrong-tool\n'):
            with self.subTest(body=body):
                self.fake('orbi', LOGGING + body)
                result = self.install('--only', 'orbi,tx')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertRegex(result.stdout, r'orbi\s+failed')
                self.assertRegex(result.stdout, r'tx\s+installed')
                self.assertEqual(self.calls('uv'), [])
        (self.bin / 'orbi').unlink()
        result = self.install('--only', 'orbi', env={'ORBI_INSTALL_FAIL': '1'})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('17', result.stdout)
        self.assertFalse((self.home / '.local/bin/orbi').exists())
        (self.bin / 'uv').unlink()
        result = self.install('--only', 'orbi')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('requires uv', result.stdout)

    def test_orbi_preserves_dangling_launcher_and_respects_tool_bin_dir(self):
        destination = self.home / 'custom bin'
        destination.mkdir()
        launcher = destination / 'orbi'
        launcher.symlink_to(destination / 'missing')
        result = self.install('--only', 'orbi', env={'UV_TOOL_BIN_DIR': str(destination)})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(launcher.is_symlink())
        self.assertEqual(self.calls('uv'), [])
        launcher.unlink()
        result = self.install('--only', 'orbi', env={'UV_TOOL_BIN_DIR': str(destination)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(launcher.is_file())
        self.assertFalse((self.home / '.local/bin/orbi').exists())

    def assert_pi_bolt_stub(self):
        binary = self.home / '.local/bin/pi-bolt'
        self.assertTrue(binary.is_file())
        self.assertEqual(self.calls('pi-bolt-installer'),
                         [f'pi-bolt-installer {binary.parent}|1|no'])

    def test_pi_bolt_bootstraps_through_the_official_installer(self):
        self.bolt.unlink()
        result = self.install('--only', 'pi-bolt')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi-bolt\s+installed.*1\.4\.0')
        self.assert_pi_bolt_stub()
        curl = self.calls('curl')
        self.assertEqual(len(curl), 1)
        for flags in ('--proto =https', '--proto-redir =https', '--tlsv1.2',
                      '--connect-timeout 15', '--max-time 300', '--max-filesize 1048576'):
            self.assertIn(flags, curl[0])
        self.assertTrue(curl[0].endswith('https://pi-bolt.opensec.in/install.sh'))
        self.assertFalse(list(self.home.glob('kit-pi-bolt-*')))
        self.assertFalse((self.home / '.profile').exists())

    def native_bolt(self, version='1.4.0', variant='x64', root=None, system='linux'):
        """Layout/banner from upstream build-pi.sh and version-fast-path.ts."""
        root = root or self.home / '.pi-bolt'
        build = root / f'pi-bolt-{system}-{variant}'
        build.mkdir(parents=True, exist_ok=True)
        native_platform = f'{system}-{"arm64" if variant.startswith("arm64") else "x64"}'
        helper = 'darwin-platform.node' if system == 'darwin' else 'linux-platform-x11.node'
        banner = f'0.67.1 (Pi-Bolt {version}, {system}-{variant}, JIT {"on" if variant.endswith("-jit") else "off"})'
        payload = PI.replace('echo 1.4.0', f'echo "{banner}"')
        (build / 'pi').write_text(payload)
        (build / 'pi').chmod(0o755)
        (build / 'pi-bolt.txt').write_text(f'Pi-Bolt {version} (Pi 0.67.1), {system}-{variant}, JIT {"on" if variant.endswith("-jit") else "off"}, built 2026-11-24\n')
        (build / 'package.json').write_text('{"version": "0.67.1"}')
        for name in ('README.md', 'photon_rs_bg.wasm', 'export-html/template.html',
                     'export-html/template.css', 'export-html/template.js',
                     'export-html/vendor/highlight.min.js', 'export-html/vendor/marked.min.js',
                     'export-html/vendor/marked-cjk-friendly.min.js',
                     'theme/dark.json', 'assets/logo.txt', 'docs/PLUGINS.md',
                     'examples/example.ts', f'native/{system}/prebuilds/{native_platform}/{helper}'):
            file = build / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('fixture')
        if system == 'darwin':
            for name in ('pi-bin', 'pi-spawn'):
                (build / name).write_text('#!/bin/sh\nexit 0\n')
                (build / name).chmod(0o755)
        self.bolt.unlink(missing_ok=True)
        self.bolt.symlink_to(build / 'pi')
        return build

    def test_pi_bolt_skips_current_build_on_install_and_update(self):
        build = self.native_bolt()
        self.recording_services()
        before = install_menu.installed_evidence([self.bolt])
        stats = [(path, path.lstat()) for path in (self.bolt, build, *build.rglob('*'))]
        for command in ((), ('update',)):
            self.log.write_text('')
            result = self.install(*command, '--only', 'pi-bolt', env={'PIBOLT_VARIANT': 'x64', 'PIBOLT_SOURCE': ''})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r'pi-bolt[^\n]*0\.67\.1 \(Pi-Bolt 1\.4\.0, linux-x64, JIT off\); current')
            self.assertEqual(install_menu.installed_evidence([self.bolt]), before)
            self.assertEqual(self.bolt.resolve(), build / 'pi')
            for path, previous in stats:
                observed = path.lstat()
                self.assertEqual((observed.st_ino, observed.st_mtime_ns),
                                 (previous.st_ino, previous.st_mtime_ns), str(path))
            self.assertEqual(len(self.calls('curl')), 1)
            self.assertTrue(self.calls('curl')[0].endswith('/releases/latest'))
            self.assertEqual(self.calls('pi-bolt-installer'), [])
            self.assertEqual(self.calls('systemctl --user try-restart'), [])
            self.assertFalse(any('install.sh' in c for c in self.calls('curl')))

    def test_pi_bolt_default_platform_and_libc_selection(self):
        read_text = Path.read_text
        def cpuinfo(path, *args, **kwargs):
            if str(path) != '/proc/cpuinfo':
                return read_text(path, *args, **kwargs)
            if cpu_flags is None:
                raise FileNotFoundError(path)
            return f'flags: {cpu_flags}'
        # Upstream defaults: AVX2, baseline on missing CPU flags, musl, ARM64 and Apple silicon.
        for system, machine, variant, libc, cpu_flags in (
                ('Linux', 'x86_64', 'x64', 'glibc', 'avx2'),
                ('Linux', 'x86_64', 'x64-baseline', None, None),
                ('Linux', 'x86_64', 'x64-musl', 'musl', 'avx2'),
                ('Linux', 'aarch64', 'arm64', 'glibc', None),
                ('Darwin', 'arm64', 'arm64', '', None)):
            with self.subTest(system=system, variant=variant):
                build = self.native_bolt(variant=variant, system=system.lower())
                real_run = subprocess.run
                def run(argv, **kwargs):
                    if argv == ['ldd', '--version']:
                        if libc is None:
                            raise FileNotFoundError('ldd')
                        return SimpleNamespace(stdout=libc, stderr='', returncode=0)
                    return real_run(argv, **kwargs)
                with patch.dict(os.environ, {'PIBOLT_INSTALL': str(build.parent)}), \
                     patch.object(install_menu.platform, 'system', return_value=system), \
                     patch.object(install_menu.platform, 'machine', return_value=machine), \
                     patch.object(install_menu.subprocess, 'run', side_effect=run), \
                     patch.object(Path, 'read_text', cpuinfo):
                    self.assertIn('Pi-Bolt 1.4.0', install_menu.pi_bolt_current(self.bolt.parent, '1.4.0'))
                    if system == 'Darwin':
                        (build / 'pi-spawn').chmod(0o644)
                        self.assertIsNone(install_menu.pi_bolt_current(self.bolt.parent, '1.4.0'))

    def test_pi_bolt_repairs_selected_build_once_then_skips(self):
        self.recording_services()
        self.upstream.write_text(self.upstream.read_text().replace(
            'cp "$FAKE_HOME/pi-bolt-fixture" "$PIBOLT_BIN_DIR/pi-bolt"',
            '''root=${PIBOLT_INSTALL:-$HOME/.pi-bolt}
mkdir -p "$root"
rm -rf "$root/pi-bolt-linux-x64"
cp -R "$FAKE_HOME/release-build" "$root/pi-bolt-linux-x64"
rm -f "$PIBOLT_BIN_DIR/pi-bolt" "$root/channel"
ln -s "$root/pi-bolt-linux-x64/pi" "$PIBOLT_BIN_DIR/pi-bolt"'''))
        for state in ('absent', 'stale', 'broken-link', 'wrong-link', 'wrong-platform',
                      'wrong-variant', 'wrong-root', 'aliased-build', 'missing-assets', 'missing-export-js',
                      'wrong-native', 'empty-native', 'bad-manifest', 'compiled', 'channel', 'invalid-channel-file'):
            with self.subTest(state=state):
                build = self.native_bolt()
                release_build = self.home / 'release-build'
                shutil.rmtree(release_build, ignore_errors=True)
                shutil.copytree(build, release_build)
                env = {'PIBOLT_VARIANT': 'x64', 'PIBOLT_CHANNEL': 'stable'}
                if state == 'absent':
                    self.bolt.unlink()
                elif state in ('broken-link', 'wrong-link'):
                    self.bolt.unlink()
                    self.bolt.symlink_to(self.home / 'missing' if state == 'broken-link' else release_build / 'pi')
                elif state == 'stale':
                    (build / 'pi').write_text((build / 'pi').read_text().replace('Pi-Bolt 1.4.0', 'Pi-Bolt 1.3.0'))
                elif state == 'wrong-platform':
                    (build / 'pi').write_text((build / 'pi').read_text().replace('linux-x64', 'darwin-arm64'))
                elif state == 'wrong-variant':
                    (build / 'pi').write_text((build / 'pi').read_text().replace('linux-x64', 'linux-x64-baseline'))
                elif state == 'wrong-root':
                    env['PIBOLT_INSTALL'] = str(self.home / 'selected root')
                elif state == 'aliased-build':
                    shutil.rmtree(build)
                    build.symlink_to(release_build, target_is_directory=True)
                elif state == 'missing-assets':
                    (build / 'export-html/template.html').unlink()
                elif state == 'missing-export-js':
                    # --version still works; Pi-Bolt's HTML export cannot read its template script.
                    (build / 'export-html/template.js').unlink()
                elif state == 'wrong-native':
                    native = build / 'native/linux/prebuilds/linux-x64'
                    native.rename(native.with_name('linux-arm64'))
                elif state == 'empty-native':
                    (build / 'native/linux/prebuilds/linux-x64/linux-platform-x11.node').write_bytes(b'')
                elif state == 'bad-manifest':
                    (build / 'pi-bolt.txt').write_text('Pi-Bolt 9.9.9 (Pi 0.67.1), linux-x64, JIT off, built today')
                elif state == 'compiled':
                    with (build / 'pi-bolt.txt').open('a') as manifest:
                        manifest.write('Extensions compiled in (pi-bolt compile, 2026-11-24): sample\n')
                elif state == 'channel':
                    (build.parent / 'channel').write_text('beta\n')
                elif state == 'invalid-channel-file':
                    os.mkfifo(build.parent / 'channel')
                self.log.write_text('')
                repaired = self.install('--only', 'pi-bolt', env=env)
                self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
                self.assertEqual(len(self.calls('pi-bolt-installer')), 1)
                self.assertTrue(self.calls('pi-bolt-installer')[0].endswith('|1|no'))
                selected = Path(env.get('PIBOLT_INSTALL', build.parent)) / build.name / 'pi'
                self.assertEqual(self.bolt.resolve(), selected)
                self.assertIn('Pi-Bolt 1.4.0', repaired.stdout)
                self.log.write_text('')
                current = self.install('update', '--only', 'pi-bolt', env=env)
                self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
                self.assertIn('current (release checked', current.stdout)
                self.assertEqual(self.calls('pi-bolt-installer'), [])
                self.assertFalse(any('install.sh' in call for call in self.calls('curl')))
                self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_pi_bolt_release_failure_preserves_existing_installation(self):
        self.native_bolt()
        before = install_menu.installed_evidence([self.bolt])
        for metadata, env in ((None, {'FAKE_RELEASE_FAIL': '1'}), ('{', {}), ('[]', {}),
                              ('{}', {}), ('{"tag_name": "nope", "draft": false, "prerelease": false}', {}),
                              (' ' * 1048577, {}), ('[' * 1100 + ']' * 1100, {})):
            for command in ((), ('update',)):
                with self.subTest(metadata=str(metadata)[:30], command=command):
                    if metadata is not None:
                        (self.home / 'release.json').write_text(metadata)
                    self.log.write_text('')
                    result = self.install(*command, '--only', 'pi-bolt', env=env)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn('Pi-Bolt release check failed', result.stdout)
                    self.assertIn('retry ./install.sh --only pi-bolt', result.stdout)
                    self.assertNotIn('current (release checked', result.stdout)
                    self.assertNotIn('contents unchanged', result.stdout)
                    self.assertEqual(install_menu.installed_evidence([self.bolt]), before)
                    self.assertEqual(self.calls('pi-bolt-installer'), [])
                    self.assertFalse(any('install.sh' in call for call in self.calls('curl')))
                    self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_pi_bolt_preserves_stored_channel_without_override(self):
        build = self.native_bolt()
        (build.parent / 'channel').write_text('beta\n')
        before = install_menu.installed_evidence([self.bolt, build.parent / 'channel'])
        # Upstream's unset channel selects latest stable for this install but leaves
        # the stored channel unchanged for future pi-bolt updates.
        for command in ((), ('update',)):
            self.log.write_text('')
            result = self.install(*command, '--only', 'pi-bolt', env={'PIBOLT_VARIANT': 'x64'})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('current (release checked', result.stdout)
            self.assertEqual(install_menu.installed_evidence([self.bolt, build.parent / 'channel']), before)
            self.assertTrue(self.calls('curl')[0].endswith('/releases/latest'))
            self.assertEqual(self.calls('pi-bolt-installer'), [])
            self.assertEqual(self.calls('systemctl --user try-restart'), [])

    def test_pi_bolt_upstream_release_overrides_and_channel(self):
        root = self.home / 'custom install'
        self.native_bolt(variant='x64-jit', root=root)
        env = {'PIBOLT_INSTALL': str(root), 'PIBOLT_VARIANT': 'jit'}
        cases = [({'PIBOLT_VERSION': 'bolt-v1.4.0'},
                  {'tag_name': 'bolt-v1.4.0', 'draft': False, 'prerelease': False}, '/tags/bolt-v1.4.0'),
                 ({'PIBOLT_CHANNEL': 'beta'},
                  [{'tag_name': 'bolt-v1.9.0', 'draft': False, 'prerelease': False},
                   {'tag_name': 'bolt-v1.10.0', 'draft': False, 'prerelease': True,
                    # The real 30-row response including assets exceeds 1 MiB.
                    'assets': [{'name': 'pi-bolt-linux-x64-jit.tar.xz'}] * 29000},
                   {'tag_name': 'bolt-v1.11.0', 'draft': True, 'prerelease': False}], '?per_page=30')]
        for overrides, metadata, suffix in cases:
            with self.subTest(overrides=overrides):
                if overrides.get('PIBOLT_CHANNEL') == 'beta':
                    self.native_bolt(version='1.10.0', variant='x64-jit', root=root)
                    (root / 'channel').write_text('beta\n')
                (self.home / 'release.json').write_text(json.dumps(metadata))
                self.log.write_text('')
                result = self.install('--only', 'pi-bolt', env={**env, **overrides})
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('current (release checked', result.stdout)
                self.assertEqual(len(self.calls('curl')), 1)
                self.assertTrue(self.calls('curl')[0].endswith(suffix))
                max_bytes, rate = ((8388608, '512K') if overrides.get('PIBOLT_CHANNEL') == 'beta'
                                   else (1048576, '64K'))
                for flag in ('--proto =https', '--proto-redir =https', '--connect-timeout 10',
                             '--max-time 30', f'--max-filesize {max_bytes}', f'--limit-rate {rate}'):
                    self.assertIn(flag, self.calls('curl')[0])
                self.assertEqual(self.calls('pi-bolt-installer'), [])
        self.log.write_text('')
        result = self.install('--only', 'pi-bolt', '--dry-run', env={**env, 'FAKE_RELEASE_FAIL': '1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls(), [])

    def test_pi_bolt_stable_start_launcher_and_ambiguous_overrides(self):
        build = self.native_bolt(root=self.home / "custom 'root'")
        install_root = f'{build.parent}/'
        launcher = build.parent / (build.name + '.start')
        # Upstream embeds the literal override, including the trailing slash and escaped quotes.
        quoted = f'{install_root}/{build.name}'.replace("'", "'\\''")
        launcher.write_text(f"#!/bin/sh\ndir='{quoted}'\n"
                            'if [ -x "$dir/pi-start" ]; then exec "$dir/pi-start" "$@"; fi\n'
                            'exec "$dir/pi" "$@"\n')
        launcher.chmod(0o755)
        self.bolt.unlink()
        self.bolt.symlink_to(launcher)
        result = self.install('--only', 'pi-bolt', env={'PIBOLT_VARIANT': 'x64', 'PIBOLT_INSTALL': install_root})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('current (release checked', result.stdout)
        self.assertEqual(self.calls('pi-bolt-installer'), [])
        for override in ({'PIBOLT_NO_PATH': '1'}, {'PIBOLT_DOWNLOAD_BASE': 'https://mirror.invalid'},
                         {'PIBOLT_LAUNCHER': '1'}, {'PIBOLT_PASEO': 'yes'},
                         {'PREFIX': '/data/user/0/com.termux/files/usr'}, {'PIBOLT_CHANNEL': 'unknown'},
                         {'PIBOLT_VARIANT': 'unknown'}):
            with self.subTest(override=override):
                self.native_bolt()
                self.log.write_text('')
                env = {'PIBOLT_VARIANT': 'x64', **override}
                direct = 'PIBOLT_VARIANT' not in override
                if direct:
                    env['FAKE_RELEASE_FAIL'] = '1'
                result = self.install('--only', 'pi-bolt', env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(self.calls('pi-bolt-installer')), 1)
                self.assertEqual(len(self.calls('curl')), 1 if direct else 2)
                self.assertTrue(self.calls('curl')[-1].endswith('/install.sh'))
                self.assertNotIn('current (release checked', result.stdout)

    def test_pi_bolt_uses_the_selected_bin_directory(self):
        destination = self.home / 'custom bin'
        result = self.install('--only', 'pi-bolt', env={'KIT_BIN_DIR': str(destination)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'{destination / "pi-bolt"}: 1.4.0', result.stdout)
        self.assertEqual(self.calls('pi-bolt-installer'),
                         [f'pi-bolt-installer {destination}|1|no'])

    def test_pi_bolt_failure_keeps_other_components(self):
        self.bolt.unlink()
        result = self.install('--only', 'pi-bolt,tx', env={'PI_BOLT_FIXTURE_STAGE': 'install'})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi-bolt\s+failed.*signature verification failed')
        self.assertRegex(result.stdout, r'tx\s+installed')
        self.assertFalse((self.home / '.local/bin/pi-bolt').exists())

    def test_pi_bolt_empty_download_fails_without_running_the_installer(self):
        result = self.install('--only', 'pi-bolt', env={'PI_BOLT_FIXTURE_STAGE': 'download-empty'})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi-bolt\s+failed.*size limit')
        self.assertEqual(self.calls('pi-bolt-installer'), [])

    def test_pi_bolt_unsupported_platform_skips_or_fails(self):
        for system, machine, supported in (('Linux', 'x86_64', True), ('Linux', 'aarch64', True),
                                           ('Darwin', 'arm64', True), ('Darwin', 'x86_64', False),
                                           ('Windows', 'AMD64', False)):
            with self.subTest(system=system, machine=machine), \
                 patch.object(install_menu.platform, 'system', return_value=system), \
                 patch.object(install_menu.platform, 'machine', return_value=machine):
                item = install_menu.pi_bolt_item()
                self.assertEqual(item.available, supported)
                package = install_menu.items([])[1]
                self.assertEqual(package.key, 'pi')
                self.assertEqual(package.available, supported)
                if not supported:
                    self.assertIn('unsupported Pi-Bolt platform', item.missing)

    def test_unknown_component_refuses_and_preserves_private_state(self):
        state = self.home / '.local/state/unknown-runner'
        state.mkdir(parents=True)
        evidence = state / 'preserved-attempt.json'
        evidence.write_text('{"unfinished": true}\n')
        for args in (('--only', 'unknown-runner'), ('update', '--only', 'unknown-runner')):
            with self.subTest(args=args):
                result = self.install(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unknown-runner', result.stdout + result.stderr)
                self.assertEqual(evidence.read_text(), '{"unfinished": true}\n')
        self.assertNotRegex(self.install('--list').stdout, r'(?m)^unknown-runner\s')

    def test_octet_install_is_removed(self):
        for args in (('--only', 'octet'), ('update', '--only', 'octet')):
            with self.subTest(args=args):
                result = self.install(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unknown item', result.stdout + result.stderr)
        self.assertNotRegex(self.install('--list').stdout, r'(?m)^octet\s')
        self.assertFalse((self.home / '.octet').exists())

    def test_all_installs_every_available_item_in_order(self):
        self.bolt.unlink()
        (self.home / '.local/bin').rmdir()
        result = self.install('--all')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi-bolt install'), [f'pi-bolt install {NEW}'])
        self.assertEqual(self.calls('pi '), [])
        # Fresh registrations are qualified before any install, without removal.
        self.assertEqual(self.calls('claude'), ['claude plugin list --json',
                                                'claude plugin marketplace add TrebuchetDynamics/kit',
                                                'claude plugin list --json',
                                                'claude plugin marketplace update kit',
                                                'claude plugin install kit@kit',
                                                'claude plugin list --json'])
        self.assertEqual(self.calls('codex'), ['codex plugin marketplace list --json',
                                               'codex plugin list --marketplace kit-marketplace --json',
                                               'codex plugin marketplace add TrebuchetDynamics/kit --ref main',
                                               'codex plugin marketplace list --json',
                                               'codex plugin list --marketplace kit-marketplace --json',
                                               'codex plugin marketplace upgrade kit-marketplace',
                                               'codex plugin add kit@kit-marketplace',
                                               'codex plugin marketplace list --json',
                                               'codex plugin list --marketplace kit-marketplace --json'])
        self.assertEqual((self.home / '.local/bin/tx').read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertTrue((self.home / '.local/share/bash-completion/completions/tx').is_file())
        for shell in ('bash', 'zsh', 'fish'):
            self.assertIn(f'{shell} completion written', result.stdout)
        self.assertTrue((self.home / '.tmux.conf').is_file())  # none existed
        self.assertRegex(result.stdout, r'hermes\s+skipped\s+hermes not found')
        self.assertRegex(result.stdout, r'tx\s+installed')
        self.assertRegex(result.stdout, r'pi-bolt\s+installed.*1\.4\.0')
        self.assertEqual(len(self.calls('pi-bolt-installer')), 1)
        self.assertRegex(result.stdout, r'pi\s+installed')
        calls = self.calls()
        self.assertLess(next(i for i, c in enumerate(calls) if c.startswith('pi-bolt-installer')),
                        calls.index(f'pi-bolt install {NEW}'))
        self.assertRegex(result.stdout, r'orbi\s+installed.*orbi 0.7.41')
        self.assertEqual(self.calls('uv'), [f'uv tool install --python 3.14 {ORBI_SOURCE}'])

    def test_codex_unsupported_registry_interface_refuses_without_fallback(self):
        self.fake('codex', LOGGING + "echo 'unrecognized subcommand list' >&2; exit 2\n")
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('required capability codex plugin marketplace list --json', result.stdout)
        self.assertIn('unrecognized subcommand list', result.stdout)
        self.assertEqual(self.calls('codex'), ['codex plugin marketplace list --json'])
        self.assertRegex(result.stdout, r'codex\s+failed')

    def test_codex_failed_registry_read_stops_before_modification(self):
        self.fake('codex', LOGGING + "echo 'permission denied while reading marketplace' >&2; exit 1\n")
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('permission denied', result.stdout)
        self.assertEqual(self.calls('codex'), ['codex plugin marketplace list --json'])
        self.assertRegex(result.stdout, r'codex\s+failed')

    def test_update_runs_the_same_items_as_a_full_install(self):
        result = self.install('update')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Kit suite update', result.stdout)
        self.assertRegex(result.stdout, r'pi-bolt\s+installed.*1\.4\.0')
        self.assertIn(f'pi-bolt install {NEW}', self.calls('pi-bolt '))
        self.assertIn('claude plugin install kit@kit', self.calls('claude'))
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))

    def test_pi_install_is_idempotent_and_stale_registration_is_repaired(self):
        (self.home / 'pi-installed').write_text(NEW + '\n')  # absent package directory
        first = self.install('--only', 'pi')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': [], 'extensions': []}]}))
        second = self.install('--only', 'pi')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.calls('pi-bolt install'), [f'pi-bolt install {NEW}'])
        self.assertEqual(self.calls('pi-bolt update'), [f'pi-bolt update {NEW}'])  # never kept
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertIn('Service decisions', second.stdout)

    def test_a_marketplace_from_a_configured_source_is_used_and_not_rewritten(self):
        self.claude_registry(['kit'], {'source': 'directory', 'path': str(ROOT)})
        registry = self.home / '.claude/plugins/known_marketplaces.json'
        before = registry.read_bytes()
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json', 'claude plugin marketplace update kit',
                                               'claude plugin install kit@kit', 'claude plugin list --json'])
        self.assertEqual(registry.read_bytes(), before)
        self.assertRegex(result.stdout, r'claude\s+installed')

    def test_an_unrelated_marketplace_failure_still_fails_the_item(self):
        self.claude_host(mutation='''
if [[ $2 == marketplace && $3 == add ]]; then
  echo 'Failed to add marketplace: network unavailable' >&2
  exit 1
fi
exit 0
''')
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('network unavailable', result.stdout)
        self.assertRegex(result.stdout, r'claude\s+failed')
        self.assertNotIn('claude plugin install kit@kit', self.calls('claude'))

    def test_a_marketplace_recording_a_folder_this_host_lacks_is_not_deleted(self):
        for name in ('kit',):
            with self.subTest(name=name):
                self.log.write_text('')
                self.claude_registry([name], {'source': 'directory', 'path': str(self.home / 'gone')})
                result = self.install('--only', 'claude')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('manual migration required', result.stdout)
                self.assertEqual(self.calls('claude'), ['claude plugin list --json'])

    def test_a_recorded_marketplace_folder_that_exists_is_left_alone(self):
        self.claude_registry(['kit'], {'source': 'directory', 'path': str(ROOT)})
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json', 'claude plugin marketplace update kit',
                                               'claude plugin install kit@kit', 'claude plugin list --json'])

    def test_a_transient_preflight_race_is_retried_once(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        import install_menu
        original = install_menu.run_command
        self.addCleanup(setattr, install_menu, 'run_command', original)
        answers = [(1, 'ValueError: Destination changed since preflight: /x/skills/SKILL.md'), (0, '')]
        install_menu.run_command = lambda argv, output, **kwargs: answers.pop(0)
        continued = self.home / 'after-retry'
        def next_step():
            continued.touch()
            return 'finished next step'
        item = install_menu.Item('hermes', 'Hermes plugin', steps=[
            install_menu.Step('update_bundle.py', ['true'], retry_on='changed since preflight'),
            install_menu.Step('dependent step', run=next_step)])
        code = install_menu.install([item], {'hermes'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 0)
        self.assertEqual(answers, [])  # the second (successful) run consumed the queue
        self.assertTrue(continued.exists())

    def test_a_failure_without_the_retry_marker_is_not_retried(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import install_menu
        original = install_menu.run_command
        self.addCleanup(setattr, install_menu, 'run_command', original)
        seen = []

        def fake(argv, output, **kwargs):
            seen.append(argv)
            return 1, 'some other failure'

        install_menu.run_command = fake
        item = install_menu.Item('hermes', 'Hermes plugin', steps=[
            install_menu.Step('update_bundle.py', ['true'], retry_on='changed since preflight')])
        code = install_menu.install([item], {'hermes'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 1)
        self.assertEqual(len(seen), 1)

    def test_partial_suite_reports_structured_hermes_cause_with_bounded_fallback(self):
        import contextlib
        import io
        import json
        import sys
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        import install_menu
        failures = (
            ('native log\n' + json.dumps({'status': 'incomplete', 'error': 'Unproven checkout',
                'action': 'Preserve local commits; retry ./install.sh --only hermes'}, indent=2),
             'Unproven checkout'),
            (json.dumps({'status': 'incomplete', 'recovery': {'profiles': {
                'default': {'error': 'Native scanner denied staged source'}}},
                'action': 'Preserve backup; retry ./install.sh --only hermes'}, indent=2),
             'Native scanner denied staged source'),
            ('network unavailable\n{\n  "status": "incomplete",\n}', 'network unavailable'),
            ('x' * 4000 + '\nGit fetch failed\n}', 'Git fetch failed'),
        )
        for text, cause in failures:
            with self.subTest(cause=cause):
                items = [install_menu.Item(key, key, steps=[install_menu.Step('install', [key])])
                         for key in ('pi', 'orbi', 'tx', 'hermes', 'claude', 'codex')]
                output = io.StringIO()
                with patch.object(install_menu, 'run_command',
                        side_effect=lambda argv, _, **kwargs: (1, text) if argv == ['hermes'] else (0, 'ok')), \
                     contextlib.redirect_stdout(output):
                    code = install_menu.install(items, {item.key for item in items},
                                                output=install_menu.Output('never', 0))
                self.assertEqual(code, 1)
                summary = output.getvalue().split('Summary:')[1]
                self.assertIn('6 installed', summary)  # five components plus service activation
                self.assertIn(cause, summary)
                self.assertNotIn('failed    }', summary)
                self.assertLess(len(summary), 2000)
                if cause == 'Unproven checkout': self.assertIn('--only hermes', summary)

    def test_no_arguments_installs_full_suite_with_verbose_output(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi-bolt install'), [f'pi-bolt install {NEW}'])
        self.assertIn('claude plugin install kit@kit', self.calls('claude'))
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))
        self.assertTrue((self.home / '.local/bin/tx').is_file())
        self.assertIn('$ codex plugin add kit@kit-marketplace', result.stdout)
        self.assertRegex(result.stdout, r'pi-bolt\s+installed.*1\.4\.0')
        self.assertRegex(result.stdout, r'hermes\s+skipped.*hermes not found')

    def test_default_install_enables_the_pi_package_without_extra_flags(self):
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [
            {'source': NEW, 'skills': [], 'extensions': []},
        ]}))
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertIn('enabled', result.stdout)

    def test_dry_run_defaults_to_the_full_suite_without_installing(self):
        self.fake('hermes', LOGGING)
        (self.home / '.hermes').mkdir()
        result = self.install('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ('pi', 'pi-bolt', 'tx', 'hermes', 'claude', 'codex'):
            self.assertRegex(result.stdout, rf'{key}\s+planned')
        self.assertEqual(self.calls('pi-bolt install'), [])
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(self.calls('hermes'), [])
        self.assertFalse(self.calls('curl'))
        self.assertEqual(list((self.home / '.local/bin').iterdir()), [self.bolt])
        self.assertIn('enable the package skills and commands in Pi settings', result.stdout)

    def test_tx_installs_executable_clipboard_helper(self):
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        helper = self.home / '.tmux/copy.sh'
        self.assertEqual(helper.read_bytes(), (ROOT / 'tmux/copy.sh').read_bytes())
        self.assertEqual(stat.S_IMODE(helper.stat().st_mode), 0o755)
        self.assertIn(str(helper), (self.home / '.tmux.conf').read_text())

    @unittest.skipUnless(shutil.which('tmux'), 'tmux is not installed')
    def test_tx_clipboard_command_works_with_spaces_in_home(self):
        home = self.home / 'desktop home'
        home.mkdir()
        env = {**self.env, 'HOME': str(home), 'DISPLAY': 'test-display',
               'TEST_CLIPBOARD': str(home / 'clipboard')}
        result = self.install('--only', 'tx', env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.fake('xsel', '#!/bin/sh\n/bin/cat > "$TEST_CLIPBOARD"\n')
        socket = str(self.home / 'clipboard-socket')
        self.addCleanup(lambda: subprocess.run(
            ['tmux', '-S', socket, 'kill-server'], env=env,
            capture_output=True, timeout=10))
        result = subprocess.run(
            ['tmux', '-S', socket, '-f', str(home / '.tmux.conf'),
             'new-session', '-d', '-s', 'test'],
            env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            ['tmux', '-S', socket, 'show-options', '-sv', 'copy-command'],
            env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        copied = subprocess.run(['/bin/sh', '-c', result.stdout.strip()],
                                input=b'clipboard probe\n', env=env,
                                capture_output=True, timeout=10)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual((home / 'clipboard').read_bytes(), b'clipboard probe\n')

    def test_tx_keeps_an_existing_tmux_config(self):
        mine = b'set -g mouse on\n# mine\n'
        paths = ('.tmux.conf', '.tmux/style.tmux', '.tmux/git-status.sh', '.tmux/short-path.sh', '.tmux/copy.sh')
        for relative in paths:
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(mine)
        completion_paths = ('.local/share/bash-completion/completions/tx',
                            '.zsh/completions/_tx', '.config/fish/completions/tx.fish')
        link_target = self.home / 'my-completion'
        link_target.write_bytes(mine)
        for index, relative in enumerate(completion_paths):
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(link_target if index != 1 else self.home / 'missing-completion')
        preview = self.install('--full', '--skip', 'hermes,pi', '--dry-run')
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse((self.home / '.local/bin/tx').exists())
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stderr)
        for relative in paths:
            self.assertEqual((self.home / relative).read_bytes(), mine, relative)
        self.assertIn('kept your existing .tmux.conf', result.stdout)
        # A kept completion is reported as kept, never as written, and the summary
        # row does not repeat its own outcome word.
        for shell, relative in zip(('bash', 'zsh', 'fish'), completion_paths):
            path = self.home / relative
            self.assertTrue(path.is_symlink())
            self.assertIn(f'{shell} completion kept', result.stdout)
            self.assertFalse(path.with_name(path.name + '.bak').exists())
        self.assertEqual(link_target.read_bytes(), mine)
        self.assertFalse((self.home / completion_paths[1]).exists())
        self.assertNotIn('completions for', result.stdout)
        self.assertNotRegex(result.stdout, r'installed\s+installed')
        self.assertEqual(self.calls('pi-bolt install'), [])
        config = self.home / '.tmux.conf'
        config.unlink()
        config.symlink_to(self.home / 'absent-user-config')
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(config.is_symlink())
        self.assertFalse(config.exists())

    def test_tx_refreshes_stale_regular_completions_with_backups(self):
        paths = {'bash': '.local/share/bash-completion/completions/tx',
                 'zsh': '.zsh/completions/_tx', 'fish': '.config/fish/completions/tx.fish'}
        for shell, relative in paths.items():
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'old {shell} completion\n')
            path.with_name(path.name + '.bak').write_text('earlier backup\n')
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        command = self.home / '.local/bin/tx'
        for shell, relative in paths.items():
            generated = subprocess.run([str(command), 'completion', shell], env=self.env,
                                       capture_output=True, timeout=10, check=True).stdout
            self.assertTrue(generated)
            path = self.home / relative
            self.assertEqual(path.read_bytes(), generated)
            self.assertEqual(path.with_name(path.name + '.bak.1').read_text(),
                             f'old {shell} completion\n')
            self.assertEqual(path.with_name(path.name + '.bak').read_text(), 'earlier backup\n')
            self.assertIn(f'{shell} completion replaced', result.stdout)
        again = self.install('--only', 'tx')
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        for shell, relative in paths.items():
            path = self.home / relative
            self.assertIn(f'{shell} completion kept', again.stdout)
            self.assertFalse(path.with_name(path.name + '.bak.2').exists())

    def test_an_ordinary_install_refreshes_a_package_missing_a_shipped_skill(self):
        # A registered checkout older than this one lacks the skills a later release
        # added (orbi). A kept package left Pi without `/skill:orbi` and `/orbi` entirely.
        self.installed_package(only=['plan-with-me'])
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi-bolt install'), [])
        self.assertEqual(self.calls('pi-bolt update'), [f'pi-bolt update {NEW}'])
        self.assertRegex(result.stdout, r'skills missing: .*\borbi\b')
        self.assertRegex(result.stdout, r'pi\s+installed')

    def test_an_ordinary_install_refreshes_a_package_that_ships_every_skill(self):
        # Complete skill folders are not proof of current content: every install
        # refreshes, so edited or removed skills cannot stay live unnoticed.
        self.installed_package()
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi-bolt update'), [f'pi-bolt update {NEW}'])
        self.assertIn('every install refreshes the installed package', result.stdout)
        self.assertNotIn('already installed', result.stdout)

    def test_every_install_refreshes_the_package_and_update_does_too(self):
        self.installed_package(only=['plan-with-me'])
        for args in (('--only', 'pi'), ('--only', 'pi'), ('update', '--only', 'pi')):
            result = self.install(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls('pi-bolt update')), 3)  # one refresh per run, never kept

    def test_a_refresh_that_cannot_reach_the_source_fails_the_item(self):
        # The package is installed but the suite's skills stay incomplete: report the
        # cause and a retry instead of claiming a complete install.
        self.installed_package(only=['plan-with-me'])
        result = self.install('--only', 'pi', env={'FAKE_PI_UPDATE_FAIL': '1'})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('network is unreachable', result.stdout)
        self.assertRegex(result.stdout, r'pi\s+failed')

    def test_successful_pi_exit_without_package_resources_is_not_installation_success(self):
        for action in ('install', 'update'):
            with self.subTest(action=action):
                if action == 'update':
                    package = self.installed_package(only=['plan-with-me'])
                else:
                    package = self.home / 'pkg/kit'
                self.fake_bolt(PI.replace('  install|update)',
                    '  install|update) echo "Skipped package updates (offline mode)"; exit 0 ;;\n  unused)'))
                settings = self.home / '.pi/agent/settings.json'
                settings.parent.mkdir(parents=True, exist_ok=True)
                settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': []}]}))
                before = settings.read_bytes()
                result = self.install('--only', 'pi')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertRegex(result.stdout, rf'pi\s+failed.*package {action} did not complete')
                self.assertIn('PI_OFFLINE', result.stdout)
                self.assertEqual(settings.read_bytes(), before)
                self.assertFalse((package / 'adapters/skills/orbi/SKILL.md').exists())
                self.assertNotIn('Open a new host session', result.stdout)

    def test_an_installed_package_is_updated_and_its_runners_move_onto_it(self):
        self.installed_package()
        result = self.install('update', '--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('pi-bolt install'), [])
        self.assertEqual(self.calls('pi-bolt update'), [f'pi-bolt update {NEW}'])
        self.assertRegex(result.stdout, r'pi\s+installed')

    def test_menu_toggles_items_and_needs_a_terminal(self):
        result = self.install('--dry-run', '--menu', stdin='3 5 6\n\n', env={'KIT_INSTALL_UI': 'text'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[x] 2 Kit package for Pi', result.stdout)
        self.assertRegex(result.stdout, r'tx\s+skipped\s+not chosen')
        self.assertRegex(result.stdout, r'pi\s+planned')
        self.assertEqual(self.calls('pi-bolt install'), [])  # a dry run runs nothing
        self.assertIn('no terminal for the menu', self.install('--menu').stderr)

    def test_previews_do_not_create_or_change_a_lock_or_receipt(self):
        binary_dir = self.home / '.local/bin'
        lock_path = binary_dir.with_name('bin.kit-install.lock')
        report = self.home / 'preview.jsonl'
        env = {'KIT_INSTALL_REPORT': str(report), 'KIT_INSTALL_UI': 'text'}

        def previews():
            before = {p.relative_to(self.home): p.read_bytes() if p.is_file() else None
                      for p in self.home.rglob('*')}
            for args, stdin in ((('--only', 'tx', '--dry-run'), None),
                                (('--list',), None),
                                (('--menu', '--dry-run', '--only', 'tx'), '\n'),
                                (('--menu',), 'q\n')):
                with self.subTest(args=args, held=lock_path.exists()):
                    result = self.install(*args, stdin=stdin, env=env)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = {p.relative_to(self.home): p.read_bytes() if p.is_file() else None
                     for p in self.home.rglob('*')}
            self.assertEqual(after, before)
            self.assertFalse(report.exists())

        previews()
        self.assertFalse(lock_path.exists())
        # Preview also succeeds while another writer actually owns the lock.
        with lock_path.open('w') as lock:
            lock.write(f'{os.getpid()}\n')
            lock.flush()
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            previews()

    def test_installer_lock_is_released_on_exception_and_old_metadata_is_not_ownership(self):
        import contextlib
        import io

        def interrupt():
            raise KeyboardInterrupt()

        item = install_menu.Item('fixture', 'Fixture', steps=[install_menu.Step('interrupt', run=interrupt)])
        output = install_menu.Output('never', 0)
        lock_path = (self.home / '.local/bin.kit-install.lock')
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            install_menu.install([item], {'fixture'}, output=output)
        inode = lock_path.stat().st_ino
        # Model a dead installer's metadata without deleting its persistent inode.
        lock_path.write_text('999999999\n')
        item.steps = [install_menu.Step('finish', run=lambda: 'done')]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_menu.install([item], {'fixture'}, output=output), 0)
        self.assertEqual(lock_path.stat().st_ino, inode)
        self.assertEqual(lock_path.read_text(), f'{os.getpid()}\n')
        with lock_path.open() as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_a_second_install_run_does_not_share_the_receipt(self):
        self.claude_host(mutation='''
if [[ "$*" == "plugin marketplace add TrebuchetDynamics/kit" ]]; then
    printf 'installer holding: '
    read -r answer
    test "$answer" = continue || exit 9
fi
''')
        report = self.home / 'install.jsonl'
        # Exercise a custom destination too; the lock belongs to the deployment,
        # not the source checkout, selected component, or receipt filename.
        binary_dir = self.home / 'custom/bin'
        env = {**self.env, 'KIT_INSTALL_REPORT': str(report),
               'KIT_BIN_DIR': str(binary_dir)}
        with subprocess.Popen(['bash', str(INSTALL), '--only', 'claude'], env=env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as first:
            seen = b''
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(first.stdout, selectors.EVENT_READ)
                    deadline = time.monotonic() + 10
                    while b'installer holding: ' not in seen:
                        remaining = deadline - time.monotonic()
                        self.assertGreater(remaining, 0, seen.decode(errors='replace'))
                        self.assertTrue(selector.select(timeout=remaining), seen.decode(errors='replace'))
                        chunk = os.read(first.stdout.fileno(), 4096)
                        self.assertTrue(chunk, seen.decode(errors='replace'))
                        seen += chunk
                before = report.read_bytes()
                calls = self.calls()
                second = subprocess.run(['bash', str(INSTALL), '--only', 'tx', '--quiet'],
                                        env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(report.read_bytes(), before, 'second run changed the active receipt')
                self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
                self.assertIn(f'PID {first.pid}', second.stdout + second.stderr)
                self.assertIn(str(binary_dir.with_name('bin.kit-install.lock')), second.stdout + second.stderr)
                self.assertEqual(self.calls(), calls)
                self.assertFalse((binary_dir / 'tx').exists())
                first.stdin.write(b'continue\n')
                first.stdin.flush()
                tail, _ = first.communicate(timeout=10)
                self.assertEqual(first.returncode, 0, (seen + tail).decode(errors='replace'))
                expected = b''.join((json.dumps({'item': key, 'status': status, 'exit': code}) + '\n').encode()
                                    for key, status, code in [
                                        ('pi-bolt', 'skipped', None), ('pi', 'skipped', None),
                                        ('tx', 'skipped', None), ('hermes', 'skipped', None),
                                        ('claude', 'installed', 0), ('codex', 'skipped', None),
                                        ('orbi', 'skipped', None), ('services', 'installed', 0)])
                self.assertEqual(b''.join((json.dumps({k: row[k] for k in ('item', 'status', 'exit')}) + '\n').encode()
                                         for row in map(json.loads, report.read_text().splitlines())), expected)
                # The same entry point succeeds after the holder finishes.
                repaired = self.install('--only', 'tx', '--quiet', env=env)
                self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
                self.assertTrue((binary_dir / 'tx').is_file())
            finally:
                if first.poll() is None:
                    first.kill()
                    first.wait(timeout=5)

    def test_failed_steps_remain_failures_even_when_output_says_already(self):
        self.fake('claude', LOGGING + 'echo "boom: no network" >&2; exit 1\n')
        self.fake('codex', LOGGING + 'echo "marketplace already added" >&2; exit 4\n')
        report = self.home / 'install.jsonl'
        result = self.install('--full', '--skip', 'hermes,pi', '-q',
                              env={'KIT_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 1)
        import json
        rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['claude'], {'item': 'claude', 'status': 'failed', 'exit': 1})
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'failed', 'exit': 4})
        self.assertEqual({k: rows['tx'][k] for k in ('item', 'status', 'exit')}, {'item': 'tx', 'status': 'installed', 'exit': 0})
        self.assertEqual(rows['hermes'], {'item': 'hermes', 'status': 'skipped', 'exit': None})
        self.assertRegex(result.stdout, r'claude\s+failed.*boom: no network')
        self.assertRegex(result.stdout, r'codex\s+failed.*marketplace already added')
        self.assertIn('unknown item(s): nope', self.install('--only', 'nope').stderr)
        (self.bin / 'codex').unlink()
        self.install('--full', '--skip', 'hermes,pi', '-q',
                     env={'KIT_INSTALL_REPORT': str(report)})
        rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'skipped', 'exit': None})

    def test_failed_marketplace_update_preserves_plugin_and_continues_other_hosts(self):
        self.claude_host(mutation='''
if [[ "$*" == "plugin marketplace update kit" ]]; then
    echo "fixture marketplace unavailable" >&2
    exit 23
fi
''')
        report = self.home / 'install.jsonl'
        result = self.install('--only', 'claude,codex', '-q',
                              env={'KIT_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), [
            'claude plugin list --json',
            'claude plugin marketplace add TrebuchetDynamics/kit',
            'claude plugin list --json',
            'claude plugin marketplace update kit',
            'claude plugin list --json'])
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))
        import json
        rows = {row['item']: row for row in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['claude'], {'item': 'claude', 'status': 'failed', 'exit': 23})
        self.assertEqual({k: rows['codex'][k] for k in ('item', 'status', 'exit')}, {'item': 'codex', 'status': 'installed', 'exit': 0})

    def test_step_exceptions_stop_only_the_failed_component(self):
        import contextlib
        import io
        for failure in ('missing executable', 'callable OS error', 'callable subprocess error'):
            with self.subTest(failure=failure):
                dependent, independent = [], []
                def fail():
                    if failure == 'callable OS error':
                        raise OSError('fixture denied')
                    raise subprocess.CalledProcessError(7, 'fixture')
                step = (install_menu.Step('missing executable', [str(self.home / 'absent')])
                        if failure == 'missing executable' else install_menu.Step('failed callable', run=fail))
                items = [install_menu.Item('failed', 'Failed component', steps=[step,
                             install_menu.Step('dependent step', run=lambda: dependent.append('ran') or 'ok')]),
                         install_menu.Item('other', 'Independent component', steps=[
                             install_menu.Step('independent step', run=lambda: independent.append('ran') or 'ok')])]
                with contextlib.redirect_stdout(io.StringIO()):
                    code = install_menu.install(items, {'failed', 'other'}, output=install_menu.Output('never', 0))
                self.assertEqual(code, 1)
                self.assertEqual(dependent, [])
                self.assertEqual(independent, ['ran'])

    def test_exhausted_retry_stops_dependent_steps_and_preserves_failure_receipt(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        attempts = self.home / 'attempts'
        report = self.home / 'install.jsonl'
        continued = []
        script = (f'from pathlib import Path; p = Path({str(attempts)!r}); '
                  'p.write_text(p.read_text() + "x" if p.exists() else "x"); '
                  'print("changed since preflight"); raise SystemExit(23)')
        item = install_menu.Item('retry', 'Retry fixture', steps=[
            install_menu.Step('retryable command', [sys.executable, '-c', script],
                              retry_on='changed since preflight'),
            install_menu.Step('dependent step', run=lambda: continued.append('ran') or 'ok')])
        with patch.dict(os.environ, KIT_INSTALL_REPORT=str(report)), contextlib.redirect_stdout(io.StringIO()):
            code = install_menu.install([item], {'retry'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 1)
        self.assertEqual(attempts.read_text(), 'xx')
        self.assertEqual(continued, [])
        rows = [json.loads(line) for line in report.read_text().splitlines()]
        self.assertEqual(rows[0], {'item': 'retry', 'status': 'failed', 'exit': 23})
        self.assertEqual({k: rows[1][k] for k in ('item', 'status', 'exit')}, {'item': 'services', 'status': 'installed', 'exit': 0})

    def test_full_selects_all_hosts_and_bundled_skills(self):
        self.fake('hermes', LOGGING)
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ('pi', 'tx', 'hermes', 'claude', 'codex'):
            self.assertRegex(result.stdout, rf'{key}\s+planned')
        self.assertIn('codex plugin add kit@kit-marketplace', result.stdout)
        self.assertIn('setup_bundle.py', result.stdout)
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(self.calls('hermes'), [])

    def test_explicit_missing_host_fails_but_other_items_continue(self):
        result = self.install('--only', 'hermes,tx')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, r'hermes\s+failed.*hermes not found')
        self.assertTrue((self.home / '.local/bin/tx').is_file())

    def test_default_output_shows_both_child_streams(self):
        self.codex_registry(mutation='echo "skill stdout"; echo "skill stderr" >&2')
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skill stdout', result.stdout)
        self.assertIn('skill stderr', result.stdout)
        self.assertIn('[1/1]', result.stdout)
        self.assertNotIn('\x1b[', result.stdout)

    def test_verbose_prints_commands_and_quiet_keeps_failure_details(self):
        self.codex_registry(mutation='echo "registered skills"')
        result = self.install('--only', 'codex', '--verbose')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('$ codex plugin add', result.stdout)
        self.assertIn('registered skills', result.stdout)
        result = self.install('--only', 'codex', '--quiet')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('registered skills', result.stdout)
        self.assertNotIn('$ codex', result.stdout)
        self.assertRegex(result.stdout, r'codex\s+installed')
        self.codex_registry(mutation='echo "failure context"; echo "failure cause" >&2; exit 4')
        result = self.install('--only', 'codex', '--quiet')
        self.assertEqual(result.returncode, 1)
        self.assertIn('failure context', result.stdout)
        self.assertIn('failure cause', result.stdout)
        self.assertIn('exit 4', result.stdout)

    def test_color_controls_and_no_color_environment(self):
        for args, env, colored in (
            (('--color', 'always'), {}, True),
            (('--color', 'never'), {}, False),
            ((), {'NO_COLOR': '1', 'TERM': 'xterm-256color'}, False),
            (('--color', 'always'), {'NO_COLOR': '1'}, True),
        ):
            with self.subTest(args=args, env=env):
                result = self.install('--full', '--dry-run', *args, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual('\x1b[' in result.stdout, colored)

    def test_auto_color_uses_terminal_and_respects_opt_out(self):
        for env, colored in (({'TERM': 'xterm'}, True),
                             ({'TERM': 'dumb'}, False),
                             ({'TERM': 'xterm', 'NO_COLOR': '1'}, False)):
            with self.subTest(env=env):
                master, slave = pty.openpty()
                try:
                    result = subprocess.run(['bash', str(INSTALL), '--only', 'codex', '--dry-run'],
                                            env={**self.env, **env}, stdout=slave,
                                            stderr=subprocess.PIPE, timeout=10)
                    os.close(slave)
                    slave = None
                    chunks = []
                    while True:
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break  # Linux PTY reports EIO when its writer closes.
                        if not chunk:
                            break
                        chunks.append(chunk)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(b'\x1b[' in b''.join(chunks), colored)
                finally:
                    os.close(master)
                    if slave is not None:
                        os.close(slave)

    def test_child_output_arrives_before_command_exits(self):
        # The child cannot finish until the parent receives its prompt.
        # A capture-until-exit implementation deadlocks this handshake.
        self.codex_registry(mutation='printf "waiting for input: "; read -r answer; '
                            'test "$answer" = continue || exit 9')
        with subprocess.Popen(['bash', str(INSTALL), '--only', 'codex'], env=self.env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
            seen = b''
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(proc.stdout, selectors.EVENT_READ)
                    # Only the fresh add, upgrade and plugin add prompt, not registry probes.
                    for _ in range(3):
                        pending = b''
                        while b'waiting for input: ' not in pending:
                            self.assertTrue(selector.select(timeout=5), seen.decode(errors='replace'))
                            chunk = os.read(proc.stdout.fileno(), 4096)
                            self.assertTrue(chunk, seen.decode(errors='replace'))
                            pending += chunk
                            seen += chunk
                        proc.stdin.write(b'continue\n')
                        proc.stdin.flush()
                tail, _ = proc.communicate(timeout=5)
                seen += tail
                self.assertEqual(proc.returncode, 0, seen.decode(errors='replace'))
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    def test_hermes_options_reach_the_hermes_item(self):
        self.fake('hermes', LOGGING)
        result = self.install('--only', 'hermes', '--dry-run', '--hermes-home', '/h', '--yes-deps')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('setup_bundle.py --yes-deps --dry-run --hermes-home /h', result.stdout)
        # Profiles with their own plugin clone (`hermes plugins install`) are updated: setup
        # would refuse them as "another checkout".
        clone = self.home / '.hermes/profiles/work/plugins/kit'
        (clone / '.git').mkdir(parents=True)
        (clone / 'plugin.yaml').write_text('name: kit\n')
        result = self.install('--only', 'hermes', '--dry-run')
        self.assertIn(f"update_bundle.py --hermes-home {self.home / '.hermes'}", result.stdout)
        self.assertNotIn('setup_bundle.py', result.stdout)


    def test_hermes_discovery_identity_matrix(self):
        self.fake('hermes', LOGGING)
        plugins = self.home / '.hermes/plugins'
        plugins.mkdir(parents=True)
        canonical = plugins / 'kit'
        (canonical / '.git').mkdir(parents=True)
        (canonical / 'plugin.yaml').write_text('name: kit\n')
        result = self.install('--only', 'hermes', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('update_bundle.py --hermes-home', result.stdout)
        (canonical / 'plugin.yaml').write_text('name: foreign\n')
        result = self.install('--only', 'hermes', '--dry-run')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Invalid or foreign plugin identity', result.stdout)
        self.assertIn(str(canonical), result.stdout)
        self.assertEqual((canonical / 'plugin.yaml').read_text(), 'name: foreign\n')
        self.assertEqual(self.calls('hermes'), [])

    def test_tx_moves_a_symlink_aside_instead_of_writing_through_it(self):
        elsewhere = self.home / 'other-checkout/tx'
        elsewhere.parent.mkdir()
        elsewhere.write_text('someone else\'s tx\n')
        (self.home / '.local/bin').mkdir(parents=True, exist_ok=True)
        (self.home / '.local/bin/tx').symlink_to(elsewhere)
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(elsewhere.read_text(), 'someone else\'s tx\n')
        self.assertFalse((self.home / '.local/bin/tx').is_symlink())
        self.assertEqual((self.home / '.local/bin/tx').read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertEqual(Path(os.readlink(self.home / '.local/state/kit/backups/tx.bak')), elsewhere)

    def test_tx_replacements_keep_only_the_newest_five_backups_off_path(self):
        command = self.home / '.local/bin/tx'
        command.parent.mkdir(parents=True, exist_ok=True)
        legacy = command.with_name('tx.bak')
        legacy.write_text('legacy backup\n')
        legacy.chmod(0o755)
        backups = self.home / '.local/state/kit/backups'
        # Continue past six to catch retention bugs when numbered slots disappear.
        for number in range(8):
            command.write_text(f'script {number}\n')
            command.chmod(0o755)
            result = self.install('--only', 'tx')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual({p.read_text() for p in backups.iterdir()},
                             {f'script {i}\n' for i in range(max(0, number - 4), number + 1)})
            self.assertEqual(list(command.parent.glob('tx.bak*')), [legacy])
            self.assertEqual(command.read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertEqual(legacy.read_text(), 'legacy backup\n')
        self.assertTrue(os.access(legacy, os.X_OK))

    def test_tx_backup_failure_preserves_command_and_can_be_repaired(self):
        command = self.home / '.local/bin/tx'
        command.parent.mkdir(parents=True, exist_ok=True)
        command.write_text('my old tx\n')
        blocker = self.home / '.local/state/kit/backups'
        blocker.parent.mkdir(parents=True)
        blocker.write_text('not a directory\n')
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'tx\s+failed')
        self.assertIn('File exists', result.stdout)
        self.assertIn(str(blocker), result.stdout)
        self.assertEqual(command.read_text(), 'my old tx\n')
        blocker.unlink()  # Repair the reported path and retry the same entry point.
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(command.read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertEqual((blocker / 'tx.bak').read_text(), 'my old tx\n')

    def test_tx_backups_support_cross_device_files_and_symlinks(self):
        for kind in ('file', 'symlink', 'dangling'):
            with self.subTest(kind=kind):
                folder = self.home / kind
                folder.mkdir()
                command, target = folder / 'tx', folder / 'target'
                if kind == 'file':
                    command.write_bytes(b'old command\n')
                    command.chmod(0o751)
                else:
                    if kind == 'symlink':
                        target.write_bytes(b'other checkout\n')
                    command.symlink_to(target)
                # Model the OS boundary, while exercising actual stdlib copy/link
                # and unlink operations on fixture files.
                cross_device = OSError(errno.EXDEV, 'cross-device link')
                with patch.object(install_menu.os, 'replace', side_effect=cross_device), \
                     patch.object(install_menu.os, 'rename', side_effect=cross_device):
                    backup = install_menu.set_aside(command, backup_dir=folder / 'backups')
                self.assertFalse(os.path.lexists(command))
                if kind == 'file':
                    self.assertEqual(backup.read_bytes(), b'old command\n')
                    self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o751)
                else:
                    self.assertTrue(backup.is_symlink())
                    self.assertEqual(os.readlink(backup), str(target))
                    if kind == 'symlink':
                        self.assertEqual(target.read_bytes(), b'other checkout\n')
                    else:
                        self.assertFalse(target.exists())

    def test_tx_failed_cross_device_copy_preserves_source_and_previous_backups(self):
        command = self.home / 'tx'
        command.write_bytes(b'original command\n')
        backups = self.home / 'backups'
        backups.mkdir()
        for number in range(5):
            (backups / f'tx.bak.{number}').write_text(f'previous {number}\n')
        before = {p.name: p.read_bytes() for p in backups.iterdir()}
        cross_device = OSError(errno.EXDEV, 'cross-device link')
        with patch.object(install_menu.os, 'replace', side_effect=cross_device), \
             patch.object(install_menu.os, 'rename', side_effect=cross_device), \
             patch.object(install_menu.shutil, 'copyfile', side_effect=OSError('copy failed')):
            with self.assertRaisesRegex(OSError, 'copy failed'):
                install_menu.set_aside(command, backup_dir=backups)
        self.assertEqual(command.read_bytes(), b'original command\n')
        self.assertEqual({p.name: p.read_bytes() for p in backups.iterdir()}, before)

    def test_a_filtered_pi_package_counts_as_installed(self):
        package = self.installed_package()
        self.fake_bolt(LOGGING + f'[ "$1" = --version ] && echo 1.4.0\n[ "$1" = list ] && printf "User packages:\\n  {NEW} (filtered)\\n    {package}\\n"\ntrue\n')
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi-bolt install'), [])
        self.assertEqual(self.calls('pi-bolt update'), [f'pi-bolt update {NEW}'])

    def test_install_clears_empty_pi_filters_that_hide_skills_and_commands(self):
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        other = {'source': 'npm:other', 'skills': []}
        settings.write_text(json.dumps({'packages': [
            {'source': NEW, 'skills': [], 'extensions': []},
            other,
        ]}))
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW, other])
        self.assertIn('enabled', result.stdout)

    def test_install_keeps_a_deliberate_partial_pi_filter(self):
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({'packages': [
            {'source': NEW, 'skills': ['+./adapters/skills'], 'extensions': []},
        ]}))
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'],
                         [{'source': NEW, 'skills': ['+./adapters/skills']}])

    def test_pi_agent_directory_override_is_honored(self):
        agent = self.home / 'custom-agent'
        agent.mkdir()
        settings = agent / 'settings.json'
        settings.write_text(json.dumps({'packages': [{'source': NEW, 'skills': []}]}))
        result = self.install('--only', 'pi', env={'PI_CODING_AGENT_DIR': str(agent)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertFalse((self.home / '.pi/agent/settings.json').exists())

    def test_missing_manifest_pyyaml_warns_and_keeps_failure_receipt(self):
        self.fake('hermes', LOGGING)
        profile = self.home / 'alternate Hermes'
        plugin = profile / 'plugins/kit'
        (plugin / '.git').mkdir(parents=True)
        manifest = plugin / 'plugin.yaml'
        manifest.write_text('name: kit\n')
        imports = self.home / 'imports'
        imports.mkdir()
        (imports / 'sitecustomize.py').write_text(
            'import sys\n'
            'class NoYAML:\n'
            '    def find_spec(self, fullname, path=None, target=None):\n'
            '        if fullname == "yaml":\n'
            '            raise ModuleNotFoundError("fixture", name="yaml")\n'
            'sys.meta_path.insert(0, NoYAML())\n')
        report = self.home / 'report.jsonl'
        env = {'PYTHONPATH': str(imports), 'KIT_INSTALL_REPORT': str(report)}
        for selection, tx_status in ((('--only', 'hermes'), 'skipped'),
                                     (('--full', '--skip', 'pi,pi-bolt,orbi,claude,codex'), 'installed')):
            with self.subTest(selection=selection):
                result = self.install(*selection, '--quiet', '--hermes-home', str(profile), env=env)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("WARNING: Hermes was not updated. The installer's python3 could not load PyYAML",
                              result.stdout)
                self.assertIn("python3 -c 'import yaml'", result.stdout)
                self.assertIn(f"./install.sh --only hermes '--hermes-home={profile}'\n", result.stdout)
                self.assertNotIn('pip install --user', result.stdout)
                self.assertRegex(result.stdout, r'hermes\s+failed')
                rows = {row['item']: row for row in map(json.loads, report.read_text().splitlines())}
                self.assertEqual(rows['hermes'], {'item': 'hermes', 'status': 'failed', 'exit': 1})
                self.assertEqual(rows['tx']['status'], tx_status)
                self.assertEqual(manifest.read_text(), 'name: kit\n')
                self.assertEqual(set(plugin.iterdir()), {manifest, plugin / '.git'})
                self.assertEqual(self.calls('hermes'), [])

        # An installed reader with a broken import must not get the missing-module warning.
        (imports / 'sitecustomize.py').unlink()
        (imports / 'yaml.py').write_text('raise ImportError("fixture broken reader")\n')
        broken = self.install('--only', 'hermes', '--quiet', '--hermes-home', str(profile), env=env)
        self.assertEqual(broken.returncode, 1, broken.stdout + broken.stderr)
        self.assertIn('Cannot load plugin identity reader', broken.stdout)
        self.assertNotIn('could not load PyYAML', broken.stdout)
        self.assertNotIn('fixture broken reader', broken.stdout + broken.stderr)

        manifest.write_text('name: [invalid\n')
        invalid = self.install('--only', 'hermes', '--quiet', '--hermes-home', str(profile))
        self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
        self.assertIn('Invalid plugin manifest', invalid.stdout)
        self.assertNotIn('could not load PyYAML', invalid.stdout)

    def test_setup_only_hermes_options_are_refused_for_profile_clones(self):
        self.fake('hermes', LOGGING)
        clone = self.home / '.hermes/profiles/work/plugins/kit'
        (clone / '.git').mkdir(parents=True)
        (clone / 'plugin.yaml').write_text('name: kit\n')
        for flag in ('--no-reload', '--bundle-only', '--yes-deps'):
            with self.subTest(flag=flag):
                result = self.install('--only', 'hermes,tx', flag)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertRegex(result.stdout, rf'hermes\s+failed\s+{flag} cannot apply')
                self.assertNotIn('update_bundle.py --hermes-home', self.calls())
                self.assertRegex(result.stdout, r'tx\s+installed')

    def test_hermes_without_a_home_is_unavailable_not_a_failed_setup(self):
        self.fake('hermes', LOGGING)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'hermes\s+skipped\s+no Hermes home at .*\.hermes')
        self.assertRegex(self.install('--list').stdout, r'hermes\s+unavailable.*no Hermes home')
        result = self.install('--only', 'hermes')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, r'hermes\s+failed\s+no Hermes home')
        self.assertEqual(self.calls('hermes'), [])

class PullCheckoutTests(unittest.TestCase):
    """install.sh first fast-forwards its own checkout (owner request 2026-10-21)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.origin, self.clone, self.other = base / 'origin.git', base / "clone with 'quote", base / 'other'
        run = lambda *a, cwd=None: subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True, timeout=10)
        run('git', 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        for repo in (self.clone, self.other):
            run('git', 'clone', '-q', str(self.origin), str(repo))
            run('git', '-C', str(repo), 'config', 'user.email', 'o@example.invalid')
            run('git', '-C', str(repo), 'config', 'user.name', 'O')
        (self.other / 'f').write_text('1')
        (self.other / 'g').write_text('base\n')
        (self.other / '.gitignore').write_text('ignored\n')
        run('git', '-C', str(self.other), 'add', '-A')
        run('git', '-C', str(self.other), 'commit', '-qm', 'one')
        run('git', '-C', str(self.other), 'push', '-q', 'origin', 'main')
        run('git', '-C', str(self.clone), 'pull', '-q')
        (self.other / 'f').write_text('2')
        run('git', '-C', str(self.other), 'commit', '-qam', 'two')
        run('git', '-C', str(self.other), 'push', '-q', 'origin', 'main')
        self.run_git = run

    def head(self, repo):
        return self.run_git('git', '-C', str(repo), 'rev-parse', 'HEAD').stdout

    def test_source_linked_codex_pull_restarts_once_for_both_entrypoints(self):
        # The supported local marketplace consumes this very checkout. Pull must
        # not erase its installed baseline, even when the installer re-executes.
        self.clone = Path(self.tmp.name) / 'source'
        self.run_git('git', 'clone', '-q', str(self.origin), str(self.clone))
        scripts = self.other / 'scripts'
        scripts.mkdir()
        shutil.copy2(ROOT / 'scripts/install_menu.py', scripts / 'install_menu.py')
        shutil.copy2(INSTALL, self.other / 'install.sh')
        manifest = self.other / '.agents/plugins/marketplace.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'name': 'kit-marketplace', 'plugins': [{'name': 'kit'}]}))
        (self.other / 'SKILL.md').write_text('old payload')
        self.run_git('git', '-C', str(self.other), 'add', '.')
        self.run_git('git', '-C', str(self.other), 'commit', '-qm', 'installed source')
        self.run_git('git', '-C', str(self.other), 'push', '-q')
        self.git('pull', '--ff-only')
        base = Path(self.tmp.name)
        home, binary = base / 'home', base / 'bin'
        home.mkdir()
        binary.mkdir()
        log, report = base / 'calls', base / 'report.jsonl'
        source = {'sourceType': 'local', 'source': str(self.clone)}
        marketplace = {'name': 'kit-marketplace', 'root': str(self.clone), 'marketplaceSource': source}
        plugin = {'pluginId': 'kit@kit-marketplace', 'name': 'kit', 'marketplaceName': 'kit-marketplace',
                  'installed': True, 'enabled': True, 'source': {'source': 'local', 'path': str(self.clone)},
                  'marketplaceSource': source}
        codex = binary / 'codex'
        codex.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                         'with open(os.environ["CALLS"], "a") as f: f.write("codex " + " ".join(sys.argv[1:]) + "\\n")\n'
                         'if sys.argv[1:] == ["plugin", "marketplace", "list", "--json"]: print(' +
                         repr(json.dumps({'marketplaces': [marketplace]})) + ')\n'
                         'elif sys.argv[1:3] == ["plugin", "list"]: print(' +
                         repr(json.dumps({'available': [], 'installed': [plugin]})) + ')\n')
        codex.chmod(0o755)
        ctl = binary / 'systemctl'
        ctl.write_text('#!/usr/bin/env python3\nimport os, sys\n'
                       'with open(os.environ["CALLS"], "a") as f: f.write("systemctl " + " ".join(sys.argv[1:]) + "\\n")\n'
                       'if "list-units" in sys.argv: print("kit-codex.service loaded active running Codex")\n'
                       'elif "show" in sys.argv: print(' + repr(f'ExecStart={{ path=/usr/bin/codex ; argv[]=/usr/bin/codex --plugin {self.clone}/SKILL.md ; }}') + ')\n')
        ctl.chmod(0o755)
        env = {'PATH': str(binary) + os.pathsep + os.environ['PATH'], 'HOME': str(home),
               'KIT_BIN_DIR': str(binary), 'CALLS': str(log), 'KIT_INSTALL_REPORT': str(report)}
        for command in ([], ['update']):
            with self.subTest(command=command):
                before_head = self.head(self.clone).strip()
                (self.other / 'SKILL.md').write_text('new payload ' + repr(command))
                self.run_git('git', '-C', str(self.other), 'commit', '-qam', 'payload advance')
                self.run_git('git', '-C', str(self.other), 'push', '-q')
                log.write_text('')
                args = ['./install.sh', *command, '--only', 'codex', '--quiet']
                preview = subprocess.run([*args, '--dry-run'], cwd=self.clone, env=env,
                                         capture_output=True, text=True, timeout=30)
                self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
                self.assertEqual(log.read_text(), '')
                self.assertEqual(self.head(self.clone).strip(), before_head)
                for expected in ('changed', 'unchanged'):
                    result = subprocess.run(args, cwd=self.clone, env=env, capture_output=True,
                                            text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
                    self.assertEqual(rows['codex']['change'], expected, result.stdout)
                    evidence = rows['codex']['evidence']
                    if expected == 'changed':
                        self.assertNotEqual(evidence['before']['inputs'], evidence['after']['inputs'])
                    else:
                        self.assertEqual(evidence['before']['inputs'], evidence['after']['inputs'])
                self.assertEqual((self.clone / 'SKILL.md').read_text(), (self.other / 'SKILL.md').read_text())
                self.assertEqual(log.read_text().splitlines().count('systemctl --user try-restart kit-codex.service'), 1)
                self.assertEqual(log.read_text().splitlines().count('codex plugin marketplace list --json'), 6)
                self.assertEqual(self.git('status', '--porcelain'), '')
                # Stash-only source repair must also retain the consumed dirty bytes.
                log.write_text('')
                (self.clone / 'SKILL.md').write_text('local damaged content')
                for expected in ('changed', 'unchanged'):
                    repaired = subprocess.run(args, cwd=self.clone, env=env, capture_output=True,
                                              text=True, timeout=30)
                    self.assertEqual(repaired.returncode, 0, repaired.stdout + repaired.stderr)
                    rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
                    self.assertEqual(rows['codex']['change'], expected, repaired.stdout)
                self.assertEqual(log.read_text().splitlines().count('systemctl --user try-restart kit-codex.service'), 1)
                self.assertTrue(self.stashes())
                self.assertEqual(self.git('status', '--porcelain'), '')

    def test_a_clean_checkout_behind_its_upstream_is_fast_forwarded(self):
        said, commands = [], []
        def run(args, **kwargs):
            commands.append(args[3:])
            return subprocess.run(args, **kwargs)
        self.assertTrue(install_menu.pull_checkout(self.clone, write=said.append, run=run))
        self.assertEqual(self.head(self.clone), self.head(self.other))
        self.assertIn('Updated this checkout', said[0])
        (self.clone / 'ignored').write_text('do not stash')
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append, run=run))
        self.assertEqual(len(said), 1)
        self.assertEqual(sum(cmd[0] == 'pull' for cmd in commands), 2)
        self.assertFalse(any(cmd[:2] == ['stash', 'push'] for cmd in commands))
        self.assertEqual(self.stashes(), [])
        self.assertEqual((self.clone / 'ignored').read_text(), 'do not stash')

    def git(self, *args):
        return self.run_git('git', '-C', str(self.clone), *args).stdout.strip()

    def dirty(self):
        (self.clone / 'g').write_text('staged\n')
        self.git('add', 'g')
        (self.clone / 'g').write_text('staged\nunstaged\n')
        (self.clone / 'untracked').write_text('saved\n')
        (self.clone / 'ignored').write_text('kept\n')

    def stashes(self):
        return self.git('stash', 'list', '--format=%H').splitlines()

    def test_local_changes_are_kept_in_an_object_addressed_stash(self):
        (self.clone / 'older').write_text('old')
        self.git('stash', 'push', '--include-untracked', '-m', 'older')
        older = self.stashes()
        self.git('config', 'rebase.autoStash', 'true')
        self.git('config', 'merge.autoStash', 'true')
        self.dirty()
        said = []
        self.assertTrue(install_menu.pull_checkout(self.clone, write=said.append))
        saved, *rest = self.stashes()
        self.assertEqual(rest, older)
        self.assertIn('Kit installer', self.git('log', '-1', '--format=%s', saved))
        self.assertEqual(self.head(self.clone), self.head(self.other))
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual((self.clone / 'g').read_text(), 'base\n')
        self.assertFalse((self.clone / 'untracked').exists())
        self.assertEqual((self.clone / 'ignored').read_text(), 'kept\n')
        self.assertIn(saved, '\n'.join(said))
        restore = next(line for line in said if ' stash apply --index ' in line)
        self.assertEqual(shlex.split(restore), ['git', '-C', str(self.clone),
                                             'stash', 'apply', '--index', saved])
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertEqual(self.stashes(), [saved, *older])  # no empty stash on repeat
        (self.clone / 'newer').write_text('new')
        self.git('stash', 'push', '--include-untracked', '-m', 'newer')
        entries = self.stashes()
        self.run_git(*shlex.split(restore))
        self.assertEqual(self.git('show', ':g'), 'staged')
        self.assertEqual((self.clone / 'g').read_text(), 'staged\nunstaged\n')
        self.assertEqual((self.clone / 'untracked').read_text(), 'saved\n')
        self.assertEqual(self.stashes(), entries)  # apply did not remove any stash

    def test_stashing_requires_reexec_even_when_head_is_current(self):
        self.git('pull', '--ff-only')
        before = self.head(self.clone)
        for count, kind in enumerate(('untracked', 'staged', 'unstaged'), 1):
            with self.subTest(kind=kind):
                (self.clone / ('untracked' if kind == 'untracked' else 'g')).write_text(kind)
                if kind == 'staged':
                    self.git('add', 'g')
                self.assertTrue(install_menu.pull_checkout(self.clone, write=lambda _: None))
                self.assertEqual(self.head(self.clone), before)
                self.assertEqual(len(self.stashes()), count)

    def test_missing_upstream_aborts_before_stashing(self):
        self.dirty()
        self.git('branch', '--unset-upstream')
        for state in ('local-only', 'missing-ref', 'detached'):
            with self.subTest(state=state):
                if state == 'missing-ref':
                    self.git('branch', '--set-upstream-to=origin/main')
                    self.git('update-ref', '-d', 'refs/remotes/origin/main')
                if state == 'detached':
                    self.git('checkout', '--detach')
                with self.assertRaisesRegex(RuntimeError, 'upstream'):
                    install_menu.pull_checkout(self.clone)
                self.assertEqual(self.stashes(), [])
                self.assertEqual((self.clone / 'g').read_text(), 'staged\nunstaged\n')

    def test_unpacked_release_does_not_discover_a_parent_repository(self):
        unpacked = self.clone / 'release'
        unpacked.mkdir()
        before = self.head(self.clone)
        self.assertFalse(install_menu.pull_checkout(unpacked))
        self.assertEqual(self.head(self.clone), before)
        self.assertEqual(self.stashes(), [])
        (unpacked / '.git').write_text('gitdir: missing\n')
        with self.assertRaisesRegex(RuntimeError, 'git'):
            install_menu.pull_checkout(unpacked)

    def test_failures_abort_before_components_and_services(self):
        real_run = subprocess.run
        original_pull_checkout = install_menu.pull_checkout
        for failure in ('status', 'stash', 'empty-stash', 'stash-cleanup', 'still-dirty', 'pull'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / 'repo'
                self.run_git('git', 'clone', '-q', str(self.origin), str(repo))
                self.run_git('git', '-C', str(repo), 'config', 'user.email', 'o@example.invalid')
                self.run_git('git', '-C', str(repo), 'config', 'user.name', 'O')
                (repo / 'untracked').write_text('save me')
                stashed = False
                def run(args, **kwargs):
                    nonlocal stashed
                    operation = args[3]
                    if ((operation == failure and operation != 'stash') or
                            (operation == 'stash' and args[4] == 'push' and failure in ('stash', 'empty-stash')) or
                            (operation == 'status' and stashed and failure == 'still-dirty')):
                        code = 0 if failure in ('empty-stash', 'still-dirty') else 1
                        return subprocess.CompletedProcess(args, code, '?? remains' if code == 0 else '',
                                                           'fixture ' + failure)
                    result = real_run(args, **kwargs)
                    if operation == 'stash' and args[4] == 'push':
                        stashed = True
                        if failure == 'stash-cleanup':
                            return subprocess.CompletedProcess(args, 1, '', 'fixture cleanup failure')
                    return result
                env = {k: v for k, v in os.environ.items()
                       if k not in ('KIT_INSTALL_NO_PULL', 'KIT_INSTALL_PULLED')}
                with patch.dict(os.environ, env, clear=True), patch.object(install_menu, 'ROOT', repo), \
                        patch.object(install_menu, 'BIN', Path(tmp) / 'bin'), \
                        patch.object(install_menu, 'pull_checkout',
                                     side_effect=lambda *a, **kw: original_pull_checkout(*a, run=run, **kw)), \
                        patch.object(install_menu, 'items') as components, \
                        patch.object(install_menu, 'restart_services') as restart:
                    self.assertEqual(install_menu.main(['--quiet']), 1)
                    components.assert_not_called()
                    restart.assert_not_called()
                saved = self.run_git('git', '-C', str(repo), 'stash', 'list', '--format=%H').stdout.splitlines()
                self.assertEqual(len(saved), int(failure in ('pull', 'stash-cleanup', 'still-dirty')))

    def test_diverged_history_keeps_stash_and_refuses_install(self):
        self.git('config', 'pull.rebase', 'true')  # --ff-only must still refuse rewriting commits
        (self.clone / 'local-commit').write_text('local')
        self.git('add', 'local-commit')
        self.git('commit', '-qm', 'local commit')
        before = self.head(self.clone)
        self.dirty()
        said = []
        with self.assertRaisesRegex(RuntimeError, 'pull'):
            install_menu.pull_checkout(self.clone, write=said.append)
        self.assertEqual(self.head(self.clone), before)
        saved, = self.stashes()
        self.assertIn(saved, '\n'.join(said))
        self.assertTrue(any('stash apply --index' in line for line in said))

    def test_pull_failure_after_stash_reports_recovery(self):
        self.dirty()
        self.git('remote', 'set-url', 'origin', str(self.clone / 'missing-origin'))
        said = []
        with self.assertRaisesRegex(RuntimeError, 'pull'):
            install_menu.pull_checkout(self.clone, write=said.append)
        saved, = self.stashes()
        self.assertIn(saved, '\n'.join(said))
        self.assertEqual(self.git('status', '--porcelain'), '')

    def installer_fixture(self):
        """Real shell/Python entry point and dispatcher; only components/services are fake."""
        scripts = self.other / 'scripts'
        scripts.mkdir()
        source = (ROOT / 'scripts/install_menu.py').read_text()
        fixture = r'''FIXTURE_VERSION = 'clean-v1'
def fixture_trace(event):
    with open(os.environ['FIXTURE_TRACE'], 'a') as stream:
        stream.write(json.dumps([event, FIXTURE_VERSION, sys.argv[1:],
                                 os.environ.get('KIT_INSTALL_PULLED', '')]) + '\n')
fixture_trace('load')
if os.environ.get('KIT_INSTALL_PULLED'):
    # Probe before main can reacquire a lock on the new revision.
    lock_path = BIN.with_name(BIN.name + '.kit-install.lock')
    with lock_path.open() as probe:
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise AssertionError('installer lock was not held across re-exec')
def fixture_component():
    fixture_trace('component')
    return 'fixture installed'
def installed_baseline(*args, **kwargs):
    return {}  # never query real host CLIs from this fixture
def items(*args, **kwargs):
    return [Item('tx', 'fixture', steps=[Step('fixture component', run=fixture_component)])]
def restart_services(output, observations=None):
    fixture_trace('restart')
    return 'fixture restarted'

'''
        (scripts / 'install_menu.py').write_text(source.replace("if __name__ == '__main__':",
                                                              fixture + "if __name__ == '__main__':"))
        shutil.copy2(INSTALL, self.other / 'install.sh')
        self.run_git('git', '-C', str(self.other), 'add', '.')
        self.run_git('git', '-C', str(self.other), 'commit', '-qm', 'installer fixture')
        self.run_git('git', '-C', str(self.other), 'push', '-q')
        self.git('pull', '--ff-only')
        base = Path(self.tmp.name)
        self.trace = base / 'trace.jsonl'
        self.entry_env = {'PATH': os.environ['PATH'], 'HOME': str(base / 'home'),
                          'KIT_BIN_DIR': str(base / 'bin'), 'FIXTURE_TRACE': str(self.trace),
                          'LANG': 'C.UTF-8',
                          # Identical edits can produce the same stash object within one second.
                          'GIT_AUTHOR_DATE': '2000-01-01T00:00:00+00:00',
                          'GIT_COMMITTER_DATE': '2000-01-01T00:00:00+00:00'}

    def entry(self, *args, env=None):
        return subprocess.run(['./install.sh', *args], cwd=self.clone, capture_output=True,
                              text=True, timeout=20, env={**self.entry_env, **(env or {})})

    def events(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()]

    def test_held_installer_lock_refuses_before_stashing_or_pulling(self):
        self.installer_fixture()
        self.dirty()
        (self.other / 'f').write_text('upstream advanced')
        self.run_git('git', '-C', str(self.other), 'commit', '-qam', 'advance')
        self.run_git('git', '-C', str(self.other), 'push', '-q')
        before = (self.head(self.clone), self.stashes(), self.git('status', '--porcelain'))
        lock_path = Path(self.entry_env['KIT_BIN_DIR']).with_name('bin.kit-install.lock').resolve()
        with lock_path.open('a+') as lock:
            inode = lock_path.stat().st_ino
            lock.write(f'{os.getpid()}\n')
            lock.flush()
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.entry()
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f'installer lock {lock_path} held by PID {os.getpid()}', result.stdout)
            self.assertEqual((self.head(self.clone), self.stashes(), self.git('status', '--porcelain')),
                             before, result.stdout)
            self.assertIn('let the holder finish, then retry; do not remove the lock file', result.stdout)
            self.assertEqual([event[0] for event in self.events()], ['load'])
        self.trace.write_text('')
        result = self.entry()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.head(self.clone), self.head(self.other))
        self.assertEqual(len(self.stashes()), 1)
        self.assertEqual(lock_path.stat().st_ino, inode)
        self.assertEqual([event[0] for event in self.events()], ['load', 'load', 'component', 'restart'])

    def test_checkout_preparation_does_not_stash_its_own_lock(self):
        self.installer_fixture()
        self.dirty()
        env = {'KIT_BIN_DIR': str(self.clone / 'bin')}
        lock_path = self.clone.resolve() / 'bin.kit-install.lock'
        before = (self.head(self.clone), self.stashes(), self.git('status', '--porcelain'))

        result = self.entry(env=env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f'installer lock {lock_path} is inside the Git checkout', result.stdout)
        self.assertIn('--no-pull', result.stdout)
        self.assertFalse(lock_path.exists())
        self.assertEqual((self.head(self.clone), self.stashes(), self.git('status', '--porcelain')), before)

        result = self.entry('--no-pull', env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.head(self.clone), self.stashes()), before[:2])
        with lock_path.open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            inode, metadata = lock_path.stat().st_ino, f'{os.getpid()}\n'
            lock.write(metadata)
            lock.truncate()
            lock.flush()
            result = self.entry(env=env)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f'installer lock {lock_path} held by PID {os.getpid()}', result.stdout)
        result = self.entry(env=env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('--no-pull', result.stdout)
        self.assertEqual((lock_path.stat().st_ino, lock_path.read_text()), (inode, metadata))
        self.assertEqual((self.head(self.clone), self.stashes()), before[:2])

    def test_unknown_item_refuses_before_stashing_or_pulling(self):
        self.installer_fixture()
        self.dirty()
        (self.other / 'f').write_text('upstream advanced')
        self.run_git('git', '-C', str(self.other), 'commit', '-qam', 'advance')
        self.run_git('git', '-C', str(self.other), 'push', '-q')
        before = (self.head(self.clone), self.stashes(), self.git('status', '--porcelain'))
        for flag in ('--only', '--skip'):
            with self.subTest(flag=flag):
                result = self.entry(flag, 'nope')
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('unknown item(s): nope', result.stderr)
                self.assertEqual((self.head(self.clone), self.stashes(), self.git('status', '--porcelain')),
                                 before, result.stdout)

    def test_entrypoint_runs_clean_disk_code_once_after_stashing(self):
        self.installer_fixture()
        for advanced in (False, True):
            with self.subTest(advanced=advanced):
                script = self.clone / 'scripts/install_menu.py'
                script.write_text(script.read_text().replace("FIXTURE_VERSION = 'clean-v1'",
                                                            "FIXTURE_VERSION = 'dirty'"))
                if advanced:
                    upstream_script = self.other / 'scripts/install_menu.py'
                    upstream_script.write_text(upstream_script.read_text().replace('clean-v1', 'clean-v2'))
                    self.run_git('git', '-C', str(self.other), 'commit', '-qam', 'new installer')
                    self.run_git('git', '-C', str(self.other), 'push', '-q')
                args = ['update', '--only', 'tx', '--quiet']
                result = self.entry(*args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                clean = 'clean-v2' if advanced else 'clean-v1'
                self.assertEqual(self.events(), [['load', 'dirty', args, ''],
                                                ['load', clean, args, '1'],
                                                ['component', clean, args, '1'],
                                                ['restart', clean, args, '1']])
                saved = self.stashes()
                self.assertEqual(len(saved), 2 if advanced else 1)
                self.assertIn(saved[0], result.stdout)
                self.assertIn('stash apply --index', result.stdout)
                self.assertEqual(self.git('status', '--porcelain'), '')
                self.trace.write_text('')
                result = self.entry(*args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.events(), [[event, clean, args, '']
                                                for event in ('load', 'component', 'restart')])
                self.assertEqual(self.stashes(), saved)
                self.trace.write_text('')

    def test_entrypoint_bypasses_and_previews_leave_checkout_and_stashes_unchanged(self):
        self.installer_fixture()
        (self.clone / 'older').write_text('older')
        self.git('stash', 'push', '-u', '-m', 'older')
        self.dirty()
        (self.other / 'f').write_text('upstream advanced')
        self.run_git('git', '-C', str(self.other), 'commit', '-qam', 'advance')
        self.run_git('git', '-C', str(self.other), 'push', '-q')
        def state():
            return (self.head(self.clone), self.git('status', '--porcelain'),
                    self.git('diff'), self.git('diff', '--cached'), self.stashes(),
                    (self.clone / 'untracked').read_text())
        before = state()
        for args, env in ((['--help'], {}), (['--list'], {}), (['--dry-run', '--only', 'tx'], {}),
                          (['--no-pull', '--only', 'tx'], {}),
                          (['--only', 'tx'], {'KIT_INSTALL_NO_PULL': '1'})):
            with self.subTest(args=args, env=env):
                result = self.entry(*args, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(state(), before)
                if args[0] in ('--help', '--list', '--dry-run'):
                    self.assertEqual([event[0] for event in self.events()], ['load'])
                self.trace.write_text('')

    def test_entrypoint_refuses_foreign_git_environment_before_mutation(self):
        self.installer_fixture()
        self.dirty()
        def state():
            return [(self.head(repo),
                     *[self.run_git('git', '-C', str(repo), *args).stdout for args in
                       (('status', '--porcelain'), ('diff',), ('diff', '--cached'),
                        ('stash', 'list', '--format=%H'))])
                    for repo in (self.clone, self.other)]
        before = state()
        for name, value in (('GIT_DIR', self.other / '.git'),
                            ('GIT_INDEX_FILE', self.other / '.git/index')):
            with self.subTest(name=name):
                # With GIT_DIR alone, even --show-toplevel reports the requested
                # -C directory, despite reading another repository's HEAD/index.
                if name == 'GIT_DIR':
                    result = subprocess.run(['git', '-C', str(self.clone), 'rev-parse', '--show-toplevel'],
                                            env={**self.entry_env, name: str(value)},
                                            capture_output=True, text=True, check=True, timeout=10)
                    self.assertEqual(Path(result.stdout.strip()), self.clone)
                result = self.entry('--quiet', env={name: str(value)})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('unset ' + name, result.stdout)
                self.assertIn('Nothing installed or restarted', result.stdout)
                self.assertEqual([event[0] for event in self.events()], ['load'])
                self.assertEqual(state(), before)
                self.assertEqual((self.clone / 'g').read_text(), 'staged\nunstaged\n')
                self.assertEqual((self.clone / 'untracked').read_text(), 'saved\n')
                self.trace.write_text('')

    def test_entrypoint_divergence_stops_before_component_and_restart(self):
        self.installer_fixture()
        (self.clone / 'local').write_text('local')
        self.git('add', 'local')
        self.git('commit', '-qm', 'local')
        (self.other / 'f').write_text('upstream')
        self.run_git('git', '-C', str(self.other), 'commit', '-qam', 'diverge')
        self.run_git('git', '-C', str(self.other), 'push', '-q')
        self.dirty()
        args = ['--only', 'tx', '--quiet']
        result = self.entry(*args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.events(), [['load', 'clean-v1', args, '']])
        saved, = self.stashes()
        self.assertIn(saved, result.stdout)
        self.assertIn('FAILED: checkout preparation: git pull', result.stdout)
        self.assertIn('Nothing installed or restarted', result.stdout)
        self.assertIn('Resolve the Git error and retry', result.stdout)
        self.assertIn('stash apply --index', result.stdout)


if __name__ == '__main__':
    unittest.main()
