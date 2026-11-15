"""Documentation contracts for safe Orbi provider and protection qualification."""

import importlib.util
from pathlib import Path, PurePosixPath
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PurePosixPath("docs/github-native.md")
TEXT = (ROOT / DOC_PATH).read_text(encoding="utf-8")

SPEC = importlib.util.spec_from_file_location(
    "github_native_docs_check", ROOT / "skills/docs-sync/scripts/docs.py")
docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs)


def section(text, heading, level=2):
    marker = "#" * level + " " + heading + "\n"
    if marker not in text:
        raise AssertionError(f"missing section: {heading}")
    body = text.split(marker, 1)[1]
    return re.split(r"^#{1," + str(level) + r"} ", body, maxsplit=1, flags=re.M)[0]


def compact(text):
    """A section's prose independent of line wrapping."""
    return " ".join(text.split())


class GithubNativeDocsTests(unittest.TestCase):
    def test_provider_qualification_names_supported_paths_and_real_call(self):
        provider = section(TEXT, "Qualify the model provider")
        prose = compact(provider)
        for phrase in (
                "`pi_providers` unset",
                "NOT CONFIGURED",
                "model provider not configured",
                "Pi uses its own agent directory",
                "per-run",
                "pi-agent",
                "`key=literal=set`",
                "real model response",
                "bare `pi --print`",
                "provider_config_loaded",
                "contextWindow",
                "maxTokens",
                "catalog"):
            self.assertIn(phrase, prose)

        layers = compact(section(
            provider, "Offline check, inference, and live delivery", level=3))
        for layer in (
                "Offline configuration check",
                "Inference through the configured path",
                "Live delivery",
                "protected merge"):
            self.assertIn(layer, layers)

    def test_examples_are_generic_and_keep_credentials_out_of_the_worktree(self):
        provider = compact(section(TEXT, "Qualify the model provider"))
        for phrase in (
                "links `auth.json`",
                "Stored authentication",
                "$PROVIDER_API_KEY",
                "never in the repository or a worktree"):
            self.assertIn(phrase, provider)
        self.assertNotRegex(
            TEXT,
            r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
            r"sk-[A-Za-z0-9]{20,}")
        self.assertNotIn("/home/", TEXT)
        self.assertNotIn("/Users/", TEXT)
        self.assertNotIn(".local/share/orbi-kit", TEXT)

    def test_protection_diagnostics_preserve_enforced_gates(self):
        protection = compact(section(TEXT, "Read protection diagnostics safely"))
        for phrase in (
                "enforce_admins",
                "gh pr merge --match-head-commit",
                "enforced administrators",
                "strict required CI",
                "independent review",
                "human-only",
                "Never disable branch protection",
                "protected merge"):
            self.assertIn(phrase, protection)
        self.assertNotIn("--admin", TEXT)
        self.assertNotIn("Do not allow bypassing", TEXT)
        self.assertNotRegex(protection, r"(?i)repair:\s*disable")

    def test_human_review_gate_is_human_only_and_not_a_protection_substitute(self):
        gate = compact(section(TEXT, "Human acceptance is a separate gate"))
        for phrase in (
                "`/orbi setup` default to `human_review_gate = false`",
                "not required CI or independent AI review",
                "Setup preserves an existing deployment's explicitly selected policy",
                "external authorization rules remain unchanged",
                "human_review_gate = true",
                "ai-human-review",
                "Only a human applies",
                "agent and Runner must never add or remove it",
                "branch protection",
                "independent review",
                "credential isolation",
                "sensitive-change",
                "protected merge"):
            self.assertIn(phrase, gate)

    def test_diagnostics_are_release_scoped_to_pinned_sources(self):
        self.assertIn("Orbi 0.7.41", TEXT)
        self.assertIn("Re-check the release", TEXT)
        for source in (
                "blob/v0.7.41/src/orbi/setup_config.py",
                "blob/v0.7.41/src/orbi/pi_session.py",
                "blob/v0.7.41/src/orbi/merge_gate.py",
                "blob/v0.7.41/src/orbi/merge_exec.py",
                "blob/v0.7.41/src/orbi/example_config.toml"):
            self.assertIn(source, TEXT)

    def test_lifecycle_skill_names_observed_states_and_platform_limits(self):
        lifecycle = compact(section(TEXT, "Kit lifecycle skill", level=3))
        for phrase in (
                "`/orbi [status|setup|start|stop|help]`",
                "Bare invocation reads status",
                "Setup prepares without activating scheduling",
                "On Linux, status names the state it observed",
                "`absent`",
                "`prepared` when an owned timer is enabled or active",
                "`running` while any service is active, activating or reloading",
                "`draining` when no service is running but one is deactivating",
                "`stopped` when services are inactive or failed",
                "`stop` can report `draining` while a subsequent status still reports `running`",
                "`unavailable`",
                "Linux supports lifecycle changes",
                "macOS is status-only",
                "macOS status reports local deployment metadata but leaves active scheduler state `unavailable`",
                "shared bootstrap"):
            self.assertIn(phrase, lifecycle)

    def test_local_links_and_anchors_resolve(self):
        repo = docs.Repo(ROOT)
        self.assertEqual(docs.check_document(repo, "github-native", DOC_PATH), [])


if __name__ == "__main__":
    unittest.main()
