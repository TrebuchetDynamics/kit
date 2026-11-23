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

    def test_push_saves_ordinary_invoking_checkout_work_without_completion_marker(self):
        push = normalized(ROOT / 'skills/push/SKILL.md')
        docs = normalized(ROOT / 'docs/workflows.md')
        for text in (push, docs):
            self.assertIn('invoking checkout only', text)
            self.assertNotIn('verified idle worktrees', text)
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

    def test_push_local_scope_does_not_invoke_the_explicit_all_sweep(self):
        push = normalized(ROOT / 'skills/push/SKILL.md')
        sweep = normalized(SKILL / 'references/worktree-sweep.md')
        self.assertIn('explicit `/git-commit-push all`', sweep)
        self.assertIn('does not call this helper or integrate sibling tips', sweep)
        self.assertIn('dirty work stays with its owner', sweep)
        self.assertNotIn('references/worktree-sweep.md', push)
        self.assertIn('git rev-parse --show-toplevel', push)
        self.assertIn('exclude nested registered roots and their descendants', push)
        self.assertIn('other worktrees were not inspected', push)
        self.assertIn('the checked-out branch, then its upstream', self.main)
        self.assertIn('completed eligible scope', self.main)
        self.assertIn('a dirty worktree is reported for its owner', self.main)
        adapter = normalized(ROOT / 'adapters/skills/push/SKILL.md')
        self.assertIn('../../../skills/push/skill.md', adapter)

    def test_catalog_descriptions_name_branch_upstream_versus_main(self):
        for folder in ('skills', 'adapters/skills'):
            for skill, expected in (
                    ('git-commit-push', 'Commit current branch, sync and push its upstream.'),
                    ('push', 'Save this checkout, pull and deliver to main.')):
                text = (ROOT / folder / skill / 'SKILL.md').read_text()
                description = re.search(r'^description: "([^"]+)"$', text, re.M).group(1)
                self.assertEqual(description, expected)
                self.assertLessEqual(len(description), 60)

    def test_exceptional_playbooks_are_prerequisites_at_the_point_of_use(self):
        prepare = self.main.split('3. **prepare the smallest delivery.**')[1].split(
            '4. **validate once, in the right order: stage → gate → push.**')[0]
        validate = self.main.split('4. **validate once, in the right order: stage → gate → push.**')[1].split(
            '5. **commit.**')[0]
        self.assertIn('before combining reviewed slices', prepare)
        self.assertIn('references/candidate-gates.md#combining-reviewed-slices', prepare)
        self.assertIn('before gating an export that needs untracked dependencies or git-bound validators', validate)
        self.assertIn('references/candidate-gates.md', validate)
        self.assertNotIn('load [candidate gates](references/candidate-gates.md) for the branch playbooks', validate)
        self.assertIn('before staging into a shared or pre-populated index', prepare)
        self.assertIn('references/shared-worktree-safety.md', prepare)
        self.assertLess(prepare.index('before any writes'), prepare.index('git checkout-index'))
        self.assertIn('a plain scoped delivery does not require these exceptional playbooks', self.main)
        gates = normalized(SKILL / 'references/candidate-gates.md')
        self.assertIn('component-removal patch can delete a field', gates)
        self.assertNotIn('component-removal patch can delete a field', self.main)
        self.assertIn('a pathspec commit reads the selected *worktree* contents', self.reference)
        self.assertIn('temporary-index landing without a development branch', self.reference)
        self.assertIn('recheck canonical `head`, the real index bytes', self.reference)

    def test_topic_commits_load_partition_checks_without_requiring_shared_index(self):
        commit = self.main.split('5. **commit.**')[1].split(
            '6. **sync with upstream (default).**')[0]
        self.assertIn('before splitting one gated tree into topic commits', commit)
        self.assertIn('references/shared-worktree-safety.md#shared-index-commits', commit)
        self.assertIn('match each commit to its pinned path/blob partition', commit)
        self.assertIn('only the final tree to the combined gated tree', commit)
        self.assertIn('for a single commit, require', commit)
        self.assertIn('check each commit\'s paths/blobs against its partition', self.reference)

    def test_plain_required_read_set_is_smaller_than_frozen_baseline(self):
        # d26a1d6d: entry plus unconditional candidate-gates read. Same simple
        # upstream-level scoped branch, no foreign index, successful local gates.
        # Shared contracts are unchanged and included on both sides, not elided
        # to exaggerate the relative saving. This measures bytes, not model speed.
        common = [ROOT / 'skills/shared' / name for name in (
            'PONYTAIL.md', 'COMMUNICATION.md', 'COMMON-CONTRACT.md',
            'DEFINITION-OF-DONE.md', 'PLAN-HANDOFF.md', 'RESEARCH-PLAN.md')]
        common.append(ROOT / 'skills/engineering/upstream/references/definition-of-done.md')
        shared_bytes = sum(len(path.read_bytes()) for path in common)
        before = 39601 + 7897 + shared_bytes
        after = len((SKILL / 'SKILL.md').read_bytes()) + shared_bytes
        self.assertLess(after, before)

    def test_no_push_and_pull_only_cannot_gain_remote_write_authority(self):
        self.assertIn('no push means no remote writes', self.main)
        self.assertIn('it pushes only when the request also asks for a push', self.main)
        pull = normalized(SKILL / 'references/pull-merge.md')
        self.assertIn('push only if the user asked', pull)
        self.assertIn('local-only requests never authorize push', self.main)
        self.assertIn('push (explicit ship target only)', self.main)
        self.assertIn('worktree sweep (`all`)', self.main)

    def test_canonical_gate_discovers_regression_suite(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        checker = importlib.import_module('check')
        self.assertIn(Path(__file__).resolve(), checker.discover_tests(ROOT))


class PushInvokingCheckoutGitTests(unittest.TestCase):
    """Replay the documented Git path, not a model or an executable /push engine.

    Ownership/exclusion decisions are explicit fixture inputs. No completion file
    exists. All publication goes to the disposable local bare repository.
    """

    def git(self, cwd, *args, expected=0):
        self.calls.append((cwd, args))
        result = subprocess.run(['git', '-C', str(cwd), *args], env=self.env,
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, expected,
                         f'git {args}: {result.stderr.decode(errors="replace")}')
        return result.stdout

    def setUp(self):
        self.calls = []
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

    def test_linked_invoking_changes_reach_remote_main_without_canonical_access(self):
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
        # Invocation begins in the linked checkout. Canonical is now dirty and
        # out of scope, not a second source or an in-place landing destination.
        (self.repo / 'edited.txt').write_text('canonical owner is still writing\n')
        canonical = (self.git(self.repo, 'rev-parse', 'HEAD'),
                     (self.repo / '.git/index').read_bytes(),
                     (self.repo / 'edited.txt').read_bytes())
        self.calls.clear()
        self.assertEqual(self.git(self.idle, 'rev-parse', '--show-toplevel').strip(),
                         str(self.idle).encode())
        self.git(self.idle, 'worktree', 'list', '--porcelain', '-z')
        # Already-staged deletion stays in the expected set, not the add list.
        self.git(self.idle, '--literal-pathspecs', 'add', '--', *self.eligible, 'deleted.txt')
        staged = self.git(self.idle, 'diff', '--cached', '--name-only', '-z').split(b'\0')[:-1]
        self.assertEqual(set(staged), {p.encode() for p in
                                      [*self.eligible, 'deleted.txt', 'staged-delete.txt']})
        self.git(self.idle, 'diff', '--cached', '--check')
        self.git(self.idle, 'commit', '-m', 'Save invoking work without a completion note')
        saved = self.git(self.idle, 'rev-parse', 'HEAD').strip().decode()
        self.git(self.idle, 'fetch', 'verified')
        # Isolate without probing canonical status/files/activity. Only metadata
        # supplies placement; this disposable fixture permits a candidate branch.
        landing = self.repo / '.worktrees/candidate'
        self.git(self.idle, 'worktree', 'add', '-b', 'candidate', str(landing), 'verified/main')
        self.git(landing, 'merge', '--no-ff', saved, '-m', 'Reconcile invoking work with upstream')
        self.git(landing, 'merge-base', '--is-ancestor', upstream.decode(), 'HEAD')
        self.git(landing, 'diff', '--check')
        candidate = self.git(landing, 'rev-parse', 'HEAD').strip().decode()
        self.git(landing, 'push', 'verified', 'HEAD:refs/heads/candidate')
        # Candidate published but no main inclusion: protected PR/check/review gates
        # would still be pending. This fixture does not pretend to perform those gates.
        self.git(self.remote, 'merge-base', '--is-ancestor', candidate, 'refs/heads/main', expected=1)
        self.assertIn('unmerged protected pr remain pending',
                      normalized(ROOT / 'docs/workflows.md'))
        # This fixture permits direct main writes. Only this readback proves delivery.
        self.git(landing, 'push', 'verified', 'HEAD:refs/heads/main')
        readback = self.git(landing, 'ls-remote', 'verified', 'refs/heads/main').split()[0].decode()
        self.assertEqual(readback, candidate)
        self.assertNotIn(self.repo, [cwd for cwd, args in self.calls])
        # Verification outside the simulated invocation may inspect the fixture.
        self.assertEqual((self.git(self.repo, 'rev-parse', 'HEAD'),
                          (self.repo / '.git/index').read_bytes(),
                          (self.repo / 'edited.txt').read_bytes()), canonical)
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

    def test_nested_registered_worktree_is_a_boundary_not_untracked_content(self):
        nested = self.idle / 'nested-worker'
        self.git(self.idle, 'worktree', 'add', '-b', 'nested-worker', str(nested))
        (nested / 'nested-only.txt').write_text('unique sibling commit\n')
        self.git(nested, 'add', '--', 'nested-only.txt')
        self.git(nested, 'commit', '-m', 'Sibling unique tip')
        (nested / 'nested-only.txt').write_text('active sibling edits\n')
        self.git(self.idle, 'worktree', 'lock', '--reason', 'active fixture writer', str(nested))
        tip = self.git(nested, 'rev-parse', 'HEAD').strip()
        index = Path(self.git(nested, 'rev-parse', '--git-path', 'index').decode().strip())
        before = (index.read_bytes(), (nested / 'nested-only.txt').read_bytes())
        self.calls.clear()
        root = self.git(self.idle, 'rev-parse', '--show-toplevel').strip().decode()
        metadata = self.git(self.idle, 'worktree', 'list', '--porcelain', '-z')
        roots = [Path(part.removeprefix(b'worktree ').decode())
                 for part in metadata.split(b'\0') if part.startswith(b'worktree ')]
        self.assertIn(nested, roots)
        self.assertEqual(Path(root), self.idle)
        # Git lists the nested repository boundary, not its contents. Filter the
        # registered roots before any file reads and stage only explicit A files.
        status = self.git(self.idle, 'status', '--porcelain=v1', '--untracked-files=all')
        self.assertIn(b'?? nested-worker/', status)
        self.assertNotIn(b'nested-only.txt', status)
        self.git(self.idle, '--literal-pathspecs', 'add', '--', *self.eligible, 'deleted.txt')
        staged = self.git(self.idle, 'diff', '--cached', '--name-only').decode().splitlines()
        self.assertFalse(any(p.startswith('nested-worker') for p in staged))
        self.git(self.idle, 'commit', '-m', 'Save invoking checkout, excluding nested boundary')
        self.git(self.idle, 'merge-base', '--is-ancestor', tip.decode(), 'HEAD', expected=1)
        self.assertNotIn(nested, [cwd for cwd, args in self.calls])
        # Post-invocation fixture verification, not part of /push's local inventory.
        self.assertEqual(self.git(nested, 'rev-parse', 'HEAD').strip(), tip)
        self.assertEqual((index.read_bytes(), (nested / 'nested-only.txt').read_bytes()), before)

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
