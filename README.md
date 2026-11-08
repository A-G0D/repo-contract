# repo-contract

[![CI](https://github.com/A-G0D/repo-contract/actions/workflows/ci.yml/badge.svg)](https://github.com/A-G0D/repo-contract/actions/workflows/ci.yml)
[![CodeQL](https://github.com/A-G0D/repo-contract/actions/workflows/codeql.yml/badge.svg)](https://github.com/A-G0D/repo-contract/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

Reads a repository's contribution docs and CI config and reports whether it allows AI or
autonomous-agent contributions, which test/lint/build commands it uses, its commit style, and its PR
rules (issue, DCO, CLA, changelog). The AI-policy verdict always quotes the matched text.

Status: alpha (0.1.0). Standard library only, no network access, never writes to the scanned repo.

## Install

```bash
pip install git+https://github.com/A-G0D/repo-contract.git   # or: pip install -e ".[dev]"
repo-contract --help
```

Python 3.10+.

## Quickstart

```bash
# 1. print the contribution contract for a repository
repo-contract scan --repo /path/to/repo

# 2. machine-readable contract (`--format markdown` prints Markdown to stdout instead)
repo-contract scan --repo /path/to/repo --format json > contract.json

# 3. write the contract as a Markdown document (e.g. CONVENTIONS.md)
repo-contract scan --repo /path/to/repo --markdown-out CONVENTIONS.md

# 4. gate mode: exit 3 when the repository forbids autonomous agents
repo-contract scan --repo /path/to/repo --fail-if-forbidden

# 5. also match Spanish wording (use `de` for German, or a JSON file; see "Other languages")
repo-contract scan --repo /path/to/repo --patterns es

# 6. demo
python3 demo/run_demo.py
```

Example output:

```
repo-contract: click (/repos/click)
  AI policy: unknown — agent contributions: allowed
  commands: test=`python -m pytest -q` lint=`ruff check .` build=—
  commit style: imperative (80 samples, conventional ratio 0.0)
  PR rules: issue=True dco=False cla=False changelog=True
  docs read: CONTRIBUTING.rst, README.rst, .github/pull_request_template.md
```

Exit codes: **0** scanned (policy allows or is unknown), **2** the `--repo` path is not a directory, a
`--patterns` file is invalid, or a `--json-out`/`--markdown-out` file cannot be written, **3** policy
forbids autonomous agents (only with `--fail-if-forbidden`).

## The AI-policy gate

The classifier reads `CONTRIBUTING`, `AGENTS.md`, `AI_POLICY*`, PR templates and similar docs, then
returns one of:

| category | meaning | agent contribution |
|---|---|---|
| `forbidden_autonomous` | docs forbid autonomous agents / AI-generated PRs | **refuse** |
| `human_in_loop` | AI use allowed with human review/disclosure requirements | allowed, disclose + review |
| `ai_mentioned` | AI is mentioned, no explicit allow/forbid rule found | allowed, ask maintainers if unsure |
| `unknown` | no AI policy found | allowed |

The matched text is quoted as evidence. Classification is regex matching: if a quote looks
ambiguous, read the document it came from.

`ai_policy` in the JSON report:

```json
{
  "category": "forbidden_autonomous",
  "evidence": "Autonomous agents are not allowed",
  "evidence_snippets": ["Autonomous agents are not allowed", "AI-generated pull requests are not accepted"],
  "evidence_sha256": ["<sha256 of each snippet>", "..."],
  "requires_disclosure": false,
  "mentions_ai": true,
  "agent_contributions_allowed": false
}
```

`evidence_snippets` holds every match of the winning category across all docs, in document order, each
cut at 400 characters; `evidence` is the first one (the only field in 0.1.0). Text output shows the
first snippet and `(+N more, see --format json)`.

### Other languages

The built-in patterns are English. Add more with `--patterns`, which takes a JSON file or the name of
a shipped set (`es`, `de`). A bare name that matches a shipped set always means that set, even if a
local file has that name; use `./es` for the file. Any other bare name is read as a local file.
Patterns are added to the English ones, not swapped in.

```json
[
  {"language": "fr", "category": "forbidden_autonomous", "label": "fr-agents",
   "pattern": "agents autonomes[^.]{0,60}(interdits|pas autoris[ée]s)"}
]
```

`category` is `forbidden_autonomous`, `human_in_loop` or `disclosure`, or the optional
`ai_mention` (terms that count as mentioning AI, e.g. `\\bIA\\b`; case-sensitive unless the regex
uses `(?i:...)`); `pattern` is a Python regex
matched case-insensitively; `language` and `label` are for humans. A malformed file exits with 2.
The shipped sets are small phrase lists tested on synthetic sentences only. They are not full
language support, and wording they do not cover is reported as `unknown`.

## What it extracts

- **AI policy** — category, evidence quotes, whether disclosure is required, and which docs were read.
- **Commands** — test / lint / build commands mined from `.github/workflows/*` and contribution docs
  (raw YAML text, no YAML parser needed).
- **Commit style** — `conventional`, `imperative`, `freeform` or `unknown`, with sample subjects and
  ratios from the last 80 commits (requires `git`; absent history reports `unknown`).
- **PR rules** — issue-before-PR, DCO sign-off, CLA requirement, changelog requirement, PR-template
  sections and instructions.
- **Changelog files** — which files the project expects a changelog entry in.

## Use it before an agent contributes

```bash
repo-contract scan --repo "$REPO" --fail-if-forbidden --quiet \
  || { echo "this repo forbids autonomous agents; stopping"; exit 0; }
```

Or in a pre-flight script:

```python
from repo_contract.contract import build_contract

contract = build_contract("/path/to/repo")
if not contract["ai_policy"]["agent_contributions_allowed"]:
    raise SystemExit("repo forbids autonomous agents")
test_cmd = (contract["commands"]["test"] or [None])[0]
print(contract["ai_policy"]["evidence"])
```

In CI (for a repository that accepts agent PRs), a guard job can check that the target repo has no
forbidding policy before an agent is dispatched:

```yaml
- run: pip install git+https://github.com/A-G0D/repo-contract.git
- run: repo-contract scan --repo . --fail-if-forbidden --quiet
```

## Design rules

1. **Quote, don't paraphrase.** Every policy verdict carries the matched evidence text.
2. **Offline.** No network calls.
3. **Read-only.** Nothing is written to the scanned repository; `--json-out` and `--markdown-out`
   write only where you point them.
4. **Conservative classification.** Only explicit prohibition text produces `forbidden_autonomous`;
   ambiguous mentions degrade to `ai_mentioned`/`unknown` rather than blocking a contribution.
5. **No git history, no problem.** Commit-style mining degrades to `unknown` when `git log` is not
   available (e.g. a source tarball).

## Limitations

- Regex matching on English text by default; `--patterns es` or `de` adds Spanish or German, and a JSON file adds your own phrases
  (see above). A policy in an image, a wiki or any other language is missed.
- PR-template sections are heading lines; unusual templates may yield few sections.
- Commands are mined as text, not validated. Always run the repository's documented command yourself;
  `repo-contract` shows what the project says, it does not execute it.
- Commit-style detection needs at least a few commits and is a heuristic, not a lint.
- The Python API (`build_contract`) is for tests/integrations; pin a version if you depend on it.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). AI-assisted contributions are welcome with disclosure;
[AGENTS.md](AGENTS.md) defines the rules for autonomous agents in this repository. Security issues:
[SECURITY.md](SECURITY.md). Community expectations: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) © 2026 A-G0D.
