"""Conversation engine — single handle(user_text, session) path."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
from typing import Literal

from advisor_scheduler.compliance import advice, disclaimer, pii
from advisor_scheduler.domain.booking import BookingRecord, BookingStatus, BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
from advisor_scheduler.domain.codes import generate_booking_code, normalize_code
from advisor_scheduler.domain.intents import Intent
from advisor_scheduler.domain.ist import IST, format_ist
from advisor_scheduler.domain.prepare_kb import format_preparation
from advisor_scheduler.domain.slots import find_slots
from advisor_scheduler.domain.topics import Topic
from advisor_scheduler.nlu.classify import classify
from advisor_scheduler.nlu.extract import (
    extract_preference,
    extract_slot_choice,
    extract_topic,
    extract_yes_no,
    looks_like_datetime_request,
    match_offered_slot_choice,
)
from advisor_scheduler.orchestrator.events import AnalyticsEvent
from advisor_scheduler.orchestrator.machine import TurnResult
from advisor_scheduler.orchestrator.session import Session, SessionState, SessionStore
from advisor_scheduler.secure_link import issue_secure_details_url

_TOPIC_PROMPT = (
    "Which consultation topic fits best? "
    "Say 1 KYC/Onboarding, 2 SIP/Mandates, 3 Statements/Tax Docs, "
    "4 Withdrawals & Timelines, or 5 Account Changes/Nominee."
)


class ConversationEngine:
    def __init__(
        self,
        *,
        calendar: MockCalendarService,
        booking_store: BookingStore | None = None,
        today_ist: date | None = None,
        booking_agent=None,
    ) -> None:
        from advisor_scheduler.agent.llm_agent import BookingAgent

        self.calendar = calendar
        self.booking_store = booking_store or BookingStore()
        self.sessions = SessionStore()
        self.today_ist = today_ist or datetime.now(tz=IST).date()
        self.booking_agent = booking_agent if booking_agent is not None else BookingAgent()

    def create_session(self, channel: Literal["chat", "voice"] = "chat") -> TurnResult:
        session = self.sessions.create(channel=channel)
        messages = [
            "Welcome to the Advisor Appointment Scheduler. I can help you reserve a "
            "tentative slot with a human advisor — no personal details needed on this chat.",
            disclaimer.script(),
        ]
        session.state = SessionState.DISCLAIMER
        self.sessions.save(session)
        return TurnResult(
            messages=messages,
            state=session.state,
            session_id=session.session_id,
            events=[
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="session_created",
                    to_state=session.state.value,
                )
            ],
            meta={},
        )

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def handle(self, session_id: str, user_text: str) -> TurnResult:
        session = self.sessions.get(session_id)
        if session is None:
            return TurnResult(
                messages=["Session not found. Please start a new session."],
                state=SessionState.ENDED,
                session_id=session_id,
            )

        events: list[AnalyticsEvent] = []
        text = user_text or ""

        # Global PII firewall
        if pii.detect(text):
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="pii_blocked",
                    from_state=session.state.value,
                    to_state=session.state.value,
                )
            )
            self.sessions.save(session)
            return TurnResult(
                messages=[pii.firewall_reply()],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        # Global advice refusal (after disclaimer ack, or anytime)
        nlu = classify(text, today_ist=self.today_ist)
        if advice.is_advice_request(text, nlu_is_advice=nlu.is_advice):
            prev = session.state
            session.state = SessionState.ADVICE_REFUSAL
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="advice_refused",
                    from_state=prev.value,
                    to_state=session.state.value,
                )
            )
            self.sessions.save(session)
            return TurnResult(
                messages=advice.refusal_messages(),
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        if session.state == SessionState.DISCLAIMER:
            return self._on_disclaimer(session, text, events)
        if session.state == SessionState.INTENT:
            return self._on_intent(session, text, nlu, events)
        if session.state == SessionState.TOPIC:
            return self._on_topic(session, text, events)
        if session.state == SessionState.PREFERENCE:
            return self._on_preference(session, text, events)
        if session.state == SessionState.OFFER_SLOTS:
            return self._on_offer_slots(session, text, events)
        if session.state == SessionState.CONFIRM:
            return self._on_confirm(session, text, events)
        if session.state == SessionState.RESCHEDULE_LOOKUP:
            return self._on_reschedule_lookup(session, text, events)
        if session.state == SessionState.RESCHEDULE_PREFERENCE:
            return self._on_reschedule_preference(session, text, events)
        if session.state == SessionState.RESCHEDULE_OFFER:
            return self._on_reschedule_offer(session, text, events)
        if session.state == SessionState.RESCHEDULE_CONFIRM:
            return self._on_reschedule_confirm(session, text, events)
        if session.state == SessionState.CANCEL_LOOKUP:
            return self._on_cancel_lookup(session, text, events)
        if session.state == SessionState.CANCEL_CONFIRM:
            return self._on_cancel_confirm(session, text, events)
        if session.state == SessionState.PREPARE_TOPIC:
            return self._on_prepare_topic(session, text, nlu, events)
        if session.state == SessionState.AVAILABILITY:
            return self._on_availability_followup(session, text, nlu, events)
        if session.state == SessionState.ADVICE_REFUSAL:
            return self._on_advice_return(session, text, nlu, events)
        if session.state in {SessionState.CLOSE, SessionState.ENDED}:
            return TurnResult(
                messages=["This booking session is complete. Start a new session to book again."],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        return TurnResult(
            messages=["Let’s start over — say book, reschedule, cancel, availability, or what to prepare."],
            state=SessionState.INTENT,
            session_id=session.session_id,
            events=events,
        )

    def _transition(self, session: Session, new_state: SessionState, events: list[AnalyticsEvent]) -> None:
        prev = session.state
        session.state = new_state
        events.append(
            AnalyticsEvent(
                correlation_id=session.correlation_id,
                session_id=session.session_id,
                name="state_transition",
                from_state=prev.value,
                to_state=new_state.value,
                intent=session.intent.value if session.intent else None,
            )
        )

    def _on_disclaimer(self, session: Session, text: str, events: list[AnalyticsEvent]) -> TurnResult:
        if not disclaimer.is_ack(text):
            return TurnResult(
                messages=[
                    "Please acknowledge the disclaimer before we continue "
                    '(reply "yes" or "I understand").',
                    disclaimer.script(),
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        session.disclaimer_acked_at = datetime.now(tz=IST)
        self._transition(session, SessionState.INTENT, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                "Thank you. How can I help — book a new slot, reschedule, cancel, "
                "check availability, or ask what to prepare?"
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
        )

    def _on_intent(
        self,
        session: Session,
        text: str,
        nlu,
        events: list[AnalyticsEvent],
    ) -> TurnResult:
        intent = nlu.intent
        if intent is None or nlu.confidence < 0.5:
            return TurnResult(
                messages=[
                    nlu.clarification_prompt
                    or "Please choose: book new, reschedule, cancel, availability, or what to prepare."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        session.intent = intent
        if intent == Intent.BOOK_NEW:
            self._transition(session, SessionState.TOPIC, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[_TOPIC_PROMPT],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"intent": intent.value},
            )

        if intent == Intent.RESCHEDULE:
            self._transition(session, SessionState.RESCHEDULE_LOOKUP, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[
                    "Sure — I can reschedule using your booking code only "
                    "(no phone lookup). Please type or say your code, e.g. NL-A742."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"intent": intent.value},
            )

        if intent == Intent.CANCEL:
            self._transition(session, SessionState.CANCEL_LOOKUP, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[
                    "I can cancel a tentative booking with your booking code only. "
                    "Please share the code (e.g. NL-A742)."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"intent": intent.value},
            )

        if intent == Intent.WHAT_TO_PREPARE:
            topic = nlu.topic or extract_topic(text)
            if topic:
                return self._emit_prepare(session, topic, events)
            self._transition(session, SessionState.PREPARE_TOPIC, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[f"Happy to help you prepare. {_TOPIC_PROMPT}"],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"intent": intent.value},
            )

        if intent == Intent.CHECK_AVAILABILITY:
            return self._emit_availability(session, events)

        self.sessions.save(session)
        return TurnResult(
            messages=["Please choose: book new, reschedule, cancel, availability, or what to prepare."],
            state=SessionState.INTENT,
            session_id=session.session_id,
            events=events,
        )

    def _on_topic(self, session: Session, text: str, events: list[AnalyticsEvent]) -> TurnResult:
        if session.disclaimer_acked_at is None:
            self._transition(session, SessionState.DISCLAIMER, events)
            self.sessions.save(session)
            return TurnResult(
                messages=["We need the disclaimer first.", disclaimer.script()],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        topic = extract_topic(text)
        if topic is None:
            return TurnResult(
                messages=[f"I didn’t catch a valid topic. {_TOPIC_PROMPT}"],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        session.topic = topic
        self._transition(session, SessionState.PREFERENCE, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                f"Topic set to {topic.value}. What day and exact time do you prefer in IST? "
                "For example: “July 16 at 10:00 am”, or a window like “July 15 morning”."
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={"topic": topic.value},
        )

    def _slots_for_preference(self, pref):
        """Resolve mock slots; mint an exact slot when the user named date + clock time."""
        slots = find_slots(pref, self.calendar, n=2)
        exact = pref.date_ist is not None and pref.exact_time_ist is not None
        if exact:
            if not slots:
                slots = [
                    self.calendar.ensure_exact_slot(pref.date_ist, pref.exact_time_ist)
                ]
            else:
                slots = slots[:1]
        return slots, exact

    def _ask_confirm_booking(
        self,
        session: Session,
        events: list[AnalyticsEvent],
        *,
        reschedule: bool = False,
    ) -> TurnResult:
        assert session.selected_slot is not None
        slot = session.selected_slot
        if reschedule:
            self._transition(session, SessionState.RESCHEDULE_CONFIRM, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[
                    f"I caught {format_ist(slot.start)} (IST) for {session.booking_code}. "
                    'Reply "yes" to confirm the reschedule, or "no" to pick again.'
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"selected_slot_id": slot.id},
            )
        self._transition(session, SessionState.CONFIRM, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                f"I caught {format_ist(slot.start)} (IST). "
                'Reply "yes" to confirm this booking, or "no" to pick again.'
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "selected_slot_id": slot.id,
                "selected_slot_start": slot.start.isoformat(),
            },
        )

    def _on_preference(self, session: Session, text: str, events: list[AnalyticsEvent]) -> TurnResult:
        pref = extract_preference(text, today_ist=self.today_ist)
        if pref is None or (pref.date_ist is None and pref.exact_time_ist is None):
            return TurnResult(
                messages=[
                    "Please share a day and time in IST. "
                    "For example: “July 16 at 10:00 am” or “July 15 morning”."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        session.preference = pref
        slots, exact = self._slots_for_preference(pref)
        if not slots:
            if pref.exact_time_ist is not None and pref.date_ist is None:
                when = pref.exact_time_ist.strftime("%H:%M")
                return TurnResult(
                    messages=[
                        f"I heard {when} IST, but need the day too. "
                        "For example: “July 16 at 10:00 am”."
                    ],
                    state=session.state,
                    session_id=session.session_id,
                    events=events,
                )
            return self._waitlist(session, events)

        if exact:
            session.offered_slots = slots
            session.selected_slot = slots[0]
            return self._ask_confirm_booking(session, events)

        session.offered_slots = slots
        self._transition(session, SessionState.OFFER_SLOTS, events)
        self.sessions.save(session)
        lines = [
            "Here are available slots matching what you said (IST):",
            f"1) {format_ist(slots[0].start)}",
            f"2) {format_ist(slots[1].start)}" if len(slots) > 1 else "",
            "Reply with 1 or 2, or say an exact date and time to confirm.",
        ]
        return TurnResult(
            messages=[m for m in lines if m],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "offered_slots": [
                    {"id": s.id, "start": s.start.isoformat(), "end": s.end.isoformat()}
                    for s in slots
                ]
            },
        )

    def _on_offer_slots(self, session: Session, text: str, events: list[AnalyticsEvent]) -> TurnResult:
        choice = match_offered_slot_choice(
            text,
            session.offered_slots,
            today_ist=self.today_ist,
        )
        if choice is None or choice > len(session.offered_slots):
            if looks_like_datetime_request(text, today_ist=self.today_ist):
                # User named a new exact date/time — restart preference resolution
                return self._on_preference(session, text, events)
            return TurnResult(
                messages=["Please choose slot 1 or 2, or say the exact date and time."],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={
                    "offered_slots": [
                        {"id": s.id, "start": s.start.isoformat(), "end": s.end.isoformat()}
                        for s in session.offered_slots
                    ]
                },
            )

        session.selected_slot = session.offered_slots[choice - 1]
        return self._ask_confirm_booking(session, events)

    def _on_confirm(self, session: Session, text: str, events: list[AnalyticsEvent]) -> TurnResult:
        decision = extract_yes_no(text)
        if decision == "no":
            # Start booking time selection over — ask for a new date/time
            session.selected_slot = None
            session.offered_slots = []
            session.preference = None
            self._transition(session, SessionState.PREFERENCE, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[
                    "No problem — let’s pick a different time. "
                    "What day and time do you prefer in IST? "
                    "For example: “July 16 at 10:00 am” or “July 15 morning”.",
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"topic": session.topic.value if session.topic else None},
            )
        if decision != "yes":
            return TurnResult(
                messages=[
                    'Please reply "yes" to confirm, or "no" / "pick again" to choose a new date/time.'
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        return self._orchestrate_confirm(session, events)

    def _orchestrate_confirm(self, session: Session, events: list[AnalyticsEvent]) -> TurnResult:
        assert session.selected_slot is not None
        assert session.topic is not None

        self._transition(session, SessionState.ORCHESTRATE, events)
        code = generate_booking_code(self.booking_store.codes())
        url = issue_secure_details_url(code)
        slot = session.selected_slot

        self.calendar.mark_held(slot.id)

        side = self.booking_agent.run_booking_side_effects(
            code=code,
            topic=session.topic.value,
            slot_start=slot.start,
            slot_end=slot.end,
            action="create",
        )
        for tool_name in side.succeeded:
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="mcp_success",
                    to_state=SessionState.ORCHESTRATE.value,
                    intent=session.intent.value if session.intent else None,
                    mcp_tool=tool_name,
                )
            )
        for tool_name in side.failed:
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="mcp_failure",
                    to_state=SessionState.ORCHESTRATE.value,
                    intent=session.intent.value if session.intent else None,
                    mcp_tool=tool_name,
                )
            )

        now = datetime.now(tz=IST)
        record = BookingRecord(
            code=code,
            topic=session.topic,
            slot_id=slot.id,
            slot_start=slot.start,
            status=BookingStatus.TENTATIVE,
            calendar_event_id=side.calendar_event_id,
            secure_details_url=url,
            created_at=now,
            updated_at=now,
        )
        self.booking_store.save(record)
        session.booking_code = code
        session.booking_status = BookingStatus.TENTATIVE
        self._transition(session, SessionState.CLOSE, events)
        self.sessions.save(session)

        messages = [
            f"Your tentative advisor slot is confirmed for {format_ist(slot.start)} (IST).",
            f"Booking code: {code}.",
            f"Complete your contact details later using this secure link: {url}",
            "No phone, email, or account numbers were collected in this chat.",
        ]
        if side.succeeded:
            messages.append(
                "Google side effects completed via MCP: " + ", ".join(side.succeeded) + "."
            )
        if side.failed:
            messages.append(
                "Some Google MCP steps could not complete: "
                + ", ".join(side.failed)
                + ". Your booking code is still valid; an advisor can finish sync manually."
            )

        return TurnResult(
            messages=messages,
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "booking_code": code,
                "secure_details_url": url,
                "slot_start": slot.start.isoformat(),
                "selected_slot_start": slot.start.isoformat(),
                "calendar_event_id": side.calendar_event_id,
                "mcp_succeeded": side.succeeded,
                "mcp_failed": side.failed,
                "mcp_errors": {
                    name: (data.get("error") if isinstance(data, dict) else None)
                    for name, data in side.tool_results.items()
                    if isinstance(data, dict) and data.get("error")
                },
            },
        )

    def _waitlist(self, session: Session, events: list[AnalyticsEvent]) -> TurnResult:
        self._transition(session, SessionState.WAITLIST, events)
        code = generate_booking_code(self.booking_store.codes())
        url = issue_secure_details_url(code)
        topic = session.topic or Topic.KYC_ONBOARDING
        pref_raw = session.preference.raw_text if session.preference else "unspecified"

        side = self.booking_agent.run_waitlist_side_effects(
            code=code,
            topic=topic.value,
            preference_raw=pref_raw,
        )
        for tool_name in side.succeeded:
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="mcp_success",
                    to_state=SessionState.WAITLIST.value,
                    mcp_tool=tool_name,
                )
            )
        for tool_name in side.failed:
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="mcp_failure",
                    to_state=SessionState.WAITLIST.value,
                    mcp_tool=tool_name,
                )
            )

        now = datetime.now(tz=IST)
        record = BookingRecord(
            code=code,
            topic=topic,
            slot_id=None,
            slot_start=None,
            status=BookingStatus.WAITLIST,
            calendar_event_id=None,
            secure_details_url=url,
            created_at=now,
            updated_at=now,
        )
        self.booking_store.save(record)
        session.booking_code = code
        session.booking_status = BookingStatus.WAITLIST
        self._transition(session, SessionState.CLOSE, events)
        self.sessions.save(session)

        messages = [
            "I couldn’t find matching available slots for that preference.",
            f"I’ve placed a waitlist hold. Reference code: {code}.",
            f"Use this secure link later for contact details: {url}",
        ]
        if side.failed:
            messages.append(
                "Waitlist Google MCP steps incomplete: " + ", ".join(side.failed) + "."
            )
        return TurnResult(
            messages=messages,
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "booking_code": code,
                "status": "waitlist",
                "mcp_succeeded": side.succeeded,
                "mcp_failed": side.failed,
            },
        )

    def _record_mcp_events(
        self,
        session: Session,
        events: list[AnalyticsEvent],
        side,
        *,
        to_state: str,
    ) -> None:
        for tool_name in side.succeeded:
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="mcp_success",
                    to_state=to_state,
                    intent=session.intent.value if session.intent else None,
                    mcp_tool=tool_name,
                )
            )
        for tool_name in side.failed:
            events.append(
                AnalyticsEvent(
                    correlation_id=session.correlation_id,
                    session_id=session.session_id,
                    name="mcp_failure",
                    to_state=to_state,
                    intent=session.intent.value if session.intent else None,
                    mcp_tool=tool_name,
                )
            )

    def _on_reschedule_lookup(
        self, session: Session, text: str, events: list[AnalyticsEvent]
    ) -> TurnResult:
        code = normalize_code(text)
        if not code:
            return TurnResult(
                messages=[
                    "I need your booking code only (no phone/email). "
                    "Example: NL-A742 or “N L dash A 7 4 2”."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        record = self.booking_store.get(code)
        if record is None:
            return TurnResult(
                messages=[
                    f"I couldn’t find booking {code}. Please check the code and try again."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        if record.status == BookingStatus.CANCELLED:
            return TurnResult(
                messages=[f"{code} is already cancelled and can’t be rescheduled."],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        session.booking_code = code
        session.topic = record.topic
        session.booking_status = record.status
        self._transition(session, SessionState.RESCHEDULE_PREFERENCE, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                f"Found {code} ({record.topic.value}). "
                "What new day/time do you prefer in IST? e.g. “July 16 morning”."
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={"booking_code": code},
        )

    def _on_reschedule_preference(
        self, session: Session, text: str, events: list[AnalyticsEvent]
    ) -> TurnResult:
        pref = extract_preference(text, today_ist=self.today_ist)
        if pref is None or (pref.date_ist is None and pref.exact_time_ist is None):
            return TurnResult(
                messages=[
                    "Please share a new day/time in IST, e.g. “July 16 at 10:00 am” "
                    "or “July 16 morning”."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        session.preference = pref
        slots, exact = self._slots_for_preference(pref)
        if not slots:
            if pref.exact_time_ist is not None and pref.date_ist is None:
                when = pref.exact_time_ist.strftime("%H:%M")
                return TurnResult(
                    messages=[
                        f"I heard {when} IST, but need the day too for reschedule. "
                        "For example: “July 16 at 10:00 am”."
                    ],
                    state=session.state,
                    session_id=session.session_id,
                    events=events,
                )
            return self._waitlist(session, events)

        if exact:
            session.offered_slots = slots
            session.selected_slot = slots[0]
            return self._ask_confirm_booking(session, events, reschedule=True)

        session.offered_slots = slots
        self._transition(session, SessionState.RESCHEDULE_OFFER, events)
        self.sessions.save(session)
        lines = [
            "Here are available slots matching what you said (IST):",
            f"1) {format_ist(slots[0].start)}",
            f"2) {format_ist(slots[1].start)}" if len(slots) > 1 else "",
            "Reply with 1 or 2, or say an exact date and time.",
        ]
        return TurnResult(
            messages=[m for m in lines if m],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "offered_slots": [
                    {"id": s.id, "start": s.start.isoformat()} for s in slots
                ]
            },
        )

    def _on_reschedule_offer(
        self, session: Session, text: str, events: list[AnalyticsEvent]
    ) -> TurnResult:
        choice = match_offered_slot_choice(
            text,
            session.offered_slots,
            today_ist=self.today_ist,
        )
        if choice is None or choice > len(session.offered_slots):
            if looks_like_datetime_request(text, today_ist=self.today_ist):
                return self._on_reschedule_preference(session, text, events)
            return TurnResult(
                messages=["Please choose slot 1 or 2, or say the exact date and time."],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        session.selected_slot = session.offered_slots[choice - 1]
        return self._ask_confirm_booking(session, events, reschedule=True)

    def _on_reschedule_confirm(
        self, session: Session, text: str, events: list[AnalyticsEvent]
    ) -> TurnResult:
        decision = extract_yes_no(text)
        if decision == "no":
            session.selected_slot = None
            session.offered_slots = []
            session.preference = None
            self._transition(session, SessionState.RESCHEDULE_PREFERENCE, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[
                    "Okay — let’s choose a different time for the reschedule. "
                    "What new day/time do you prefer in IST? "
                    "For example: “July 16 at 10:00 am” or “July 16 morning”.",
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
                meta={"booking_code": session.booking_code},
            )
        if decision != "yes":
            return TurnResult(
                messages=[
                    'Please reply "yes" to confirm the reschedule, or "no" / "pick again" '
                    "for a new date/time."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        assert session.booking_code and session.selected_slot and session.topic
        code = session.booking_code
        record = self.booking_store.get(code)
        assert record is not None
        slot = session.selected_slot

        if record.slot_id:
            try:
                self.calendar.release(record.slot_id)
            except KeyError:
                pass
        self.calendar.mark_held(slot.id)

        side = self.booking_agent.run_reschedule_side_effects(
            code=code,
            topic=session.topic.value,
            slot_start=slot.start,
            slot_end=slot.end,
            event_id=record.calendar_event_id,
        )
        self._record_mcp_events(session, events, side, to_state=SessionState.RESCHEDULE_CONFIRM.value)

        now = datetime.now(tz=IST)
        updated = record.model_copy(
            update={
                "slot_id": slot.id,
                "slot_start": slot.start,
                "status": BookingStatus.RESCHEDULED,
                "calendar_event_id": side.calendar_event_id or record.calendar_event_id,
                "updated_at": now,
            }
        )
        self.booking_store.save(updated)
        session.booking_status = BookingStatus.RESCHEDULED
        self._transition(session, SessionState.CLOSE, events)
        self.sessions.save(session)

        messages = [
            f"Rescheduled {code} to {format_ist(slot.start)} (IST).",
            f"Your booking code remains {code}.",
            f"Secure details link: {record.secure_details_url}",
        ]
        if side.failed:
            messages.append("Some Google MCP steps failed: " + ", ".join(side.failed) + ".")
        return TurnResult(
            messages=messages,
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "booking_code": code,
                "mcp_succeeded": side.succeeded,
                "mcp_failed": side.failed,
            },
        )

    def _on_cancel_lookup(
        self, session: Session, text: str, events: list[AnalyticsEvent]
    ) -> TurnResult:
        code = normalize_code(text)
        if not code:
            return TurnResult(
                messages=[
                    "Please share the booking code only (e.g. NL-A742). "
                    "I won’t ask for a phone number."
                ],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        record = self.booking_store.get(code)
        if record is None:
            return TurnResult(
                messages=[f"No booking found for {code}. Please re-check the code."],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        if record.status == BookingStatus.CANCELLED:
            return TurnResult(
                messages=[f"{code} is already cancelled."],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        session.booking_code = code
        session.topic = record.topic
        self._transition(session, SessionState.CANCEL_CONFIRM, events)
        self.sessions.save(session)
        slot_txt = format_ist(record.slot_start) if record.slot_start else "waitlist/unscheduled"
        return TurnResult(
            messages=[
                f"Cancel booking {code} ({record.topic.value}, {slot_txt})? "
                'Reply "yes" to confirm cancellation.'
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={"booking_code": code},
        )

    def _on_cancel_confirm(
        self, session: Session, text: str, events: list[AnalyticsEvent]
    ) -> TurnResult:
        decision = extract_yes_no(text)
        if decision != "yes":
            if decision == "no":
                self._transition(session, SessionState.INTENT, events)
                self.sessions.save(session)
                return TurnResult(
                    messages=["Okay — cancellation aborted. How else can I help?"],
                    state=session.state,
                    session_id=session.session_id,
                    events=events,
                )
            return TurnResult(
                messages=['Please reply "yes" to cancel or "no" to keep the booking.'],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        assert session.booking_code
        code = session.booking_code
        record = self.booking_store.get(code)
        assert record is not None

        if record.slot_id:
            try:
                self.calendar.release(record.slot_id)
            except KeyError:
                pass

        slot_label = format_ist(record.slot_start) if record.slot_start else "cancelled"
        side = self.booking_agent.run_cancel_side_effects(
            code=code,
            topic=record.topic.value,
            event_id=record.calendar_event_id,
            slot_label=slot_label,
        )
        self._record_mcp_events(session, events, side, to_state=SessionState.CANCEL_CONFIRM.value)

        now = datetime.now(tz=IST)
        self.booking_store.save(
            record.model_copy(
                update={
                    "status": BookingStatus.CANCELLED,
                    "updated_at": now,
                    "slot_id": None,
                }
            )
        )
        session.booking_status = BookingStatus.CANCELLED
        self._transition(session, SessionState.CLOSE, events)
        self.sessions.save(session)

        messages = [
            f"Booking {code} has been cancelled.",
            "No personal contact details were required for this cancellation.",
        ]
        if side.failed:
            messages.append("Some Google MCP steps failed: " + ", ".join(side.failed) + ".")
        return TurnResult(
            messages=messages,
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "booking_code": code,
                "status": "cancelled",
                "mcp_succeeded": side.succeeded,
                "mcp_failed": side.failed,
            },
        )

    def _emit_prepare(
        self, session: Session, topic: Topic, events: list[AnalyticsEvent]
    ) -> TurnResult:
        session.topic = topic
        session.intent = Intent.WHAT_TO_PREPARE
        self._transition(session, SessionState.PREPARE_TOPIC, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                format_preparation(topic),
                'Would you like to book a tentative slot for this topic? Say "book a new slot".',
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={"topic": topic.value, "intent": Intent.WHAT_TO_PREPARE.value},
        )

    def _on_prepare_topic(
        self, session: Session, text: str, nlu, events: list[AnalyticsEvent]
    ) -> TurnResult:
        lowered = text.lower()
        explicit_book = bool(
            re.search(r"\bbook\b", lowered)
            or re.search(r"\bschedule\b", lowered)
            or re.search(r"\breserve\b", lowered)
        )
        if explicit_book:
            session.intent = Intent.BOOK_NEW
            if session.topic:
                self._transition(session, SessionState.PREFERENCE, events)
                self.sessions.save(session)
                return TurnResult(
                    messages=[
                        f"Great — continuing with {session.topic.value}. "
                        "What day/time do you prefer in IST?"
                    ],
                    state=session.state,
                    session_id=session.session_id,
                    events=events,
                )
            self._transition(session, SessionState.TOPIC, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[_TOPIC_PROMPT],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )

        topic = extract_topic(text)
        if topic is None:
            return TurnResult(
                messages=[f"Please pick a topic. {_TOPIC_PROMPT}"],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        return self._emit_prepare(session, topic, events)

    def _emit_availability(
        self, session: Session, events: list[AnalyticsEvent]
    ) -> TurnResult:
        session.intent = Intent.CHECK_AVAILABILITY
        available = self.calendar.list_available()[:5]
        self._transition(session, SessionState.AVAILABILITY, events)
        self.sessions.save(session)
        if not available:
            messages = [
                "There are no available mock-calendar windows right now.",
                'Say "book a new slot" to join the waitlist flow, or try again later.',
            ]
        else:
            lines = ["Next available windows (IST):"]
            for idx, slot in enumerate(available, start=1):
                lines.append(f"{idx}) {format_ist(slot.start)}")
            lines.append(
                'Want to reserve one? Say "book a new slot" and I’ll walk you through topics.'
            )
            messages = lines
        return TurnResult(
            messages=messages,
            state=session.state,
            session_id=session.session_id,
            events=events,
            meta={
                "intent": Intent.CHECK_AVAILABILITY.value,
                "windows": [s.start.isoformat() for s in available],
            },
        )

    def _on_availability_followup(
        self, session: Session, text: str, nlu, events: list[AnalyticsEvent]
    ) -> TurnResult:
        if nlu.intent == Intent.BOOK_NEW or "book" in text.lower():
            session.intent = Intent.BOOK_NEW
            self._transition(session, SessionState.TOPIC, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[_TOPIC_PROMPT],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        if nlu.intent == Intent.CHECK_AVAILABILITY or "again" in text.lower():
            return self._emit_availability(session, events)
        self._transition(session, SessionState.INTENT, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                "You can book a new slot, reschedule, cancel, check availability again, "
                "or ask what to prepare."
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
        )

    def _on_advice_return(self, session: Session, text: str, nlu, events: list[AnalyticsEvent]) -> TurnResult:
        # Allow pivoting back to booking
        if nlu.intent == Intent.BOOK_NEW or extract_yes_no(text) == "yes" or "book" in text.lower():
            session.intent = Intent.BOOK_NEW
            self._transition(session, SessionState.TOPIC, events)
            self.sessions.save(session)
            return TurnResult(
                messages=[_TOPIC_PROMPT],
                state=session.state,
                session_id=session.session_id,
                events=events,
            )
        self._transition(session, SessionState.INTENT, events)
        self.sessions.save(session)
        return TurnResult(
            messages=[
                "Would you like to book a tentative advisor slot instead? "
                "Say “book a new slot” to continue."
            ],
            state=session.state,
            session_id=session.session_id,
            events=events,
        )


def default_engine(*, today_ist: date | None = None) -> ConversationEngine:
    root = Path(__file__).resolve().parents[3]
    import os

    path = Path(os.getenv("MOCK_CALENDAR_PATH", str(root / "data" / "mock_calendar.json")))
    if not path.is_absolute():
        path = root / path
    return ConversationEngine(
        calendar=MockCalendarService.load(path),
        today_ist=today_ist,
    )
