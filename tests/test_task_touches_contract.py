"""GitHub issue scope and dependency instruction contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'skills/shared/RESEARCH-PLAN.md'


class TaskTouchesContractTests(unittest.TestCase):
    def test_the_shared_protocol_owns_the_rule_once(self):
        text = ' '.join(PROTOCOL.read_text().split())
        for requirement in (
                'Every executable issue has an observable outcome',
                'bounded scope and exclusions',
                'Native GitHub dependencies own ordering'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, text)
        self.assertNotIn('Every executable task you create or rewrite gets `touches`', text)


if __name__ == '__main__':
    unittest.main()
