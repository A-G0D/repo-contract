# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |
| < 0.1 | not released |

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private vulnerability
reporting on this repository:

1. Go to <https://github.com/A-G0D/repo-contract/security/advisories/new>.
2. Describe the issue, the affected version/commit, and a minimal reproduction.

If private reporting is unavailable to you, open a normal issue that says only
"security report — please contact me for details" without exploit details.

## Threat model

`repo-contract` is a **read-only analyzer**:

- It walks files under the repository path you give it, reads text documents, and runs read-only
  `git log` / `git remote get-url` queries. It never writes to the target repository, never stages or
  commits, and never executes repository code.
- It makes no network calls.
- It has no runtime dependencies, so there is no supply-chain surface beyond the standard library.
- Output files (`--json-out`, `--markdown-out`) are written only where the user points them.

## What is in scope

- Path traversal or symlink escapes in document discovery that cause files **outside** the target
  repository to be read and emitted (for example in `--format json` output).
- Command or path injection through CLI arguments or document content. (Note: document content is
  only ever treated as text; it is never executed.)
- A crash, hang, or unbounded memory use from a malicious document or directory tree (for example a
  very deep tree, a huge file, or catastrophic regex backtracking).
- Misclassification that marks a repository **allowed** when its docs explicitly forbid autonomous
  agents (a safety bypass), or that leaks document content beyond the quoted evidence field.
- Any way to make the tool mutate the target repository.

## Out of scope

- Misclassification of ambiguous prose as `ai_mentioned`/`unknown` instead of `forbidden_autonomous`.
  The classifier is documented as English-language and heuristic; open an issue with the snippet.
- Content of documents the user asked the tool to read being present in output (that is the tool's
  purpose; evidence is quoted and truncated).
- Vulnerabilities in `git` itself.

## Release hygiene

The repository is protected by its own CI: lint, tests on Python 3.10–3.13, a deterministic demo, a
gitleaks secret scan, CodeQL, and a wheel/console-script install check. Dependabot security updates
and private vulnerability reporting are enabled for the repository.
