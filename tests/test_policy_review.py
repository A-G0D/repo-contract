"""A possible AI ban the phrase list cannot confirm is shown for a human check, never enforced."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest

from repo_contract.cli import main
from repo_contract.contract import build_contract, render_markdown
from repo_contract.policy import classify

POSSIBLE_BAN = "AI must not write the code in your patches."


class ReviewSentenceTests(unittest.TestCase):
    def test_possible_ban_is_flagged_but_not_enforced(self):
        ai = classify(POSSIBLE_BAN)
        self.assertNotEqual(ai["category"], "forbidden_autonomous")
        self.assertTrue(ai["agent_contributions_allowed"])
        self.assertEqual(ai["review_sentences"], [POSSIBLE_BAN])

    def test_confirmed_ban_needs_no_review(self):
        ai = classify("No AI-generated contributions. " + POSSIBLE_BAN)
        self.assertEqual(ai["category"], "forbidden_autonomous")
        self.assertEqual(ai["review_sentences"], [])

    def test_plain_refusal_the_phrase_list_misses_is_flagged(self):
        text = "We do not accept AI-generated contributions."
        self.assertEqual(classify(text)["review_sentences"], [text])

    def test_exception_clears_the_flag(self):
        text = "AI must not write patches unless a person checks them."
        self.assertEqual(classify(text)["review_sentences"], [])

    def test_ai_product_topic_is_not_flagged(self):
        text = "We rejected the patch for the AI feature."
        self.assertEqual(classify(text)["review_sentences"], [])

    def test_each_part_of_the_rule_is_required(self):
        for text in (
            "Patches must not touch vendored code.",  # no AI term
            "AI wrote the code in this patch.",  # no refusal
            "AI must not be trusted.",  # no contribution word
        ):
            self.assertEqual(classify(text)["review_sentences"], [], text)

    def test_sentences_are_judged_one_at_a_time(self):
        text = "We like AI.\nPatches must not touch vendored code."
        self.assertEqual(classify(text)["review_sentences"], [])

    def test_lines_without_punctuation_are_separate_sentences(self):
        text = "Our AI tools\nPatches must not touch vendored code"
        self.assertEqual(classify(text)["review_sentences"], [])

    def test_control_characters_are_removed(self):
        text = "AI code is not allowed.\x1b]0;pwned\x07\x1b[2J done"
        [sentence] = classify(text)["review_sentences"]
        self.assertTrue(all(c.isprintable() for c in sentence), repr(sentence))

    def test_no_docs_text(self):
        self.assertEqual(classify("")["review_sentences"], [])


class ReviewOutputTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = tmp.name
        with open(os.path.join(self.repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
            fh.write(POSSIBLE_BAN + "\n")

    def test_markdown_shows_the_sentence(self):
        md = render_markdown(build_contract(self.repo))
        self.assertIn("check by hand", md)
        self.assertIn(POSSIBLE_BAN, md)
        self.assertIn("agent contributions allowed: YES", md)

    def test_markdown_cannot_inject_links_or_html(self):
        with open(os.path.join(self.repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
            fh.write("AI code is not allowed `x` [click](http://evil) <img src=x>\n")
        line = next(
            ln
            for ln in render_markdown(build_contract(self.repo)).splitlines()
            if "check by hand" in ln
        )
        quoted = line.split(": ", 1)[1]
        self.assertTrue(quoted.startswith("`") and quoted.endswith("`"), line)
        self.assertNotIn("`", quoted[1:-1])

    def test_text_output_shows_the_sentence(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["scan", "--repo", self.repo, "--fail-if-forbidden"])
        self.assertEqual(code, 0)  # a flag for a human never fails the gate
        self.assertIn("check by hand", out.getvalue())
        self.assertIn(POSSIBLE_BAN, out.getvalue())

    def test_no_note_without_a_flag(self):
        with open(os.path.join(self.repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
            fh.write("Run the tests first.\n")
        self.assertNotIn("check by hand", render_markdown(build_contract(self.repo)))


if __name__ == "__main__":
    unittest.main()
