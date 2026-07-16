"""Phase 1 domain tests — topics, calendar, slots, codes, IST, bookings, secure link."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from advisor_scheduler.domain.booking import BookingRecord, BookingStatus, BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
from advisor_scheduler.domain.codes import (
    BOOKING_CODE_PATTERN,
    generate_booking_code,
    normalize_code,
    spell_code_for_tts,
)
from advisor_scheduler.domain.ist import format_ist
from advisor_scheduler.domain.slots import Slot, TimePreference, find_slots
from advisor_scheduler.domain.topics import Topic, parse_topic
from advisor_scheduler.secure_link import issue_secure_details_url

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_CALENDAR = REPO_ROOT / "data" / "mock_calendar.json"
CODE_RE = re.compile(r"^NL-[A-Z0-9]{4}$")


# --- topics -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("KYC/Onboarding", Topic.KYC_ONBOARDING),
        ("kyc onboarding", Topic.KYC_ONBOARDING),
        ("K Y C", Topic.KYC_ONBOARDING),
        ("1", Topic.KYC_ONBOARDING),
        ("option 1", Topic.KYC_ONBOARDING),
        ("option one", Topic.KYC_ONBOARDING),
        ("I want 2", Topic.SIP_MANDATES),
        ("I will take 3", Topic.STATEMENTS_TAX),
        ("I need help with SIP mandates", Topic.SIP_MANDATES),
        ("S I P", Topic.SIP_MANDATES),
        ("2", Topic.SIP_MANDATES),
        ("statements and tax docs", Topic.STATEMENTS_TAX),
        ("tax docs", Topic.STATEMENTS_TAX),
        ("3", Topic.STATEMENTS_TAX),
        ("number three", Topic.STATEMENTS_TAX),
        ("withdrawals & timelines", Topic.WITHDRAWALS),
        ("withdrawal", Topic.WITHDRAWALS),
        ("4", Topic.WITHDRAWALS),
        ("account changes nominee", Topic.ACCOUNT_NOMINEE),
        ("nominee", Topic.ACCOUNT_NOMINEE),
        ("5", Topic.ACCOUNT_NOMINEE),
        ("fifth", Topic.ACCOUNT_NOMINEE),
        ("go with 1", Topic.KYC_ONBOARDING),
        ("1 KYC/Onboarding", Topic.KYC_ONBOARDING),
    ],
)
def test_parse_topic_accepts_known_topics(text: str, expected: Topic) -> None:
    assert parse_topic(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "portfolio tips",
        "which fund should I buy",
        "",
        "something unrelated",
        # STT echo of the agent prompt listing every topic
        "Which consultation topic fits best? Say 1 KYC/Onboarding, 2 SIP/Mandates, "
        "3 Statements/Tax Docs, 4 Withdrawals & Timelines, or 5 Account Changes/Nominee.",
    ],
)
def test_parse_topic_rejects_unknown(text: str) -> None:
    assert parse_topic(text) is None


# --- IST --------------------------------------------------------------------


def test_format_ist_always_contains_ist() -> None:
    dt = datetime(2026, 7, 15, 10, 0, tzinfo=IST)
    formatted = format_ist(dt)
    assert "IST" in formatted
    assert "15" in formatted
    assert "2026" in formatted


def test_format_ist_converts_utc_to_ist_display() -> None:
    # 04:30 UTC == 10:00 IST
    dt = datetime(2026, 7, 15, 4, 30, tzinfo=timezone.utc)
    formatted = format_ist(dt)
    assert "IST" in formatted
    assert "10:00" in formatted or "10:00 AM" in formatted.upper()


# --- codes ------------------------------------------------------------------


def test_generate_booking_code_matches_pattern() -> None:
    code = generate_booking_code(set())
    assert CODE_RE.match(code)
    assert BOOKING_CODE_PATTERN.match(code)


def test_generate_booking_code_unique_against_existing() -> None:
    existing = {generate_booking_code(set()) for _ in range(20)}
    for _ in range(50):
        code = generate_booking_code(existing)
        assert code not in existing
        assert CODE_RE.match(code)
        existing.add(code)


def test_normalize_code_from_plain_and_spoken() -> None:
    assert normalize_code("NL-A742") == "NL-A742"
    assert normalize_code("nl-a742") == "NL-A742"
    assert normalize_code("N L dash A 7 4 2") == "NL-A742"
    assert normalize_code("n l - a 7 4 2") == "NL-A742"
    assert normalize_code("garbage") is None


def test_spell_code_for_tts() -> None:
    assert spell_code_for_tts("NL-A742") == "N L dash A 7 4 2"


# --- mock calendar ----------------------------------------------------------


@pytest.fixture
def calendar() -> MockCalendarService:
    return MockCalendarService.load(MOCK_CALENDAR)


def test_mock_calendar_lists_available_only(calendar: MockCalendarService) -> None:
    available = calendar.list_available()
    assert available
    assert all(s.status == "available" for s in available)
    assert all(s.id != "slot_20260715_1600" for s in available)


def test_mock_calendar_mark_held_and_release(calendar: MockCalendarService) -> None:
    slot_id = "slot_20260715_1000"
    calendar.mark_held(slot_id)
    assert slot_id not in {s.id for s in calendar.list_available()}
    held = calendar.get(slot_id)
    assert held is not None
    assert held.status == "held"

    calendar.release(slot_id)
    assert slot_id in {s.id for s in calendar.list_available()}


def test_mock_calendar_never_invents_slots(calendar: MockCalendarService) -> None:
    ids = {s.id for s in calendar.all_slots()}
    assert "invented_slot" not in ids


# --- find_slots -------------------------------------------------------------


def test_find_slots_returns_exactly_two_when_available(
    calendar: MockCalendarService,
) -> None:
    pref = TimePreference(
        date_ist=date(2026, 7, 15),
        window_start_ist=time(9, 0),
        window_end_ist=time(12, 0),
        raw_text="July 15 morning",
    )
    found = find_slots(pref, calendar, n=2)
    assert len(found) == 2
    assert all(isinstance(s, Slot) for s in found)
    assert all(s.status == "available" for s in found)
    # Closest morning slots on that day should win
    assert found[0].id == "slot_20260715_1000"
    assert found[1].id == "slot_20260715_1130"


def test_find_slots_empty_when_none_match(calendar: MockCalendarService) -> None:
    # Far future date with no slots in JSON
    pref = TimePreference(
        date_ist=date(2099, 1, 1),
        window_start_ist=time(9, 0),
        window_end_ist=time(17, 0),
        raw_text="year 2099",
    )
    assert find_slots(pref, calendar, n=2) == []


def test_find_slots_returns_fewer_than_n_if_only_one_left(
    calendar: MockCalendarService,
) -> None:
    # Hold everything except one far slot, prefer that day
    for s in list(calendar.list_available()):
        if s.id != "slot_20260720_1100":
            calendar.mark_held(s.id)

    pref = TimePreference(
        date_ist=date(2026, 7, 20),
        window_start_ist=None,
        window_end_ist=None,
        raw_text="July 20",
    )
    found = find_slots(pref, calendar, n=2)
    assert len(found) == 1
    assert found[0].id == "slot_20260720_1100"


def test_find_slots_does_not_return_held(calendar: MockCalendarService) -> None:
    pref = TimePreference(
        date_ist=date(2026, 7, 15),
        window_start_ist=time(15, 0),
        window_end_ist=time(17, 0),
        raw_text="July 15 afternoon",
    )
    found = find_slots(pref, calendar, n=2)
    assert all(s.id != "slot_20260715_1600" for s in found)


def test_find_slots_exact_time_match(calendar: MockCalendarService) -> None:
    pref = TimePreference(
        date_ist=date(2026, 7, 15),
        exact_time_ist=time(10, 0),
        raw_text="July 15 at 10:00",
    )
    found = find_slots(pref, calendar, n=2)
    assert len(found) == 1
    assert found[0].id == "slot_20260715_1000"


def test_find_slots_exact_time_no_match(calendar: MockCalendarService) -> None:
    pref = TimePreference(
        date_ist=date(2026, 7, 15),
        exact_time_ist=time(10, 15),
        raw_text="July 15 at 10:15",
    )
    assert find_slots(pref, calendar, n=2) == []


# --- booking store ----------------------------------------------------------


def test_booking_store_save_and_get() -> None:
    store = BookingStore()
    now = datetime.now(tz=IST)
    record = BookingRecord(
        code="NL-A742",
        topic=Topic.SIP_MANDATES,
        slot_id="slot_20260715_1000",
        slot_start=datetime(2026, 7, 15, 10, 0, tzinfo=IST),
        status=BookingStatus.TENTATIVE,
        calendar_event_id=None,
        secure_details_url="https://example.com/prebook/NL-A742",
        created_at=now,
        updated_at=now,
    )
    store.save(record)
    assert store.get("NL-A742") == record
    assert store.get("NL-ZZZZ") is None
    assert "NL-A742" in store.codes()


# --- secure link ------------------------------------------------------------


def test_issue_secure_details_url_includes_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURE_LINK_BASE", "https://example.com/prebook")
    monkeypatch.delenv("SECURE_LINK_SECRET", raising=False)
    url = issue_secure_details_url("NL-A742")
    assert url.startswith("https://example.com/prebook/")
    assert "NL-A742" in url
