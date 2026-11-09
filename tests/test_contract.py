"""Tests for document discovery, AI-policy classification, contract building, and the CLI."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repo_contract.cli import main
from repo_contract.contract import build_contract, extract_commands, render_markdown
from repo_contract.docs import find_docs, walk_files
from repo_contract.policy import classify, load_patterns

FORBIDDEN = """# AI Policy

Autonomous agents are not allowed to be used for contributing to this project.
Pull requests that appear in violation of this will be closed.
"""

HUMAN_IN_LOOP = """# Contributing

## Use of AI

AI-assisted contributions are allowed with disclosure. The human author must review
and be responsible for any code submitted. Explain AI assistance in the PR.
Add an entry in CHANGES.md for every change.
Sign off your commits with Signed-off-by.
"""

WORKFLOW = """name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test
        run: |
          python -m pytest -q
          python -m ruff check .
"""


def make_repo(tmp: str, *, forbidden: bool = False) -> str:
    repo = os.path.join(tmp, "repo")
    os.makedirs(os.path.join(repo, ".github", "workflows"), exist_ok=True)
    os.makedirs(os.path.join(repo, "src"), exist_ok=True)
    with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# demo\n\nA demo repository.\n")
    with open(os.path.join(repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
        fh.write(FORBIDDEN if forbidden else HUMAN_IN_LOOP)
    with open(os.path.join(repo, ".github", "workflows", "ci.yml"), "w", encoding="utf-8") as fh:
        fh.write(WORKFLOW)
    with open(os.path.join(repo, "CHANGES.md"), "w", encoding="utf-8") as fh:
        fh.write("# Changes\n")
    with open(
        os.path.join(repo, ".github", "pull_request_template.md"), "w", encoding="utf-8"
    ) as fh:
        fh.write("# Summary\n\n# Tests\n\nDescribe the tests you ran.\n")
    with open(os.path.join(repo, "src", "app.py"), "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    return repo


def git_commit(repo: str, message: str) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=demo",
            "-c",
            "user.email=demo@example.com",
            "commit",
            "-qm",
            message,
        ],
        cwd=repo,
        check=True,
    )


class TestDocs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-docs-")
        self.repo = make_repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_find_docs_kinds(self):
        docs = find_docs(self.repo)
        kinds = set(docs.values())
        self.assertIn("contributing", kinds)
        self.assertIn("changelog", kinds)
        self.assertIn("pr_template", kinds)
        self.assertIn("readme", kinds)

    def test_walk_skips_git_and_caches(self):
        for skip in (".git", "__pycache__", ".venv"):
            os.makedirs(os.path.join(self.repo, skip), exist_ok=True)
            with open(os.path.join(self.repo, skip, "ignored.txt"), "w", encoding="utf-8") as fh:
                fh.write("x")
        files = walk_files(self.repo)
        self.assertFalse(any(f.split("/")[0] in (".git", "__pycache__", ".venv") for f in files))


class TestPolicy(unittest.TestCase):
    def test_forbidden(self):
        result = classify(FORBIDDEN)
        self.assertEqual(result["category"], "forbidden_autonomous")
        self.assertFalse(result["agent_contributions_allowed"])
        self.assertIn("Autonomous agents", result["evidence"])

    def test_human_in_loop(self):
        result = classify(HUMAN_IN_LOOP)
        self.assertEqual(result["category"], "human_in_loop")
        self.assertTrue(result["agent_contributions_allowed"])
        self.assertTrue(result["requires_disclosure"])

    def test_ai_mentioned(self):
        result = classify("# Contributing\n\nPlease mention when you use an AI assistant.\n")
        self.assertEqual(result["category"], "ai_mentioned")

    def test_unknown(self):
        result = classify("# Contributing\n\nRun the tests before opening a PR.\n")
        self.assertEqual(result["category"], "unknown")
        self.assertTrue(result["agent_contributions_allowed"])

    def test_fully_automated_variant(self):
        text = "Fully automated agents will be rejected.\n"
        self.assertEqual(classify(text)["category"], "forbidden_autonomous")


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-cmd-")
        self.repo = make_repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_commands_from_workflow(self):
        commands = extract_commands(self.repo, "")
        self.assertIn("python -m pytest -q", commands["test"])
        self.assertIn("python -m ruff check .", commands["lint"])

    def test_docs_commands_as_fallback(self):
        docs = "Run `pytest -q` and `ruff check .` in the repository root.\n"
        commands = extract_commands(self.repo, docs)
        self.assertTrue(any("pytest" in c for c in commands["test"]))
        self.assertTrue(any("ruff" in c for c in commands["lint"]))


class TestContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-contract-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_allowed_contract(self):
        repo = make_repo(self.tmp)
        git_commit(repo, "feat: add demo app")
        contract = build_contract(repo)
        self.assertTrue(contract["ai_policy"]["agent_contributions_allowed"])
        self.assertIn("CONTRIBUTING.md", contract["docs"])
        self.assertTrue(contract["pr"]["requires_changelog"])
        self.assertTrue(contract["pr"]["requires_dco_signoff"])
        self.assertIn("Summary", contract["pr"]["template_sections"])
        self.assertEqual(contract["commit_style"]["style"], "conventional")
        self.assertIn("Contribution contract", render_markdown(contract))

    def test_forbidden_contract(self):
        repo = make_repo(self.tmp, forbidden=True)
        git_commit(repo, "Initial commit")
        contract = build_contract(repo)
        self.assertEqual(contract["ai_policy"]["category"], "forbidden_autonomous")
        self.assertFalse(contract["ai_policy"]["agent_contributions_allowed"])
        self.assertEqual(contract["commit_style"]["style"], "imperative")

    def test_bad_path_raises(self):
        with self.assertRaises(ValueError):
            build_contract(os.path.join(self.tmp, "does-not-exist"))


TWO_RULES = """# Contributing

