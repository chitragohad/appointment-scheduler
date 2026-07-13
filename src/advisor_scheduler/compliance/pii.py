"""PII firewall — detect and redirect; never store hits."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PiiHit:
    kind: str
    matched: str


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b")),
    ("phone", re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("account", re.compile(r"\b(?:account|a/?c|acct)(?:\s*(?:number|no\.?|#))?\s*[:=]?\s*\d{8,}\b", re.I)),
    ("account", re.compile(r"\b\d{10,18}\b")),  # long digit runs likely account-like
)


def detect(text: str) -> PiiHit | None:
    if not text:
        return None
    for kind, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            # Avoid treating booking codes / short numbers as accounts when clearly NL-
            if kind == "account" and re.search(r"\bNL-[A-Z0-9]{4}\b", text, re.I):
                # If the only long digits are unrelated, still check; skip if match is part of code
                if "NL-" in text.upper() and len(re.findall(r"\d", match.group(0))) <= 4:
                    continue
            return PiiHit(kind=kind, matched=match.group(0))
    return None


def firewall_reply() -> str:
    return (
        "I can’t collect phone numbers, emails, or account details on this chat. "
        "After we reserve a tentative slot, you’ll get a secure link to share contact "
        "details safely offline."
    )
