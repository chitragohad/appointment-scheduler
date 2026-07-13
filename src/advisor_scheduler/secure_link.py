"""Secure URL issuer for post-session contact details (no PII in-session)."""

from __future__ import annotations

import hashlib
import hmac
import os
from urllib.parse import urlencode


def issue_secure_details_url(code: str) -> str:
    """
    Build a secure details URL for completing contact info off-session.

    Uses ``SECURE_LINK_BASE`` and optional ``SECURE_LINK_SECRET`` for a simple
    HMAC token (placeholder until PM locks the issuer model).
    """
    base = os.getenv("SECURE_LINK_BASE", "https://example.com/prebook").rstrip("/")
    secret = os.getenv("SECURE_LINK_SECRET", "")

    path = f"{base}/{code}"
    if not secret:
        return path

    token = hmac.new(
        secret.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"{path}?{urlencode({'t': token})}"
