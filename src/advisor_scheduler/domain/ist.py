"""IST display helpers — all user-facing times include timezone label."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def format_ist(dt: datetime) -> str:
    """Format a datetime for users: full date + time + 'IST'."""
    if dt.tzinfo is None:
        local = dt.replace(tzinfo=IST)
    else:
        local = dt.astimezone(IST)
    # Example: Wednesday, 15 July 2026, 10:00 IST
    return local.strftime("%A, %d %B %Y, %H:%M IST")
