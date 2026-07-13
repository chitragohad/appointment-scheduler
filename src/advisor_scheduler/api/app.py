"""FastAPI application factory."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from advisor_scheduler.agent.llm_agent import BookingAgent
from advisor_scheduler.api.chat import router
from advisor_scheduler.domain.booking import BookingStore
from advisor_scheduler.domain.calendar_mock import MockCalendarService
from advisor_scheduler.orchestrator.engine import ConversationEngine


def _calendar_path() -> Path:
    import os

    load_dotenv()
    root = Path(__file__).resolve().parents[3]
    raw = os.getenv("MOCK_CALENDAR_PATH", "data/mock_calendar.json")
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path


def create_app(*, today_ist: date | None = None, booking_agent: BookingAgent | None = None) -> FastAPI:
    load_dotenv()
    app = FastAPI(title="Advisor Appointment Scheduler", version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    engine = ConversationEngine(
        calendar=MockCalendarService.load(_calendar_path()),
        booking_store=BookingStore(),
        today_ist=today_ist,
        booking_agent=booking_agent if booking_agent is not None else BookingAgent(),
    )
    app.state.engine = engine
    app.include_router(router)
    return app


app = create_app()
