"""Ponytail reaches worker and reviewer prompts with the explicit runner level."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'pi-autowork'))
from pi_autowork import common  # noqa: E402
from pi_autowork.engine import parallel_dispatch  # noqa: E402


class PonytailRunnerTests(unittest.TestCase):
    def test_level_defaults_to_full_and_refuses_unknown_values(self):
        self.assertEqual(common.ponytail_level({}), 'full')
        self.assertEqual(common.ponytail_level({'PI_AUTOWORK_PONYTAIL_LEVEL': 'ultra'}), 'ultra')
        self.assertEqual(common.ponytail_level({'PI_AUTOWORK_PONYTAIL_LEVEL': 'nonsense'}), 'full')

    def test_worker_prompt_carries_level_and_method_path(self):
        task = {'id': 'T-1', 'title': 'Test', 'fields': {'Touches': 'src/'},
                'contract': '- Scope: test', 'rev': 'HEAD'}
        with patch.dict(os.environ, {'PI_AUTOWORK_PONYTAIL_LEVEL': 'lite'}), \
                patch.object(parallel_dispatch, 'earlier_task_work', return_value=[]):
            text = parallel_dispatch.prompt(task, '/tmp/worktree', 'branch', 'base', '/tmp/report.json')
        self.assertIn('Ponytail level: lite', text)
        self.assertIn(str(ROOT / 'skills/shared/PONYTAIL.md'), text)
        self.assertIn('smallest complete change', text)

    def test_reviewer_prompt_names_the_review_protocol_and_off_is_explicit(self):
        review = common.ponytail_prompt('full', review=True)
        self.assertIn(str(ROOT / 'skills/ponytail/upstream/skills/ponytail-review/PROTOCOL.md'), review)
        off = common.ponytail_prompt('off')
        self.assertIn('Ponytail is off', off)
        self.assertNotIn('smallest complete change', off)


if __name__ == '__main__':
    unittest.main()
