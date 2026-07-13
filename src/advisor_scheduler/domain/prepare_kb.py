"""Educational prep guidance by topic (not investment advice)."""

from __future__ import annotations

from advisor_scheduler.domain.topics import Topic

_PREPARE: dict[Topic, list[str]] = {
    Topic.KYC_ONBOARDING: [
        "Keep a government ID ready for verification (shared only via the secure link later).",
        "Note any existing folio or application reference numbers (do not share them in chat).",
        "List questions about onboarding steps and timelines.",
    ],
    Topic.SIP_MANDATES: [
        "Note your SIP amount and preferred date (details completed offline).",
        "Have bank mandate status questions ready (e.g. pending / active).",
        "This session is scheduling only — no product recommendations.",
    ],
    Topic.STATEMENTS_TAX: [
        "Know the financial year or statement period you need.",
        "List which documents you are looking for (statement, tax report, etc.).",
        "Do not paste account numbers in this chat.",
    ],
    Topic.WITHDRAWALS: [
        "Note the approximate amount and urgency (not advice — for scheduling context).",
        "Prepare questions about processing timelines and documentation.",
        "Contact details are collected only via the secure link after booking.",
    ],
    Topic.ACCOUNT_NOMINEE: [
        "List the type of change (nominee, contact, demat linkage, etc.).",
        "Have supporting document names ready (upload happens outside this chat).",
        "We cannot collect PII here — use the secure link after a slot is held.",
    ],
}


def preparation_for(topic: Topic) -> list[str]:
    return list(_PREPARE[topic])


def format_preparation(topic: Topic) -> str:
    bullets = "\n".join(f"• {item}" for item in preparation_for(topic))
    return (
        f"Here’s what to prepare for {topic.value} (educational only — not advice):\n"
        f"{bullets}"
    )
