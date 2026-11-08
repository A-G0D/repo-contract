"""Edge-case tests for uncovered branches: docs walking, pattern loading, command extraction, git probes, CLI formats."""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repo_contract import docs as docs_mod
from repo_contract.cli import main
from repo_contract.contract import _command_candidates, detect_commit_style, detect_remote, workflow_files
from repo_contract.docs import find_docs, read_text, walk_files
from repo_contract.policy import load_patterns


class TestDocsEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-edge-docs-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _touch(self, rel, text="x\n"):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_walk_files_stops_at_cap(self):
        for i in range(5):
            self._touch(f"f{i}.txt")
        with mock.patch.object(docs_mod, "MAX_SCAN_FILES", 3):
            self.assertEqual(len(walk_files(self.tmp)), 3)

    def test_read_text_missing_file_is_empty(self):
        self.assertEqual(read_text(self.tmp, "nope.md"), "")

    def test_find_docs_skips_kind_already_seen(self):
        self._touch("a.md")
        self._touch("b.md")
        patterns = ((r"^a\.md$", "a.md"), (r"^b\.md$", "a.md"))
        with mock.patch.object(docs_mod, "DOC_PATTERNS", patterns):
            self.assertEqual(find_docs(self.tmp), {"a.md": "a.md"})

    @unittest.expectedFailure
    def test_find_docs_keeps_one_entry_per_kind(self):
        # Bug: find_docs checks `kind in docs` (keys are paths), so duplicate kinds are never dropped.
        self._touch("CONTRIBUTING.md")
        self._touch(".github/CONTRIBUTING.md")
        kinds = list(find_docs(self.tmp).values())
        self.assertEqual(kinds.count("contributing"), 1)


class TestPolicyEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-edge-pol-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_directory_path_is_unreadable(self):
        sub = os.path.join(self.tmp, "dir.d")
        os.makedirs(sub)
        with self.assertRaises(ValueError):
            load_patterns(sub)

    def test_empty_pattern_rejected(self):
        path = self._write("empty.json", '[{"category": "human_in_loop", "pattern": ""}]')
        with self.assertRaises(ValueError):
            load_patterns(path)


class TestCommandEdges(unittest.TestCase):
    def test_skips_templated_long_and_unknown_lines(self):
        text = "\n".join(
            [
                "- run: pytest ${{ matrix.x }}",
                "- run: pytest " + "x" * 250,
                "- run: echo hello",
                "- run: go version",
                "- run: pytest -q",
            ]
        )
        self.assertEqual(_command_candidates(text), ["pytest -q"])


class TestWorkflowEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-edge-wf-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_gitlab_ci_is_a_workflow(self):
        with open(os.path.join(self.tmp, ".gitlab-ci.yml"), "w", encoding="utf-8") as fh:
            fh.write("job: {}\n")
        self.assertIn(".gitlab-ci.yml", workflow_files(self.tmp))


class TestGitProbeEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-edge-git-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_commit_style_when_git_fails(self):
        with mock.patch("repo_contract.contract.subprocess.run", side_effect=OSError("no git")):
            self.assertEqual(detect_commit_style(self.tmp)["style"], "unknown")

    def test_commit_style_outside_repo_is_unknown(self):
        self.assertEqual(detect_commit_style(self.tmp)["style"], "unknown")

    def test_commit_style_freeform(self):
        out = subprocess.CompletedProcess(args=[], returncode=0, stdout="wip\nmisc\nstuff\n", stderr="")
        with mock.patch("repo_contract.contract.subprocess.run", return_value=out):
            self.assertEqual(detect_commit_style(self.tmp)["style"], "freeform")

    def test_remote_when_git_fails(self):
        with mock.patch("repo_contract.contract.subprocess.run", side_effect=OSError("no git")):
            self.assertEqual(detect_remote(self.tmp), "")

    def test_remote_without_origin_is_empty(self):
        self.assertEqual(detect_remote(self.tmp), "")


class TestCliEdges(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-edge-cli-")
        os.makedirs(os.path.join(self.tmp, "src"))
        with open(os.path.join(self.tmp, "src", "app.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_json_format_prints_contract(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["scan", "--repo", self.tmp, "--format", "json"]), 0)
        self.assertTrue(out.getvalue().lstrip().startswith("{"))

    def test_markdown_format_prints_contract(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["scan", "--repo", self.tmp, "--format", "markdown"]), 0)
        self.assertTrue(out.getvalue().strip())

    def test_module_entry_point_version(self):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["repo-contract", "--version"]):
            with contextlib.redirect_stdout(out):
                with self.assertRaises(SystemExit) as cm:
                    runpy.run_module("repo_contract.__main__", run_name="__main__")
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("repo-contract", out.getvalue())


if __name__ == "__main__":
    unittest.main()
