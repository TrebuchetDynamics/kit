"""Offline Ponytail provenance, universal routing and installed resource checks."""
import hashlib
import importlib.util
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

    def test_hermes_setup_no_longer_requires_an_external_ponytail_plugin(self):
        manifest = yaml.safe_load((ROOT / 'plugin.yaml').read_text())
        defaults = json.loads((ROOT / 'plugins/defaults.json').read_text())
        self.assertNotIn('ponytail', manifest['requires_plugins'])
        self.assertNotIn('ponytail', defaults['imported_plugins'])
        self.assertNotIn('dietrichgebert/ponytail', (ROOT / 'plugins/PLUGINS.md').read_text().lower())

    def test_existing_profile_gets_missing_shared_resources_without_overwriting_edits(self):
        spec = importlib.util.spec_from_file_location('ponytail_upgrade', ROOT / 'scripts/install_skills.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            shared = home / 'skills/shared'
            shared.mkdir(parents=True)
            for name in ('COMMON-CONTRACT.md', 'PLAN-HANDOFF.md', 'WORKTREE-ISOLATION.md'):
                (shared / name).write_text('existing local edit\n')
            selected = [ROOT / 'skills/shared', PACK]
            for preview in (True, False, False):
                self.assertEqual(installer.install(ROOT / 'skills', [('fixture', home)],
                                                  skills=selected, dry_run=preview, report=lambda _: None), 0)
                self.assertEqual((shared / 'COMMON-CONTRACT.md').read_text(), 'existing local edit\n')
                for source in (METHOD, COMMUNICATION):
                    if preview:
                        self.assertFalse((shared / source.name).exists())
                    else:
                        self.assertTrue((shared / source.name).is_file(), 'missing shared support after upgrade')
                        self.assertEqual((shared / source.name).read_bytes(), source.read_bytes())
            # An existing shared directory alias is not a destination we own.
            other = home / 'linked/skills'
            other.mkdir(parents=True)
            (other / 'shared').symlink_to(shared, target_is_directory=True)
            self.assertEqual(installer.install(ROOT / 'skills', [('linked', home / 'linked')],
                                              skills=[ROOT / 'skills/shared'], report=lambda _: None), 1)

    def test_native_writing_guidance_works_with_only_the_skills_bundle(self):
        spec = importlib.util.spec_from_file_location('writing_install', ROOT / 'scripts/install_skills.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            selected = [ROOT / 'skills' / name for name in ('writing-for-agents', 'shared')]
            self.assertEqual(installer.install(ROOT / 'skills', [('fixture', home)],
                                              skills=selected, report=lambda _: None), 0)
            self.assertFalse((home / 'docs').exists())
            entry = home / 'skills/writing-for-agents/SKILL.md'
            text = entry.read_text()
            self.assertEqual(text, (ROOT / 'skills/writing-for-agents/SKILL.md').read_text())
            # The essential policy is inline, not dependent on an absent checkout doc.
            for rule in ('explicit host command', 'disable-model-invocation: true',
                         'allow_implicit_invocation: false', 'write nothing'):
                self.assertIn(rule, text)
            for link in ('upstream/PROTOCOL.md', 'upstream/SKILL-MECHANICS.md',
                         '../shared/COMMUNICATION.md', '../shared/PONYTAIL.md'):
                self.assertIn('](' + link + ')', text)
                self.assertTrue((entry.parent / link).is_file())

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

    def test_native_install_carries_the_method_protocols_and_executable_map(self):
        spec = importlib.util.spec_from_file_location('ponytail_install', ROOT / 'scripts/install_skills.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            selected = [ROOT / 'skills' / name for name in sorted(NAMES | {'shared'})]
            self.assertTrue(all(path.is_dir() for path in selected), 'bundled suite is missing')
            self.assertEqual(installer.install(ROOT / 'skills', [('fixture', home)],
                                              skills=selected, report=lambda _: None), 0)
            self.assertEqual((home / 'skills/shared/PONYTAIL.md').read_bytes(), METHOD.read_bytes())
            project = home / 'project with spaces'
            project.mkdir()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            (project / 'lib.py').write_text('def reuse_this():\n    return 1\n')
            (project / '.gitignore').write_text('ignored.py\n')
            (project / 'ignored.py').write_text('def do_not_read():\n    pass\n')
            subprocess.run(['git', '-C', str(project), 'add', 'lib.py', '.gitignore'], check=True)
            script = home / 'skills/ponytail/upstream/scripts/ponytail-map.cjs'
            result = subprocess.run(['node', str(script), str(project)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('reuse_this', result.stdout)
            self.assertNotIn('do_not_read', result.stdout)
            self.assertEqual(sorted(p.name for p in project.iterdir()),
                             ['.git', '.gitignore', 'ignored.py', 'lib.py'])


if __name__ == '__main__':
    unittest.main()
