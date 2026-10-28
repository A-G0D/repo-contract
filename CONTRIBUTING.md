# Contributing to repo-contract

Thanks for considering a contribution. The tool reads other projects' contribution rules, so its own
rules are about evidence and restraint.

## Development setup

```bash
git clone https://github.com/A-G0D/repo-contract.git
cd repo-contract
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

No runtime dependencies are needed, so the environment is quick to build.

## Before you open a PR

Run exactly what CI runs:

```bash
ruff check .
ruff format --check .
python3 -m pytest -q
python3 demo/run_demo.py
```

All four must pass. Paste the commands and results in the PR description. If you change a
classification pattern or an extraction rule, add a test that fails without your change and passes
with it — including a test for the "ambiguous, should not block" case.

## Commit messages

Conventional commits, imperative mood, subject ≤ 72 characters:

```
feat(policy): detect 'AI-generated PRs are not accepted' phrasing
fix(commands): ignore commented-out CI lines
docs(readme): document the --fail-if-forbidden gate
```

One logical change per PR; no reformatting-only PRs.

## What we will not merge

- Broadening `forbidden_autonomous` without explicit prohibition text and tests. False "forbidden"
  verdicts cause contributors to skip repositories that would welcome them.
- Network access, telemetry, or writing into the target repository.
- Runtime dependencies without prior discussion and a changelog entry.
- Tests that depend on network access or on the content of live third-party repositories. Build
  synthetic repositories on disk instead.
- Secret-shaped strings or personal data in the tree or tests (this repository's own CI runs a
  secret scan).

## AI-assisted contributions

AI-assisted contributions are allowed and expected. Please disclose with one line in the PR, be able
to explain every changed line, and include the verification output you actually ran. See
[AGENTS.md](AGENTS.md) for the rules that autonomous agents must follow here.

## Reporting bugs and requesting features

Use the issue templates. Good reports include a minimal repository layout (or the exact document
snippet) and the expected vs. actual classification. Never paste private repository content.

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).
