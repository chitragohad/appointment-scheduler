"""Shared fixtures — mock Google API boundary for unit tests (actual MCP tools still run)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from advisor_scheduler.mcp_server import google_auth


@pytest.fixture
def mock_google_apis(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """
    Patch Google API service clients so FastMCP tools execute without live credentials.

    This is not FakeMCP — the MCP tool path and agent still run; only the Google HTTP
    transport is stubbed for unit tests.
    """
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "primary")
    monkeypatch.setenv("GOOGLE_DOCS_PREBOOKINGS_ID", "doc-prebookings")
    monkeypatch.setenv("GMAIL_DRAFT_TO", "advisor@example.com")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/unused-sa.json")

    calendar = MagicMock(name="calendar")
    docs = MagicMock(name="docs")
    gmail = MagicMock(name="gmail")

    # Calendar: no existing event; insert returns id
    calendar.events.return_value.list.return_value.execute.return_value = {"items": []}
    calendar.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt_test_123"
    }
    calendar.events.return_value.update.return_value.execute.return_value = {
        "id": "evt_test_123"
    }
    calendar.events.return_value.delete.return_value.execute.return_value = None
    calendar.events.return_value.get.return_value.execute.return_value = {
        "id": "evt_test_123",
        "summary": "old",
        "extendedProperties": {"private": {}},
    }

    # Docs
    docs.documents.return_value.get.return_value.execute.return_value = {
        "body": {"content": [{"endIndex": 2}]}
    }
    docs.documents.return_value.batchUpdate.return_value.execute.return_value = {}

    # Gmail draft
    gmail.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "id": "draft_test_456"
    }

    services = {"calendar": calendar, "docs": docs, "gmail": gmail}

    def _get_service(api: str, version: str):
        if api not in services:
            raise AssertionError(f"Unexpected Google API: {api}")
        return services[api]

    google_auth.clear_service_cache()
    monkeypatch.setattr(google_auth, "get_service", _get_service)
    return services
