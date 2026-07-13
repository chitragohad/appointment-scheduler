"""Intent taxonomy."""

from __future__ import annotations

from enum import Enum


class Intent(str, Enum):
    BOOK_NEW = "book_new"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    WHAT_TO_PREPARE = "what_to_prepare"
    CHECK_AVAILABILITY = "check_availability"
