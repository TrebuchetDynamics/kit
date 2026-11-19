"""Portable hosts expose adapters rather than Hermes-only worker instructions."""
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
            for name in ('autowork', 'work', 'pending', 'blockers'):
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
        self.assertNotIn('autowork', pi['bin'])
        self.assertFalse(any('pi-autowork' in entry or entry.startswith('src/')
                             for entry in pi['files']))
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
            self.assertFalse((installed / 'pi-autowork').exists())
            self.assertFalse((installed / 'src').exists())
            for root in ('skills', 'adapters/skills'):
                for name in ('autowork', 'work', 'pending', 'blockers'):
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
            self.assertIn('macOS supports status and help; setup/start/stop are refused before side effects.',
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
            self.assertIn('[status|setup|start|update|stop|help]', usage.stdout)
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

    def test_portable_skills_and_references_are_self_contained(self):
        folder = ROOT / 'adapters/skills'
        names = {p.parent.name for p in folder.glob('*/SKILL.md')}
        self.assertEqual(names, {'plan-with-me', 'unblock', 'plan-for-me', 'docs-sync', 'orbi', 'update-kit',
            'autoresearch', 'impeccable', 'lgtm', 'goal',
            'git-commit-push', 'push', 'ui-taste', 'unslop', 'beautify-github-readme',
            'ponytail', 'ponytail-review', 'ponytail-audit', 'ponytail-debt',
            'ponytail-gain', 'ponytail-help', 'bug-harvest',
            'autonomous-codebase-improver', 'split-folder', 'unused-code',
            'test-optimizer', 'apk-get', 'graphify', 'writing-for-agents',
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
