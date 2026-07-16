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
        "casey",
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

# Spoken number words + common speech-to-text mishears
_ORDINAL_WORDS = {
    "one": 1,
    "first": 1,
    "won": 1,  # STT: "one"
    "two": 2,
    "second": 2,
    "to": 2,  # only used when utterance is short / clearly a choice
    "too": 2,
    "three": 3,
    "third": 3,
    "tree": 3,  # STT: "three"
    "four": 4,
    "fourth": 4,
    "for": 4,  # STT: "four" — only when short/clear choice
    "five": 5,
    "fifth": 5,
}

_AMBIGUOUS_STT = {"to", "too", "for", "won", "tree"}


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


def _looks_like_prompt_echo(normalized: str) -> bool:
    """Detect when STT captured the agent reading the topic list."""
    hits = 0
    for token in ("kyc", "sip", "statements", "withdrawals", "nominee", "onboarding", "mandates"):
        if re.search(rf"\b{token}\b", normalized):
            hits += 1
    return hits >= 3 or "consultation topic" in normalized or "fits best" in normalized


def _extract_topic_index(normalized: str) -> int | None:
    """Map '1' / 'option 2' / 'I want three' to 1-based index into TOPIC_CHOICES."""
    if not normalized:
        return None

    # Bare number
    if normalized in {str(i) for i in range(1, len(TOPIC_CHOICES) + 1)}:
        return int(normalized)

    # "option 1", "number 2", "topic 3", "choice 4", "pick 5", "#1"
    m = re.search(r"\b(?:option|topic|number|choice|pick|select|go with|#)\s*([1-5])\b", normalized)
    if m:
        return int(m.group(1))

    # "option one", "number two"
    m = re.search(
        r"\b(?:option|topic|number|choice|pick|select|go with)\s+"
        r"(one|two|three|four|five|first|second|third|fourth|fifth|won|tree)\b",
        normalized,
    )
    if m:
        return _ORDINAL_WORDS.get(m.group(1))

    # "I want 3" / "take 2" / "say 1" / "I'll go with 4"
    m = re.search(
        r"\b(?:want|take|say|choose|pick|select|need|prefer|go with|do)\s+"
        r"(?:option\s+|number\s+|topic\s+)?"
        r"([1-5]|one|two|three|four|five|first|second|third|fourth|fifth|won|tree)\b",
        normalized,
    )
    if m:
        token = m.group(1)
        if token.isdigit():
            return int(token)
        return _ORDINAL_WORDS.get(token)

    # Leading choice: "1 kyc...", "2 sip"
    m = re.match(r"^([1-5])\b", normalized)
    if m:
        return int(m.group(1))

    # Short utterance with a single digit 1-5 (avoid dates like july 15)
    digits = re.findall(r"\b([1-5])\b", normalized)
    if len(digits) == 1 and not re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|20\d{2})\b",
        normalized,
    ):
        if len(normalized) <= 32:
            return int(digits[0])

    # Ordinal / number words — short phrases, or unambiguous words only
    words = set(normalized.split())
    for word, idx in _ORDINAL_WORDS.items():
        if word not in words:
            continue
        if word in _AMBIGUOUS_STT and len(words) > 2:
            continue
        if word in _AMBIGUOUS_STT and normalized not in {word, f"option {word}", f"number {word}"}:
            # allow "to"/"for" only as nearly bare answers
            if len(normalized) > 8:
                continue
        if idx <= len(TOPIC_CHOICES):
            return idx

    return None


def parse_topic(text: str) -> Topic | None:
    """Map free text to a Topic, or None if not in the closed set."""
    if not text or not text.strip():
        return None

    normalized = _normalize(text)
    if not normalized:
        return None

    # Ignore STT echo of the agent's own topic prompt
    if _looks_like_prompt_echo(normalized):
        return None

    # Exact enum label after normalization
    for topic in Topic:
        if normalized == _normalize(topic.value):
            return topic

    # Numbered / ordinal choice first (voice users often say "1" / "option 2")
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
