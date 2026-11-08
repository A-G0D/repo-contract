"""Tests that kill surviving single-site mutants in repo_contract/cli.py and contract.py."""

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from repo_contract import contract
from repo_contract.cli import _render_text, build_parser, main


def _contract(**over) -> dict:
    base = {
        "name": "demo",
        "repo": "/x/demo",
        "remote": "",
        "ai_policy": {
            "category": "human_in_loop",
            "agent_contributions_allowed": True,
            "evidence": "",
            "evidence_snippets": [],
            "requires_disclosure": False,
        },
        "policy_sources": [],
        "commands": {"test": [], "lint": [], "build": []},
        "commit_style": {"style": "freeform", "n": 3, "conventional_ratio": 0.0},
        "pr": {
            "issue_required": False,
            "requires_dco_signoff": False,
            "requires_cla": False,
            "requires_changelog": False,
            "template_sections": [],
        },
        "docs": {},
    }
    base.update(over)
    return base


class TextRenderTests(unittest.TestCase):
    def test_single_evidence_has_no_extra_suffix(self):
        c = _contract()
        c["ai_policy"]["evidence"] = "agents banned"
        c["ai_policy"]["evidence_snippets"] = ["agents banned"]
        out = _render_text(c)
        self.assertIn("  evidence: agents banned", out)
        self.assertNotIn("more", out)

    def test_no_evidence_has_no_evidence_line(self):
        self.assertNotIn("evidence:", _render_text(_contract()))

    def test_verdict_words(self):
        self.assertIn("agent contributions: allowed", _render_text(_contract()))
        c = _contract()
        c["ai_policy"]["agent_contributions_allowed"] = False
        self.assertIn("agent contributions: FORBIDDEN", _render_text(c))

    def test_quiet_keeps_exactly_two_lines(self):
        c = _contract(policy_sources=["CONTRIBUTING.md"], docs={"CONTRIBUTING.md": "contributing"})
        c["ai_policy"]["evidence"] = "agents banned"
        c["ai_policy"]["evidence_snippets"] = ["agents banned"]
        out = _render_text(c, quiet=True)
        self.assertEqual(len(out.split("\n")), 2)
        self.assertNotIn("commands:", out)

    def test_policy_docs_line_only_when_sources(self):
        self.assertNotIn("policy docs:", _render_text(_contract()))
        c = _contract(policy_sources=["CONTRIBUTING.md", "AGENTS.md"])
        self.assertIn("  policy docs: CONTRIBUTING.md, AGENTS.md", _render_text(c))

    def test_docs_read_line_only_when_docs(self):
        self.assertNotIn("docs read:", _render_text(_contract()))
        c = _contract(docs={"CONTRIBUTING.md": "contributing"})
        self.assertIn("  docs read: CONTRIBUTING.md", _render_text(c))

    def test_commit_ratio_label(self):
        out = _render_text(_contract())
        self.assertIn("(3 samples, conventional ratio 0.0)", out)


