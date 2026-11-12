"""Exercise the offline runner in small copies without importing unsafe tests."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check.py'


class TextualDependencyTests(unittest.TestCase):
    def test_fast_ci_prepares_pinned_textual_before_offline_suites(self):
        import yaml

        steps = yaml.safe_load((ROOT / '.github/workflows/test.yml').read_text())['jobs']['fast']['steps']
        dependency = next(i for i, step in enumerate(steps)
                          if 'pip install -r requirements-test.txt' in step.get('run', ''))
        self.assertIn('uv==0.11.3', steps[dependency]['run'])
        acceptance = (ROOT / 'pi-autowork/tests/runner/test_tui_architecture.py').read_text()
        pin = re.search(r"['\"](textual==[0-9.]+)['\"]", acceptance).group(1)
        cached = next(i for i, step in enumerate(steps) if 'uv run ' in step.get('run', ''))
        self.assertIn('--python 3.12', steps[cached]['run'])
        self.assertIn('--with ' + pin, steps[cached]['run'])
        self.assertIn('import textual', steps[cached]['run'])
        self.assertFalse(steps[cached].get('continue-on-error', False))
        suites = next(i for i, step in enumerate(steps) if 'python scripts/check.py' in step.get('run', ''))
        self.assertLess(dependency, cached)
        self.assertLess(cached, suites)
        self.assertFalse(steps[suites].get('continue-on-error', False))

    def test_optional_checks_skip_only_unavailable_dependencies(self):
        # Replay the saved uv diagnostic at each public unittest seam. A zero
        # exit represents an executed pilot; its original marker checks still apply.
        missing = '''  × No solution found when resolving `--with` dependencies:
  ╰─▶ Because textual was not found in the cache and you require
      textual==8.2.8, we can conclude that your requirements are
      unsatisfiable.

      hint: Packages were unavailable because the network was disabled. When
      the network is disabled, registry packages may only be read from the
      cache.
'''
        legacy = 'error: textual==8.2.8 is not available in the offline cache'
        cases = [
            ('pi-autowork/tests/runner/test_task_prepare.py', 'PackageImportTests',
             'test_every_module_imports_in_isolation_and_all_import_edges_are_acyclic', None),
            ('pi-autowork/tests/runner/test_blockers_report.py', 'BlockersPilotTests',
             'test_pinned_textual_report_interactions', 1),
            ('pi-autowork/tests/runner/test_fleet_view.py', 'FleetViewTests',
             'test_the_tui_drives_the_same_actions_headless', 1),
            ('pi-autowork/tests/runner/test_planning_ui.py', 'PlanningUiTests',
             'test_fleet_answers_preserve_authority_and_stale_edits', 1),
            ('pi-autowork/tests/runner/test_planning_ui.py', 'PlanningUiTests',
             'test_planning_chat_navigation_preview_and_apply', 1),
            ('pi-autowork/tests/runner/test_task_history.py', 'TaskHistoryPilotTests',
             'test_pinned_textual_open_and_closed_navigation', 1),
            *[('pi-autowork/tests/runner/test_tui_controls.py', 'TuiControlsTests', name, 1)
              for name in ('test_answer_mnemonic_portable_save_and_small_screen',
                           'test_compact_forms_and_long_confirmations_keep_controls_visible',
                           'test_fleet_menu_clicks_match_keyboard_without_running_commands')],
            ('pi-autowork/tests/runner/test_tui_layout.py', 'TuiLayoutTests',
             'test_responsive_layout_preserves_evidence_and_read_only_controls', 1),
            *[('pi-autowork/tests/runner/test_tui_mouse.py', 'MouseSelectionTests', name, 1)
              for name in ('test_click_mode_is_opt_in_and_preserved_for_the_browser',
                           'test_terminal_defaults_to_native_drag_selection')],
        ]
        scenarios = [(1, missing, 'skip'), (2, legacy, 'skip'), (0, '', 'pass'),
                     (0, missing, 'pass'), (3, missing, 'fail'),
                     (2, legacy.replace('8.2.8', '8.2.80'), 'fail'),
                     (2, legacy.replace('8.2.8', '8.2.8.post1'), 'fail'),
                     (1, "ModuleNotFoundError: No module named 'textual'", 'fail'),
                     (1, 'AssertionError: pilot failed', 'fail'),
                     (2, 'error: invalid option --offline for textual', 'fail'),
                     (1, missing.replace('textual was not found', 'other was not found'), 'fail'),
                     (1, missing.replace('8.2.8', '9.0.0'), 'fail')]
        with mock.patch.object(sys, 'path', [str(ROOT / 'pi-autowork/tests/runner'), str(ROOT / 'pi-autowork/tests'), str(ROOT / 'pi-autowork/src'), str(ROOT / 'pi-autowork'), *sys.path]), \
                mock.patch('shutil.which', return_value='uv'):
            for path, cls, method, skip_count in cases:
                spec = importlib.util.spec_from_file_location('fixture_' + Path(path).stem, ROOT / path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                expected_skips = len(module.PackageImportTests.RENDERERS) if skip_count is None else skip_count
                for code, stderr, outcome in scenarios:
                    with self.subTest(test=method, code=code, stderr=stderr):
                        def run(command, **kwargs):
                            if command[0] != 'uv':
                                return subprocess.CompletedProcess(command, 0, '', '')
                            self.assertIn('--offline', command)
                            self.assertIn('textual==8.2.8', command)
                            return subprocess.CompletedProcess(command, code, 'LAYOUT PILOT OK', stderr)
                        result = unittest.TestResult()
                        with mock.patch('subprocess.run', side_effect=run):
                            getattr(module, cls)(method).run(result)
                        self.assertEqual(result.errors, [])
                        self.assertEqual(len(result.skipped), expected_skips if outcome == 'skip' else 0)
                        self.assertEqual(bool(result.failures), outcome == 'fail', result.failures)


class OfflineCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='offline checker ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        self.script = self.root / 'scripts/check.py'
        if SCRIPT.exists():
            shutil.copy2(SCRIPT, self.script)

    def write(self, relative, content):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def run_check(self, *args, env=None):
        env = dict(os.environ if env is None else env)
        env.setdefault('PI_AUTOWORK_CHECK_ROOT', str(self.root / 'check-pool'))
        return subprocess.run([sys.executable, str(self.script), *args],
                              cwd=self.root, env=env, text=True,
                              capture_output=True, timeout=15)

    def test_listing_is_import_free_and_uses_owned_directories(self):
        sentinel = "raise RuntimeError('unsafe import must never run')\n"
        self.write('tests/test_unit.py', sentinel)
        self.write('pi-autowork/tests/engine/test_task_execution.py', sentinel)
        self.write('vendor/examples/test_external.py', sentinel)
        self.write('skills/autowork/references/vendor/test_external.py', sentinel)
        self.write('tests/integration_bundle.py', sentinel)
        self.write('tests/integration_plugin.py', sentinel)
        result = self.run_check('--list')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('RUN tests/test_unit.py', result.stdout)
        self.assertIn('RUN pi-autowork/tests/engine/test_task_execution.py', result.stdout)
        self.assertIn('EXCLUDE tests/integration_bundle.py [integration]', result.stdout)
        self.assertIn('EXCLUDE tests/integration_plugin.py [integration]', result.stdout)
        self.assertNotIn('test_external.py', result.stdout)
        self.assertNotIn('unsafe import', result.stdout + result.stderr)

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.email=t@example.invalid', '-c', 'user.name=T', *args],
                              cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def affected_repo(self):
        shutil.copy2(ROOT / 'scripts/affected_tests.py', self.root / 'scripts/affected_tests.py')
        self.git('init', '-q')
        self.git('add', '-A')
        self.git('commit', '-qm', 'base')
        return self.git('rev-parse', 'HEAD')

    def test_affected_fleet_change_runs_importers_and_core_not_unrelated_tests(self):
        self.write('pi-autowork/pi_autowork/fleet_view.py', 'VALUE = 1\n')
        self.write('pi-autowork/pi_autowork/__init__.py', 'from .fleet_view import VALUE\n')
        self.write('pi-autowork/pi_autowork/command.py', 'def view():\n    from . import fleet_view\n')
        self.write('pi-autowork/pi_autowork/sub.py', 'VALUE = 0\n')
        for name, dependency in (('fleet', 'from pi_autowork import fleet_view'),
                                 ('command', 'import command'), ('package', 'import pi_autowork'),
                                 ('dotted', 'import pi_autowork.sub')):
            self.write(f'tests/test_{name}.py',
                       f'import unittest\nif False:\n    {dependency}\n'
                       f'class Check(unittest.TestCase):\n    def test_view(self): print("RAN {name}")\n')
        self.write('tests/test_unrelated.py', 'raise RuntimeError("unselected module ran")\n')
        self.write('scripts/tree_guard.py', 'print("CORE guard")\n')
        self.write('skills/docs-sync/scripts/docs.py', 'print("CORE docs")\n')
        self.write('tasks/items/T.md', '# fixture\n')
        self.write('pi-autowork/bin/autowork', '#!/usr/bin/env python3\nprint("CORE tasks")\n').chmod(0o755)
        base = self.affected_repo()
        self.write('pi-autowork/pi_autowork/fleet_view.py', 'VALUE = 2\n')
        self.git('commit', '-qam', 'fleet change')
        result = self.run_check('--affected', base + '..HEAD', '--jobs', '1')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for text in ('RAN fleet', 'RAN command', 'RAN package', 'RAN dotted',
                     'CORE guard', 'CORE docs', 'CORE tasks',
                     'test_command.py <- pi-autowork/pi_autowork/command.py <- pi-autowork/pi_autowork/fleet_view.py'):
            self.assertIn(text, result.stdout)
        self.assertNotIn('unselected module ran', result.stdout + result.stderr)
        self.assertFalse(list((self.root / 'scripts').glob('__pycache__/*')))

    def test_affected_named_paths_include_tests_and_ambiguous_basename_consumers(self):
        self.write('tests/test_direct.py', 'import unittest\n')
        self.write('tests/test_wrapper.py', 'from pathlib import Path\nPath("tests/test_direct.py")\n')
        self.write('tests/test_reader.py', 'from pathlib import Path\nPath("data") / "config.json"\n')
        self.write('tests/test_unrelated.py', 'import unittest\n')
        self.write('data/config.json', '{}\n')
        self.write('backup/config.json', '{}\n')
        base = self.affected_repo()
        self.write('tests/test_direct.py', 'import unittest\n# changed\n')
        self.git('commit', '-qam', 'test change')
        result = self.run_check('--affected', base + '..HEAD', '--list')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RUN tests/test_direct.py', result.stdout)
        self.assertIn('RUN tests/test_wrapper.py', result.stdout)
        self.assertNotIn('RUN tests/test_unrelated.py', result.stdout)
        self.assertIn('test_wrapper.py <- tests/test_direct.py', result.stdout)
        self.write('tests/test_direct.py', 'import unittest\nDATA = "data/config.json"\n')
        self.git('commit', '-qam', 'direct consumer')
        base = self.git('rev-parse', 'HEAD')
        self.write('data/config.json', '{"value": 2}\n')
        self.git('commit', '-qam', 'data change')
        result = self.run_check('--affected', base + '..HEAD', '--list')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RUN tests/test_direct.py', result.stdout)
        self.assertIn('RUN tests/test_reader.py', result.stdout)
        self.assertNotIn('RUN tests/test_unrelated.py', result.stdout)

    def test_affected_unresolved_and_global_inputs_fall_back_to_full(self):
        self.write('tests/test_one.py', 'import unittest\n')
        self.write('tests/test_two.py', 'import unittest\n')
        self.affected_repo()
        for path in ('unknown.dat', 'pi-autowork/pi_autowork/__init__.py', 'tests/conftest.py', 'pyproject.toml',
                     '.github/workflows/ci.yml', 'scripts/check.py'):
            with self.subTest(path=path):
                base = self.git('rev-parse', 'HEAD')
                target = self.root / path
                self.write(path, target.read_text() + '\n' if target.exists() else '# changed\n')
                self.git('add', '-A'); self.git('commit', '-qm', 'change')
                result = self.run_check('--affected', base + '..HEAD', '--list')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for text in ('whole suite', path, 'RUN tests/test_one.py', 'RUN tests/test_two.py'):
                    self.assertIn(text, result.stdout)
        result = self.run_check('--affected', 'missing..HEAD', '--list')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_selector_retains_deleted_paths_when_git_detects_a_rename(self):
        owner = self.write('owner.py', 'VALUE = 1\n')
        self.write('tests/test_old.py', 'from owner import VALUE\n')
        self.write('tests/test_new.py', 'from owner import VALUE\n')
        base = self.affected_repo()
        for operation in ('rename', 'delete'):
            with self.subTest(operation=operation):
                if operation == 'rename':
                    owner.rename(self.root / 'moved.py')
                    self.write('tests/test_new.py', 'from moved import VALUE\n')
                else:
                    (self.root / 'moved.py').unlink()
                self.git('add', '-A')
                result = subprocess.run([sys.executable, str(self.root / 'scripts/affected_tests.py'),
                                         '--base', base, '--json'], cwd=self.root,
                                        text=True, capture_output=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                selection = json.loads(result.stdout)
                self.assertIn('owner.py', selection['changed'])
                self.assertTrue(selection['full'])
                self.assertEqual(selection['tests'], ['tests/test_new.py', 'tests/test_old.py'])

    def test_source_guard_inspects_owners_not_just_public_shims(self):
        from src_fixture import copy_sources
        copy_sources(self.root)
        self.write('tests/test_one.py', 'import unittest\nclass One(unittest.TestCase):\n    def test_one(self): pass\n')
        self.write('scripts/bundle.py', "bootstrap.execute(globals(), 'pi-autowork/src/autowork_runtime/bundle.py')\n")
        owner = self.write('pi-autowork/src/autowork_runtime/bundle.py', 'def broken(:\n')
        result = self.run_check('tests/test_one.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('pi-autowork/src/autowork_runtime/bundle.py', result.stdout)
        owner.unlink()
        result = self.run_check('tests/test_one.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing selected-release source', result.stdout)
        self.write('pi-autowork/src/autowork_runtime/bundle.py', 'VALUE = 1\n')
        bad = self.write('pi-autowork/pi_autowork/consumer.py', 'import task_store\n')
        result = self.run_check('tests/test_one.py')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unqualified engine import', result.stdout)
        bad.write_text('from .engine import task_store\n')
        result = self.run_check('tests/test_one.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_component_layout_preserves_baseline_inventory_and_partitions(self):
        import hashlib
        import runpy
        fixture = json.loads((ROOT / 'tests/fixtures/python-layout.json').read_text())
        checker = runpy.run_path(str(SCRIPT))
        actual = {p.relative_to(ROOT).as_posix(): p for p in checker['discover_tests'](ROOT)}
        required = {p: set(row['methods']) for p, row in fixture['modules'].items()
                    if row['source'] is not None}
        # Reconcile immutable pre-migration, failed-integration, landed-base and task-base
        # inputs. Only recorded historical renames may remove an original identity.
        renames = {(row['source'], row['old']): row for row in fixture['renames']}
        inputs, removed = {}, set()
        for snapshot in fixture['snapshots']:
            for path, delta in snapshot['delta'].items():
                methods = required.setdefault(path, set())
                for name in delta['removed']:
                    source = fixture['modules'][path]['source'] or path
                    proof = renames[source, name]
                    self.assertIn(proof['new'], delta['added'])
                    self.assertRegex(proof['commit'], r'^[0-9a-f]{40}$')
                    if 'before_input' in proof:
                        self.assertEqual(inputs[path], proof['before_input'])
                        self.assertEqual(snapshot['inputs'][path], proof['after_input'])
                        self.assertEqual(snapshot['revision'], proof['commit'])
                        self.assertRegex(proof['parent'], r'^[0-9a-f]{40}$')
                        for input_path, mode, blob in (proof['before_input'], proof['after_input']):
                            self.assertEqual(input_path, proof['path'])
                            self.assertEqual(mode, '100644')
                            self.assertRegex(blob, r'^[0-9a-f]{40}$')
                    methods.remove(name)
                    removed.add((source, name))
                self.assertFalse(methods & set(delta['added']), (path, 'duplicate addition'))
                methods.update(delta['added'])
            inputs.update(snapshot['inputs'])
            fingerprint = hashlib.sha256(json.dumps(
                {p: sorted(ids) for p, ids in sorted(required.items())}, sort_keys=True).encode()).hexdigest()
            self.assertEqual(fingerprint, snapshot['method_inventory_sha256'], snapshot['role'])
            self.assertEqual(set(inputs), set(required))
        self.assertEqual(removed, set(renames))
        self.assertEqual(set(required), set(fixture['modules']))
        self.assertFalse(set(required) - set(actual), 'lost baseline modules')
        for path, methods in required.items():
            with self.subTest(path=path):
                ids = {name.removeprefix(actual[path].stem + '.')
                       for name in checker['test_ids'](actual[path])}
                self.assertEqual(methods - ids, set(), 'lost baseline methods')
        # Later work may add modules/methods; every current ID still participates in
        # the disjoint/exhaustive shard proof instead of freezing an obsolete count.
        self.assertEqual(checker['SPLIT'], fixture['split'])
        self.assertEqual({p: list(value) for p, value in checker['EXCLUSIONS'].items()}, fixture['exclusions'])
        for name, count in fixture['split'].items():
            groups = list(checker['units'](ROOT, [actual[name]]))
            self.assertEqual(len(groups), count)
            self.assertEqual(sorted(i for _, ids in groups for i in ids),
                             sorted(checker['test_ids'](actual[name])))
        partitions = [[(str(folder.relative_to(ROOT)), name)
                       for folder, names in checker['units'](ROOT, list(actual.values()), shard=(i, 3))
                       for name in names] for i in range(3)]
        observed = set().union(*map(set, partitions))
        self.assertEqual(sum(map(len, partitions)), len(observed))
        expected = {(str(path.parent.relative_to(ROOT)), name)
                    for path in actual.values() for name in checker['test_ids'](path) or [path.stem]}
        self.assertEqual(observed, expected)
        mapping = fixture['tracked_mapping']
        self.assertEqual(len(mapping), len(set(mapping.values())), 'duplicate editable owners')
        for previous, current in mapping.items():
            with self.subTest(previous=previous, current=current):
                # Keep the immutable relocation input; resolve its runner owners
                # through the later approved consolidation, not an edited fixture.
                owner = current.replace('pi-autowork/src/pi_autowork/',
                                        'pi-autowork/pi_autowork/', 1)
                self.assertTrue((ROOT / owner).is_file())
                if owner != current:
                    self.assertFalse((ROOT / current).exists())
                if previous.startswith('src/') or (previous != current and Path(previous).name.startswith('test_')):
                    self.assertFalse((ROOT / previous).exists())

    def test_importable_inventory_is_side_effect_free(self):
        self.assertTrue(SCRIPT.is_file(), 'missing offline checker')
        spec = importlib.util.spec_from_file_location('check_inventory', SCRIPT)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        included = self.write('tests/test_unit.py', "raise RuntimeError('do not import')\n")
        self.assertEqual(checker.discover_tests(self.root), [included])
        alias = self.root / 'checkout-alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(checker.discover_tests(alias), [included])
        (self.root / 'tests/test_link.py').symlink_to(included)
        self.assertEqual(checker.discover_tests(self.root), [included])

    def test_symlinked_directory_components_never_import_external_tests(self):
        cases = (('tests', 'test_external.py'),
                 ('pi-autowork', 'tests/engine/test_external.py'),
                 ('pi-autowork/tests/engine', 'test_external.py'))
        base = self.root
        for index, (link_name, module_name) in enumerate(cases):
            with self.subTest(component=link_name):
                self.root = base / f'case-{index}'
                self.script = self.root / 'scripts/check.py'
                self.script.parent.mkdir(parents=True)
                shutil.copy2(SCRIPT, self.script)
                external = base / f'external-{index}'
                external.mkdir()
                sentinel = external / 'imported'
                module = external / module_name
                module.parent.mkdir(parents=True, exist_ok=True)
                module.write_text(f'from pathlib import Path\nPath({str(sentinel)!r}).touch()\n')
                link = self.root / link_name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(external, target_is_directory=True)
                try:
                    control = ('skills/docs-sync/scripts/test_owned.py'
                               if link_name == 'tests' else 'tests/test_owned.py')
                    self.write(control,
                               'import unittest\nclass Owned(unittest.TestCase):\n'
                               '    def test_owned(self): pass\n')
                    listed = self.run_check('--list')
                    self.assertEqual(listed.returncode, 0, listed.stderr)
                    self.assertNotIn('RUN ' + str(Path(link_name) / module_name), listed.stdout)
                    result = self.run_check()
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('Ran 1 test', result.stdout)
                    self.assertFalse(sentinel.exists(), 'external module was imported')
                finally:
                    link.unlink()

    def test_runs_real_tests_without_live_flags_or_unsafe_imports(self):
        self.write('tests/test_environment.py', '''import os, unittest
class Check(unittest.TestCase):
    def test_environment(self):
        for name in ('CONTAINMENT_LINUX_TESTS', 'RUN_CONTROLLER_BRIDGE_LINUX', 'HERMES_NATIVE_HANDOFF_TEST', 'HERMES_NATIVE_REGISTRATION_TEST',
                     'PI_AUTOWORK_MAIN_CHECK', 'AUTOWORK_CACHE'):
            self.assertFalse(name in os.environ, name + ' leaked into offline tests')
        self.assertEqual(os.environ.get('AUTOWORK_PORT_BASE'), '20300')
        self.assertTrue(os.path.isdir(os.environ['TMPDIR']), 'the offline check must supply TMPDIR')
''')
        self.write('tests/integration_bundle.py',
                   "raise RuntimeError('live integration imported')\n")
        env = dict(os.environ, CONTAINMENT_LINUX_TESTS='1', RUN_CONTROLLER_BRIDGE_LINUX='1',
                   HERMES_NATIVE_HANDOFF_TEST='1', HERMES_NATIVE_REGISTRATION_TEST='1',
                   PI_AUTOWORK_MAIN_CHECK='false', AUTOWORK_CACHE='/elsewhere', AUTOWORK_PORT_BASE='20300')
        result = self.run_check(env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 1 test', result.stdout + result.stderr)
        self.assertIn('1 test directories passed', result.stdout)
        self.assertNotIn('live model imported', result.stdout + result.stderr)

    def test_a_broken_tree_fails_before_any_test_runs(self):
        """Conflict markers twice reached main in Python modules; the tree guard runs first."""
        from src_fixture import copy_sources
        copy_sources(self.root)
        guard = ROOT / 'scripts/tree_guard.py'
        self.assertTrue(guard.is_file(), 'missing tree guard')
        # Every helper check.py runs before the tests, not only the guard: a new one it named
        # (scripts/private_terms.py) failed this fixture in every batch that carried it.
        for name in set(re.findall(r'scripts/(\w+\.py)', SCRIPT.read_text())) | {'tree_guard.py'}:
            if (ROOT / 'scripts' / name).is_file():
                shutil.copy2(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        self.write('tests/test_ran.py', 'import unittest\nfrom pathlib import Path\nclass Ran(unittest.TestCase):\n'
                   "    def test_ran(self): Path('ran').write_text('yes')\n")
        git = lambda *a: subprocess.run(['git', '-c', 'user.email=t@example.invalid', '-c', 'user.name=T', *a],
                                        cwd=self.root, check=True, capture_output=True)
        git('init', '-q')
        self.write('broken.py', 'def f(:\n')
        git('add', '-A')
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('broken.py:1: python', result.stdout)
        self.assertFalse((self.root / 'tests/ran').exists(), 'tests ran on a broken tree')
        self.assertTrue(self.run_check('--list').returncode == 0, 'listing stays import- and check-free')
        self.write('broken.py', 'x = 1\n')
        git('add', '-A')
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('tree_guard: OK', result.stdout)

    def test_tests_the_resource_gate_skipped_are_counted_not_failed(self):
        """TOOLSET-193-54: a busy host is not a failing check."""
        self.write('tests/test_gate.py', '''import sys, unittest
class Gate(unittest.TestCase):
    def test_gated(self):
        print('RESOURCE_GATE_SKIP: resource gate: load average 30.00 >= 24 CPUs', file=sys.stderr)
        raise unittest.SkipTest('host busy')
''')
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Skipped by the host resource gate: 1 test(s)', result.stdout)

    def test_fixtures_can_push_although_the_runner_guards_pushes(self):
        """TOOLSET-186-07: a runner's main check reported 20 failures, all fixture pushes its
        push guard refused; outside the runner the same tree passed."""
        self.write('tests/test_push.py', '''import os, subprocess, tempfile, unittest
class Push(unittest.TestCase):
    def test_push(self):
        with tempfile.TemporaryDirectory() as root:
            git = lambda *a: subprocess.run(['git', '-c', 'user.email=t@example.invalid', '-c', 'user.name=T', *a],
                                           check=True, capture_output=True)
            git('init', '-q', '--bare', root + '/bare')
            git('init', '-q', root + '/work')
            git('-C', root + '/work', 'commit', '-q', '--allow-empty', '-m', 'x')
            git('-C', root + '/work', 'push', '-q', root + '/bare', 'HEAD:refs/heads/main')
        self.assertEqual(os.environ.get('GIT_CONFIG_KEY_0'), 'core.abbrev')  # other settings stay
''')
        guard = {'GIT_CONFIG_COUNT': '3', 'GIT_CONFIG_KEY_0': 'url.pi-autowork-push-disabled:///.pushInsteadOf',
                 'GIT_CONFIG_VALUE_0': '', 'GIT_CONFIG_KEY_1': 'core.abbrev', 'GIT_CONFIG_VALUE_1': '12',
                 'GIT_CONFIG_KEY_2': 'protocol.pi-autowork-push-disabled.allow', 'GIT_CONFIG_VALUE_2': 'never'}
        result = self.run_check(env=dict(os.environ, **guard))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('1 test directories passed', result.stdout)
        with tempfile.TemporaryDirectory() as root:  # the guard itself still refuses pushes
            subprocess.run(['git', 'init', '-q', '--bare', root + '/bare'], check=True)
            pushed = subprocess.run(['git', 'push', root + '/bare', 'HEAD:refs/heads/x'], cwd=ROOT, capture_output=True,
                                    env=dict(os.environ, **guard))
            self.assertNotEqual(pushed.returncode, 0)

    def test_failure_propagates_but_other_directory_still_runs(self):
        self.write('tests/test_failure.py', '''import unittest
class Check(unittest.TestCase):
    def test_failure(self): self.fail('deliberate regression')
''')
        self.write('skills/docs-sync/scripts/test_marker.py', '''from pathlib import Path
import unittest
class Check(unittest.TestCase):
    def test_marker(self): Path('checked').write_text('yes')
''')
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('deliberate regression', result.stdout + result.stderr)
        self.assertTrue((self.root / 'skills/docs-sync/scripts/checked').is_file())

    def test_nonfinite_timeout_is_rejected_before_checks(self):
        marker = self.root / 'executed'
        self.write('tests/test_marker.py',
                   f'from pathlib import Path\nPath({str(marker)!r}).touch()\n')
        for value in ('nan', 'inf', '-inf'):
            with self.subTest(timeout=value):
                marker.unlink(missing_ok=True)
                result = self.run_check(f'--timeout={value}')
                self.assertFalse(marker.exists(), result.stdout + result.stderr)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('--timeout must be positive', result.stderr)
                self.assertNotIn('CHECK', result.stdout)

    def test_invalid_output_bytes_preserve_results_and_other_directories(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                self.write('tests/test_bytes.py',
                           'import os, unittest\nclass Check(unittest.TestCase):\n'
                           '    def test_bytes(self):\n'
                           '        os.write(1, b"diagnostic-\\xff\\n")\n'
                           f'        self.assertFalse({fails!r}, "deliberate failure")\n')
                self.sleeper('skills/docs-sync/scripts/test_control.py', 0, 'control')
                result = self.run_check()
                self.assertEqual(result.returncode, int(fails), result.stdout + result.stderr)
                self.assertIn('diagnostic-\ufffd', result.stdout)
                self.assertIn('OUTPUT-control', result.stdout)
                self.assertIn(f'{2 - int(fails)} test directories passed; {int(fails)} failed',
                              result.stdout)
                self.assertNotIn('UnicodeDecodeError', result.stderr)

    def test_timeout_is_a_failure_not_a_skip(self):
        self.write('tests/test_hang.py', 'import time; time.sleep(3)\n')
        result = self.run_check('--timeout', '0.1')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TIMEOUT', result.stdout)


    def sleeper(self, relative, seconds, marker):
        self.write(relative, f'''import time, unittest
class Check(unittest.TestCase):
    def test_{marker}(self):
        time.sleep({seconds})
        print('OUTPUT-{marker}', flush=True)
''')

    def test_directories_run_concurrently_with_output_in_directory_order(self):
        self.sleeper('tests/test_slow.py', 1.5, 'first')
        self.sleeper('skills/docs-sync/scripts/test_fast.py', 1.5, 'second')
        started = time.monotonic()
        result = self.run_check('--jobs', '2')
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(elapsed, 2.8, 'directories did not overlap')
        out = result.stdout
        self.assertLess(out.index('CHECK tests'), out.index('OUTPUT-first'))
        self.assertLess(out.index('OUTPUT-first'), out.index('CHECK skills/docs-sync/scripts'))
        self.assertLess(out.index('CHECK skills/docs-sync/scripts'), out.index('OUTPUT-second'))
        self.assertTrue(out.rstrip().endswith('Offline result: 2 test directories passed; 0 failed; 0 modules excluded.'))

    def test_modules_of_one_directory_run_concurrently(self):
        self.sleeper('tests/test_slow.py', 1.5, 'first')
        self.sleeper('tests/test_also_slow.py', 1.5, 'second')
        started = time.monotonic()
        result = self.run_check('--jobs', '2')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(time.monotonic() - started, 2.8, 'modules did not overlap')
        self.assertLess(result.stdout.index('OUTPUT-second'), result.stdout.index('OUTPUT-first'))  # module order
        self.assertIn('1 test directories passed', result.stdout)

    def test_selected_split_module_runs_only_its_shards(self):
        progress = self.root / 'modules.json'
        body = ''.join(f'''    def test_{n}(self):
        self.assertNotIn('AUTOWORK_MODULE_PROGRESS', os.environ)
        self.assertEqual(json.loads(Path({str(progress)!r}).read_text()), dict(total=1, completed=0))
        Path('ran-{n}').write_text(str(os.getpid()))
''' for n in range(24))
        module = self.write('pi-autowork/tests/runner/test_pi_autowork.py', 'import json, os, unittest\nfrom pathlib import Path\n'
                            'class Runner(unittest.TestCase):\n' + body)
        self.write('skills/docs-sync/scripts/test_unselected.py', "raise RuntimeError('not selected')\n")
        for paths in (['pi-autowork/tests/runner/test_pi_autowork.py'], ['pi-autowork/tests'], [str(module), 'pi-autowork/tests']):
            with self.subTest(paths=paths):
                for marker in module.parent.glob('ran-*'):
                    marker.unlink()
                result = self.run_check(*paths, env=dict(os.environ, AUTOWORK_MODULE_PROGRESS=str(progress)))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(progress.read_text()), dict(total=1, completed=1))
                self.assertIn('Offline inventory: 1 modules in 1 directories', result.stdout)
                self.assertIn('1 test directories passed; 0 failed', result.stdout)
                pids = [(module.parent / f'ran-{n}').read_text() for n in range(24)]
                self.assertEqual(len(set(pids)), 12)  # two tests per shard, not serial or duplicated
                self.assertNotIn('not selected', result.stdout)
        for marker in module.parent.glob('ran-*'):
            marker.unlink()
        filtered = self.run_check('pi-autowork/tests/runner/test_pi_autowork.py', '-k', 'test_23',
                                  env=dict(os.environ, AUTOWORK_MODULE_PROGRESS=str(progress)))
        self.assertEqual(filtered.returncode, 0, filtered.stdout + filtered.stderr)
        self.assertEqual([p.name for p in module.parent.glob('ran-*')], ['ran-23'])
        self.assertIn('Ran 1 test', filtered.stdout)
        module.write_text(module.read_text() + '    def test_failure(self): self.fail("shard failure")\n')
        failed = self.run_check('pi-autowork/tests/runner/test_pi_autowork.py',
                                env=dict(os.environ, AUTOWORK_MODULE_PROGRESS=str(progress)))
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn('shard failure', failed.stdout)
        for path in ('tests/missing.py', 'vendor', '../outside',
                     'tests/integration_bundle.py'):
            with self.subTest(invalid=path):
                result = self.run_check('pi-autowork/tests/runner/test_pi_autowork.py', path)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('CHECK', result.stdout)

    def test_shards_and_exclusions_split_a_selection_across_machines(self):
        body = ''.join(f'''    def test_{n}(self):
        Path('ran-{n}').write_text(str(os.getpid()))
''' for n in range(24))
        split = self.write('pi-autowork/tests/runner/test_pi_autowork.py', 'import os, unittest\nfrom pathlib import Path\n'
                           'class Runner(unittest.TestCase):\n' + body)
        self.write('pi-autowork/tests/runner/test_other.py', 'import unittest\nfrom pathlib import Path\n'
                   'class Other(unittest.TestCase):\n'
                   "    def test_a(self): Path('ran-other-a').write_text('')\n"
                   "    def test_b(self): Path('ran-other-b').write_text('')\n")
        # Tests the inventory cannot list without importing run whole, on the first shard only.
        self.write('pi-autowork/tests/runner/test_dynamic.py', 'import unittest\nfrom pathlib import Path\n'
                   'def load_tests(loader, tests, pattern):\n'
                   "    return unittest.TestSuite([unittest.FunctionTestCase(lambda: Path('ran-dynamic').write_text(''))])\n")
        folder = split.parent
        seen = {}
        for shard in ('1/3', '2/3', '3/3'):
            for marker in folder.glob('ran-*'):
                marker.unlink()
            result = self.run_check('pi-autowork/tests', '--shard', shard)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f'Shard {shard[0]} of 3', result.stdout)
            seen[shard] = {p.name for p in folder.glob('ran-*')}
        self.assertEqual(set.union(*seen.values()), {f'ran-{n}' for n in range(24)} | {'ran-other-a', 'ran-other-b', 'ran-dynamic'})
        self.assertEqual(len(seen['1/3'] & seen['2/3'] & seen['3/3']), 0)
        self.assertEqual([shard for shard, names in seen.items() if 'ran-dynamic' in names], ['1/3'])
        self.assertEqual(sorted(len(names & {f'ran-{n}' for n in range(24)}) for names in seen.values()), [8, 8, 8])
        for marker in folder.glob('ran-*'):
            marker.unlink()
        result = self.run_check('pi-autowork/tests', '--exclude', 'pi-autowork/tests/runner/test_pi_autowork.py', '--exclude', 'pi-autowork/tests/runner/test_dynamic.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({p.name for p in folder.glob('ran-*')}, {'ran-other-a', 'ran-other-b'})
        self.assertIn('Offline inventory: 1 modules', result.stdout)
        for invalid in (('--exclude', 'tests/missing.py'), ('--exclude', '../outside'), ('--shard', '4/3'), ('--shard', 'x')):
            with self.subTest(invalid=invalid):
                result = self.run_check('pi-autowork/tests', *invalid)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('CHECK', result.stdout)

    def test_default_jobs_follow_idle_cpus_between_four_and_eight(self):
        from unittest import mock
        spec = importlib.util.spec_from_file_location('check_jobs', SCRIPT)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        # (cpus, load, jobs for a niced check from the load average, jobs from busy CPUs, rounded up)
        # Keep the baseline method identity; the accepted range is now one to two.
        for cpus, load, jobs, unniced in ((22, 0.5, 2, 2), (22, 16.2, 2, 2), (22, 30.0, 1, 1), (2, 0.0, 2, 2)):
            # A niced check (a worker's own) counts the whole load average, as before.
            with self.subTest(cpus=cpus, load=load), mock.patch.object(checker.os, 'cpu_count', return_value=cpus), \
                    mock.patch.object(checker.os, 'getpriority', return_value=10), \
                    mock.patch.object(checker.os, 'getloadavg', return_value=(load, load, load)):
                self.assertEqual(checker.default_jobs(), jobs)
            # The integration check, not niced, counts only CPU busy at normal priority: niced
            # workers yield to it (the load average read 23 on 24 CPUs that were 80% idle).
            with self.subTest(cpus=cpus, busy=load), mock.patch.object(checker.os, 'cpu_count', return_value=cpus), \
                    mock.patch.object(checker.os, 'getpriority', return_value=0), \
                    mock.patch.object(checker, 'busy_cpus', return_value=load), \
                    mock.patch.object(checker.os, 'getloadavg', side_effect=AssertionError('load average read')):
                self.assertEqual(checker.default_jobs(), unniced)

    def test_busy_cpus_leave_out_niced_time(self):
        from unittest import mock
        spec = importlib.util.spec_from_file_location('check_busy', SCRIPT)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        # user nice system idle iowait irq softirq steal: 1000 ticks, 600 of them niced, 200 idle
        samples = iter([[0] * 8, [100, 600, 100, 200, 0, 0, 0, 0]])
        with mock.patch.object(checker, '_cpu_times', side_effect=lambda: next(samples)), \
                mock.patch.object(checker.os, 'cpu_count', return_value=10), \
                mock.patch.object(checker.time, 'sleep'):
            self.assertAlmostEqual(checker.busy_cpus(), 2.0)  # 200 of 1000 ticks busy at normal priority

    def test_jobs_one_runs_sequentially_with_the_same_output(self):
        self.sleeper('tests/test_slow.py', 1, 'first')
        self.sleeper('skills/docs-sync/scripts/test_fast.py', 1, 'second')
        started = time.monotonic()
        sequential = self.run_check('--jobs', '1')
        self.assertGreaterEqual(time.monotonic() - started, 2)
        concurrent = self.run_check('--jobs', '2')
        for result in (sequential, concurrent):
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        strip = lambda text: [line for line in text.splitlines() if not line.startswith(('Ran ', '---', 'OK'))]
        self.assertEqual(strip(sequential.stdout), strip(concurrent.stdout))

    def test_explicit_jobs_cannot_oversubscribe_a_check(self):
        self.sleeper('tests/test_one.py', 0, 'one')
        spec = importlib.util.spec_from_file_location('check_capacity', self.script)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        with mock.patch.object(checker, 'ThreadPoolExecutor', wraps=checker.ThreadPoolExecutor) as pool, \
                mock.patch.object(checker, 'run_unit', return_value=(True, '')):
            self.assertEqual(checker.main(['tests/test_one.py', '--jobs', '32']), 0)
        self.assertEqual(pool.call_args.kwargs['max_workers'], 2)

    def test_provision_keeps_the_inherited_fleet_lease(self):
        self.write('requirements-test.txt', '')
        spec = importlib.util.spec_from_file_location('check_provision', self.script)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        capacity = mock.Mock()
        capacity.inherited_check_lease.return_value = 17
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(checker.sys, 'version_info', (3, 14)), \
                mock.patch.object(checker.shutil, 'which', return_value='/fixture/uv'), \
                mock.patch.object(checker, 'check_capacity', return_value=capacity), \
                mock.patch.object(checker.subprocess, 'run', return_value=mock.Mock(returncode=0)) as run:
            self.assertEqual(checker.provision(self.root), 0)
        self.assertEqual(run.call_args.kwargs['pass_fds'], (17,))

    def test_direct_focused_checker_joins_the_fleet_pool(self):
        from src_fixture import copy_sources
        from pi_autowork import main_check
        copy_sources(self.root)
        marker = self.root / 'ran'
        self.write('tests/test_one.py', 'import unittest\nfrom pathlib import Path\n'
                   'class One(unittest.TestCase):\n'
                   f'    def test_one(self): Path({str(marker)!r}).touch()\n')
        log = self.root / 'checker.log'
        with mock.patch.dict(os.environ, PI_AUTOWORK_CHECK_ROOT=str(self.root / 'pool'),
                             PI_AUTOWORK_CHECK_SLOTS='1'):
            for wrapped in (False, True):
                with self.subTest(wrapped=wrapped):
                    marker.unlink(missing_ok=True)
                    command = [sys.executable, str(self.script), 'tests/test_one.py', '-k', 'one']
                    if wrapped:
                        command = [sys.executable, str(ROOT / 'pi-autowork/engine/autowork_run.py'), *command]
                    with log.open('w') as output, main_check.check_slot(lambda _: self.fail('private pool busy')):
                        child = subprocess.Popen(command, cwd=self.root, env=os.environ,
                                                 stdout=output, stderr=subprocess.STDOUT)
                        self.addCleanup(child.wait)
                        self.addCleanup(lambda c=child: c.poll() is None and c.kill())
                        deadline = time.monotonic() + 15
                        while 'queued for a fleet slot' not in log.read_text():
                            self.assertIsNone(child.poll(), log.read_text())
                            self.assertLess(time.monotonic(), deadline, log.read_text())
                            time.sleep(.02)
                        self.assertFalse(marker.exists())
                    self.assertEqual(child.wait(timeout=15), 0, log.read_text())
                    self.assertTrue(marker.exists())

    def test_jobs_must_be_a_positive_integer(self):
        for value in ('0', '-1', 'x'):
            with self.subTest(jobs=value):
                result = self.run_check('--jobs', value)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('CHECK', result.stdout)

    def test_concurrent_timeout_fails_only_its_directory(self):
        self.write('tests/test_hang.py', 'import time; time.sleep(5)\n')
        self.sleeper('skills/docs-sync/scripts/test_fast.py', 0, 'second')
        result = self.run_check('--timeout', '1')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('TIMEOUT: ', result.stdout)
        self.assertIn('OUTPUT-second', result.stdout)
        self.assertIn('1 test directories passed; 1 failed', result.stdout)

if __name__ == '__main__':
    unittest.main()
