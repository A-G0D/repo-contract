"""Build a repository's contribution contract: AI policy, commands, style, PR rules.

Zero third-party dependencies: CI workflow commands are mined from the raw YAML text rather than
parsed, which is enough to find ``run:`` commands and keeps this tool dependency-free.
"""

from __future__ import annotations

import os
import re
import subprocess

from .docs import docs_text, find_docs, read_text, walk_files
from .policy import classify, policy_sources

CMD_START = (
    "pytest",
    "uv",
    "tox",
    "nox",
    "hatch",
    "pre-commit",
    "ruff",
    "black",
    "flake8",
    "mypy",
    "pyright",
    "npm",
    "pnpm",
    "yarn",
    "node",
    "jest",
    "vitest",
    "eslint",
    "prettier",
    "tsc",
    "cargo",
    "clippy",
    "rustfmt",
    "go",
    "make",
    "python",
    "python3",
    "poetry",
    "pipenv",
)
CMD_TOKENS = (
    "pytest",
    "tox",
    "nox",
    "hatch",
    "pre-commit",
    "ruff",
    "black",
    "flake8",
    "mypy",
    "pyright",
    "npm",
    "pnpm",
    "yarn",
    "node",
    "jest",
    "vitest",
    "eslint",
    "prettier",
    "tsc",
    "cargo",
    "clippy",
    "rustfmt",
    "go test",
    "go vet",
    "go build",
    "make",
    "python -m unittest",
    "python -m pytest",
)
TEST_HINT = r"(test|pytest|tox|nox|jest|vitest|cargo test|go test|unittest)"
LINT_HINT = (
    r"(lint|ruff|black|flake8|eslint|prettier|clippy|mypy|pyright|rustfmt|go vet|pre-commit)"
)
BUILD_HINT = r"(build|tsc|cargo build|go build|compile)"

CONVENTIONAL = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?:\s", re.I
)
IMPERATIVE = re.compile(r"^[A-Z][a-z]+(\s|$)")
ISSUE_REQUIRED = re.compile(
    r"(?i)(before opening a (pr|pull request)[^.]*(ticket|issue)|"
    r"open (a|an) (ticket|issue)|file (a|an) issue|create (a|an) issue)"
)
DCO = re.compile(r"(?i)signed-off-by|DCO\b|developer certificate")
CLA = re.compile(r"(?i)\bCLA\b|contributor license agreement")
CHANGELOG = re.compile(r"(?i)changelog|CHANGES\.[a-z]+|release notes")


def _command_candidates(text: str) -> list[str]:
    """Lines that look like runnable commands, from raw YAML/docs text."""
    candidates: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "${{" in stripped or "$(" in stripped or stripped.endswith("\\"):
            continue
        line = re.sub(r"^-\s*", "", stripped)
        line = re.sub(r"^(?:run|command|script):\s*", "", line)
        line = line.strip()
        if not line or len(line) > 200:
            continue
        first = line.split()[0]
        if first not in CMD_START:
            continue
        if not any(token in line.lower() for token in CMD_TOKENS):
            continue
        candidates.append(line)
    return candidates


def extract_commands(root: str, docs_txt: str) -> dict[str, list[str]]:
    """Collect test/lint/build commands from CI workflows first, then contribution docs."""
    candidates: list[str] = []
    for rel in workflow_files(root):
        candidates.extend(_command_candidates(read_text(root, rel)))
    candidates.extend(_command_candidates(docs_txt))

    def pick(hint: str) -> list[str]:
        seen: set[str] = set()
        picked: list[str] = []
        for command in candidates:
            if re.search(hint, command, re.I) and command not in seen:
                seen.add(command)
                picked.append(command)
        return picked[:5]

    return {"test": pick(TEST_HINT), "lint": pick(LINT_HINT), "build": pick(BUILD_HINT)}


def workflow_files(root: str) -> list[str]:
    """CI workflow files, relative to the repository root."""
    files = []
    for rel in walk_files(root):
        lowered = rel.lower()
        if lowered.startswith(".github/workflows/") and lowered.endswith((".yml", ".yaml")):
            files.append(rel)
        elif lowered in (".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml"):
            files.append(rel)
    return files


