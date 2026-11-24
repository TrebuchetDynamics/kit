"""The skill standard: description shape, boundaries and a checkable done line.

See docs/skill-standard.md. These are the mechanical rules; judgement rules (one
home, disclosure, positive wording) stay with review.
"""
import importlib.util
import re
import subprocess
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
BANNED_OPENERS = ('use when', 'use to', 'use for', 'use if', 'use after', 'use before')
# Hermes installs Graphify's own skill into profiles, so Kit ships the adapter only.
ADAPTER_ONLY = {'graphify'}
PILOT = ('orbi', 'update-kit', 'unslop', 'plan-for-me', 'ponytail-review',
         'git-commit-push', 'push', 'unblock', 'docs-sync', 'plan-with-me')


GUI_ANCHOR = 'gui-actions-and-visual-evidence'
GUI_TRIGGER = 'For an authorized GUI action or a visual claim, read'


def gui_entrypoint_routes(root):
    """Check the explicit conditional instruction, not fragment-stripped reachability.

    Also used against the actual npm archive. Only Kit-owned SKILL entrypoints are
    in scope: independently installed upstream Hermes Graphify is not bundled.
    """
    owner = root / 'skills/shared/COMMON-CONTRACT.md'
    if '## GUI actions and visual evidence' not in owner.read_text():
        raise AssertionError('missing GUI decision anchor')
    routes = (root / 'skills/shared/PONYTAIL.md', root / 'adapters/skills/COMMON.md')
    for route in routes:
        text = ' '.join(route.read_text().split())
        target = ('COMMON-CONTRACT.md' if route.parent.name == 'shared' else
                  '../../skills/shared/COMMON-CONTRACT.md') + '#' + GUI_ANCHOR
        if GUI_TRIGGER not in text or '](' + target + ')' not in text:
            raise AssertionError(f'{route}: missing conditional GUI anchor instruction')
        # Safety instruction must precede optional Ponytail levels/coaching.
        if route.parent.name == 'shared' and text.index(GUI_TRIGGER) > text.index('## Scope and levels'):
            raise AssertionError('GUI decision hidden behind optional coaching')
    inventory = {}
    for folder in ('skills', 'adapters/skills'):
        for entry in sorted((root / folder).glob('*/SKILL.md')):
            targets = {(entry.parent / link.split('#')[0]).resolve()
                       for link in re.findall(r'\]\(([^)\s]+)\)', entry.read_text())}
            reached = [route for route in routes if route.resolve() in targets]
            if not reached:
                raise AssertionError(f'{entry}: no explicit shared entry route')
            inventory[str(entry.relative_to(root))] = [str(r.relative_to(root)) for r in reached]
    if not inventory:
        raise AssertionError('empty shipped entrypoint inventory')
    return inventory


