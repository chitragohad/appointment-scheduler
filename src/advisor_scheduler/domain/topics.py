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


_ALIASES: dict[Topic, tuple[str, ...]] = {
    Topic.KYC_ONBOARDING: (
        "kyc/onboarding",
        "kyc onboarding",
        "kyc",
        "onboarding",
    ),
    Topic.SIP_MANDATES: (
        "sip/mandates",
        "sip mandates",
        "sip",
        "mandates",
    ),
    Topic.STATEMENTS_TAX: (
        "statements/tax docs",
        "statements and tax docs",
        "statements",
        "tax docs",
        "tax documents",
    ),
    Topic.WITHDRAWALS: (
        "withdrawals & timelines",
        "withdrawals and timelines",
        "withdrawals",
        "timelines",
    ),
    Topic.ACCOUNT_NOMINEE: (
        "account changes/nominee",
        "account changes nominee",
        "account changes",
        "nominee",
    ),
}


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def parse_topic(text: str) -> Topic | None:
    """Map free text to a Topic, or None if not in the closed set."""
    if not text or not text.strip():
        return None

    normalized = _normalize(text)

    for topic in Topic:
        if normalized == topic.value.lower():
            return topic

    # Prefer longer aliases first to avoid short-token false matches across topics
    scored: list[tuple[int, Topic]] = []
    for topic, aliases in _ALIASES.items():
        for alias in aliases:
            if alias == normalized or alias in normalized:
                scored.append((len(alias), topic))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]
