"""Pointer-only licensing boundary and real offline skills installation, not model proof."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'skills/sakurai'
REPOSITORY = 'https://github.com/kociden/sakurai-skill'


class SakuraiTests(unittest.TestCase):
    def test_no_grant_ships_only_a_pointer_and_source_note(self):
        self.assertTrue((PACK / 'SKILL.md').is_file())
        self.assertEqual({p.relative_to(PACK).as_posix() for p in PACK.rglob('*') if p.is_file()},
                         {'SKILL.md', 'UPSTREAM.json'})
        pin = json.loads((PACK / 'UPSTREAM.json').read_text())
        self.assertEqual(pin['repository'], REPOSITORY)
        self.assertEqual(pin['distribution'], 'pointer-only')
        self.assertIsNone(pin['revision'])  # No silently substituted vendoring pin.
        self.assertEqual(pin['requested_revision'], 'c138943cd6c35276d02e9bcbcf9e4332e58aa2ef')
        self.assertEqual(pin['files'], {})
        self.assertIsNone(pin['license_evidence']['grant_url'])
        self.assertEqual(pin['license_evidence']['status'], 'no-redistribution-grant')
        skill = (PACK / 'SKILL.md').read_text()
        for target in (REPOSITORY, REPOSITORY + '/blob/main/skills/sakurai/SKILL.md',
                       REPOSITORY + '/tree/main/skills/sakurai/references',
                       '../shared/PONYTAIL.md', '../shared/COMMUNICATION.md', 'UPSTREAM.json'):
            self.assertIn('](' + target + ')', skill)
        for text in (skill, json.dumps(pin, ensure_ascii=False)):
            for caveat in ('AI summaries', 'automatic YouTube captions', 'transcription errors',
                           'not human-verified', 'Masahiro Sakurai', 'Sora Ltd.',
                           'https://www.youtube.com/@sora_sakurai_jp'):
                self.assertIn(caveat, text)
        standard = (ROOT / 'docs/skill-standard.md').read_text()
        self.assertIn('sakurai', standard)
        self.assertIn('pointer-only', standard)

if __name__ == '__main__':
    unittest.main()