class CliExitAndStreamTests(unittest.TestCase):
    def test_json_stdout_ends_with_single_newline(self):
        fixed = _contract()
        buf = io.StringIO()
        with mock.patch("repo_contract.cli.build_contract", return_value=fixed):
            with contextlib.redirect_stdout(buf):
                self.assertEqual(main(["scan", "--repo", "/x", "--format", "json"]), 0)
        out = buf.getvalue()
        self.assertTrue(out.endswith("}\n"))
        self.assertFalse(out.endswith("}\n\n"))
        self.assertEqual(json.loads(out), fixed)

    def test_bad_patterns_message_goes_to_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("not json")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(main(["scan", "--repo", tmp, "--patterns", bad]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("repo-contract:", err.getvalue())

    def test_missing_subcommand_is_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main([])
        self.assertEqual(cm.exception.code, 2)


class ParserDefaultTests(unittest.TestCase):
    def test_defaults(self):
        args = build_parser().parse_args(["scan"])
        self.assertEqual(args.repo, ".")
        self.assertEqual(args.format, "text")
        self.assertIsNone(args.patterns)
        self.assertFalse(args.quiet)
        self.assertFalse(args.fail_if_forbidden)

    def test_version_string(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit):
                build_parser().parse_args(["--version"])
        self.assertTrue(buf.getvalue().startswith("repo-contract "))


class ContractHelperTests(unittest.TestCase):
    def test_line_continuation_is_not_a_command(self):
        self.assertEqual(contract._command_candidates("pytest -q \\"), [])

    def test_non_test_go_command_filtered(self):
        self.assertEqual(contract._command_candidates("go run ./cmd/app"), [])

    def test_command_pick_capped_at_five(self):
        docs = "\n".join(f"pytest tests/test_{i}.py" for i in range(6))
        with tempfile.TemporaryDirectory() as tmp:
            picked = contract.extract_commands(tmp, docs)["test"]
        self.assertEqual(len(picked), 5)

    def test_workflow_files_yaml_and_travis(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rel in (".github/workflows/ci.yaml", ".travis.yml", ".github/other.yml"):
                path = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("x: 1\n")
            files = contract.workflow_files(tmp)
        self.assertIn(".github/workflows/ci.yaml", files)
        self.assertIn(".travis.yml", files)
        self.assertNotIn(".github/other.yml", files)

    def test_build_contract_rejects_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x")
            with self.assertRaisesRegex(ValueError, "not a directory"):
                contract.build_contract(path)

    def test_generated_by_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(contract.build_contract(tmp)["generated_by"], "repo-contract")


class CommitStyleTests(unittest.TestCase):
    def _style(self, messages):
        proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="\n".join(messages))
        with mock.patch("repo_contract.contract.subprocess.run", return_value=proc):
            return contract.detect_commit_style("/x")

    def test_conventional_threshold_is_inclusive(self):
        msgs = ["feat: a", "fix: b", "chore: c", "x d", "y e"]
        self.assertEqual(self._style(msgs)["style"], "conventional")

    def test_imperative_threshold_is_inclusive(self):
        msgs = ["Add a", "Fix b", "Make c", "x d", "y e"]
        self.assertEqual(self._style(msgs)["style"], "imperative")

    def test_ratio_rounded_to_two_places(self):
        style = self._style(["feat: a", "feat: b", "Add c"])
        self.assertEqual(style["conventional_ratio"], 0.67)

    def test_samples_capped_at_eight(self):
        style = self._style([f"Add item {i}" for i in range(10)])
        self.assertEqual(style["n"], 10)
        self.assertEqual(len(style["samples"]), 8)


class PrRuleTests(unittest.TestCase):
    def _with_template(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "PULL_REQUEST_TEMPLATE.md"), "w", encoding="utf-8") as fh:
                fh.write(text)
            return contract.detect_pr_rules(
                tmp, {"PULL_REQUEST_TEMPLATE.md": "pr_template"}, ""
            )

    def test_headings_are_sections_not_instructions(self):
        rules = self._with_template("# Summary\n\nExplain the change in detail.\n")
        self.assertEqual(rules["template_sections"], ["Summary"])
        self.assertEqual(rules["template_instructions"], ["Explain the change in detail."])

    def test_html_comments_are_not_instructions(self):
        rules = self._with_template("<!-- hidden comment line here -->\nVisible instruction text.\n")
        self.assertEqual(rules["template_instructions"], ["Visible instruction text."])

    def test_instruction_min_length_is_sixteen(self):
        fifteen = "a" * 15
        sixteen = "b" * 16
        rules = self._with_template(f"{fifteen}\n{sixteen}\n")
        self.assertEqual(rules["template_instructions"], [sixteen])

    def test_section_cap_is_twelve(self):
        text = "".join(f"# Section {i}\n" for i in range(13))
        rules = self._with_template(text)
        self.assertEqual(len(rules["template_sections"]), 12)


class RemoteTests(unittest.TestCase):
    def _remote(self, url: str) -> str:
        proc = subprocess.CompletedProcess(args=[], returncode=0, stdout=url + "\n")
        with mock.patch("repo_contract.contract.subprocess.run", return_value=proc):
            return contract.detect_remote("/x")

    def test_http_userinfo_dropped(self):
        self.assertEqual(
            self._remote("http://user:tok@example.com/r.git"), "http://example.com/r.git"
        )

    def test_ssh_keeps_login_user_drops_password(self):
        self.assertEqual(self._remote("ssh://git:pw@example.com/r.git"), "ssh://git@example.com/r.git")


class MarkdownTests(unittest.TestCase):
    def test_markdown_generated_by_and_disclosure_label(self):
        out = contract.render_markdown(_contract())
        self.assertIn("- disclosure required: False", out)
        self.assertIn("- remote: `(none)`", out)
        self.assertIn("- AI policy evidence: (none found)", out)

    def test_markdown_no_template_section_line_when_empty(self):
        self.assertNotIn("PR template sections", contract.render_markdown(_contract()))

    def test_markdown_empty_command_dash(self):
        self.assertIn("- test: —", contract.render_markdown(_contract()))

    def test_markdown_doc_kind_is_code_span(self):
        out = contract.render_markdown(_contract(docs={"CONTRIBUTING.md": "contributing"}))
        self.assertIn("- `CONTRIBUTING.md` (contributing)", out)
        self.assertIn("## Documents read", out)


class PrintableTests(unittest.TestCase):
    def test_newline_is_replaced(self):
        self.assertEqual(contract._printable("a\nb"), "a b")

    def test_backtick_quoted_in_code_span(self):
        self.assertEqual(contract._code("a`b"), "`a'b`")


if __name__ == "__main__":
    unittest.main()
