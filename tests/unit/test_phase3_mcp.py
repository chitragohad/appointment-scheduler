"""Phase 3 — actual Google MCP tools via BookingAgent (Google HTTP mocked at boundary)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from advisor_scheduler.agent.llm_agent import BookingAgent
from advisor_scheduler.agent.tool_bindings import REQUIRED_BOOKING_TOOLS, REQUIRED_WAITLIST_TOOLS
from advisor_scheduler.domain.booking import BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
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


def test_mcp_server_lists_google_tools() -> None:
    import asyncio

    from fastmcp import Client

    async def _list():
        async with Client(create_mcp()) as client:
            tools = await client.list_tools()
            return sorted(t.name for t in tools)

    names = asyncio.run(_list())
    for required in (
        "calendar_create_hold",
        "calendar_delete_hold",
        "calendar_update_hold",
        "docs_append_prebooking",
        "gmail_create_draft",
    ):
        assert required in names


def test_agent_calls_mcp_tools_in_order(agent: BookingAgent, mock_google_apis) -> None:
    start = datetime(2026, 7, 15, 10, 0, tzinfo=IST)
    end = datetime(2026, 7, 15, 10, 30, tzinfo=IST)
    result = agent.run_booking_side_effects(
        code="NL-A742",
        topic="SIP/Mandates",
        slot_start=start,
        slot_end=end,
    )
    assert result.failed == []
    assert result.succeeded == list(REQUIRED_BOOKING_TOOLS)
    assert result.calendar_event_id == "evt_test_123"
    assert result.docs_ok is True
    assert result.gmail_draft_id == "draft_test_456"

    # Calendar insert was invoked through actual MCP → tool → google mock
    mock_google_apis["calendar"].events.return_value.insert.assert_called()
    mock_google_apis["docs"].documents.return_value.batchUpdate.assert_called()
    mock_google_apis["gmail"].users.return_value.drafts.return_value.create.assert_called()


def test_waitlist_agent_skips_calendar_create(agent: BookingAgent) -> None:
    result = agent.run_waitlist_side_effects(
        code="NL-W001",
        topic="KYC/Onboarding",
        preference_raw="July 99",
    )
    assert result.succeeded == list(REQUIRED_WAITLIST_TOOLS)
    assert "calendar_create_hold" not in result.succeeded


def test_confirm_flow_invokes_actual_mcp_via_agent(
    engine: ConversationEngine,
    mock_google_apis,
) -> None:
    created = engine.create_session(channel="chat")
    sid = created.session_id
    engine.handle(sid, "I understand")
    engine.handle(sid, "book a new slot")
    engine.handle(sid, "SIP Mandates")
    engine.handle(sid, "July 15 morning")
    engine.handle(sid, "1")
    final = engine.handle(sid, "yes")

    assert final.state == SessionState.CLOSE
    assert final.meta.get("mcp_succeeded") == list(REQUIRED_BOOKING_TOOLS)
    assert final.meta.get("calendar_event_id") == "evt_test_123"
    assert "NL-" in " ".join(final.messages)
    assert "IST" in " ".join(final.messages)
    record = engine.booking_store.get(final.meta["booking_code"])
    assert record is not None
    assert record.calendar_event_id == "evt_test_123"


def test_partial_mcp_failure_still_returns_code(engine: ConversationEngine, mock_google_apis) -> None:
    # Break gmail only
    mock_google_apis["gmail"].users.return_value.drafts.return_value.create.return_value.execute.side_effect = (
        RuntimeError("503 unavailable")
    )

    created = engine.create_session(channel="chat")
    sid = created.session_id
    engine.handle(sid, "I understand")
    engine.handle(sid, "book a new slot")
    engine.handle(sid, "KYC Onboarding")
    engine.handle(sid, "July 15 morning")
    engine.handle(sid, "1")
    final = engine.handle(sid, "yes")

    assert final.state == SessionState.CLOSE
    assert "gmail_create_draft" in (final.meta.get("mcp_failed") or [])
    assert final.meta.get("booking_code")
    assert "NL-" in " ".join(final.messages)
