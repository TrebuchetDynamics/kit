"""The display is evidence for a person, never an authorization input."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ('task_display', 'runner_display', 'record_display', 'closure_display')


class DisplayAuthorityTests(unittest.TestCase):
    def test_display_words_never_reach_an_authority_module(self):
        engine = ROOT / 'Src/pi_autowork/engine'
        offenders = sorted(path.relative_to(ROOT).as_posix() for path in engine.rglob('*.py')
                           if any(name in path.read_text() for name in FORBIDDEN))
        self.assertEqual(offenders, [])


if __name__ == '__main__':
    unittest.main()
