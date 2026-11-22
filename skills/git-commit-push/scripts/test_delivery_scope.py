#!/usr/bin/env python3
"""Offline policy-contract regressions, not live publication or model behavior proof.

Run: python git-commit-push/scripts/test_delivery_scope.py
The canonical scripts/check.py discovers this standalone unittest suite.
"""
from pathlib import Path
import importlib
import os
import re
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parent.parent


def normalized(path):
    return re.sub(r'\s+', ' ', path.read_text(encoding='utf-8')).lower()


class DeliveryScopePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = normalized(SKILL / 'SKILL.md')
        cls.reference = normalized(SKILL / 'references/shared-worktree-safety.md')

    def both_require(self, *phrases):
        for label, text in [('skill', self.main), ('reference', self.reference)]:
            for phrase in phrases:
                with self.subTest(document=label, phrase=phrase):
                    self.assertIn(phrase, text)

    def test_pushes_never_leave_the_remote_or_canonical_main_behind(self):
        """A worktree pushed HEAD:main while the canonical main stayed stale; the next merge diverged."""
        for phrase in ('never push a branch that is behind its push target',
                       'is an ancestor of what you push',
                       'leave the canonical checkout current after pushing the default branch from elsewhere',
                       'merge --ff-only origin/main', 'local main stale'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.main)
        closeout = normalized(SKILL / 'references/worktree-closeout.md')
        self.assertIn('integrating onto a stale local `main` diverges from the remote', closeout)

    def test_completed_cross_agent_work_is_eligible_for_repo_wide_ship(self):
        self.both_require('all eligible changes in requested scope',
                          'take delivery ownership', 'provenance',
                          'candidate-bound verification',
                          'authorship alone never excludes changes or yields no-op')
        self.assertIn('completed cross-agent implementation is eligible', self.main)
        self.assertIn('implementer is someone else or no card exists', self.main)
        self.assertIn('attribute contributors and verification receipts in the commit message', self.main)

    def test_live_writer_and_incomplete_work_remain_excluded(self):
        self.both_require('live writer/lease hunks', 'secrets', 'unapproved',
                          'unfinished', 'verification')
        self.assertIn('hold live writer/lease hunks, incomplete or unverifiable work', self.main)
        self.assertIn('live ownership/leases remain excluded', self.reference)

    def test_stale_only_ledger_is_not_a_restoration_commit(self):
        self.assertIn('a stale-only ledger contains no new work', self.main)
        self.assertIn('do not create a restoration commit', self.main)
        self.assertIn('stale-only copies yield no new commit', self.reference)
        self.both_require('no actual unshipped delta in requested scope',
                          'regardless of author', 'report behind/diverged status separately')

    def test_remote_additions_conserved_in_isolated_reconciliation(self):
        self.both_require('fresh upstream', 'isolated candidate',
                          'preserve newer remote entries', 'never delete remote lines',
                          'supported GitHub issue operations'.lower(),
                          'anchored prose edits', 'validate and inspect the resulting diff')

    def test_worker_local_only_audit_and_allowlist_do_not_gain_authority(self):
        self.both_require('local-only requests never authorize push',
                          'audit never authorizes git writes')
        self.assertIn('autonomous worker/card without explicit repo-wide authorization remains limited to its owned slice', self.main)
        self.assertIn('a path/topic allowlist stays narrow', self.main)
        self.assertIn('without that authorization, remain within the worker/card or path allowlist', self.reference)

    def test_agent_branch_does_not_equal_requested_target(self):
        self.assertIn('a card-branch commit is not proof it already reached the requested target', self.main)
        self.assertIn('committed on an agent branch does not mean published to the requested target', self.reference)

    def test_authorship_veto_removed_without_weakening_staging_or_preservation(self):
        for text in (self.main, self.reference):
            self.assertNotIn("another writer's uncommitted implementation is not yours to publish", text)
            self.assertNotIn('nothing of yours to commit', text)
            self.assertNotIn('belongs to that card, so exclude it', text)
            self.assertNotIn('when the foreign hunks cannot be separated safely', text)
        self.assertIn('stage explicit paths only', self.main)
        self.assertIn('never `git add -a` / `git add .`', self.main)
        self.assertIn("do not discard, stash, revert, or `git clean` other agents'", self.main)
        self.assertIn('committed is not deployed', self.reference)
        self.assertIn('held/asked, not no-op', self.main)

    def test_push_saves_ordinary_idle_work_without_completion_marker(self):
        push = normalized(ROOT / 'skills/push/SKILL.md')
        docs = normalized(ROOT / 'docs/workflows.md')
        for text in (push, docs):
            self.assertIn('verified idle worktrees', text)
            self.assertIn('no separate completion note or marker', text)
            self.assertIn('staged, unstaged, deleted', text)
            self.assertIn('ordinary non-ignored untracked', text)
        self.assertNotIn('the completed changes in idle dirty worktrees', push)
        self.assertIn('head, index bytes and file contents', push)
        self.assertIn('save pending', push)
        for exclusion in ('private runtime state', 'ignored untracked output',
                          'active or uncertain ownership', 'pause or recovery hold'):
            self.assertIn(exclusion, push)
        self.assertIn('without exposing contents', push)
        self.assertIn('remote `main`', push)
        self.assertIn('otherwise push the candidate branch', push)
        self.assertIn('exact publication blocker', push)

    def test_push_exception_does_not_widen_sibling_or_sweep_helper(self):
        sweep = normalized(SKILL / 'references/worktree-sweep.md')
        self.assertIn('## when called by `/push`', sweep)
        self.assertIn('no separate completion note or marker', sweep)
        self.assertIn('the helper still never commits dirty worktrees', sweep)
        self.assertIn('the checked-out branch, then its upstream', self.main)
        self.assertIn('completed eligible scope', self.main)
        self.assertIn('a dirty worktree is reported for its owner', self.main)
        adapter = normalized(ROOT / 'adapters/skills/push/SKILL.md')
        self.assertIn('../../../skills/push/skill.md', adapter)

    def test_canonical_gate_discovers_regression_suite(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        checker = importlib.import_module('check')
        self.assertIn(Path(__file__).resolve(), checker.discover_tests(ROOT))


class PushIdleWorktreeGitTests(unittest.TestCase):
    """Replay the documented Git path, not a model or an executable /push engine.

    Ownership/exclusion decisions are explicit fixture inputs. No completion file
    exists. All publication goes to the disposable local bare repository.
    """

    def git(self, cwd, *args, expected=0):
        result = subprocess.run(['git', '-C', str(cwd), *args], env=self.env,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, expected,
                         f'git {args}: {result.stderr.decode(errors="replace")}')
        return result.stdout

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_TERMINAL_PROMPT='0', GIT_EDITOR='true', GIT_OPTIONAL_LOCKS='0')
        self.remote = root / 'remote.git'
        self.repo = root / 'repo'
        self.repo.mkdir()
        self.git(root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.git(self.repo, 'init', '--initial-branch=main')
        self.git(self.repo, 'config', 'user.name', 'Offline fixture')
        self.git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.repo, 'remote', 'add', 'verified', str(self.remote))
        initial = {'.gitignore': '.worktrees/\nignored/\n',
                   'edited.txt': 'old edit\n', 'staged.txt': 'old staged\n',
                   'deleted.txt': 'delete me\n', 'staged-delete.txt': 'delete me too\n',
                   'active.txt': 'original active\n'}
        for path, content in initial.items():
            (self.repo / path).write_text(content)
        self.git(self.repo, 'add', '--', *initial)
        self.git(self.repo, 'commit', '-m', 'Initial fixture')
        self.git(self.repo, 'push', '--set-upstream', 'verified', 'HEAD:refs/heads/main')
        self.idle = self.repo / '.worktrees/idle'
        self.git(self.repo, 'worktree', 'add', '-b', 'idle', str(self.idle))
        self.eligible = {'edited.txt': 'idle edit\n', 'staged.txt': 'idle staged\n',
                         'new ordinary [1].txt': 'new ordinary\n'}
        for path, content in self.eligible.items():
            (self.idle / path).write_text(content)
        (self.idle / 'deleted.txt').unlink()
        (self.idle / 'staged-delete.txt').unlink()
        self.git(self.idle, 'add', '--', 'staged.txt', 'staged-delete.txt')
        self.exclusions = {'.env': 'secret', 'runtime/session.json': 'private runtime state',
                           'ignored/cache.txt': 'ignored untracked output',
                           'active.txt': 'active ownership', 'uncertain.txt': 'uncertain ownership',
                           'paused.txt': 'pause', 'recovery.txt': 'recovery hold'}
        for path in self.exclusions:
            target = self.idle / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('synthetic held fixture bytes\n')

    def baseline(self):
        index = self.git(self.idle, 'rev-parse', '--git-path', 'index').decode().strip()
        paths = sorted([*self.eligible, *self.exclusions, 'deleted.txt', 'staged-delete.txt'])
        return (self.git(self.idle, 'rev-parse', 'HEAD'), Path(index).read_bytes(),
                self.git(self.idle, 'status', '--porcelain=v1', '-z', '--untracked-files=all'),
                tuple((p, (self.idle / p).read_bytes() if (self.idle / p).exists() else None)
                      for p in paths))

    def test_ordinary_idle_changes_reach_remote_main_and_exclusions_survive(self):
        self.assertEqual(len(self.git(self.repo, 'worktree', 'list', '--porcelain')
                             .split(b'worktree ')) - 1, 2)
        baseline = self.baseline()
        held = {p: (self.idle / p).read_bytes() for p in self.exclusions}
        self.assertIn(b'ignored/cache.txt', self.git(self.idle, 'ls-files', '--others',
                                                   '--ignored', '--exclude-standard'))
        # Save the invoking checkout, then simulate upstream main advancing while
        # the idle tree still holds ordinary uncommitted changes at the older pin.
        (self.repo / 'invoking.txt').write_text('invoking checkout change\n')
        self.git(self.repo, 'add', '--', 'invoking.txt')
        self.git(self.repo, 'commit', '-m', 'Save invoking checkout')
        self.git(self.repo, 'push', 'verified', 'HEAD:refs/heads/main')
        upstream = self.git(self.repo, 'rev-parse', 'HEAD').strip()
        self.assertEqual(self.baseline(), baseline)  # HEAD, index AND file bytes
        # Already-staged deletion stays in the expected set, not the add list.
        self.git(self.idle, '--literal-pathspecs', 'add', '--', *self.eligible, 'deleted.txt')
        staged = self.git(self.idle, 'diff', '--cached', '--name-only', '-z').split(b'\0')[:-1]
        self.assertEqual(set(staged), {p.encode() for p in
                                      [*self.eligible, 'deleted.txt', 'staged-delete.txt']})
        self.git(self.idle, 'diff', '--cached', '--check')
        self.git(self.idle, 'commit', '-m', 'Save ordinary idle work without a completion note')
        saved = self.git(self.idle, 'rev-parse', 'HEAD').strip().decode()
        # Merge on the invoking checkout; never integrate over the held dirty files.
        self.git(self.repo, 'merge', '--no-ff', saved, '-m', 'Reconcile idle work with upstream')
        self.git(self.repo, 'merge-base', '--is-ancestor', upstream.decode(), 'HEAD')
        self.git(self.repo, 'diff', '--check')
        candidate = self.git(self.repo, 'rev-parse', 'HEAD').strip().decode()
        self.git(self.repo, 'push', 'verified', 'HEAD:refs/heads/candidate')
        # Candidate published but no main inclusion: protected PR/check/review gates
        # would still be pending. This fixture does not pretend to perform those gates.
        self.git(self.remote, 'merge-base', '--is-ancestor', candidate, 'refs/heads/main', expected=1)
        self.assertIn('unmerged protected pr remain pending',
                      normalized(ROOT / 'docs/workflows.md'))
        # This fixture permits direct main writes. Only this readback proves delivery.
        self.git(self.repo, 'push', 'verified', 'HEAD:refs/heads/main')
        readback = self.git(self.repo, 'ls-remote', 'verified', 'refs/heads/main').split()[0].decode()
        self.assertEqual(readback, candidate)
        self.git(self.remote, 'merge-base', '--is-ancestor', saved, readback)
        for path, content in {**self.eligible, 'invoking.txt': 'invoking checkout change\n'}.items():
            self.assertEqual(self.git(self.remote, 'show', f'{readback}:{path}'), content.encode())
        remote_paths = self.git(self.remote, 'ls-tree', '-r', '--name-only', readback).decode().splitlines()
        for path in ['deleted.txt', 'staged-delete.txt', *self.exclusions]:
            self.assertEqual(path in remote_paths, path == 'active.txt')
        self.assertEqual(self.git(self.remote, 'show', f'{readback}:active.txt'), b'original active\n')
        self.assertEqual({p: (self.idle / p).read_bytes() for p in self.exclusions}, held)
        self.assertEqual(self.git(self.idle, 'diff', '--cached', '--name-only'), b'')
        residual = self.git(self.idle, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
        for path in self.exclusions.keys() - {'ignored/cache.txt'}:
            self.assertIn(path.encode() + b'\0', residual)

    def test_same_status_baseline_drift_requires_reinventory_not_staging(self):
        before = self.baseline()
        (self.idle / 'edited.txt').write_text('a new writer changed the same dirty path\n')
        after = self.baseline()
        self.assertEqual(before[:3], after[:3])  # HEAD/index/status alone miss it
        self.assertNotEqual(before[3], after[3])
        # Stop before add/commit: the documented Save pending repair requires new
        # ownership evidence and inventory. Verify both index and remote stayed put.
        self.assertEqual(before[1], after[1])
        self.assertEqual(self.git(self.repo, 'ls-remote', 'verified', 'refs/heads/main').split()[0],
                         before[0].strip())
        self.assertIn('save pending', normalized(ROOT / 'skills/push/SKILL.md'))


if __name__ == '__main__':
    unittest.main()
