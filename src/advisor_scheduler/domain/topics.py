"""Closed-set consultation topics and parser."""

from __future__ import annotations

import re
from enum import Enum


class Topic(str, Enum):
    KYC_ONBOARDING = "KYC/Onboarding"
    SIP_MANDATES = "SIP/Mandates"
    STATEMENTS_TAX = "Statements/Tax Docs"
    WITHDRAWALS = "Withdrawals & Timelines"
    ACCOUNT_NOMINEE = "Account Changes/Nominee"


# Prompt order — also used for "1"/"option 2" style answers (voice + UI)
TOPIC_CHOICES: tuple[Topic, ...] = (
    Topic.KYC_ONBOARDING,
    Topic.SIP_MANDATES,
    Topic.STATEMENTS_TAX,
    Topic.WITHDRAWALS,
    Topic.ACCOUNT_NOMINEE,
)

_ALIASES: dict[Topic, tuple[str, ...]] = {
    Topic.KYC_ONBOARDING: (
        "kyc/onboarding",
        "kyc onboarding",
        "know your customer",
        "know your client",
        "kyc",
        "onboarding",
        "casey",  # common STT of "KYC"
    ),
    Topic.SIP_MANDATES: (
        "sip/mandates",
        "sip mandates",
        "systematic investment",
        "sip",
        "mandates",
        "mandate",
    ),
    Topic.STATEMENTS_TAX: (
        "statements/tax docs",
        "statements and tax docs",
        "statement tax docs",
        "statement tax doc",
        "statements tax docs",
        "tax documents",
        "tax docs",
        "tax doc",
        "statements",
        "statement",
        "taxes",
        "tax",
    ),
    Topic.WITHDRAWALS: (
        "withdrawals & timelines",
        "withdrawals and timelines",
        "withdrawal and timelines",
        "withdrawals and time lines",
        "withdrawal timelines",
        "withdrawals",
        "withdrawal",
        "redeem",
        "redemption",
        "timelines",
        "timeline",
    ),
    Topic.ACCOUNT_NOMINEE: (
        "account changes/nominee",
        "account changes nominee",
        "account change nominee",
        "account changes",
        "account change",
        "nominee update",
        "nominee",
        "bank change",
        "demat",
    ),
}

_ORDINAL_WORDS = {
    "one": 1,
    "first": 1,
    "two": 2,
    "second": 2,
    "three": 3,
    "third": 3,
    "four": 4,
    "fourth": 4,
    "five": 5,
    "fifth": 5,
}


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = re.sub(r"[.]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Collapse spelled initials: "k y c" → "kyc", "s i p" → "sip"
    text = re.sub(r"\b([a-z])(?:\s+[a-z]){1,4}\b", lambda m: m.group(0).replace(" ", ""), text)
    return text


def _extract_topic_index(normalized: str) -> int | None:
    """Map '1' / 'option 2' / 'third one' to 1-based index into TOPIC_CHOICES."""
    if normalized in {str(i) for i in range(1, len(TOPIC_CHOICES) + 1)}:
        return int(normalized)

    m = re.search(r"\b(?:option|topic|number|choice|pick|#)\s*([1-5])\b", normalized)
    if m:
        return int(m.group(1))

    m = re.search(r"\b([1-5])(?:st|nd|rd|th)?\b", normalized)
    if m and len(normalized) <= 12:
        return int(m.group(1))

    for word, idx in _ORDINAL_WORDS.items():
        if re.search(rf"\b{word}\b", normalized):
            if idx <= len(TOPIC_CHOICES):
                return idx
    return None


def parse_topic(text: str) -> Topic | None:
    """Map free text to a Topic, or None if not in the closed set."""
    if not text or not text.strip():
        return None

    normalized = _normalize(text)

    # Exact enum label after normalization
    for topic in Topic:
        if normalized == _normalize(topic.value):
            return topic

    # Numbered / ordinal choice matching the spoken prompt order
    index = _extract_topic_index(normalized)
    if index is not None and 1 <= index <= len(TOPIC_CHOICES):
        return TOPIC_CHOICES[index - 1]

    # Prefer longer aliases first to avoid short-token false matches
    scored: list[tuple[int, Topic]] = []
    for topic, aliases in _ALIASES.items():
        for alias in aliases:
            alias_n = _normalize(alias)
            if len(alias_n) < 3:
                continue
            if alias_n == normalized:
                scored.append((len(alias_n) + 10, topic))
            elif re.search(rf"\b{re.escape(alias_n)}\b", normalized):
                scored.append((len(alias_n), topic))
            elif alias_n in normalized:
                scored.append((len(alias_n), topic))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]
