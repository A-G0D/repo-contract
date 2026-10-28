"""Discover and read the documents that define a repository's contribution contract."""

from __future__ import annotations

import os
import re

DOC_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?i)readme", "readme"),
    (r"(?i)contributing", "contributing"),
    (r"(?i)^agents\.md$", "agents"),
    (r"(?i)^ai[_-]?policy", "ai_policy"),
    (r"(?i)code_of_conduct", "code_of_conduct"),
    (r"(?i)^security", "security"),
    (r"(?i)pull_request_template", "pr_template"),
    (r"(?i)issue_template", "issue_template"),
    (r"(?i)^changelog|^changes", "changelog"),
    (r"(?i)^support", "support"),
)

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "target",
    "dist",
    "build",
    ".next",
    ".cache",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
}

MAX_SCAN_FILES = 5000


def walk_files(root: str) -> list[str]:
    """Relative paths of repository files, skipping build/VCS directories."""
    found: list[str] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            found.append(os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
            if len(found) >= MAX_SCAN_FILES:
                return found
    return found


def find_docs(root: str) -> dict[str, str]:
    """Map a document path to its kind (``contributing``, ``agents``, ...).

    Both ``CONTRIBUTING.md`` at the root and ``.github/CONTRIBUTING.md`` count; the first match
    per kind wins, except that readme/contributing prefer the shallowest path.
    """
    docs: dict[str, str] = {}
    for rel in walk_files(root):
        base = os.path.basename(rel)
        for pattern, kind in DOC_PATTERNS:
            if not (re.search(pattern, base) or re.search(pattern, rel)):
                continue
            if kind in docs:
                continue
            docs[rel] = kind
            break
    return docs


def read_text(root: str, rel: str, limit: int = 60_000) -> str:
    """Read a document, returning an empty string when it is unreadable or binary."""
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def docs_text(root: str, docs: dict[str, str], limit: int = 80_000) -> str:
    """Concatenate contribution docs (not readmes) for rule mining."""
    parts = []
    for rel, kind in docs.items():
        if kind in ("readme", "code_of_conduct", "issue_template"):
            continue
        parts.append(f"## {rel}\n" + read_text(root, rel))
    return "\n\n".join(parts)[:limit]
