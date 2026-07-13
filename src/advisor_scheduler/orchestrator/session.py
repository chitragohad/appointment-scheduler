"""Session state and in-memory session store."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from advisor_scheduler.domain.booking import BookingStatus
from advisor_scheduler.domain.intents import Intent
from advisor_scheduler.domain.slots import Slot, TimePreference
from advisor_scheduler.domain.topics import Topic


class SessionState(str, Enum):
    GREET = "greet"
    DISCLAIMER = "disclaimer"
    INTENT = "intent"
    TOPIC = "topic"
    PREFERENCE = "preference"
    OFFER_SLOTS = "offer_slots"
    CONFIRM = "confirm"
    ORCHESTRATE = "orchestrate"
    WAITLIST = "waitlist"
    CLOSE = "close"
    RESCHEDULE_LOOKUP = "reschedule_lookup"
    RESCHEDULE_PREFERENCE = "reschedule_preference"
    RESCHEDULE_OFFER = "reschedule_offer"
    RESCHEDULE_CONFIRM = "reschedule_confirm"
    CANCEL_LOOKUP = "cancel_lookup"
    CANCEL_CONFIRM = "cancel_confirm"
    PREPARE_TOPIC = "prepare_topic"
    AVAILABILITY = "availability"
    ADVICE_REFUSAL = "advice_refusal"
    ENDED = "ended"


class Session(BaseModel):
    session_id: str
    state: SessionState = SessionState.GREET
    disclaimer_acked_at: datetime | None = None
    intent: Intent | None = None
    topic: Topic | None = None
    preference: TimePreference | None = None
    offered_slots: list[Slot] = Field(default_factory=list)
    selected_slot: Slot | None = None
    booking_code: str | None = None
    booking_status: BookingStatus | None = None
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel: Literal["chat", "voice"] = "chat"


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, channel: Literal["chat", "voice"] = "chat") -> Session:
        session = Session(session_id=str(uuid.uuid4()), channel=channel)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        return session.model_copy(deep=True) if session else None

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session.model_copy(deep=True)
