"""One machine planning authority: limits, prompt text and record-authority diffs."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import planning, planning_authority  # noqa: E402
from pi_autowork.engine import task_store  # noqa: E402

TASK = (ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store/tasks/items/T-1.md').read_text()
GOAL = (ROOT / 'pi-autowork/tests/fixtures/engine/fixtures/task_store/tasks/goals/G-1.md').read_text()


class PlanningAuthorityTests(unittest.TestCase):
    def test_paths_and_file_limits_are_one_rule_set(self):
        for path in ('tasks/items/T-1.md', 'tasks/goals/G-1.md',
                     'docs/plans/design.md', 'docs/specs/spec.md'):
            with self.subTest(path=path):
                self.assertEqual(str(planning_authority.path_allowed(path)), path)
        for path in ('../escape.md', 'tasks/evidence/X.md', '.git/config',
                     'docs/plans/../x.md', 'docs/plans/credentials.md',
                     'tasks/items/a/b.md', 'src/app.py'):
            with self.subTest(path=path), self.assertRaises(planning_authority.PlanningAuthorityError):
                planning_authority.path_allowed(path)
        with self.assertRaises(planning_authority.PlanningAuthorityError):
            planning_authority.check_files({'docs/plans/big.md': 'x' * (planning_authority.MAX_FILE + 1)})
        with self.assertRaises(planning_authority.PlanningAuthorityError):
            planning_authority.check_files({'docs/plans/secret.md': 'PASSWORD = "supersecretvalue"'})

    def test_prompt_text_is_generated_from_the_same_module(self):
        self.assertIn(planning_authority.policy_text(), planning.POLICY)
        self.assertIn('At most 64 files', planning.POLICY)
        self.assertIn('New live obligations require explicit live = "denied" and ownership = "owner"',
                      planning.POLICY)
        self.assertNotIn('At most 64 files, 256 KiB per file, 2 MiB total. Ordinary chat', planning.POLICY)

    def test_ordinary_task_fields_remain_editable(self):
        changed = (TASK.replace('rank = 1', 'rank = 5')
                   .replace('scope = "Read only"', 'scope = "Refine the plan"')
                   .replace('touches = ["src/"]', 'touches = ["src/", "tests/"]'))
        task_store.planner_authority(TASK, changed)

    def test_task_authority_transitions_are_refused(self):
        for changed, message in (
                (TASK.replace('status = "open"', 'status = "done"'), 'close'),
                (TASK.replace('live = "denied"', 'live = "authorized"'), 'live'),
                (TASK.replace('resources = []', 'resources = ["live"]'), 'live resource'),
                (TASK.replace('ownership = "worker"', 'ownership = "owner"'), 'ownership'),
                (TASK + '- Evidence: invented\n', 'evidence'),
                (TASK.replace('status = "open"', 'status = "open"') + '- Held by: owner\n', 'evidence|hold')):
            with self.subTest(message=message), self.assertRaisesRegex(task_store.StoreError, message):
                task_store.planner_authority(TASK, changed, path='tasks/items/T-1.md')

    def test_new_task_may_start_open_but_not_closed_or_live(self):
        new = TASK.replace('id = "T-1"', 'id = "T-2"')
        task_store.planner_authority(None, new, path='tasks/items/T-2.md')
        with self.assertRaisesRegex(task_store.StoreError, 'close'):
            task_store.planner_authority(None, new.replace('status = "open"', 'status = "done"'),
                                         path='tasks/items/T-2.md')
        with self.assertRaisesRegex(task_store.StoreError, 'live'):
            task_store.planner_authority(None, new.replace('live = "denied"', 'live = "authorized"'),
                                         path='tasks/items/T-2.md')

    def test_new_owner_live_obligation_is_allowed_without_execution_authority(self):
        pending = (TASK.replace('id = "T-1"', 'id = "T-2"')
                   .replace('resources = []', 'resources = ["live"]')
                   .replace('ownership = "worker"', 'ownership = "owner"')
                   .replace('section = "Now"', 'section = "Needs decision"'))
        task_store.planner_authority(None, pending, path='tasks/items/T-2.md')
        for changed in (
                pending.replace('live = "denied"', 'live = "authorized"'),
                pending.replace('live = "denied"\n', ''),
                *(pending.replace('ownership = "owner"', f'ownership = "{owner}"')
                  for owner in ('worker', 'coordinator', 'unknown')),
                pending.replace('ownership = "owner"\n', ''),
                task_store.edit(pending, {'live_scope': []}),
                task_store.edit(pending, {'live_actor': 'invented'}),
                task_store.edit(pending, {'closure_evidence': 'invented'}),
                pending + '- Evidence: invented\n',
                pending + '- Held by: owner\n'):
            with self.subTest(changed=changed), self.assertRaises(task_store.StoreError):
                task_store.planner_authority(None, changed, path='tasks/items/T-2.md')

    def test_existing_live_resource_gate_stays_protected_for_owner_tasks(self):
        owner = TASK.replace('ownership = "worker"', 'ownership = "owner"')
        live = owner.replace('resources = []', 'resources = ["live"]')
        for before, after in ((owner, live), (live, owner)):
            with self.subTest(before=before), self.assertRaisesRegex(task_store.StoreError, 'live resource'):
                task_store.planner_authority(before, after)
        task_store.planner_authority(live, live.replace('rank = 1', 'rank = 5'))

    def test_goal_progress_and_owner_notes_are_refused(self):
        task_store.planner_authority(GOAL, GOAL.replace('priority = 1', 'priority = 5'),
                                     goal=True, path='tasks/goals/G-1.md')
        for changed, message in (
                (GOAL.replace('status = "unmet"', 'status = "met"'), 'progress'),
                (GOAL + '- Evidence: invented\n', 'evidence'),
                (GOAL.replace('status = "unmet"', 'status = "unmet"') + '- Owner waiver: owner\n', 'evidence')):
            with self.subTest(message=message), self.assertRaisesRegex(task_store.StoreError, message):
                task_store.planner_authority(GOAL, changed, goal=True, path='tasks/goals/G-1.md')
        with self.assertRaisesRegex(task_store.StoreError, 'progress'):
            task_store.planner_authority(None, GOAL.replace('status = "unmet"', 'status = "partial"'),
                                         goal=True, path='tasks/goals/G-2.md')

    def test_record_schema_refusal_stays_in_the_store(self):
        with self.assertRaisesRegex(task_store.StoreError, 'malformed TOML|expected opening'):
            task_store.planner_authority(None, 'not a record\n', path='tasks/items/BAD.md')


if __name__ == '__main__':
    unittest.main()
