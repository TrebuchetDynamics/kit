"""Focused resilience repair: orphaned integration worktrees are preserved, not fatal."""
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import command  # noqa: E402
from pi_autowork.engine import parallel_integrate  # noqa: E402


class OrphanedWorktreeTests(unittest.TestCase):
    def test_an_orphaned_integration_worktree_is_quarantined_and_journaled(self):
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary) / 'common'
            common.mkdir()
            (common / 'journal.jsonl').touch()
            path = Path(temporary) / 'worktrees' / 'autowork-integration'
            path.mkdir(parents=True)
            (path / '.git').write_text('gitdir: /nonexistent/autowork/.git/worktrees/autowork-integration\n')
            (path / 'kept.txt').write_text('preserve me\n')

            kept = parallel_integrate.quarantine_worktree(common, path, 'orphaned integration worktree')

            self.assertFalse(path.exists())
            self.assertTrue(kept.is_dir())
            self.assertEqual((kept / 'kept.txt').read_text(), 'preserve me\n')
            events = [json.loads(line) for line in (common / 'journal.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'worktree_quarantined')
            self.assertEqual(events[-1]['worktree'], str(path))
            self.assertEqual(events[-1]['kept'], str(kept))


class RetryCommandTests(unittest.TestCase):
    def test_retry_requests_set_aside_for_an_exhausted_no_commit_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / 'repo'
            repo.mkdir()
            subprocess.run(['git', '-C', str(repo), 'init', '-q'], check=True)
            slots = repo / '.git' / 'autowork-execution' / 'slots'
            slots.mkdir(parents=True)
            (slots / 'T-1.json').write_text(json.dumps({
                'task_id': 'T-1', 'state': 'held', 'attempt': 2, 'reason': 'dead worker'}))
            state = Path(temporary) / 'state'
            state.mkdir()
            runner = SimpleNamespace(name='r', repo=str(repo), state_dir=str(state))
            args = SimpleNamespace(target='.', tasks=[], dry_run=False)
            with patch.object(command, 'resolve', return_value=(str(repo), 'r')), \
                    patch.object(command, 'runners', return_value=[runner]):
                self.assertEqual(command.cmd_retry(args, {}), 0)
            self.assertTrue((state / 'requests' / 'set-aside-T-1').is_file())
