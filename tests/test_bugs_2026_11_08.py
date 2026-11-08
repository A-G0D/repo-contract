"""Regression tests for bugs confirmed on 2026-11-08."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repo_contract.cli import main
from repo_contract.contract import build_contract, detect_remote, render_markdown
from repo_contract.docs import find_docs, read_text


class _TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-bug-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _touch(self, rel, text="x\n"):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class TestMarkdownRemoteBacktick(_TmpCase):
    def test_remote_line_closes_with_backtick(self):
        # Bug 1: the "(none)" remote line opened with a backtick but closed with a quote.
        md = render_markdown(build_contract(self.tmp))
        self.assertIn("- remote: `(none)`\n", md)


class TestRemoteCredentialsStripped(unittest.TestCase):
    def test_userinfo_removed_from_https_remote(self):
        # Bug 2: credentials embedded in an http(s) remote URL must not be stored.
        out = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="https://user:tok@github.com/o/r.git\n", stderr=""
        )
        with mock.patch("repo_contract.contract.subprocess.run", return_value=out):
            self.assertEqual(detect_remote("/nonexistent"), "https://github.com/o/r.git")

    def test_password_removed_from_ssh_remote_user_kept(self):
        for url, want in (
            ("ssh://git:pw@host.example/o/r.git\n", "ssh://git@host.example/o/r.git"),
            ("ssh://git@host.example/o/r.git\n", "ssh://git@host.example/o/r.git"),
            ("git@github.com:o/r.git\n", "git@github.com:o/r.git"),
        ):
            out = subprocess.CompletedProcess(args=[], returncode=0, stdout=url, stderr="")
            with mock.patch("repo_contract.contract.subprocess.run", return_value=out):
                self.assertEqual(detect_remote("/nonexistent"), want)


class TestChangelogHeaderNotMatched(_TmpCase):
    def test_changelog_file_without_mention_does_not_require_entry(self):
        # Bug 3: the injected "## CHANGELOG.md" header must not count as a changelog requirement.
        self._touch("CHANGELOG.md", "Release history for the project.\n")
        self._touch("CONTRIBUTING.md", "Write tests and keep diffs small.\n")
        self.assertFalse(build_contract(self.tmp)["pr"]["requires_changelog"])


class TestCliOutputPathErrors(_TmpCase):
    def test_unwritable_json_out_is_clean_exit_2(self):
        # Bug 4: a missing output directory must not raise a traceback.
        bad = os.path.join(self.tmp, "no-such-dir", "out.json")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(main(["scan", "--repo", self.tmp, "--json-out", bad]), 2)
        self.assertIn("repo-contract:", err.getvalue())

    def test_unwritable_markdown_out_is_clean_exit_2(self):
        bad = os.path.join(self.tmp, "no-such-dir", "out.md")
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(main(["scan", "--repo", self.tmp, "--markdown-out", bad]), 2)
        self.assertIn("repo-contract:", err.getvalue())


class TestSymlinkedDocsIgnored(_TmpCase):
    def setUp(self):
        super().setUp()
        self.outside = tempfile.mkdtemp(prefix="rc-bug-outside-")
        self.secret = os.path.join(self.outside, "secret.txt")
        with open(self.secret, "w", encoding="utf-8") as fh:
            fh.write("TOP SECRET\n")

    def tearDown(self):
        shutil.rmtree(self.outside, ignore_errors=True)
        super().tearDown()

    def test_symlinked_contributing_is_not_a_doc(self):
        # Bug 5: CONTRIBUTING.md -> outside file must not be discovered.
        os.symlink(self.secret, os.path.join(self.tmp, "CONTRIBUTING.md"))
        self.assertNotIn("CONTRIBUTING.md", find_docs(self.tmp))

    def test_symlinked_doc_is_not_read(self):
        os.symlink(self.secret, os.path.join(self.tmp, "CONTRIBUTING.md"))
        self.assertEqual(read_text(self.tmp, "CONTRIBUTING.md"), "")


if __name__ == "__main__":
    unittest.main()
