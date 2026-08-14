"""
Memory Policy — M2

Deterministic gate between LLM-extracted fact candidates and Chroma storage.

The LLM extractor produces *candidates* only:
    {"fact": "...", "topic": "...", "importance": 1-5}

This module decides whether each candidate is stored. The LLM has no authority
over storage — it never produces a "store": true field, and even if it did, this
module ignores it.

Three gates are applied in order:
    1. Hard exclusion  — credentials, auth tokens, card numbers, PINs, etc.
                         These are NEVER stored, regardless of importance.
    2. Sensitive info  — health, financial, government IDs.
                         Excluded by default in M2 (conservative baseline).
    3. Importance      — LLM-scored 1-5. Only importance >= 3 is stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Hard-exclusion patterns (regex, case-insensitive)
# Anything matching one of these is NEVER stored in long-term memory.
# ---------------------------------------------------------------------------

_HARD_EXCLUSION_PATTERNS: list[re.Pattern] = [
    # Passwords / passphrases
    re.compile(r"\bpassword\b", re.I),
    re.compile(r"\bpassphrase\b", re.I),
    # API keys / tokens / secrets
    re.compile(r"\bapi[_\s-]?key\b", re.I),
    re.compile(r"\baccess[_\s-]?token\b", re.I),
    re.compile(r"\bauth[_\s-]?token\b", re.I),
    re.compile(r"\bsecret[_\s-]?key\b", re.I),
    re.compile(r"\bprivate[_\s-]?key\b", re.I),
    re.compile(r"\bbearer\b", re.I),
    # PINs and OTPs
    re.compile(r"\bpin\b", re.I),
    re.compile(r"\botp\b", re.I),
    re.compile(r"\bone[_\s-]time[_\s-]password\b", re.I),
    # Card / banking numbers
    re.compile(r"\bcredit[_\s-]?card\b", re.I),
    re.compile(r"\bdebit[_\s-]?card\b", re.I),
    re.compile(r"\bcard[_\s-]?number\b", re.I),
    re.compile(r"\baccount[_\s-]?number\b", re.I),
    re.compile(r"\bcvv\b", re.I),
    re.compile(r"\biban\b", re.I),
    # Cryptographic keys / cookies
    re.compile(r"\bsession[_\s-]?cookie\b", re.I),
    re.compile(r"\bprivate[_\s-]?key\b", re.I),
    re.compile(r"\bcryptographic\b", re.I),
    # Literal patterns for common credential formats
    re.compile(r"sk-[A-Za-z0-9]{20,}"),          # OpenAI-style key
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),          # Groq-style key
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),          # GitHub PAT
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),          # Generic long hex (token-like)
]

# ---------------------------------------------------------------------------
# Sensitive-info patterns — excluded by default in M2 (conservative baseline)
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS: list[re.Pattern] = [
    # Health
    re.compile(r"\bdiagnos\w*\b", re.I),
    re.compile(r"\bmedication\b", re.I),
    re.compile(r"\bprescription\b", re.I),
    re.compile(r"\billness\b", re.I),
    re.compile(r"\bdisease\b", re.I),
    re.compile(r"\bmental health\b", re.I),
    re.compile(r"\btherapist\b", re.I),
    # Financial
    re.compile(r"\bsalary\b", re.I),
    re.compile(r"\bincome\b", re.I),
    re.compile(r"\bnet worth\b", re.I),
    re.compile(r"\btax return\b", re.I),
    re.compile(r"\bsocial security\b", re.I),
    # Government identifiers
    re.compile(r"\bssn\b", re.I),
    re.compile(r"\bsocial security number\b", re.I),
    re.compile(r"\bpassport[_\s-]?number\b", re.I),
    re.compile(r"\bnational[_\s-]?id\b", re.I),
    re.compile(r"\bdriver['\s]?s[_\s-]?licen[sc]e\b", re.I),
]

# Minimum importance score required for storage (1-5 scale from LLM)
_MIN_IMPORTANCE: int = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class PolicyVerdict:
    store: bool
    reason: str   # human-readable, used in logs and tests


def apply_policy(item: dict) -> PolicyVerdict:
    """
    Apply the M2 memory policy to a single extracted fact candidate.

    Args:
        item: dict with keys "fact", "topic", "importance" (all from LLM extractor).
              Any "store" key in item is ignored — the LLM has no authority here.

    Returns:
        PolicyVerdict(store=True/False, reason=str)
    """
    fact = str(item.get("fact", ""))
    topic = str(item.get("topic", ""))
    importance = int(item.get("importance", 0))

    combined = f"{fact} {topic}"

    # Gate 1: Hard exclusion
    for pattern in _HARD_EXCLUSION_PATTERNS:
        if pattern.search(combined):
            return PolicyVerdict(
                store=False,
                reason=f"hard_exclusion: matched pattern {pattern.pattern!r}",
            )

    # Gate 2: Sensitive info (conservative M2 default — exclude)
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(combined):
            return PolicyVerdict(
                store=False,
                reason=f"sensitive_info: matched pattern {pattern.pattern!r}",
            )

    # Gate 3: Importance threshold
    if importance < _MIN_IMPORTANCE:
        return PolicyVerdict(
            store=False,
            reason=f"importance_too_low: {importance} < {_MIN_IMPORTANCE}",
        )

    return PolicyVerdict(store=True, reason="passed_all_gates")