class SkillStandardTests(unittest.TestCase):
    def test_tracked_content_has_no_retired_executor_name(self):
        name = 'auto' + 'work'
        result = subprocess.run(
            ['git', 'grep', '-i', '-I', '-l', '-e', name, '--'],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1,
                         'Remove the retired executor name from tracked content:\n'
                         + result.stdout + result.stderr)

    def test_tracked_paths_have_no_retired_executor_name(self):
        name = b'auto' + b'work'
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                                capture_output=True, check=True, timeout=30)
        matches = [path.decode(errors='replace') for path in result.stdout.split(b'\0')
                   if name in path.lower()]
        self.assertEqual(matches, [], 'Rename tracked paths containing the retired executor name')

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

    def test_all_public_entrypoints_load_the_gui_decision(self):
        inventory = gui_entrypoint_routes(ROOT)
        self.assertIn('adapters/skills/graphify/SKILL.md', inventory)
        self.assertIn('skills/grill-me/SKILL.md', inventory)
        self.assertEqual(set(inventory), {
            str(p.relative_to(ROOT)) for folder in ('skills', 'adapters/skills')
            for p in self.skills(folder)})

    def test_gui_route_rejects_wrong_fragment_or_missing_conditional_instruction(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in ('skills/shared/COMMON-CONTRACT.md', 'skills/shared/PONYTAIL.md',
                         'adapters/skills/COMMON.md', 'adapters/skills/graphify/SKILL.md'):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((ROOT / path).read_text())
            self.assertIn('adapters/skills/graphify/SKILL.md', gui_entrypoint_routes(root))
            for relative in ('skills/shared/PONYTAIL.md', 'adapters/skills/COMMON.md'):
                route = root / relative
                original = route.read_text()
                for old, new in ((GUI_ANCHOR, 'source-freshness-and-delivery-ownership'),
                                 ('For an authorized GUI action or a visual claim, read',
                                  'Optional reference:')):
                    with self.subTest(route=relative, missing=old):
                        route.write_text(original.replace(old, new))
                        with self.assertRaisesRegex(AssertionError, 'conditional GUI anchor'):
                            gui_entrypoint_routes(root)
                        route.write_text(original)

    def test_visual_owners_cover_findings_and_explicit_edit_verification(self):
        for name in ('ui-taste', 'impeccable', 'unslop',
                     'responsive-screenshots', 'beautify-github-readme'):
            with self.subTest(skill=name):
                text = (ROOT / f'skills/{name}/SKILL.md').read_text()
                self.assertIn('../shared/COMMON-CONTRACT.md#' + GUI_ANCHOR, text)
        findings = (ROOT / 'skills/shared/UI-FINDINGS.md').read_text()
        self.assertIn('COMMON-CONTRACT.md#' + GUI_ANCHOR, findings)
        for name, section in (('ui-taste', '## Toolset rules'),
                              ('beautify-github-readme', '## Toolset rules'),
                              ('impeccable', '## Verification')):
            text = (ROOT / f'skills/{name}/SKILL.md').read_text().split(section, 1)[1]
            self.assertIn('../shared/COMMON-CONTRACT.md#' + GUI_ANCHOR, text)

    def test_planning_fast_forward_exception_is_narrow_and_source_bound(self):
        text = ' '.join((ROOT / 'skills/shared/COMMON-CONTRACT.md').read_text().split())
        section = text.split('### Standalone planner freshness', 1)[1].split(
            '**Verify identity, not names.**', 1)[0]
        for rule in ('Plan With Me and Plan For Me only', 'before scoped code analysis',
                     'canonical repository', 'intended analysis branch', 'fetch URL',
                     'branch.<branch>.remote', 'branch.<branch>.merge',
                     'exclusively held', 'untracked', 'local-only commits',
                     'detached', 'wrong-branch', 'active/foreign-worker',
                     'missing or ambiguous', 'read-only source at a verified remote SHA',
                     'local-only changes', 'historical/pinned', 'Orbi-owned',
                     'before publication', 'material drift', 'not on every interview turn',
                     'HEAD', 'FETCH_HEAD', 'freshness-dependent decisions',
                     'no commit, push, rebase, merge commit, stash, reset',
                     'no-pull/no-sync', 'no-write'):
            with self.subTest(rule=rule):
                self.assertIn(rule, section)
        for flag in ('--ff-only', '--no-rebase', '--no-autostash',
                     '--no-recurse-submodules'):
            self.assertIn(flag, section)
        for path in ('docs/project.md', 'docs/github-native.md', 'docs/cross-host.md',
                     'docs/workflows.md', 'skills/shared/WORKTREE-ISOLATION.md'):
            with self.subTest(path=path):
                self.assertNotRegex((ROOT / path).read_text(),
                    r'planning (?:modes )?do not (?:fetch|create worktrees or fetch)|'
                    r'writable planning do not fetch|does not sync or commit')

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

    def test_writing_for_agents_resolves_kit_invocation_and_read_only_completion(self):
        # Source contract only: these assertions do not measure model adherence.
        text = ' '.join((ROOT / 'skills/writing-for-agents/SKILL.md').read_text().split())
        invocation = text.split('## The bar for a document', 1)[0]
        for rule in ('before choosing metadata', 'Kit public skills',
                     'explicit host command', '/docs-sync', 'plain reference',
                     'disable-model-invocation: true', 'allow_implicit_invocation: false',
                     '../../docs/skill-standard.md', 'skills-only', 'non-Kit projects'):
            with self.subTest(rule=rule):
                self.assertIn(rule, invocation)
        planning = text.split('## Planning or read-only advice', 1)[1].split(
            '## Editing an existing skill', 1)[0]
        self.assertIn('Plan a Kit skill that another workflow needs; do not edit.', planning)
        for rule in ('inline', 'write nothing', 'executable instructions', 'proposed design'):
            self.assertIn(rule, planning)
        done = text.split('**Done when:**', 1)[1].split('**Receipt:**', 1)[0]
        self.assertIn('authorized edit', done)
        self.assertIn('affected checks', done)
        self.assertIn('planning/read-only', done)
        self.assertIn('without implementation or a line delta', done)
        adapter = (ROOT / 'adapters/skills/writing-for-agents/SKILL.md').read_text()
        self.assertNotIn('Report the documents changed, lines before and after', adapter)

    def test_orbi_protection_observations_do_not_override_activation_authority(self):
        skill = ' '.join((ROOT / 'skills/orbi/SKILL.md').read_text().split())
        lifecycle = ' '.join((ROOT / 'skills/orbi/references/lifecycle.md').read_text().split())
        for text in (skill, lifecycle):
            for rule in ('Branch protection is not a Kit setup/start prerequisite',
                         'informational, not scheduling blockers', 'HTTP 403',
                         'PR-only', 'repository access', 'ownership'):
                self.assertIn(rule, text)
        self.assertIn('explicit pauses, cutover requirements and human-only gates', skill)
        self.assertIn('Keep explicit pauses and human-only gates', lifecycle)
        self.assertNotIn('obtain the read-only protection view/owner repair above', lifecycle)
        self.assertNotIn('pause/cutover/branch/CI/human', lifecycle)

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

    def test_lgtm_continues_open_session_todos_without_adding_authority(self):
        skill = ' '.join((ROOT / 'skills/lgtm/SKILL.md').read_text().split())
        for rule in ('host\'s native todo or task-list tool for the current session',
                     'Pi and Pi-Bolt todos, Claude Code tasks',
                     'Without such a list, this rule does not apply',
                     'session state, not a backlog or a replacement for GitHub Issues',
                     'A todo item adds no authority',
                     'outside inherited authority or needing a new owner decision',
                     'report it and do not do it',
                     'A blocked item stays open',
                     'report the exact blocker once',
                     'continue items that do not depend on it',
                     'unanswered external request', 'host approval gate',
                     'continuing no-write/no-push limit',
                     'only when no actionable todo item is open'):
            with self.subTest(rule=rule):
                self.assertIn(rule, skill)
        table = skill.split('## Low-effort input', 1)[1].split('## Fast path', 1)[0]
        self.assertIn('| Open session todo items after the checkpoint action |', table)
        fast_path = skill.split('## Fast path', 1)[1].split('## Checkpoint scope', 1)[0]
        for rule in ('After resolving the checkpoint action, read open session todo items',
                     'inside inherited authority in dependency order with its checks',
                     'mark it done only after its check passes',
                     'continue until each is done or blocked'):
            self.assertIn(rule, fast_path)

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
                 ('agents-md-generator', 'writing-for-agents'),
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
