"""Autoresearch instruction and pinned distribution contracts."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

COMMANDS = ('plan', 'debug', 'fix', 'security', 'ship', 'probe', 'scenario',
            'predict', 'reason', 'learn', 'improve', 'evals', 'regression')


class AutoresearchInstructionContracts(unittest.TestCase):
    """Source consistency controls, not model runs or execution authorization."""

    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / 'skills/autoresearch/SKILL.md').read_text()
        cls.portable = (ROOT / 'adapters/skills/autoresearch/SKILL.md').read_text()

    def section(self, heading):
        return ' '.join(self.text.split(f'## {heading}\n', 1)[1].split('\n## ', 1)[0].split())

    def test_current_backlog_binding_preserves_legacy_provenance(self):
        binding = self.section('First: bind research to the repository')
        for rule in ('GitHub Issues own the executable backlog',
                     'open and closed GitHub Issues', 'PRs', 'accepted requirement IDs',
                     'actual ownership', 'dirty changes', 'existing research receipts',
                     'Reuse existing issues', 'read-only provenance', 'never a writable queue',
                     'without moving or deleting', 'never reinstall the removed task CLI'):
            with self.subTest(rule=rule):
                self.assertIn(rule, binding)
        # Historical tasks/ mentions are valid; the old current-authority direction is not.
        for text in (binding, self.portable):
            self.assertNotRegex(text, r"(?:checkout's|main) `tasks/` (?:store )?is canonical")
        self.assertIn('../shared/PLAN-HANDOFF.md', binding)
        self.assertIn('../../../skills/autoresearch/SKILL.md', self.portable)
        self.assertIn('../COMMON.md', self.portable)
        self.assertIn('Preserve legacy records; the task CLI is removed', self.portable)

    def test_authorized_fix_and_experiment_remain_valid_paths(self):
        execution = self.section('Execution, experiments and completion')
        boundaries = self.section('Boundaries')
        self.assertIn('Only an actually authorized `fix` or bounded experiment may change product code', execution)
        self.assertIn('Authorized `fix` and bounded experiments may implement within accepted scope', boundaries)
        self.assertNotIn('- Not implementation;', boundaries)
        for rule in ('isolated owned worktree/branch', "experiment's exact SHA",
                     'validation, ownership, PR and independent review gates remain authoritative'):
            self.assertIn(rule, execution)
        self.assertIn('do not repeat upstream\'s generic “confirm”/“run now?” questions',
                      self.section('First: bind research to the repository'))

    def test_standalone_plan_and_analysis_do_not_implement(self):
        boundaries = self.section('Boundaries')
        self.assertIn('Plan/analysis does not implement', boundaries)
        self.assertIn('../shared/RESEARCH-PLAN.md#planning-artifact-and-authority-contract', boundaries)
        self.assertIn('../shared/PLAN-HANDOFF.md', boundaries)
        self.assertIn('and stop', boundaries)
        self.assertIn('Planning does not implement', self.portable)
        analysis = self.section('Document and schedule through docs-sync')
        self.assertIn('do not silently turn recommendations into product-code changes', analysis)

    def test_fix_and_chain_inherit_refusal_limits(self):
        execution = self.section('Execution, experiments and completion')
        self.assertIn('Inherit all caller limits', execution)
        for limit in ('read-only', 'no-write', '--dry-run', 'no-implementation', 'no-commit'):
            with self.subTest(limit=limit):
                self.assertIn(limit, execution)
        self.assertIn('an explicit selector or `--chain fix` adds no authority', execution)
        analysis = self.section('Document and schedule through docs-sync')
        for rule in ('Explicit audit/read-only requests write nothing',
                     '`--dry-run` performs no mutations or dispatch',
                     'must not run a mutating Verify command',
                     '“Do not implement” remains binding despite `--chain fix`'):
            with self.subTest(rule=rule):
                self.assertIn(rule, analysis)
        self.assertIn('Honor no-commit instructions', execution)

    def test_coordinator_substep_and_ship_keep_existing_gates(self):
        self.assertIn('An Orbi-owned substep returns to the same coordinator', self.section('Boundaries'))
        self.assertIn('return to the same issue and candidate', ' '.join(self.text.split()))
        handoff = self.section('Document and schedule through docs-sync')
        self.assertIn('This handoff does not activate Orbi', handoff)
        self.assertIn('Never start a competing worker or reinstall the removed executor', handoff)
        execution = self.section('Execution, experiments and completion')
        self.assertIn('Push, deploy, publication and external messages need the actual user-authorized scope', execution)
        self.assertIn('research success or command chaining alone provides none', execution)


class AutoresearchDistribution(unittest.TestCase):
    def test_vendor_integrity_and_complete_command_set(self):
        root = ROOT / 'skills/autoresearch'
        self.assertTrue((root / 'UPSTREAM.json').is_file(), 'Missing pinned upstream')
        manifest = json.loads((root / 'UPSTREAM.json').read_text())
        self.assertEqual(set(manifest['commands']), set(COMMANDS))
        for name, digest in manifest['sha256'].items():
            self.assertEqual(hashlib.sha256((root / 'upstream' / name).read_bytes()).hexdigest(), digest, name)
        for command in ('autoresearch', *COMMANDS):
            self.assertIn(command + '.md', manifest['sha256'])

    def test_vendored_runtime_executes_without_host_plugin(self):
        script = ROOT / 'skills/autoresearch/upstream/scripts/orchestrate.sh'
        self.assertTrue(script.is_file(), 'Missing runtime')
        result = subprocess.run(['bash', str(script), 'classify', 'fix the cache bug'], text=True, capture_output=True)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'fix-broken'))


if __name__ == '__main__':
    unittest.main()
