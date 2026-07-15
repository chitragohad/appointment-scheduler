#!/usr/bin/env python3
"""Export Google env values for Vercel (writes a gitignored local file)."""

from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
TOKEN_PATH = ROOT / ".secrets" / "google_token.json"
OUT_PATH = ROOT / ".secrets" / "vercel_google_env.txt"


def _env_get(key: str) -> str:
    if not ENV_PATH.is_file():
        return ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def main() -> None:
    if not TOKEN_PATH.is_file():
        raise SystemExit(f"Missing {TOKEN_PATH}. Run local OAuth once first.")

    token_raw = TOKEN_PATH.read_text(encoding="utf-8").strip()
    token_b64 = base64.b64encode(token_raw.encode("utf-8")).decode("ascii")

    lines = [
        "# Paste these into Vercel → API project → Settings → Environment Variables",
        "# File is gitignored. Do not commit or share.",
        "",
        f"GOOGLE_OAUTH_TOKEN_JSON={token_raw}",
        "",
        "# Alternative (same value, base64) if the JSON one-liner is awkward in the UI:",
        f"GOOGLE_OAUTH_TOKEN_JSON_B64={token_b64}",
        "",
        f"GOOGLE_CALENDAR_ID={_env_get('GOOGLE_CALENDAR_ID')}",
        f"GOOGLE_DOCS_PREBOOKINGS_ID={_env_get('GOOGLE_DOCS_PREBOOKINGS_ID')}",
        f"GMAIL_DRAFT_TO={_env_get('GMAIL_DRAFT_TO') or _env_get('ADVISOR_EMAIL')}",
        f"ADVISOR_EMAIL={_env_get('ADVISOR_EMAIL') or _env_get('GMAIL_DRAFT_TO')}",
        "",
        "# After saving env vars, Redeploy the API project, then open:",
        "#   https://YOUR-API.vercel.app/health/google",
        "# Expect ready=true",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print("Open that file locally and paste values into Vercel (API project).")


if __name__ == "__main__":
    main()
