"""GitHub planning publication and authority contracts."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLANNER = 'skills/plan-for-me/SKILL.md'
HANDOFF = 'skills/shared/PLAN-HANDOFF.md'
INTERACTIVE = ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md')


def prose(path):
    return ' '.join((ROOT / path).read_text().split())


class PlanningCliContractTests(unittest.TestCase):
    def test_both_planners_select_source_before_investigation(self):
        anchor = 'COMMON-CONTRACT.md#standalone-planner-freshness'
        for path in (PLANNER, INTERACTIVE[0], 'skills/shared/RESEARCH-PLAN.md'):
            with self.subTest(path=path):
                self.assertIn(anchor, prose(path))
        shared = prose('skills/shared/RESEARCH-PLAN.md')
        self.assertLess(shared.index('**Source.**'), shared.index('**Investigate and decide.**'))
        self.assertIn('chosen revision', shared)
        self.assertIn('source receipt', shared)
        host = prose('adapters/skills/COMMON.md')
        self.assertIn(anchor, host)
        self.assertIn('not a sync on skill loading', host)

    def test_runtime_failure_preserves_existing_contract(self):
        text = prose('skills/shared/RESEARCH-PLAN.md').split(
            '## Existing execution is not a new planning problem', 1)[1]
        for rule in ('same coordinator', 'exact failed operation and evidence',
                     'existing issue', 'Do not create a replacement implementation task'):
            self.assertIn(rule, text)
        for path in (PLANNER, INTERACTIVE[0]):
            self.assertIn('../shared/RESEARCH-PLAN.md#shared-planning-interface', prose(path))
            self.assertIn('../shared/PLAN-HANDOFF.md#execution-handoff', prose(path))

    def test_active_planning_routes_share_github_authority(self):
        for path in ('skills/unslop/SKILL.md', 'skills/docs-sync/SKILL.md',
                     'skills/shared/RESEARCH-PLAN.md', HANDOFF):
            text = prose(path)
            with self.subTest(path=path):
                self.assertIn('GitHub', text)
                self.assertIn('ai-ready', text)
                self.assertIn('UNSAVED', text)
        for path in (PLANNER, INTERACTIVE[0]):
            self.assertIn('../shared/PLAN-HANDOFF.md#publication-and-dependencies', prose(path))
            self.assertIn('../shared/PLAN-HANDOFF.md#persistence-not-local-main-admission', prose(path))
        for name in ('plan-for-me', 'plan-with-me', 'unslop', 'docs-sync', 'unblock'):
            text = prose(f'adapters/skills/{name}/SKILL.md')
            self.assertIn(f'../../../skills/{name}/SKILL.md', text)
            self.assertIn('../COMMON.md', text)

    def test_handoff_publishes_complete_native_graph_before_readiness(self):
        text = prose(HANDOFF)
        for required in ('observable', '**Scope:**', '**Exclusions:**', '**Acceptance:**',
                         '**Verification:**', '**Sources:**', 'blockedBy', 'ai-epic',
                         'ai-planning', 'final publication phase', 'regardless of author',
                         'open **and closed**', 'actual ownership', 'UNSAVED',
                         'no GitHub, label, document or scratch writes',
                         'not pickup, implementation or merge'):
            self.assertIn(required, text)

    def test_local_main_and_legacy_store_are_not_admission_requirements(self):
        text = prose(HANDOFF)
        self.assertIn('no longer requires', text)
        self.assertIn('canonical local `main` commit', text)



class PlanningSourceGitRecipeTests(unittest.TestCase):
    """Run the instruction's Git recipe, not a planner/model or a new sync helper."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote, self.producer, self.checkout = [root / p for p in
                                                    ('upstream.git', 'producer', 'analysis')]
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_SYSTEM='/dev/null',
                        GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0',
                        GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                        GIT_COMMITTER_NAME='Fixture',
                        GIT_COMMITTER_EMAIL='fixture@example.invalid')
        self.git(root, 'init', '--bare', str(self.remote))
        self.git(root, 'init', '-b', 'trunk', str(self.producer))
        self.commit(self.producer, 'baseline')
        self.git(self.producer, 'push', str(self.remote), 'trunk')
        self.git(root, 'clone', '-o', 'team', '-b', 'trunk', str(self.remote), str(self.checkout))
        self.git(self.checkout, 'branch', '-m', 'analysis')
        self.before = self.git(self.checkout, 'rev-parse', 'HEAD').stdout.strip()

    def git(self, cwd, *args, check=True):
        return subprocess.run(['git', '-C', str(cwd), *args], env=self.env,
                              capture_output=True, text=True, check=check, timeout=10)

    def commit(self, cwd, version):
        for name in ('source.txt', 'tests.txt'):
            (cwd / name).write_text(version + '\n')
        self.git(cwd, 'add', '--', 'source.txt', 'tests.txt')
        self.git(cwd, 'commit', '-m', version)
        return self.git(cwd, 'rev-parse', 'HEAD').stdout.strip()

    def advance(self, version='upstream'):
        sha = self.commit(self.producer, version)
        self.git(self.producer, 'push', str(self.remote), 'trunk')
        return sha

    def pull_recipe(self):
        contract = (ROOT / 'skills/shared/COMMON-CONTRACT.md').read_text()
        commands = re.findall(r'```sh\n(.*?)\n\s*```', contract, re.S)
        recipe = next((c for c in commands if 'pull --ff-only' in c), '')
        self.assertTrue(recipe, 'shared contract must provide the exact bounded pull recipe')
        values = {'$checkout': str(self.checkout), '$fetch_remote': 'team',
                  '$upstream_ref': 'refs/heads/trunk'}
        command = [values.get(token, token) for token in shlex.split(recipe)]
        return subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=15)

    def snapshot(self):
        git_dir = Path(self.git(self.checkout, 'rev-parse', '--absolute-git-dir').stdout.strip())
        return (self.git(self.checkout, 'rev-parse', 'HEAD').stdout,
                self.git(self.checkout, 'for-each-ref', '--format=%(refname) %(objectname)').stdout,
                {name: (git_dir / name).read_bytes() if (git_dir / name).exists() else None
                 for name in ('HEAD', 'index', 'FETCH_HEAD')},
                {p.name: p.read_bytes() for p in self.checkout.iterdir() if p.is_file()})

    def test_clean_fast_forward_then_noop_analyzes_fetched_source_and_tests(self):
        upstream = self.advance()
        # Hostile defaults must not turn this recipe into a rebase or autostash.
        for key, value in (('pull.rebase', 'true'), ('pull.ff', 'false'),
                           ('merge.autostash', 'true'), ('rebase.autostash', 'true'),
                           ('submodule.recurse', 'true')):
            self.git(self.checkout, 'config', key, value)
        # Verify the configured identity rather than infer origin/main. The bare
        # repository supplies a read-only stand-in for host ancestry/source reads.
        self.assertEqual(self.git(self.checkout, 'symbolic-ref', '--short', 'HEAD').stdout.strip(),
                         'analysis')
        self.assertEqual(self.git(self.checkout, 'config', '--get',
                                  'branch.analysis.remote').stdout.strip(), 'team')
        self.assertEqual(self.git(self.checkout, 'config', '--get',
                                  'branch.analysis.merge').stdout.strip(), 'refs/heads/trunk')
        self.assertEqual(self.git(self.checkout, 'remote', 'get-url', 'team').stdout.strip(),
                         str(self.remote))
        metadata = self.git(self.checkout, 'ls-remote', '--exit-code', 'team', 'refs/heads/trunk')
        self.assertEqual(metadata.stdout.split()[0], upstream)
        self.git(self.remote, 'merge-base', '--is-ancestor', self.before, upstream)
        self.assertEqual(self.git(self.checkout, 'status', '--porcelain=v1',
                                  '--untracked-files=all').stdout, '')
        result = self.pull_recipe()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(self.before, upstream)
        for ref in ('HEAD', 'FETCH_HEAD'):
            self.assertEqual(self.git(self.checkout, 'rev-parse', ref).stdout.strip(), upstream)
        # These are the first scoped analysis reads, after the pull.
        for name in ('source.txt', 'tests.txt'):
            self.assertEqual((self.checkout / name).read_text(), 'upstream\n')
            self.assertEqual(self.git(self.checkout, 'show', f'{upstream}:{name}').stdout,
                             'upstream\n')
        self.assertEqual(self.git(self.checkout, 'rev-list', '--count', 'HEAD').stdout.strip(), '2')
        snapshot = self.snapshot()
        noop = self.pull_recipe()
        self.assertEqual(noop.returncode, 0, noop.stderr)
        self.assertIn('Already up to date', noop.stdout)
        self.assertEqual(self.snapshot(), snapshot)

    def test_held_paths_allow_metadata_and_pinned_reads_without_local_mutation(self):
        # Explicitly selected no-sync paths: this proves the probes preserve state,
        # not that a model will choose the path. Policy/trace tests cover the choice.
        for scenario in ('dirty', 'staged', 'untracked-collision', 'ahead', 'diverged',
                         'missing-upstream', 'wrong-branch', 'detached', 'active-worker',
                         'read-only', 'no-sync', 'pinned', 'coordinator'):
            with self.subTest(scenario=scenario):
                # Each case gets an independent disposable checkout.
                case = Path(self.temp.name) / scenario
                self.git(case.parent, 'clone', '-o', 'team', '-b', 'trunk',
                         str(self.remote), str(case))
                self.checkout = case
                if scenario in ('dirty', 'staged'):
                    (case / 'source.txt').write_text('local edit\n')
                    if scenario == 'staged':
                        self.git(case, 'add', 'source.txt')
                elif scenario == 'untracked-collision':
                    (case / 'incoming.txt').write_text('private untracked\n')
                    (self.producer / 'incoming.txt').write_text('remote incoming\n')
                    self.git(self.producer, 'add', 'incoming.txt')
                    self.advance('collision')
                elif scenario in ('ahead', 'diverged'):
                    self.commit(case, 'local-only')
                    if scenario == 'diverged':
                        self.advance('diverged-upstream')
                elif scenario == 'missing-upstream':
                    self.git(case, 'config', '--unset', 'branch.trunk.merge')
                elif scenario == 'wrong-branch':
                    self.git(case, 'switch', '-c', 'unrelated')
                elif scenario == 'detached':
                    self.git(case, 'checkout', '--detach')
                snapshot = self.snapshot()
                self.git(case, 'worktree', 'list', '--porcelain')
                self.git(case, 'status', '--porcelain=v1', '--untracked-files=all')
                self.git(case, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False)
                self.git(case, 'config', '--get', 'branch.trunk.merge', check=False)
                metadata = self.git(case, 'ls-remote', '--exit-code', 'team', 'refs/heads/trunk')
                remote_sha = metadata.stdout.split()[0]
                # Read-only provider stand-in: read immutable remote source, never fetch it.
                remote_source = self.git(self.remote, 'show', f'{remote_sha}:source.txt').stdout
                self.assertTrue(remote_source)
                self.assertEqual(self.snapshot(), snapshot)

    def test_remote_advance_between_observation_and_pull_uses_fetched_revision(self):
        observed = self.advance('observed')
        fetched = self.advance('advanced')
        self.assertNotEqual(observed, fetched)
        result = self.pull_recipe()
        self.assertEqual(result.returncode, 0, result.stderr)
        for ref in ('HEAD', 'FETCH_HEAD'):
            self.assertEqual(self.git(self.checkout, 'rev-parse', ref).stdout.strip(), fetched)
        self.assertEqual((self.checkout / 'source.txt').read_text(), 'advanced\n')
        # Publication metadata detects another advance without another pull.
        snapshot = self.snapshot()
        latest = self.advance('publication-drift')
        metadata = self.git(self.checkout, 'ls-remote', 'team', 'refs/heads/trunk')
        self.assertEqual(metadata.stdout.split()[0], latest)
        self.assertNotEqual(latest, fetched)
        self.assertEqual(self.snapshot(), snapshot)

    def test_rejected_pull_does_not_rewrite_local_history_or_hide_error(self):
        self.advance()
        # Simulate local drift after preflight. Never use this as an ahead-tree recipe.
        local = self.commit(self.checkout, 'concurrent-local')
        files = self.snapshot()[3]
        result = self.pull_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Not possible to fast-forward', result.stderr)
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD').stdout.strip(), local)
        self.assertEqual(self.snapshot()[3], files)
        self.assertNotEqual(self.git(self.checkout, 'rev-parse', 'FETCH_HEAD').stdout.strip(), local)
        self.assertFalse((self.checkout / '.git/MERGE_HEAD').exists())
        self.assertFalse((self.checkout / '.git/refs/stash').exists())

    def test_remote_failure_retains_head_refs_index_and_files(self):
        self.git(self.checkout, 'remote', 'set-url', 'team', str(self.remote / 'missing'))
        snapshot = self.snapshot()
        result = self.pull_recipe()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not appear to be a git repository', result.stderr)
        after = self.snapshot()
        self.assertEqual(after[:2], snapshot[:2])  # HEAD and every ref
        self.assertEqual(after[2]['index'], snapshot[2]['index'])
        self.assertEqual(after[3], snapshot[3])
        # Git may create/truncate FETCH_HEAD even when transport fails. Report it;
        # failed pull is not a no-write invocation or successful source refresh.
        self.assertEqual(after[2]['FETCH_HEAD'], b'')


if __name__ == '__main__':
    unittest.main()
