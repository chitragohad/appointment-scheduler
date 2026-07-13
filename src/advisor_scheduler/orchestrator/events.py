"""Analytics events (no PII)."""

from __future__ import annotations

from pydantic import BaseModel


class AnalyticsEvent(BaseModel):
    correlation_id: str
    session_id: str
    name: str
    from_state: str | None = None
    to_state: str | None = None
    intent: str | None = None
    mcp_tool: str | None = None
