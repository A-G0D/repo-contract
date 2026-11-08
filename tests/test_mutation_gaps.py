"""Tests for behavior that mutation testing showed no existing test protects."""

import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from repo_contract import contract, docs, policy


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class DocsGapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_find_docs_matches_nested_agents_file(self):
        # Like .github/CONTRIBUTING.md, a nested AGENTS.md counts as the agents doc.
        _write(self.root, ".github/AGENTS.md", "rules\n")
        self.assertEqual(docs.find_docs(self.root), {".github/AGENTS.md": "agents"})

    def test_read_text_unreadable_file_returns_empty(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root can read mode-000 files")
        _write(self.root, "CONTRIBUTING.md", "secret rules\n")
        path = os.path.join(self.root, "CONTRIBUTING.md")
        os.chmod(path, 0)
        try:
            self.assertEqual(docs.read_text(self.root, "CONTRIBUTING.md"), "")
        finally:
            os.chmod(path, 0o644)

    def test_read_text_honours_limit(self):
        _write(self.root, "a.md", "abcdefgh")
        self.assertEqual(docs.read_text(self.root, "a.md", limit=5), "abcde")

    def test_docs_text_excludes_readme(self):
        _write(self.root, "README.md", "README ONLY TEXT\n")
        _write(self.root, "CONTRIBUTING.md", "contribute here\n")
        out = docs.docs_text(
            self.root, {"README.md": "readme", "CONTRIBUTING.md": "contributing"}
        )
        self.assertNotIn("README ONLY TEXT", out)
        self.assertIn("contribute here", out)

    def test_docs_text_is_capped_at_limit(self):
        # Two 60k docs (read_text's own cap) exceed the 80k default, so the join must be cut.
        _write(self.root, "CONTRIBUTING.md", "c" * 60_000)
        _write(self.root, "AGENTS.md", "a" * 60_000)
        out = docs.docs_text(
            self.root, {"CONTRIBUTING.md": "contributing", "AGENTS.md": "agents"}
        )
        self.assertEqual(len(out), 80_000)


class PolicyGapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_whitespace_only_match_is_not_evidence(self):
        result = policy.classify(
            "hello world", extra={"forbidden_autonomous": (" ",)}
        )
        self.assertEqual(result["category"], "unknown")
        self.assertEqual(result["evidence_snippets"], [])

    def test_adjacent_matches_are_both_kept(self):
        # "a" ends exactly where "b" starts: non-overlapping, so both are evidence.
        result = policy.classify("ab", extra={"forbidden_autonomous": ("a", "b")})
        self.assertEqual(result["evidence_snippets"], ["a", "b"])

    def test_snippet_truncated_to_snippet_max(self):
        result = policy.classify(
            "x" * 500, extra={"forbidden_autonomous": ("x+",)}
        )
        self.assertEqual(len(result["evidence"]), policy.SNIPPET_MAX)

    def test_no_evidence_is_empty_string(self):
        result = policy.classify("nothing relevant here")
        self.assertEqual(result["evidence"], "")
        self.assertEqual(result["category"], "unknown")

    def test_path_with_separator_is_a_file_not_a_shipped_set(self):
        # Only a bare name (no separator) selects a shipped set.
        sub = os.path.join(self.root, "sub")
        os.makedirs(sub)
        local = os.path.join(sub, "es")
        with open(local, "w", encoding="utf-8") as fh:
            json.dump(
                [{"language": "en", "category": "forbidden_autonomous",
                  "pattern": "zzz-local-only", "label": "local"}],
                fh,
            )
        loaded = policy.load_patterns(local)
        self.assertEqual(loaded["forbidden_autonomous"], ("zzz-local-only",))

        # "./es" has a separator, so it is a file path: no file here means an error,
        # even though a shipped set named "es" exists.
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with self.assertRaises(ValueError):
                policy.load_patterns("./es")
        finally:
            os.chdir(cwd)

    def test_policy_sources_selects_only_policy_documents(self):
        docs_map = {
            "README.md": "readme",
            "SECURITY.md": "security",
            "CHANGELOG.md": "changelog",
            "CONTRIBUTING.md": "contributing",
            "AGENTS.md": "agents",
        }
        self.assertEqual(
            sorted(policy.policy_sources(docs_map)), ["AGENTS.md", "CONTRIBUTING.md"]
        )


class ContractGapTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_command_with_shell_substitution_is_skipped(self):
        self.assertEqual(contract._command_candidates("run: pytest -q $(ls)"), [])

    def test_command_line_length_boundary(self):
        ok = "pytest " + "a" * (200 - len("pytest "))
        too_long = ok + "a"
        self.assertEqual(contract._command_candidates(ok), [ok])
        self.assertEqual(contract._command_candidates(too_long), [])

    def test_extract_commands_deduplicates(self):
        cmds = contract.extract_commands(self.root, "run: pytest -q\nrun: pytest -q\n")
        self.assertEqual(cmds["test"], ["pytest -q"])

    def test_workflow_files_ignores_yaml_outside_ci(self):
        _write(self.root, ".github/workflows/ci.yml", "x: 1\n")
        _write(self.root, "config/deploy.yml", "x: 1\n")
        self.assertEqual(contract.workflow_files(self.root), [".github/workflows/ci.yml"])

    def _commit_style(self, messages):
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="\n".join(messages) + "\n", stderr=""
        )
        with mock.patch.object(contract.subprocess, "run", return_value=proc):
            return contract.detect_commit_style(self.root)

    def test_commit_style_conventional_at_exact_threshold(self):
        # 3 of 5 (0.6) conventional is enough; nothing else matches.
        style = self._commit_style(["feat: a", "fix: b", "chore: c", "wip", "..."])
        self.assertEqual(style["style"], "conventional")

    def test_commit_style_imperative_at_exact_threshold(self):
        style = self._commit_style(["Add parser", "Fix bug", "Update docs", "wip", "..."])
        self.assertEqual(style["style"], "imperative")

    def test_pr_template_skips_html_comment_lines(self):
        _write(
            self.root,
            "PULL_REQUEST_TEMPLATE.md",
            "## Summary\n<!-- Fill in the sections below before you open the PR\n"
            "Describe your change in detail here\n"
            "the comment block closes on this line -->\n",
        )
        rules = contract.detect_pr_rules(
            self.root, {"PULL_REQUEST_TEMPLATE.md": "pr_template"}, ""
        )
        self.assertEqual(rules["template_instructions"], ["Describe your change in detail here"])

    def test_detect_remote_leaves_plain_https_url_alone(self):
        proc = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://github.com/acme/repo.git\n", stderr=""
        )
        with mock.patch.object(contract.subprocess, "run", return_value=proc):
            self.assertEqual(
                contract.detect_remote(self.root), "https://github.com/acme/repo.git"
            )

    def test_build_contract_reports_changelog_files(self):
        _write(self.root, "CHANGELOG.md", "# changes\n")
        _write(self.root, "README.md", "# hi\n")
        built = contract.build_contract(self.root)
        self.assertEqual(built["changelog_files"], ["CHANGELOG.md"])


if __name__ == "__main__":
    unittest.main()
