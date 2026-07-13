"""Booking code generation, normalization, and TTS spelling."""

from __future__ import annotations

import re
import secrets
import string

BOOKING_CODE_PATTERN = re.compile(r"^NL-[A-Z0-9]{4}$")
_ALPHANUM = string.ascii_uppercase + string.digits


def generate_booking_code(existing: set[str] | None = None) -> str:
    """Generate ``NL-`` + 4 alphanumeric chars, avoiding collisions in ``existing``."""
    existing = existing or set()
    for _ in range(10_000):
        suffix = "".join(secrets.choice(_ALPHANUM) for _ in range(4))
        code = f"NL-{suffix}"
        if code not in existing:
            return code
    raise RuntimeError("Unable to generate a unique booking code")


def normalize_code(text: str) -> str | None:
    """Normalize typed or spoken booking codes to ``NL-XXXX``."""
    if not text or not text.strip():
        return None

    # Prefer an embedded NL-XXXX / spoken form anywhere in the utterance
    embedded = re.search(
        r"\bN\s*L\s*(?:DASH|-)?\s*([A-Z0-9](?:\s*[A-Z0-9]){3})\b",
        text.upper(),
    )
    if embedded:
        suffix = re.sub(r"\s+", "", embedded.group(1))
        candidate = f"NL-{suffix}"
        if BOOKING_CODE_PATTERN.match(candidate):
            return candidate

    cleaned = text.strip().upper()
    cleaned = cleaned.replace("DASH", "-")
    cleaned = re.sub(r"[^A-Z0-9\-]", "", cleaned)

    if BOOKING_CODE_PATTERN.match(cleaned):
        return cleaned

    compact = re.sub(r"[^A-Z0-9]", "", cleaned)
    match = re.search(r"NL([A-Z0-9]{4})", compact)
    if match:
        candidate = f"NL-{match.group(1)}"
        if BOOKING_CODE_PATTERN.match(candidate):
            return candidate

    return None


def spell_code_for_tts(code: str) -> str:
    """Spell booking code for TTS, e.g. ``NL-A742`` → ``N L dash A 7 4 2``."""
    normalized = normalize_code(code) or code.upper()
    parts: list[str] = []
    for ch in normalized:
        if ch == "-":
            parts.append("dash")
        else:
            parts.append(ch)
    return " ".join(parts)
