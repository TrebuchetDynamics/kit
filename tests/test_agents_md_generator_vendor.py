"""Pinned upstream integrity and offline instruction-workflow contracts, not model proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'skills/agents-md-generator'
REVISION = 'ac929caec7e5313e5a53033db68673c47a84c42c'
# Independently read from the source git tree at REVISION, not from local UPSTREAM.json.
EXPECTED = {
  "LICENSE": [
    "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
    "100644"
  ],
  "skills/agents-md-generator/SKILL.md": [
    "8f6af61893859daae134e4e55514589aa36a3a9eacb4c7f5351366cadb8bc85a",
    "100644"
  ],
  "skills/agents-md-generator/agents/openai.yaml": [
    "4de84ed69ca4c2ee2899b0984ce483f033c61c7264d6964ed6a9fdfa9539a0c7",
    "100644"
  ],
  "skills/agents-md-generator/references/discovery.md": [
    "10dddfb039655955d6e97b069c9335fba89541f5428b0d96e4b083e8a5d21c39",
    "100644"
  ],
  "skills/agents-md-generator/references/merge-and-verify.md": [
    "03adf690837780aec33baff76438e0507f4a5c942b59c443c4af69e6240e0a6c",
    "100644"
  ],
  "skills/agents-md-generator/references/output-template.md": [
    "dbae8c9055afb09c34f0ba778efa16c20ed97e31966ff547ebfe325f5436893c",
    "100644"
  ],
  "skills/agents-md-generator/references/tool-compatibility.md": [
    "bdd27ffd81e7a7634300f8db8d3b0df613c53d2192555c13a06d4a5773e5b68b",
    "100644"
  ],
  "skills/agents-md-generator/scripts/detect-agent-context": [
    "cd4c330743a0d3af9545f4bb37170564589c12513ae218ed424352c7179653cd",
    "100755"
  ],
  "skills/agents-md-generator/scripts/detect-agent-context.cmd": [
    "351ebce50d2a0d03d5be49938f59753552579cc44e60d0cd2d4a55e7365ad33c",
    "100644"
  ],
  "skills/agents-md-generator/scripts/detect-agent-context.ps1": [
    "07ba94190ecb45d31e59302ba0c297168167362659ac8f41826b99ba14622768",
    "100644"
  ],
  "skills/agents-md-generator/scripts/detect-agent-context.py": [
    "0a612230e0aad322831b3d2825515eb1022122149d2677502ee4ddea9fff384d",
    "100755"
  ],
  "skills/agents-md-generator/scripts/detect-agent-context.sh": [
    "f7b9948f36bd14d31dfba1138ae24815eb8675f6da58a25f26f03b4723b9c5bc",
    "100755"
  ]
}


def snapshot(root):
    return {str(p.relative_to(root)): (stat.S_IMODE(p.lstat().st_mode),
            ('link', os.readlink(p)) if p.is_symlink() else
            ('directory',) if p.is_dir() else ('file', p.read_bytes()))
            for p in root.rglob('*')}


class AgentsMdGeneratorTests(unittest.TestCase):
    def test_complete_pin_inventory_bytes_modes_and_no_nested_public_entry(self):
        pin = json.loads((PACK / 'UPSTREAM.json').read_text())
        self.assertEqual(pin['repository'], 'https://github.com/thienanblog/awesome-ai-agent-skills')
        self.assertEqual(pin['revision'], REVISION)
        self.assertEqual(pin['license'], 'Apache-2.0')
        self.assertEqual(set(pin['files']), set(EXPECTED))
        paths = set()
        for source, (digest, mode) in EXPECTED.items():
            with self.subTest(source=source):
                relative = source.removeprefix('skills/agents-md-generator/')
                relative = 'PROTOCOL.md' if relative == 'SKILL.md' else relative
                target = 'upstream/' + relative
                item = pin['files'][source]
                self.assertEqual(item['path'], target)
                self.assertEqual(item['sha256'], digest)
                self.assertEqual(item['mode'], mode)
                path = PACK / target
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
                self.assertEqual(bool(path.stat().st_mode & 0o111), mode == '100755')
                paths.add(target)
        self.assertEqual({p.relative_to(PACK).as_posix() for p in (PACK / 'upstream').rglob('*')
                          if p.is_file()}, paths)
        self.assertEqual(list(PACK.rglob('SKILL.md')), [PACK / 'SKILL.md'])
        self.assertIn('Apache License', (PACK / 'upstream/LICENSE').read_text())
        self.assertIn('inert', ' '.join(pin['adaptations']).lower())

    def test_installed_detector_reads_external_target_without_writes_and_fails_usefully(self):
        with tempfile.TemporaryDirectory(prefix='agent instructions ') as temporary:
            base = Path(temporary)
            installed, target = base / 'installed skill', base / 'target repo'
            shutil.copytree(PACK, installed)
            (target / 'src').mkdir(parents=True)
            (target / 'AGENTS.md').write_text('Use npm run old. Preserve human release approval.\n')
            (target / 'CLAUDE.md').write_text('Read AGENTS.md. Use EnterWorktree. Use npm run old.\n')
            (target / 'src/AGENTS.md').write_text('Only edit schema source, not generated output.\n')
            (target / 'src/AGENTS.override.md').write_text('Scoped override: check schema.\n')
            (target / 'GEMINI.md').symlink_to('AGENTS.md')
            (target / 'untracked notes.txt').write_text('unrelated work\n')
            (base / 'AGENTS.md').write_text('Ancestor policy outside target edit authority.\n')
            (target / 'package.json').write_text(json.dumps({'packageManager': 'npm@10.0.0',
                                                          'scripts': {'check': 'node check.js'}}))
            helper = installed / 'upstream/scripts/detect-agent-context'
            before = snapshot(base)
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            usage = subprocess.run([str(helper), '--help'], cwd=installed, env=env,
                                   capture_output=True, text=True, timeout=15)
            self.assertEqual(usage.returncode, 0, usage.stderr)
            self.assertIn('--root', usage.stdout)
            result = subprocess.run([str(helper), '--root', str(target), '--format', 'json'],
                                    cwd=installed, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['root'], str(target))
            self.assertEqual({p['path'] for p in report['instruction_sources']},
                             {'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'src/AGENTS.md',
                              'src/AGENTS.override.md'})
            self.assertIn('src/AGENTS.override.md shadows src/AGENTS.md', '\n'.join(report['warnings']))
            self.assertEqual(report['declared_commands'], [{'command': 'npm run check',
                             'name': 'check', 'runner': 'npm', 'source': 'package.json'}])
            # Detector indexes paths, not ancestor contents or symlink ownership.
            # Canonical workflow requires native reads for those missing facts.
            missing = target / 'missing'
            failure = subprocess.run([sys.executable, '-B', str(helper) + '.py', '--root', str(missing)],
                                     cwd=installed, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(failure.returncode, 2)
            self.assertIn('error: root directory does not exist: ' + str(missing), failure.stderr)
            self.assertEqual(snapshot(base), before, 'audit helper changed bytes, modes, links or untracked paths')

    def test_bare_audit_and_update_have_distinct_effect_contracts(self):
        # These assert the authored protocol. No deterministic rewriter or fake model.
        text = ' '.join((PACK / 'SKILL.md').read_text().split())
        bare = text.split('**Bare invocation**', 1)[1].split('**Audit**', 1)[0]
        for rule in ('both target-root `AGENTS.md` and `CLAUDE.md`', 'end to end',
                     'without a mode', 'diff approval', 'Create missing root instructions',
                     'meaning of valid requirements', 'working symlinks'):
            self.assertIn(rule, bare)
        audit = text.split('**Audit**', 1)[1].split('**Update**', 1)[0]
        for rule in ('strictly read-only', 'inline', 'scratch', 'reports', 'issue writes', 'cache-writing tests'):
            self.assertIn(rule, audit)
        update = text.split('**Update**', 1)[1].split('2. **Discover**', 1)[0]
        self.assertIn('no second confirmation', update)
        self.assertIn('requested scope', update)
        for rule in ('explicit read-only restriction always wins', '--root',
                     'ancestor', 'nested', 'AGENTS.override.md', 'symlink ownership',
                     'native reads', 'command definitions', 'generated artifacts',
                     'keep/update/move/remove/unresolved', 'maintainer decisions',
                     'exact question', 'independent scoped work', 'no fixed length quota',
                     '../writing-for-agents/SKILL.md', 'inspected, run and unrun'):
            self.assertIn(rule, text)

    def test_maintenance_is_conditional_plain_committed_guidance(self):
        reference = ROOT / 'skills/shared/AGENT-INSTRUCTIONS.md'
        agents = (ROOT / 'AGENTS.md').read_text()
        self.assertIn('](skills/shared/AGENT-INSTRUCTIONS.md)', agents)
        text = ' '.join(reference.read_text().split())
        for rule in ('same PR', 'No affected guidance', 'no edit', 'verified lessons',
                     'precise blocking question', 'explicit generator scope',
                     'committed Markdown', 'review gates'):
            self.assertIn(rule, text)
        self.assertFalse((reference.parent / 'SKILL.md').exists())
        self.assertIn('[AGENTS.md](AGENTS.md)', (ROOT / 'CLAUDE.md').read_text())
        for path in ('AGENTS.md', 'CLAUDE.md'):
            import re
            source = ROOT / path
            for link in re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)', source.read_text()):
                self.assertTrue((source.parent / link).exists(), (path, link))


if __name__ == '__main__':
    unittest.main()
