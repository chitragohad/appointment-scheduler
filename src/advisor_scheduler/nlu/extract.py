"""Entity extraction helpers (rules-first; LLM optional later)."""

from __future__ import annotations

import calendar
import re
from datetime import date, time, timedelta
from typing import Literal

from advisor_scheduler.domain.slots import Slot, TimePreference
from advisor_scheduler.domain.topics import Topic, parse_topic

_YES = re.compile(r"^\s*(yes|yep|yeah|yup|sure|confirm|correct|ok(ay)?)\b", re.I)
_NO = re.compile(
    r"^\s*(no|nope|nah|cancel that|not really|pick again|choose again|different|"
    r"another (slot|time|date|one)|change (it|slot|time|date)|start over)\b",
    re.I,
)
_PICK_AGAIN = re.compile(
    r"\b(pick again|choose again|another (slot|time|date|one)|different (slot|time|date|one)|"
    r"change (the )?(slot|time|date)|new (slot|time|date)|not that one)\b",
    re.I,
)
_DATEISH = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|tomorrow|today|morning|afternoon|evening|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"am|pm|\d{1,2}:\d{2}|\d{1,2}\s*(am|pm))\b",
    re.I,
)
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})


def extract_yes_no(text: str) -> Literal["yes", "no", "unknown"]:
    if not text or not text.strip():
        return "unknown"
    stripped = text.strip()
    if _PICK_AGAIN.search(stripped):
        return "no"
    if _YES.search(stripped):
        return "yes"
    if _NO.search(stripped):
        return "no"
    return "unknown"


def extract_slot_choice(text: str) -> Literal[1, 2] | None:
    """Accept clear option-1 / option-2 answers."""
    if not text:
        return None
    lowered = text.strip().lower()
    explicit_option = bool(
        re.search(r"\b(option|slot|choice|number|#)\s*[12]\b", lowered)
        or re.search(r"\b(first|second|1st|2nd)\b", lowered)
        or lowered in {"1", "2", "one", "two"}
    )
    if _DATEISH.search(lowered) and not explicit_option:
        return None
    if len(lowered) > 48 and not explicit_option:
        return None

    if re.search(r"\b(first|1st|option\s*1|slot\s*1|choice\s*1|number\s*1|#\s*1)\b", lowered):
        return 1
    if re.search(r"\b(second|2nd|option\s*2|slot\s*2|choice\s*2|number\s*2|#\s*2)\b", lowered):
        return 2
    if lowered in {"1", "one"}:
        return 1
    if lowered in {"2", "two"}:
        return 2
    return None


def _parse_clock_time(text: str) -> time | None:
    """Parse an exact clock time from speech/text (IST assumed)."""
    lowered = text.strip().lower()
    # 10:00, 10:00am, 10:00 am, 10:00 IST
    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?\b", lowered)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        meridiem = (m.group(3) or "").replace(".", "")
        if meridiem.startswith("p") and hour < 12:
            hour += 12
        if meridiem.startswith("a") and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute)

    # 10am, 10 am, 11 pm
    m = re.search(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)\b", lowered)
    if m:
        hour = int(m.group(1))
        meridiem = m.group(2).replace(".", "")
        if meridiem.startswith("p") and hour < 12:
            hour += 12
        if meridiem.startswith("a") and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            return time(hour, 0)
    return None


def match_offered_slot_choice(
    text: str,
    offered: list[Slot],
    *,
    today_ist: date,
) -> Literal[1, 2] | None:
    """
    Map user text to option 1/2.
    Spoken date/time is accepted only when it exactly matches one offered slot.
    """
    if not text or not offered:
        return None

    direct = extract_slot_choice(text)
    if direct is not None and direct <= len(offered):
        return direct

    pref = extract_preference(text, today_ist=today_ist)
    exact_time = pref.exact_time_ist if pref else _parse_clock_time(text)
    weekday = None
    lowered = text.strip().lower()
    for name, idx in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", lowered):
            weekday = idx
            break

    matches: list[int] = []
    for idx, slot in enumerate(offered[:2], start=1):
        local = slot.start
        slot_day = local.date()
        slot_t = local.time().replace(second=0, microsecond=0)

        if exact_time is not None:
            if slot_t.hour != exact_time.hour or slot_t.minute != exact_time.minute:
                continue
            if pref and pref.date_ist is not None and slot_day != pref.date_ist:
                continue
            if weekday is not None and slot_day.weekday() != weekday:
                continue
            matches.append(idx)
            continue

        if pref is not None and pref.date_ist is not None:
            if slot_day != pref.date_ist:
                continue
            if pref.window_start_ist and pref.window_end_ist:
                if not (pref.window_start_ist <= slot_t < pref.window_end_ist):
                    continue
            matches.append(idx)
            continue

        if weekday is not None and slot_day.weekday() == weekday:
            if "morning" in lowered and not (time(9, 0) <= slot_t < time(12, 0)):
                continue
            if "afternoon" in lowered and not (time(12, 0) <= slot_t < time(17, 0)):
                continue
            if "evening" in lowered and not (time(17, 0) <= slot_t < time(20, 0)):
                continue
            matches.append(idx)

    if len(matches) == 1:
        return matches[0]  # type: ignore[return-value]
    return None


def looks_like_datetime_request(text: str) -> bool:
    """True when the user appears to propose a date/time instead of option 1/2."""
    if not text or not text.strip():
        return False
    if extract_slot_choice(text) is not None:
        return False
    return extract_preference(text, today_ist=date.today()) is not None or bool(
        _DATEISH.search(text.lower())
    )


def extract_topic(text: str) -> Topic | None:
    return parse_topic(text)


def extract_preference(text: str, *, today_ist: date) -> TimePreference | None:
    """Parse day / window / exact clock time preference into IST fields."""
    if not text or not text.strip():
        return None

    raw = text.strip()
    lowered = raw.lower()
    exact_time = _parse_clock_time(lowered)

    window_start: time | None = None
    window_end: time | None = None
    if exact_time is None:
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
                try:
                    date_ist = date(today_ist.year + 1, month, day)
                except ValueError:
                    pass

    if date_ist is None:
        if "tomorrow" in lowered:
            date_ist = today_ist + timedelta(days=1)
        elif "today" in lowered:
            date_ist = today_ist
        else:
            for name, weekday in _WEEKDAYS.items():
                if re.search(rf"\b{name}\b", lowered):
                    # Next occurrence of that weekday (including today)
                    delta = (weekday - today_ist.weekday()) % 7
                    date_ist = today_ist + timedelta(days=delta)
                    break

    if date_ist is None and window_start is None and exact_time is None:
        return None

    return TimePreference(
        date_ist=date_ist,
        window_start_ist=window_start,
        window_end_ist=window_end,
        exact_time_ist=exact_time,
        raw_text=raw,
    )
