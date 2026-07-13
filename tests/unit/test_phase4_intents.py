"""Phase 4 — secondary intents: reschedule, cancel, prepare, availability."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from advisor_scheduler.agent.llm_agent import BookingAgent
from advisor_scheduler.agent.tool_bindings import REQUIRED_CANCEL_TOOLS, REQUIRED_RESCHEDULE_TOOLS
from advisor_scheduler.domain.booking import BookingRecord, BookingStatus, BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
from advisor_scheduler.domain.prepare_kb import format_preparation
from advisor_scheduler.domain.topics import Topic
from advisor_scheduler.mcp_client.google_mcp import GoogleMcpClient
from advisor_scheduler.mcp_server.server import create_mcp
from advisor_scheduler.orchestrator.engine import ConversationEngine
from advisor_scheduler.orchestrator.session import SessionState

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_CALENDAR = REPO_ROOT / "data" / "mock_calendar.json"


@pytest.fixture
def agent(mock_google_apis) -> BookingAgent:
    return BookingAgent(mcp=GoogleMcpClient(mcp=create_mcp()))


@pytest.fixture
def engine(agent: BookingAgent, monkeypatch: pytest.MonkeyPatch) -> ConversationEngine:
    monkeypatch.setenv("SECURE_LINK_BASE", "https://example.com/prebook")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return ConversationEngine(
        calendar=MockCalendarService.load(MOCK_CALENDAR),
        booking_store=BookingStore(),
        today_ist=date(2026, 7, 13),
        booking_agent=agent,
    )


def _seed_booking(engine: ConversationEngine, code: str = "NL-A742") -> BookingRecord:
    now = datetime.now(tz=IST)
    record = BookingRecord(
        code=code,
        topic=Topic.SIP_MANDATES,
        slot_id="slot_20260715_1000",
        slot_start=datetime(2026, 7, 15, 10, 0, tzinfo=IST),
        status=BookingStatus.TENTATIVE,
        calendar_event_id="evt_seed_1",
        secure_details_url=f"https://example.com/prebook/{code}",
        created_at=now,
        updated_at=now,
    )
    engine.booking_store.save(record)
    engine.calendar.mark_held("slot_20260715_1000")
    return record


def _to_intent(engine: ConversationEngine, session_id: str, utterance: str):
    engine.handle(session_id, "I understand")
    return engine.handle(session_id, utterance)


def test_prepare_kb_is_educational() -> None:
    text = format_preparation(Topic.KYC_ONBOARDING)
    assert "KYC" in text
    assert "advice" in text.lower() or "Educational" in text or "educational" in text


def test_what_to_prepare_flow(engine: ConversationEngine, mock_google_apis) -> None:
    created = engine.create_session()
    sid = created.session_id
    mid = _to_intent(engine, sid, "what should I prepare")
    assert mid.state == SessionState.PREPARE_TOPIC
    result = engine.handle(sid, "SIP Mandates")
    joined = " ".join(result.messages).lower()
    assert "sip" in joined
    assert "book" in joined
    # Prepare must not create calendar holds
    mock_google_apis["calendar"].events.return_value.insert.assert_not_called()


def test_check_availability_flow(engine: ConversationEngine) -> None:
    created = engine.create_session()
    sid = created.session_id
    result = _to_intent(engine, sid, "what times are available")
    assert result.state == SessionState.AVAILABILITY
    assert result.meta.get("windows")
    assert any("IST" in m for m in result.messages)

    follow = engine.handle(sid, "book a new slot")
    assert follow.state == SessionState.TOPIC


def test_reschedule_by_code_only(engine: ConversationEngine, mock_google_apis) -> None:
    _seed_booking(engine, "NL-A742")
    created = engine.create_session()
    sid = created.session_id
    _to_intent(engine, sid, "I need to reschedule my booking")
    lookup = engine.handle(sid, "NL-A742")
    assert lookup.state == SessionState.RESCHEDULE_PREFERENCE

    offer = engine.handle(sid, "July 16 morning")
    assert offer.state == SessionState.RESCHEDULE_OFFER
    confirm = engine.handle(sid, "1")
    assert confirm.state == SessionState.RESCHEDULE_CONFIRM
    assert "IST" in " ".join(confirm.messages)

    done = engine.handle(sid, "yes")
    assert done.state == SessionState.CLOSE
    assert done.meta.get("mcp_succeeded") == list(REQUIRED_RESCHEDULE_TOOLS)
    record = engine.booking_store.get("NL-A742")
    assert record is not None
    assert record.status == BookingStatus.RESCHEDULED
    mock_google_apis["calendar"].events.return_value.update.assert_called()
    mock_google_apis["calendar"].events.return_value.insert.assert_not_called()


def test_reschedule_accepts_spoken_code(engine: ConversationEngine) -> None:
    _seed_booking(engine, "NL-A742")
    created = engine.create_session()
    sid = created.session_id
    _to_intent(engine, sid, "reschedule")
    result = engine.handle(sid, "N L dash A 7 4 2")
    assert result.state == SessionState.RESCHEDULE_PREFERENCE


def test_cancel_by_code_only(engine: ConversationEngine, mock_google_apis) -> None:
    _seed_booking(engine, "NL-C900")
    created = engine.create_session()
    sid = created.session_id
    _to_intent(engine, sid, "cancel my appointment")
    confirm = engine.handle(sid, "NL-C900")
    assert confirm.state == SessionState.CANCEL_CONFIRM
    done = engine.handle(sid, "yes")
    assert done.state == SessionState.CLOSE
    assert done.meta.get("status") == "cancelled"
    assert done.meta.get("mcp_succeeded") == list(REQUIRED_CANCEL_TOOLS)
    record = engine.booking_store.get("NL-C900")
    assert record is not None
    assert record.status == BookingStatus.CANCELLED
    mock_google_apis["calendar"].events.return_value.delete.assert_called()


def test_cancel_rejects_phone_lookup_path(engine: ConversationEngine) -> None:
    """Cancellation asks for code; PII phone is blocked before lookup."""
    created = engine.create_session()
    sid = created.session_id
    _to_intent(engine, sid, "cancel")
    blocked = engine.handle(sid, "cancel using phone 9876543210")
    assert any("secure" in m.lower() or "phone" in m.lower() or "can’t collect" in m.lower() or "can't collect" in m.lower() for m in blocked.messages)