Autonomous agents are not allowed to be used for contributing to this project.

## Later section

AI-generated pull requests are not accepted. Autonomous agents are not allowed here either.
"""


class TestEvidence(unittest.TestCase):
    def test_all_snippets_returned_in_document_order(self):
        res = classify(TWO_RULES)
        self.assertEqual(res["category"], "forbidden_autonomous")
        self.assertEqual(len(res["evidence_snippets"]), 2)
        self.assertEqual(
            res["evidence_snippets"][0],
            "Autonomous agents are not allowed",
        )
        self.assertIn("AI-generated pull requests are not accepted", res["evidence_snippets"][1])

    def test_evidence_string_stays_first_snippet(self):
        res = classify(TWO_RULES)
        self.assertEqual(res["evidence"], res["evidence_snippets"][0])

    def test_hashes_match_snippets_and_are_stable(self):
        res = classify(TWO_RULES)
        self.assertEqual(len(res["evidence_sha256"]), 2)
        self.assertEqual(res["evidence_sha256"], classify(TWO_RULES)["evidence_sha256"])
        self.assertEqual(len(res["evidence_sha256"][0]), 64)

    def test_no_evidence_gives_empty_list(self):
        self.assertEqual(classify("Nothing here.")["evidence_snippets"], [])

    def test_cli_text_notes_more(self):
        tmp = tempfile.mkdtemp(prefix="rc-ev-")
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = make_repo(tmp)
        with open(os.path.join(repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
            fh.write(TWO_RULES)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["scan", "--repo", repo])
        self.assertIn("(+1 more, see --format json)", buf.getvalue())


ES_DOC = """# Contribuir

