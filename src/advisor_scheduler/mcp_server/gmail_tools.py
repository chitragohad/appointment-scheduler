"""Actual Gmail MCP tool implementations (draft-only, never send)."""

from __future__ import annotations

import base64
from email.message import EmailMessage

from advisor_scheduler.mcp_server import google_auth


def gmail_create_draft(subject: str, body: str, to: str | None = None) -> str:
    """Create a Gmail draft for human approval — never auto-sends."""
    service = google_auth.get_service("gmail", "v1")
    recipient = (to or google_auth.gmail_draft_to()).strip()
    if not recipient:
        raise google_auth.GoogleAuthError("GMAIL_DRAFT_TO or ADVISOR_EMAIL is required")

    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return draft.get("id", "")
