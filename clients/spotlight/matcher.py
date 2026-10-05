"""High-performance acronym and fuzzy string matcher for DevToolkit Spotlight.

Directly adapted from Flow Launcher and PowerToys Run algorithms.
Sub-millisecond acronym extraction, continuous substring scoring,
and word-boundary bonuses for instant workstation search.
"""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Optional, Tuple


def extract_acronym(text: str) -> str:
    """Extract acronym initials from text based on capitals, word boundaries, and numbers.

    Examples:
        'Visual Studio Code' -> 'vsc'
        'Windows Terminal' -> 'wt'
        'Google Chrome' -> 'gc'
        'PowerShell 7' -> 'ps7'
        'DevToolkit' -> 'dt'
        'command-prompt' -> 'cp'
    """
    if not text:
        return ""

    # Clean extension if present (e.g. .exe, .lnk)
    if "." in text:
        text = text.rsplit(".", 1)[0]

    # Split by spaces, hyphens, underscores
    tokens = re.split(r"[\s\-_]+", text.strip())
    acronym_chars: list[str] = []

    for token in tokens:
        if not token:
            continue
        # Check for CamelCase words inside token (e.g. DevToolkit -> D, T)
        camel_parts = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", token)
        if len(camel_parts) > 1:
            for part in camel_parts:
                if part:
                    acronym_chars.append(part[0].lower())
        else:
            acronym_chars.append(token[0].lower())
            # Also capture trailing digits if any (e.g. Python 3.12 -> p, 3)
            digits = re.findall(r"\d+", token[1:])
            for d in digits:
                acronym_chars.append(d)

    return "".join(acronym_chars)


@lru_cache(maxsize=4096)
def _score_acronym(query_low: str, acronym: str) -> int:
    """Score query against pre-computed acronym initials."""
    if not acronym or not query_low:
        return 0

    # Exact acronym match gets highest priority score (Flow Launcher style)
    if query_low == acronym:
        return 200

    # Prefix acronym match (e.g. 'vs' matching 'vsc')
    if acronym.startswith(query_low):
        return 160 + (len(query_low) * 5)

    # Subsequence match within acronym
    it = iter(acronym)
    if all(char in it for char in query_low):
        return 120 + len(query_low)

    return 0


def score_match(query: str, target: str, acronym: Optional[str] = None) -> int:
    """Compute matching score (0 to 250) between query and target name.

    Returns:
        0 if no match; higher score represents stronger relevance.
    """
    if not query or not target:
        return 0

    q_low = query.lower().strip()
    t_low = target.lower()

    # 1. Exact match bonus
    if q_low == t_low:
        return 250

    # 2. Flow Launcher Acronym matching
    acr = acronym if acronym is not None else extract_acronym(target)
    acr_score = _score_acronym(q_low, acr)
    if acr_score > 0:
        return acr_score

    # 3. Exact Prefix match
    if t_low.startswith(q_low):
        # Shorter targets get higher priority for the same prefix
        length_penalty = min(20, len(t_low) - len(q_low))
        return 150 - length_penalty

    # 4. Word-boundary substring match
    pattern = rf"(^|[\s\-_.]){re.escape(q_low)}"
    if re.search(pattern, t_low):
        return 110

    # 5. Continuous Substring match
    idx = t_low.find(q_low)
    if idx != -1:
        # Closer to start of string gets higher score
        pos_bonus = max(0, 30 - idx)
        return 70 + pos_bonus

    # 6. Fuzzy character subsequence
    it = iter(t_low)
    if all(char in it for char in q_low):
        return 40

    return 0

