"""Actual Google Calendar MCP tool implementations."""

from __future__ import annotations

from typing import Any

from advisor_scheduler.mcp_server import google_auth


def event_title(topic: str, code: str) -> str:
    return f"Advisor Q&A — {topic} — {code}"


def _find_event_by_code(service: Any, code: str) -> dict | None:
    cal_id = google_auth.calendar_id()
    # Search private extended property + title fallback
    events = (
        service.events()
        .list(
            calendarId=cal_id,
            privateExtendedProperty=f"bookingCode={code}",
            maxResults=5,
            singleEvents=True,
        )
        .execute()
        .get("items", [])
    )
    if events:
        return events[0]

    # Fallback: query by title fragment
    result = (
        service.events()
        .list(
            calendarId=cal_id,
            q=code,
            maxResults=10,
            singleEvents=True,
        )
        .execute()
        .get("items", [])
    )
    for item in result:
        if code in (item.get("summary") or ""):
            return item
    return None


def calendar_create_hold(
    code: str,
    topic: str,
    start_iso: str,
    end_iso: str,
) -> str:
    """Create a tentative Google Calendar hold; idempotent by booking code."""
    service = google_auth.get_service("calendar", "v3")
    existing = _find_event_by_code(service, code)
    body = {
        "summary": event_title(topic, code),
        "description": f"Tentative advisor pre-booking. Code: {code}. Topic: {topic}.",
        "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
        "status": "tentative",
        "extendedProperties": {"private": {"bookingCode": code}},
    }
    cal_id = google_auth.calendar_id()
    if existing:
        updated = (
            service.events()
            .update(calendarId=cal_id, eventId=existing["id"], body={**existing, **body})
            .execute()
        )
        return updated["id"]

    created = service.events().insert(calendarId=cal_id, body=body).execute()
    return created["id"]


def calendar_delete_hold(code: str, event_id: str | None = None) -> str:
    """Delete/cancel a tentative hold; idempotent by booking code."""
    service = google_auth.get_service("calendar", "v3")
    cal_id = google_auth.calendar_id()
    target_id = event_id
    if not target_id:
        existing = _find_event_by_code(service, code)
        if not existing:
            return f"no_event_for_{code}"
        target_id = existing["id"]
    try:
        service.events().delete(calendarId=cal_id, eventId=target_id).execute()
    except Exception as exc:  # noqa: BLE001
        # Already gone is success for idempotency
        if "404" not in str(exc) and "Not Found" not in str(exc):
            raise
    return target_id


def calendar_update_hold(
    code: str,
    event_id: str,
    start_iso: str,
    end_iso: str,
    topic: str,
) -> str:
    """Reschedule an existing hold on the real Google Calendar."""
    service = google_auth.get_service("calendar", "v3")
    cal_id = google_auth.calendar_id()
    existing = (
        service.events().get(calendarId=cal_id, eventId=event_id).execute()
        if event_id
        else _find_event_by_code(service, code)
    )
    if not existing:
        return calendar_create_hold(code, topic, start_iso, end_iso)

    existing["summary"] = event_title(topic, code)
    existing["start"] = {"dateTime": start_iso, "timeZone": "Asia/Kolkata"}
    existing["end"] = {"dateTime": end_iso, "timeZone": "Asia/Kolkata"}
    existing["status"] = "tentative"
    existing.setdefault("extendedProperties", {}).setdefault("private", {})["bookingCode"] = code
    updated = (
        service.events()
        .update(calendarId=cal_id, eventId=existing["id"], body=existing)
        .execute()
    )
    return updated["id"]
