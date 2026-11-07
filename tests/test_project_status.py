"""Offline project-status regressions; no native execution or timing claims."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATH = ROOT / "docs/project.md"
PROJECT_TEXT = PROJECT_PATH.read_text(encoding="utf-8")


def section(text, heading, level=2):
    marker = "#" * level + " " + heading + "\n"
    body = text.split(marker, 1)[1]
    return re.split(r"^#{1," + str(level) + r"} ", body, maxsplit=1, flags=re.M)[0]


def anchors(text):
    """GitHub-style anchors for this document's plain Markdown headings."""
    result = set()
    counts = {}
    for heading in re.findall(r"^#{1,6} (.+)$", text, re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if not count else f"{slug}-{count}")
    return result


class ProjectStatusTests(unittest.TestCase):
    def test_current_requirements_replace_completed_task_reports(self):
        status = section(PROJECT_TEXT, "Planned work and verification")
        self.assertIn("task store", status)
        self.assertNotRegex(PROJECT_TEXT, r"\bTOOLSET-\d+")
        self.assertNotIn("TODO.archive.md", PROJECT_TEXT)
        authority = section(PROJECT_TEXT, "Autonomous execution authority")
        self.assertIn("operating-policy question without another user permission round", authority)
        self.assertIn("caller scope and saved stop/batch limits control", authority)

    def test_current_spec_does_not_retain_task_context_measurements(self):
        context = section(PROJECT_TEXT, "Task context simplification", 3)
        self.assertNotIn("five then-pending IDs", context)
        self.assertNotIn("29.0%", context)
        self.assertNotIn("At requirement capture", PROJECT_TEXT)
        self.assertTrue(context.strip(), "Keep the current context-selection contract")

    def test_live_qualification_stays_open_and_separate(self):
        # Removing completed-task history must not turn pending live proof into success.
        self.assertRegex(PROJECT_TEXT, r"[Mm]easured native qualification remains pending")
        self.assertRegex(PROJECT_TEXT, r"externally\s+enforced spending/descendant limits")
        self.assertRegex(PROJECT_TEXT, r"do not establish actual model startup or universal\s+latency")
        self.assertRegex(PROJECT_TEXT, r"offline helper tests prove none of those live outcomes")

    def test_project_local_links_and_fragments_exist(self):
        links = re.findall(r"\]\(([^)]+)\)", PROJECT_TEXT)
        self.assertTrue(links, "Link extraction must not silently match zero links")
        for link in links:
            if "://" in link or link.startswith("mailto:"):
                continue
            path, _, fragment = unquote(link).partition("#")
            target = (PROJECT_PATH.parent / path).resolve() if path else PROJECT_PATH
            with self.subTest(link=link):
                exists = target.is_dir() if path.endswith("/") else target.is_file()
                self.assertTrue(exists, f"Missing local link: {link}")
                if fragment:
                    self.assertIn(fragment, anchors(target.read_text(encoding="utf-8")))

    def test_repository_has_no_completed_task_archive(self):
        self.assertFalse((ROOT / "TODO.archive.md").exists())
        self.assertNotIn("docs/tasks/", PROJECT_TEXT)
        self.assertNotIn("](../TODO.md", PROJECT_TEXT)
        policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Git history is the record of past work", policy)
        self.assertIn("never remove an active", policy)


if __name__ == "__main__":
    unittest.main()
