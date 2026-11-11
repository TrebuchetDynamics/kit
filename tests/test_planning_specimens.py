"""Offline specimen mechanics only: real Git/CLI, never a model or installed host."""
import hashlib
import json
import os
import runpy
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/planning'
COMMAND = ROOT / 'pi-autowork/pi_autowork/command.py'
command_environment = runpy.run_path(str(FIXTURES / 'scenarios.py'))['command_environment']


class PlanningSpecimenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scratch = Path(self.tmp.name)
        self.home = self.scratch / 'home'
        self.home.mkdir()

    def run_command(self, *args, cwd=None, env=None, timeout=180):
        started = time.monotonic()
        with subprocess.Popen(args, cwd=cwd or ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env if env is not None else command_environment(self.home),
                              umask=0o002, start_new_session=True) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                exc.add_note(f'cwd={cwd or ROOT}; python={sys.executable}; load={os.getloadavg()}')
                raise
            finally:
                # A timed-out builder can still own a CLI/Git child holding its pipes.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
        self.assertEqual(process.returncode, 0,
                         f'{args!r}; cwd={cwd or ROOT}; elapsed={time.monotonic() - started:.3f}s; '
                         f'python={sys.executable}; load={os.getloadavg()}; stderr={stderr}')
        return stdout

    def builder(self, script, action, root, *args):
        started = time.monotonic()
        try:
            return json.loads(self.run_command(sys.executable, str(FIXTURES / script),
                                               action, str(root), *args))
        finally:
            if action == 'prepare':
                print(f'PLANNING_PREPARE {script} {args!r}: {time.monotonic() - started:.3f}s; '
                      f'python={sys.executable} {sys.version.split()[0]}; load={os.getloadavg()}', file=sys.stderr)

    def tasks(self, repo, *args):
        return self.run_command(sys.executable, str(COMMAND), 'tasks', *args, cwd=repo)

    def test_prepare_preserves_cases_with_native_committed_seeds_and_source_provenance(self):
        # Reverting to TODO-only or hand-written/incomplete records breaks real CLI reads.
        expected = {
            'native-with-easy', 'portable-for-easy', 'native-for-bulk', 'portable-with-bulk',
            'native-easy', 'portable-easy', 'native-bulk', 'portable-bulk', 'bare-established',
            'bare-sparse', 'bare-undefined', 'mature-backlog', 'vague-goal', 'verification-gap',
            'spec-conflict', 'proposal', 'read-only', 'active-dirty', 'repeat', 'large',
            'old-authority', 'supporting-skill', 'questions-only', 'later-execution',
            'coordinator', 'challenge', 'research-plan',
        }
        expected |= {f'{entry}-{case}' for entry in ('native', 'portable') for case in (
            'technical-choice', 'local-fixture', 'external-input', 'owner-destructive', 'builder-closure')}
        expected |= {f'{entry}-task-{case}' for entry in ('native', 'portable') for case in (
            'vague-name', 'sibling-names', 'path-scope', 'repetitive-body')}
        interviews = {'two-decisions', 'vague-intent', 'fully-specified', 'ambiguous-round',
                      'shared-constraint', 'stop-resume', 'delegation', 'builder-followup'}
        for script, names in (
                ('scenarios.py', expected),
                ('interviews.py', {f'{entry}-{case}' for entry in ('native', 'portable')
                                   for case in interviews})):
            with self.subTest(script=script):
                root = self.scratch / script
                self.builder(script, 'prepare', root)
                self.assertEqual({p.name.removesuffix('.request.txt')
                                  for p in root.glob('*.request.txt')}, names)
                for name in names:
                    repo = root / name
                    self.assertTrue((repo / '.git/HEAD').is_file())
                    self.assertFalse((repo / 'TODO.md').exists())
                    self.assertFalse((repo / 'goals.json').exists())
                    if name == 'active-dirty':
                        held = tomllib.loads((repo / 'tasks/items/FMT-900-ab.md').read_text().split('+++')[1])
                        self.assertEqual(held['rank'], 1000)
                seed = root / ('native-easy' if script == 'scenarios.py' else 'native-fully-specified')
                self.assertTrue(json.loads(self.tasks(seed, 'validate'))['ok'])
                task = json.loads(self.tasks(seed, 'show', 'FMT-01'))
                self.assertEqual((task['id'], task['goal'], task['rank']), ('FMT-01', 'FORMAT', 1000))
                self.assertEqual(task['touches'], ['src/formatting.py', 'tests/test_formatting.py'])
                self.assertEqual(task['scope'], 'src/formatting.py and tests/test_formatting.py; no dependencies.')
                self.assertEqual(task['acceptance'], ['normalize(" X ") returns "x"; planned test_lowercase.'])
                self.assertFalse(task['draft'])
                self.assertIn('Ownership: Maintainer', task['notes'])
                self.assertIn('Sources: docs/plan.md#accepted-scope', task['notes'])
                goal = tomllib.loads((seed / 'tasks/goals/FORMAT.md').read_text().split('+++')[1])
                self.assertEqual((goal['id'], goal['source']), ('FORMAT', 'docs/plan.md#accepted-scope'))
                self.assertEqual(self.run_command('git', 'show', 'HEAD:tasks/items/FMT-01.md', cwd=seed),
                                 (seed / 'tasks/items/FMT-01.md').read_text())
                self.assertEqual(self.run_command('git', 'status', '--porcelain', cwd=seed), '')
                hashes = json.loads((root / 'source-sha256.json').read_text())
                for path, digest in hashes.items():
                    self.assertEqual(digest, hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
                for entry in ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md'):
                    self.assertIn(entry, hashes)
                self.assertTrue(all(not row['changed'] for row in self.builder(script, 'inspect', root)))

    def test_command_failure_and_timeout_close_owned_process_and_pipes(self):
        popen = subprocess.Popen
        for code, error in (('raise SystemExit(1)', AssertionError),
                            ('import signal; signal.pause()', subprocess.TimeoutExpired)):
            with self.subTest(code=code):
                processes = []

                def launch(*args, **kwargs):
                    process = popen(*args, **kwargs)
                    processes.append(process)
                    return process

                with patch.object(subprocess, 'Popen', side_effect=launch), self.assertRaises(error):
                    self.run_command(sys.executable, '-c', code,
                                     timeout=1 if error is subprocess.TimeoutExpired else 180)
                process, = processes
                self.assertIsNotNone(process.poll())
                self.assertTrue(process.stdout.closed)
                self.assertTrue(process.stderr.closed)
                with self.assertRaises(ProcessLookupError):
                    os.killpg(process.pid, 0)

    def test_prepare_ignores_inherited_git_config_and_python_imports(self):
        poisoned = self.scratch / 'poisoned-home'
        poisoned.mkdir()
        (poisoned / 'ignored').write_text('tasks/\n')
        (poisoned / '.gitconfig').write_text(f'[core]\n\texcludesFile = {poisoned / "ignored"}\n')
        (poisoned / 'git').mkdir()
        (poisoned / 'git/config').write_text('[core]\n\tautocrlf = true\n')
        (poisoned / 'json.py').write_text('raise RuntimeError("inherited Python import")\n')
        env = {**os.environ, 'HOME': str(poisoned), 'XDG_CONFIG_HOME': str(poisoned),
               'GIT_DIR': str(poisoned / 'wrong-repo'),
               'GIT_INDEX_FILE': str(poisoned / 'wrong-index')}
        for script, case, selectors in (
                ('scenarios.py', 'native-easy', ['--cases', 'native-easy']),
                ('interviews.py', 'native-fully-specified',
                 ['--cases', 'fully-specified', '--entrypoints', 'native'])):
            with self.subTest(script=script):
                root = self.scratch / script
                # Inject at the builder boundary, rather than sanitizing in the test launcher.
                self.run_command(sys.executable, str(FIXTURES / script), 'prepare', str(root),
                                 *selectors, env=env)
                repo = root / case
                self.assertEqual(self.run_command('git', 'show', 'HEAD:tasks/items/FMT-01.md', cwd=repo),
                                 (repo / 'tasks/items/FMT-01.md').read_text())
                self.assertEqual(self.run_command('git', 'status', '--porcelain', cwd=repo), '')
                self.assertTrue(json.loads(self.tasks(repo, 'validate'))['ok'])
                self.assertTrue(all(not row['changed'] for row in self.builder(script, 'inspect', root, *selectors)))
        # Test-launcher reads must also ignore inherited Git redirection and Python imports.
        with patch.dict(os.environ, {**env, 'PYTHONPATH': str(poisoned)}):
            self.assertEqual(self.run_command(sys.executable, '-c', 'import json; print(json.dumps(True))'),
                             'true\n')
            self.assertEqual(self.run_command('git', 'status', '--porcelain', cwd=repo), '')
        self.assertFalse((poisoned / 'wrong-index').exists())

    def test_stall_cases_seed_both_entrypoints_with_reachable_evidence_and_existing_task(self):
        # Missing cases, invalid seeds or silently replacing FMT-01 must fail offline.
        cases = ('technical-choice', 'local-fixture', 'external-input',
                 'owner-destructive', 'builder-closure')
        names = [f'{entry}-{case}' for entry in ('native', 'portable') for case in cases]
        available = runpy.run_path(str(FIXTURES / 'scenarios.py'))['CASES']
        self.assertLessEqual(set(names), set(available))
        root = self.scratch / 'stalls'
        self.builder('scenarios.py', 'prepare', root, '--cases', ','.join(names))
        for entry in ('native', 'portable'):
            for case in cases:
                name = f'{entry}-{case}'
                with self.subTest(name=name):
                    repo = root / name
                    request = (root / f'{name}.request.txt').read_text()
                    source = ('skills' if entry == 'native' else 'adapters/skills') + '/plan-for-me/SKILL.md'
                    self.assertIn(str(ROOT / source), request)
                    self.assertTrue(json.loads(self.tasks(repo, 'validate', '--worktree'))['ok'])
                    task = json.loads(self.tasks(repo, 'show', 'FMT-01'))
                    self.assertFalse(task['draft'])
                    self.assertEqual(task['goal'], 'FORMAT')
                    self.assertEqual(task['rank'], 1000)
                    self.assertIn('Ownership: Maintainer', task['notes'])
                    self.assertEqual(self.run_command('git', 'show', 'HEAD:tasks/items/FMT-01.md', cwd=repo),
                                     (repo / 'tasks/items/FMT-01.md').read_text())
                    if case == 'technical-choice':
                        # The convention is executable evidence, not just a prompt hint.
                        self.run_command(sys.executable, '-B', '-c',
                                         'from src.rows import encode_row; '
                                         'assert encode_row(["a|b", "c"]) == \'"a|b"|c\\n\'', cwd=repo)
                    elif case == 'local-fixture':
                        self.assertFalse((repo / 'tests/fixtures/normalization.json').exists())
                        check = subprocess.run(
                            [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                             '-p', 'test_fixture_contract.py'], cwd=repo, capture_output=True, text=True)
                        self.assertNotEqual(check.returncode, 0)
                        self.assertIn('FileNotFoundError', check.stderr)
                        self.assertIn('normalization.json', check.stderr)
                        self.assertIn('[" X ", " y "]', (repo / 'docs/plan.md').read_text())
                    elif case == 'external-input':
                        self.assertFalse((repo / 'external/scanner-v2.json').exists())
                        self.assertIn('scanner-v2.json', (repo / 'docs/plan.md').read_text())
                        self.assertIn('independent', request)
                    elif case == 'owner-destructive':
                        self.assertEqual((repo / 'archive/sample.txt').read_text(), 'Public sample export.\n')
                        self.assertIn('not authorized deletion', (repo / 'docs/plan.md').read_text())
                    else:
                        self.assertIn('all-whitespace', (repo / 'docs/builder-review.md').read_text())
                        self.run_command(sys.executable, '-B', '-m', 'unittest', 'discover',
                                         '-s', 'tests', '-p', 'test_importer.py', cwd=repo)
        # Read/validation commands must not disguise implementation writes.
        for row in self.builder('scenarios.py', 'inspect', root, '--cases', ','.join(names)):
            self.assertEqual(row['outside_planning_owners'], [])

    def test_task_writing_cases_preserve_scope_and_evidence(self):
        cases = ('task-vague-name', 'task-sibling-names', 'task-path-scope',
                 'task-repetitive-body', 'external-input')
        names = [f'{entry}-{case}' for entry in ('native', 'portable') for case in cases]
        root = self.scratch / 'task-writing'
        prepared = self.builder('scenarios.py', 'prepare', root, '--cases', ','.join(names))
        self.assertEqual(set(prepared['prepared']), set(names))
        hashes = json.loads((root / 'source-sha256.json').read_text())
        for path in ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md',
                     'skills/plan-for-me/SKILL.md',
                     'adapters/skills/plan-for-me/SKILL.md', 'skills/shared/TODO-WORKCENTER.md',
                     'skills/shared/RESEARCH-PLAN.md', 'skills/shared/PLAN-HANDOFF.md'):
            self.assertEqual(hashes[path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        self.assertEqual((root / 'source-revision.txt').read_text(),
                         self.run_command('git', 'rev-parse', 'HEAD'))
        for name in names:
            with self.subTest(name=name):
                repo = root / name
                mode = 'for' if name.endswith('external-input') else 'with'
                prefix = 'skills' if name.startswith('native-') else 'adapters/skills'
                self.assertIn(str(ROOT / f'{prefix}/plan-{mode}-me/SKILL.md'),
                              (root / f'{name}.request.txt').read_text())
                self.assertTrue(json.loads(self.tasks(repo, 'validate'))['ok'])
                task = json.loads(self.tasks(repo, 'show', 'FMT-01'))
                self.assertFalse(task['draft'])
                self.assertEqual(task['scope'], 'src/formatting.py and tests/test_formatting.py; no dependencies.')
                self.assertEqual(task['checks'], ['python3 -m unittest discover -s tests'])
                self.assertIn('Sources: docs/plan.md#accepted-scope', task['notes'])
                self.assertEqual(self.run_command('git', 'status', '--porcelain', cwd=repo), '')
                plan = (repo / 'docs/plan.md').read_text()
                if name.endswith('external-input'):
                    self.assertFalse((repo / 'external/scanner-v2.json').exists())
                    self.assertIn('retain the device transcript', plan)
                else:
                    self.assertIn('" X Y " becomes "x y"', plan)
                    self.assertIn('No new dependencies or network access', plan)
                if name.endswith('sibling-names'):
                    self.assertIn('without lowercasing or a final newline', plan)
                    self.assertIn('python3 -m unittest discover -s tests -p test_export.py', plan)
                elif name.endswith('repetitive-body'):
                    self.assertEqual(plan.count('Inspect the source, implement the change'), 6)
        self.assertTrue(all(not row['changed'] for row in self.builder(
            'scenarios.py', 'inspect', root, '--cases', ','.join(names))))

    def test_inspect_accepts_native_planning_but_reports_forbidden_inventories(self):
        # A blanket tasks/ or .git/ exception would hide the negative inventory.
        for script, case in (('scenarios.py', 'native-easy'), ('scenarios.py', 'bare-sparse'),
                             ('interviews.py', 'native-fully-specified')):
            with self.subTest(script=script):
                root = self.scratch / case
                selectors = ['--cases', case.removeprefix('native-')] if script == 'interviews.py' else ['--cases', case]
                if script == 'interviews.py':
                    selectors += ['--entrypoints', 'native']
                self.builder(script, 'prepare', root, *selectors)
                repo = root / case
                if case == 'bare-sparse':
                    (repo / 'docs').mkdir()
                    (repo / 'docs/plan.md').write_text('# Formatter plan\n\n## Accepted scope\nStatus: Accepted\n')
                    self.tasks(repo, 'goal', 'FORMAT', '--title', 'Formatter', '--priority', '10',
                               '--source', 'docs/plan.md#accepted-scope')
                    self.tasks(repo, 'add', '--id', 'FMT-01', '--goal', 'FORMAT',
                               '--title', 'Lowercase text', '--short', 'Lowercase', '--scope', 'src/formatting.py',
                               '--acceptance', 'Lowercase text', '--checks', 'true', '--touches', 'src/formatting.py')
                self.tasks(repo, 'field', 'FMT-01', 'title', 'Clarified lowercase task')
                self.tasks(repo, 'goal', 'FORMAT', '--title', 'Clarified formatter')
                self.tasks(repo, 'add', '--goal', 'FORMAT', '--title', 'Export pipes', '--short', 'Pipes',
                           '--scope', 'src/export.py', '--touches', 'src/export.py',
                           '--acceptance', 'Pipe-delimited rows', '--checks', 'true')
                with (repo / 'docs/plan.md').open('a') as stream:
                    stream.write('\nClarified planning decisions.\n')
                self.assertTrue(json.loads(self.tasks(repo, 'validate', '--worktree'))['ok'])
                planned = self.builder(script, 'inspect', root, *selectors)[0]
                self.assertEqual(planned['outside_planning_owners'], [])
                self.assertIn('tasks/items/FMT-01.md', planned['changed'])
                forbidden = ['tasks/evidence/FMT-01.toml', 'tasks/unknown.md', 'tasks/items/nested/x.md',
                             'src/formatting.py', 'tests/test_formatting.py', 'skills/ship-now/SKILL.md',
                             'README.md', 'AGENTS.md', 'scratch.json', 'package-lock.json',
                             '.git/config', '.git/refs/heads/forbidden', '.git/objects/unknown',
                             '.git/autowork-tasks.lock', 'tasks/items/BROKEN.md']
                for path in forbidden:
                    dest = repo / path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with dest.open('a') as stream:
                        stream.write('\n# forbidden\n' if path == '.git/config' else '\nforbidden\n')
                # Staging even an allowed planning owner must remain visible.
                self.run_command('git', 'add', 'docs/plan.md', cwd=repo)
                report = self.builder(script, 'inspect', root, *selectors)[0]
                self.assertTrue(set(forbidden + ['.git/index']) <= set(report['outside_planning_owners']), report)
                self.assertIn('.git/index', report['git_metadata_changes'])
                self.assertIn('.git/objects/unknown', report['changed'])

    def test_no_write_cases_allow_zero_effects_including_locks_and_scratch(self):
        for script, cases in (('scenarios.py', 'questions-only,challenge,read-only'),
                              ('interviews.py', 'vague-intent,builder-followup')):
            with self.subTest(script=script):
                root = self.scratch / script
                selectors = ['--cases', cases]
                self.builder(script, 'prepare', root, *selectors)
                initial = self.builder(script, 'inspect', root, *selectors)
                self.assertTrue(all(row['changed'] == [] for row in initial))
                for row in initial:
                    repo = root / row['case']
                    for path in ('docs/plan.md', '.docs-sync-goals.lock', '.git/autowork-tasks.lock', 'scratch.json'):
                        dest = repo / path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with dest.open('a') as stream:
                            stream.write('changed\n')
                    (repo / '.git/unknown.lock').touch()
                    (repo / 'empty-scratch').mkdir()
                    repo.chmod(0o700)
                for row in self.builder(script, 'inspect', root, *selectors):
                    self.assertIn('.', row['changed'])
                    self.assertEqual(row['outside_planning_owners'], row['changed'])

    def test_later_execution_uses_a_separate_phase_one_baseline(self):
        root = self.scratch / 'execution'
        selectors = ['--cases', 'later-execution']
        self.builder('scenarios.py', 'prepare', root, *selectors)
        repo = root / 'later-execution'
        self.tasks(repo, 'field', 'FMT-01', 'title', 'Accepted lowercase')
        planning = self.builder('scenarios.py', 'inspect', root, *selectors)[0]
        self.assertEqual(planning['outside_planning_owners'], [])
        self.builder('scenarios.py', 'baseline', root, *selectors, '--phase', 'execution')
        (repo / 'src/formatting.py').write_text('def normalize(value):\n    return value.strip().lower()\n')
        execution = self.builder('scenarios.py', 'inspect', root, *selectors, '--phase', 'execution')[0]
        self.assertEqual(execution['changed'], ['src/formatting.py'])
        self.assertEqual(execution['outside_planning_owners'], [])
        self.assertIn('src/formatting.py', self.builder('scenarios.py', 'inspect', root, *selectors)[0]['outside_planning_owners'])
        (repo / 'skills/ship-now/SKILL.md').write_text('rewritten\n')
        self.assertEqual(self.builder('scenarios.py', 'inspect', root, *selectors, '--phase', 'execution')[0]['outside_planning_owners'],
                         ['skills/ship-now/SKILL.md'])


if __name__ == '__main__':
    unittest.main()
