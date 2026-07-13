"""NLU result contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from advisor_scheduler.domain.intents import Intent
from advisor_scheduler.domain.slots import TimePreference
from advisor_scheduler.domain.topics import Topic


class NluResult(BaseModel):
    intent: Intent | None = None
    confidence: float = 0.0
    topic: Topic | None = None
    preference_raw: str | None = None
    preference: TimePreference | None = None
    confirmation: Literal["yes", "no", "unknown"] | None = None
    slot_choice: Literal[1, 2] | None = None
    is_advice: bool = False
    needs_clarification: bool = False
    clarification_prompt: str | None = None
