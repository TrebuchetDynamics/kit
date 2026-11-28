"""Every bundled skill is available offline, including Impeccable's support tree."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompleteBundleTests(unittest.TestCase):
    def test_impeccable_snapshot_has_license_and_exact_hashes(self):
        pack = ROOT / 'skills/impeccable'
        manifest = json.loads((pack / 'UPSTREAM.json').read_text())
        self.assertEqual(manifest['revision'], '414603bf14c7a344edb466bb1f85690c77ce8b7d')
        self.assertIn('Apache License', (pack / 'LICENSE').read_text())
        self.assertTrue((pack / 'NOTICE.md').is_file())
        notices = json.loads((pack / 'THIRD-PARTY.json').read_text())
        self.assertEqual(set(notices), {'modern-screenshot', 'platform-design-skills'})
        for notice in notices.values():
            self.assertEqual(hashlib.sha256((pack / notice['license_file']).read_bytes()).hexdigest(), notice['license_sha256'])
        third = notices['modern-screenshot']
        license_bytes = (pack / third['license_file']).read_bytes()
        self.assertEqual(hashlib.sha256(license_bytes).hexdigest(), third['license_sha256'])
        self.assertIn(b'2021-present wxm', license_bytes)
        for name, digest in manifest['sha256'].items():
            self.assertEqual(hashlib.sha256((pack / name).read_bytes()).hexdigest(), digest, name)
        self.assertIn('scripts/impeccable', manifest['sha256'])
        self.assertIn('reference/routing.md', manifest['sha256'])

    def test_impeccable_default_uses_shared_finding_handoff_not_vendor_menu(self):
        skill = (ROOT / 'skills/impeccable/SKILL.md').read_text()
        portable = (ROOT / 'adapters/skills/impeccable/SKILL.md').read_text()
        self.assertIn('../shared/UI-FINDINGS.md', skill)
        for rule in ('take precedence', 'bare invocation', 'explicit design/edit',
                     'Scheduled, cron or unattended'):
            self.assertIn(rule, skill)
        self.assertIn('../../../skills/impeccable/SKILL.md', portable)
        self.assertIn('canonical modes take precedence', portable)

    def test_shared_keyboard_finding_contract_reuses_issue_across_skills(self):
        # Instruction coverage, not a simulation or proof of model publication.
        path = ROOT / 'skills/shared/UI-FINDINGS.md'
        self.assertTrue(path.is_file(), 'the two workflows need one evidence contract')
        guidance = ' '.join(path.read_text().split())
        for rule in ('route, state, viewport and source', 'observed', 'inferred',
                     'repeatable check', 'sanitized', 'freshness',
                     'open and closed issues', 'linked PRs', 'same fix and acceptance check',
                     'regardless of which skill found it', 'report its verified link',
                     '/checkout', 'Tab', 'Enter', 'validation error',
                     'single-invocation-specialist-handoff', 'ai-planning',
                     'blockedBy', 'ai-ready', 'last', 'stop after publication'):
            self.assertIn(rule, guidance)
        # Both public entries must resolve to this same contract.
        for name in ('impeccable', 'ui-taste'):
            skill = (ROOT / f'skills/{name}/SKILL.md').read_text()
            self.assertIn('../shared/UI-FINDINGS.md', skill, name)

if __name__ == '__main__':
    unittest.main()
