"""Booking records and in-memory store keyed by booking code."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from advisor_scheduler.domain.topics import Topic


class BookingStatus(str, Enum):
    TENTATIVE = "tentative"
    WAITLIST = "waitlist"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class BookingRecord(BaseModel):
    code: str
    topic: Topic
    slot_id: str | None
    slot_start: datetime | None
    status: BookingStatus
    calendar_event_id: str | None
    secure_details_url: str
    created_at: datetime
    updated_at: datetime


class BookingStore:
    """Lightweight in-memory store for tentative / waitlist bookings."""

    def __init__(self) -> None:
        self._by_code: dict[str, BookingRecord] = {}

    def save(self, record: BookingRecord) -> None:
        self._by_code[record.code] = record.model_copy(deep=True)

    def get(self, code: str) -> BookingRecord | None:
        record = self._by_code.get(code)
        return record.model_copy(deep=True) if record else None

    def codes(self) -> set[str]:
        return set(self._by_code.keys())

    def delete(self, code: str) -> None:
        self._by_code.pop(code, None)
