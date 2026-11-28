"""Portable hosts expose adapters rather than Hermes-only worker instructions."""
from hashlib import sha256
import json
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class PortablePackageTests(unittest.TestCase):
    def test_installation_docs_use_pi_bolt_not_stock_pi_bootstrap(self):
        for name in ('README.md', 'docs/installation.md',
                     'docs/dependencies.md', 'docs/cross-host.md', 'skills/update-kit/SKILL.md'):
            with self.subTest(path=name):
                text = (ROOT / name).read_text()
                self.assertIn('Pi-Bolt is the only Pi harness', text)
                self.assertNotIn('pi.dev', text)
                self.assertNotIn('bootstrap Pi/Pi-Bolt', text)
        self.assertIn('pi install git:github.com/TrebuchetDynamics/kit',
                      (ROOT / 'README.md').read_text())  # manual stock Pi remains supported

    def test_removed_skill_resources_are_absent(self):
        for root in ('skills', 'adapters/skills'):
            for name in ('work', 'pending', 'blockers'):
                self.assertFalse((ROOT / root / name).exists(), f'{root}/{name}')

    def test_only_the_required_hermes_adapter_is_python_at_root(self):
        self.assertEqual({p.name for p in ROOT.glob('*.py')}, {'__init__.py'})

    def test_native_manifests_select_portable_resources(self):
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        pi = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(codex['skills'], './adapters/skills/')
        self.assertEqual(pi['pi']['skills'], ['./adapters/skills'])
        self.assertEqual(pi['pi']['extensions'], ['./adapters/pi.mjs'])
        self.assertNotIn('scripts', pi, 'installation must not run setup hooks')
        for helper in ('github_issues.py', 'worktree_paths.py', 'checkout_lock.py'):
            self.assertIn('scripts/' + helper, pi['files'])
        self.assertIn('docs/', pi['files'])
        self.assertFalse(any(entry.startswith('src/') for entry in pi['files']))
        marketplace = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text())
        self.assertEqual(marketplace['name'], 'kit-marketplace')
        self.assertEqual(codex['name'], 'kit')
        self.assertEqual(marketplace['plugins'][0]['name'], 'kit')
        self.assertEqual(marketplace['plugins'][0]['source'], {'source': 'local', 'path': '.'})

    def test_archive_contains_only_portable_delivery_resources(self):
        import os
        import shutil
        import subprocess
        import sys
        import tempfile

        with tempfile.TemporaryDirectory(prefix='portable inference ') as temporary:
            base = Path(temporary)
            source, foreign = base / 'source', base / 'foreign'
            source.mkdir()
            foreign.mkdir()
            manifest = json.loads((ROOT / 'package.json').read_text())
            for entry in ('package.json', *manifest['files']):
                path = ROOT / entry
                if entry.startswith('!') or not path.exists():
                    continue
                target = source / entry
                target.parent.mkdir(parents=True, exist_ok=True)
                if path.is_dir():
                    shutil.copytree(path, target, ignore=shutil.ignore_patterns('node_modules', '__pycache__'))
                else:
                    shutil.copy2(path, target)
            packed = subprocess.run(['npm', 'pack', '--ignore-scripts', '--offline', '--json'],
                                    cwd=source, check=True, capture_output=True, text=True)
            archive = source / json.loads(packed.stdout)[0]['filename']
            subprocess.run(['tar', '-xzf', str(archive), '-C', str(base)], check=True)
            installed = base / 'package'
            self.assertFalse((installed / 'src').exists())
            for root in ('skills', 'adapters/skills'):
                for name in ('work', 'pending', 'blockers'):
                    self.assertFalse((installed / root / name).exists())
            self.assertFalse((installed / 'paseo-plugin.json').exists())
            self.assertTrue((installed / 'docs/github-native.md').is_file())
            # Prove the common policy closure in the actual npm payload, not just
            # the source checkout. Every adapter reaches COMMON or Ponytail.
            policy = installed / 'skills/shared/COMMON-CONTRACT.md'
            self.assertTrue(policy.is_file())
            for relative, target in (
                    ('adapters/skills/COMMON.md', '../../skills/shared/COMMON-CONTRACT.md'),
                    ('skills/shared/PONYTAIL.md', 'COMMON-CONTRACT.md')):
                entry = installed / relative
                self.assertIn('](' + target, entry.read_text())
                self.assertEqual((entry.parent / target).resolve(), policy.resolve())

            # Enumerate every shipped entrypoint and check the actual conditional
            # GUI instruction + fragment, including portable-only Graphify and
            # canonical compatibility entries. No claim of model loading/adherence.
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                'skill_standard', ROOT / 'tests/test_skill_standard.py')
            standard = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(standard)
            shipped = standard.gui_entrypoint_routes(installed)
            self.assertEqual(set(shipped), set(standard.gui_entrypoint_routes(ROOT)))

            skill = installed / 'skills/100x'
            upstream = skill / 'upstream'
            files = json.loads((skill / 'UPSTREAM.json').read_text())['files']
            self.assertEqual(files, {
                path.relative_to(upstream).as_posix(): sha256(path.read_bytes()).hexdigest()
                for path in upstream.rglob('*') if path.is_file()
            })
            adapter = installed / 'adapters/skills/100x/SKILL.md'
            self.assertIn('](../../../skills/100x/SKILL.md)', adapter.read_text())
            self.assertIn('](skills/100x/SKILL.md)', (installed / 'README.md').read_text())
            self.assertRegex((installed / 'skills/ask-kit/SKILL.md').read_text(), r'\| `/100x` \|')

            self.check_visual_reference_packs(installed)
            self.check_open_3d(installed)
            self.check_forever_discovery(installed, foreign)

            # Writing guidance is reached through the real installed adapter,
            # including its mode-specific completion, not a checkout-only copy.
            adapter = installed / 'adapters/skills/writing-for-agents/SKILL.md'
            target = '../../../skills/writing-for-agents/SKILL.md'
            self.assertIn('](' + target + ')', adapter.read_text())
            canonical = (adapter.parent / target).resolve()
            self.assertTrue(canonical.is_relative_to(installed))
            self.assertEqual(canonical.read_bytes(),
                             (ROOT / 'skills/writing-for-agents/SKILL.md').read_bytes())

            batch = foreign / 'batch.json'
            batch.write_text(json.dumps({'issues': [{
                'key': 'example', 'title': 'Example bounded task',
                **{field: 'Complete fixture contract' for field in
                   ('outcome', 'scope', 'exclusions', 'acceptance', 'verification', 'sources')}
            }]}))
            # Preview must work from the installed archive, without a checkout or gh.
            result = subprocess.run([sys.executable, '-B',
                                     str(installed / 'scripts/github_issues.py'),
                                     '--repo', 'example/project', '--batch', str(batch)],
                                    cwd=foreign, env=dict(os.environ, PATH=str(foreign)),
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            preview = json.loads(result.stdout)
            self.assertTrue(preview['preview'])
            self.assertFalse(preview['remote_checked'])
            self.assertEqual(preview['issues'][0]['key'], 'example')

            # The packaged lifecycle helper resolves its skill and reference from the
            # archive and reads status from a foreign directory without a checkout,
            # Hermes source, executor payload or any staged/installed deployment.
            helper = installed / 'skills/orbi/scripts/orbi_control.py'
            canonical = (installed / 'skills/orbi/SKILL.md').read_text()
            reference = (installed / 'skills/orbi/references/lifecycle.md').read_text()
            self.assertIn('<this-skill>/scripts/orbi_control.py', canonical)
            self.assertIn('Linux is the only mutation platform', canonical)
            self.assertIn('macOS supports status, version and help; setup/start/update/stop are refused before side effects.',
                          reference)
            checkout = foreign / 'target repo'
            checkout.mkdir()
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True, timeout=30)
            subprocess.run(['git', '-C', str(checkout), 'remote', 'add', 'origin',
                            'https://github.com/example/project.git'], check=True, timeout=30)
            tools = foreign / 'bin'
            tools.mkdir()
            git = shutil.which('git')
            self.assertIsNotNone(git, 'the archive check needs git on PATH')
            (tools / 'git').symlink_to(git)
            home, state = foreign / 'home', foreign / 'xdg'
            home.mkdir()
            state.mkdir()
            sandbox = {'PATH': str(tools), 'HOME': str(home), 'XDG_DATA_HOME': str(state),
                       'XDG_CONFIG_HOME': str(foreign / 'config'),
                       'PYTHONDONTWRITEBYTECODE': '1'}
            usage = subprocess.run([sys.executable, '-B', str(helper), '--help'],
                                   cwd=foreign, capture_output=True, text=True,
                                   timeout=60, env=sandbox)
            self.assertEqual(usage.returncode, 0, usage.stderr)
            self.assertIn('[status|version|setup|start|update|stop|prune|help]', usage.stdout)
            before = sorted(path.relative_to(checkout) for path in checkout.rglob('*'))
            status = subprocess.run(
                [sys.executable, '-B', str(helper), 'status',
                 '--repo-dir', str(checkout), '--json'],
                cwd=foreign, capture_output=True, text=True, timeout=60, env=sandbox)
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            report = json.loads(status.stdout)
            self.assertEqual(report['deployment'], {
                'state': 'absent',
                'harness': {'management': 'legacy', 'requested_kind': None,
                            'selection_source': 'legacy', 'launcher': None,
                            'executable': None, 'state': 'unknown',
                            'reason': 'unconfigured; new setup defaults to pi-bolt'},
            })
            self.assertEqual(report['scheduler']['state'], 'unavailable')
            self.assertEqual(report['queue']['state'], 'unavailable')
            self.assertEqual(sorted(path.relative_to(checkout) for path in checkout.rglob('*')),
                             before, 'status wrote into the target repository')
            self.assertEqual(list(home.rglob('.orbi*')), [], 'status staged a deployment')
            self.assertEqual(list(state.rglob('*')), [], 'status installed a deployment')

            # The new engine-only action also works from the actual portable archive.
            version = subprocess.run(
                [sys.executable, '-B', str(helper), 'version',
                 '--repo-dir', str(checkout), '--json'],
                cwd=foreign, capture_output=True, text=True, timeout=30, env=sandbox)
            self.assertEqual(version.returncode, 0, version.stdout + version.stderr)
            report = json.loads(version.stdout)
            self.assertEqual(report['action'], 'version')
            self.assertEqual(report['repo'], 'example/project')
            self.assertEqual(report['deployment']['state'], 'absent')
            self.assertEqual(report['deployment']['engine']['state'], 'unconfigured')
            self.assertIsNone(report['deployment']['engine']['version'])
            self.assertNotIn('scheduler', report)
            self.assertEqual(sorted(path.relative_to(checkout) for path in checkout.rglob('*')), before)
            self.assertEqual(list(home.iterdir()), [], 'version wrote to HOME')
            self.assertEqual(list(state.iterdir()), [], 'version installed a deployment')

            # Update preview from the shipped archive: no git/bash/lsof/host probes,
            # no checkout, locks, cache or destination directory creation.
            update = installed / 'skills/update-kit/scripts/update_kit.py'
            self.assertTrue(update.is_file())
            self.assertIn('<this-skill>/scripts/update_kit.py',
                          (installed / 'skills/update-kit/SKILL.md').read_text())
            sandbox['PATH'] = str(foreign / 'no-tools')
            before = sorted(path.relative_to(foreign) for path in foreign.rglob('*'))
            result = subprocess.run([sys.executable, '-B', str(update), '--dry-run', '--only', 'pi'],
                                    cwd=foreign, env=sandbox, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(state / 'kit/source'), result.stdout)
            self.assertIn('NOT_CHECKED', result.stdout)
            self.assertIn('update --no-pull --only pi', result.stdout)
            self.assertEqual(sorted(path.relative_to(foreign) for path in foreign.rglob('*')), before)

            self.assert_visual_workflows(installed, base)

    def assert_visual_workflows(self, installed, base):
        import os
        import subprocess
        import sys

        pins = {
            'brand-identity': ('fatihaydost/brand-identity-skill', 'af7ba40fe067b8b4aaeb2af90ed6c8996d014791'),
            'styleseed': ('bitjaru/styleseed', '78d1e08e6e931e04c737d34ed3cde1dda540faa6'),
        }
        for name, (repo, revision) in pins.items():
            skill = installed / 'skills' / name
            pin = json.loads((skill / 'UPSTREAM.json').read_text())
            self.assertEqual((pin['repository'], pin['revision'], pin['license']),
                             (f'https://github.com/{repo}', revision, 'MIT'))
            upstream = skill / 'upstream'
            files = {p.relative_to(upstream).as_posix(): sha256(p.read_bytes()).hexdigest()
                     for p in upstream.rglob('*') if p.is_file()}
            self.assertEqual(files, pin['files'] | pin.get('derived_files', {}))
            self.assertIn('MIT License', (upstream / 'LICENSE').read_text())
            self.assertEqual(list(upstream.rglob('SKILL.md')), [])
            adapter = installed / 'adapters/skills' / name / 'SKILL.md'
            self.assertIn(f'../../../skills/{name}/SKILL.md', adapter.read_text())

        project = base / 'visual project'
        project.mkdir()
        uv = project / 'uv'
        uv.write_text('#!/bin/sh\ntouch attempted-install\nexit 1\n')
        uv.chmod(0o755)
        env = dict(os.environ, HOME=str(project), PATH=f'{project}{os.pathsep}{os.environ["PATH"]}')
        env.pop('BRAND_IDENTITY_ENV', None)

        def run(*args):
            return subprocess.run(args, cwd=project, env=env, text=True,
                                  capture_output=True, timeout=30)

        brand = installed / 'skills/brand-identity'
        preflight = [sys.executable, '-BS', str(brand / 'upstream/scripts/preflight.py')]
        self.assertEqual(run(*preflight).returncode, 0, 'plain intake needs no render dependencies')
        missing = run(*preflight, '--type', '--font', 'missing.ttf')
        self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
        self.assertIn('fontTools', missing.stderr)
        self.assertIn('pathops', missing.stderr, 'type audits can instance variable fonts')
        self.assertIn('missing.ttf', missing.stderr)
        self.assertIn('requirements.txt', missing.stderr)
        helper = run(sys.executable, '-BS', str(brand / 'upstream/scripts/brand.py'), 'check', '--type')
        self.assertEqual(helper.returncode, 1, helper.stdout + helper.stderr)
        self.assertIn('fontTools', helper.stderr)
        self.assertIn('requirements.txt', helper.stderr)
        self.assertEqual(list(project.iterdir()), [uv], 'capability checks must not install or write')

        style = installed / 'skills/styleseed/upstream/skills/styleseed'
        workflows = style / 'workflows'
        self.assertEqual(len(list(workflows.glob('ss-*/WORKFLOW.md'))), 22)
        missing = run('node', str(style / 'preflight.mjs'), '--browser', str(project / 'missing.mjs'))
        self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
        self.assertIn('Playwright', missing.stderr)
        # If the supplied module exports no Chromium, do not probe a different
        # browser from the project and report that the requested renderer is ready.
        import shutil
        project_browser = project / 'node_modules/playwright'
        project_browser.mkdir(parents=True)
        (project_browser / 'index.js').write_text('exports.chromium = { launch: async () => ({ close() {} }) };')
        wrong_browser = project / 'other.mjs'
        wrong_browser.write_text('export default {};')
        wrong = run('node', str(style / 'preflight.mjs'), '--browser', str(wrong_browser))
        self.assertEqual(wrong.returncode, 1, wrong.stdout + wrong.stderr)
        self.assertIn('other.mjs: Playwright Chromium launch is not exported', wrong.stderr)
        wrong_browser.unlink()
        shutil.rmtree(project_browser.parent)
        external = run('node', str(workflows / 'ss-reference/scripts/measure-reference.mjs'), '--designlang')
        self.assertEqual(external.returncode, 1, external.stdout + external.stderr)
        self.assertIn('Kit does not install Designlang', external.stderr)
        self.assertEqual(list(project.iterdir()), [uv])
        resolve = workflows / 'ss-resolve/scripts/resolve-context.mjs'
        for host, title in [('pi', 'Pi'), ('hermes', 'Hermes')]:
            with self.subTest(host=host):
                cmd = ['node', str(resolve), '--agent', host, '--grammar', 'operations-console',
                       '--adapter', 'product-ui', '--key-color', '#2468AB']
                compiled = run(*cmd)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                bundle = (project / '.styleseed/effective-rules.md').read_text()
                self.assertIn(f'## {title} execution contract', bundle)
                self.assertIn(f'- Agent: {host}', bundle)
                manifest = json.loads((project / '.styleseed/manifest.json').read_text())
                self.assertEqual(manifest['selection']['agent'], host)
                self.assertEqual(manifest['selection']['paletteGeneration']['keyColor'].lower(), '#2468ab')
                self.assertIn('--ss-primary:', (project / '.styleseed/palette.css').read_text())
                checked = run(*cmd, '--check')
                self.assertEqual(checked.returncode, 0, checked.stderr)

        # The catalog cannot hash itself in the upstream inventory. Its Hermes mapping
        # must still be checked against the digest tied to the Kit distribution.
        catalog = workflows / 'ss-resolve/references/catalog.json'
        original = catalog.read_bytes()
        data = json.loads(original)
        data['agents']['hermes'] = 'Replaced execution contract'
        catalog.write_text(json.dumps(data))
        for result in (run('node', str(style / 'preflight.mjs')), run(*cmd)):
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('catalog.json', result.stderr)
            self.assertIn('Restore', result.stderr)
        doctor = run('node', str(resolve.with_name('styleseed-doctor.mjs')), '--json')
        self.assertEqual(doctor.returncode, 1, doctor.stdout + doctor.stderr)
        installation = json.loads(doctor.stdout)['installation']
        self.assertEqual(installation['status'], 'invalid')
        self.assertIn('catalog.json', installation['detail'])
        self.assertEqual((project / '.styleseed/effective-rules.md').read_text(), bundle)
        catalog.write_bytes(original)

        # Mutate an otherwise valid shipped workflow. Both preflight and compile
        # must fail rather than issuing a verified receipt or rewriting the bundle.
        workflow = workflows / 'ss-setup/WORKFLOW.md'
        workflow.write_text(workflow.read_text() + '\nChanged after packaging.\n')
        for result in (run('node', str(style / 'preflight.mjs')), run(*cmd)):
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('tampered', result.stderr)
            self.assertIn('Restore', result.stderr)
        self.assertEqual((project / '.styleseed/effective-rules.md').read_text(), bundle)

    def check_forever_discovery(self, installed, foreign):
        import subprocess
        import sys

        skill = installed / 'skills/forever-components'
        pin = json.loads((skill / 'UPSTREAM.json').read_text())
        self.assertEqual(pin['revision'], 'ae685e51644be5a793cce5b4becfd31009593f00')
        self.assertEqual(pin['license'], 'MIT')
        self.assertEqual(pin['source_paths'], {
            'LICENSE': 'LICENSE', 'NOTICE.md': 'NOTICE.md', 'llms.txt': 'llms.txt',
            'facets.json': 'infinite/facets.json', 'components.index.json': 'infinite/components.index.json',
        })
        upstream = skill / 'upstream'
        self.assertEqual({p.relative_to(upstream).as_posix() for p in upstream.rglob('*') if p.is_file()},
                         set(pin['source_paths']))
        self.assertFalse(list(skill.rglob('*.html')), 'tile sources are retrieved, not shipped')
        for name, digest in pin['files'].items():
            self.assertEqual(sha256((upstream / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(pin['files'].keys(), pin['source_paths'].keys())

        # Run the real helper from the packed skill in a foreign directory.
        before = set(foreign.iterdir())
        def search(*args):
            result = subprocess.run([sys.executable, str(skill / 'scripts/catalog.py'), 'search', *args],
                                    cwd=foreign, check=True, capture_output=True, text=True, timeout=10)
            return json.loads(result.stdout)

        css_loader = ('--facet', 'role=loader', '--facet', 'technique=css-only',
                      '--facet', 'perfTier=cheap', '--facet', 'deps=none')
        matches = search(*css_loader, '--text', 'Equalizer Bars')
        self.assertEqual([(c['title'], c['file']) for c in matches],
                         [('Equalizer Bars', 'loaders/08-equalizer-bars.html')])
        self.assertEqual(len(search(*css_loader)), 3)
        self.assertEqual(search(*css_loader, '--text', 'no-matching-widget'), [])
        self.assertEqual(set(foreign.iterdir()), before)

    def test_forever_does_not_follow_redirects_from_the_pinned_url(self):
        from contextlib import redirect_stderr
        from email.message import Message
        import io
        import runpy
        import tempfile
        from unittest.mock import patch
        from urllib import request, response

        main = runpy.run_path(str(ROOT / 'skills/forever-components/scripts/catalog.py'))['main']
        calls = []

        def redirected_source(handler, req):
            calls.append(req.full_url)
            headers = Message()
            headers['Location'] = 'https://example.com/other.html'
            redirected = response.addinfourl(io.BytesIO(), headers, req.full_url,
                                            302 if len(calls) == 1 else 200)
            redirected.msg = 'Found' if len(calls) == 1 else 'OK'
            return redirected

        with (tempfile.TemporaryDirectory() as temp,
              patch.object(request.HTTPSHandler, 'https_open', redirected_source)):
            dest = Path(temp) / 'tile'
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(['fetch', 'loaders/08-equalizer-bars.html', str(dest)]), 1)
            self.assertEqual(len(calls), 1, calls)
            self.assertIn(calls[0], error.getvalue())
            self.assertIn('302', error.getvalue())
            self.assertFalse(dest.exists())

    def test_forever_fetches_one_indexed_tile_with_provenance_and_attribution(self):
        from contextlib import redirect_stderr, redirect_stdout
        from http.client import IncompleteRead
        import io
        import runpy
        import tempfile
        from unittest.mock import patch
        from urllib.error import URLError

        skill = ROOT / 'skills/forever-components'
        main = runpy.run_path(str(skill / 'scripts/catalog.py'))['main']
        url = ('https://raw.githubusercontent.com/isas1/forever-ai-components/'
               'ae685e51644be5a793cce5b4becfd31009593f00/infinite/loaders/08-equalizer-bars.html')
        raw = b'<!doctype html><title>Equalizer Bars</title>\n'
        with tempfile.TemporaryDirectory() as temp, patch('urllib.request.OpenerDirector.open') as fetch:
            dest = Path(temp) / 'tile'
            error = io.StringIO()
            with redirect_stderr(error), self.assertRaises(SystemExit) as rejected:
                main(['fetch', '../NOTICE.md', str(dest)])
            self.assertEqual(rejected.exception.code, 2)
            self.assertIn('choose an exact file from search', error.getvalue())
            fetch.assert_not_called()
            self.assertFalse(dest.exists())

            args = ['fetch', 'loaders/08-equalizer-bars.html', str(dest)]
            fetch.side_effect = URLError('network unavailable')
            error = io.StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(args), 1)
            self.assertIn(url, error.getvalue())
            self.assertIn('network unavailable', error.getvalue())
            self.assertIn('Restore access', error.getvalue())
            self.assertFalse(dest.exists())

            fetch.reset_mock(side_effect=True)
            response = fetch.return_value.__enter__.return_value
            response.headers = {'Content-Length': str(len(raw))}
            for failure in ('short body', 'broken chunk', 'partial content'):
                with self.subTest(failure=failure):
                    response.status = 206 if failure == 'partial content' else 200
                    response.read.return_value = raw if failure == 'partial content' else raw[:-1]
                    response.read.side_effect = IncompleteRead(raw[:-1]) if failure == 'broken chunk' else None
                    failed_dest = Path(temp) / failure
                    error = io.StringIO()
                    with redirect_stderr(error), redirect_stdout(io.StringIO()):
                        self.assertEqual(main([*args[:-1], str(failed_dest)]), 1)
                    self.assertIn(url, error.getvalue())
                    self.assertIn('206' if failure == 'partial content' else 'incomplete', error.getvalue().lower())
                    self.assertIn('retry', error.getvalue())
                    self.assertFalse(failed_dest.exists())

            fetch.reset_mock()
            response.status = 200
            response.read.side_effect = None
            response.read.return_value = raw
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args), 0)
            fetch.assert_called_once()
            self.assertEqual(fetch.call_args.args, (url,))
            self.assertEqual((dest / '08-equalizer-bars.html').read_bytes(), raw)
            receipt = json.loads((dest / 'provenance.json').read_text())
            self.assertEqual(receipt['source_path'], 'infinite/loaders/08-equalizer-bars.html')
            self.assertEqual(receipt['source_url'], url)
            self.assertEqual(receipt['revision'], 'ae685e51644be5a793cce5b4becfd31009593f00')
            self.assertEqual(receipt['sha256'], sha256(raw).hexdigest())
            for name in ('LICENSE', 'NOTICE.md'):
                self.assertEqual((dest / name).read_bytes(), (skill / 'upstream' / name).read_bytes())

    def check_visual_reference_packs(self, installed):
        packs = (
            ('skills/procedural-drawing/UPSTREAM.json', 'cloveric/claude-drawing-skill',
             '6af36dc717b63d6ddafb54d2eaa120cacd99ab4d', '.', (
                 'skills/procedural-drawing/upstream/LICENSE',
                 'skills/procedural-drawing/upstream/PROTOCOL.md',
                 'skills/procedural-drawing/upstream/requirements.txt',
                 'skills/procedural-drawing/scripts/preflight.py',
             )),
            ('skills/genart/UPSTREAM.json', 'camilleroux/genart-skill',
             '36bb7f1f673580c6d6cbb13a80a15062d6c00459', 'skills/genart', (
                 'skills/genart/upstream/LICENSE', 'skills/genart/upstream/PROTOCOL.md',
                 'skills/genart/upstream/references/determinism.md',
                 'skills/genart/upstream/references/verification.md',
                 'skills/genart/scripts/verify_canvas.py', 'skills/genart/examples/seeded.html',
             )),
            ('skills/tastemaker/UPSTREAM.json', 'codeswithroh/tastemaker',
             '792a28a820ec4e9159ef8621c21a6c88528bbf2e', 'skills/tastemaker', (
                 'skills/tastemaker/upstream/LICENSE', 'skills/tastemaker/upstream/ideagram/LICENSE',
                 'skills/tastemaker/upstream/references/verbs/study.md',
                 'skills/tastemaker/upstream/references/verbs/audit.md',
                 'skills/tastemaker/upstream/references/verbs/comps.md',
                 'skills/tastemaker/upstream/scripts/extract_palette.py',
                 'skills/tastemaker/upstream/scripts/check_contrast.py',
                 'skills/tastemaker/upstream/scripts/generate_palette.py',
                 'skills/tastemaker/upstream/scripts/anti_slop_scan.py',
                 'skills/tastemaker/upstream/scripts/audit_motion.py',
             )),
            ('skills/dembrandt/UPSTREAM.json', 'dembrandt/dembrandt-skills',
             'cd3ff4b085557fe20f2f247dd853e4be7df583f3', 'directory/skills', (
                 'skills/dembrandt/upstream/LICENSE', 'skills/dembrandt/upstream/directory/LICENSE',
                 'skills/dembrandt/upstream/skills/extract-design/PROTOCOL.md',
                 'skills/dembrandt/upstream/skills/generate-ui-from-brand/PROTOCOL.md',
             )),
            ('skills/genjutsu/UPSTREAM.json', 'AThevon/genjutsu',
             'a22540b623590505879d6489dd03d7f3072bce05', 'skills', (
                 'skills/genjutsu/upstream/LICENSE',
                 'skills/genjutsu/upstream/skills/_jutsu/ui-ux-pro-max/LICENSE-upstream.txt',
                 'skills/genjutsu/upstream/skills/cast/PROTOCOL.md',
                 'skills/genjutsu/upstream/skills/paint/PROTOCOL.md',
                 'skills/genjutsu/upstream/skills/bunshin/PROTOCOL.md',
                 'skills/genjutsu/upstream/skills/_jutsu/motion-principles/PROTOCOL.md',
             )),
            ('skills/motion-graphics/UPSTREAM.json', 'charlie947/motion-graphics-skills',
             '229022ebca76972e119e36ada23a1648d51665ab', 'skills', (
                 'skills/motion-graphics/upstream/LICENSE',
                 'skills/motion-graphics/upstream/skills/motion-effects/PROTOCOL.md',
                 'skills/motion-graphics/upstream/skills/motion-effects/references/effects.md',
                 'skills/motion-graphics/scripts/capture.py',
             )),
        )
        for manifest, repo, revision, source_path, required in packs:
            with self.subTest(repo=repo):
                skill = (installed / manifest).parent
                pin = json.loads((installed / manifest).read_text())
                self.assertEqual(pin['repository'], f'https://github.com/{repo}')
                self.assertEqual(pin['revision'], revision)
                self.assertEqual(pin['license'], 'MIT')
                self.assertEqual(pin['source_path'], source_path)
                self.assertTrue(pin['transform'])
                upstream = skill / 'upstream'
                files = {p.relative_to(upstream).as_posix(): sha256(p.read_bytes()).hexdigest()
                         for p in upstream.rglob('*') if p.is_file()}
                # A relocated entry maps the original upstream path to {path, sha256}.
                recorded = {(entry['path'].removeprefix('upstream/') if isinstance(entry, dict) else stored):
                            (entry['sha256'] if isinstance(entry, dict) else entry)
                            for stored, entry in pin['files'].items()}
                self.assertEqual(files, recorded)
                self.assertFalse(list(upstream.rglob('SKILL.md')), 'upstream is not discoverable')
                for relative in required:
                    path = installed / relative
                    self.assertTrue(path.is_file(), relative)
                    if path.name == 'LICENSE':
                        self.assertIn('MIT License', path.read_text())

        genjutsu = installed / 'skills/genjutsu'
        pin = json.loads((genjutsu / 'UPSTREAM.json').read_text())
        third_party = 'skills/_jutsu/ui-ux-pro-max/LICENSE-upstream.txt'
        self.assertEqual(pin['third_party']['license'], 'MIT')
        self.assertEqual(pin['third_party']['source_path'], third_party)
        self.assertIn('Next Level Builder', (genjutsu / 'upstream' / third_party).read_text())
        for name in ('genjutsu', 'motion-graphics'):
            adapter = installed / 'adapters/skills' / name
            metadata = yaml.safe_load((adapter / 'SKILL.md').read_text().split('---', 2)[1])
            policy = yaml.safe_load((adapter / 'agents/openai.yaml').read_text())['policy']
            self.assertIs(metadata['disable-model-invocation'], True)
            self.assertIs(policy['allow_implicit_invocation'], False)
            for link in re.findall(r'\]\(([^)#]+)\)', (installed / 'skills' / name / 'SKILL.md').read_text()):
                self.assertTrue((installed / 'skills' / name / link).is_file(), (name, link))

        drawing = installed / 'skills/procedural-drawing'
        index = '\n'.join(line for line in (drawing / 'styles.md').read_text().splitlines()
                          if line.startswith('| '))
        for folder, pattern in (('lib', '[a-z0-9]+'), ('examples', '[a-z0-9_]+')):
            selected = re.findall(rf'\]\((upstream/{folder}/{pattern}\.py)\)', index)
            self.assertEqual(len(selected), 83)
            self.assertCountEqual(selected, [p.relative_to(drawing).as_posix()
                                            for p in drawing.glob(f'upstream/{folder}/*.py')
                                            if p.name != 'core.py'])

        for name in ('procedural-drawing', 'genart'):
            adapter = installed / 'adapters/skills' / name / 'SKILL.md'
            canonical = installed / 'skills' / name / 'SKILL.md'
            self.assertIn(f'](../../../skills/{name}/SKILL.md)', adapter.read_text())
            for relative in re.findall(r'\]\(([^)#\s]+)', canonical.read_text()):
                self.assertTrue((canonical.parent / relative).is_file(), relative)

        skill = installed / 'skills/dembrandt'
        index = (skill / 'references/corpus.md').read_text()
        selected = re.findall(r'\]\(\.\./(upstream/skills/[^/)]+/PROTOCOL\.md)\)', index)
        self.assertEqual(len(selected), 45)
        self.assertCountEqual(selected, [p.relative_to(skill).as_posix()
                                         for p in skill.glob('upstream/skills/*/PROTOCOL.md')])

    def check_open_3d(self, installed):
        skill = installed / 'skills/open-3d'
        upstream = skill / 'upstream'
        pin = json.loads((skill / 'UPSTREAM.json').read_text())
        self.assertEqual(pin['repository'], 'https://github.com/Moh4696/open-3d-skills')
        self.assertEqual(pin['revision'], '53beb899e77f65d50160a3765f36f5ddb8b3c19b')
        self.assertEqual(pin['license'], 'MIT')
        self.assertIn('Copyright (c) 2026 exploraX', (upstream / 'LICENSE').read_text())
        files = {p.relative_to(upstream).as_posix(): sha256(p.read_bytes()).hexdigest()
                 for p in upstream.rglob('*') if p.is_file()}
        self.assertEqual(files, pin['files'])
        self.assertFalse(list(upstream.rglob('SKILL.md')))
        self.assertEqual({p.parent.name for p in upstream.glob('skills/*/PROTOCOL.md')},
                         {'alpha-cutout', 'cursor-rig', 'exploded-view', 'frame-capture',
                          'motion-assets', 'scroll-film', 'site-check', 'threejs-scene'})
        original = 'skills/frame-capture/scripts/record.py'
        self.assertEqual(pin['derived_runtime']['source'], original)
        self.assertIn(original, files)
        self.assertEqual(pin['derived_runtime']['path'], 'runtime/record.py')
        self.assertNotEqual((skill / 'runtime/record.py').read_bytes(), (upstream / original).read_bytes())
        for relative in ('SKILL.md', 'references/runtime.md'):
            guide = skill / relative
            for link in re.findall(r'\[[^\]\n]+\]\(([^)#\s]+)(?:#[^)]+)?\)', guide.read_text()):
                self.assertTrue((guide.parent / link).is_file(), (relative, link))
        adapter = installed / 'adapters/skills/open-3d'
        entry = (adapter / 'SKILL.md').read_text()
        self.assertIn('](../../../skills/open-3d/SKILL.md)', entry)
        self.assertNotIn('upstream/', entry)
        self.assertIs(yaml.safe_load(entry.split('---', 2)[1])['disable-model-invocation'], True)
        self.assertIs(yaml.safe_load((adapter / 'agents/openai.yaml').read_text())
                      ['policy']['allow_implicit_invocation'], False)

    def test_portable_skills_and_references_are_self_contained(self):
        folder = ROOT / 'adapters/skills'
        names = {p.parent.name for p in folder.glob('*/SKILL.md')}
        self.assertEqual(names, {'plan-with-me', 'unblock', 'plan-for-me', 'docs-sync', 'orbi', 'update-kit',
            'autoresearch', '100x', 'impeccable', 'lgtm', 'goal',
            'git-commit-push', 'push', 'ui-taste', 'open-3d', 'sakurai', 'forever-components',
            'unslop', 'beautify-github-readme',
            'tastemaker', 'dembrandt', 'genjutsu', 'motion-graphics',
            'brand-identity', 'styleseed', 'procedural-drawing', 'genart',
            'ponytail', 'ponytail-review', 'ponytail-audit', 'ponytail-debt',
            'ponytail-gain', 'ponytail-help', 'bug-harvest',
            'autonomous-codebase-improver', 'split-folder', 'unused-code',
            'test-optimizer', 'apk-get', 'graphify', 'writing-for-agents', 'agents-md-generator',
            'grilling', 'grill-with-docs', 'improve-codebase-architecture', 'ask-kit',
            'responsive-screenshots', 'state-machine'})
        for source in folder.rglob('*.md'):
            text = source.read_text()
            if source.name == 'SKILL.md':
                metadata = yaml.safe_load(text.split('---', 2)[1])
                self.assertEqual(metadata['name'], source.parent.name)
                self.assertIsInstance(metadata['description'], str)
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((source.parent / link.split('#')[0]).exists(), (source, link))

    def test_claude_code_marketplace_loads_only_the_portable_adapters(self):
        plugin = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        pi = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(marketplace['name'], 'kit')
        self.assertEqual(plugin['name'], 'kit')
        self.assertEqual(codex['version'], pi['version'])
        # A pinned version takes precedence over the source commit: `claude plugin
        # update` then reports "already at the latest version" and keeps a stale copy.
        self.assertNotIn('version', plugin)
        # A plugin.json `skills` path adds to the default root skills/ scan, which holds
        # the Hermes-only skills; only the marketplace entry's list replaces that scan.
        for key in ('skills', 'commands', 'agents', 'hooks', 'mcpServers'):
            self.assertNotIn(key, plugin)
        [entry] = marketplace['plugins']
        self.assertEqual(entry['name'], plugin['name'])
        self.assertEqual(entry['source'], './')
        self.assertNotIn('version', entry)
        self.assertEqual(entry['skills'], ['./adapters/skills/'])
        for folder in ('commands', 'agents', 'hooks', 'bin', 'output-styles', 'monitors'):
            self.assertFalse((ROOT / folder).exists(), f'{folder}/ would load as a Claude Code component')
        self.assertFalse((ROOT / '.mcp.json').exists())

    def test_every_portable_adapter_is_explicit_only_in_claude_code_and_pi(self):
        # Claude Code and Pi read `disable-model-invocation`; Codex reads agents/openai.yaml.
        for skill in sorted((ROOT / 'adapters/skills').glob('*/SKILL.md')):
            with self.subTest(adapter=skill.parent.name):
                metadata = yaml.safe_load(skill.read_text().split('---', 2)[1])
                self.assertIs(metadata.get('disable-model-invocation'), True)

    def test_host_contract_keeps_namespaced_planning_invocation(self):
        contract = (ROOT / 'adapters/skills/COMMON.md').read_text()
        self.assertIn('/kit:plan-with-me', contract)

    def test_every_codex_adapter_is_explicit_only(self):
        # Codex treats a missing policy as implicit invocation allowed (TOOLSET-035).
        for skill in sorted((ROOT / 'adapters/skills').glob('*/SKILL.md')):
            with self.subTest(adapter=skill.parent.name):
                policy = skill.parent / 'agents/openai.yaml'
                self.assertTrue(policy.is_file(), f'{policy} is missing')
                data = yaml.safe_load(policy.read_text())
                self.assertIs(data['policy']['allow_implicit_invocation'], False)

    def test_challenge_is_a_planning_mode_and_research_plan_is_not_recursive(self):
        folder = ROOT / 'adapters/skills'
        challenge = (folder / 'grill-me/PROTOCOL.md').read_text()
        self.assertNotIn('name: grill-me', challenge)
        planner = (folder / 'plan-with-me/SKILL.md').read_text()
        self.assertIn('../../../skills/plan-with-me/SKILL.md', planner)
        self.assertIn('../grill-me/SKILL.md', (ROOT / 'skills/plan-with-me/SKILL.md').read_text())
        plan = (folder / 'plan-for-me/SKILL.md').read_text()
        self.assertIn('../../../skills/plan-for-me/SKILL.md', plan)
        self.assertIn('../autoresearch/upstream/plan.md', (ROOT / 'skills/plan-for-me/SKILL.md').read_text())
        self.assertNotIn('../autoresearch/SKILL.md', plan)
        research = (folder / 'autoresearch/SKILL.md').read_text()
        self.assertIn('../plan-for-me/SKILL.md', research)
        selectors = json.loads((ROOT / 'skills/autoresearch/UPSTREAM.json').read_text())['commands']
        self.assertEqual(len(selectors), 13)
        for selector in selectors:
            self.assertIn(selector, research)
            self.assertTrue((ROOT / f'skills/autoresearch/upstream/{selector}.md').is_file())

if __name__ == '__main__': unittest.main()
