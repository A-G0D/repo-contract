"""repo-contract CLI: read a repository's contract, optionally enforce its AI policy."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .contract import build_contract, render_markdown

EXIT_FORBIDDEN = 3


def _render_text(contract: dict, *, quiet: bool = False) -> str:
    ai = contract["ai_policy"]
    commands = contract["commands"]
    style = contract["commit_style"]
    pr = contract["pr"]
    lines = [
        f"repo-contract: {contract['name']} ({contract['repo']})",
        f"  AI policy: {ai['category']} — agent contributions: "
        f"{'allowed' if ai['agent_contributions_allowed'] else 'FORBIDDEN'}",
    ]
    if ai["evidence"]:
        lines.append(f"  evidence: {ai['evidence']}")
    if not quiet:
        if contract["policy_sources"]:
            lines.append(f"  policy docs: {', '.join(contract['policy_sources'])}")
        lines.append(
            f"  commands: test={'`' + commands['test'][0] + '`' if commands['test'] else '—'}"
            f" lint={'`' + commands['lint'][0] + '`' if commands['lint'] else '—'}"
            f" build={'`' + commands['build'][0] + '`' if commands['build'] else '—'}"
        )
        lines.append(
            f"  commit style: {style['style']} "
            f"({style['n']} samples, conventional ratio {style['conventional_ratio']})"
        )
        lines.append(
            f"  PR rules: issue={pr['issue_required']} dco={pr['requires_dco_signoff']} "
            f"cla={pr['requires_cla']} changelog={pr['requires_changelog']}"
        )
        if contract["docs"]:
            lines.append("  docs read: " + ", ".join(contract["docs"]))
    else:
        lines = lines[:2]
    return "\n".join(lines)


def cmd_scan(args: argparse.Namespace) -> int:
    try:
        contract = build_contract(args.repo)
    except ValueError as exc:
        print(f"repo-contract: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(contract, indent=2) + "\n", end="")
    elif args.format == "markdown":
        print(render_markdown(contract))
    else:
        print(_render_text(contract, quiet=args.quiet))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(contract, fh, indent=2)
            fh.write("\n")
    if args.markdown_out:
        with open(args.markdown_out, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(contract))

    if not contract["ai_policy"]["agent_contributions_allowed"] and args.fail_if_forbidden:
        print(
            "repo-contract: this repository's contribution docs forbid autonomous agents; "
            "do not submit agent-generated contributions here.",
            file=sys.stderr,
        )
        return EXIT_FORBIDDEN
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-contract",
        description="Read a repository's contribution contract before an agent contributes.",
    )
    parser.add_argument("--version", action="version", version=f"repo-contract {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan a repository's contribution docs and CI")
    scan.add_argument("--repo", default=".", help="repository path (default: current directory)")
    scan.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="output format (default: text)",
    )
    scan.add_argument("--json-out", default=None, help="write the contract as JSON to this file")
    scan.add_argument(
        "--markdown-out", default=None, help="write the contract as Markdown to this file"
    )
    scan.add_argument(
        "--fail-if-forbidden",
        action="store_true",
        help="exit 3 when the repository forbids autonomous agents (CI gate mode)",
    )
    scan.add_argument("--quiet", action="store_true", help="AI-policy verdict only")
    scan.set_defaults(func=cmd_scan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main(os.sys.argv[1:]))
