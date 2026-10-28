#!/usr/bin/env python3
"""Deterministic demo: no network, temporary repositories only.

Shows the check an agent should run before contributing:

1. a repository whose docs forbid autonomous agents -> gate exits 3;
2. a repository that allows AI-assisted contributions -> contract printed, exit 0.

Run from anywhere: ``python3 demo/run_demo.py``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from repo_contract.cli import main  # noqa: E402

FORBIDDEN_DOC = """# AI Policy

Autonomous agents are not allowed to be used for contributing to this project.
"""

ALLOWED_DOC = """# Contributing

AI-assisted contributions are welcome with disclosure. The human author must review and be
responsible for any code submitted.
Add an entry in CHANGES.md for every change.
"""

WORKFLOW = """name: tests
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: python -m pytest -q
"""


def make_repo(root: str, contributing: str) -> str:
    repo = os.path.join(root, "repo")
    os.makedirs(os.path.join(repo, ".github", "workflows"))
    with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# demo\n")
    with open(os.path.join(repo, "CONTRIBUTING.md"), "w", encoding="utf-8") as fh:
        fh.write(contributing)
    with open(os.path.join(repo, ".github", "workflows", "ci.yml"), "w", encoding="utf-8") as fh:
        fh.write(WORKFLOW)
    with open(os.path.join(repo, "CHANGES.md"), "w", encoding="utf-8") as fh:
        fh.write("# Changes\n")
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
            "docs: initial",
        ],
        cwd=repo,
        check=True,
    )
    return repo


def main_demo() -> int:
    tmp = tempfile.mkdtemp(prefix="repo-contract-demo-")
    failures = 0
    try:
        print("=" * 72)
        print("1) repo whose docs forbid autonomous agents -> expect exit 3")
        print("=" * 72)
        forbidden_repo = make_repo(os.path.join(tmp, "forbidden"), FORBIDDEN_DOC)
        rc = main(["scan", "--repo", forbidden_repo, "--fail-if-forbidden"])
        failures += rc != 3

        print()
        print("=" * 72)
        print("2) repo that allows AI-assisted contributions -> expect exit 0")
        print("=" * 72)
        allowed_repo = make_repo(os.path.join(tmp, "allowed"), ALLOWED_DOC)
        rc = main(["scan", "--repo", allowed_repo])
        failures += rc != 0

        print()
        print("=" * 72)
        if failures:
            print(f"DEMO FAILED: {failures} expectation(s) not met")
            return 1
        print("DEMO OK: forbidden repo was refused, allowed repo compiled a contract")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main_demo())