def detect_commit_style(repo: str) -> dict:
    """Mine the last 80 commit subjects for conventional/imperative style."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo, "log", "--format=%s", "-80"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "style": "unknown",
            "samples": [],
            "n": 0,
            "conventional_ratio": None,
            "avg_length": 0.0,
        }
    messages = [line for line in proc.stdout.splitlines() if line.strip()]
    if not messages or proc.returncode != 0:
        return {
            "style": "unknown",
            "samples": [],
            "n": 0,
            "conventional_ratio": None,
            "avg_length": 0.0,
        }
    conventional = sum(1 for m in messages if CONVENTIONAL.match(m))
    imperative = sum(1 for m in messages if IMPERATIVE.match(m))
    if conventional / len(messages) >= 0.6:
        style = "conventional"
    elif imperative / len(messages) >= 0.6:
        style = "imperative"
    else:
        style = "freeform"
    return {
        "style": style,
        "samples": messages[:8],
        "n": len(messages),
        "conventional_ratio": round(conventional / len(messages), 2),
        "avg_length": round(sum(len(m) for m in messages) / len(messages), 1),
    }


def detect_pr_rules(root: str, docs: dict[str, str], docs_txt: str) -> dict:
    """Contribution requirements: issue, DCO, CLA, changelog, PR template sections."""
    template = ""
    for rel, kind in docs.items():
        if kind == "pr_template":
            template = read_text(root, rel)
            break
    sections: list[str] = []
    instructions: list[str] = []
    for line in template.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            sections.append(stripped.lstrip("# ").strip())
        elif stripped and "<!--" not in stripped and "-->" not in stripped:
            instructions.append(stripped)
    return {
        "issue_required": bool(ISSUE_REQUIRED.search(docs_txt)),
        "requires_dco_signoff": bool(DCO.search(docs_txt)),
        "requires_cla": bool(CLA.search(docs_txt)),
        "requires_changelog": bool(CHANGELOG.search(docs_txt)),
        "template_sections": sections[:12],
        "template_instructions": [x for x in instructions if len(x) > 15][:15],
    }


def detect_remote(repo: str) -> str:
    """Origin remote URL, or an empty string when there is none."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def build_contract(repo: str) -> dict:
    """Build the full contract for a repository path."""
    repo = os.path.abspath(repo)
    if not os.path.isdir(repo):
        raise ValueError(f"not a directory: {repo}")
    docs = find_docs(repo)
    docs_txt = docs_text(repo, docs)
    ai_policy = classify(docs_txt)
    return {
        "repo": repo,
        "name": os.path.basename(repo.rstrip(os.sep)) or repo,
        "remote": detect_remote(repo),
        "docs": docs,
        "ai_policy": ai_policy,
        "policy_sources": policy_sources(docs),
        "workflows": workflow_files(repo),
        "commands": extract_commands(repo, docs_txt),
        "commit_style": detect_commit_style(repo),
        "pr": detect_pr_rules(repo, docs, docs_txt),
        "changelog_files": [rel for rel, kind in docs.items() if kind == "changelog"],
        "generated_by": "repo-contract",
    }


def render_markdown(contract: dict) -> str:
    """Render the contract as a reviewable Markdown document."""
    ai = contract["ai_policy"]
    lines = [
        f"# Contribution contract: {contract['name']}",
        "",
        f"- repository: `{contract['repo']}`",
        f"- remote: `{contract['remote'] or '(none)'}'",
        f"- **agent contributions allowed: "
        f"{'YES' if ai['agent_contributions_allowed'] else 'NO'}** "
        f"(AI policy: `{ai['category']}`)",
        f"- AI policy evidence: {ai['evidence'] or '(none found)'}",
        f"- disclosure required: {ai['requires_disclosure']}",
        "",
        "## Commands",
        "",
    ]
    for kind in ("test", "lint", "build"):
        commands = contract["commands"][kind]
        lines.append(f"- {kind}: " + (", ".join(f"`{c}`" for c in commands) or "—"))
    style = contract["commit_style"]
    lines += [
        "",
        "## Commit style",
        "",
        f"- style: `{style['style']}` (samples: {style['n']}, "
        f"conventional ratio: {style['conventional_ratio']})",
        "",
        "## Pull-request rules",
        "",
        f"- issue required before PR: {contract['pr']['issue_required']}",
        f"- DCO sign-off required: {contract['pr']['requires_dco_signoff']}",
        f"- CLA required: {contract['pr']['requires_cla']}",
        f"- changelog entry required: {contract['pr']['requires_changelog']}",
    ]
    if contract["pr"]["template_sections"]:
        lines.append(f"- PR template sections: {', '.join(contract['pr']['template_sections'])}")
    lines += ["", "## Documents read", ""]
    lines += [f"- `{rel}` ({kind})" for rel, kind in contract["docs"].items()]
    return "\n".join(lines) + "\n"
