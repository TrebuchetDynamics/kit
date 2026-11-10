"""File-overlap ranking and retry admission at the pure planner seam."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from support import store_fixture

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parallel_plan import plan


def task(tid, touches, status='open'):
    return {'id': tid, 'fields': {'Touches': touches, 'Status': status}}


class HotFileTests(unittest.TestCase):
    def test_heavily_shared_file_uses_available_workers(self):
        a, b, c, free = [task(tid, path) for tid, path in
                          [('A', 'a.py'), ('B', 'a.py'), ('C', 'a.py'), ('FREE', 'b.py')]]
        for phase in ('dispatching', 'running', 'integrating'):
            with self.subTest(phase=phase):
                running = [] if phase == 'dispatching' else [a]
                candidates = [a, b, c, free] if not running else [b, c, free]
                result = plan(candidates, running, all_tasks=[a, b, c, free],
                              finished={'A'} if phase == 'integrating' else ())
                self.assertEqual([t['id'] for t in result['dispatch']],
                                 ['A', 'FREE', 'B', 'C'] if not running else ['FREE', 'B', 'C'])
                self.assertEqual(result['waiting'], [])
        # A noncandidate or idle claim must not turn file overlap into a wait.
        c['fields']['Held by'] = 'an interactive session'
        result = plan([b, free], [a], all_tasks=[a, b, c, free])
        self.assertEqual(result, {'dispatch': [free, b], 'waiting': []})
        self.assertEqual(plan([a, b, free], all_tasks=[a, b, c, free])['dispatch'], [a, free, b])
        # The retry adapter uses the same policy, even beside an unlanded commit.
        import parallel_dispatch as dispatch
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            store_fixture.write_todo(repo, '''## Now
- [ ] A — running
  Scope: a.py
  Touches: a.py
  Acceptance: works
  Checks: test a
- [ ] B — retry
  Scope: a.py
  Touches: a.py
  Acceptance: works
  Checks: test a
## Needs decision
- [ ] C — later
  Touches: a.py
''')
            result = dispatch.retry_plan(repo, [
                {'task_id': 'A', 'state': 'reported', 'attempt': 1},
                {'task_id': 'B', 'state': 'held', 'attempt': 1}])
            self.assertEqual([t['id'] for t in result['dispatch']], ['B'])
            self.assertEqual(result['waiting'], [])

    def test_cold_overlap_keeps_ranking(self):
        a, b, free = task('A', 'a.py, a.py'), task('B', 'a.py'), task('FREE', 'b.py')
        # Repeated declarations and the same contract in multiple inputs count once;
        # done tasks do not turn a two-task overlap hot.
        result = plan([a, b, free], all_tasks=[a, b, free, task('DONE', 'a.py', 'done')])
        self.assertEqual(result, {'dispatch': [a, free, b], 'waiting': []})
        result = plan([b, free], [a], all_tasks=[a, b, free])
        self.assertEqual(result, {'dispatch': [free, b], 'waiting': []})


if __name__ == '__main__':
    unittest.main()
