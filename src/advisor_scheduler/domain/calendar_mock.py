"""Mock advisor calendar loaded from JSON (slot picking source of truth)."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path

from advisor_scheduler.domain.ist import IST
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

    def ensure_exact_slot(
        self,
        date_ist: date,
        time_ist: time,
        *,
        duration_minutes: int = 30,
    ) -> Slot:
        """
        Return an available slot at the exact IST start, creating one if needed.

        Used when the caller names a precise date and time so booking can proceed
        even if that moment was not pre-seeded in the mock calendar JSON.
        """
        start = datetime.combine(date_ist, time_ist, tzinfo=IST)
        end = start + timedelta(minutes=duration_minutes)
        for slot in self._slots.values():
            local = slot.start if slot.start.tzinfo else slot.start.replace(tzinfo=IST)
            local = local.astimezone(IST)
            if local.replace(second=0, microsecond=0) != start:
                continue
            if slot.status == "available":
                return slot.model_copy(deep=True)
            # Held/waitlist at same instant — mint a distinct bookable id
            break

        slot_id = f"slot_{date_ist.strftime('%Y%m%d')}_{time_ist.strftime('%H%M')}"
        if slot_id in self._slots:
            suffix = 1
            while f"{slot_id}_{suffix}" in self._slots:
                suffix += 1
            slot_id = f"{slot_id}_{suffix}"
        created = Slot(id=slot_id, start=start, end=end, status="available")
        self._slots[slot_id] = created
        return created.model_copy(deep=True)

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
