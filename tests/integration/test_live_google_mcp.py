"""Live Google MCP integration — skipped unless credentials are configured."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from dotenv import load_dotenv

load_dotenv()

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[2]


def _live_google_configured() -> bool:
    has_creds = bool(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS")
    )
    has_ids = bool(
        os.getenv("GOOGLE_CALENDAR_ID")
        and os.getenv("GOOGLE_DOCS_PREBOOKINGS_ID")
        and (os.getenv("GMAIL_DRAFT_TO") or os.getenv("ADVISOR_EMAIL"))
    )
    # Avoid treating empty placeholder paths as configured
    sa = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    oauth = os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "").strip()
    path_ok = (sa and Path(sa).is_file()) or (oauth and Path(oauth).is_file())
    return has_creds and has_ids and path_ok


pytestmark = pytest.mark.skipif(
    not _live_google_configured(),
    reason="Live Google credentials / IDs not configured",
)


def test_live_mcp_booking_side_effects() -> None:
    from advisor_scheduler.agent.llm_agent import BookingAgent
    from advisor_scheduler.mcp_client.google_mcp import GoogleMcpClient
    from advisor_scheduler.mcp_server.google_auth import clear_service_cache
    from advisor_scheduler.mcp_server.server import create_mcp

    clear_service_cache()
    agent = BookingAgent(mcp=GoogleMcpClient(mcp=create_mcp()))
    start = datetime.now(tz=IST) + timedelta(days=2)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=30)
    code = f"NL-T{start.strftime('%H%M')}"[:7].ljust(7, "0")
    # Ensure NL-XXXX pattern
    code = f"NL-T{start.day:02d}{start.hour:01d}"[:7]
    if len(code) < 7:
        code = (code + "0000")[:7]
    # Force valid pattern NL- + 4
    code = f"NL-{start.strftime('%d%H')}"

    result = agent.run_booking_side_effects(
        code=code,
        topic="KYC/Onboarding",
        slot_start=start,
        slot_end=end,
        action="create",
    )
    assert result.failed == [], result.tool_results
    assert result.calendar_event_id
    assert result.docs_ok
    assert result.gmail_draft_id
