"""Attempt provenance: immutable, allowlisted evidence that never authorizes."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import provenance


def repository(folder):
    repo = Path(folder)
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    return repo


def commit(repo, path, text):
    (repo / path).write_text(text)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.email=t@example.invalid',
                    '-c', 'user.name=T', 'add', '-A'], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.email=t@example.invalid',
                    '-c', 'user.name=T', 'commit', '-qm', 'fixture'], check=True)
    return subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()


class ManifestTests(unittest.TestCase):
    def test_records_identity_and_hashes_never_prompt_text_or_instruction_text(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = repository(folder)
            rev = commit(repo, 'AGENTS.md', 'repository instructions\n')
            record = provenance.manifest(
                task='T-1', attempt=2, attempt_id='a2', contract_hash='c' * 8, record_revision='r' * 8,
                rev=rev, host='pi', model='provider/model', toolset='abc1234',
                prompt=b'prompt body with MARKER-XYZ', instructions=provenance.instructions(repo, rev),
                ownership='worker', live='authorized', live_actor='owner', live_at='2026-11-04',
                live_scope=['live'], captured_at=100)
            self.assertEqual((record['task'], record['attempt'], record['attempt_id']), ('T-1', 2, 'a2'))
            self.assertEqual((record['host'], record['model'], record['toolset']), ('pi', 'provider/model', 'abc1234'))
            self.assertEqual(record['captured_at'], 100)
            self.assertEqual(record['prompt'], dict(sha256=provenance.digest(b'prompt body with MARKER-XYZ'),
                                                    bytes=len(b'prompt body with MARKER-XYZ')))
            self.assertEqual([(item['path'], item['state']) for item in record['instructions']],
                             [('AGENTS.md', 'present'), ('CLAUDE.md', 'unavailable')])
            self.assertEqual(record['instructions'][0]['sha256'],
                             provenance.digest(b'repository instructions\n'))
            self.assertEqual(record['authorization'], dict(
                ownership='worker', live='authorized', live_actor='owner', live_at='2026-11-04',
                live_scope=['live']))
            text = json.dumps(record)
            self.assertNotIn('MARKER-XYZ', text)
            self.assertNotIn('repository instructions', text)
            self.assertNotIn('prompt body', text)
            self.assertEqual(set(record), {'schema', 'task', 'attempt', 'attempt_id', 'captured_at',
                                           'contract_hash', 'record_revision', 'rev', 'worktree_revision',
                                           'toolset', 'host', 'model', 'prompt', 'instructions',
                                           'authorization'})

    def test_unavailable_metadata_is_null_and_never_inferred(self):
        record = provenance.manifest(task='T-1', attempt=1, contract_hash=None, record_revision=None,
                                     rev=None, host=None, model=None, toolset=None, prompt=b'p',
                                     instructions=[('AGENTS.md', None)], captured_at=1)
        self.assertEqual((record['host'], record['model'], record['toolset'], record['rev']), (None, None, None, None))
        self.assertEqual(record['instructions'], [dict(path='AGENTS.md', sha256=None, state='unavailable')])
        self.assertEqual(record['authorization'],
                         dict(ownership='worker', live='', live_actor=None, live_at=None, live_scope=[]))

    def test_a_secret_environment_value_never_reaches_the_record(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'provenance.jsonl'
            with patch.dict(os.environ, PI_AUTOWORK_TEST_SECRET='tok-9f3c'):
                provenance.capture(path, provenance.manifest(
                    task='T-1', attempt=1, contract_hash='c', record_revision='r', rev='v',
                    host='pi', model='m', toolset='t', prompt=b'p', captured_at=1))
            text = path.read_text()
            self.assertNotIn('tok-9f3c', text)
            self.assertNotIn('PI_AUTOWORK_TEST_SECRET', text)


class WorktreeInstructionTests(unittest.TestCase):
    def test_instructions_come_from_the_worktree_the_worker_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'AGENTS.md').write_text('worktree instructions\n')
            values = provenance.instructions_from(root)
            self.assertEqual([(path, state) for path, (_, state) in
                              zip(('AGENTS.md', 'CLAUDE.md'), [(d, d is not None) for _, d in values])],
                             [('AGENTS.md', True), ('CLAUDE.md', False)])
            self.assertEqual(values[0][1], b'worktree instructions\n')
            self.assertIsNone(values[1][1])


class CaptureTests(unittest.TestCase):
    def record(self, **changes):
        base = dict(task='T-1', attempt=1, contract_hash='c', record_revision='r', rev='v', host='pi',
                    model='m', toolset='t', prompt=b'p', captured_at=1)
        base.update(changes)
        return provenance.manifest(**base)

    def test_appends_keep_every_earlier_byte_and_read_in_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'provenance.jsonl'
            provenance.capture(path, self.record(prompt=b'first'))
            before = path.read_bytes()
            provenance.capture(path, self.record(prompt=b'second'))
            self.assertTrue(path.read_bytes().startswith(before))
            records = provenance.read(path)
            self.assertEqual([item['prompt']['sha256'] for item in records],
                             [provenance.digest(b'first'), provenance.digest(b'second')])

    def test_a_missing_file_is_empty_and_a_torn_final_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'provenance.jsonl'
            self.assertEqual(provenance.read(path), [])
            path.write_bytes((json.dumps(self.record()) + '\n').encode() + b'{"schema": 1, "task": "T')
            records = provenance.read(path)
            self.assertEqual([item['task'] for item in records], ['T-1'])
            provenance.capture(path, self.record(attempt=2))
            self.assertEqual([item['attempt'] for item in provenance.read(path)], [1, 2])

    def test_an_unknown_schema_is_ignored_by_older_readers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'provenance.jsonl'
            path.write_text(json.dumps(dict(schema=2, task='T-1')) + '\n')
            self.assertEqual(provenance.read(path), [])


class EvidenceOnlyTests(unittest.TestCase):
    def test_only_the_dispatch_writer_imports_or_reads_provenance(self):
        engine = Path(__file__).resolve().parents[3] / 'pi-autowork/pi_autowork/engine'
        allowed = {'parallel_dispatch.py', 'provenance.py'}
        package = engine.parents[1]
        for path in sorted([*engine.rglob('*.py'), *package.rglob('*.py')]):
            if '__pycache__' in path.parts or path.name.startswith('test_') or path.name in allowed:
                continue
            text = path.read_text()
            self.assertIsNone(re.search(r'\b(?:import|from)\s+[^\n]*\bprovenance\b', text), path.name)
            for read in ('provenance.read', 'provenance.capture', 'provenance.jsonl'):
                self.assertNotIn(read, text, path.name)
        self.assertIn('from pi_autowork.engine import provenance',
                      (engine / 'parallel_dispatch.py').read_text())


if __name__ == '__main__':
    unittest.main()
