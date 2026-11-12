"""scripts/affected_tests.py selects the test modules a change can reach, with the reason."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import affected_tests  # noqa: E402


SELF = 'tests/test_affected_tests.py'  # names the paths below, so it is selected by them too


class AffectedTestsTests(unittest.TestCase):
    def test_extensionless_binary_is_not_decoded_as_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'build').mkdir()
            (root / 'bin').mkdir()
            (root / 'tests').mkdir()
            binary = root / 'build/program'
            binary.write_bytes(b'\x7fELF\0' + b'x' * 10000)
            (root / 'bin/tool').write_text('#!/bin/sh\necho fixture\n')
            (root / 'tests/test_tool.py').write_text('TOOL = "bin/tool"\n')
            files = ['build/program', 'bin/tool', 'tests/test_tool.py']
            original = Path.read_text
            def guarded(path, *args, **kwargs):
                self.assertNotEqual(path, binary, 'binary reached full text decoding')
                return original(path, *args, **kwargs)
            with patch.object(affected_tests, 'ROOT', root), \
                 patch.object(affected_tests, 'git', side_effect=['\n'.join(files[1:]), files[0]]), \
                 patch.object(Path, 'read_text', guarded):
                admitted = affected_tests.repository_files()
                self.assertNotIn('build/program', admitted)
                graph = affected_tests.dependency_graph(files, tests=['tests/test_tool.py'])
                self.assertNotIn('build/program', graph)
                self.assertIn('bin/tool', graph['tests/test_tool.py'])

    def test_deleted_source_remains_a_dependency_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'test_deleted.py').write_text('import deleted_module\n')
            with patch.object(affected_tests, 'ROOT', root):
                graph = affected_tests.dependency_graph(['deleted_module.py', 'test_deleted.py'])
                self.assertIn('deleted_module.py', graph['test_deleted.py'])

    def test_a_document_selects_only_the_tests_that_read_it(self):
        tests, reasons, full = affected_tests.select(['docs/project.md'])
        self.assertFalse(full)
        self.assertEqual([t for t in tests if t != SELF], ['tests/test_project_status.py'])
        self.assertEqual(reasons['tests/test_project_status.py'], 'tests/test_project_status.py <- docs/project.md')

    def test_code_selects_its_importers_and_the_tests_that_run_it(self):
        """Today's real breakages: each change's selection holds the tests that failed."""
        for change, failed in (('pi-autowork/pi_autowork/task_commands.py', ['pi-autowork/tests/runner/test_task_commands.py']),
                               ('pi-autowork/pi_autowork/task_migrate.py', ['pi-autowork/tests/engine/test_parallel_plan.py']),
                               ('pi-autowork/pi_autowork/worker.py', ['pi-autowork/tests/runner/test_pi_autowork.py']),
                               ('scripts/install_skills.py', ['tests/test_engineering_vendor.py'])):
            with self.subTest(change=change):
                tests, _, full = affected_tests.select([change])
                self.assertFalse(full)
                self.assertTrue(set(failed) <= set(tests), (failed, tests))
                self.assertLess(len(tests), len(affected_tests.check_module().discover_tests(ROOT)))  # not the suite

    def test_a_changed_test_module_selects_itself_and_an_extensionless_script_its_tests(self):
        self.assertIn('tests/test_tx.py', affected_tests.select(['tests/test_tx.py'])[0])
        self.assertIn('tests/test_tx.py', affected_tests.select(['tmux/tx'])[0])

    def test_the_check_ci_and_packaging_select_the_whole_suite(self):
        for change in ('scripts/check.py', '.github/workflows/test.yml', 'requirements-test.txt'):
            with self.subTest(change=change):
                tests, _, full = affected_tests.select([change])
                self.assertTrue(full)
                self.assertGreater(len(tests), 100)

    def test_src_relative_qualified_and_legacy_edges_do_not_confuse_duplicate_stems(self):
        files = {
            'pi-autowork/pi_autowork/__init__.py': '',
            'pi-autowork/pi_autowork/engine/__init__.py': '',
            'pi-autowork/pi_autowork/engine/owner.py': 'VALUE = 1\n',
            'pi-autowork/pi_autowork/engine/consumer.py': 'from .owner import VALUE\n',
            'pi-autowork/pi_autowork/command.py': 'from .engine import consumer\n',
            'pi-autowork/engine/consumer.py': '# flat engine entry\n',
            'unrelated/owner.py': 'VALUE = 2\n',
            'tests/test_public.py': 'import pi_autowork.command\n',
            'tests/test_path.py': 'ENTRY = "pi-autowork/pi_autowork/command.py"\n',
            'tests/test_other.py': 'import unrelated.owner\n',
            **{f'pi-autowork/tests/{suite}/test_public.py': 'import pi_autowork.command\n'
               for suite in ('runner', 'engine', 'native')},
            'pi-autowork/tests/support/store_fixture.py': 'import pi_autowork.command\n',
            'tests/test_support.py': 'import store_fixture\n',
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, body in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            with patch.object(affected_tests, 'ROOT', root):
                graph = affected_tests.dependency_graph(list(files), conservative=True)
                self.assertIn('pi-autowork/pi_autowork/engine/owner.py', graph['pi-autowork/pi_autowork/engine/consumer.py'])
                self.assertIn('pi-autowork/pi_autowork/engine/consumer.py', graph['pi-autowork/engine/consumer.py'])
                self.assertIn('pi-autowork/pi_autowork/__init__.py', graph['tests/test_public.py'])
                self.assertNotIn('unrelated/owner.py', graph['pi-autowork/pi_autowork/engine/consumer.py'])
                self.assertNotIn('pi-autowork/pi_autowork/engine/owner.py', graph['tests/test_other.py'])
            # Real direct-child inventory; no discovery plugin or flattened test stem.
            checker = affected_tests.check_module()
            with patch.object(affected_tests, 'ROOT', root), \
                    patch.object(affected_tests, 'check_module', return_value=checker), \
                    patch.object(affected_tests, 'repository_files', return_value=list(files)):
                owner = 'pi-autowork/pi_autowork/engine/owner.py'
                expected = {'tests/test_public.py', 'tests/test_path.py', 'tests/test_support.py',
                            *(f'pi-autowork/tests/{suite}/test_public.py'
                              for suite in ('runner', 'engine', 'native'))}
                selected, _, full = affected_tests.select([owner], conservative=True)
                self.assertFalse(full)
                self.assertEqual(set(selected), expected)
                all_tests = {p.relative_to(root).as_posix() for p in checker.discover_tests(root)}
                for changed in ('pi-autowork/pi_autowork/__init__.py', 'missing.py'):
                    selected, _, full = affected_tests.select([changed], conservative=True)
                    self.assertTrue(full)
                    self.assertEqual(set(selected), all_tests)
                (root / owner).rename(root / owner.replace('owner.py', 'renamed.py'))
                for changed in (owner, owner.replace('owner.py', 'renamed.py')):
                    if (root / changed).exists():
                        (root / changed).unlink()
                    selected, _, full = affected_tests.select([changed], conservative=True)
                    self.assertTrue(full)
                    self.assertEqual(set(selected), all_tests)

    def test_an_unmapped_document_selects_nothing_but_unmapped_code_selects_the_whole_suite(self):
        """A changelog line cost the whole suite before every push; code with no mapped test still does."""
        for change in ('docs/new-note.md', 'docs/new-note.txt'):
            with self.subTest(change=change):
                tests, _, full = affected_tests.select([change], conservative=True)
                self.assertEqual(([t for t in tests if t != SELF], full), ([], False))
        # A document reaches the tests that read it and the tests of the code that reads it, no
        # further: the engine names CHANGELOG.md because it edits one in target repositories.
        for change in ('CHANGELOG.md', 'README.md'):
            with self.subTest(change=change):
                tests, reasons, full = affected_tests.select([change], conservative=True)
                self.assertFalse(full)
                self.assertTrue(tests)
                self.assertLess(len(tests), len(affected_tests.check_module().discover_tests(ROOT)) // 2, tests)
                self.assertTrue(all(len(reason.split(' <- ')) <= 3 for reason in reasons.values()), reasons)
        tests, reasons, full = affected_tests.select(['scripts/new_tool.py'], conservative=True)
        self.assertTrue(full)
        self.assertIn('the whole suite', next(iter(reasons.values())))

    def test_planning_records_select_nothing(self):
        tests, _, full = affected_tests.select(['tasks/items/TOOLSET-001-00.md'])
        self.assertEqual(([t for t in tests if t != SELF], full), ([], False))


class ExecutionTests(unittest.TestCase):
    def invoke(self, argv, *, full=True, tests=None):
        tests = ['tests/test_example.py'] if tests is None else tests
        reasons = {test: 'unmapped.py has no resolved test mapping: the whole suite' for test in tests}
        output = io.StringIO()
        with patch.object(affected_tests, 'changed_files', return_value=['unmapped.py']), \
                patch.object(affected_tests, 'select', return_value=(tests, reasons, full)) as select, \
                patch.object(affected_tests.subprocess, 'run', return_value=Mock(returncode=7)) as run, \
                contextlib.redirect_stdout(output):
            code = affected_tests.main(['--base', 'HEAD', *argv])
        select.assert_called_once_with(['scripts/check.py'] if '--full' in argv else ['unmapped.py'],
                                       'HEAD', conservative=True)
        return code, output.getvalue(), run

    def test_push_defers_a_full_selection_with_an_explicit_reason(self):
        code, output, run = self.invoke(['--run', '--defer-full'])
        self.assertEqual(code, 0)
        run.assert_not_called()
        self.assertIn('unmapped.py has no resolved test mapping', output)
        self.assertIn('deferred to CI', output)
        self.assertIn('no test modules run locally', output)

    def test_default_execution_keeps_the_conservative_full_suite(self):
        for argv in (['--run'], ['--run', '--full']):
            with self.subTest(argv=argv):
                code, _, run = self.invoke(argv)
                self.assertEqual(code, 7)
                run.assert_called_once_with(
                    [sys.executable, str(ROOT / 'scripts/check.py')], cwd=ROOT)

    def test_push_runs_targeted_tests_and_preserves_failure_and_pattern(self):
        code, _, run = self.invoke(['--run', '--defer-full', '-k', 'example'], full=False)
        self.assertEqual(code, 7)
        run.assert_called_once_with(
            [sys.executable, str(ROOT / 'scripts/check.py'), 'tests/test_example.py', '-k', 'example'], cwd=ROOT)

    def test_empty_and_preview_selections_do_not_run(self):
        for argv, full, tests in ((['--defer-full'], True, ['tests/test_example.py']),
                                  (['--run', '--defer-full'], False, [])):
            with self.subTest(argv=argv, full=full):
                code, _, run = self.invoke(argv, full=full, tests=tests)
                self.assertEqual(code, 0)
                run.assert_not_called()

    def test_json_distinguishes_deferral_from_a_passing_test_run(self):
        code, output, run = self.invoke(['--run', '--defer-full', '--json'])
        self.assertEqual(code, 0)
        selection = json.loads(output)
        self.assertTrue(selection['full'])
        self.assertTrue(selection['deferred'])
        self.assertEqual(selection['tests'], ['tests/test_example.py'])
        run.assert_not_called()
        _, output, _ = self.invoke(['--defer-full', '--json'])
        self.assertFalse(json.loads(output)['deferred'])

    def test_explicit_full_and_deferral_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            affected_tests.main(['--full', '--defer-full'])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
