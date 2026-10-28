# repo-contract

[![CI](https://github.com/A-G0D/repo-contract/actions/workflows/ci.yml/badge.svg)](https://github.com/A-G0D/repo-contract/actions/workflows/ci.yml)
[![CodeQL](https://github.com/A-G0D/repo-contract/actions/workflows/codeql.yml/badge.svg)](https://github.com/A-G0D/repo-contract/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**Read a repository's contribution contract before an agent contributes.** One command tells you
whether a repository permits autonomous or AI-assisted contributions, which commands its CI runs,
what commit style it expects, and which PR requirements (issue, DCO, CLA, changelog) apply.

```
repo docs + CI ──► policy classifier ──► allowed / human-in-the-loop / forbidden (with evidence)
                └► command miner      ──► test / lint / build commands
                └► style miner        ──► commit style from the last 80 subjects
                └► PR-rule detector   ──► issue / DCO / CLA / changelog / template sections
```

Agentic contributors need to read the instructions before they write. In 2026 that includes a real
question: **does this repository permit autonomous agents at all?** Some projects explicitly forbid
AI-generated contributions; sending an agent there wastes tokens, spams maintainers, and violates the
project's rules. `repo-contract` answers that question from the repository's own words, quotes the
evidence, and can fail a CI/pre-flight step when the answer is "no".

Status: **alpha (0.1.0)**.

## Install

```bash
pip install git+https://github.com/A-G0D/repo-contract.git   # or: pip install -e ".[dev]"
repo-contract --help
```

Python 3.10+. No runtime dependencies; standard library only.

## Quickstart

```bash
# 1. print the contribution contract for a repository
repo-contract scan --repo /path/to/repo

# 2. machine-readable contract
repo-contract scan --repo /path/to/repo --format json > contract.json

# 3. write the contract as a Markdown document (e.g. CONVENTIONS.md)
repo-contract scan --repo /path/to/repo --markdown-out CONVENTIONS.md

# 4. gate mode: exit 3 when the repository forbids autonomous agents
repo-contract scan --repo /path/to/repo --fail-if-forbidden

# 5. deterministic demo
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

Exit codes: **0** scanned (policy allows or is unknown), **2** unreadable repository, **3** policy
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

The finding always quotes the matched text as evidence, because the point is to make the repository's
own wording visible — not to replace reading it. Classification is heuristic: if the evidence line
looks ambiguous, read the linked document.

## What it extracts

- **AI policy** — category, evidence quote, whether disclosure is required, and which docs were read.
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
2. **Zero dependencies, offline.** Standard library only; no network calls.
3. **Read-only.** The tool never writes to the target repository; `--json-out`/`--markdown-out` write
   where you point them, and `--markdown-out CONVENTIONS.md` is an explicit choice made by the user.
4. **Conservative classification.** Only explicit prohibition text produces `forbidden_autonomous`;
   ambiguous mentions degrade to `ai_mentioned`/`unknown` rather than blocking a contribution.
5. **No git history, no problem.** Commit-style mining degrades to `unknown` when `git log` is not
   available (e.g. a source tarball).

## Limitations

- Heuristic, English-language document parsing. A policy written only in an image, a wiki or a
  language other than English will be missed; prefer the repository's own `AGENTS.md`/`AI_POLICY`.
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
