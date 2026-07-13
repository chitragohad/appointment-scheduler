# Advisor Appointment Scheduler

Compliant pre-booking assistant (chat-first, voice later). See `context.md`, `architecture.md`, and `architecture-low-level.md`.

## Status

| Phase | Status |
|-------|--------|
| 1 Domain + mock calendar | Done |
| 2 Chat orchestrator + compliance + NLU | Done |
| 3 Actual Google MCP via LLM agent | Done |
| 4 Secondary intents | Done |
| 5 Voice UI (Stitch Acoustic Serenity) | Done (browser STT/TTS) |

## Setup

Requires **Python 3.10+** (3.12 recommended).

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
```

## Run chat

```bash
python -m advisor_scheduler
python -m advisor_scheduler --serve
```

## Run voice UI (frontend)

Design system: Stitch **Acoustic Serenity** (`stitch_voice_concierge_scheduler/acoustic_serenity/DESIGN.md`).

```bash
# Terminal 1 — API (CORS allows Vite)
source .venv/bin/activate
python -m advisor_scheduler --serve --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:5173 — tap the voice orb or use suggestion chips / text fallback. Chrome works best for Web Speech API.

### Intents (all five)

| Intent | Example utterances |
|--------|-------------------|
| Book new | `book a new slot` → topic → `July 15 morning` → `1` → `yes` |
| Reschedule | `reschedule` → `NL-A742` → new preference → `1` → `yes` |
| Cancel | `cancel` → `NL-A742` → `yes` |
| What to prepare | `what should I prepare` → `SIP Mandates` |
| Availability | `what times are available` → optional `book a new slot` |

Reschedule/cancel use **booking code only** (no phone/email lookup). Spoken codes like `N L dash A 7 4 2` are accepted.

### MCP side effects

| Action | MCP tools (order) |
|--------|-------------------|
| Book / confirm | `calendar_create_hold` → `docs_append_prebooking` → `gmail_create_draft` |
| Reschedule | `calendar_update_hold` → `docs_append_prebooking` → `gmail_create_draft` |
| Cancel | `calendar_delete_hold` → `docs_append_prebooking` → `gmail_create_draft` |
| Waitlist | `docs_append_prebooking` → `gmail_create_draft` |
| Prepare | none (KB only) |

## Mock calendar JSON

- Path: [`data/mock_calendar.json`](data/mock_calendar.json)
- Timezone: `Asia/Kolkata` (IST)
- Used for **slot picking / availability**; Google Calendar holds still go through actual MCP.

## Google credentials (live MCP)

Set `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_OAUTH_CLIENT_SECRETS`, plus `GOOGLE_CALENDAR_ID`, `GOOGLE_DOCS_PREBOOKINGS_ID`, and `GMAIL_DRAFT_TO`.

## Deploy (Vercel)

See [`deployment.md`](deployment.md) for the frontend + FastAPI Vercel plan (two projects, env vars, serverless constraints, and go-live checklist).
