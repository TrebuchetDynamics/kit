"""Portable hosts expose adapters rather than Hermes-only worker instructions."""
import json
from pathlib import Path
import re
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class PortablePackageTests(unittest.TestCase):
    def test_only_the_required_hermes_adapter_is_python_at_root(self):
        self.assertEqual({p.name for p in ROOT.glob('*.py')}, {'__init__.py'})

    def test_native_manifests_select_portable_resources(self):
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        pi = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(codex['skills'], './adapters/skills/')
        self.assertEqual(pi['pi']['skills'], ['./adapters/skills'])
        self.assertEqual(pi['pi']['extensions'], ['./adapters/pi.mjs'])
        self.assertNotIn('scripts', pi, 'installation must not run setup hooks')
        for entry in ('scripts/autowork_bootstrap.py', 'src/autowork_bootstrap.py', 'src/pi_autowork/'):
            self.assertIn(entry, pi['files'])
        self.assertNotIn('src/', pi['files'], 'native-only sources must not leak into npm')
        self.assertNotIn('src/autowork_runtime/', pi['files'])
        marketplace = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text())
        self.assertEqual(marketplace['plugins'][0]['source'], {'source': 'local', 'path': '.'})

    def test_portable_skills_and_references_are_self_contained(self):
        folder = ROOT / 'adapters/skills'
        names = {p.parent.name for p in folder.glob('*/SKILL.md')}
        self.assertEqual(names, {'plan-with-me', 'blockers', 'unblock', 'plan-for-me', 'docs-sync', 'autowork', 'work',
            'autoresearch', 'impeccable', 'lgtm', 'goal',
            'git-commit-push', 'push', 'ui-taste', 'beautify-github-readme', 'pending',
            'ponytail', 'ponytail-review', 'ponytail-audit', 'ponytail-debt',
            'ponytail-gain', 'ponytail-help', 'bug-harvest',
            'autonomous-codebase-improver', 'split-folder', 'unused-code',
            'test-optimizer', 'apk-get', 'graphify', 'writing-for-agents',
            'grilling', 'grill-with-docs', 'improve-codebase-architecture', 'ask-kit',
            'responsive-screenshots'})
        for source in folder.rglob('*.md'):
            text = source.read_text()
            if source.name == 'SKILL.md':
                metadata = yaml.safe_load(text.split('---', 2)[1])
                self.assertEqual(metadata['name'], source.parent.name)
                self.assertIsInstance(metadata['description'], str)
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((source.parent / link.split('#')[0]).exists(), (source, link))
        worker = (folder / 'autowork/SKILL.md').read_text()
        self.assertNotIn('start_goal.py', worker)
        self.assertNotIn('finish_task.py', worker)

    def test_work_selects_and_continues_here_without_the_runner_first_route(self):
        adapter = (ROOT / 'adapters/skills/work/SKILL.md').read_text()
        skill = ' '.join((ROOT / 'skills/work/SKILL.md').read_text().split())
        self.assertIn('../../../skills/work/SKILL.md', adapter)
        self.assertNotIn('../autowork/SKILL.md', adapter)
        for required in ('No task argument is required', 'current session',
                         'autowork tasks list', 'autowork tasks why ID',
                         'canonical selection order', 'A supplied task ID or scope narrows selection',
                         'as many eligible tasks as it can',
                         'When the queue is empty or all open tasks are gated',
                         'repository-maintenance.md', 'source, tests, docs and existing user flows',
                         'then select the next task automatically',
                         'One completed task is not a stop condition',
                         'An explicit one-task or named-task limit wins',
                         'Preserve live and owner-only tasks as pending',
                         'Named-task-only requests stay on that task',
                         'no useful eligible work', 'Do not invent busywork',
                         'read-only requests read-only',
                         'fresh context window', 'read-only permission',
                         '../autowork/SKILL.md', '../shared/DEFINITION-OF-DONE.md'):
            self.assertIn(required, skill)
        self.assertNotIn('autowork start .', skill)
        self.assertNotIn('Stop after one task by default', skill)
        self.assertNotIn('Stop rather than inventing a task', skill)
        execution = ' '.join((ROOT / 'skills/autowork/SKILL.md').read_text().split())
        self.assertIn('autowork tasks done ID --by WHO --reason TEXT [--evidence REF]', execution)
        self.assertIn('Manual, not Verified', execution)
        closeout = ' '.join((ROOT / 'skills/autowork/references/iteration-and-decisions.md').read_text().split())
        self.assertIn('autowork tasks done ID --by WHO --reason TEXT [--evidence REF]', closeout)
        self.assertIn('Manual, not Verified', closeout)
        self.assertIn('/work', (ROOT / 'adapters/skills/autowork/SKILL.md').read_text())

    def test_claude_code_marketplace_loads_only_the_portable_adapters(self):
        plugin = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
        pi = json.loads((ROOT / 'package.json').read_text())
        self.assertEqual(plugin['name'], 'kit')
        self.assertEqual(plugin['version'], codex['version'])
        self.assertEqual(plugin['version'], pi['version'])
        # A plugin.json `skills` path adds to the default root skills/ scan, which holds
        # the Hermes-only skills; only the marketplace entry's list replaces that scan.
        for key in ('skills', 'commands', 'agents', 'hooks', 'mcpServers'):
            self.assertNotIn(key, plugin)
        [entry] = marketplace['plugins']
        self.assertEqual(entry['name'], plugin['name'])
        self.assertEqual(entry['source'], './')
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
        self.assertIn('../grill-me/PROTOCOL.md', planner)
        plan = (folder / 'plan-for-me/SKILL.md').read_text()
        self.assertIn('../../../skills/autoresearch/upstream/plan.md', plan)
        self.assertNotIn('../autoresearch/SKILL.md', plan)
        research = (folder / 'autoresearch/SKILL.md').read_text()
        self.assertIn('../plan-for-me/SKILL.md', research)
        selectors = json.loads((ROOT / 'skills/autoresearch/UPSTREAM.json').read_text())['commands']
        self.assertEqual(len(selectors), 13)
        for selector in selectors:
            self.assertIn(selector, research)
            self.assertTrue((ROOT / f'skills/autoresearch/upstream/{selector}.md').is_file())

if __name__ == '__main__': unittest.main()
