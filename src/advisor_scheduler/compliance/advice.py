"""Investment-advice refusal path (educational links only)."""

from __future__ import annotations

import re

_ADVICE_PATTERNS = (
    r"\binvest(ment)? advice\b",
    r"\bwhich (fund|stock|sip|scheme)\b",
    r"\bshould i (buy|sell|invest)\b",
    r"\brecommend( a| an| me)? (fund|stock|portfolio)\b",
    r"\bhigh returns?\b",
    r"\bguaranteed returns?\b",
    r"\bwhere (should|can) i invest\b",
    r"\bportfolio tips?\b",
)

_EDU_LINKS = (
    "https://www.sebi.gov.in/ (investor education — SEBI)",
    "https://www.nseindia.com/invest/investors-home (NSE investor resources)",
)


def is_advice_request(text: str, nlu_is_advice: bool = False) -> bool:
    if nlu_is_advice:
        return True
    if not text:
        return False
    lowered = text.lower()
    return any(re.search(pat, lowered) for pat in _ADVICE_PATTERNS)


def refusal_messages() -> list[str]:
    links = " ".join(_EDU_LINKS)
    return [
        "I can’t provide investment advice — only scheduling and educational information.",
        f"You may find these educational resources helpful: {links}",
        "If you’d like, I can help you book a tentative advisor slot instead.",
    ]
