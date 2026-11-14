"""GitHub planning contracts plus retained legacy recovery seam checks."""
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / 'pi-autowork/pi_autowork/command.py'
WORKCENTER = 'skills/shared/TODO-WORKCENTER.md'
PLANNER = 'skills/plan-for-me/SKILL.md'
HANDOFF = 'skills/shared/PLAN-HANDOFF.md'
INTERACTIVE = ('skills/plan-with-me/SKILL.md', 'adapters/skills/plan-with-me/SKILL.md')
AUTONOMOUS = (PLANNER, 'adapters/skills/plan-for-me/SKILL.md')
SPECIAL_CASES = 'skills/plan-with-me/references/special-cases.md'
# Deliberate public-entrypoint inventory: shallow globs exclude immutable upstream trees.
FIRST_PARTY_SKILLS = '''
apk-get ask-kit autonomous-codebase-improver autoresearch autowork
beautify-github-readme blockers bug-harvest docs-sync git-commit-push goal
grilling grill-with-docs impeccable improve-codebase-architecture lgtm pending
plan-for-me plan-with-me ponytail ponytail-audit ponytail-debt ponytail-gain
ponytail-help ponytail-review push responsive-screenshots split-folder state-machine
test-optimizer ui-taste unblock unused-code work writing-for-agents
'''.split()
TASK_WRITING_LINKS = (
    *((path, ('../../../skills/shared/' if path.startswith('adapters/') else '../shared/')
       + 'RESEARCH-PLAN.md') for path in (*INTERACTIVE, *AUTONOMOUS)),
    ('skills/docs-sync/SKILL.md', '../shared/TODO-WORKCENTER.md'),
    ('adapters/skills/docs-sync/SKILL.md', '../../../skills/docs-sync/SKILL.md'),
    ('skills/autoresearch/SKILL.md', '../shared/RESEARCH-PLAN.md'),
    ('adapters/skills/autoresearch/SKILL.md', '../../../skills/shared/TODO-WORKCENTER.md'),
    ('skills/autowork/SKILL.md', '../shared/TODO-WORKCENTER.md'),
    ('adapters/skills/autowork/SKILL.md', '../../../skills/autowork/SKILL.md'),
    ('skills/autowork/references/backlog-planning.md', '../../shared/TODO-WORKCENTER.md'),
    ('skills/plan-for-me/references/discovery.md', '../../shared/RESEARCH-PLAN.md'),
    ('skills/goal/SKILL.md', '../shared/COMMON-CONTRACT.md'),
    ('skills/autonomous-codebase-improver/SKILL.md', '../shared/TODO-WORKCENTER.md'),
    ('skills/shared/COMMON-CONTRACT.md', 'TODO-WORKCENTER.md'),
)


def prose(path):
    return ' '.join((ROOT / path).read_text().split())


class PlanningCliContractTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / 'repo'
        shutil.copytree(ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store', self.repo)
        for args in (('init', '-q'), ('add', '-A'), ('commit', '-qm', 'fixture')):
            subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid', *args],
                           check=True, capture_output=True, text=True)

    def tasks(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(COMMAND), 'tasks', *args],
                                cwd=self.repo, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        return result

    def show(self):
        return json.loads(self.tasks('show', 'T-1', '--worktree').stdout)

    def test_absolute_python_entrypoint_targets_consumer_from_unrelated_cwd(self):
        def run(*args, consumer_cwd=False):
            argv = [sys.executable, str(COMMAND), *args]
            if consumer_cwd:
                # field --json cannot disambiguate a repository from optional label/value.
                argv = ['sh', '-c', f'cd {shlex.quote(str(self.repo))} && {shlex.join(argv)}']
            result = subprocess.run(argv, cwd=self.repo.parent,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout

        caps = json.loads(run('capabilities'))
        self.assertGreaterEqual(caps['prepare_api'], 4)
        self.assertIn('tasks', caps['commands'])
        self.assertTrue({'prepare', 'add', 'field', 'show', 'validate'} <= set(caps['tasks']))
        for key in ('executable', 'toolset', 'release'):
            self.assertIn(key, caps)
        task_json = self.repo.parent / 'task.json'
        task_json.write_text(json.dumps(dict(title='Add an offline invoice export', scope='Export invoices',
                                            acceptance=['Export readable'], checks=['true'], touches=['docs/'])))
        tid = run('tasks', 'add', str(self.repo), '--json', str(task_json)).split()[-1]
        shown = json.loads(run('tasks', 'show', tid, str(self.repo), '--worktree'))
        field_json = self.repo.parent / 'field.json'
        literal = '`literal` $(not-a-command) $VAR "quoted" café\nsecond line'
        field_json.write_text(json.dumps({'label': 'scope', 'value': literal}), encoding='utf-8')
        run('tasks', 'field', tid, '--json', str(field_json),
            '--expect', shown['record_revision'], consumer_cwd=True)
        final = json.loads(run('tasks', 'show', tid, str(self.repo), '--worktree'))
        self.assertEqual(final['scope'], literal)
        run('tasks', 'validate', '--worktree', str(self.repo))
        self.assertFalse((self.repo.parent / 'tasks').exists())

    def test_git_history_preserves_a_pruned_manual_close_without_a_receipt(self):
        self.tasks('done', 'T-1', '--by', 'fixture', '--reason', 'accepted manual disposition')

        def git(*args):
            return subprocess.run(
                ['git', '-C', str(self.repo), '-c', 'user.name=Fixture',
                 '-c', 'user.email=fixture@example.invalid', *args],
                check=True, capture_output=True, text=True).stdout.strip()

        git('add', 'tasks/')
        git('commit', '-qm', 'close fixture')
        closure = git('rev-parse', 'HEAD')
        self.tasks('delete', 'T-1')
        git('add', 'tasks/')
        git('commit', '-qm', 'prune fixture')
        self.assertFalse((self.repo / 'tasks/items/T-1.md').exists())
        self.assertFalse((self.repo / 'tasks/evidence/T-1.toml').exists())
        log = git('log', 'HEAD', '--format=%H', '--', 'tasks/items/', 'tasks/evidence/')
        self.assertIn(closure, log.splitlines())
        record = git('show', f'{closure}:tasks/items/T-1.md')
        self.assertIn('status = "done"', record)
        self.assertIn('closure = "manual"', record)
        self.assertIn('accepted manual disposition', record)
        self.assertFalse((self.repo / 'tasks/items/T-1.md').exists())

    def test_documented_literal_update_reconciles_a_stale_read(self):
        center = prose(WORKCENTER)
        read = 'autowork tasks show ID --worktree'
        update = 'autowork tasks field ID --json field.json --expect REV'
        shown = json.loads(self.tasks(*['T-1' if arg == 'ID' else arg
                                        for arg in shlex.split(read)[2:]]).stdout)
        literal = '`literal` $(not-a-command) $VAR "quoted" café\nsecond line'
        (self.repo / 'field.json').write_text(json.dumps({'label': 'scope', 'value': literal}), encoding='utf-8')
        self.tasks('field', 'T-1', 'Evidence', 'Concurrent evidence to preserve')
        path = self.repo / 'tasks/items/T-1.md'
        current = path.read_bytes()
        args = [shown['record_revision'] if arg == 'REV' else 'T-1' if arg == 'ID' else arg
                for arg in shlex.split(update)[2:]]
        refused = self.tasks(*args, ok=False)
        self.assertIn('reread', refused.stderr)
        self.assertEqual(path.read_bytes(), current)
        latest = self.show()
        # Reconcile the intended scope delta, not a replay of the earlier whole record.
        self.assertEqual(latest['scope'], shown['scope'])
        self.assertIn('Concurrent evidence to preserve', latest['notes'])
        args[-1] = latest['record_revision']
        self.tasks(*args)
        final = self.show()
        self.assertEqual(final['scope'], literal)
        self.assertIn('Concurrent evidence to preserve', final['notes'])


    def test_documented_planning_close_forms_are_manual(self):
        # Retained recovery API: retirement must not turn manual closure into proof.
        self.tasks('done', 'T-1', '--by', 'fixture', '--reason', 'manual disposition')
        record = json.loads(self.tasks('show', 'T-1', '--worktree').stdout)
        self.assertEqual(record['closure']['provenance'], 'manual')
        self.assertFalse((self.repo / 'tasks/evidence/T-1.toml').exists())

    def test_identifier_guidance_matches_current_allocation_without_renaming_history(self):
        before = (self.repo / 'tasks/items/T-1.md').read_bytes()
        self.assertRegex(self.tasks('new-id').stdout.strip(), r'^T-\d+$')
        self.assertEqual((self.repo / 'tasks/items/T-1.md').read_bytes(), before)

    def test_runtime_failure_preserves_existing_contract(self):
        for path in (PLANNER, INTERACTIVE[0]):
            text = prose(path)
            with self.subTest(path=path):
                self.assertIn('same coordinator', text)
                self.assertIn('existing issue', text)
                self.assertIn('candidate evidence', text)
                self.assertIn('do not create replacement work', text)

    def test_active_planning_routes_share_github_authority(self):
        for path in (PLANNER, INTERACTIVE[0], 'skills/docs-sync/SKILL.md',
                     'skills/shared/RESEARCH-PLAN.md', HANDOFF):
            text = prose(path)
            with self.subTest(path=path):
                self.assertIn('GitHub', text)
                self.assertIn('ai-ready', text)
                self.assertIn('UNSAVED', text)
                for command in ('autowork tasks add', 'autowork tasks validate', 'autowork tasks prepare'):
                    self.assertNotIn(command, text)
        for name in ('plan-for-me', 'plan-with-me', 'docs-sync', 'work', 'autowork', 'pending'):
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
        center = prose(WORKCENTER)
        for required in ('Retired as an active backlog contract', 'migration',
                         'Preserve existing task data', 'currently owned work stays undispatched',
                         'immutable', 'autowork tasks prune'):
            self.assertIn(required, center)

    def test_runtime_handoffs_do_not_revive_old_executor(self):
        runner = prose('skills/autowork/SKILL.md')
        self.assertIn('never starts, resumes, installs or schedules', runner)
        self.assertIn('Orbi', runner)
        manual = prose('skills/work/SKILL.md')
        self.assertIn('Labels are not an atomic lock', manual)
        self.assertIn('fresh context window', manual)
        self.assertIn('independent review', manual)
        self.assertIn('GitHub', prose('skills/pending/SKILL.md'))


if __name__ == '__main__':
    unittest.main()
