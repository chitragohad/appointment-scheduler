"""Disclaimer script and acknowledgment detection."""

from __future__ import annotations

import re

_DISCLAIMER = (
    "Before we continue: this assistant is informational only and is not investment advice. "
    "Please reply with \"yes\" or \"I understand\" to acknowledge and proceed."
)

_ACK_PATTERNS = (
    r"^\s*yes\b",
    r"\bi understand\b",
    r"\bi acknowledge\b",
    r"\bagreed?\b",
    r"\bok(ay)?\b",
)


def script() -> str:
    return _DISCLAIMER


def is_ack(text: str) -> bool:
    if not text or not text.strip():
        return False
    lowered = text.strip().lower()
    return any(re.search(pat, lowered) for pat in _ACK_PATTERNS)
