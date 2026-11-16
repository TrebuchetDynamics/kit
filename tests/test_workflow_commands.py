"""Public workflow names preserve skill identity, arguments and gateway routing."""
import re
import tomllib
import unittest
from unittest.mock import patch
import yaml
import test_plugin as fixture


class WorkflowCommands(unittest.TestCase):
    setUp = fixture.PluginTests.setUp
    skill = fixture.PluginTests.skill

    def test_new_names_route_to_existing_skills_and_preserve_arguments(self):
        for name in ('plan-with-me', 'plan-for-me', 'docs-sync', 'update-kit', 'autoresearch'):
            self.skill(name)
        self.plugin.register(self.ctx)
        self.session.update(HERMES_SESSION_PLATFORM='telegram', HERMES_SESSION_CHAT_ID='fixture')
        for command, skill in (
                ('plan_with_me', 'plan-with-me'),
                ('docs_sync', 'docs-sync'),
                ('plan_for_me', 'plan-for-me'),
                ('update_kit', 'update-kit')):
            for spelling in (command, command.replace('_', '-')):
                with self.subTest(spelling=spelling):
                    self.assertIn(spelling, self.ctx.commands)
                    raw = ('read-only: compare TODO.md and goals.json\n'
                           '--no-push $(literal); echo "TODO.md" > goals.json')
                    self.ctx.commands[spelling](raw)
                    prompt, routing = self.ctx.messages[-1]
                    self.assertIn('kit:' + skill, prompt)
                    injected, arguments = prompt.split('User arguments:\n', 1)
                    self.assertEqual(arguments, raw)
                    self.assertNotIn('TODO.md', injected)
                    self.assertNotIn('goals.json', injected)
                    self.assertEqual('GitHub Issues are the executable backlog' in injected, skill == 'plan-for-me')
                    self.assertNotIn('`autowork tasks`', injected)
                    self.assertEqual(routing['origin']['chat_id'], 'fixture')
                    if skill.startswith('plan-'):
                        self.assertIn('../shared/RESEARCH-PLAN.md', prompt)
        for alias in ('autoresearch-plan', 'autoresearch:plan'):
            raw = 'questions only\n$(literal); no push'
            self.ctx.commands[alias](raw)
            prompt, _ = self.ctx.messages[-1]
            self.assertIn('Selected subcommand: plan', prompt)
            self.assertIn('../shared/RESEARCH-PLAN.md', prompt)
            self.assertTrue(prompt.endswith(raw))
        self.ctx.commands['autoresearch']('plan ' + raw)
        self.assertIn('../shared/RESEARCH-PLAN.md', self.ctx.messages[-1][0])
        self.assertTrue(self.ctx.messages[-1][0].endswith('plan ' + raw))
        for retired in ('repo-docs', 'repo_docs', 'repo-interview', 'repo_interview'):
            self.assertNotIn(retired, self.ctx.commands)

    def test_orbi_route_forwards_lifecycle_arguments_without_a_service_call(self):
        # `/orbi` is a thin explicit-only route: loading and invoking it forwards the
        # user's words verbatim and runs no service or install command itself.
        self.skill('orbi')
        with patch('subprocess.run') as run:
            self.plugin.register(self.ctx)
            raw = ('setup --dry-run --json\n'
                   '--repo-dir "/tmp/checkout $(literal)"; no push')
            self.ctx.commands['orbi'](raw)
            run.assert_not_called()
        prompt, _ = self.ctx.messages[-1]
        self.assertIn('skill_view(name="kit:orbi")', prompt)
        injected, arguments = prompt.split('User arguments:\n', 1)
        self.assertEqual(arguments, raw)
        self.assertNotIn('checkout', injected)
        self.assertNotIn('../shared/RESEARCH-PLAN.md', prompt)

    def test_update_kit_aliases_preserve_existing_owners(self):
        self.skill('update-kit')
        self.existing['update_kit'] = {'plugin': 'other'}
        self.plugin.register(self.ctx)
        self.assertNotIn('update-kit', self.ctx.commands)
        self.assertNotIn('update_kit', self.ctx.commands)

    def test_update_kit_provisions_complete_helper_and_shared_resources(self):
        self.plugin.SKILLS_DIR = fixture.ROOT / 'skills'
        self.plugin.register(self.ctx)
        installed = self.root.parent / 'home/skills'
        source = fixture.ROOT / 'skills/update-kit'
        self.assertEqual((installed / 'update-kit/SKILL.md').read_bytes(), (source / 'SKILL.md').read_bytes())
        self.assertEqual((installed / 'update-kit/scripts/update_kit.py').read_bytes(),
                         (source / 'scripts/update_kit.py').read_bytes())
        self.assertTrue((installed / 'shared/DEFINITION-OF-DONE.md').is_file())
        raw = '--only pi --hermes-home "space $(literal); home"'
        with patch('subprocess.run') as run:
            self.ctx.commands['update_kit'](raw)
            run.assert_not_called()
        self.assertTrue(self.ctx.messages[-1][0].endswith('User arguments:\n' + raw))

    def test_orbi_route_preserves_an_existing_command_owner(self):
        self.skill('orbi')
        self.existing['orbi'] = {'plugin': 'other'}
        self.plugin.register(self.ctx)
        self.assertNotIn('orbi', self.ctx.commands)

    def test_plan_for_me_is_registered_and_installed_from_its_own_source(self):
        source = fixture.ROOT / 'skills/plan-for-me/SKILL.md'
        self.assertTrue(source.is_file())
        self.plugin.SKILLS_DIR = fixture.ROOT / 'skills'
        self.plugin.register(self.ctx)
        self.assertEqual(self.ctx.skills['plan-for-me'], source)
        self.assertEqual(self.ctx.skills['autoresearch'], fixture.ROOT / 'skills/autoresearch/SKILL.md')
        installed = self.root.parent / 'home/skills/plan-for-me/SKILL.md'
        self.assertEqual(installed.read_bytes(), source.read_bytes())

    def test_bare_plan_for_me_selects_discovery_and_explicit_goals_stay_focused(self):
        self.plugin.SKILLS_DIR = fixture.ROOT / 'skills'
        self.plugin.register(self.ctx)
        for raw in ('', '   '):
            with self.subTest(raw=repr(raw)):
                self.ctx.commands['plan_for_me'](raw)
                prompt = self.ctx.messages[-1][0]
                self.assertIn('Selected route: autonomous project discovery', prompt)
                self.assertIn('do not ask for a goal', prompt)
                self.assertTrue(prompt.endswith('User arguments:\n' + raw))
        self.ctx.commands['plan_for_me']('implement offline support')
        prompt = self.ctx.messages[-1][0]
        self.assertNotIn('Selected route: autonomous project discovery', prompt)
        self.assertTrue(prompt.endswith('implement offline support'))

    def test_planners_publish_evidence_backed_issues_without_legacy_rolling_jobs(self):
        self.plugin.SKILLS_DIR = fixture.ROOT / 'skills'
        self.plugin.register(self.ctx)
        protocol = (fixture.ROOT / 'skills/shared/RESEARCH-PLAN.md').read_text()
        for command, skill in (('plan_for_me', 'plan-for-me'), ('plan_with_me', 'plan-with-me')):
            text = self.ctx.skills[skill].read_text() + protocol
            for required in ('GitHub Issues', 'ai-ready', 'ai-planning', 'blockedBy',
                             'do not create an automatic legacy'):
                self.assertIn(required, text)
            for request in ('port this project to Flutter', 'fix a README typo'):
                self.ctx.commands[command](request)
                self.assertTrue(self.ctx.messages[-1][0].endswith(request))
            self.assertNotIn('autowork tasks add', text)

    def test_plan_for_me_reserves_both_spellings_for_existing_owners(self):
        self.skill('plan-for-me')
        self.existing['plan_for_me'] = {'plugin': 'other'}
        self.plugin.register(self.ctx)
        self.assertNotIn('plan-for-me', self.ctx.commands)
        self.assertNotIn('plan_for_me', self.ctx.commands)

    def test_alias_pair_preserves_existing_command_owner(self):
        self.skill('docs-sync')
        self.existing['docs-sync'] = {'plugin': 'other'}
        self.plugin.register(self.ctx)
        self.assertNotIn('docs-sync', self.ctx.commands)
        self.assertNotIn('docs_sync', self.ctx.commands)
        self.assertNotIn('repo-docs', self.ctx.commands)
        self.assertNotIn('repo_docs', self.ctx.commands)

    def test_retired_local_snapshots_are_not_discovered_or_installed(self):
        for name in ('repo-docs', 'repo-interview', 'docs-sync', 'plan-with-me'):
            self.skill(name)
        discovered = self.plugin._discover_skills()
        self.assertEqual({name for name, _, _ in discovered}, {'docs-sync', 'plan-with-me'})
        self.plugin.register(self.ctx)
        self.assertEqual(set(self.ctx.skills), {'docs-sync', 'plan-with-me'})
        for retired in ('repo-docs', 'repo_docs', 'repo-interview', 'repo_interview'):
            self.assertNotIn(retired, self.ctx.commands)
        self.ctx.commands['docs_sync']('resume')
        self.assertIn('kit:docs-sync', self.ctx.messages[-1][0])

    def test_foreign_retired_command_does_not_block_docs_sync(self):
        self.skill('docs-sync')
        self.existing['repo-docs'] = {'plugin':'other'}
        self.plugin.register(self.ctx)
        self.assertNotIn('repo-docs',self.ctx.commands)
        self.assertNotIn('repo_docs',self.ctx.commands)
        self.assertIn('docs_sync',self.ctx.commands)

    def test_pilot_command_descriptions_are_distinct_and_routed(self):
        router = (fixture.ROOT / 'skills/ask-kit/SKILL.md').read_text()
        descriptions = {}
        for name in ('plan-for-me', 'ponytail-review',
                     'git-commit-push', 'docs-sync', 'plan-with-me'):
            with self.subTest(name=name):
                text = (fixture.ROOT / f'skills/{name}/SKILL.md').read_text()
                metadata = yaml.safe_load(text.split('---', 2)[1])
                descriptions[name] = metadata['description']
                self.assertIn(f'`/{name}`', router)
                self.assertNotIn('use when', metadata['description'].lower())
        self.assertEqual(len(set(descriptions.values())), len(descriptions))

    def test_missing_skills_do_not_advertise_workflows(self):
        self.skill('other')
        self.plugin.register(self.ctx)
        for command in ('docs-sync', 'docs_sync', 'plan-with-me', 'plan-for-me'):
            self.assertNotIn(command, self.ctx.commands)

    def test_catalog_uses_current_names_and_grilling_is_a_mode(self):
        for name in ('plan-with-me', 'plan-for-me', 'docs-sync', 'autoresearch', 'grill-me'):
            self.skill(name)
        self.plugin.register(self.ctx)
        self.assertEqual(set(self.ctx.skills), {'plan-with-me', 'docs-sync', 'plan-for-me', 'autoresearch'})
        self.ctx.commands['grill-me']('challenge my cache plan')
        prompt, _ = self.ctx.messages[-1]
        self.assertIn('skill_view(name="kit:plan-with-me")', prompt)
        self.assertIn('Selected mode: challenge', prompt)
        self.assertNotIn('central work queue', prompt)
        self.assertIn('../shared/RESEARCH-PLAN.md', prompt)
        self.assertTrue(prompt.endswith('challenge my cache plan'))

    def test_foreign_namespace_keeps_its_own_skill_identity(self):
        for name in ('autoresearch', 'plan-for-me'):
            with self.subTest(name=name):
                path = self.skill(name)
                raw = 'read-only: TODO.md; $(literal) > goals.json'
                self.plugin._invoke(self.ctx, name, path, raw, namespace='other')
                prompt = self.ctx.messages[-1][0]
                self.assertIn(f'skill_view(name="other:{name}")', prompt)
                self.assertNotIn('central work queue', prompt)
                self.assertNotIn('../shared/RESEARCH-PLAN.md', prompt)
                self.assertTrue(prompt.endswith('User arguments:\n' + raw))
