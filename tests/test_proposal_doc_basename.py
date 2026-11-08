import os
import tempfile
import unittest

from repo_contract import docs
from repo_contract.docs import find_docs


def _touch(root, rel):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("x\n")


class ProposalDocBasenameTests(unittest.TestCase):
    def test_module_imported_from_worktree(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertTrue(os.path.abspath(docs.__file__).startswith(here))

    def test_non_doc_files_in_doc_named_dirs_are_not_docs(self):
        with tempfile.TemporaryDirectory() as root:
            _touch(root, "readme-assets/logo.png")
            _touch(root, "contributing/diagram.svg")
            _touch(root, "security/scan.py")
            self.assertEqual(find_docs(root), {})

    def test_root_and_github_docs_still_found(self):
        with tempfile.TemporaryDirectory() as root:
            _touch(root, "README.md")
            _touch(root, "CONTRIBUTING.md")
            _touch(root, ".github/CONTRIBUTING.md")
            _touch(root, "SECURITY.md")
            _touch(root, ".github/ISSUE_TEMPLATE/bug_report.md")
            found = find_docs(root)
            self.assertEqual(found.get("README.md"), "readme")
            self.assertEqual(found.get("CONTRIBUTING.md"), "contributing")
            self.assertEqual(found.get(".github/CONTRIBUTING.md"), "contributing")
            self.assertEqual(found.get("SECURITY.md"), "security")
            self.assertIn(".github/ISSUE_TEMPLATE/bug_report.md", found)

    def test_pr_template_dir_file_is_pr_template(self):
        with tempfile.TemporaryDirectory() as root:
            _touch(root, ".github/PULL_REQUEST_TEMPLATE/feature.md")
            found = find_docs(root)
            self.assertEqual(found.get(".github/PULL_REQUEST_TEMPLATE/feature.md"), "pr_template")


if __name__ == "__main__":
    unittest.main()
