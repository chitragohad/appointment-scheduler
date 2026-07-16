"""Phase 2 — compliance, orchestrator book_new flow, and chat API."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from advisor_scheduler.api.app import create_app
from advisor_scheduler.compliance import advice, disclaimer, pii
from advisor_scheduler.domain.booking import BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
from advisor_scheduler.domain.ist import IST
from advisor_scheduler.domain.topics import Topic
from advisor_scheduler.nlu.classify import classify
from advisor_scheduler.nlu.extract import extract_preference, extract_slot_choice, extract_yes_no
from advisor_scheduler.orchestrator.engine import ConversationEngine
from advisor_scheduler.orchestrator.session import SessionState

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_CALENDAR = REPO_ROOT / "data" / "mock_calendar.json"


@pytest.fixture
def calendar() -> MockCalendarService:
    return MockCalendarService.load(MOCK_CALENDAR)


@pytest.fixture
def engine(
    calendar: MockCalendarService,
    monkeypatch: pytest.MonkeyPatch,
    mock_google_apis,
) -> ConversationEngine:
    monkeypatch.setenv("SECURE_LINK_BASE", "https://example.com/prebook")
    monkeypatch.delenv("SECURE_LINK_SECRET", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from advisor_scheduler.agent.llm_agent import BookingAgent
    from advisor_scheduler.mcp_client.google_mcp import GoogleMcpClient
    from advisor_scheduler.mcp_server.server import create_mcp

    return ConversationEngine(
        calendar=calendar,
        booking_store=BookingStore(),
        today_ist=date(2026, 7, 13),
        booking_agent=BookingAgent(mcp=GoogleMcpClient(mcp=create_mcp())),
    )


def _ack_to_intent(engine: ConversationEngine, session_id: str) -> None:
    engine.handle(session_id, "I understand")


def _drive_to_topic(engine: ConversationEngine, session_id: str) -> None:
    _ack_to_intent(engine, session_id)
    engine.handle(session_id, "I want to book a new advisor slot")


# --- compliance -------------------------------------------------------------


def test_disclaimer_requires_acknowledgment() -> None:
    assert disclaimer.is_ack("yes")
    assert disclaimer.is_ack("I understand")
    assert not disclaimer.is_ack("tell me about SIP")
    assert "not investment advice" in disclaimer.script().lower()


def test_pii_detects_phone_email_account() -> None:
    assert pii.detect("call me at 9876543210") is not None
    assert pii.detect("email me at user@example.com") is not None
    assert pii.detect("my account number is 123456789012") is not None
    assert pii.detect("I want SIP help") is None
    assert "secure" in pii.firewall_reply().lower() or "link" in pii.firewall_reply().lower()


def test_advice_detection_and_refusal() -> None:
    assert advice.is_advice_request("which mutual fund should I buy?")
    assert advice.is_advice_request("give me investment advice")
    assert not advice.is_advice_request("book a slot for KYC")
    msgs = advice.refusal_messages()
    assert msgs
    assert any("http" in m.lower() or "www" in m.lower() or "educat" in m.lower() for m in msgs)


# --- NLU rules --------------------------------------------------------------


def test_classify_book_new_intent() -> None:
    result = classify("I'd like to book a new appointment")
    assert result.intent is not None
    assert result.intent.value == "book_new"
    assert result.is_advice is False


def test_classify_advice_flag() -> None:
    result = classify("Should I invest in equity now?")
    assert result.is_advice is True


def test_extract_yes_no_and_slot_choice() -> None:
    assert extract_yes_no("yes please") == "yes"
    assert extract_yes_no("no") == "no"
    assert extract_slot_choice("I'll take the first one") == 1
    assert extract_slot_choice("option 2") == 2


def test_extract_preference_july_15_morning() -> None:
    pref = extract_preference("July 15 morning", today_ist=date(2026, 7, 13))
    assert pref is not None
    assert pref.date_ist == date(2026, 7, 15)
    assert pref.window_start_ist == time(9, 0)
    assert pref.window_end_ist == time(12, 0)


def test_extract_preference_exact_time() -> None:
    pref = extract_preference("July 16 at 10:00 am", today_ist=date(2026, 7, 13))
    assert pref is not None
    assert pref.date_ist == date(2026, 7, 16)
    assert pref.exact_time_ist == time(10, 0)
    assert pref.window_start_ist is None


# --- orchestrator guards ----------------------------------------------------


def test_disclaimer_required_before_topic(engine: ConversationEngine) -> None:
    created = engine.create_session(channel="chat")
    session_id = created.session_id
    assert created.state == SessionState.DISCLAIMER

    # Attempt to skip disclaimer with a topic
    result = engine.handle(session_id, "SIP Mandates")
    assert result.state == SessionState.DISCLAIMER
    assert any("understand" in m.lower() or "disclaimer" in m.lower() or "acknowledge" in m.lower() for m in result.messages)


def test_pii_blocks_and_keeps_state(engine: ConversationEngine) -> None:
    created = engine.create_session(channel="chat")
    session_id = created.session_id
    _drive_to_topic(engine, session_id)

    before = engine.get_session(session_id)
    assert before is not None
    assert before.state == SessionState.TOPIC

    result = engine.handle(session_id, "My phone is 9876543210")
    assert result.state == SessionState.TOPIC
    assert any("secure" in m.lower() or "link" in m.lower() or "contact" in m.lower() for m in result.messages)
    assert engine.booking_store.codes() == set()


def test_advice_refusal_does_not_book(engine: ConversationEngine) -> None:
    created = engine.create_session(channel="chat")
    session_id = created.session_id
    _ack_to_intent(engine, session_id)

    result = engine.handle(session_id, "Which fund should I buy for high returns?")
    assert result.state in {SessionState.ADVICE_REFUSAL, SessionState.INTENT}
    assert engine.booking_store.codes() == set()
    joined = " ".join(result.messages).lower()
    assert "advice" in joined or "educational" in joined or "http" in joined


def test_book_new_happy_path_to_close_with_ist_and_code(
    engine: ConversationEngine,
) -> None:
    created = engine.create_session(channel="chat")
    session_id = created.session_id

    engine.handle(session_id, "I understand")
    engine.handle(session_id, "book a new slot")
    engine.handle(session_id, "SIP Mandates")
    offer = engine.handle(session_id, "July 15 morning")
    assert offer.state == SessionState.OFFER_SLOTS
    assert len(offer.meta.get("offered_slots", [])) == 2

    confirm = engine.handle(session_id, "1")
    assert confirm.state == SessionState.CONFIRM
    assert any("IST" in m for m in confirm.messages)

    final = engine.handle(session_id, "yes")
    assert final.state in {SessionState.CLOSE, SessionState.ENDED}
    joined = " ".join(final.messages)
    assert "IST" in joined
    assert "NL-" in joined
    assert "https://example.com/prebook/" in joined
    assert engine.booking_store.codes()
    code = next(iter(engine.booking_store.codes()))
    record = engine.booking_store.get(code)
    assert record is not None
    assert record.topic == Topic.SIP_MANDATES


def test_confirm_message_repeats_full_ist_datetime(engine: ConversationEngine) -> None:
    created = engine.create_session(channel="chat")
    session_id = created.session_id
    engine.handle(session_id, "I understand")
    engine.handle(session_id, "book new")
    engine.handle(session_id, "KYC Onboarding")
    engine.handle(session_id, "July 15 morning")

    session = engine.get_session(session_id)
    assert session is not None
    assert session.state == SessionState.OFFER_SLOTS
    assert len(session.offered_slots) == 2

    result = engine.handle(session_id, "1")
    assert result.state == SessionState.CONFIRM
    joined = " ".join(result.messages)
    assert "IST" in joined
    # Slot 1 on July 15 morning is 10:00
    assert "15" in joined and "2026" in joined


# --- HTTP API ---------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, mock_google_apis) -> TestClient:
    monkeypatch.setenv("SECURE_LINK_BASE", "https://example.com/prebook")
    monkeypatch.setenv("MOCK_CALENDAR_PATH", str(MOCK_CALENDAR))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from advisor_scheduler.agent.llm_agent import BookingAgent
    from advisor_scheduler.mcp_client.google_mcp import GoogleMcpClient
    from advisor_scheduler.mcp_server.server import create_mcp

    app = create_app(
        today_ist=date(2026, 7, 13),
        booking_agent=BookingAgent(mcp=GoogleMcpClient(mcp=create_mcp())),
    )
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_happy_path_book_new(client: TestClient) -> None:
    start = client.post("/sessions", json={"channel": "chat"})
    assert start.status_code == 200
    body = start.json()
    session_id = body["session_id"]
    assert body["state"] == SessionState.DISCLAIMER.value

    def say(text: str) -> dict:
        r = client.post(f"/sessions/{session_id}/message", json={"text": text})
        assert r.status_code == 200
        return r.json()

    say("I understand")
    say("book a new advisor appointment")
    say("SIP Mandates")
    mid = say("July 15 morning")
    assert mid["state"] == SessionState.OFFER_SLOTS.value
    confirm = say("1")
    assert confirm["state"] == SessionState.CONFIRM.value
    assert any("IST" in m for m in confirm["messages"])
    done = say("yes")
    assert done["state"] in {SessionState.CLOSE.value, SessionState.ENDED.value}
    joined = " ".join(done["messages"])
    assert "NL-" in joined
    assert "IST" in joined
