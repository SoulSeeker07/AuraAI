"""
Browser High-Risk Action & Redaction Patterns
Location: src/browser/patterns.py

Single source of truth for high-risk web interaction patterns across:
1. SafetyGate DOM element inspection
2. Universal ExecutionPolicy / classify_action_risk
3. Audit logger credential redaction
"""

from __future__ import annotations

import re
from typing import Any, Dict

# High-risk click actions requiring human confirmation (e.g. irreversible purchases, mutations)
HIGH_RISK_CLICK_PATTERNS = [
    r"\b(?:place\s+order|buy\s+now|pay\s+now|complete\s+order|submit\s+payment|checkout)\b",
    r"\b(?:confirm\s+purchase|purchase|pay\s+with|transfer\s+money|send\s+payment)\b",
    r"\b(?:delete\s+account|terminate\s+account|cancel\s+subscription)\b",
]

# High-risk input fields requiring confirmation (e.g. credentials, payment details)
HIGH_RISK_TYPE_PATTERNS = [
    r"\b(?:password|cvv|cvc|card\s*number|credit\s*card|debit\s*card|security\s*code|ssn|pin)\b",
    r"\b(?:2fa|otp|one\s*time\s*password|authenticator\s*code)\b",
]

_CLICK_RE = re.compile("|".join(HIGH_RISK_CLICK_PATTERNS), re.IGNORECASE)
_TYPE_RE = re.compile("|".join(HIGH_RISK_TYPE_PATTERNS), re.IGNORECASE)


def is_high_risk_click(description: str) -> bool:
    """Check if a click target description matches high-risk purchasing or destructive actions."""
    if not description:
        return False
    return bool(_CLICK_RE.search(description))


def is_high_risk_type(description: str) -> bool:
    """Check if an input target description matches sensitive credential or financial fields."""
    if not description:
        return False
    return bool(_TYPE_RE.search(description))


def sanitize_browser_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize browser tool arguments before persisting to tickets or writing to audit logs.
    Redacts cleartext passwords and financial numbers while preserving descriptive context.
    """
    sanitized = dict(args)
    if tool_name in ("type_text", "type"):
        desc = sanitized.get("description", "")
        if is_high_risk_type(desc) and "text" in sanitized:
            sanitized["text"] = "[REDACTED_SECRET]"
    return sanitized
