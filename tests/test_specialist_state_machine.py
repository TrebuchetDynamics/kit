"""Offline public-entry contracts, not live model or GitHub publication proof."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/state-machine/SKILL.md'
ADAPTER = ROOT / 'adapters/skills/state-machine/SKILL.md'


def normalized(path):
    return ' '.join(path.read_text().split())


class StateMachineSpecialistTests(unittest.TestCase):
    def handoff(self):
        # Follow the actual entrypoint's policy link, not an assumed default.
        match = re.search(r'\[single-invocation specialist handoff\]\(([^)]+)\)',
                          SKILL.read_text())
        self.assertIsNotNone(match, 'State Machine must opt into the shared default')
        path, anchor = match.group(1).split('#')
        target = (SKILL.parent / path).resolve()
        self.assertEqual(target, ROOT / 'skills/shared/PLAN-HANDOFF.md')
        self.assertEqual(anchor, 'single-invocation-specialist-handoff')
        return normalized(target)

    def test_bare_invocation_analyzes_and_publishes_without_follow_up(self):
        skill = normalized(SKILL)
        self.assertIn('With no area supplied, inspect the current repository', skill)
        handoff = self.handoff()
        for rule in ('without a publication directive', 'same invocation',
                     'all supported, buildable, uncovered outcomes',
                     'preview in chat without waiting',
                     'finding numbers, approval, a second command or a planner invocation',
                     'report verified issue links and stop'):
            with self.subTest(rule=rule):
                self.assertIn(rule, handoff)
        self.assertNotIn('Default to a read-only analysis', skill)
        self.assertNotIn('invoke `/bug-harvest` immediately after', skill)

    def test_findings_require_a_supported_transition_and_regression_sequence(self):
        skill = normalized(SKILL)
        self.assertIn('[state-machine analysis](PROTOCOL.md)', skill)
        for field in ('trigger', 'initial and resulting state', 'violated invariant',
                      'source location', 'regression sequence'):
            with self.subTest(field=field):
                self.assertIn(field, skill)
        for rule in ('Hold undecided product rules', 'do not invent expected behavior',
                     'source-supported unexecuted counterexamples', 'hypotheses'):
            self.assertIn(rule, skill)
        protocol = normalized(ROOT / 'skills/state-machine/PROTOCOL.md')
        for rule in ('accepted requirements', 'shortest known reachable event sequence',
                     'Concurrency needs a controlled schedule', 'independent expected result'):
            self.assertIn(rule, protocol)

    def test_mixed_findings_reconcile_and_continue_without_duplicates(self):
        handoff = self.handoff()
        for rule in ('open and closed issues, linked PRs and ownership',
                     'covered, completed, owned and unsupported findings create no duplicate issue',
                     'Group findings that share a fix and acceptance check',
                     'Hold only uncertain findings with the reason and resume condition',
                     'continue independent qualifying work', 'native `blockedBy`',
                     '`ai-ready` as the **final publication phase**',
                     'no-dispatch', 'human-only', 'live ownership',
                     'neither local implementation nor service activation'):
            with self.subTest(rule=rule):
                self.assertIn(rule, handoff)

    def test_zero_qualifying_findings_means_zero_new_issues(self):
        handoff = self.handoff()
        self.assertIn('Zero qualifying findings means zero new issues', handoff)
        self.assertIn('report covered/held dispositions or that no change is warranted', handoff)

    def test_report_only_and_dry_run_are_inline_without_any_writes(self):
        skill = normalized(SKILL)
        for rule in ('`report only`', '`read-only`', '`no-write`', '`dry-run`',
                     'inline and write nothing', 'caches or fixtures'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        self.assertIn('no GitHub, label, document or scratch writes', self.handoff())

    def test_publication_failure_uses_existing_partial_receipts(self):
        handoff = self.handoff()
        for rule in ('**UNSAVED**, with the exact failure and retry command',
                     'per-issue partial receipt', '**UNKNOWN**',
                     'Inspect ownership and reconcile the cause before retrying',
                     'Do not create a substitute executable queue'):
            with self.subTest(rule=rule):
                self.assertIn(rule, handoff)

    def test_explicit_authorized_fix_mode_is_separate(self):
        skill = normalized(SKILL)
        for rule in ('explicitly requested and authorized fix/apply mode',
                     '[`/bug-harvest`](../bug-harvest/SKILL.md#findings-from-the-preceding-response)',
                     'reuse the map and findings', 'ownership, review, PR and human-only gates',
                     'Default publication does not implement findings locally'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        bug_harvest = normalized(ROOT / 'skills/bug-harvest/SKILL.md')
        for rule in ('Recheck the findings against current source and ownership',
                     'No automatic commit or push'):
            self.assertIn(rule, bug_harvest)

    def test_portable_entry_and_public_guidance_match_the_default(self):
        adapter = normalized(ADAPTER)
        for link in ('../../../skills/state-machine/SKILL.md',
                     '../../../skills/shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff',
                     '../COMMON.md'):
            self.assertIn(link, adapter)
        self.assertIn('disable-model-invocation: true', adapter)
        self.assertIn('/skill:state-machine', adapter)
        protocol = normalized(ROOT / 'skills/state-machine/PROTOCOL.md')
        self.assertNotIn('Direct invocation uses the read-only', protocol)
        self.assertIn("Other workflows read this file as reference", protocol)
        docs = (ROOT / 'docs/workflows.md').read_text().split('## State machine', 1)[1].split('\n## ', 1)[0]
        self.assertIn('/skill:state-machine inspect checkout retries and cancellation\n', docs)
        self.assertIn('same invocation', docs)
        self.assertNotIn('The default is read-only', docs)
        catalog = (ROOT / 'README.md').read_text()
        self.assertNotIn('map implicit states and unsafe transitions, read-only', catalog)


if __name__ == '__main__':
    unittest.main()
