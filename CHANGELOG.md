# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Markdown/JSON config for custom policy patterns and additional document names.
- Optional `--require-clean` check that verifies the repository has a README, CONTRIBUTING and CI
  before an agent is dispatched.
- Language-aware policy detection for non-English contribution docs (currently English-only).
- GitHub Action wrapper that annotates a pull request with the target repository's contract.
- Structured evidence: return all matching policy snippets, not only the first.

## [0.1.0] - 2026-10-28

First public release.

### Added
- `repo-contract scan` command: reads a repository's contribution docs and CI on disk, with text,
  Markdown and JSON output.
- AI-policy classification into `forbidden_autonomous`, `human_in_loop`, `ai_mentioned` and `unknown`,
  always with a quoted evidence snippet; `--fail-if-forbidden` gate mode exits 3 for repositories
  that forbid autonomous agents.
- Contribution document discovery: README, CONTRIBUTING, AGENTS.md, AI policy, code of conduct,
  security, PR/issue templates, changelog, support.
- CI command mining for test/lint/build commands from `.github/workflows/*` and contribution docs
  (raw text, no YAML dependency).
- Commit-style detection (`conventional` / `imperative` / `freeform` / `unknown`) from the last 80
  commit subjects.
- PR-rule detection: issue-before-PR, DCO sign-off, CLA, changelog requirement, PR template sections
  and instructions.
- JSON contract output and Markdown rendering (`CONVENTIONS.md` style).
- Deterministic no-network demo, 17 unit/integration tests, Python 3.10–3.13, zero runtime
  dependencies.
- CI (lint + tests + demo + gitleaks + wheel/console-script smoke), CodeQL, Dependabot.

[Unreleased]: https://github.com/A-G0D/repo-contract/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/A-G0D/repo-contract/releases/tag/v0.1.0
