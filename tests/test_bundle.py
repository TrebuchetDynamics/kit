import argparse
import json
import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'scripts/bundle.py').exists(), 'Missing bundle integration')
        spec = importlib.util.spec_from_file_location('bundle_test', ROOT / 'scripts/bundle.py')
        self.bundle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bundle)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'SKILL.md'
        self.path.write_text('skill')
        self.commands = {'ponytail-review': {'plugin': 'ponytail', 'handler': object()}}
        self.skills = ['ponytail:ponytail', 'ponytail:ponytail-review', 'hermes-speech:configure-allmodels-speech']
        self.manager = types.SimpleNamespace(
            _cli_commands={},
            list_plugin_skill_metadata=lambda: [{'name': n} for n in self.skills],
            find_plugin_skill=lambda n: self.path,
        )
        self.ctx = types.SimpleNamespace(
            register_command=self.register_command,
            get_config=lambda key, default=None: default,
        )
        self.messages = []
        stubs = {
            'hermes_cli.plugins': types.SimpleNamespace(get_plugin_manager=lambda: self.manager,
                                                        get_plugin_commands=lambda: self.commands),
            'hermes_cli.commands': types.SimpleNamespace(resolve_command=lambda n: object() if n == 'help' else None),
        }
        p = patch.dict('sys.modules', stubs)
        p.start()
        self.addCleanup(p.stop)

    def register_command(self, name, handler, description='', args_hint=''):
        self.commands[name] = {'handler': handler, 'plugin': 'kit'}

    def invoke(self, ctx, name, path, args, namespace='kit'):
        self.messages.append((namespace, name, args))

    def test_chat_maintenance_helpers_are_removed(self):
        for name in ('handle_chat', 'maintenance_reply', 'start_update', 'update_status',
                     'list_commands', 'overview'):
            self.assertFalse(hasattr(self.bundle, name), name)

    def test_terminal_parser_keeps_only_supported_actions(self):
        parser = argparse.ArgumentParser()
        self.bundle.setup_parser(parser)
        for action in ('update', 'setup', 'finalize', 'pin', 'doctor'):
            argv = {'finalize': ['--hermes-home', '/fixture'], 'pin': ['fixture']}.get(action, [])
            self.assertEqual(parser.parse_args([action, *argv]).action, action)
        self.assertEqual(set(parser._subparsers._group_actions[0].choices),
                         {'update', 'setup', 'finalize', 'pin', 'doctor'})

    def test_terminal_update_waits_prints_receipt_and_preserves_exit(self):
        import subprocess
        source = Path(self.tmp.name) / 'source'
        (source / 'scripts').mkdir(parents=True)
        (source / 'scripts/update_bundle.py').write_text(
            'import json, os, sys\n'
            'code = int(os.environ["FIXTURE_EXIT"])\n'
            'print(json.dumps({"status": "incomplete" if code else "complete", "arguments": sys.argv[1:], '
            '"action": "Repair fixture source before retrying." if code else ""}), flush=True)\n'
            'raise SystemExit(code)\n')
        # Invoke the public terminal handler in a child so its inherited stdout is real.
        code = (
            'import argparse, importlib.util, types; from pathlib import Path; '
            f'spec=importlib.util.spec_from_file_location("fixture_bundle", {str(ROOT / "scripts/bundle.py")!r}); '
            'm=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); '
            f'm.ROOT=Path({str(source)!r}); '
            'commands={}; m.register_imported_skills=lambda *a: None; '
            'import sys; sys.modules["hermes_cli.plugins"]=types.SimpleNamespace('
            'get_plugin_manager=lambda: types.SimpleNamespace(_cli_commands={})); '
            'ctx=types.SimpleNamespace(register_cli_command=lambda name, **kw: commands.update({name: kw})); '
            'm.register_bundle(ctx, None); '
            'assert set(commands) == {"kit"}; '
            'p=argparse.ArgumentParser(prog="hermes"); sub=p.add_subparsers(required=True); '
            'kit=sub.add_parser("kit"); commands["kit"]["setup_fn"](kit); '
            'kit.set_defaults(func=commands["kit"]["handler_fn"]); '
            'args=p.parse_args(["kit", "update", "--check", "--hermes-home", "/fixture home"]); '
            'raise SystemExit(args.func(args))'
        )
        import os
        for expected_code in (0, 7):
            with self.subTest(exit=expected_code):
                result = subprocess.run([__import__('sys').executable, '-c', code],
                                        env=dict(os.environ, FIXTURE_EXIT=str(expected_code)),
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, expected_code, result.stderr)
                receipt = json.loads(result.stdout)
                self.assertEqual(receipt['status'], 'incomplete' if expected_code else 'complete')
                self.assertEqual(receipt['arguments'], ['--hermes-home', '/fixture home', '--check'])
                self.assertEqual(receipt['action'], 'Repair fixture source before retrying.' if expected_code else '')

    def test_inventory_keeps_optional_ponytail_handlers_for_upgrade_readiness(self):
        names = {p.parent.name for p in (ROOT / 'skills').glob('*/SKILL.md')}
        self.commands = {name: {'plugin': 'kit', 'handler': object()} for name in names}
        self.commands['ponytail-review']['plugin'] = 'ponytail'
        self.skills = ['kit:' + name for name in names]
        self.manager.home_path = Path(self.tmp.name)
        self.manager.discover_and_load = lambda: None
        plugins = [{'name': 'kit', 'enabled': True}, {'name': 'ponytail', 'enabled': True}]
        self.manager.list_plugins = lambda: plugins
        stubs = {
            'hermes_cli.commands_platforms': types.SimpleNamespace(
                telegram_menu_commands=lambda **_: ([], []), telegram_menu_max_commands=lambda: 100),
            'agent.skill_commands': types.SimpleNamespace(get_skill_commands=lambda: {}),
        }
        spec = importlib.util.spec_from_file_location('ponytail_setup_inventory', ROOT / 'scripts/setup_runtime.py')
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        with patch.dict('sys.modules', stubs):
            report = self.bundle.inventory()
            self.assertIn('ponytail-review', [r['command'] for r in report['commands'] if r['source'] == 'ponytail'])
            diagnosed = self.bundle.diagnose(report, core_only=True)
            self.assertEqual(diagnosed['status'], 'ready', diagnosed)
            self.assertEqual(diagnosed['bundled_skill_fallbacks'], ['kit:ponytail-review'])
            installed, code = runtime.finish_profile(ROOT, Path(self.tmp.name), Path(self.tmp.name),
                                                      report, bundle_only=True, no_reload=True)
            self.assertEqual(code, 0, installed)
            self.assertNotIn('ponytail', report['missing_plugins'])
            plugins.pop()
            self.commands['ponytail-review']['plugin'] = 'kit'
            report = self.bundle.inventory()
            self.assertNotIn('ponytail', report['missing_plugins'])
            self.assertEqual(self.bundle.diagnose(report, core_only=True)['status'], 'ready')

    def test_imported_skills_get_commands_without_overwriting_native_handlers(self):
        native = self.commands['ponytail-review']['handler']
        self.bundle.register_imported_skills(self.ctx, self.invoke)
        self.assertIs(self.commands['ponytail-review']['handler'], native)
        self.commands['configure-allmodels-speech']['handler']('full')
        self.assertEqual(self.messages, [('hermes-speech', 'configure-allmodels-speech', 'full')])
        self.assertNotIn('ponytail', self.commands, 'Ponytail is bundled, not an imported alias')

    def test_builtin_collision_uses_plugin_prefix(self):
        self.skills = ['hermes-speech:help']
        self.bundle.register_imported_skills(self.ctx, self.invoke)
        self.assertNotIn('help', self.commands)
        self.commands['hermes-speech-help']['handler']('details')
        self.assertEqual(self.messages, [('hermes-speech', 'help', 'details')])

    def test_long_imported_skill_names_have_stable_telegram_safe_alias(self):
        self.skills = ['hermes-speech:' + 'long-name-' * 6]
        first = self.bundle.register_imported_skills(self.ctx, self.invoke)
        name = next(iter(first))
        self.assertLessEqual(len(name), 32)
        self.assertRegex(name, r'^[a-z0-9-]+$')
        self.commands.clear()
        self.assertEqual(first, self.bundle.register_imported_skills(self.ctx, self.invoke))

    def test_unlisted_plugin_skills_are_not_exported(self):
        self.skills = ['other:secret']
        self.assertEqual(self.bundle.register_imported_skills(self.ctx, self.invoke), {})

    def test_setup_uses_complete_orchestrator_and_preserves_arguments(self):
        args = argparse.Namespace(action='setup', dry_run=True, hermes_home='/tmp/home with spaces',
                                  yes_deps=True, bundle_only=True, no_reload=True)
        with patch.object(self.bundle.subprocess, 'run', return_value=types.SimpleNamespace(returncode=7)) as run:
            self.assertEqual(self.bundle.handle_cli(args), 7)
        self.assertEqual(run.call_args.args[0], ['python3', str(ROOT / 'scripts/setup_bundle.py'),
            '--dry-run', '--yes-deps', '--bundle-only', '--no-reload', '--hermes-home', '/tmp/home with spaces'])
        self.assertNotIn('shell', run.call_args.kwargs)

    def test_update_uses_selected_profiles_root_without_explicit_override(self):
        import sys
        parser = argparse.ArgumentParser()
        self.bundle.setup_parser(parser)
        root = Path(self.tmp.name) / 'hermes root'
        for home in (root, root / 'profiles/work'):
            with self.subTest(home=home), \
                 patch.dict('sys.modules', {'hermes_constants': types.SimpleNamespace(get_hermes_home=lambda: home)}), \
                 patch.object(self.bundle.subprocess, 'run', return_value=types.SimpleNamespace(returncode=7)) as run:
                self.assertEqual(self.bundle.handle_cli(parser.parse_args(['update'])), 7)
            run.assert_called_once_with([sys.executable, str(ROOT / 'scripts/update_bundle.py'),
                                         '--hermes-home', str(root)], cwd=ROOT, check=False)

    def test_finalize_forwards_profile_scope_options_and_preserves_receipt_exit(self):
        import contextlib
        import io
        parser = argparse.ArgumentParser()
        self.bundle.setup_parser(parser)
        args = parser.parse_args(['finalize', '--hermes-home', '/fixture home',
                                  '--bundle-only', '--no-reload'])
        runtime = self.bundle._KIT_COMPAT.peer(vars(self.bundle), 'setup_runtime')
        report = {'fixture': 'selected profile inventory'}
        receipt = {'status': 'incomplete', 'action': 'Repair fixture registration.'}
        output = io.StringIO()
        with patch.object(self.bundle, 'inventory', return_value=report), \
             patch.object(runtime, 'finalize', return_value=(receipt, 7)) as finalize, \
             contextlib.redirect_stdout(output):
            self.assertEqual(self.bundle.handle_cli(args), 7)
        finalize.assert_called_once_with(ROOT, report, args)
        self.assertEqual((args.hermes_home, args.bundle_only, args.no_reload),
                         ('/fixture home', True, True))
        self.assertEqual(json.loads(output.getvalue()), receipt)

    def test_setup_parser_requires_action_and_supports_doctor(self):
        parser = argparse.ArgumentParser()
        self.bundle.setup_parser(parser)
        args = parser.parse_args(['doctor', '--json'])
        self.assertEqual(args.action, 'doctor')
        self.assertTrue(args.json)

    def external_source_fixture(self):
        source=Path(self.tmp.name)/'source';(source/'plugins').mkdir(parents=True)
        (source/'plugins/defaults.json').write_bytes((ROOT/'plugins/defaults.json').read_bytes())
        (source/'plugins/PLUGINS.md').write_text('skills https://github.com/example/optional-skills all profiles\n')
        return source

    def test_missing_imports_track_partial_install_and_removed_commands(self):
        home = Path(self.tmp.name)
        source=self.external_source_fixture()
        self.bundle.record_skill_repository(home, 'https://github.com/example/optional-skills', ['alpha', 'beta'])
        with patch.object(self.bundle,'ROOT',source):
            missing, unchecked = self.bundle.missing_skill_imports(home, {'alpha', 'graphify', 'sample-plan'})
        self.assertEqual(missing, ['beta'])
        self.assertEqual(unchecked, [])

    def test_unattempted_skill_repository_is_not_reported_healthy(self):
        source=self.external_source_fixture()
        with patch.object(self.bundle,'ROOT',source):
            missing, unchecked = self.bundle.missing_skill_imports(Path(self.tmp.name), {'graphify', 'sample-plan'})
        self.assertEqual(missing, [])
        self.assertEqual(unchecked, ['https://github.com/example/optional-skills'])

    def test_retired_external_addy_inventory_does_not_require_duplicate_imports(self):
        home=Path(self.tmp.name)
        self.bundle.record_skill_repository(home,'https://github.com/addyosmani/agent-skills',['old-import'])
        missing,unchecked=self.bundle.missing_skill_imports(home,{'graphify','sample-plan'})
        self.assertNotIn('old-import',missing)
        self.assertNotIn('https://github.com/addyosmani/agent-skills',unchecked)

    def test_named_profiles_do_not_require_or_export_unlisted_plugins(self):
        self.manager.home_path = Path(self.tmp.name) / 'profiles/coder'
        self.manager.discover_and_load = lambda: None
        self.manager.list_plugins = lambda: []
        modules = {
            'hermes_cli.commands_platforms': types.SimpleNamespace(
                telegram_menu_commands=lambda **kw: ([], 0), telegram_menu_max_commands=lambda: 100),
            'agent.skill_commands': types.SimpleNamespace(get_skill_commands=lambda: {}),
        }
        with patch.dict('sys.modules', modules):
            report = self.bundle.inventory()
        self.assertNotIn('example-plugin', report['missing_plugins'])
        self.skills = ['example-plugin:example-plugin']
        self.assertEqual(self.bundle.register_imported_skills(self.ctx, self.invoke), {})
        self.assertNotIn('example-plugin', (ROOT / 'plugins/PLUGINS.md').read_text())
        self.assertNotIn('example-plugin', (ROOT / 'plugin.yaml').read_text())

    def test_optional_hindsight_is_not_part_of_bundle_inventory(self):
        self.manager.home_path = Path(self.tmp.name)
        self.manager.discover_and_load = lambda: None
        self.manager.list_plugins = lambda: [{'name': 'hindsight', 'kind': 'exclusive',
            'enabled': False, 'error': 'exclusive plugin — activate via <category>.provider config'}]
        modules = {
            'hermes_cli.commands_platforms': types.SimpleNamespace(
                telegram_menu_commands=lambda **kw: ([], 0), telegram_menu_max_commands=lambda: 100),
            'agent.skill_commands': types.SimpleNamespace(get_skill_commands=lambda: {}),
            'hermes_cli.config': types.SimpleNamespace(load_config_readonly=lambda: {'memory': {'provider': 'hindsight'}}),
            'plugins.memory': types.SimpleNamespace(load_memory_provider=lambda *a, **kw:
                types.SimpleNamespace(is_available=lambda: True)),
        }
        with patch.dict('sys.modules', modules):
            report = self.bundle.inventory()
        self.assertNotIn('hindsight', report['missing_plugins'])
        self.assertEqual(report['plugins'], [])



if __name__ == '__main__':
    unittest.main()
