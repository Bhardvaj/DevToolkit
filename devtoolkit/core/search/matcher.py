"""High-performance acronym and fuzzy string matcher inspired by Flow Launcher and PowerToys.

Provides sub-millisecond acronym extraction, continuous substring scoring,
and word-boundary bonuses for instant workstation search.
"""

from __future__ import annotations

import re
from functools import lru_cache
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
def score_match(query: str, target: str, acronym: Optional[str] = None) -> int:
    """Score the match quality between query and target string.

    Returns:
        int: Match score from 0 (no match) to 1000+ (exact match).
    """
    if not query or not target:
        return 0

    q = query.strip().lower()
    t = target.strip().lower()

    if not q or not t:
        return 0

    # 1. Exact match
    if q == t:
        return 1000

    # 2. Acronym match (Ultra-high priority for short queries)
    if not acronym:
        acronym = extract_acronym(target)
    acr = acronym.lower()

    if acr:
        if q == acr:
            # Exact acronym match: e.g. "vsc" == "vsc"
            return 800
        if acr.startswith(q) and len(q) >= 2:
            # Acronym prefix match: e.g. "vs" matches prefix of "vsc"
            return 650

    # 3. Exact prefix match on target
    if t.startswith(q):
        return 500 + max(0, 100 - len(t))

    # 4. Word boundary prefix match
    # e.g. query "code" matches "Visual Studio [Code]"
    words = re.split(r"[\s\-_.]+", t)
    for word in words:
        if word == q:
            return 450
        if word.startswith(q):
            return 350

    # 5. Continuous Substring match
    idx = t.find(q)
    if idx != -1:
        # Penalize match further down the string
        position_penalty = min(idx * 5, 100)
        return 300 - position_penalty

    # 6. Sequential fuzzy match (all query characters appear in order)
    q_len = len(q)
    t_len = len(t)
    if q_len > t_len:
        return 0

    q_idx = 0
    consecutive_run = 0
    score = 0

    for i, ch in enumerate(t):
        if q_idx < q_len and ch == q[q_idx]:
            q_idx += 1
            consecutive_run += 1
            score += 10 + (consecutive_run * 5)
            # Bonus for word boundary
            if i == 0 or t[i - 1] in " -_./\\":
                score += 20
        else:
            consecutive_run = 0

    if q_idx == q_len:
        # Full subsequence matched
        # Scale score relative to string length to favor tighter matches
        coverage = q_len / t_len
        return int(score * coverage)

    return 0

