"""The pre-push hook runs the affected selection for what is being pushed, and nothing more."""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pre_push_check  # noqa: E402

ZERO = '0' * 40
A, B, C = 'a' * 40, 'b' * 40, 'c' * 40


class PushedBasesTests(unittest.TestCase):
    def test_the_remote_sha_is_the_base_when_this_clone_knows_it(self):
        lines = [f'refs/heads/main {B} refs/heads/main {A}']
        self.assertEqual(pre_push_check.pushed_bases(lines, known=lambda sha: True), [A])

    def test_an_unknown_remote_sha_or_a_new_branch_uses_the_selector_default(self):
        self.assertEqual(pre_push_check.pushed_bases([f'refs/heads/x {B} refs/heads/x {A}'], known=lambda sha: False), [None])
        self.assertEqual(pre_push_check.pushed_bases([f'refs/heads/x {B} refs/heads/x {ZERO}'], known=lambda sha: True), [None])

    def test_deletions_unchanged_refs_and_malformed_lines_select_nothing(self):
        lines = [f'(delete) {ZERO} refs/heads/old {A}', f'refs/heads/main {A} refs/heads/main {A}', 'garbage']
        self.assertEqual(pre_push_check.pushed_bases(lines, known=lambda sha: True), [])

    def test_each_distinct_base_is_kept_once_in_order(self):
        lines = [f'refs/heads/main {B} refs/heads/main {A}', f'refs/heads/dev {C} refs/heads/dev {A}',
                 f'refs/heads/new {C} refs/heads/new {ZERO}']
        self.assertEqual(pre_push_check.pushed_bases(lines, known=lambda sha: True), [A, None])


class MainTests(unittest.TestCase):
    def test_runs_the_selection_per_base_and_stops_at_the_first_failure(self):
        calls = []
        with mock.patch.object(pre_push_check, 'known', lambda sha: True):
            code = pre_push_check.main([], io.StringIO(f'refs/heads/main {B} refs/heads/main {A}\n'), run=lambda base: calls.append(base) or 0)
        self.assertEqual((code, calls), (0, [A]))
        calls.clear()
        with mock.patch.object(pre_push_check, 'known', lambda sha: True), mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            code = pre_push_check.main([], io.StringIO(f'refs/heads/main {B} refs/heads/main {A}\nrefs/heads/dev {C} refs/heads/dev {ZERO}\n'),
                                       run=lambda base: calls.append(base) or 1)
        self.assertEqual((code, calls), (1, [A]))
        self.assertIn('--no-verify', err.getvalue())

    def test_nothing_to_push_and_the_skip_flag_run_no_tests(self):
        calls = []
        self.assertEqual(pre_push_check.main([], io.StringIO(''), run=lambda base: calls.append(base) or 1), 0)
        with mock.patch.dict(os.environ, KIT_PRE_PUSH='0'):
            self.assertEqual(pre_push_check.main([], io.StringIO(f'refs/heads/main {B} refs/heads/main {A}\n'), run=lambda base: calls.append(base) or 1), 0)
        self.assertEqual(calls, [])

    def test_install_writes_a_hook_chains_an_exec_hook_once_and_leaves_others_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            hooks = Path(folder)
            self.assertEqual(pre_push_check.install(hooks), 0)
            hook = hooks / 'pre-push'
            self.assertIn('pre_push_check.py', hook.read_text())
            self.assertTrue(os.access(hook, os.X_OK))
            self.assertEqual(pre_push_check.install(hooks), 0)  # idempotent
            self.assertEqual(hook.read_text().count('pre_push_check.py'), 1)
            hook.write_text('#!/bin/sh\nexec "$(git rev-parse --git-common-dir)/hooks/private-terms-check" pre-push "$@"\n')
            self.assertEqual(pre_push_check.install(hooks), 0)
            text = hook.read_text()
            self.assertLess(text.index('private-terms-check'), text.index('pre_push_check.py'))  # the cheap refusal first
            self.assertIn('input=$(cat)', text)
            self.assertEqual(text.count('"$input"'), 2)
            hook.write_text('#!/bin/sh\necho custom\n')
            with mock.patch('sys.stderr', new_callable=io.StringIO):
                self.assertEqual(pre_push_check.install(hooks), 1)
            self.assertEqual(hook.read_text(), '#!/bin/sh\necho custom\n')


if __name__ == '__main__':
    unittest.main()
