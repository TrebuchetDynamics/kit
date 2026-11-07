"""`autowork tasks ...` against a real Git repository built from the TaskStore fixture."""
from datetime import date
import json
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / 'pi-autowork/pi_autowork/command.py'
FIXTURE = ROOT / 'pi-autowork/engine/fixtures/task_store'
sys.path.insert(0, str(ROOT / 'pi-autowork/engine'))
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from task_store import TaskStore, edit  # noqa: E402
from pi_autowork import task_commands as commands  # noqa: E402


class TaskCommandTests(unittest.TestCase):
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

    def qualify(self, tid, criterion, note='owner_waiver', text='waived for this scope'):
        """A complete structured waiver: actor, date and the criterion it covers."""
        self.tasks('field', tid, note, text)
        self.tasks('field', tid, 'waiver_actor', 'owner')
        self.tasks('field', tid, 'waiver_at', '2026-10-21')
        self.tasks('field', tid, 'waiver_for', criterion)

    def show(self, tid):
        self.commit()
        return json.loads(self.tasks('show', tid).stdout)

    def add(self, title, *extra):
        out = self.tasks('add', '--goal', 'G-1', '--title', title, '--short', title, '--scope', 'x',
                         '--acceptance', 'done', '--checks', 'true', '--touches', 'src/', *extra).stdout
        return out.split()[-1]

    def test_list_and_show_carry_the_store_only_display(self):
        rows = commands.cmd_list(self.repo)
        self.assertTrue(rows)
        self.assertTrue(all('display' in row for row in rows))
        for row in rows:
            self.assertEqual(set(row['display']),
                             {'state', 'bucket', 'why', 'question', 'pending', 'blocker', 'closure', 'record_revision'})
        show = commands.cmd_show(self.repo, rows[0]['id'])
        self.assertEqual(show['display'], rows[0]['display'])

    def test_worktree_validation_and_writes_leave_no_git_objects(self):
        # Exercise common-dir lookup and C-quoted alternates in a linked checkout.
        origin = self.repo.with_name('repo:\x01with-"quotes"')
        self.repo.rename(origin)
        self.repo = origin
        linked = origin / '.worktrees/validation'
        self.git('worktree', 'add', '-qb', 'validation', str(linked))
        self.repo = linked
        index_path = Path(self.git('rev-parse', '--absolute-git-dir').strip()) / 'index'
        # A private index alone still leaks add/write-tree/commit-tree objects.
        (self.repo / 'staged.txt').write_text('unrelated staged content\n')
        self.git('add', 'staged.txt')
        index = index_path.read_bytes()
        refs = self.git('show-ref', '--head')
        objects = self.git('count-objects', '-v')
        path = self.repo / 'tasks/items/T-1.md'
        path.write_text(path.read_text().replace('Read tasks', 'Edited task'))
        for args in (('validate', '--worktree'), ('prepare',),
                     ('field', 'T-1', 'title', 'Written task'),
                     ('show', 'T-1', '--worktree')):
            with self.subTest(command=args):
                result = self.tasks(*args)
                if args[0] == 'show':
                    self.assertEqual(json.loads(result.stdout)['title'], 'Written task')
                self.assertEqual(self.git('count-objects', '-v'), objects)
                self.assertEqual(index_path.read_bytes(), index)
                self.assertEqual(self.git('show-ref', '--head'), refs)
        path.write_text('invalid frontmatter\n')
        self.assertNotEqual(self.tasks('validate', '--worktree', ok=False).returncode, 0)
        self.assertEqual(self.git('count-objects', '-v'), objects)

    def test_add_then_show(self):
        legacy = self.add('Legacy task', '--id', 'T-010-ab')
        legacy_path = self.repo / 'tasks/items' / f'{legacy}.md'
        legacy_bytes = legacy_path.read_bytes()
        tid = self.add('Second task')
        text = (self.repo / f'tasks/items/{tid}.md').read_text()
        self.assertTrue(text.endswith('+++\n'), repr(text[-20:]))
        self.git('add', '--', f'tasks/items/{tid}.md')
        self.git('diff', '--cached', '--check')
        record = self.show(tid)
        self.assertEqual((record['title'], record['section'], record['status'], record['rank']),
                         ('Second task', 'Now', 'open', 2000))
        self.assertFalse(record['draft'])
        self.assertEqual((record['resources'], record['live']), ([], 'denied'))
        self.assertRegex(tid, r'^T-011-[0-9a-f]{8}$')
        self.assertRegex(self.tasks('new-id').stdout.strip(), r'^T-012-[0-9a-f]{8}$')
        self.assertEqual(legacy_path.read_bytes(), legacy_bytes)
        # Equal ranks exercise the ID tie-break with both suffix lengths.
        self.tasks('field', legacy, 'rank', '2000')
        self.assertTrue(json.loads(self.tasks('validate', '--worktree').stdout)['ok'])
        self.commit()
        self.assertTrue(json.loads(self.tasks('validate').stdout)['ok'])
        rows = json.loads(self.tasks('list').stdout)
        self.assertEqual([row['id'] for row in rows], ['T-1', legacy, tid])
        self.assertEqual([row['position'] for row in rows], [1, 2, 3])
        (self.repo / 'TODO.archive.md').write_text('- T-020-deadbeef — archived\n')
        self.assertRegex(self.tasks('new-id').stdout.strip(), r'^T-021-[0-9a-f]{8}$')
        self.assertFalse((self.repo / 'TODO.md').exists())
        self.assertFalse((self.repo / 'goals.json').exists())

    def test_add_list_flags_accept_json_arrays_and_repeated_items(self):
        self.add('Other prerequisite', '--id', 'T-2')
        expected = dict(touches=['[ab].py', 'b'], acceptance=['done, checked', 'proven'],
                        checks=['[ -f README.md ]', 'true'], depends_on=['T-1', 'T-2'],
                        verified_depends_on=['T-1', 'T-2'], resources=['exclusive', 'test-db'],
                        exclusions=['no push', 'no live'])
        for mode in ('repeated', 'json', 'mixed'):
            with self.subTest(mode=mode):
                flags = []
                for field, values in expected.items():
                    inputs = (values if mode == 'repeated' else [json.dumps(values)] if mode == 'json'
                              else [json.dumps(values[:1]), values[1], '[]'])
                    for value in inputs:
                        flags.extend(['--' + field.replace('_', '-'), value])
                tid = self.tasks('add', '--goal', 'G-1', '--title', mode, '--short', mode,
                                 '--scope', 'x', *flags).stdout.split()[-1]
                record = json.loads(self.tasks('show', tid, '--worktree').stdout)
                self.assertEqual({key: record[key] for key in expected}, expected)

    def test_add_refuses_nonstring_json_list_items_without_writing(self):
        before = self.git('status', '--porcelain', '--', 'tasks')
        for value in ('[1]', '[["a"]]', '[true]', '[null]'):
            with self.subTest(value=value):
                refused = self.tasks('add', '--goal', 'G-1', '--title', 'Bad list', '--short', 'Bad list',
                                     '--touches', value, ok=False)
                self.assertEqual(refused.returncode, 1)
                self.assertIn('touches', refused.stderr)
                self.assertNotIn('Traceback', refused.stderr)
                self.assertEqual(self.git('status', '--porcelain', '--', 'tasks'), before)

    def test_json_input_round_trips_literal_prose_without_shell_execution(self):
        # Run the documented shell form; expanding either command would leave a marker.
        prose = '  `touch backtick-ran` $(touch substitution-ran) $VAR "double" \'single\' café\nnext line  '
        bin_dir = self.repo / 'bin'
        bin_dir.mkdir()
        wrapper = bin_dir / 'autowork'
        wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(COMMAND))} "$@"\n')
        wrapper.chmod(0o755)
        env = {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'], 'VAR': 'expanded'}
        for index, source in enumerate(('payload.json', '- < payload.json')):
            with self.subTest(source=source):
                def invoke(verb, payload):
                    (self.repo / 'payload.json').write_text(json.dumps(payload), encoding='utf-8')
                    result = subprocess.run(['/bin/sh', '-c', f'autowork tasks {verb} --json {source}'],
                                            cwd=self.repo, env=env, capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse((self.repo / 'backtick-ran').exists())
                    self.assertFalse((self.repo / 'substitution-ran').exists())
                    return result.stdout.strip()

                gid = f'JSON-{index}'
                invoke(f'goal {gid}', dict(title=prose, source='docs/plan.md#json', priority=2))
                tid = invoke('add', dict(goal=gid, title=f'Literal {index}', short='Literal', scope=prose,
                                         acceptance=[prose], notes=prose, checks=['true'], touches=['src/'])).split()[-1]
                record = json.loads(self.tasks('show', tid, '--worktree').stdout)
                self.assertEqual((record['scope'], record['acceptance'], record['notes']), (prose, [prose], prose))
                changed = prose + '\nupdated'
                for label, value in (('scope', changed), ('acceptance', [changed]), ('notes', changed)):
                    invoke(f'field {tid}', dict(label=label, value=value))
                record = self.show(tid)
                self.assertEqual((record['scope'], record['acceptance'], record['notes']),
                                 (changed, [changed], changed))
                self.assertEqual(TaskStore.at(self.repo, 'HEAD').goals[gid].title, prose)

    def test_json_input_refuses_invalid_or_ambiguous_values_without_writing(self):
        path = self.repo / 'payload.json'
        before = self.git('status', '--porcelain', '--', 'tasks')
        for verb, payload in (
            (['add'], '{'), (['add'], '[]'), (['add'], '{"goal": "G-1"}'),
            (['add'], '{"goal": "G-1", "title": "x", "short": "x", "acceptance": "not an array"}'),
            (['add', '--title', 'flag'], '{"goal": "G-1", "title": "json", "short": "x"}'),
            (['field', 'T-1'], '{"label": "rank", "value": true}'),
            (['field', 'T-1'], '{"label": "scope", "value": 1}'),
            (['field', 'T-1'], '{"label": "acceptance", "value": [1]}'),
            (['goal', 'G-1'], '{"focus": "false"}'),
            (['goal', 'G-1'], '{"priority": true}'),
            (['goal', 'G-1'], '{"unknown": "x"}'),
            (['add'], '{"goal": "G-1", "title": "x", "short": "x", "notes": "raw", "sources": "docs/plan.md"}'),
        ):
            with self.subTest(verb=verb, payload=payload):
                path.write_text(payload)
                refused = self.tasks(*verb, '--json', str(path), ok=False)
                self.assertNotEqual(refused.returncode, 0)
                self.assertNotIn('Traceback', refused.stderr)
                self.assertEqual(self.git('status', '--porcelain', '--', 'tasks'), before)
        self.assertNotEqual(self.tasks('field', 'T-1', '--json', 'missing.json', ok=False).returncode, 0)

    def test_field_sets_a_typed_field_or_a_note(self):
        self.tasks('field', 'T-1', 'touches', 'src/, docs/')
        self.tasks('field', 'T-1', 'Held by', 'the owner; until 2026-10-27')
        self.tasks('field', 'T-1', 'notes', 'legacy note')
        record = self.show('T-1')
        self.assertEqual(record['touches'], ['src/', 'docs/'])
        self.assertIn('- Held by: the owner; until 2026-10-27', record['notes'])
        self.assertIn('- notes: legacy note', record['notes'])
        self.assertEqual(self.tasks('field', 'T-1', 'rank', 'high', ok=False).returncode, 1)
        self.assertEqual(self.tasks('field', 'T-1', 'status', 'done', ok=False).returncode, 1)

    def test_a_live_grant_is_structured_and_scope_bound(self):
        self.tasks('field', 'T-1', 'resources', 'live')
        self.tasks('field', 'T-1', 'live', 'authorized')
        self.tasks('field', 'T-1', 'live_actor', 'owner')
        self.tasks('field', 'T-1', 'live_at', '2026-11-04')
        self.tasks('field', 'T-1', 'live_scope', 'live')
        record = self.show('T-1')
        self.assertEqual((record['live'], record['live_actor'], record['live_at'], record['live_scope']),
                         ('authorized', 'owner', '2026-11-04', ['live']))
        refused = self.tasks('field', 'T-1', 'live_scope', 'network', ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn('undeclared scope network', refused.stderr)
        self.assertEqual(self.show('T-1')['live_scope'], ['live'])  # nothing written

    def test_a_waiver_is_structured_and_names_its_criterion(self):
        self.tasks('field', 'T-1', 'owner_waiver', 'criterion waived')
        self.tasks('field', 'T-1', 'waiver_actor', 'owner')
        self.tasks('field', 'T-1', 'waiver_at', '2026-11-04')
        record = self.show('T-1')
        self.assertEqual((record['waiver_actor'], record['waiver_at']), ('owner', '2026-11-04'))
        refused = self.tasks('field', 'T-1', 'waiver_for', 'not a criterion', ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn('waiver_for must name one of', refused.stderr)
        self.tasks('field', 'T-1', 'waiver_for', 'Pinned reads')
        self.assertEqual(self.show('T-1')['waiver_for'], 'Pinned reads')

    def test_place_into_needs_decision_changes_the_contract(self):
        sys.path.insert(0, str(ROOT / 'pi-autowork'))
        import parallel_status
        from pi_autowork import questions
        self.add('Waiting for decision', '--depends-on', 'T-1')
        before = self.show('T-1')
        self.tasks('place', 'T-1', 'Needs decision')
        after = self.show('T-1')
        self.assertEqual(after['section'], 'Needs decision')
        self.assertNotEqual(after['contract_hash'], before['contract_hash'])
        self.assertEqual(json.loads(self.tasks('why', 'T-1').stdout)['reasons'][0]['code'], 'NEEDS_DECISION')
        blockers = questions.update('', questions.build(parallel_status.snapshot(self.repo), self.repo))
        self.assertIn('### Q-T-1 ', blockers)
        for decision, dated in (('deferred', f'{date.today().isoformat()}: deferred'),
                                ('2001-02-03: deferred', '2001-02-03: deferred')):
            with self.subTest(decision=decision):
                self.tasks('place', 'T-1', 'Needs decision', '--decision', decision)
                self.assertIn(f'- Owner decision: {dated}\n', self.show('T-1')['notes'])
                updated = questions.update(blockers, questions.build(parallel_status.snapshot(self.repo), self.repo))
                self.assertNotIn('### Q-T-1 ', updated)

    def test_move_changes_only_the_rank(self):
        second = self.add('Second')
        before = self.show(second)
        self.tasks('move', second, 'up')
        after = self.show(second)
        self.assertLess(after['rank'], self.show('T-1')['rank'])
        self.assertEqual(after['contract_hash'], before['contract_hash'])
        self.assertEqual(self.git('status', '--porcelain'), '')
        first = json.loads(self.tasks('why', second).stdout)
        self.assertEqual((first['eligible'], first['first']), (True, True))

    def test_move_without_a_gap_rebalances_locally(self):
        ids = [self.add(f'Task {n}') for n in range(4)]
        for tid, rank in zip(['T-1', *ids], (1, 2, 3, 4, 5000)):
            self.tasks('field', tid, 'rank', str(rank))
        self.commit()
        out = self.tasks('move', ids[2], 'up').stdout
        changed = {line.split()[0] for line in out.removeprefix('ok ').split(', ')}
        ranks = {tid: self.show(tid)['rank'] for tid in ['T-1', *ids]}
        order = sorted(ranks, key=lambda tid: (ranks[tid], tid))
        self.assertEqual(order, ['T-1', ids[0], ids[2], ids[1], ids[3]])
        self.assertNotIn('T-1', changed, 'the run before the moved task keeps its ranks')
        self.assertNotIn(ids[0], changed)
        self.assertEqual(ranks[ids[3]], 5000, 'a neighbour with room is not renumbered')

    def test_hold_keeps_the_runner_off_until_release(self):
        before = self.show('T-1')
        self.tasks('hold', 'T-1', '--by', 'an interactive session', '--until', '2999-01-01')
        held = self.show('T-1')
        self.assertEqual((held['status'], held['contract_hash']), ('open', before['contract_hash']))
        self.assertIn('- Held by: an interactive session; until 2999-01-01', held['notes'])
        why = json.loads(self.tasks('why', 'T-1').stdout)
        self.assertEqual(why['reasons'], [{'code': 'HELD', 'detail': 'an interactive session; until 2999-01-01'}])
        self.assertEqual(self.tasks('hold', 'T-1', '--by', 'x', '--until', 'soon', ok=False).returncode, 1)
        self.tasks('release', 'T-1')
        self.assertNotIn('Held by', self.show('T-1')['notes'])
        self.assertTrue(json.loads(self.tasks('why', 'T-1').stdout)['first'])
        self.assertEqual(self.tasks('release', 'T-1', ok=False).returncode, 1)

    def test_manual_closure_records_provenance_without_verification(self):
        sys.path.insert(0, str(ROOT / 'pi-autowork'))
        from pi_autowork import fleet_view
        for kind in ('implementation', 'plan', 'inspection'):
            with self.subTest(kind=kind):
                tid = self.add(kind, '--kind', kind)
                before = self.show(tid)
                evidence = None if kind == 'inspection' else 'docs/review.md'
                self.tasks('done', tid, '--by', 'owner', '--reason', 'Stopped after review',
                           *(['--evidence', evidence] if evidence else []))
                record = self.show(tid)
                self.assertEqual(record['contract_hash'], before['contract_hash'])
                closure = record['closure']
                self.assertEqual((closure['provenance'], closure['actor'], closure['reason'], closure['evidence']),
                                 ('manual', 'owner', 'Stopped after review', evidence))
                self.assertRegex(closure['timestamp'], r'^\d{4}-\d\d-\d\dT.*\+00:00$')
                self.assertFalse((self.repo / 'tasks/evidence').exists())
                self.assertNotIn('Evidence:', record['notes'])
                listed = next(r for r in json.loads(self.tasks('list').stdout) if r['id'] == tid)
                why = json.loads(self.tasks('why', tid).stdout)
                self.assertEqual(listed['display'], record['display'])
                self.assertEqual(listed['display']['closure']['provenance'], 'manual')
                self.assertIs(listed['display']['closure']['verified'], False)
                self.assertEqual(listed['closure'], closure)
                self.assertEqual(why['closure'], closure)
                rows = fleet_view.task_rows(fleet_view.Runner('fixture', repo=str(self.repo)), include_closed=True)
                row = next(r for r in rows if r.task == tid)
                self.assertEqual(row.state, listed['display']['state'])
                self.assertEqual(row.why, listed['display']['closure']['detail'])
                self.assertEqual(row.state, 'Manual')
                self.assertEqual(row.why, f'Manually closed by owner at {closure["timestamp"]}; '
                                 'not coordinator-verified. Stopped after review')
                actions = fleet_view.task_actions(fleet_view.Runner('fixture', repo=str(self.repo)), row,
                                                   command='aw', script='aw.sh')
                self.assertEqual([(action.key, action.argv) for action in actions],
                                 [('x', ['aw', 'tasks', 'delete', tid, str(self.repo)])])

    def test_verified_dependencies_require_verification_or_an_owner_waiver(self):
        ordinary = self.add('Ordinary', '--depends-on', 'T-1')
        verified = self.add('Verified consumer', '--depends-on', 'T-1', '--verified-depends-on', 'T-1')
        self.tasks('done', 'T-1', '--by', 'owner', '--reason', 'Not verified')
        self.commit()
        self.assertTrue(json.loads(self.tasks('why', ordinary).stdout)['eligible'])
        why = json.loads(self.tasks('why', verified).stdout)
        self.assertEqual(why['reasons'], [{'code': 'DEPENDENCY_UNVERIFIED', 'detail': 'T-1'}])
        self.qualify('T-1', 'Pinned reads', text='Owner 2026-10-21: waive prerequisite proof for this scope')
        self.commit()
        self.assertTrue(json.loads(self.tasks('why', verified).stdout)['eligible'])

    def test_goal_met_requires_qualification_of_manual_closures(self):
        self.tasks('done', 'T-1', '--by', 'owner', '--reason', 'Hand closed')
        refused = self.tasks('goal', 'G-1', '--status', 'met', '--evidence', 'goal check: pass', ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn('T-1', refused.stderr)
        self.qualify('T-1', 'Pinned reads', note='owner_qualification',
                     text='Owner 2026-10-21: inspected result docs/review.md')
        accepted = self.tasks('goal', 'G-1', '--status', 'met', '--evidence', 'goal check: pass')
        self.assertIn('T-1', accepted.stdout)
        self.assertIn('docs/review.md', accepted.stdout)
        self.commit()
        self.assertIn('docs/review.md', TaskStore.at(self.repo, 'HEAD').goals['G-1'].body)

    def test_decide_records_direction_without_inventing_authority(self):
        path = self.repo / 'tasks/items/T-1.md'
        original = json.loads(self.tasks('show', 'T-1', '--worktree').stdout)
        self.tasks('decide', 'T-1', 'Use the smaller design')
        record = json.loads(self.tasks('show', 'T-1', '--worktree').stdout)
        self.assertIn(f'Owner decision: {date.today().isoformat()}: Use the smaller design', record['notes'])
        self.assertEqual((record['rank'], record['contract_hash'], record['status'], record['live']),
                         (original['rank'], original['contract_hash'], 'open', 'denied'))
        before = path.read_bytes()
        self.assertEqual(self.tasks('decide', 'T-1', '  ', ok=False).returncode, 1)
        self.assertEqual(self.tasks('decide', 'T-1', 'Changed', '--expect', original['record_revision'],
                                    ok=False).returncode, 1)
        self.assertEqual(path.read_bytes(), before)
        self.tasks('decide', 'T-1', 'Wait for input', '--section', 'Needs decision')
        record = json.loads(self.tasks('show', 'T-1', '--worktree').stdout)
        self.assertEqual(record['section'], 'Needs decision')
        self.tasks('decide', 'T-1', 'Input supplied; proceed', '--section', 'Next')
        record = json.loads(self.tasks('show', 'T-1', '--worktree').stdout)
        self.assertEqual(record['section'], 'Next')
        self.assertEqual(record['live'], 'denied')

    def test_decide_commit_hands_only_the_answer_to_the_committed_store(self):
        path = self.repo / 'tasks/items/T-1.md'
        other = self.repo / 'tasks/goals/G-1.md'
        other.write_text(other.read_text() + '\n- Other editor: unrelated task edit\n')
        path.write_text(path.read_text() + '\n- Other editor: unrelated note\n')
        (self.repo / 'staged.txt').write_text('keep staged\n')
        self.git('add', 'staged.txt')
        self.git('add', str(other.relative_to(self.repo)))
        staged = self.git('diff', '--cached', '--binary')
        original = TaskStore.at(self.repo, 'HEAD').tasks['T-1']
        revision = commands.cmd_show(self.repo, 'T-1', worktree=True)['record_revision']
        result = json.loads(self.tasks('decide', 'T-1', 'authorized', '--section', 'Next',
                                       '--expect', revision, '--commit').stdout)
        record = TaskStore.at(self.repo, 'HEAD').tasks['T-1']
        self.assertEqual(result['lifecycle']['state'], 'committed')
        self.assertEqual(result['commit'], self.git('rev-parse', 'HEAD').strip())
        self.assertIn('authorized', record.body)
        self.assertEqual((record.section, record.status, record.live), ('Next', 'open', 'denied'))
        self.assertEqual(record.ownership, original.ownership)
        self.assertEqual(record.contract_hash, original.contract_hash)
        self.assertNotIn('Other editor', record.body)
        self.assertIn('unrelated note', path.read_text())
        self.assertEqual(self.git('diff', '--cached', '--binary'), staged)
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD').split(),
                         ['tasks/items/T-1.md'])

    def test_decide_commit_recovers_a_previously_saved_answer(self):
        self.tasks('decide', 'T-1', 'Old local answer')
        self.tasks('decide', 'T-1', 'Use the offline option', '--commit')
        self.assertIn('Use the offline option', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)
        self.assertNotIn('tasks/', self.git('status', '--porcelain'))

    def test_decide_commit_keeps_answer_on_hook_failure_and_reports_pending(self):
        head = self.git('rev-parse', 'HEAD')
        hook = self.repo / '.git/hooks/pre-commit'
        hook.write_text('#!/bin/sh\necho blocked-by-test >&2\nexit 1\n')
        hook.chmod(0o755)
        refused = self.tasks('decide', 'T-1', 'Keep my answer', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('pending commit', refused.stderr)
        self.assertIn('blocked-by-test', refused.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn('Keep my answer', (self.repo / 'tasks/items/T-1.md').read_text())
        self.assertNotIn('Keep my answer', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)
        hook.unlink()
        self.tasks('decide', 'T-1', 'Keep my answer', '--commit')
        self.assertIn('Keep my answer', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)

    def test_decide_commit_refuses_staged_target_or_uncommitted_contract(self):
        path = self.repo / 'tasks/items/T-1.md'
        original = path.read_bytes()
        path.write_text(path.read_text() + '\n- Other editor: staged\n')
        self.git('add', str(path.relative_to(self.repo)))
        index = (self.repo / '.git/index').read_bytes()
        refused = self.tasks('decide', 'T-1', 'Not recorded', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('staged', refused.stderr)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index)
        self.assertNotIn('Not recorded', path.read_text())
        self.git('reset', '-q', 'HEAD', '--', str(path.relative_to(self.repo)))
        path.write_text(edit(original.decode(), {'scope': 'a different contract'}))
        refused = self.tasks('decide', 'T-1', 'Not recorded', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('contract', refused.stderr)
        self.assertNotIn('Not recorded', path.read_text())

    def test_decide_commit_refuses_head_branch_and_index_drift_after_save(self):
        path = self.repo / 'tasks/items/T-1.md'
        original = path.read_bytes()
        real_set = commands._set
        for drift in ('head', 'branch', 'index'):
            with self.subTest(drift=drift):
                before = self.git('rev-parse', 'HEAD')
                branch = self.git('branch', '--show-current').strip()
                def race(*args, **kwargs):
                    real_set(*args, **kwargs)
                    if drift == 'head':
                        self.git('commit', '--allow-empty', '-qm', 'external writer')
                    elif drift == 'branch':
                        self.git('checkout', '-qb', 'alternate')
                    else:
                        self.git('add', 'tasks/items/T-1.md')
                with patch.object(commands, '_set', side_effect=race):
                    with self.assertRaisesRegex(commands.CommandError, 'pending commit'):
                        commands.cmd_decide(self.repo, 'T-1', 'Retain this answer', commit=True)
                self.assertNotIn('Retain this answer', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)
                self.assertIn('Retain this answer', path.read_text())
                if drift == 'branch':
                    self.git('checkout', branch)
                if drift != 'head':
                    self.assertEqual(self.git('rev-parse', 'HEAD'), before)
                self.git('reset', '-q', 'HEAD', '--', 'tasks/items/T-1.md')
                path.write_bytes(original)

    def test_decide_commit_pins_publication_and_preserves_concurrent_commit(self):
        head = self.git('rev-parse', 'HEAD').strip()
        branch = self.git('symbolic-ref', 'HEAD').strip()
        real_git = commands._git
        with tempfile.TemporaryDirectory() as tmp:
            env = {'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
            blob_file = Path(tmp) / 'content'
            blob_file.write_text('concurrent committed content\n')
            real_git(self.repo, 'read-tree', head, env=env)
            blob = real_git(self.repo, 'hash-object', '-w', str(blob_file))
            real_git(self.repo, 'update-index', '--add', '--cacheinfo',
                     f'100644,{blob},concurrent.txt', env=env)
            tree = real_git(self.repo, 'write-tree', env=env)
            concurrent = self.git('commit-tree', tree, '-p', head, '-m', 'concurrent').strip()
            def race(repo, *args, **kwargs):
                if args[0] == 'commit':
                    # Another worktree can update the shared ref despite this checkout's locks.
                    external = Path(tmp) / 'external-git'
                    external.mkdir()
                    (external / 'HEAD').write_text(head + '\n')
                    (external / 'commondir').write_text(str(self.repo / '.git') + '\n')
                    real_git(repo, 'update-ref', branch, concurrent, head,
                             env={'GIT_DIR': str(external), 'GIT_WORK_TREE': str(repo)})
                return real_git(repo, *args, **kwargs)
            with patch.object(commands, '_git', side_effect=race):
                with self.assertRaisesRegex(commands.CommandError, 'pending commit'):
                    commands.cmd_decide(self.repo, 'T-1', 'Do not lose either edit', commit=True)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), concurrent)
        self.assertEqual(self.git('show', 'HEAD:concurrent.txt'), 'concurrent committed content\n')
        self.assertNotIn('Do not lose either edit', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)
        self.assertIn('Do not lose either edit', (self.repo / 'tasks/items/T-1.md').read_text())
        self.assertFalse((self.repo / '.git/index.lock').exists())
        self.assertFalse((self.repo / '.git/HEAD.lock').exists())

    def test_decide_commit_reserves_real_index_and_branch_through_commit(self):
        branch = self.git('branch', '--show-current').strip()
        real_git = commands._git
        attempted = []
        def race(repo, *args, **kwargs):
            if args[0] == 'commit':
                for argv in (('add', 'tasks/items/T-1.md'), ('checkout', '-qb', 'wrong-branch')):
                    attempted.append(subprocess.run(['git', '-C', str(repo), *argv],
                                                     capture_output=True, text=True))
            return real_git(repo, *args, **kwargs)
        with patch.object(commands, '_git', side_effect=race):
            receipt = commands.cmd_decide(self.repo, 'T-1', 'On the correct branch', commit=True)
        self.assertEqual(len(attempted), 2)
        self.assertTrue(all(r.returncode != 0 and 'index.lock' in r.stderr for r in attempted))
        self.assertEqual(self.git('branch', '--show-current').strip(), branch)
        self.assertEqual(receipt['commit'], self.git('rev-parse', 'HEAD').strip())
        self.assertIn('On the correct branch', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)

    def test_decide_commit_preserves_common_hook_helper_lookup(self):
        hooks = self.repo / '.git/hooks'
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\nexec "$(git rev-parse --git-common-dir)/hooks/policy-helper"\n')
        helper = hooks / 'policy-helper'
        helper.write_text('#!/bin/sh\necho shared-hook-helper-ran >&2\nexit 1\n')
        hook.chmod(0o755)
        helper.chmod(0o755)
        refused = self.tasks('decide', 'T-1', 'Do not skip common helper', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('shared-hook-helper-ran', refused.stderr)

    def test_decide_commit_preserves_worktree_configured_hooks(self):
        self.git('config', 'extensions.worktreeConfig', 'true')
        hooks = self.repo / 'local-hooks'
        hooks.mkdir()
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\necho worktree-hook-must-run >&2\nexit 1\n')
        hook.chmod(0o755)
        self.git('config', '--worktree', 'core.hooksPath', str(hooks))
        head = self.git('rev-parse', 'HEAD')
        refused = self.tasks('decide', 'T-1', 'Retain answer', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('worktree-hook-must-run', refused.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn('Retain answer', (self.repo / 'tasks/items/T-1.md').read_text())

    def test_decide_commit_preserves_branch_conditioned_config_and_hook_semantics(self):
        self.git('branch', '-m', 'main')
        hooks = self.repo / 'conditional-hooks'
        hooks.mkdir()
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\n'
                        'if [ "$(git symbolic-ref --quiet --short HEAD)" = main ]; then\n'
                        ' echo branch-hook-must-refuse >&2; exit 1\nfi\n')
        hook.chmod(0o755)
        config = self.repo / 'branch-config'
        self.git('config', '--file', str(config), 'core.hooksPath', str(hooks))
        self.git('config', 'includeIf.onbranch:main.path', str(config))
        head = self.git('rev-parse', 'HEAD')
        refused = self.tasks('decide', 'T-1', 'Do not skip main policy', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('branch-hook-must-refuse', refused.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)

    def test_decide_commit_retains_prepared_index_when_cas_response_is_lost(self):
        real_git = commands._git
        def lose_response(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if 'update-ref' in args:
                raise subprocess.TimeoutExpired('git update-ref', 60)
            return result
        with patch.object(commands, '_git', side_effect=lose_response):
            with self.assertRaisesRegex(commands.CommandError, 'prepared index retained'):
                commands.cmd_decide(self.repo, 'T-1', 'Published but response lost', commit=True)
        self.assertIn('Published but response lost', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)
        recovery = self.repo / '.git/index.lock'
        self.assertTrue(recovery.exists())
        env = {**os.environ, 'GIT_INDEX_FILE': str(recovery)}
        check = subprocess.run(['git', '-C', str(self.repo), 'diff', '--cached', '--name-only', 'HEAD'],
                               env=env, capture_output=True, text=True, check=True)
        self.assertEqual(check.stdout, '')
        self.assertFalse((self.repo / '.git/HEAD.lock').exists())

    def test_decide_commit_does_not_remove_a_new_writers_index_lock(self):
        replace = commands.os.replace
        lock = self.repo / '.git/index.lock'
        def another_writer(source, target):
            replace(source, target)
            if Path(source) == lock:
                lock.write_text('new writer owns this lock\n')
        with patch.object(commands.os, 'replace', side_effect=another_writer):
            result = commands.cmd_decide(self.repo, 'T-1', 'Answer committed', commit=True)
        self.assertEqual(result['lifecycle']['state'], 'committed')
        self.assertEqual(lock.read_text(), 'new writer owns this lock\n')

    def test_decide_commit_retains_index_if_install_fails_after_publication(self):
        replace = commands.os.replace
        lock = self.repo / '.git/index.lock'
        def fail_install(source, target):
            if Path(source) == lock:
                raise OSError('injected install failure')
            return replace(source, target)
        with patch.object(commands.os, 'replace', side_effect=fail_install):
            with self.assertRaisesRegex(commands.CommandError, 'prepared index retained'):
                commands.cmd_decide(self.repo, 'T-1', 'Published answer', commit=True)
        self.assertIn('Published answer', TaskStore.at(self.repo, 'HEAD').tasks['T-1'].body)
        self.assertTrue(lock.exists())

    def test_decide_commit_busy_index_is_not_removed_and_no_answer_is_published(self):
        lock = self.repo / '.git/index.lock'
        lock.write_text('another Git writer\n')
        head = self.git('rev-parse', 'HEAD')
        refused = self.tasks('decide', 'T-1', 'Pending answer', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('pending commit', refused.stderr)
        self.assertEqual(lock.read_text(), 'another Git writer\n')
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn('Pending answer', (self.repo / 'tasks/items/T-1.md').read_text())

    def test_decide_commit_section_still_refuses_active_worker(self):
        path = self.repo / 'tasks/items/T-1.md'
        original = path.read_bytes()
        with patch.object(commands, 'in_flight', return_value=({'T-1'}, [])):
            with self.assertRaisesRegex(commands.CommandError, 'held by a worker'):
                commands.cmd_decide(self.repo, 'T-1', 'Proceed', section='Needs decision', commit=True)
        self.assertEqual(path.read_bytes(), original)

    def test_blocker_resolution_commit_is_scoped_and_does_not_clear_the_hold(self):
        self.tasks('field', 'T-1', 'Held by', 'owner')
        self.commit()
        self.tasks('field', 'T-1', 'Blocker resolution', 'ab12cd; producer T-2', '--commit')
        record = TaskStore.at(self.repo, 'HEAD').tasks['T-1']
        self.assertIn('Blocker resolution: ab12cd; producer T-2', record.body)
        self.assertIn('Held by: owner', record.body)
        refused = self.tasks('field', 'T-1', 'live', 'authorized', '--commit', ok=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(TaskStore.at(self.repo, 'HEAD').tasks['T-1'].live, 'denied')

    def test_goals_lists_every_goal_record_in_priority_order(self):
        goals = json.loads(self.tasks('goals').stdout)
        self.assertTrue(goals)
        for goal in goals:
            self.assertLessEqual({'id', 'title', 'priority', 'source', 'status', 'focus', 'depends_on',
                                  'contract_hash', 'record_revision', 'path', 'notes', 'rev'}, set(goal))
        priorities = [g['priority'] for g in goals if g['priority'] is not None]
        self.assertEqual(priorities, sorted(priorities))

    def test_list_and_detail_share_python_presentation_meaning(self):
        rows = json.loads(self.tasks('list').stdout)
        row = next(row for row in rows if row['id'] == 'T-1')
        detail = json.loads(self.tasks('show', 'T-1').stdout)
        self.assertEqual(row['presentation'], detail['presentation'])
        self.assertEqual(set(detail['presentation']), {'tone', 'closure_tone'})
        self.assertNotIn('authorized', detail['presentation'])

    def test_commit_commits_only_task_edits_and_previews_first(self):
        (self.repo / 'unrelated.txt').write_text('stays uncommitted\n')
        self.tasks('decide', 'T-1', 'Use the smaller design')
        head = self.git('rev-parse', 'HEAD').strip()
        preview = json.loads(self.tasks('commit', '--dry-run').stdout)
        self.assertEqual((preview['files'], preview['commit'], preview['dry_run']), (['tasks/items/T-1.md'], None, True))
        self.assertIn('Owner decision', preview['diff'])
        self.assertEqual(preview['lifecycle']['state'], 'pending_commit')
        self.assertIn('committed records', preview['lifecycle']['message'])
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), head)
        result = json.loads(self.tasks('commit', '--message', 'answer T-1').stdout)
        self.assertEqual(result['commit'], self.git('rev-parse', 'HEAD').strip())
        self.assertEqual(result['lifecycle']['state'], 'committed')
        self.assertNotEqual(result['commit'], head)
        self.assertEqual(self.git('log', '-1', '--format=%s').strip(), 'answer T-1')
        self.assertEqual(self.git('show', '--name-only', '--format=', 'HEAD').split(), ['tasks/items/T-1.md'])
        self.assertIn('unrelated.txt', self.git('status', '--porcelain'))
        self.assertNotIn('tasks/', self.git('status', '--porcelain'))
        clean = json.loads(self.tasks('commit', '--dry-run').stdout)
        self.assertEqual(clean['files'], [])
        self.assertEqual(clean['lifecycle']['state'], 'clean')

    def test_pending_revision_refuses_changed_added_or_deleted_task_content(self):
        for change in ('edit', 'add', 'delete'):
            with self.subTest(change=change):
                self.tasks('decide', 'T-1', 'Reviewed answer')
                preview = json.loads(self.tasks('commit', '--dry-run').stdout)
                token = preview['pending_revision']
                self.assertEqual(len(token), 64)
                path = self.repo / 'tasks/items/T-1.md'
                original = path.read_bytes()
                extra = self.repo / 'tasks/extra note.txt'
                if change == 'edit':
                    path.write_bytes(original + b'\n- Later decision: preserve me\n')
                elif change == 'add':
                    extra.write_text('Not reviewed\n')
                else:
                    path.unlink()
                head = self.git('rev-parse', 'HEAD')
                index = (self.repo / '.git/index').read_bytes()
                refused = self.tasks('commit', '--expect-pending', token, ok=False)
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn('pending task edits changed', refused.stderr)
                self.assertEqual(self.git('rev-parse', 'HEAD'), head)
                self.assertEqual((self.repo / '.git/index').read_bytes(), index)
                if change == 'edit':
                    self.assertIn(b'preserve me', path.read_bytes())
                elif change == 'add':
                    self.assertEqual(extra.read_text(), 'Not reviewed\n')
                else:
                    self.assertFalse(path.exists())
                path.write_bytes(original)
                extra.unlink(missing_ok=True)

    def test_pending_revision_binds_head_and_preserves_unrelated_staged_edits(self):
        self.tasks('decide', 'T-1', 'Reviewed answer')
        token = json.loads(self.tasks('commit', '--dry-run').stdout)['pending_revision']
        self.git('commit', '--allow-empty', '-qm', 'head moved')
        refused = self.tasks('commit', '--expect-pending', token, ok=False)
        self.assertNotEqual(refused.returncode, 0)
        token = json.loads(self.tasks('commit', '--dry-run').stdout)['pending_revision']
        other = self.repo / 'unrelated.txt'
        other.write_text('staged outside tasks\n')
        self.git('add', '--', 'unrelated.txt')
        committed = json.loads(self.tasks('commit', '--expect-pending', token).stdout)
        self.assertEqual(committed['pending_revision'], token)
        self.assertNotIn('unrelated.txt', self.git('show', '--name-only', '--format=', 'HEAD'))
        self.assertIn('A  unrelated.txt', self.git('status', '--porcelain'))

    def test_pending_revision_refuses_branch_switch_and_unfinished_git_operation(self):
        self.tasks('decide', 'T-1', 'Reviewed answer')
        token = json.loads(self.tasks('commit', '--dry-run').stdout)['pending_revision']
        self.git('checkout', '-qb', 'another-branch')
        refused = self.tasks('commit', '--expect-pending', token, ok=False)
        self.assertIn('pending task edits changed', refused.stderr)
        token = json.loads(self.tasks('commit', '--dry-run').stdout)['pending_revision']
        head = self.git('rev-parse', 'HEAD').strip()
        marker = self.repo / '.git/MERGE_HEAD'
        marker.write_text(head + '\n')
        index = (self.repo / '.git/index').read_bytes()
        refused = self.tasks('commit', '--expect-pending', token, ok=False)
        self.assertIn('merge is in progress', refused.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), head)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index)
        self.assertTrue(marker.exists())
        # The guard and commit must resolve the same checkout despite ambient routing.
        with patch.dict(os.environ, {'GIT_DIR': str(self.repo / 'does-not-exist')}):
            with self.assertRaisesRegex(commands.CommandError, 'merge is in progress'):
                commands.cmd_commit(self.repo, dry_run=True)
            with self.assertRaisesRegex(commands.CommandError, 'merge is in progress'):
                commands.cmd_commit(self.repo, expected=token)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), head)
        self.assertEqual((self.repo / '.git/index').read_bytes(), index)
        self.assertTrue(marker.exists())

    def test_pending_revision_commits_frozen_bytes_if_editor_changes_after_staging(self):
        self.tasks('decide', 'T-1', 'Reviewed answer')
        token = json.loads(self.tasks('commit', '--dry-run').stdout)['pending_revision']
        path = self.repo / 'tasks/items/T-1.md'
        reviewed = path.read_text()
        original_git = commands._git
        def race(repo, *args, **kwargs):
            if args and args[0] == 'commit':
                path.write_text(reviewed + '\n- Later decision: preserve me\n')
            return original_git(repo, *args, **kwargs)
        with patch.object(commands, '_git', side_effect=race):
            result = commands.cmd_commit(self.repo, expected=token)
        self.assertEqual(self.git('show', 'HEAD:tasks/items/T-1.md'), reviewed)
        self.assertIn('preserve me', path.read_text())
        self.assertEqual(result['pending_revision'], token)

    def test_decide_refuses_closed_task_without_rewriting_history(self):
        self.tasks('done', 'T-1', '--by', 'owner', '--reason', 'manual closure')
        path = self.repo / 'tasks/items/T-1.md'
        before = path.read_bytes()
        refused = self.tasks('decide', 'T-1', 'Changed direction', ok=False)
        self.assertEqual(refused.returncode, 1)
        self.assertIn('open task', refused.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_supersede_names_its_successor(self):
        successor = self.add('Successor')
        self.tasks('supersede', 'T-1', '--by', successor, '--reason', 'replaced')
        record = self.show('T-1')
        self.assertEqual(record['status'], 'superseded')
        self.assertIn(f'- Superseded by: {successor}; replaced', record['notes'])

    def test_delete_removes_any_task_and_warns_without_refusing(self):
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        path = self.repo / 'tasks/items/T-1.md'
        with patch.object(commands, 'in_flight', return_value=({'T-1'}, ['a live coordinator lease'])):
            warnings = commands.cmd_delete(self.repo, 'T-1')
        self.assertFalse(path.exists())
        self.assertTrue((self.repo / f'tasks/items/{dependent}.md').exists())
        self.assertTrue(any('T-1' in warning and 'held' in warning for warning in warnings), warnings)
        self.assertIn('a live coordinator lease', warnings)
        self.assertTrue(any(dependent in warning for warning in warnings), warnings)
        self.commit()
        self.assertTrue(json.loads(self.tasks('validate').stdout)['ok'])
        self.assertEqual(self.tasks('show', 'T-1', ok=False).returncode, 1)

    def test_delete_cli_reports_dependents_and_proceeds(self):
        dependent = self.add('Dependent', '--depends-on', 'T-1')
        result = self.tasks('delete', 'T-1')
        self.assertIn('deleted', result.stdout)
        self.assertIn(dependent, result.stdout)
        self.assertFalse((self.repo / 'tasks/items/T-1.md').exists())
        self.commit()
        self.assertEqual(self.tasks('show', 'T-1', ok=False).returncode, 1)

    def test_list_and_why_disclose_selection_only_even_for_a_runtime_hold(self):
        from pi_autowork.engine import parallel_status
        slots = self.repo / '.git/autowork-execution/slots'
        slots.mkdir(parents=True)
        held = dict(task_id='T-1', state='held', attempt=1, cause='blocker',
                    reason='needs a signed artifact', started_at=1, worker=None,
                    worktree=str(self.repo / '.worktrees/held'))
        slot = slots / 'T-1.json'
        slot.write_text(json.dumps(held))
        self.assertEqual(parallel_status.snapshot(self.repo)['tasks'][0]['state'], 'held')
        revision = self.git('rev-parse', 'HEAD').strip()
        expected = dict(only=True, admission_evaluated=False, runtime_evaluated=False,
                        source='committed', ref='HEAD', revision=revision, revision_ephemeral=False)
        row, = json.loads(self.tasks('list').stdout)
        why = json.loads(self.tasks('why', 'T-1').stdout)
        self.assertEqual((row['position'], row['blocked_by'], why['eligible'], why['first']),
                         (1, None, True, True))
        for result in (row, why):
            self.assertIn('selection', result)
            self.assertEqual(result['selection'], expected)
        self.assertEqual(json.loads(slot.read_text()), held, 'reading selection cannot clear a runtime hold')

    def test_selection_metadata_pins_explicit_revision_and_does_not_imply_admission(self):
        self.tasks('field', 'T-1', 'ownership', 'owner')
        self.commit()
        revision = self.git('rev-parse', 'HEAD').strip()
        self.tasks('place', 'T-1', 'Needs decision')
        self.commit()
        row, = json.loads(self.tasks('list', '--rev', revision).stdout)
        why = json.loads(self.tasks('why', 'T-1', '--rev', revision).stdout)
        for result in (row, why):
            self.assertIn('selection', result)
            self.assertEqual(result['selection'], dict(
                only=True, admission_evaluated=False, runtime_evaluated=False,
                source='committed', ref=revision, revision=revision, revision_ephemeral=False))
        self.assertEqual(row['position'], 1)
        self.assertTrue(why['eligible'], 'selection eligibility is not worker authority')
        self.assertEqual(json.loads(self.tasks('why', 'T-1').stdout)['reasons'][0]['code'], 'NEEDS_DECISION')
        unknown = json.loads(self.tasks('why', 'T-404').stdout)
        self.assertEqual(unknown['reasons'][0]['code'], 'UNKNOWN_TASK')
        self.assertIn('selection', unknown)
        self.assertEqual(unknown['selection']['revision'], self.git('rev-parse', 'HEAD').strip())

    def test_worktree_list_identifies_its_ephemeral_proof_not_head(self):
        revision = self.git('rev-parse', 'HEAD').strip()
        self.tasks('field', 'T-1', 'title', 'Pending title')
        row, = json.loads(self.tasks('list', '--worktree').stdout)
        self.assertEqual(row['title'], 'Pending title')
        self.assertIn('selection', row)
        metadata = row['selection']
        self.assertEqual({k: v for k, v in metadata.items() if k != 'revision'}, dict(
            only=True, admission_evaluated=False, runtime_evaluated=False,
            source='working-tree', ref=None, revision_ephemeral=True))
        self.assertRegex(metadata['revision'], r'^[0-9a-f]{40,64}$')
        self.assertNotEqual(metadata['revision'], revision)
        with self.assertRaises(subprocess.CalledProcessError):
            self.git('cat-file', '-e', metadata['revision'])
        committed, = json.loads(self.tasks('list').stdout)
        self.assertEqual(committed['title'], 'Read tasks')
        self.assertEqual(committed['selection']['revision'], revision)

    def test_why_and_list_name_their_reasons(self):
        before = self.git('status', '--porcelain', '--', 'tasks')
        for flags in (('--depends-on', 'T-404'), ('--depends-on', '["T-404"]')):
            with self.subTest(flags=flags):
                refused = self.tasks('add', '--goal', 'G-1', '--title', 'Missing dependency',
                                     '--short', 'Missing dependency', *flags, ok=False)
                self.assertEqual(refused.returncode, 1)
                self.assertIn('T-404', refused.stderr)
                self.assertEqual(self.git('status', '--porcelain', '--', 'tasks'), before)
        blocked = self.add('Blocked', '--depends-on', 'T-1')
        self.assertEqual(self.tasks('validate', '--worktree', ok=False).returncode, 0)
        self.commit()
        reasons = json.loads(self.tasks('why', blocked).stdout)
        self.assertEqual(reasons['reasons'], [{'code': 'DEPENDENCY_UNFINISHED', 'detail': 'T-1'}])
        rows = {row['id']: row for row in json.loads(self.tasks('list', '--json').stdout)}
        shown = json.loads(self.tasks('show', blocked, '--json').stdout)
        self.assertEqual(rows[blocked]['display'], shown['display'])
        self.assertEqual(shown['display'], dict(state='Waiting', bucket='Waiting',
                         why='dependency: T-1', question=False, pending=False,
                         blocker='dependency unfinished', closure=None, record_revision=shown['record_revision']))
        self.assertEqual((rows['T-1']['position'], rows[blocked]['blocked_by']), (1, 'DEPENDENCY_UNFINISHED'))

    def test_validate_fails_on_a_broken_file(self):
        self.assertEqual(json.loads(self.tasks('validate').stdout)['tasks'], 1)
        path = self.repo / 'tasks/items/T-1.md'
        path.write_text(path.read_text().replace('rank = 1', 'rank = ['))
        broken = self.tasks('validate', '--worktree', ok=False)
        self.assertEqual(broken.returncode, 1)
        self.assertRegex(broken.stderr, r'tasks/items/T-1.md:\d+:')
        self.commit()
        self.assertEqual(self.tasks('validate', ok=False).returncode, 1)

    def test_validate_refuses_json_encoded_list_items(self):
        path = self.repo / 'tasks/items/T-1.md'
        original = path.read_text()
        for field in ('touches', 'acceptance', 'checks', 'depends_on', 'resources', 'exclusions',
                      'verified_depends_on'):
            with self.subTest(field=field):
                path.write_text(edit(original, {field: ['["a", "b"]']}))
                refused = self.tasks('validate', '--worktree', ok=False)
                self.assertEqual(refused.returncode, 1)
                self.assertRegex(refused.stderr, rf'tasks/items/T-1.md:\d+:.*{field}')
                self.assertIn('JSON', refused.stderr)

    def test_a_write_that_breaks_the_store_is_undone(self):
        path = self.repo / 'tasks/items/T-1.md'
        before = path.read_bytes()
        result = self.tasks('field', 'T-1', 'goal', 'NOPE', ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('unknown goal', result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_goal_adds_and_changes_a_goal_and_moves_focus(self):
        self.assertIn('needs --source, --priority', self.tasks('goal', 'G-2', '--title', 'Two', ok=False).stderr)
        self.assertEqual(self.tasks('goal', 'G-2', '--title', 'Two', '--source', 'docs/plan.md#two',
                                    '--priority', '2', '--depends-on', 'G-1').stdout.strip(), 'added goal G-2')
        refused = self.tasks('goal', 'G-2', '--status', 'met', ok=False)
        self.assertIn('needs --evidence', refused.stderr)
        self.tasks('goal', 'G-2', '--status', 'met', '--evidence', 'python3 -m unittest passed (offline)')
        self.tasks('goal', 'G-2', '--focus')
        self.commit()
        store = TaskStore.at(self.repo, 'HEAD')
        two = store.goals['G-2']
        self.assertEqual((two.title, two.priority, two.status, two.focus, two.depends_on),
                         ('Two', 2, 'met', True, ('G-1',)))
        self.assertIn('- Evidence: python3 -m unittest passed (offline)', two.body)
        self.assertEqual([g.id for g in store.goals.values() if g.focus], ['G-2'])  # at most one
        self.assertIn('is a task', self.tasks('goal', 'T-1', '--title', 'x', ok=False).stderr)

    def test_the_first_goal_starts_a_new_store(self):
        shutil.rmtree(self.repo / 'tasks')
        self.commit()
        self.assertEqual(self.tasks('goal', 'G-1', '--title', 'One', '--source', 'docs/plan.md#one',
                                    '--priority', '1').stdout.strip(), 'added goal G-1')
        first = self.add('First task')
        self.assertEqual(json.loads(self.tasks('validate', '--worktree').stdout)['tasks'], 1)
        self.assertEqual(self.show(first)['goal'], 'G-1')

    def test_an_unconverted_repository_is_refused(self):
        shutil.rmtree(self.repo / 'tasks')
        self.commit()
        result = self.tasks('list', ok=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('no task store', result.stderr)


if __name__ == '__main__':
    unittest.main()
