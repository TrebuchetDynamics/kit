"""`autowork tasks prune` and the dependent-safe, batched `tasks delete`, on a real Git repository."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
COMMAND = ROOT / 'pi-autowork/pi_autowork/command.py'
FIXTURE = ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store'
sys.path.insert(0, str(ROOT / 'pi-autowork/engine'))
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import task_commands as commands, task_prepare, task_prune  # noqa: E402


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'
        shutil.copytree(FIXTURE, self.repo)
        self.git('init', '-q')
        self.commit()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), '-c', 'user.email=f@example.invalid',
                               '-c', 'user.name=F', *args], check=True, capture_output=True, text=True).stdout

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-q', '--allow-empty', '-m', 'tasks')

    def tasks(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(COMMAND), 'tasks', *args], cwd=self.repo,
                                capture_output=True, text=True, timeout=60)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def add(self, title, *extra):
        out = self.tasks('add', '--goal', 'G-1', '--title', title, '--short', title, '--scope', 'x',
                         '--acceptance', 'done', '--checks', 'true', '--touches', 'src/', *extra).stdout
        return out.split()[-1]

    def done(self, tid):
        self.tasks('done', tid, '--by', 'owner', '--reason', 'finished')

    def exists(self, tid):
        return (self.repo / f'tasks/items/{tid}.md').exists()


class DeleteTests(Repo):
    def test_delete_refuses_while_a_surviving_task_depends_on_it(self):
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        refused = self.tasks('delete', 'T-1', ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn(dependent, refused.stderr)
        self.assertIn('nothing written', refused.stderr)
        self.assertTrue(self.exists('T-1'))

    def test_closure_prints_dependents_and_writes_nothing(self):
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        closure = json.loads(self.tasks('delete', 'T-1', '--closure').stdout)
        self.assertEqual(closure['dependents'], {'T-1': [dependent]})
        self.assertTrue(self.exists('T-1'))

    def test_force_deletes_and_names_the_dangling_edge(self):
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        out = self.tasks('delete', 'T-1', '--force').stdout
        self.assertIn('dangling', out)
        self.assertIn(dependent, out)
        self.assertFalse(self.exists('T-1'))

    def test_ids_file_deletes_a_set_whose_dependents_are_inside_it(self):
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        other = self.add('Other')
        ids = Path(self.tmp.name) / 'ids'
        ids.write_text(f'T-1\n# a comment\n\n{dependent}  # trailing\n')
        out = self.tasks('delete', '--ids-file', str(ids), str(self.repo)).stdout
        self.assertIn('2 tasks deleted', out)
        self.assertFalse(self.exists('T-1') or self.exists(dependent))
        self.assertTrue(self.exists(other))

    def test_ids_file_is_all_or_nothing(self):
        other = self.add('Other')
        ids = Path(self.tmp.name) / 'ids'
        ids.write_text(f'{other}\nT-404\n')
        refused = self.tasks('delete', '--ids-file', str(ids), ok=False)
        self.assertIn('unknown task T-404', refused.stderr)
        self.assertTrue(self.exists(other))

    def test_delete_needs_a_task_or_an_ids_file(self):
        self.assertEqual(self.tasks('delete', ok=False).returncode, 1)


class PruneTests(Repo):
    def plan(self):
        return json.loads(self.tasks('prune').stdout)

    def reasons(self, report):
        return {item['id']: item['reason'] for item in report['retain']}

    def test_plan_writes_nothing_and_apply_deletes_done_records_and_their_satisfied_edges(self):
        self.done('T-1')
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        self.commit()
        before = self.git('status', '--porcelain')
        report = self.plan()
        self.assertEqual(self.git('status', '--porcelain'), before)
        self.assertEqual(report['delete'], ['T-1'])
        self.assertEqual(report['edges'], [dict(task=dependent, removes=['T-1'], depends_on=[])])
        self.assertFalse(report['applied'])
        applied = json.loads(self.tasks('prune', '--apply', '--expect-plan', report['plan_revision']).stdout)
        self.assertTrue(applied['applied'])
        self.assertFalse(self.exists('T-1'))
        shown = json.loads(self.tasks('show', dependent, '--store', 'worktree').stdout)
        self.assertEqual(shown['depends_on'], [])
        self.assertTrue(json.loads(self.tasks('validate', '--worktree').stdout)['ok'])
        self.commit()
        again = self.plan()
        self.assertEqual((again['delete'], again['finished']), ([], 0))

    def test_a_changed_plan_refuses_apply(self):
        self.done('T-1')
        self.commit()
        refused = self.tasks('prune', '--apply', '--expect-plan', 'f' * 64, ok=False)
        self.assertIn('plan changed', refused.stderr)
        self.assertTrue(self.exists('T-1'))

    def test_open_records_are_never_candidates(self):
        report = self.plan()
        self.assertEqual((report['finished'], report['delete'], report['retain']), (0, [], []))

    def test_uncommitted_closure_is_retained(self):
        self.done('T-1')
        self.assertEqual(self.reasons(self.plan()), {'T-1': 'UNCOMMITTED'})

    def test_done_record_in_needs_decision_is_retained(self):
        self.tasks('place', 'T-1', 'Needs decision')
        self.done('T-1')
        self.commit()
        self.assertEqual(self.reasons(self.plan()), {'T-1': 'NEEDS_DECISION'})

    def test_verified_dependency_and_its_chain_are_retained(self):
        first = self.add('First')
        self.done(first)
        self.done('T-1')
        self.tasks('field', 'T-1', 'depends_on', first)
        self.add('Consumer', '--depends-on', 'T-1', '--verified-depends-on', 'T-1')
        self.commit()
        report = self.plan()
        self.assertEqual(self.reasons(report), {'T-1': 'VERIFIED_DEPENDENCY', first: 'RETAINED_DEPENDENT'})
        self.assertEqual(report['delete'], [])

    def test_superseded_dependency_is_retained_until_repointed(self):
        successor = self.add('Successor')
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        self.tasks('supersede', 'T-1', '--by', successor, '--reason', 'replaced')
        self.commit()
        report = self.plan()
        self.assertEqual(self.reasons(report), {'T-1': 'SUPERSEDED_DEPENDENCY'})
        self.assertIn(dependent, report['retain'][0]['detail'])

    def test_runtime_slot_and_held_dependent_retain(self):
        self.done('T-1')
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        self.commit()
        fact = dict(holder='slot', state='running', attempt=1, attempt_id='abcdef0123', owner_pid=4242,
                    age_seconds=7300)
        with patch.object(commands, 'in_flight_facts', return_value=({'T-1': fact}, [])):
            report = task_prune.plan(self.repo)
        self.assertEqual(self.reasons(report), {'T-1': 'RUNTIME_SLOT'})
        self.assertEqual(report['retain'][0]['detail'], 'slot running, attempt 1 (abcdef01), pid 4242, 2h old')
        with patch.object(commands, 'in_flight_facts', return_value=({dependent: fact}, [])):
            self.assertEqual(self.reasons(task_prune.plan(self.repo)), {'T-1': 'DEPENDENT_IN_FLIGHT'})
        with patch.object(commands, 'in_flight_facts', return_value=({}, ['worker slots cannot be read (x)'])):
            self.assertEqual(self.reasons(task_prune.plan(self.repo)), {'T-1': 'OWNERSHIP_UNKNOWN'})

    def test_current_document_blocks_and_frozen_history_does_not(self):
        self.done('T-1')
        (self.repo / 'docs').mkdir(exist_ok=True)
        (self.repo / 'docs/TODO-archive.md').write_text('# Archive\n\n- T-1 closed long ago\n')
        (self.repo / 'docs/record.md').write_text('<!-- doc-ref-guard: record -->\n\nT-1 history\n')
        self.commit()
        self.assertEqual(self.plan()['delete'], ['T-1'])
        (self.repo / 'docs/current.md').write_text('# Current\n\nSee T-1 for the proof; T-10 is unrelated.\n')
        self.commit()
        report = self.plan()
        self.assertEqual(self.reasons(report), {'T-1': 'CURRENT_DOC'})
        self.assertEqual(report['retain'][0]['detail'], 'docs/current.md:3 cites it')

    def test_citation_by_an_open_task_note_retains(self):
        self.done('T-1')
        other = self.add('Other')
        self.tasks('field', other, 'Evidence', 'see T-1 for the earlier gate')
        self.commit()
        self.assertEqual(self.reasons(self.plan()), {'T-1': 'CITED_BY_OPEN_TASK'})

    def test_summary_keeps_counts_and_reasons_only(self):
        self.done('T-1')
        report = json.loads(self.tasks('prune', '--summary').stdout)
        self.assertEqual(report['retained_by_reason'], {'UNCOMMITTED': 1})
        self.assertNotIn('retain', report)


class PrepareCheckTests(Repo):
    def check(self, *flags, code=0):
        result = self.tasks('prepare', '--check', *flags, ok=False)
        self.assertEqual(result.returncode, code, result.stderr)
        return json.loads(result.stdout), result.stderr

    def test_check_reads_uncommitted_task_files_and_says_so(self):
        report, err = self.check()
        self.assertEqual(report['read'], 'HEAD')
        self.assertIn('read: HEAD', err)
        self.tasks('field', 'T-1', 'touches', 'tasks/items/')
        report, err = self.check()
        self.assertEqual(report['read'], 'worktree')
        self.assertIn('read: worktree (includes 1 uncommitted task files)', err)
        self.assertIn('TOUCHES_TASK_STORE', report['diagnostic_summary']['by_code'])
        self.assertEqual(self.git('status', '--porcelain').strip(), 'M tasks/items/T-1.md')

    def test_an_interrupted_edit_is_ignored_with_a_note(self):
        self.tasks('field', 'T-1', 'touches', 'tasks/items/')
        (self.repo / '.git/autowork-tasks.transaction').write_text('[]')
        report, err = self.check()
        self.assertEqual(report['read'], 'HEAD')
        self.assertIn('1 uncommitted task files ignored', err)

    def test_filters_summary_and_exit_codes(self):
        self.tasks('field', 'T-1', 'touches', 'tasks/items/')
        report, _ = self.check('--summary')
        self.assertNotIn('diagnostics', report)
        self.assertEqual(report['diagnostic_summary']['by_code']['TOUCHES_TASK_STORE'], 1)
        report, _ = self.check('--code', 'TOUCHES_TASK_STORE', '--limit', '0')
        self.assertEqual((report['diagnostics'], report['diagnostics_truncated']), ([], 1))
        self.check('--fail-on-diagnostics', code=4)

    def test_frozen_fixture_and_allowlisted_hits_are_counted_not_listed(self):
        (self.repo / 'docs').mkdir(exist_ok=True)
        (self.repo / 'docs/TODO-archive.md').write_text('moved from TODO.md\n')
        (self.repo / 'testdata').mkdir()
        (self.repo / 'testdata/case.txt').write_text('TODO.md\n')
        (self.repo / 'rules_test.go').write_text('// a root TODO.md must be rejected\n')
        (self.repo / 'README.md').write_text('See TODO.md\n')
        (self.repo / task_prepare.ALLOWLIST).write_text('rules_test.go lint rule R1 must reject this name\n'
                                                        'README.md\n')
        self.commit()
        report, _ = self.check()
        legacy = [d['id'] for d in report['diagnostics'] if d['code'].startswith('LEGACY_')]
        self.assertEqual(legacy, ['README.md'])
        self.assertEqual((report['suppressed']['frozen'], report['suppressed']['intentional']), (1, 2))
        self.assertEqual(len(report['suppressed']['allowlist_problems']), 1)
        everything, _ = self.check('--all', '--code', 'LEGACY_CONSUMER', '--code', 'LEGACY_DOCUMENTATION')
        self.assertEqual(len(everything['diagnostics']), 4)

    def test_broken_source_names_the_nearest_anchor(self):
        (self.repo / 'plan.md').write_text('# Plan\n\n## Catches ledger: what each column measures\n')
        self.commit()
        self.assertEqual(task_prepare._target(self.repo, 'plan.md#catches-ledger'),
                         'plan.md has no heading #catches-ledger; did you mean '
                         '#catches-ledger-what-each-column-measures')


if __name__ == '__main__':
    unittest.main()
