"""Pinned 100x content and Kit's explicit invocation boundary (offline)."""
from hashlib import sha256
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/100x'
REPOSITORY = 'https://github.com/DeadInternetStudios/100x-engineer-skill'
REVISION = '8b43a726e3114882061f4b0b5dc1887bb96cefa3'
MODES = {'mockup', 'wrapup', 'judge', 'grind', 'solo', 'status', 'report', 'setup', 'adhd'}


class HundredXTests(unittest.TestCase):
    def test_pin_and_vendored_bytes(self):
        pin = json.loads((ROOT / 'skills/100x/UPSTREAM.json').read_text())
        self.assertEqual((pin['repository'], pin['revision'], pin['version'], pin['license']),
                         (REPOSITORY, REVISION, '0.1.1', 'MIT'))
        self.assertEqual(set(pin['source_paths']), {'skills/100x', 'LICENSE', 'NOTICE.md'} |
                         {f'skills/100x-{mode}/SKILL.md' for mode in MODES})
        upstream = SKILL / 'upstream'
        notice = (ROOT / 'skills/100x/upstream/NOTICE.md').read_text()
        self.assertIn('MIT License', (ROOT / 'skills/100x/upstream/LICENSE').read_text())
        pstack = pin['attribution']['pstack']
        self.assertEqual(pstack['notice'], 'upstream/NOTICE.md')
        for key, expected in (
                ('source', 'https://github.com/cursor/plugins/tree/main/pstack'),
                ('revision', 'bf0c7cd80abdbf7fe47b634978a7d1b4071f71a7'),
                ('license', 'MIT'), ('copyright', 'Copyright (c) 2026 Lauren Tan')):
            self.assertEqual(pstack[key], expected)
            self.assertIn(expected, notice)
        self.assertEqual(pin['files'], {
            path.relative_to(upstream).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in upstream.rglob('*') if path.is_file()
        })
        self.assertEqual({path.name for path in upstream.iterdir()},
                         {'PROTOCOL.md', 'LICENSE', 'NOTICE.md', 'modes', 'references', 'assets'})
        self.assertEqual({path.relative_to(ROOT).as_posix() for path in (upstream / 'assets').iterdir()}, {
            'skills/100x/upstream/assets/asset-check.mjs',
            'skills/100x/upstream/assets/economy-simulator.mjs',
            'skills/100x/upstream/assets/fresh-data-check.mjs',
            'skills/100x/upstream/assets/money-checks.test.mjs',
            'skills/100x/upstream/assets/property-checker.mjs',
            'skills/100x/upstream/assets/seed-localstorage.js',
        })
        self.assertTrue((ROOT / 'skills/100x/upstream/PROTOCOL.md').is_file())
        self.assertEqual({f'modes/{mode}.md' for mode in MODES},
                         {path.relative_to(upstream).as_posix() for path in (upstream / 'modes').iterdir()})
        self.assertEqual({p.relative_to(ROOT).as_posix()
                          for base in ('skills', 'adapters/skills')
                          for folder in (ROOT / base).glob('100x*') for p in folder.rglob('SKILL.md')},
                         {'skills/100x/SKILL.md', 'adapters/skills/100x/SKILL.md'})

    def test_wrapper_preflights_before_loading_the_selected_protocol(self):
        wrapper = (ROOT / 'skills/100x/SKILL.md').read_text()
        self.assertIn('`command -v 100x`', wrapper)
        self.assertIn('`100x --version`', wrapper)
        self.assertLess(wrapper.index('`command -v 100x`'), wrapper.index('`100x --version`'))
        self.assertLess(wrapper.index('`100x --version`'), wrapper.index('](upstream/PROTOCOL.md)'))
        self.assertIn('100x CLI not found on PATH; Kit requires 0.1.1.', wrapper)
        self.assertIn(f'{REPOSITORY}/blob/{REVISION}/docs/install.md#install-a-pinned-release', wrapper)
        self.assertNotRegex(wrapper, r'scripts/install\.sh|\b100x\s+(?:install|browsers)\b|\bnpm\s+install\b')
        self.assertEqual(set(re.findall(r'\]\(upstream/modes/([a-z]+)\.md\)', wrapper)), MODES)
        self.assertIn('Orbi (`/plan-for-me`)', wrapper)
        for link in re.findall(r'\]\(([^)#\s]+)(?:#[^)]+)?\)', wrapper):
            if '://' not in link:
                self.assertTrue((SKILL / link).is_file(), link)
        boundaries = wrapper.split('## Boundaries', 1)[1]
        for sibling in ('plan-with-me', 'plan-for-me', 'grill-me', 'unslop', 'lgtm', 'ponytail-review'):
            self.assertIn(f'`/{sibling}`', boundaries)
