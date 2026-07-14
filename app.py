"""Vercel / local ASGI entry — ensures ``src/`` is importable."""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from advisor_scheduler.api.app import app

__all__ = ["app"]
