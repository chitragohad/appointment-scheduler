"""Chat HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from advisor_scheduler.api.schemas import CreateSessionRequest, MessageRequest, TurnResponse
from advisor_scheduler.orchestrator.engine import ConversationEngine

router = APIRouter()


def _engine(request: Request) -> ConversationEngine:
    return request.app.state.engine


@router.get("/")
def root() -> dict[str, str]:
    return {
        "service": "advisor-scheduler-api",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/sessions", response_model=TurnResponse)
def create_session(body: CreateSessionRequest, request: Request) -> TurnResponse:
    result = _engine(request).create_session(channel=body.channel)
    return TurnResponse(
        messages=result.messages,
        state=result.state.value,
        session_id=result.session_id,
        events=[e.model_dump() for e in result.events],
        meta=result.meta,
    )


@router.post("/sessions/{session_id}/message", response_model=TurnResponse)
def post_message(session_id: str, body: MessageRequest, request: Request) -> TurnResponse:
    engine = _engine(request)
    if engine.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    result = engine.handle(session_id, body.text)
    return TurnResponse(
        messages=result.messages,
        state=result.state.value,
        session_id=result.session_id,
        events=[e.model_dump() for e in result.events],
        meta=result.meta,
    )


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request) -> dict:
    session = _engine(request).get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")
