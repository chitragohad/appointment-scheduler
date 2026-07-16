"""Slot and time-preference models plus slot picker."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel


from advisor_scheduler.domain.ist import IST

if TYPE_CHECKING:
    from advisor_scheduler.domain.calendar_mock import MockCalendarService


class Slot(BaseModel):
    id: str
    start: datetime
    end: datetime
    status: Literal["available", "held", "waitlist"]


class TimePreference(BaseModel):
    date_ist: date | None = None
    window_start_ist: time | None = None
    window_end_ist: time | None = None
    # When set, only slots starting at this exact IST clock time are eligible
    exact_time_ist: time | None = None
    raw_text: str = ""


def _to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _preference_anchor(pref: TimePreference) -> datetime | None:
    """Build an IST anchor datetime used to score distance to slots."""
    if pref.date_ist is None:
        return None

    start_t = pref.window_start_ist or time(0, 0)
    end_t = pref.window_end_ist or time(23, 59)

    # Midpoint of window on preferred date
    start_dt = datetime.combine(pref.date_ist, start_t, tzinfo=IST)
    end_dt = datetime.combine(pref.date_ist, end_t, tzinfo=IST)
    if end_dt < start_dt:
        end_dt = start_dt
    delta = end_dt - start_dt
    return start_dt + (delta / 2)


def _score_slot(slot: Slot, pref: TimePreference) -> float:
    """Lower score is better (closer to preference)."""
    start = _to_ist(slot.start)
    anchor = _preference_anchor(pref)

    if anchor is None:
        # No date preference — prefer sooner slots
        return start.timestamp()

    # Prefer same calendar day strongly
    day_penalty = abs((start.date() - pref.date_ist).days) * 86_400  # type: ignore[union-attr]

    # Distance from window midpoint
    time_distance = abs((start - anchor).total_seconds())

    # Extra penalty if outside preferred window (when window given)
    window_penalty = 0.0
    if pref.window_start_ist and pref.window_end_ist and pref.date_ist:
        win_start = datetime.combine(pref.date_ist, pref.window_start_ist, tzinfo=IST)
        win_end = datetime.combine(pref.date_ist, pref.window_end_ist, tzinfo=IST)
        if start.date() == pref.date_ist and not (win_start <= start <= win_end):
            window_penalty = 3_600.0

    return day_penalty + time_distance + window_penalty


def find_slots(
    preference: TimePreference,
    calendar: MockCalendarService,
    n: int = 2,
) -> list[Slot]:
    """
    Return up to ``n`` available slots closest to preference (IST).

    Never invents slots; returns [] when none are available / suitable.
    If ``exact_time_ist`` is set, only same-clock-time slots (and same day when
    ``date_ist`` is set) are returned — no fuzzy substitutes.
    """
    available = list(calendar.list_available())
    if not available:
        return []

    if preference.exact_time_ist is not None:
        exact: list[Slot] = []
        for s in available:
            start = _to_ist(s.start)
            if start.hour != preference.exact_time_ist.hour or start.minute != preference.exact_time_ist.minute:
                continue
            if preference.date_ist is not None and start.date() != preference.date_ist:
                continue
            exact.append(s)
        return sorted(exact, key=lambda s: _to_ist(s.start))[:n]

    # If a preferred date is set, only consider slots within ±3 days;
    # if still empty, return [] (waitlist path) rather than distant invent-like matches.
    if preference.date_ist is not None:
        window_days = 3
        lo = preference.date_ist - timedelta(days=window_days)
        hi = preference.date_ist + timedelta(days=window_days)
        nearby = [
            s
            for s in available
            if lo <= _to_ist(s.start).date() <= hi
        ]
        if not nearby:
            return []
        available = nearby

    ranked = sorted(available, key=lambda s: (_score_slot(s, preference), s.start, s.id))
    return ranked[:n]
