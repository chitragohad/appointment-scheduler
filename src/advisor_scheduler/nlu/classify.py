"""Intent classification — rules fallback; optional Gemini when configured."""

from __future__ import annotations

import json
import os
import re

from advisor_scheduler.compliance import advice
from advisor_scheduler.domain.intents import Intent
from advisor_scheduler.nlu.extract import (
    extract_preference,
    extract_slot_choice,
    extract_topic,
    extract_yes_no,
)
from advisor_scheduler.nlu.models import NluResult

_INTENT_PATTERNS: list[tuple[Intent, tuple[str, ...]]] = [
    (
        Intent.BOOK_NEW,
        (
            r"\bbook\b",
            r"\bnew (slot|appointment|booking)\b",
            r"\bschedule\b",
            r"\breserve\b",
            r"\btalk to (an )?advisor\b",
        ),
    ),
    (
        Intent.RESCHEDULE,
        (r"\breschedule\b", r"\bchange (my )?(booking|slot|appointment)\b", r"\bmove (my )?booking\b"),
    ),
    (
        Intent.CANCEL,
        (r"\bcancel\b", r"\bdelete (my )?booking\b"),
    ),
    (
        Intent.WHAT_TO_PREPARE,
        (r"\bwhat (should|to) (i )?prepare\b", r"\bwhat (do i|should i) bring\b", r"\bprepare for\b"),
    ),
    (
        Intent.CHECK_AVAILABILITY,
        (r"\bavailability\b", r"\bwhen (can|are) (i|you)\b", r"\bwhat times?\b", r"\bfree slots?\b"),
    ),
]


def _classify_rules(text: str) -> NluResult:
    is_adv = advice.is_advice_request(text)
    intent: Intent | None = None
    confidence = 0.0

    for candidate, patterns in _INTENT_PATTERNS:
        if any(re.search(pat, text.lower()) for pat in patterns):
            intent = candidate
            confidence = 0.85
            break

    if intent is None and not is_adv:
        # Soft default when user is mid-booking with topic-like text
        if extract_topic(text):
            intent = Intent.BOOK_NEW
            confidence = 0.55

    return NluResult(
        intent=intent,
        confidence=confidence,
        topic=extract_topic(text),
        preference_raw=text.strip() or None,
        preference=None,  # filled by caller with today_ist
        confirmation=extract_yes_no(text),
        slot_choice=extract_slot_choice(text),
        is_advice=is_adv,
        needs_clarification=intent is None and not is_adv and confidence < 0.5,
        clarification_prompt=(
            "Would you like to book a new advisor slot, reschedule, cancel, "
            "check availability, or ask what to prepare?"
            if intent is None and not is_adv
            else None
        ),
    )


def _classify_gemini(text: str) -> NluResult | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import urllib.error
        import urllib.request

        model = os.getenv("LLM_MODEL", "gemini-2.0-flash")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        prompt = (
            "Classify the user message for an advisor appointment scheduler. "
            "Return ONLY JSON with keys: intent "
            "(book_new|reschedule|cancel|what_to_prepare|check_availability|null), "
            "confidence (0-1), is_advice (bool). Message: "
            + json.dumps(text)
        )
        body = json.dumps(
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        raw_text = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(raw_text)
        intent_raw = data.get("intent")
        intent = Intent(intent_raw) if intent_raw in {i.value for i in Intent} else None
        return NluResult(
            intent=intent,
            confidence=float(data.get("confidence") or 0.0),
            topic=extract_topic(text),
            preference_raw=text.strip() or None,
            confirmation=extract_yes_no(text),
            slot_choice=extract_slot_choice(text),
            is_advice=bool(data.get("is_advice")) or advice.is_advice_request(text),
            needs_clarification=intent is None and not bool(data.get("is_advice")),
        )
    except Exception:
        return None


def classify(text: str, *, today_ist=None) -> NluResult:
    """Classify user text. Uses Gemini when ``GEMINI_API_KEY`` is set; else rules."""
    result = _classify_gemini(text) or _classify_rules(text)
    if today_ist is not None:
        result.preference = extract_preference(text, today_ist=today_ist)
    else:
        # Leave preference unset unless extract without today — skip
        pass
    return result
