"""Google API credentials for actual Calendar / Docs / Gmail MCP tools."""

from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GoogleAuthError(RuntimeError):
    """Raised when Google credentials are missing or invalid."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(raw: str) -> Path:
    path = Path(raw.strip())
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _oauth_token_path() -> Path:
    raw = os.getenv("GOOGLE_OAUTH_TOKEN_PATH", ".secrets/google_token.json")
    return _resolve_path(raw)


def _is_serverless() -> bool:
    return bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def _load_json_env(*names: str) -> dict[str, Any] | None:
    for name in names:
        raw = os.getenv(name, "").strip()
        if not raw:
            continue
        try:
            if raw.startswith("{"):
                return json.loads(raw)
            # Allow base64-encoded JSON for easier Vercel pasting
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)
        except Exception as exc:  # noqa: BLE001
            raise GoogleAuthError(f"{name} is not valid JSON (or base64 JSON)") from exc
    return None


def get_credentials() -> Any:
    """
    Resolve credentials for Google Workspace APIs.

    Preference order:
    1. ``GOOGLE_APPLICATION_CREDENTIALS`` service-account JSON file
       or ``GOOGLE_SERVICE_ACCOUNT_JSON`` / ``GOOGLE_SERVICE_ACCOUNT_JSON_B64``
    2. ``GOOGLE_OAUTH_TOKEN_JSON`` / ``GOOGLE_OAUTH_TOKEN_JSON_B64`` (Vercel-friendly)
    3. OAuth installed-app client secrets file + local token cache (local only)
    """
    load_dotenv(_repo_root() / ".env")

    sa_info = _load_json_env("GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if sa_info or sa_path:
        if sa_info:
            creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        else:
            path = _resolve_path(sa_path)
            if not path.is_file():
                raise GoogleAuthError(f"Service account file not found: {path}")
            creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
        subject = os.getenv("GOOGLE_IMPERSONATE_USER", "").strip()
        if subject:
            creds = creds.with_subject(subject)
        return creds

    token_info = _load_json_env("GOOGLE_OAUTH_TOKEN_JSON", "GOOGLE_OAUTH_TOKEN_JSON_B64")
    if token_info:
        creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise GoogleAuthError(
                    "GOOGLE_OAUTH_TOKEN_JSON credentials are not valid "
                    "(missing refresh_token or client fields)."
                )
        return creds

    client_secrets = os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS", "").strip()
    if not client_secrets:
        raise GoogleAuthError(
            "Google credentials missing. On Vercel set GOOGLE_OAUTH_TOKEN_JSON "
            "(contents of .secrets/google_token.json) plus GOOGLE_CALENDAR_ID, "
            "GOOGLE_DOCS_PREBOOKINGS_ID, and GMAIL_DRAFT_TO."
        )

    secrets_path = _resolve_path(client_secrets)
    if not secrets_path.is_file():
        if _is_serverless():
            raise GoogleAuthError(
                "OAuth client secrets file is not available on Vercel. "
                "Set GOOGLE_OAUTH_TOKEN_JSON to your authorized-user token JSON."
            )
        raise GoogleAuthError(f"OAuth client secrets file not found: {secrets_path}")

    token_path = _oauth_token_path()
    creds: Credentials | None = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if _is_serverless():
                raise GoogleAuthError(
                    "No valid Google OAuth token on Vercel. "
                    "Set GOOGLE_OAUTH_TOKEN_JSON from a locally authorized token."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


@lru_cache(maxsize=8)
def get_service(api: str, version: str) -> Any:
    """Build a Google API service client (cached)."""
    return build(api, version, credentials=get_credentials(), cache_discovery=False)


def calendar_id() -> str:
    load_dotenv(_repo_root() / ".env")
    value = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
    if not value:
        raise GoogleAuthError("GOOGLE_CALENDAR_ID is required")
    return value


def docs_prebookings_id() -> str:
    load_dotenv(_repo_root() / ".env")
    value = os.getenv("GOOGLE_DOCS_PREBOOKINGS_ID", "").strip()
    if not value:
        raise GoogleAuthError("GOOGLE_DOCS_PREBOOKINGS_ID is required")
    return value


def gmail_draft_to() -> str:
    load_dotenv(_repo_root() / ".env")
    return (
        os.getenv("GMAIL_DRAFT_TO", "").strip()
        or os.getenv("ADVISOR_EMAIL", "").strip()
        or ""
    )


def google_config_status() -> dict[str, bool]:
    """Non-secret status for /health diagnostics."""
    load_dotenv(_repo_root() / ".env")
    return {
        "has_oauth_token_env": bool(
            os.getenv("GOOGLE_OAUTH_TOKEN_JSON", "").strip()
            or os.getenv("GOOGLE_OAUTH_TOKEN_JSON_B64", "").strip()
        ),
        "has_oauth_token_file": _oauth_token_path().is_file(),
        "has_service_account_env": bool(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "").strip()
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        ),
        "has_calendar_id": bool(os.getenv("GOOGLE_CALENDAR_ID", "").strip()),
        "has_docs_id": bool(os.getenv("GOOGLE_DOCS_PREBOOKINGS_ID", "").strip()),
        "has_gmail_to": bool(
            os.getenv("GMAIL_DRAFT_TO", "").strip() or os.getenv("ADVISOR_EMAIL", "").strip()
        ),
        "serverless": _is_serverless(),
    }


def clear_service_cache() -> None:
    get_service.cache_clear()
