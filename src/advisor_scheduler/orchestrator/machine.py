"""Turn result and allowed state transitions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from advisor_scheduler.orchestrator.events import AnalyticsEvent
from advisor_scheduler.orchestrator.session import SessionState

ALLOWED_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.GREET: {SessionState.DISCLAIMER},
    SessionState.DISCLAIMER: {SessionState.INTENT, SessionState.ADVICE_REFUSAL},
    SessionState.INTENT: {
        SessionState.TOPIC,
        SessionState.ADVICE_REFUSAL,
        SessionState.RESCHEDULE_LOOKUP,
        SessionState.CANCEL_LOOKUP,
        SessionState.PREPARE_TOPIC,
        SessionState.AVAILABILITY,
        SessionState.INTENT,
    },
    SessionState.TOPIC: {SessionState.PREFERENCE, SessionState.TOPIC, SessionState.ADVICE_REFUSAL},
    SessionState.PREFERENCE: {
        SessionState.OFFER_SLOTS,
        SessionState.WAITLIST,
        SessionState.PREFERENCE,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.OFFER_SLOTS: {
        SessionState.CONFIRM,
        SessionState.PREFERENCE,
        SessionState.OFFER_SLOTS,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.CONFIRM: {
        SessionState.ORCHESTRATE,
        SessionState.CLOSE,
        SessionState.OFFER_SLOTS,
        SessionState.CONFIRM,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.ORCHESTRATE: {SessionState.CLOSE},
    SessionState.WAITLIST: {SessionState.CLOSE},
    SessionState.CLOSE: {SessionState.ENDED},
    SessionState.ADVICE_REFUSAL: {
        SessionState.INTENT,
        SessionState.TOPIC,
        SessionState.ADVICE_REFUSAL,
        SessionState.ENDED,
    },
    SessionState.RESCHEDULE_LOOKUP: {
        SessionState.RESCHEDULE_PREFERENCE,
        SessionState.RESCHEDULE_LOOKUP,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.RESCHEDULE_PREFERENCE: {
        SessionState.RESCHEDULE_OFFER,
        SessionState.RESCHEDULE_PREFERENCE,
        SessionState.WAITLIST,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.RESCHEDULE_OFFER: {
        SessionState.RESCHEDULE_CONFIRM,
        SessionState.RESCHEDULE_OFFER,
        SessionState.RESCHEDULE_PREFERENCE,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.RESCHEDULE_CONFIRM: {
        SessionState.CLOSE,
        SessionState.RESCHEDULE_OFFER,
        SessionState.RESCHEDULE_CONFIRM,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.CANCEL_LOOKUP: {
        SessionState.CANCEL_CONFIRM,
        SessionState.CANCEL_LOOKUP,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.CANCEL_CONFIRM: {
        SessionState.CLOSE,
        SessionState.CANCEL_CONFIRM,
        SessionState.INTENT,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.PREPARE_TOPIC: {
        SessionState.PREPARE_TOPIC,
        SessionState.TOPIC,
        SessionState.INTENT,
        SessionState.ADVICE_REFUSAL,
    },
    SessionState.AVAILABILITY: {
        SessionState.TOPIC,
        SessionState.INTENT,
        SessionState.AVAILABILITY,
        SessionState.ADVICE_REFUSAL,
    },
}


class TurnResult(BaseModel):
    messages: list[str]
    state: SessionState
    session_id: str
    events: list[AnalyticsEvent] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


def can_transition(current: SessionState, nxt: SessionState) -> bool:
    if current == nxt:
        return True
    return nxt in ALLOWED_TRANSITIONS.get(current, set())
