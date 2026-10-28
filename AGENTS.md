# AGENTS.md — rules for AI agents working in this repository

This file is the contract for autonomous or semi-autonomous coding agents (Claude Code, Codex,
Cursor, OpenHands, custom harnesses, ...) contributing to repo-contract. Humans get the same rules
via [CONTRIBUTING.md](CONTRIBUTING.md). If your harness supports a project instruction file, point it
at this file.

## TL;DR

1. Read `README.md` and this file before editing.
2. Run `ruff check . && ruff format --check . && python3 -m pytest -q && python3 demo/run_demo.py`.
3. **Never weaken the classifier's defaults or a test to make your change pass.** A pattern may be
   refined, but only with tests that show the old behavior was wrong.
4. No private repository content, personal data, credentials, or scraped third-party documents in
   the tree. Test fixtures must be synthetic and minimal.
5. Disclose AI assistance in the PR description; be able to explain every changed line yourself.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## The one command that defines "done"

```bash
ruff check . && ruff format --check . && python3 -m pytest -q && python3 demo/run_demo.py
```

## What you may edit

- `repo_contract/` — document discovery, policy classification, contract building, CLI.
- `tests/` — add coverage for a behavior change. Do not delete, skip, or loosen an existing test to
  make a change pass; if a test encodes the wrong behavior, change the behavior deliberately and say
  so in the PR.
- `README.md` / `CHANGELOG.md` — keep claims honest. Update the changelog for every user-visible
  behavior change.

## What you must not do

- Do not modify `.github/workflows/*` to make CI pass. CI is the oracle; if it is genuinely wrong,
  explain why with evidence in the PR.
- Do not broaden `forbidden_autonomous`: only explicit prohibition text may produce that category.
  Ambiguous AI mentions must degrade to `ai_mentioned`/`unknown`, with a test proving it.
- Do not add runtime dependencies. The zero-dependency property is a feature; discuss first.
- Do not add network access or telemetry. The tool must work offline and read-only.
- Do not use real projects' contribution documents as test fixtures beyond short synthetic
  paraphrases; tests must build their own repositories on disk.
- Do not make the tool trigger side effects in the target repository (no writes, no git mutations
  other than read-only `git log`/`git remote` queries).
- Do not impersonate the maintainer or other contributors.

## Code style

- Python 3.10+, `from __future__ import annotations`, type hints on public functions.
- Ruff with the repository config; format with `ruff format`.
- Policy evidence must be quoted verbatim from the document, truncated if long.
- New category or extraction rule? Update `README.md` and `CHANGELOG.md`, and add tests for the
  positive and negative cases (including the ambiguous case).

## Repository layout

```
repo_contract/    package: docs, policy, contract, cli
tests/            unit + integration tests (pytest / unittest compatible)
demo/             deterministic demo, synthetic repositories only
.github/          CI, CodeQL, Dependabot, issue templates
```

## Reporting

Security-sensitive changes (document discovery boundaries, path handling, command-text mining) must
be called out in the PR. Report actual vulnerabilities privately per [SECURITY.md](SECURITY.md).