Los agentes autonomos no estan permitidos en este proyecto.
"""


class TestPatterns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-pat-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_default_is_english_only(self):
        self.assertEqual(classify(ES_DOC)["category"], "unknown")

    def test_custom_pattern_file(self):
        path = self._write(
            "p.json",
            json.dumps(
                [
                    {
                        "language": "es",
                        "category": "forbidden_autonomous",
                        "pattern": "agentes autonomos no estan permitidos",
                        "label": "es-forbid",
                    }
                ]
            ),
        )
        extra = load_patterns(path)
        res = classify(ES_DOC, extra)
        self.assertEqual(res["category"], "forbidden_autonomous")
        self.assertIn("agentes autonomos no estan permitidos", res["evidence"].lower())
        self.assertFalse(res["agent_contributions_allowed"])

    def test_malformed_file_raises_value_error(self):
        for text in (
            "not json",
            "{}",
            '[{"category": "bogus", "pattern": "x"}]',
            '[{"category": "human_in_loop", "pattern": "("}]',
        ):
            with self.assertRaises(ValueError, msg=text):
                load_patterns(self._write("bad.json", text))

    def test_cli_bad_patterns_exit_2(self):
        repo = make_repo(self.tmp)
        bad = self._write("bad.json", "nope")
        self.assertEqual(main(["scan", "--repo", repo, "--patterns", bad]), 2)

    def test_shipped_sets_load_and_classify(self):
        cases = {
            "es": "Los agentes autonomos no estan permitidos en este proyecto.",
            "de": "Autonome Agenten sind in diesem Projekt nicht erlaubt.",
        }
        for name, text in cases.items():
            res = classify(text, load_patterns(name))
            self.assertEqual(res["category"], "forbidden_autonomous", name)

    def test_cli_with_shipped_set(self):
        repo = make_repo(self.tmp)
        with open(os.path.join(repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
            fh.write(ES_DOC)
        self.assertEqual(main(["scan", "--repo", repo, "--fail-if-forbidden", "--quiet"]), 0)
        self.assertEqual(
            main(["scan", "--repo", repo, "--fail-if-forbidden", "--quiet", "--patterns", "es"]), 3
        )


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rc-cli-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan_allowed_repo_exits_zero(self):
        repo = make_repo(self.tmp)
        self.assertEqual(main(["scan", "--repo", repo]), 0)

    def test_fail_if_forbidden_gate_mode(self):
        repo = make_repo(self.tmp, forbidden=True)
        self.assertEqual(main(["scan", "--repo", repo]), 0)
        self.assertEqual(main(["scan", "--repo", repo, "--fail-if-forbidden"]), 3)

    def test_json_output(self):
        repo = make_repo(self.tmp)
        out = os.path.join(self.tmp, "contract.json")
        self.assertEqual(main(["scan", "--repo", repo, "--json-out", out, "--quiet"]), 0)
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["ai_policy"]["category"], "human_in_loop")
        self.assertIn("commands", data)

    def test_markdown_output(self):
        repo = make_repo(self.tmp)
        out = os.path.join(self.tmp, "CONVENTIONS.md")
        self.assertEqual(main(["scan", "--repo", repo, "--markdown-out", out]), 0)
        with open(out, encoding="utf-8") as fh:
            self.assertIn("# Contribution contract", fh.read())

    def test_bad_repo_returns_usage_error(self):
        self.assertEqual(main(["scan", "--repo", os.path.join(self.tmp, "nope")]), 2)


class TestLocalizedSets(unittest.TestCase):
    def _disc(self, name, text):
        return classify(text, load_patterns(name))["requires_disclosure"]

    def test_es_disclosure_moods(self):
        for t in (
            "Divulgue el uso de IA.",
            "Indique si usó inteligencia artificial.",
            "Declare el uso de IA.",
            "Mencione la IA usada.",
            "Divulguen el uso de IA.",
            "Indiquen el uso de IA.",
            "Se indica el uso de IA.",
        ):
            self.assertTrue(self._disc("es", t), t)
        self.assertFalse(self._disc("es", "Declare que es historia."))

    def test_de_disclosure_forms(self):
        for t in (
            "Geben Sie die Nutzung von KI an.",
            "Legen Sie die KI-Nutzung offen.",
            "KI-Nutzung bitte kennzeichnen.",
            "Die Kennzeichnung von KI ist Pflicht.",
            "KI muss angegeben werden.",
        ):
            self.assertTrue(self._disc("de", t), t)

    def test_ai_mention_localized(self):
        self.assertEqual(classify("Usamos IA aqui.")["category"], "unknown")
        for name, t in (
            ("es", "Usamos IA aqui."),
            ("es", "Usamos inteligencia artificial."),
            ("de", "Wir nutzen KI."),
            ("de", "Künstliche Intelligenz hilft."),
        ):
            r = classify(t, load_patterns(name))
            self.assertEqual((r["category"], r["mentions_ai"]), ("ai_mentioned", True), t)
        self.assertFalse(classify("La historia y la dia.", load_patterns("es"))["mentions_ai"])
        self.assertFalse(classify("Ski und Kiwi.", load_patterns("de"))["mentions_ai"])

    def test_dedupe_snippets(self):
        r = classify("Autonomous agents are not allowed. Autonomous agents are not allowed.")
        self.assertEqual(len(r["evidence_snippets"]), len(set(r["evidence_snippets"])))

    def test_shipped_name_beats_local_file(self):
        cwd = os.getcwd()
        tmp = tempfile.mkdtemp(prefix="rc-shadow-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(os.chdir, cwd)
        with open(os.path.join(tmp, "es"), "w") as fh:
            fh.write("not json")
        os.chdir(tmp)
        self.assertTrue(load_patterns("es")["disclosure"])


if __name__ == "__main__":
    unittest.main()
