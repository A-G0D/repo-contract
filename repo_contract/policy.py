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


def _first_match(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0).strip()[:400]
    return ""


def classify(text: str) -> dict:
    """Return ``{category, evidence, requires_disclosure, mentions_ai}`` for the given docs text."""
    evidence = _first_match(text, FORBIDDEN_PATTERNS)
    if evidence:
        category = "forbidden_autonomous"
    else:
        evidence = _first_match(text, HUMAN_IN_LOOP_PATTERNS)
        if evidence:
            category = "human_in_loop"
        elif AI_MENTION.search(text):
            category = "ai_mentioned"
        else:
            category = "unknown"
    return {
        "category": category,
        "evidence": evidence,
        "requires_disclosure": bool(_first_match(text, DISCLOSURE_PATTERNS)),
        "mentions_ai": bool(AI_MENTION.search(text)),
        "agent_contributions_allowed": category != "forbidden_autonomous",
    }


def policy_sources(docs: dict[str, str]) -> list[str]:
    """Documents that should be inspected for an AI policy."""
    return [
        rel
        for rel, kind in docs.items()
        if kind in ("contributing", "agents", "ai_policy", "pr_template")
    ]
