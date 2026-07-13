"""Actual Google Docs MCP tool implementations."""

from __future__ import annotations

from advisor_scheduler.mcp_server import google_auth


def docs_append_prebooking(
    date: str,
    topic: str,
    slot: str,
    code: str,
    action: str = "create",
) -> str:
    """Append a line to the Advisor Pre-Bookings Google Doc."""
    service = google_auth.get_service("docs", "v1")
    doc_id = google_auth.docs_prebookings_id()
    line = f"{date} | {topic} | {slot} | {code} | {action}\n"

    # Insert at end of document body
    doc = service.documents().get(documentId=doc_id).execute()
    end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1)
    # endIndex points past last content; insert just before final newline
    insert_at = max(1, end_index - 1)

    service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {"index": insert_at},
                        "text": line,
                    }
                }
            ]
        },
    ).execute()
    return f"appended:{code}:{action}"
