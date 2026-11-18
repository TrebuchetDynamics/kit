"""The skill standard: description shape, boundaries and a checkable done line.

See docs/skill-standard.md. These are the mechanical rules; judgement rules (one
home, disclosure, positive wording) stay with review.
"""
import importlib.util
import re
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
BANNED_OPENERS = ('use when', 'use to', 'use for', 'use if', 'use after', 'use before')
# Hermes installs Graphify's own skill into profiles, so Autowork ships the adapter only.
ADAPTER_ONLY = {'graphify'}
PILOT = ('orbi', 'update-kit', 'unslop', 'plan-for-me', 'ponytail-review',
         'git-commit-push', 'push', 'unblock', 'docs-sync', 'plan-with-me')


class SkillStandardTests(unittest.TestCase):
    def skills(self, folder):
        return sorted((ROOT / folder).glob('*/SKILL.md'))

    def test_all_public_skills_reach_the_shared_freshness_owner(self):
        owner = ROOT / 'skills/shared/COMMON-CONTRACT.md'
        entrypoints = self.skills('skills') + self.skills('adapters/skills')
        common = {owner, ROOT / 'skills/shared/PONYTAIL.md',
                  ROOT / 'adapters/skills/COMMON.md'}
        for entry in entrypoints:
            seen, pending = set(), [entry]
            while pending:
                path = pending.pop()
                if path in seen:
                    continue
                seen.add(path)
                for link in re.findall(r'\]\(([^)\s]+)\)', path.read_text()):
                    target = (path.parent / link.split('#')[0]).resolve()
                    if target in common and target.is_file():
                        pending.append(target)
            with self.subTest(entry=str(entry.relative_to(ROOT))):
                self.assertIn(owner, seen, 'no common-entrypoint path to freshness policy')
        text = owner.read_text()
        self.assertIn('## Source freshness and delivery ownership', text)
        for mode in ('Read-only', 'Writable planning', 'Authorized implementation',
                     'Delivery/sync', 'Non-repository'):
            self.assertIn(mode, text)

    def test_delivery_references_do_not_call_fetch_read_only(self):
        for name in ('skills/git-commit-push/SKILL.md',
                     'skills/git-commit-push/references/pull-merge.md'):
            text = (ROOT / name).read_text()
            with self.subTest(path=name):
                self.assertNotRegex(text, r'(?i)read-only fetch|Fetch and report; change nothing')
        push = (ROOT / 'skills/push/SKILL.md').read_text()
        for category in ('merged upstream', 'open/owned', 'failed/blocked',
                         'closed-unmerged', 'already included/equivalent', 'unavailable/unknown'):
            self.assertIn(category, push)
        self.assertIn('pagination', push)

    def test_sync_recipes_preserve_restrictions_and_live_checkout_isolation(self):
        delivery = (ROOT / 'skills/git-commit-push/SKILL.md').read_text()
        sync = delivery.split('6. **Sync with upstream (default).**', 1)[1].split(
            '7. **Push (explicit ship target only).**', 1)[0]
        self.assertIn('no-pull/no-sync: use permitted remote metadata without fetch', sync)
        self.assertNotRegex(sync, r'Before every push[\s\S]*?fetch and confirm')
        pull = (ROOT / 'skills/git-commit-push/references/pull-merge.md').read_text()
        self.assertNotIn('No overlap → git can update', pull)
        safety = (ROOT / 'skills/git-commit-push/references/shared-worktree-safety.md').read_text()
        self.assertNotIn('Empty means merge', safety)
        self.assertIn('isolate even when incoming paths are disjoint', pull)
        self.assertIn('isolate even when incoming paths are disjoint', safety)

    def test_descriptions_are_summaries_within_the_index(self):
        for path in self.skills('skills') + self.skills('adapters/skills'):
            with self.subTest(skill=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertTrue(text.startswith('---\n'))
                description = yaml.safe_load(text.split('---', 2)[1])['description']
                self.assertIsInstance(description, str)
                self.assertLessEqual(len(description), 60, description)
                self.assertFalse(description.lower().startswith(BANNED_OPENERS), description)
                self.assertRegex(description, r'\.$')
                self.assertEqual(description.count('.'), 1, description)

    def test_relative_links_resolve_from_each_skill_file(self):
        """Check section targets too: a migration guide is not the retired CLI policy."""
        spec = importlib.util.spec_from_file_location('docs_check', ROOT / 'skills/docs-sync/scripts/docs.py')
        docs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(docs)
        repo = docs.Repo(ROOT)
        files = self.skills('skills') + self.skills('adapters/skills') + [ROOT / 'adapters/skills/COMMON.md']
        for pattern in ('shared/*.md', '*/references/*.md', 'engineering/local/*/PROTOCOL.md'):
            files.extend((ROOT / 'skills').glob(pattern))
        for source in files:
            path = source.relative_to(ROOT)
            with self.subTest(file=str(path)):
                self.assertEqual(docs.check_document(repo, 'skill', path), [])

    def test_lgtm_inherits_planning_authority_without_a_second_approval_round(self):
        skill = ' '.join((ROOT / 'skills/lgtm/SKILL.md').read_text().split())
        self.assertIn('LGTM is a yes', skill)
        self.assertIn('low-effort', skill)
        self.assertIn('originating workflow and last unambiguous user-authorized action', skill)
        for owner in ('RESEARCH-PLAN.md#planning-artifact-and-authority-contract',
                      'PLANNING-CRAFT.md#consequential-uncertainty'):
            self.assertIn(f'../shared/{owner}', skill)
        for rule in ('one clear recommendation', 'only ambiguous choices unresolved',
                     'all clear recommendations in the latest round',
                     'does not authorize implementation',
                     'already-authorized implementation, commit and push',
                     'harmless delegated engineering defaults'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        for obsolete in ('accept every recommendation', 'accept all six',
                         'LGTM accepts the first stated recommendation'):
            self.assertNotIn(obsolete, skill)

    def test_lgtm_accepts_recommended_batch_without_reopening_settled_rounds(self):
        skill = ' '.join((ROOT / 'skills/lgtm/SKILL.md').read_text().split())
        for rule in ('A numbered list is not ambiguity by itself',
                     'no second approval round',
                     'A new recommendation introduced after approval needs its own answer',
                     'accept retention and ask only about access',
                     'Explicit partial approval or corrections narrow acceptance'):
            owner = (ROOT / 'skills/shared/PLANNING-CRAFT.md').read_text()
            self.assertIn(rule, skill + ' ' + ' '.join(owner.split()))
        for threshold in ('at least $5 in settled paper profit per scheduled 24 hours',
                          'before modeled rebates', 'drawdown at most $50',
                          'fixed 72-hour test with no extension',
                          'at least 200 settled market windows with fills',
                          'at least 24 distinct UTC hours',
                          '95% interval lower bound above zero',
                          'pre-rebate profit per filled share',
                          'accept both exactly as stated',
                          'or start the bot', 'Keep Round 1 settled'):
            with self.subTest(threshold=threshold):
                self.assertIn(threshold, skill)

    def test_shared_planning_acceptance_has_no_blanket_batch_rejection(self):
        craft = ' '.join((ROOT / 'skills/shared/PLANNING-CRAFT.md').read_text().split())
        self.assertIn('LGTM accepts all clear recommendations shown in that round', craft)
        self.assertIn('Acceptance sets planning decisions, not permission to implement', craft)
        for path, obsolete in (
            ('skills/shared/PLANNING-CRAFT.md', 'not several recommendations'),
            ('skills/shared/RESEARCH-PLAN.md', 'never several separate recommendations'),
            ('skills/plan-with-me/SKILL.md', 'never several separate recommendations'),
            ('skills/plan-with-me/SKILL.md', 'Several recommendations accepted by one bare yes'),
            ('skills/plan-with-me/references/special-cases.md',
             'approval of separate task recommendations'),
            ('docs/workflows.md', 'not a batch of recommendations'),
        ):
            self.assertNotIn(obsolete, (ROOT / path).read_text())

    def test_lgtm_portable_adapter_has_no_second_approval_policy(self):
        path = ROOT / 'adapters/skills/lgtm/SKILL.md'
        text = path.read_text()
        self.assertIn('disable-model-invocation: true', text)
        self.assertIn('../../../skills/lgtm/SKILL.md', text)
        self.assertIn('../COMMON.md', text)
        # A reference-only body: no local fast path, examples or approval defaults.
        body = text.split('---', 2)[2]
        prose = [line for line in body.splitlines() if line.strip() and not line.startswith('#')]
        self.assertTrue(prose)
        for line in prose:
            self.assertRegex(line, r'\]\([^)]+\)', line)
        self.assertNotIn('accept every recommendation', text)

    def test_every_native_skill_states_boundaries_and_a_done_line(self):
        for path in self.skills('skills'):
            if path.parent.name == 'shared':
                continue
            with self.subTest(skill=path.parent.name):
                text = path.read_text()
                self.assertIn('## Boundaries', text)
                boundaries = text.split('## Boundaries', 1)[1]
                self.assertRegex(boundaries, r'(?m)^- \S', 'a boundary with no cut')
                self.assertIn('**Done when:**', text)
                self.assertEqual(text.count('**Done when:**'), 1, 'one completion line')

    def test_high_risk_skills_name_excuses_red_flags_and_dod(self):
        for name in PILOT:
            with self.subTest(skill=name):
                text = (ROOT / 'skills' / name / 'SKILL.md').read_text()
                self.assertIn('## Common Rationalizations', text)
                self.assertIn('| Rationalization | Reality |', text)
                self.assertIn('## Red Flags', text)
                self.assertIn('../shared/DEFINITION-OF-DONE.md', text)
                self.assertEqual(text.count('**Done when:**'), 1)

    def test_definition_of_done_is_one_shared_reference(self):
        text = (ROOT / 'skills/shared/DEFINITION-OF-DONE.md').read_text()
        self.assertIn('../engineering/upstream/references/definition-of-done.md', text)
        self.assertIn('Task acceptance is met', text)
        self.assertIn('NOT_CHECKED', text)

    def test_sibling_pairs_name_each_other(self):
        # The pairs from docs/skill-standard.md, in both directions.
        pairs = [('plan-with-me', 'plan-for-me'), ('grilling', 'grill-me'),
                 ('grilling', 'grill-with-docs'), ('grill-me', 'grill-with-docs'),
                 ('bug-harvest', 'unused-code'), ('bug-harvest', 'test-optimizer'),
                 ('unused-code', 'split-folder'),
                 ('git-commit-push', 'ponytail-review'),
                 ('ponytail-review', 'ponytail-audit')]
        for a, b in pairs:
            with self.subTest(pair=f'{a} -> {b}'):
                text = (ROOT / 'skills' / a / 'SKILL.md').read_text()
                self.assertIn(f'`/{b}`', text.split('## Boundaries', 1)[1])

    def test_the_router_names_every_skill(self):
        # Upstream's rule: a router that never mentions a skill, or still names a
        # removed one, is a router that lies.
        router = (ROOT / 'skills/ask-kit/SKILL.md').read_text()
        for path in self.skills('skills'):
            name = path.parent.name
            if name in ('shared', 'ask-kit'):
                continue
            with self.subTest(skill=name):
                self.assertIn(f'`/{name}`', router)
        listed = set(re.findall(r'`/([a-z0-9-]+)`', router))
        known = {p.parent.name for p in self.skills('skills')} | {'graphify'}
        self.assertEqual(sorted(listed - known), [], 'router names a missing skill')

    def test_portable_adapters_point_at_the_native_skill(self):
        for path in self.skills('adapters/skills'):
            name = path.parent.name
            with self.subTest(adapter=name):
                text = path.read_text()
                if name in ADAPTER_ONLY:
                    self.assertNotIn(f'../../../skills/{name}/', text)
                else:
                    native = ROOT / 'skills' / name / 'SKILL.md'
                    self.assertTrue(native.is_file(), f'{name} has no native skill')
                    self.assertIn(f'../../../skills/{name}/SKILL.md', text)
                self.assertTrue((path.parent / 'agents/openai.yaml').is_file())


if __name__ == '__main__':
    unittest.main()
