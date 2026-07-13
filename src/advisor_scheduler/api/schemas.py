"""HTTP schemas for the chat harness."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    channel: Literal["chat", "voice"] = "chat"


class MessageRequest(BaseModel):
    text: str = Field(..., min_length=0)


class TurnResponse(BaseModel):
    messages: list[str]
    state: str
    session_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
