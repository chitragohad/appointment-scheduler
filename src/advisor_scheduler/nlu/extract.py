"""Entity extraction helpers (rules-first; LLM optional later)."""

from __future__ import annotations

import calendar
import re
from datetime import date, time, timedelta
from typing import Literal

from advisor_scheduler.domain.slots import TimePreference
from advisor_scheduler.domain.topics import Topic, parse_topic

_YES = re.compile(r"^\s*(yes|yep|yeah|yup|sure|confirm|correct|ok(ay)?)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|nah|cancel that|not really)\b", re.I)


def extract_yes_no(text: str) -> Literal["yes", "no", "unknown"]:
    if not text or not text.strip():
        return "unknown"
    if _YES.search(text.strip()):
        return "yes"
    if _NO.search(text.strip()):
        return "no"
    return "unknown"


def extract_slot_choice(text: str) -> Literal[1, 2] | None:
    if not text:
        return None
    lowered = text.strip().lower()
    if re.search(r"\b(first|1st|option\s*1|slot\s*1|#\s*1)\b", lowered) or lowered in {"1", "one"}:
        return 1
    if re.search(r"\b(second|2nd|option\s*2|slot\s*2|#\s*2)\b", lowered) or lowered in {"2", "two"}:
        return 2
    return None


def extract_topic(text: str) -> Topic | None:
    return parse_topic(text)


_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})


def extract_preference(text: str, *, today_ist: date) -> TimePreference | None:
    """Parse a simple day/time preference into IST fields."""
    if not text or not text.strip():
        return None

    raw = text.strip()
    lowered = raw.lower()

    window_start: time | None = None
    window_end: time | None = None
    if "morning" in lowered:
        window_start, window_end = time(9, 0), time(12, 0)
    elif "afternoon" in lowered:
        window_start, window_end = time(12, 0), time(17, 0)
    elif "evening" in lowered:
        window_start, window_end = time(17, 0), time(20, 0)

    date_ist: date | None = None

    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", lowered)
    if iso:
        date_ist = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    else:
        m = re.search(
            r"\b(" + "|".join(_MONTHS.keys()) + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(20\d{2}))?\b",
            lowered,
        )
        if m:
            month = _MONTHS[m.group(1)]
            day = int(m.group(2))
            year = int(m.group(3)) if m.group(3) else today_ist.year
            try:
                date_ist = date(year, month, day)
            except ValueError:
                date_ist = None
            if date_ist and date_ist < today_ist and not m.group(3):
                # Roll to next year if month/day already passed
                try:
                    date_ist = date(today_ist.year + 1, month, day)
                except ValueError:
                    pass

    if date_ist is None:
        if "tomorrow" in lowered:
            date_ist = today_ist + timedelta(days=1)
        elif "today" in lowered:
            date_ist = today_ist

    if date_ist is None and window_start is None:
        return None

    return TimePreference(
        date_ist=date_ist,
        window_start_ist=window_start,
        window_end_ist=window_end,
        raw_text=raw,
    )
