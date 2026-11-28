"""Static recovery boundaries, not proof of model recovery or service health."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UnblockSkillTests(unittest.TestCase):
    def test_recovery_targets_github_without_reviving_executor(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for contract in ('current repository', 'GitHub Issues', 'actual ownership',
                         'does not invoke recovery', 'Standing policy:',
                         'Observe the expected transition', 'do not claim success',
                         'do not loop unchanged retries', 'Do not create backlog work',
                         'This invocation does not authorize enabling Orbi'):
            self.assertIn(contract, text)

    def test_waits_are_not_successful_recovery(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for contract in ('**Recovered** only', '**Idle** only', '**Blocked**',
                         'No work resumed.', 'smallest concrete question',
                         'unfinished recovery', 'then inspect consumption'):
            self.assertIn(contract, text)
        self.assertIn('A planning closure or an evidenced wait is not recovery', text)

    def test_changed_requirements_handback_contract(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        phase = ' '.join(text.split('## Changed requirements:', 1)[1]
                         .split('## Recover, verify, continue', 1)[0].split())
        for contract in ('retained commit SHA, the missing behavior, and the test',
                         'existing delivery owner on the same issue or linked PR',
                         'required for delivery, not for handoff',
                         'follow the documented answer', 'when binding decisions conflict',
                         'Reuse an unchanged handoff without reposting',
                         'hold only the affected work', 'leave dispatch alone',
                         'report **Handed back**', 'only after observed pickup or continued work'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_promotes_both_eligible_issue_states(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        for contract in ('`ai-planning` → `ai-ready`', '`ai-blocked` → `ai-ready`',
                         'If both labels apply, require both conditions',
                         'explicit no-dispatch request holds publication',
                         'Confirm readiness before\n  removing resolved state labels'):
            self.assertIn(contract, text)

    def stale_state_phase(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        repair = text.split('3. **Repair.**', 1)[1].split('4. **Verify.**', 1)[0]
        self.assertIn('(#stale-issue-state)', repair)
        return text.split('## Stale issue state', 1)[1].split('## Changed requirements:', 1)[0]

    def test_closed_cleanup_reads_back_state_and_limits_label_removal(self):
        phase = self.stale_state_phase().split('### Base-red blocks', 1)[0]
        phase = ' '.join(phase.split())
        self.assertIn('`closed_issues` from the fleet inventory or repeat the single-repo inventory with `state=closed`',
                      phase)
        self.assertRegex(phase, r'Re-read .* `CLOSED`.* Remove only .*'
                         r'`ai-blocked`, `ai-fix-needed`, `ai-in-progress` and `ai-pr-opened`')
        self.assertIn('Keep `ai-merged` and unrelated labels', phase)
        self.assertIn('Read back `CLOSED` and the remaining labels; confirm the four stale labels are absent', phase)

    def test_base_red_requeue_requires_verified_base_pass_and_pr_update(self):
        phase = self.stale_state_phase().split('### Base-red blocks', 1)[1]
        rules, example = ' '.join(phase.split()).split('**Worked example:**', 1)
        for contract in ('latest trusted failure', '`orbi:base-ci-red:v1`', '`origin/<base>`',
                         'Rerun the named checks with a timeout', 'on the new base SHA',
                         'leave the PR and labels unchanged', 'exact tested base SHA',
                         'normal merge', 'Never force-push', 'Read back the remote PR head',
                         'evidence comment', 'verified base and PR head still match',
                         'Replace `ai-blocked` with `ai-fix-needed` only if the issue is still open',
                         'Read back the open state and both labels'):
            with self.subTest(contract=contract):
                self.assertIn(contract, rules)
        self.assertLess(rules.index('Rerun'), rules.index('normal merge'))
        self.assertLess(rules.index('Read back the remote PR head'),
                        rules.index('Replace `ai-blocked` with `ai-fix-needed`'))
        self.assertIn('readback shows `ai-fix-needed` instead of `ai-blocked`', example)
        self.assertIn('If the check had exited 1, report its failing output and leave the PR and issue labels untouched',
                      example)

    def test_base_red_blocks_do_not_fall_through_to_other_requeues(self):
        text = ' '.join((ROOT / 'skills/unblock/SKILL.md').read_text().split())
        self.assertIn('With `owner-task` issues set aside, route base-red blocks only to '
                      '[base-red recovery](#base-red-blocks), even when `ai-planning` also applies', text)
        self.assertIn('A held or failed base-red recheck does not fall through to '
                      '`ai-ready` or another repair record for the same blocker', text)

    def test_owner_tasks_are_inventory_only_including_during_followups(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        inventory = ' '.join(text.split('**Bind and inventory.**', 1)[1].split('**Diagnose.**', 1)[0].split())
        self.assertRegex(inventory, r'timeout [1-9]\d* gh api --paginate')
        self.assertIn("repository's `owner_tasks` for the receipt", inventory)
        self.assertIn('Set aside `owner-task` issues before reading bodies', inventory)
        self.assertIn('Apply this exclusion in PR and dependency follow-ups', inventory)
        receipt = text.split('**Receipt:**', 1)[1]
        self.assertIn('`Owner tasks: N` separately', receipt)
        self.assertIn('oldest issue link and creation date', receipt)
        self.assertIn('coverage unavailable rather than a zero count', receipt)

    def test_service_boundary_preserves_pauses_jobs_and_evidence(self):
        text = (ROOT / 'skills/unblock/references/services.md').read_text()
        for contract in ('deliberate-stop', 'pending service jobs',
                         'Observe an existing restart', 'explicit user authorization',
                         'actual executable release', 'attempts/recovery state',
                         'An Unblock invocation does not enable a deployment'):
            self.assertIn(contract, text)
        self.assertIn('No Pi extension', (ROOT / 'adapters/skills/unblock/SKILL.md').read_text())

    def pr_phase(self):
        text = (ROOT / 'skills/unblock/SKILL.md').read_text()
        self.assertIn('## Blocked PRs: owner-first repair records', text)
        return ' '.join(text.split('## Blocked PRs: owner-first repair records', 1)[1]
                        .split('## Common Rationalizations', 1)[0].split())

    def test_pr_inventory_includes_unlinked_prs_and_head_bound_evidence(self):
        phase = self.pr_phase()
        for contract in ('every scoped open PR, including PRs with no linked issue',
                         'head SHA, base ref/SHA', 'review decision',
                         'required checks', 'mergeability', 'live owner',
                         'check/run URLs', 'observation time', 'Unknown',
                         'exact read error', 'no speculative writes'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_pending_superseded_and_missing_checks_are_not_guessed_failures(self):
        phase = self.pr_phase()
        for contract in ('failed checks', 'missing required checks',
                         'changes requested', 'conflicts/stale heads',
                         'native dependencies', 'external service/transport',
                         'Pending is a wait, not failure', 'superseded heads',
                         'expected trigger', 'do not assume a code repair'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_exact_active_owner_gets_evidence_once_not_a_second_writer(self):
        phase = self.pr_phase()
        for contract in ('existing issue owns the exact PR repair',
                         'new evidence as a comment', 'live worker',
                         'keep its owner and PR branch',
                         'never edit the live worker\'s instructions',
                         'no second tracking issue or worker',
                         'PR/blocker/head and evidence URLs/conclusions',
                         'unchanged evidence is a no-op, including comments'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_unowned_failure_and_independent_prerequisite_use_existing_publication(self):
        phase = self.pr_phase()
        for contract in ('uncovered actionable repair', 'one linked repair issue',
                         'Outcome, Scope, Exclusions, Acceptance, Verification and Sources',
                         'first executable action', 'owner/branch handoff',
                         'existing PR delivery line', 'independent prerequisite',
                         'reuse a shared prerequisite', 'native blockedBy',
                         'ai-planning', 'ai-ready last', 'PLAN-HANDOFF.md'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_repeated_scans_recheck_and_reconcile_before_writes(self):
        phase = self.pr_phase()
        for contract in ('open and closed issues', 'stable PR/blocker key',
                         'head SHA belongs in evidence, not the issue identity',
                         'Immediately before each write', 'comments',
                         'refresh PR head/base', 'ownership', 'Serialize publishers of the same PR/blocker',
                         'ambiguous', 'timed-out write', 'read back before retrying'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_human_paused_and_unknown_gates_are_held_with_next_input(self):
        phase = self.pr_phase()
        for contract in ('human gate', 'explicit pause', 'Held',
                         'named next input', 'resume condition',
                         'do not fabricate approval', 'meaningless executable work'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)

    def test_publication_is_not_recovery_and_receipt_accounts_for_each_pr(self):
        phase = self.pr_phase()
        for contract in ('read back issue content, PR links, native edges and readiness',
                         'subsequent PR/check/run movement separately',
                         'issue creation is not recovery', 'one disposition per PR',
                         'repair issue or owner', 'head-bound evidence', 'next input'):
            with self.subTest(contract=contract):
                self.assertIn(contract, phase)
        workflow = (ROOT / 'docs/workflows.md').read_text()
        self.assertIn('../skills/unblock/SKILL.md#blocked-prs-owner-first-repair-records', workflow)

    def test_workflow_reference_links_exist(self):
        for name in ('skills/unblock/SKILL.md', 'skills/unblock/references/services.md',
                     'adapters/skills/unblock/SKILL.md'):
            source = ROOT / name
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', source.read_text()):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((source.parent / link.split('#')[0]).is_file(), (name, link))


if __name__ == '__main__':
    unittest.main()
