"""Mock advisor calendar loaded from JSON (slot picking source of truth)."""

from __future__ import annotations

import json
from pathlib import Path

from advisor_scheduler.domain.slots import Slot


class MockCalendarService:
    """In-memory calendar backed by ``data/mock_calendar.json``."""

    def __init__(self, slots: list[Slot], timezone: str = "Asia/Kolkata") -> None:
        self.timezone = timezone
        self._slots: dict[str, Slot] = {s.id: s.model_copy(deep=True) for s in slots}

    @classmethod
    def load(cls, path: str | Path) -> MockCalendarService:
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        slots = [Slot.model_validate(item) for item in raw.get("slots", [])]
        return cls(slots=slots, timezone=raw.get("timezone", "Asia/Kolkata"))

    def all_slots(self) -> list[Slot]:
        return [s.model_copy(deep=True) for s in self._slots.values()]

    def list_available(self) -> list[Slot]:
        return [
            s.model_copy(deep=True)
            for s in sorted(self._slots.values(), key=lambda x: x.start)
            if s.status == "available"
        ]

    def get(self, slot_id: str) -> Slot | None:
        slot = self._slots.get(slot_id)
        return slot.model_copy(deep=True) if slot else None

    def mark_held(self, slot_id: str) -> None:
        slot = self._slots.get(slot_id)
        if slot is None:
            raise KeyError(f"Unknown slot id: {slot_id}")
        self._slots[slot_id] = slot.model_copy(update={"status": "held"})

    def release(self, slot_id: str) -> None:
        slot = self._slots.get(slot_id)
        if slot is None:
            raise KeyError(f"Unknown slot id: {slot_id}")
        self._slots[slot_id] = slot.model_copy(update={"status": "available"})

    def mark_waitlist(self, slot_id: str) -> None:
        slot = self._slots.get(slot_id)
        if slot is None:
            raise KeyError(f"Unknown slot id: {slot_id}")
        self._slots[slot_id] = slot.model_copy(update={"status": "waitlist"})
