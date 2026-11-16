"""install.sh's component menu against fake host CLIs in a throwaway HOME.

The Hermes item runs only as a dry run here: the real setup changes live profiles.
"""
import json
import os
import pty
import shutil
import signal
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

# A fake pi: `pi list` reads installed sources from a file; install, update and remove edit it,
# and install and update materialise the skill folders the checkout under test ships.
PI = r'''#!/usr/bin/env bash
echo "pi $*" >> "$FAKE_LOG"
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
  --version) echo 0.72.0 ;;
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


class InstallMenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.project = self.home / 'project'
        self.project.mkdir()
        self.bin = self.home / 'fakebin'
        self.bin.mkdir()
        self.log = self.home / 'calls.log'
        self.log.touch()
        self.fake('pi', PI)
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
printf '#!/bin/sh\ncase "${1:-}" in --version) echo 1.4.0 ;; *) echo "pi-bolt $*" >> "$FAKE_LOG" ;; esac\n' > "$PIBOLT_BIN_DIR/pi-bolt"
chmod 755 "$PIBOLT_BIN_DIR/pi-bolt"
''')
        self.fake('curl', '''#!/usr/bin/env python3
import os, pathlib, shutil, stat, sys
args = sys.argv[1:]
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write('curl ' + ' '.join(args) + '\\n')
if args[-1] not in ('https://pi-bolt.opensec.in/install.sh', 'https://pi.dev/install.sh'):
    raise SystemExit('unexpected network request')
dest = pathlib.Path(args[args.index('--output') + 1])
assert stat.S_IMODE(dest.parent.stat().st_mode) == 0o700
assert stat.S_IMODE(dest.stat().st_mode) == 0o600
if args[-1] == 'https://pi.dev/install.sh':
    if os.environ.get('PI_FIXTURE_STAGE') == 'download':
        print('curl: (22) HTTP 503', file=sys.stderr)
        dest.write_text('exit 98')  # a failed response must never execute
        raise SystemExit(22)
    shutil.copyfile(pathlib.Path(os.environ['FAKE_HOME']) / 'upstream-pi-install.sh', dest)
    if os.environ.get('PI_FIXTURE_STAGE') == 'download-empty':
        dest.write_bytes(b'')
else:
    shutil.copyfile(pathlib.Path(os.environ['FAKE_HOME']) / 'upstream-pi-bolt-install.sh', dest)
if os.environ.get('PI_BOLT_FIXTURE_STAGE') == 'download-empty':
    dest.write_bytes(b'')
''')
        self.fake('systemctl', LOGGING)
        self.claude_host()
        self.codex_registry()
        self.env = {'PATH': f'{self.bin}:/usr/bin:/bin', 'HOME': str(self.home), 'FAKE_LOG': str(self.log),
                    'FAKE_HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config'),
                    'PI_AUTOWORK_SYSTEMCTL': str(self.bin / 'systemctl'), 'LANG': 'C.UTF-8',
                    'FAKE_KIT_CHECKOUT': str(ROOT),
                    'TMPDIR': str(self.home), 'AUTOWORK_INSTALL_NO_PULL': '1'}  # never pull the checkout under test
        # In-process installer tests must also never discover the real host fleet.
        self.environment = patch.dict(os.environ, self.env)
        self.environment.start()
        self.addCleanup(self.environment.stop)

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
        (self.home / 'pi-installed').write_text(NEW + '\n')  # what the fake `pi list` reports
        return package

    def missing_pi(self):
        (self.bin / 'pi').unlink()
        (self.home / 'pi-fixture').write_text(PI)
        (self.home / 'upstream-pi-install.sh').write_text(r'''#!/bin/sh
set -eu
echo "pi-installer $#" >> "$FAKE_LOG"
# Official installer gates agent startup on stdout being a terminal.
if [ -t 1 ]; then echo 'agent would start' >&2; exit 97; fi
case "${PI_FIXTURE_STAGE:-}" in
  bootstrap) echo 'npm registry unavailable' >&2; exit 9 ;;
  native-prerequisite)
    exec 3<>/dev/tty
    printf 'Pi needs Node.js 22.19.0 or newer and npm. Install them now? [Y/n] ' >&3
    read -r answer <&3
    echo "native-prerequisite-answer $answer" >> "$FAKE_LOG"
    echo 'Install Node.js 22.19.0 or newer and npm, then run this installer again.'
    exit 1 ;;
  refusal) printf 'Install Node.js 22.19.0 or newer and npm? [Y/n] '
    read -r answer || answer=n
    echo "prerequisite-answer $answer" >> "$FAKE_LOG"
    echo 'Install Node.js 22.19.0 or newer and npm, then run this installer again.'
    exit 1 ;;
  probe-missing) exit 0 ;;
esac
agent=${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}
if [ -n "${PI_MANAGED_INSTALL_ROOT:-}" ]; then agent=${PI_MANAGED_INSTALL_ROOT%/*}; fi
mkdir -p "$agent/bin"
cp "$FAKE_HOME/pi-fixture" "$agent/bin/pi"
chmod 755 "$agent/bin/pi"
case "${PI_FIXTURE_STAGE:-}" in
  probe-nonexec) chmod 644 "$agent/bin/pi" ;;
  probe-version) printf '#!/bin/sh\necho wrong-tool\n' > "$agent/bin/pi" ;;
  probe-exit) printf '#!/bin/sh\necho "node: not found" >&2; exit 127\n' > "$agent/bin/pi" ;;
esac
''')

    def claude_host(self, installed=(), mutation=''):
        (self.home / 'claude-installed.json').write_text(json.dumps(installed))
        self.fake('claude', LOGGING + '''
if [[ "$*" == "plugin list --json" ]]; then
  cat "$FAKE_HOME/claude-installed.json"
else
  :
''' + mutation + '\nfi\n')

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
''' + mutation + '\nfi\n')

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

    def test_marketplace_fresh_and_canonical_traces(self):
        for canonical in (False, True):
            with self.subTest(canonical=canonical):
                self.log.write_text('')
                self.codex_registry([self.marketplace('kit-marketplace')] if canonical else [])
                self.claude_registry(['kit'] if canonical else [])
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

    def test_legacy_and_coexisting_registrations_refuse_without_mutation(self):
        for both in (False, True):
            with self.subTest(both=both):
                self.log.write_text('')
                self.claude_registry(['autowork', 'kit'] if both else ['autowork'])
                names = ['autowork-marketplace', 'kit-marketplace'] if both else ['autowork-marketplace']
                self.codex_registry([self.marketplace(n) for n in names])
                before = (self.home / '.claude/plugins/known_marketplaces.json').read_bytes()
                result = self.install('--only', 'claude,codex,tx', '--quiet')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('manual migration required', result.stdout)
                self.assertRegex(result.stdout, r'tx\s+installed')
                self.assertFalse(any(any(' '+verb+' ' in c for verb in
                                     ('add', 'install', 'remove', 'uninstall', 'update', 'upgrade'))
                                     for c in self.calls() if c.startswith(('claude ', 'codex '))))
                self.assertEqual((self.home / '.claude/plugins/known_marketplaces.json').read_bytes(), before)

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
                    'claude plugin marketplace update kit', f'claude plugin update kit@kit --scope {scope}'])
                self.assertEqual(self.calls('codex'), ['codex plugin marketplace list --json',
                    'codex plugin list --marketplace autowork-marketplace --json',
                    'codex plugin list --marketplace kit-marketplace --json',
                    'codex plugin marketplace upgrade kit-marketplace'])
                self.assertEqual({p: p.read_bytes() for p in snapshot}, snapshot)

    def test_claude_settings_scope_selection_and_legacy_installed_identity(self):
        self.claude_registry(['kit'])
        settings = self.project / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text(json.dumps({'enabledPlugins': {'kit@kit': True, 'other@elsewhere': False}}))
        before = settings.read_bytes()
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('claude plugin install kit@kit --scope project', self.calls('claude'))
        self.assertEqual(settings.read_bytes(), before)
        self.claude_host([{'id': 'kit@autowork', 'scope': 'user', 'enabled': False}])
        self.log.write_text('')
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('legacy installed kit@autowork', result.stdout)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json'])

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

    def test_claude_project_legacy_settings_and_malformed_installed_list_hold(self):
        path = self.project / '.claude/settings.local.json'
        path.parent.mkdir()
        path.write_text(json.dumps({'extraKnownMarketplaces': {'autowork': {
            'source': {'source': 'directory', 'path': '/gone'}}},
            'enabledPlugins': {'other@elsewhere': True}}))
        before = path.read_bytes()
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), [])
        self.assertEqual(path.read_bytes(), before)
        path.unlink()
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

    def test_codex_local_source_reused_and_legacy_installed_without_registry_holds(self):
        canonical = self.marketplace('kit-marketplace')
        canonical.update(root=str(ROOT), marketplaceSource={'sourceType': 'local', 'source': str(ROOT)})
        self.codex_registry([canonical])
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('codex')[-1], 'codex plugin add kit@kit-marketplace')
        self.assertFalse(self.calls('codex plugin marketplace upgrade'))
        self.assertFalse(self.calls('codex plugin marketplace add'))
        legacy = self.marketplace('autowork-marketplace')
        self.codex_registry([], {'autowork-marketplace': {'installed': [{
            'pluginId': 'kit@autowork-marketplace', 'name': 'kit',
            'marketplaceName': 'autowork-marketplace', 'installed': True, 'enabled': False,
            'source': {'source': 'local', 'path': legacy['root']},
            'marketplaceSource': legacy['marketplaceSource']}], 'available': []}})
        self.log.write_text('')
        result = self.install('--only', 'codex')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(all(' list ' in call for call in self.calls('codex')))

    def test_legacy_claude_refusal_does_not_stop_later_codex_install(self):
        self.claude_registry(['autowork'])
        result = self.install('--only', 'claude,codex', '--quiet')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'claude\s+failed.*manual migration required')
        self.assertRegex(result.stdout, r'codex\s+installed')
        self.assertEqual(self.calls('claude'), [])
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))

    def test_marketplace_dry_run_is_not_checked_and_invokes_no_hosts(self):
        self.claude_registry(['autowork', 'kit'])
        self.codex_registry([self.marketplace('autowork-marketplace')])
        before = {p: p.read_bytes() for p in self.home.rglob('*.json')}
        self.log.write_text('')
        result = self.install('--only', 'claude,codex', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NOT_CHECKED', result.stdout)
        self.assertIn('codex plugin marketplace list --json', result.stdout)
        self.assertEqual(self.calls(), [])
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_missing_pi_bootstraps_and_enables_in_one_invocation_then_refreshes(self):
        self.missing_pi()
        settings = self.home / '.pi/agent/settings.json'
        settings.parent.mkdir(parents=True)
        original = {'packages': [{'source': NEW, 'skills': [], 'extensions': []},
                                 {'source': 'npm:other', 'skills': []}], 'model': 'keep-me'}
        settings.write_text(json.dumps(original))
        profile = self.home / '.profile'
        profile.write_text('# keep my profile\n')
        result = self.install('--no-pull', '--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r'pi\s+installed')
        self.assertEqual(self.calls('pi-installer'), ['pi-installer 0'])
        self.assertEqual(self.calls('pi '), ['pi --version', 'pi list', f'pi install {NEW}', 'pi list'])
        curl = self.calls('curl')
        self.assertEqual(len(curl), 1)
        for flag in ('--fail', '--location', '--output', '--proto =https'):
            self.assertIn(flag, curl[0])
        self.assertTrue(curl[0].endswith('https://pi.dev/install.sh'))
        original['packages'][0] = NEW
        self.assertEqual(json.loads(settings.read_text()), original)
        self.log.write_text('')
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # A registered package is never kept: every install refreshes it, so an edited
        # or removed skill cannot stay live behind a complete-looking skill folder set.
        self.assertIn(f'refreshing {self.home / "pkg/kit"}', result.stdout)
        self.assertEqual(self.calls('pi '), ['pi --version', 'pi list', f'pi update {NEW}', 'pi list'])
        self.assertEqual(self.calls('curl'), [])  # a present harness is still not re-downloaded
        self.assertEqual(json.loads(settings.read_text()), original)
        self.assertEqual(profile.read_text(), '# keep my profile\n')
        self.assertFalse(self.calls('systemctl --user try-restart'))
        self.assertFalse(list(self.home.glob('kit-pi-*')))

    def test_off_path_pi_locations_reuse_absolute_executable_and_stale_package_fix(self):
        self.missing_pi()
        package = self.installed_package(only=['plan-with-me'])
        for relative, env in (
            ('.pi/agent/bin/pi', {}), ('.local/bin/pi', {}), ('bin/pi', {}),
            ('custom agent/bin/pi', {'PI_CODING_AGENT_DIR': str(self.home / 'custom agent')}),
            ('managed/bin/pi', {'PI_MANAGED_INSTALL_ROOT': str(self.home / 'managed/install')}),
        ):
            with self.subTest(relative=relative):
                (package / 'adapters/skills/orbi/SKILL.md').unlink(missing_ok=True)
                binary = self.home / relative
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_text(PI)
                binary.chmod(0o755)
                self.log.write_text('')
                result = self.install('--only', 'pi', env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.calls('pi '), ['pi --version', 'pi list', f'pi update {NEW}', 'pi list'])
                self.assertIn('skills missing:', result.stdout)
                self.assertIn(str(binary), result.stdout)
                self.assertFalse(self.calls('curl'))
                self.assertTrue(package.is_dir())
                binary.unlink()

    def test_pi_download_bootstrap_probe_and_prerequisite_failures_are_actionable(self):
        self.missing_pi()
        for stage, cause in (('download', 'HTTP 503'), ('download-empty', 'empty'),
                             ('bootstrap', 'npm registry unavailable'),
                             ('refusal', 'Install Node.js 22.19.0'),
                             ('probe-missing', 'executable'), ('probe-nonexec', 'executable'),
                             ('probe-version', 'wrong-tool'), ('probe-exit', 'node: not found')):
            with self.subTest(stage=stage):
                shutil.rmtree(self.home / '.pi', ignore_errors=True)
                self.log.write_text('')
                result = self.install('--only', 'pi,tx', '--quiet', stdin='n\n',
                                      env={'PI_FIXTURE_STAGE': stage})
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertRegex(result.stdout, r'pi\s+failed')
                self.assertIn(cause, result.stdout)
                self.assertIn('--only pi', result.stdout)
                self.assertRegex(result.stdout, r'tx\s+installed')
                self.assertFalse(self.calls('pi install'))
                self.assertFalse((self.home / '.pi/agent/settings.json').exists())
                if stage.startswith('download'):
                    self.assertFalse(self.calls('pi-installer'))
                if stage == 'refusal':
                    self.assertEqual(self.calls('prerequisite-answer'), ['prerequisite-answer n'])
                self.assertFalse(list(self.home.glob('kit-pi-*')))
                self.assertFalse((self.home / '.profile').exists())

    def test_pi_native_prerequisite_prompt_can_be_refused_through_controlling_terminal(self):
        self.missing_pi()
        pid, master = pty.fork()
        if pid == 0:
            os.execvpe('bash', ['bash', str(INSTALL), '--only', 'pi', '--quiet'],
                       {**self.env, 'PI_FIXTURE_STAGE': 'native-prerequisite'})
        seen, answered, status = b'', False, None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(master, selectors.EVENT_READ)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if selector.select(timeout=0.2):
                        try:
                            chunk = os.read(master, 4096)
                        except OSError:
                            break  # PTY EIO after the child closes stdout.
                        if not chunk:
                            break
                        seen += chunk
                        if b'Install them now? [Y/n]' in seen and not answered:
                            os.write(master, b'n\n')
                            answered = True
                # Never block waiting for a potentially stuck installer.
                while time.monotonic() < deadline:
                    waited, child_status = os.waitpid(pid, os.WNOHANG)
                    if waited:
                        status = child_status
                        break
                    time.sleep(0.01)
            self.assertIsNotNone(status, seen.decode(errors='replace'))
            self.assertEqual(os.waitstatus_to_exitcode(status), 1, seen.decode(errors='replace'))
            self.assertTrue(answered)
            self.assertEqual(self.calls('native-prerequisite-answer'), ['native-prerequisite-answer n'])
            self.assertIn(b'--only pi', seen)
            self.assertFalse(self.calls('pi install'))
            self.assertFalse((self.home / '.pi').exists())
            self.assertFalse((self.home / '.profile').exists())
        finally:
            if status is None:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(master)

    def test_pi_bootstrap_requires_download_tools_and_bounds_the_executable_probe(self):
        with patch.object(install_menu, 'pi_executable', return_value=None):
            for missing in ('curl', 'sh'):
                with self.subTest(missing=missing), patch.object(install_menu.shutil, 'which',
                        side_effect=lambda name: None if name == missing else '/fake/' + name), \
                     patch.object(install_menu, 'run_command') as run:
                    with self.assertRaisesRegex(OSError, f'requires {missing}.*--only pi'):
                        install_menu.install_pi_harness(install_menu.Output(verbosity=0))
                    run.assert_not_called()
        with patch.object(install_menu.subprocess, 'run',
                          side_effect=subprocess.TimeoutExpired('/fake/pi', 30)) as run:
            with self.assertRaisesRegex(OSError, r'probe failed.*timed out.*--only pi'):
                install_menu.pi_version('/fake/pi')
        self.assertEqual(run.call_args.args[0], ['/fake/pi', '--version'])
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
        for stage in ('download', 'bootstrap'):
            def command(argv, output, **kwargs):
                if stage == 'bootstrap' and argv[0] == 'curl':
                    Path(argv[argv.index('--output') + 1]).write_text('exit 0\n')
                    return 0, ''
                return 124, 'command timed out'
            with self.subTest(stage=stage), \
                 patch.object(install_menu, 'pi_executable', return_value=None), \
                 patch.object(install_menu, 'run_command', side_effect=command) as run:
                with self.assertRaisesRegex(OSError, rf'{stage} failed.*timed out.*--only pi'):
                    install_menu.install_pi_harness(output)
                self.assertEqual(run.call_args.kwargs['timeout'], 600)
        with patch.object(install_menu, 'install_pi_harness', return_value='/fake/pi'), \
             patch.object(install_menu, 'pi_package', return_value=None), \
             patch.object(install_menu, 'run_command', return_value=(124, 'command timed out')) as run:
            with self.assertRaisesRegex(OSError, r'package install failed.*timed out.*--only pi'):
                install_menu.install_pi_package(output)
            self.assertEqual(run.call_args.kwargs['timeout'], 600)

    def test_pi_package_failure_after_bootstrap_does_not_enable_or_claim_success(self):
        self.missing_pi()
        (self.home / 'pi-fixture').write_text(PI.replace('  install|update)',
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

    def test_existing_broken_pi_is_not_replaced_or_bootstrapped(self):
        body = LOGGING + 'echo "node: not found" >&2; exit 127\n'
        self.fake('pi', body)
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('node: not found', result.stdout)
        self.assertIn('--only pi', result.stdout)
        self.assertFalse(self.calls('curl'))
        self.assertEqual((self.bin / 'pi').read_text(), body)

    def test_missing_pi_preview_skip_and_menu_do_not_execute_or_write(self):
        self.missing_pi()
        report = self.home / 'preview.jsonl'
        for args, stdin, env in (
            (('--no-pull', '--dry-run', '--only', 'pi'), None, {'AUTOWORK_INSTALL_REPORT': str(report)}),
            (('--list',), None, {}),
            (('--only', 'pi', '--skip', 'pi'), None, {}),
            (('--menu', '--dry-run'), '\n', {'AUTOWORK_INSTALL_UI': 'text'}),
            (('--menu',), 'q\n', {'AUTOWORK_INSTALL_UI': 'text'}),
        ):
            with self.subTest(args=args):
                before = sorted(str(p) for p in self.home.rglob('*'))
                result = self.install(*args, stdin=stdin, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(sorted(str(p) for p in self.home.rglob('*')), before)
                self.assertEqual(self.calls(), [])
                if '--dry-run' in args:
                    self.assertRegex(result.stdout, r'pi\s+planned')
                    self.assertIn('https://pi.dev/install.sh', result.stdout)
                if '--menu' in args:
                    self.assertIn('[x] 1 Pi package', result.stdout)
        # Missing Pi is selected by the default full flow as well.
        result = self.install('--skip', 'pi-bolt,orbi,tx,hermes,claude,codex')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])

    def test_restart_services_excludes_legacy_runner_and_tries_host_services(self):
        listed = subprocess.CompletedProcess([], 0,
            'pi-autowork@repo.service loaded active running Runner\n'
            'orbi-kit@1.service loaded active running Orbi\n'
            'hermes-gateway.service loaded active running Hermes\n'
            'kit-helper.service loaded active running Helper\n'
            'unrelated.service loaded active running Other\n', '')
        with patch.object(install_menu.platform, 'system', return_value='Linux'), \
                patch.object(install_menu.shutil, 'which', return_value='/bin/systemctl'), \
                patch.object(install_menu.subprocess, 'run', return_value=listed) as discover, \
                patch.object(install_menu, 'run_command', side_effect=[(1, 'failure'), (0, ''), (0, '')]) as run:
            with self.assertRaisesRegex(RuntimeError, 'hermes-gateway.service'):
                install_menu.restart_services(install_menu.Output(verbosity=0))
        self.assertIn('--state=active', discover.call_args.args[0])
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][-2:], ['try-restart', 'hermes-gateway.service'])
        self.assertEqual(commands[-1][-2:], ['try-restart', 'kit-helper.service'])
        self.assertNotIn('pi-autowork@*.service', discover.call_args.args[0])

    def test_restart_phase_runs_on_unchanged_and_failed_installs_but_not_preview(self):
        item = install_menu.Item('fixture', 'Fixture', steps=[
            install_menu.Step('unchanged', run=lambda: 'already current')])
        with patch.object(install_menu, 'restart_services', return_value='restarted') as restart:
            for _ in range(2):
                self.assertEqual(install_menu.install([item], {'fixture'}), 0)
            self.assertEqual(restart.call_count, 2)
            install_menu.install([item], {'fixture'}, dry_run=True)
            self.assertEqual(restart.call_count, 2)
            item.refuse = 'fixture failure'
            self.assertEqual(install_menu.install([item], {'fixture'}), 1)
            self.assertEqual(restart.call_count, 3)

    def test_restart_failure_makes_install_fail(self):
        with patch.object(install_menu, 'restart_services', side_effect=RuntimeError('restart failed')):
            item = install_menu.Item('fixture', 'Fixture')
            self.assertEqual(install_menu.install([item], {'fixture'}), 1)

    def test_every_host_includes_bundled_ponytail_without_a_second_plugin(self):
        self.fake('hermes', LOGGING)
        result = self.install('--only', 'pi,claude,codex,hermes', '--dry-run',
                              '--hermes-home', str(self.home))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('bundled Ponytail'), 4)
        self.assertNotIn('DietrichGebert/ponytail', result.stdout)
        self.assertFalse(self.calls('pi install'))
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
        self.fake('hermes', '#!/bin/sh\nexec "/bin/${AUTOWORK_HOST:-sh}" "$@"\n')
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

    def test_pi_bolt_refreshes_on_install_and_on_update(self):
        first = self.install('--only', 'pi-bolt')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(len(self.calls('pi-bolt-installer')), 1)
        second = self.install('--only', 'pi-bolt')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotIn('kept', second.stdout)
        self.assertEqual(len(self.calls('pi-bolt-installer')), 2)  # install refreshes too
        updated = self.install('update', '--only', 'pi-bolt')
        self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
        self.assertEqual(len(self.calls('pi-bolt-installer')), 3)

    def test_pi_bolt_uses_the_selected_bin_directory(self):
        destination = self.home / 'custom bin'
        result = self.install('--only', 'pi-bolt', env={'AUTOWORK_BIN_DIR': str(destination)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'{destination / "pi-bolt"}: 1.4.0', result.stdout)
        self.assertEqual(self.calls('pi-bolt-installer'),
                         [f'pi-bolt-installer {destination}|1|no'])

    def test_pi_bolt_failure_keeps_other_components(self):
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
                if not supported:
                    self.assertIn('unsupported Pi-Bolt platform', item.missing)

    def test_removed_runner_cannot_be_installed_or_updated(self):
        state = self.home / '.local/state/pi-autowork'
        state.mkdir(parents=True)
        evidence = state / 'preserved-attempt.json'
        evidence.write_text('{"unfinished": true}\n')
        for args in (('--only', 'autowork'), ('update', '--only', 'autowork')):
            with self.subTest(args=args):
                result = self.install(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('autowork', result.stdout + result.stderr)
                self.assertFalse((self.home / '.local/bin/autowork').exists())
                self.assertEqual(evidence.read_text(), '{"unfinished": true}\n')
        self.assertNotRegex(self.install('--list').stdout, r'(?m)^autowork\s')

    def test_octet_install_is_removed(self):
        for args in (('--only', 'octet'), ('update', '--only', 'octet')):
            with self.subTest(args=args):
                result = self.install(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('unknown item', result.stdout + result.stderr)
        self.assertNotRegex(self.install('--list').stdout, r'(?m)^octet\s')
        self.assertFalse((self.home / '.octet').exists())

    def test_all_installs_every_available_item_in_order(self):
        result = self.install('--all')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])
        # Fresh registrations are qualified before any install, without removal.
        self.assertEqual(self.calls('claude'), ['claude plugin list --json',
                                                'claude plugin marketplace add TrebuchetDynamics/kit',
                                                'claude plugin marketplace update kit',
                                                'claude plugin install kit@kit'])
        self.assertEqual(self.calls('codex'), ['codex plugin marketplace list --json',
                                               'codex plugin list --marketplace autowork-marketplace --json',
                                               'codex plugin list --marketplace kit-marketplace --json',
                                               'codex plugin marketplace add TrebuchetDynamics/kit --ref main',
                                               'codex plugin marketplace upgrade kit-marketplace',
                                               'codex plugin add kit@kit-marketplace'])
        link = self.home / '.local/bin/autowork'
        self.assertFalse(link.exists())  # removed executor has no installation path
        self.assertEqual((self.home / '.local/bin/tx').read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertTrue((self.home / '.local/share/bash-completion/completions/tx').is_file())
        self.assertIn('wrote completions for bash, zsh, fish', result.stdout)
        self.assertTrue((self.home / '.tmux.conf').is_file())  # none existed
        self.assertRegex(result.stdout, r'hermes\s+skipped\s+hermes not found')
        self.assertRegex(result.stdout, r'tx\s+installed')
        self.assertRegex(result.stdout, r'pi-bolt\s+installed.*1\.4\.0')
        self.assertEqual(len(self.calls('pi-bolt-installer')), 1)
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
        self.assertIn(f'pi install {NEW}', self.calls('pi'))
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
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])
        self.assertEqual(self.calls('pi update'), [f'pi update {NEW}'])  # never kept
        self.assertEqual(json.loads(settings.read_text())['packages'], [NEW])
        self.assertIn('Restart active Kit services', second.stdout)

    def test_a_marketplace_from_a_configured_source_is_used_and_not_rewritten(self):
        self.claude_registry(['kit'], {'source': 'directory', 'path': str(ROOT)})
        registry = self.home / '.claude/plugins/known_marketplaces.json'
        before = registry.read_bytes()
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json', 'claude plugin marketplace update kit',
                                               'claude plugin install kit@kit'])
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
        for name in ('autowork', 'kit'):
            with self.subTest(name=name):
                self.log.write_text('')
                self.claude_registry([name], {'source': 'directory', 'path': str(self.home / 'gone')})
                result = self.install('--only', 'claude')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('manual migration required', result.stdout)
                self.assertEqual(self.calls('claude'), [] if name == 'autowork' else ['claude plugin list --json'])

    def test_a_recorded_marketplace_folder_that_exists_is_left_alone(self):
        self.claude_registry(['kit'], {'source': 'directory', 'path': str(ROOT)})
        result = self.install('--only', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), ['claude plugin list --json', 'claude plugin marketplace update kit',
                                               'claude plugin install kit@kit'])

    def test_a_transient_preflight_race_is_retried_once(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        self.addCleanup(sys.path.remove, str(ROOT / 'scripts'))
        import install_menu
        original = install_menu.run_command
        self.addCleanup(setattr, install_menu, 'run_command', original)
        answers = [(1, 'ValueError: Destination changed since preflight: /x/skills/SKILL.md'), (0, '')]
        install_menu.run_command = lambda argv, output: answers.pop(0)
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

        def fake(argv, output):
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
                         for key in ('pi', 'autowork', 'tx', 'hermes', 'claude', 'codex')]
                output = io.StringIO()
                with patch.object(install_menu, 'run_command',
                        side_effect=lambda argv, _: (1, text) if argv == ['hermes'] else (0, 'ok')), \
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
        self.assertEqual(self.calls('pi install'), [f'pi install {NEW}'])
        self.assertIn('claude plugin install kit@kit', self.calls('claude'))
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))
        self.assertFalse((self.home / '.local/bin/autowork').exists())
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
        self.assertNotRegex(result.stdout, r'autowork\s+planned')
        for key in ('pi', 'pi-bolt', 'tx', 'hermes', 'claude', 'codex'):
            self.assertRegex(result.stdout, rf'{key}\s+planned')
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(self.calls('hermes'), [])
        self.assertFalse(self.calls('curl'))
        self.assertFalse((self.home / '.local/bin').exists())
        self.assertIn('enable the package skills and commands in Pi settings', result.stdout)

    def test_tx_keeps_an_existing_tmux_config(self):
        mine = b'set -g mouse on\n# mine\n'
        paths = ('.tmux.conf', '.tmux/style.tmux', '.tmux/git-status.sh', '.tmux/short-path.sh',
                 '.local/share/bash-completion/completions/tx', '.zsh/completions/_tx',
                 '.config/fish/completions/tx.fish')
        for relative in paths:
            path = self.home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(mine)
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
        self.assertIn('bash completion, zsh completion, fish completion', result.stdout)
        self.assertNotIn('completions for', result.stdout)
        self.assertNotRegex(result.stdout, r'installed\s+installed')
        self.assertEqual(self.calls('pi install'), [])
        config = self.home / '.tmux.conf'
        config.unlink()
        config.symlink_to(self.home / 'absent-user-config')
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(config.is_symlink())
        self.assertFalse(config.exists())

    def test_an_ordinary_install_refreshes_a_package_missing_a_shipped_skill(self):
        # A registered checkout older than this one lacks the skills a later release
        # added (orbi). A kept package left Pi without `/skill:orbi` and `/orbi` entirely.
        self.installed_package(only=['plan-with-me'])
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('pi update'), [f'pi update {NEW}'])
        self.assertRegex(result.stdout, r'skills missing: .*\borbi\b')
        self.assertRegex(result.stdout, r'pi\s+installed')

    def test_an_ordinary_install_refreshes_a_package_that_ships_every_skill(self):
        # Complete skill folders are not proof of current content: every install
        # refreshes, so edited or removed skills cannot stay live unnoticed.
        self.installed_package()
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi update'), [f'pi update {NEW}'])
        self.assertIn('every install refreshes the installed package', result.stdout)
        self.assertNotIn('already installed', result.stdout)

    def test_every_install_refreshes_the_package_and_update_does_too(self):
        self.installed_package(only=['plan-with-me'])
        for args in (('--only', 'pi'), ('--only', 'pi'), ('update', '--only', 'pi')):
            result = self.install(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls('pi update')), 3)  # one refresh per run, never kept

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
                self.fake('pi', PI.replace('  install|update)',
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
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('pi update'), [f'pi update {NEW}'])
        self.assertRegex(result.stdout, r'pi\s+installed')

    def test_menu_toggles_items_and_needs_a_terminal(self):
        result = self.install('--dry-run', '--menu', stdin='3 5 6\n\n', env={'AUTOWORK_INSTALL_UI': 'text'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[x] 1 Pi package', result.stdout)
        self.assertRegex(result.stdout, r'tx\s+skipped\s+not chosen')
        self.assertRegex(result.stdout, r'pi\s+planned')
        self.assertEqual(self.calls('pi install'), [])  # a dry run runs nothing
        self.assertIn('no terminal for the menu', self.install('--menu').stderr)

    def test_failed_steps_remain_failures_even_when_output_says_already(self):
        self.fake('claude', LOGGING + 'echo "boom: no network" >&2; exit 1\n')
        self.fake('codex', LOGGING + 'echo "marketplace already added" >&2; exit 4\n')
        report = self.home / 'install.jsonl'
        result = self.install('--full', '--skip', 'hermes,pi', '-q',
                              env={'AUTOWORK_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 1)
        import json
        rows = {r['item']: r for r in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['claude'], {'item': 'claude', 'status': 'failed', 'exit': 1})
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'failed', 'exit': 4})
        self.assertEqual(rows['tx'], {'item': 'tx', 'status': 'installed', 'exit': 0})
        self.assertEqual(rows['hermes'], {'item': 'hermes', 'status': 'skipped', 'exit': None})
        self.assertRegex(result.stdout, r'claude\s+failed.*boom: no network')
        self.assertRegex(result.stdout, r'codex\s+failed.*marketplace already added')
        self.assertIn('unknown item(s): nope', self.install('--only', 'nope').stderr)
        (self.bin / 'codex').unlink()
        self.install('--full', '--skip', 'hermes,pi', '-q',
                     env={'AUTOWORK_INSTALL_REPORT': str(report)})
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
                              env={'AUTOWORK_INSTALL_REPORT': str(report)})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.calls('claude'), [
            'claude plugin list --json',
            'claude plugin marketplace add TrebuchetDynamics/kit',
            'claude plugin marketplace update kit'])
        self.assertIn('codex plugin add kit@kit-marketplace', self.calls('codex'))
        import json
        rows = {row['item']: row for row in map(json.loads, report.read_text().splitlines())}
        self.assertEqual(rows['claude'], {'item': 'claude', 'status': 'failed', 'exit': 23})
        self.assertEqual(rows['codex'], {'item': 'codex', 'status': 'installed', 'exit': 0})

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
        with patch.dict(os.environ, AUTOWORK_INSTALL_REPORT=str(report)), contextlib.redirect_stdout(io.StringIO()):
            code = install_menu.install([item], {'retry'}, output=install_menu.Output('never', 0))
        self.assertEqual(code, 1)
        self.assertEqual(attempts.read_text(), 'xx')
        self.assertEqual(continued, [])
        rows = [json.loads(line) for line in report.read_text().splitlines()]
        self.assertEqual(rows[0], {'item': 'retry', 'status': 'failed', 'exit': 23})
        self.assertEqual(rows[1], {'item': 'services', 'status': 'installed', 'exit': 0})

    def test_full_selects_all_hosts_and_bundled_skills(self):
        self.fake('hermes', LOGGING)
        (self.home / '.hermes').mkdir()
        result = self.install('--full', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotRegex(result.stdout, r'autowork\s+planned')
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
        clone = self.home / '.hermes/profiles/work/plugins/autowork'
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
        (plugins / 'autowork').symlink_to(canonical)
        result = self.install('--only', 'hermes', '--dry-run')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate Kit registrations', result.stdout)
        self.assertIn(str(canonical), result.stdout)
        self.assertTrue((plugins / 'autowork').is_symlink())
        self.assertEqual(self.calls('hermes'), [])

    def test_tx_moves_a_symlink_aside_instead_of_writing_through_it(self):
        elsewhere = self.home / 'other-checkout/tx'
        elsewhere.parent.mkdir()
        elsewhere.write_text('someone else\'s tx\n')
        (self.home / '.local/bin').mkdir(parents=True)
        (self.home / '.local/bin/tx').symlink_to(elsewhere)
        result = self.install('--only', 'tx')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(elsewhere.read_text(), 'someone else\'s tx\n')
        self.assertFalse((self.home / '.local/bin/tx').is_symlink())
        self.assertEqual((self.home / '.local/bin/tx').read_bytes(), (ROOT / 'tmux/tx').read_bytes())
        self.assertEqual(Path(os.readlink(self.home / '.local/bin/tx.bak')), elsewhere)

    def test_a_second_replacement_keeps_the_first_backup(self):
        command = self.home / '.local/bin/tx'
        command.parent.mkdir(parents=True)
        for content in ('first script\n', 'second script\n'):
            command.write_text(content)
            result = self.install('--only', 'tx')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(command.with_name('tx.bak').read_text(), 'first script\n')
        self.assertEqual(command.with_name('tx.bak.1').read_text(), 'second script\n')

    def test_a_filtered_pi_package_counts_as_installed(self):
        package = self.installed_package()
        self.fake('pi', LOGGING + f'[ "$1" = --version ] && echo 0.72.0\n[ "$1" = list ] && printf "User packages:\\n  {NEW} (filtered)\\n    {package}\\n"\ntrue\n')
        result = self.install('--only', 'pi')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls('pi install'), [])
        self.assertEqual(self.calls('pi update'), [f'pi update {NEW}'])
        self.assertFalse((self.home / '.local/bin/autowork').exists())

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

    def test_setup_only_hermes_options_are_refused_for_profile_clones(self):
        self.fake('hermes', LOGGING)
        clone = self.home / '.hermes/profiles/work/plugins/autowork'
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
        self.origin, self.clone, self.other = base / 'origin.git', base / 'clone', base / 'other'
        run = lambda *a, cwd=None: subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True)
        run('git', 'init', '-q', '--bare', '-b', 'main', str(self.origin))
        for repo in (self.clone, self.other):
            run('git', 'clone', '-q', str(self.origin), str(repo))
            run('git', '-C', str(repo), 'config', 'user.email', 'o@example.invalid')
            run('git', '-C', str(repo), 'config', 'user.name', 'O')
        (self.other / 'f').write_text('1')
        run('git', '-C', str(self.other), 'add', '-A')
        run('git', '-C', str(self.other), 'commit', '-qm', 'one')
        run('git', '-C', str(self.other), 'push', '-q', 'origin', 'main')
        run('git', '-C', str(self.clone), 'pull', '-q')
        (self.other / 'f').write_text('2')
        run('git', '-C', str(self.other), 'commit', '-qam', 'two')
        run('git', '-C', str(self.other), 'push', '-q', 'origin', 'main')
        self.run_git = run

    def head(self, repo):
        return subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout

    def test_a_clean_checkout_behind_its_upstream_is_fast_forwarded(self):
        said = []
        self.assertTrue(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertEqual(self.head(self.clone), self.head(self.other))
        self.assertIn('Updated this checkout', said[0])
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))  # up to date: quiet
        self.assertEqual(len(said), 1)

    def test_local_changes_are_installed_as_they_are(self):
        (self.clone / 'f').write_text('mine')
        said = []
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertEqual((self.clone / 'f').read_text(), 'mine')
        self.assertIn('local changes', said[0])

    def test_a_detached_or_local_only_checkout_is_not_pulled(self):
        self.run_git('git', '-C', str(self.clone), 'checkout', '-q', '--detach')
        said = []
        self.assertFalse(install_menu.pull_checkout(self.clone, write=said.append))
        self.assertIn('no upstream', said[0])
        self.assertFalse(install_menu.pull_checkout(Path(self.tmp.name), write=said.append))  # not a checkout
        self.assertEqual(len(said), 1)


if __name__ == '__main__':
    unittest.main()
