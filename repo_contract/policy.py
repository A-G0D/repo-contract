"""Classify a repository's AI-contribution policy from its contribution docs.

The categories are deliberately coarse and evidence is always quoted, because the point is to make
the repository's own words visible to the person (or agent) about to contribute:

``forbidden_autonomous``
    The docs say autonomous agents / AI-generated PRs are not allowed. Do not contribute with an
    agent; the tool refuses when asked to enforce this.
``human_in_loop``
    AI use is mentioned together with human responsibility/disclosure requirements.
``ai_mentioned``
    AI is mentioned but no explicit allow/forbid rule was found.
``unknown``
    No AI policy detected at all.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"autonomous agents? (are|is) not allowed",
    r"autonomous agents?[^.]{0,80}(not permitted|prohibited|forbidden)",
    r"not allowed to be used for contributing",
    r"AI-generated (pull requests?|prs?|contributions?) (are|is) "
    r"(not allowed|prohibited|not accepted)",
    r"do not (submit|open|create) (pull requests?|prs?|issues?) (with|using|from) AI",
    r"fully (automated|autonomous) (agents?|contributions?) "
    r"(are|will be) (not )?(accepted|allowed|rejected|closed)",
    r"(no|without) (AI|LLM)[- ](generated|assisted) (contributions?|pull requests?)",
)

HUMAN_IN_LOOP_PATTERNS: tuple[str, ...] = (
    r"human in the loop",
    r"human (review|oversight|responsibility)",
    r"responsible for any (code|change)",
    r"AI[- ]assisted",
    r"should be able to (explain|describe)",
    r"written by humans?",
    r"you must (understand|review)",
)

DISCLOSURE_PATTERNS: tuple[str, ...] = (
    r"disclos",
    r"quote block",
    r"in your own words",
    r"state (that|whether) .{0,40}AI",
    r"mention .{0,40}(AI|LLM)",
)

AI_MENTION = re.compile(r"(?i)\bAI\b|\bLLMs?\b|\blanguage models?\b|ChatGPT|Copilot|Claude")


SNIPPET_MAX = 400
CATEGORIES = ("forbidden_autonomous", "human_in_loop", "disclosure", "ai_mention")


def _matches(text: str, patterns: tuple[str, ...]) -> list[str]:
    """Every non-overlapping match of any pattern, in document order, truncated per snippet."""
    spans = sorted(
        (m.start(), m.end())
        for pattern in patterns
        for m in re.finditer(pattern, text, re.I)
        if m.group(0).strip()
    )
    out: list[str] = []
    last_end = -1
    for start, end in spans:
        if start >= last_end:
            snippet = text[start:end].strip()[:SNIPPET_MAX]
            if snippet not in out:
                out.append(snippet)
            last_end = end
    return out


def load_patterns(source: str) -> dict[str, tuple[str, ...]]:
    """Load extra patterns from a JSON file or a shipped set name (``es``, ``de``).

    The file is a list of ``{language, category, pattern, label}`` objects; ``category`` is one of
    ``forbidden_autonomous``, ``human_in_loop``, ``disclosure``, or ``ai_mention`` (optional: terms
    that count as mentioning AI; matched case-sensitively unless the regex says ``(?i:...)``). Raises ``ValueError`` on bad input.
    """
    # A bare name (no separator, no extension) means a shipped set, even if a local file shares it.
    shipped = os.path.join(os.path.dirname(__file__), "patterns", f"{source}.json")
    bare = not os.path.splitext(source)[1] and os.path.basename(source) == source
    path = shipped if bare and os.path.isfile(shipped) else source
    try:
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh)
    except OSError as exc:
        raise ValueError(f"cannot read patterns file {source!r}: {exc.strerror}") from exc
    except (json.JSONDecodeError, RecursionError) as exc:  # deep nesting overflows the parser
        raise ValueError(f"patterns file {source!r} is not valid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise ValueError(f"patterns file {source!r} must be a JSON list of objects")
    extra: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("category") not in CATEGORIES:
            raise ValueError(
                f"{source!r} entry {i}: category must be one of {', '.join(CATEGORIES)}"
            )
        pattern = entry.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"{source!r} entry {i}: pattern must be a non-empty string")
        try:
            re.compile(pattern)
        except (re.error, RecursionError) as exc:  # deeply nested groups overflow re's compiler
            raise ValueError(f"{source!r} entry {i}: bad regex: {exc}") from exc
        extra[entry["category"]].append(pattern)
    return {c: tuple(v) for c, v in extra.items()}


def classify(text: str, extra: dict[str, tuple[str, ...]] | None = None) -> dict:
    """Classify docs text. ``extra`` adds opt-in patterns (see ``load_patterns``).

    ``evidence`` is the first snippet (0.1.0 contract); ``evidence_snippets`` holds all of them in
    document order and ``evidence_sha256`` their hashes, so reports compare across scans.
    """
    extra = extra or {}
    forbidden = FORBIDDEN_PATTERNS + extra.get("forbidden_autonomous", ())
    human = HUMAN_IN_LOOP_PATTERNS + extra.get("human_in_loop", ())
    disclosure = DISCLOSURE_PATTERNS + extra.get("disclosure", ())
    mentions_ai = bool(AI_MENTION.search(text)) or any(
        re.search(p, text) for p in extra.get("ai_mention", ())
    )
    snippets = _matches(text, forbidden)
    if snippets:
        category = "forbidden_autonomous"
    else:
        snippets = _matches(text, human)
        if snippets:
            category = "human_in_loop"
        elif mentions_ai:
            category = "ai_mentioned"
        else:
            category = "unknown"
    return {
        "category": category,
        "evidence": snippets[0] if snippets else "",
        "evidence_snippets": snippets,
        "evidence_sha256": [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in snippets],
        "requires_disclosure": bool(_matches(text, disclosure)),
        "mentions_ai": mentions_ai,
        "agent_contributions_allowed": category != "forbidden_autonomous",
    }


def policy_sources(docs: dict[str, str]) -> list[str]:
    """Documents that should be inspected for an AI policy."""
    return [
        rel
        for rel, kind in docs.items()
        if kind in ("contributing", "agents", "ai_policy", "pr_template")
    ]
