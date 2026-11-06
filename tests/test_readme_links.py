"""Root README navigation contracts; external URLs and GitHub rendering are not checked."""
import importlib.util
from pathlib import Path, PurePosixPath
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('docs_check', ROOT / 'skills/docs-sync/scripts/docs.py')
docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs)


class ReadmeLinksTests(unittest.TestCase):
    def test_relative_links_and_pinned_incoming_anchors(self):
        readme = PurePosixPath('README.md')
        repo = docs.Repo(ROOT)
        self.assertEqual(docs.check_document(repo, 'readme', readme), [])

        # Keep incoming targets even when the README no longer links to them itself.
        pinned = set('''
            kit a-toolset-of-skills-for-coding-agents the-skills install pi claude-code
            codex paseo hermes-optional first-use-in-your-project the-runner-autowork
            your-work-queue safety-before-installing updating renamed-from-hermes-toolset
            what-verification-proves project-status paseo-interface documentation
        '''.split())
        self.assertLessEqual(pinned, docs.anchors(repo.text(readme)))

        # These consumers are outside the role manifest's Markdown-link coverage.
        incoming = (
            ('tasks/goals/PASEO-PLUGIN.md', 'README.md#paseo-interface'),
            ('docs/evaluation.md', '../README.md#safety-before-installing'),
            ('docs/troubleshooting.md', '../README.md#first-use-in-your-project'),
        )
        for name, target in incoming:
            with self.subTest(consumer=name):
                prose = docs.FENCE.sub('', repo.text(PurePosixPath(name)))
                if name.startswith('tasks/'):
                    self.assertIn(f'\nsource = "{target}"\n', prose)
                    base = ROOT  # Task sources are repository-relative, not document-relative.
                else:
                    self.assertIn(target, docs.LINK.findall(docs.CODE.sub('', prose)))
                    base = (ROOT / name).parent
                file, _, anchor = target.partition('#')
                self.assertEqual((base / file).resolve(), ROOT / readme)
                self.assertFalse(repo.anchor_missing(readme, anchor), target)


if __name__ == '__main__':
    unittest.main()
