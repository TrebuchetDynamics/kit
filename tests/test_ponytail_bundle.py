"""Offline Ponytail provenance, universal routing and installed resource checks."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'skills/ponytail'
NAMES = {'ponytail', 'ponytail-review', 'ponytail-audit', 'ponytail-debt',
         'ponytail-gain', 'ponytail-help'}
METHOD = ROOT / 'skills/shared/PONYTAIL.md'
COMMUNICATION = ROOT / 'skills/shared/COMMUNICATION.md'


class PonytailBundleTests(unittest.TestCase):
    def test_pinned_resources_have_no_nested_skill_or_hook_registration(self):
        self.assertTrue((PACK / 'UPSTREAM.json').is_file(), 'Ponytail must work offline')
        pin = json.loads((PACK / 'UPSTREAM.json').read_text())
        self.assertEqual(set(pin['skills']), NAMES)
        self.assertRegex(pin['revision'], r'^[0-9a-f]{40}$')
        self.assertEqual(pin['repository'], 'https://github.com/DietrichGebert/ponytail')
        for source, item in pin['files'].items():
            with self.subTest(source=source):
                self.assertEqual(hashlib.sha256((PACK / item['path']).read_bytes()).hexdigest(), item['sha256'])
        self.assertEqual(list((PACK / 'upstream').rglob('SKILL.md')), [])
        self.assertIn('MIT License', (PACK / 'upstream/LICENSE').read_text())
        self.assertFalse((PACK / 'upstream/hooks').exists())
        self.assertFalse((PACK / 'upstream/package.json').exists())
        self.assertTrue((PACK / 'upstream/scripts/ponytail-map.cjs').is_file())
        for name in NAMES:
            self.assertTrue((ROOT / f'skills/{name}/SKILL.md').is_file())
            self.assertTrue((ROOT / f'adapters/skills/{name}/SKILL.md').is_file())

    def test_every_entry_reaches_shared_method_and_language_without_optional_routing(self):
        # Direct links keep standalone and native skill invocation covered too.
        for folder in (ROOT / 'skills', ROOT / 'adapters/skills'):
            for skill in folder.glob('*/SKILL.md'):
                links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', skill.read_text())
                targets = {(skill.parent / link).resolve() for link in links if '://' not in link}
                with self.subTest(skill=skill.relative_to(ROOT)):
                    self.assertIn(METHOD, targets)
                    self.assertIn(COMMUNICATION, targets)
                    self.assertTrue(COMMUNICATION.is_file())

    def test_review_routes_regressions_to_the_existing_change_owner(self):
        # Instruction contracts, not a simulation of model decisions or GitHub writes.
        text = ' '.join((ROOT / 'skills/ponytail-review/SKILL.md').read_text().split())
        for contract in (
            '## Finding routing and receipt',
            'current PR URL and head SHA',
            'owning issue URL',
            'severity, concrete regression evidence (source lines or reproducer)',
            'required check with its expected result',
            'review receipt includes each finding and owner link',
            'Keep the existing live owner and review lane',
            'Do not open a tracking issue or start repairs',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

    def test_review_gates_publication_and_keeps_unknown_findings_inline(self):
        text = ' '.join((ROOT / 'skills/ponytail-review/SKILL.md').read_text().split())
        for contract in (
            'Read the existing review/comments before any authorized post',
            'Reuse the existing finding link',
            'unchanged evidence produces no duplicate post',
            'Post only to that existing PR or issue thread when review publication is already authorized',
            'Read-only/no-write review never posts',
            'If ownership is unknown, return the finding inline',
            'If a required read fails, report the concrete error, missing input and safe resume action',
            'hold publication rather than guess ownership or absence of a prior finding',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

    def test_portable_review_reaches_the_canonical_routing_receipt(self):
        adapter = ROOT / 'adapters/skills/ponytail-review/SKILL.md'
        text = adapter.read_text()
        self.assertIn('finding-routing receipt', text)
        links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', text)
        canonical = ROOT / 'skills/ponytail-review/SKILL.md'
        self.assertIn(canonical, {(adapter.parent / link).resolve() for link in links})
        self.assertIn('## Finding routing and receipt', canonical.read_text())
        self.assertIn('disable-model-invocation: true', text)
        self.assertIn('read-only/no-write/no-push restrictions', text)

    def test_debt_requires_evidence_of_a_reached_revisit_trigger(self):
        # Instruction contracts from #177, not a model or publication simulation.
        text = ' '.join((ROOT / 'skills/ponytail-debt/SKILL.md').read_text().split())
        for contract in (
            'shortcut:', 'ponytail:', 'existing ledger as context',
            'source, supported configuration or measured evidence',
            'marker location and text, ceiling, stated revisit trigger',
            'breached assumption, bounded remedy and verification check',
            'Do not file markers simply because they exist',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)
        # Positive: supported capacity exceeds the documented assumption.
        self.assertIn('100 entries', text)
        self.assertIn('supported configuration now permits 200', text)
        self.assertIn('one issue', text)

    def test_debt_unreached_missing_and_unsupported_triggers_create_no_issue(self):
        text = ' '.join((ROOT / 'skills/ponytail-debt/SKILL.md').read_text().split())
        for contract in (
            'still permits only 100 entries: trigger unreached, no issue',
            'no stated revisit trigger: tag `no-trigger`, no issue',
            'Missing or conflicting evidence: hold that finding',
            'exact missing input and resume condition',
            'continue independent eligible findings',
            'concrete error and safe resume action',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

    def test_debt_uses_the_single_invocation_handoff_and_keeps_scan_safeguards(self):
        text = ' '.join((ROOT / 'skills/ponytail-debt/SKILL.md').read_text().split())
        self.assertIn('../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff', text)
        for contract in (
            'bare invocation analyzes and publishes eligible outcomes',
            'without selection, confirmation or a second command',
            'read-only/dry-run/no-write', 'no-dispatch', 'Stop after publication',
            'Git exit 1 means no matches', 'literal data', 'Inspect hits before counting',
            'tracked-but-ignored files', 'No-marker output',
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)
        handoff = ' '.join((ROOT / 'skills/shared/PLAN-HANDOFF.md').read_text().split())
        for contract in ('open and closed issues', 'linked PRs and ownership',
                         'Group findings that share a fix and acceptance check',
                         'native `blockedBy`', 'entire batch', '**final publication phase**'):
            with self.subTest(handoff=contract):
                self.assertIn(contract, handoff)
        method = (ROOT / 'skills/shared/PONYTAIL.md').read_text()
        self.assertNotIn('Standalone review/audit/debt commands report only', method)

    def test_portable_debt_routes_to_canonical_trigger_analysis(self):
        adapter = ROOT / 'adapters/skills/ponytail-debt/SKILL.md'
        text = adapter.read_text()
        canonical = ROOT / 'skills/ponytail-debt/SKILL.md'
        links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', text)
        self.assertIn(canonical, {(adapter.parent / link).resolve() for link in links})
        self.assertIn('trigger analysis and issue handoff', text)
        self.assertIn('disable-model-invocation: true', text)
        self.assertIn('read-only/no-write/no-push restrictions', text)
        policy = yaml.safe_load((adapter.parent / 'agents/openai.yaml').read_text())
        self.assertFalse(policy['policy']['allow_implicit_invocation'])
        help_text = (ROOT / 'skills/ponytail-help/SKILL.md').read_text()
        self.assertIn('Publish issues for triggered shortcuts', help_text)

    def test_audit_single_invocation_modes_and_finding_dispositions(self):
        # Source contracts, not simulated model choices or live issue publication.
        text = ' '.join((ROOT / 'skills/ponytail-audit/SKILL.md').read_text().split())
        cases = {
            'bare invocation': (
                'single-invocation specialist handoff',
                '../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff',
                'ordinary `/ponytail-audit` invocation analyzes the requested scope and publishes',
                'without selection, confirmation or a planner invocation',
                'Do not apply the upstream report-only route or 20-finding cap to publication',
            ),
            'actionable evidence': (
                'severity, source/reproducer evidence, expected load where relevant and next action',
                'an observable check with its expected result',
                'A badge, unread area or preference alone is not actionable',
            ),
            'mixed actionable and held': (
                'all supported, buildable, uncovered outcomes',
                'Group findings that share a fix and acceptance check',
                'Hold only uncertain findings with the reason and resume condition',
                'continue independent qualifying work',
                'open and closed issues, linked PRs and actual ownership',
                'covered, completed, owned and unsupported findings create no duplicate issue',
            ),
            'zero qualifying findings': (
                'Zero qualifying findings means zero new issues',
            ),
            'explicit report-only': (
                'Explicit report-only, read-only, no-write or dry-run means no writes',
                'Return findings inline without GitHub, label, document or scratch writes',
            ),
            'authorized fix/apply': (
                'explicitly requested and authorized local fix/apply mode',
                'separate from default publication',
                'ownership, review, PR and human-only gates',
                'Default publication does not implement findings locally or activate services',
            ),
            'publication and failure receipt': (
                'preview in chat without waiting',
                'native `blockedBy` dependencies and `ai-ready` last',
                'report verified issue links and stop',
                'Preserve explicit no-dispatch, pauses and live ownership',
                'concrete error, missing input and safe resume action',
                'unknown coverage, not an empty backlog',
                'UNSAVED/UNKNOWN and partial receipts',
            ),
        }
        for scenario, contracts in cases.items():
            for contract in contracts:
                with self.subTest(scenario=scenario, contract=contract):
                    self.assertIn(contract, text)
        self.assertNotIn('Report only: no fixes, new backlog', text)

    def test_portable_audit_reaches_canonical_publication_and_mode_routing(self):
        adapter = ROOT / 'adapters/skills/ponytail-audit/SKILL.md'
        text = adapter.read_text()
        links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', text)
        self.assertIn(ROOT / 'skills/ponytail-audit/SKILL.md',
                      {(adapter.parent / link).resolve() for link in links})
        self.assertIn('default publication and explicit mode routing', text)
        self.assertIn('disable-model-invocation: true', text)
        self.assertIn('read-only/no-write/no-push restrictions', text)
        shared = ' '.join(METHOD.read_text().split())
        self.assertNotIn('Standalone review/audit/debt commands report only', shared)
        self.assertIn('../ponytail-audit/SKILL.md', shared)

    def test_map_limits_file_reads_not_only_the_parsed_string(self):
        script = PACK / 'upstream/scripts/ponytail-map.cjs'
        self.assertTrue(script.is_file())
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            large = project / 'bundle.js'
            with large.open('wb') as output:
                output.write(b'export function reusable() {}\n')
                output.truncate(10 * 1024 * 1024)
            probe = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {buildMap} = require(process.argv[1]);
const originalRead = fs.readFileSync;
fs.readFileSync = function(file, ...args) {
  assert.notEqual(String(file), process.argv[2] + '/bundle.js', 'whole-file read');
  return originalRead.call(this, file, ...args);
};
const originalBoundedRead = fs.readSync;
let read = 0;
fs.readSync = function(fd, buffer, offset, length, position) {
  assert.ok(length <= 65536, 'bounded allocation/read');
  const count = originalBoundedRead.call(this, fd, buffer, offset, length, position);
  read += count;
  return count;
};
assert.match(buildMap(process.argv[2]), /reusable/);
assert.ok(read > 0 && read <= 65536, 'must read at most 64 KiB');
'''
            result = subprocess.run(['node', '-e', probe, str(script), str(project)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
