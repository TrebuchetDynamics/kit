"""Offline smoke-runner checks; fake Pi never calls a model or external service."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from planning_smoke import main  # noqa: E402

FAKE_PI = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
args = sys.argv[1:]
agent = pathlib.Path(os.environ['PI_CODING_AGENT_DIR'])
assert json.loads((agent / 'settings.json').read_text()) == {}
assert (agent / 'auth.json').is_symlink()
for flag in ('--no-session', '--no-extensions', '--no-mcp', '--no-skills', '--no-context-files'):
    assert flag in args
assert args[args.index('--tools') + 1] == 'read,bash,edit,write'
assert args[-1].startswith('/skill:')
case = os.environ.get('SMOKE_FAKE_CASE', 'pass')
if case == 'timeout':
    time.sleep(10)
if case == 'descendant':
    subprocess.Popen([sys.executable, '-c',
                      "import time,pathlib; time.sleep(0.5); pathlib.Path('late-write').write_text('escaped')"])
    time.sleep(10)
if case == 'empty':
    print(json.dumps({'type': 'session'})); sys.exit(0)
kit = pathlib.Path(args[args.index('--skill') + 1]).parents[2]
skill = pathlib.Path(args[args.index('--skill') + 1]).name
for n, path in enumerate(('README.md', str(kit / 'skills' / skill / 'SKILL.md'))):
    print(json.dumps({'type': 'tool_execution_start', 'toolCallId': str(n),
                     'toolName': 'read', 'args': {'path': path}}))
    print(json.dumps({'type': 'tool_execution_end', 'toolCallId': str(n),
                     'isError': case == 'read-error'}))
if case == 'mutation':
    pathlib.Path('README.md').write_text('changed')
if case == 'attempt':
    print(json.dumps({'type': 'tool_execution_start', 'toolCallId': 'w',
                     'toolName': 'write', 'args': {'path': 'docs/plan.md'}}))
print(json.dumps({'type': 'message_end', 'message': {'role': 'assistant',
                  'stopReason': 'error' if case == 'error' else 'stop',
                  'content': [{'type': 'text', 'text': 'How should whitespace be handled?'}]}}))
sys.exit(1 if case == 'exit' else 0)
'''


class PlanningSmokeTests(unittest.TestCase):
    def test_help_shows_pi_bolt_as_default(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as error:
            main(['--help'])
        self.assertEqual(error.exception.code, 0)
        self.assertIn('default: pi-bolt', output.getvalue())

    def test_fake_runs_preserve_profiles_and_refuse_false_success(self):
        for case, failure in (('pass', None), ('empty', 'no completed assistant response'),
                              ('mutation', 'fixture files changed'), ('attempt', 'attempted a write/edit'),
                              ('read-error', 'missing successful read'), ('error', 'did not finish normally'),
                              ('exit', 'Pi exited with 1'), ('timeout', 'TimeoutExpired'),
                              ('descendant', 'TimeoutExpired')):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                auth = root / 'existing-agent'; auth.mkdir()
                (auth / 'auth.json').write_text('{"fixture": "not a credential"}')
                (auth / 'settings.json').write_text('{"preserve": true}')
                fake = root / 'pi'; fake.write_text(FAKE_PI)
                fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
                output = root / 'evidence'
                with patch.dict(os.environ, {'SMOKE_FAKE_CASE': case}), contextlib.redirect_stdout(io.StringIO()):
                    result = main(['--provider', 'fixture', '--model', 'fixture', '--pi', str(fake),
                                   '--agent-dir', str(auth), '--output-dir', str(output),
                                   '--timeout', '0.15' if case in ('timeout', 'descendant') else '10'])
                receipt = json.loads((output / 'receipt.json').read_text())
                self.assertEqual(result, 0 if failure is None else 1, receipt)
                self.assertEqual(receipt['ok'], failure is None)
                if failure:
                    self.assertTrue(any(failure in f for f in receipt['failures']), receipt)
                self.assertEqual((auth / 'settings.json').read_text(), '{"preserve": true}')
                self.assertEqual((auth / 'auth.json').read_text(), '{"fixture": "not a credential"}')
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertTrue((output / 'session.jsonl').exists())
                if case == 'descendant':
                    time.sleep(0.6)
                    self.assertFalse((output / 'project/late-write').exists(),
                                     'timed-out descendants must not mutate the fixture later')

    def test_existing_evidence_and_source_paths_are_refused_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory)
            sentinel = existing / 'receipt.json'; sentinel.write_text('retain original evidence')
            for output in (existing, ROOT / 'must-not-be-created', existing / 'agent/new'):
                with self.subTest(output=output), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        main(['--provider', 'fixture', '--model', 'fixture',
                              '--agent-dir', str(existing / 'agent'), '--output-dir', str(output)])
                    self.assertEqual(error.exception.code, 2)
            self.assertEqual(sentinel.read_text(), 'retain original evidence')
            self.assertFalse((ROOT / 'must-not-be-created').exists())
            self.assertFalse((existing / 'agent').exists())


if __name__ == '__main__':
    unittest.main()
