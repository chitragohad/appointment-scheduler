# Deployment Plan — Vercel (Frontend + Backend)

> **Status:** Plan only (not yet executed)  
> **Target:** Deploy Advisor Appointment Scheduler UI + FastAPI API on Vercel  
> **Date:** 2026-07-13

**Goal:** Ship the Acoustic Serenity voice UI and FastAPI orchestrator to production URLs on Vercel, with env-based secrets and CORS wired correctly.

**Architecture (recommended):** Two Vercel projects from one Git monorepo.

| Project | Root directory | Runtime | Public URL role |
|---------|----------------|---------|-----------------|
| `advisor-scheduler-web` | `frontend/` | Static (Vite → `dist/`) | User-facing UI |
| `advisor-scheduler-api` | repository root | Python / FastAPI (Vercel Functions) | `/sessions`, `/health` |

```text
Browser (Vercel web)
    │  HTTPS
    │  VITE_API_BASE=https://advisor-scheduler-api.vercel.app
    ▼
FastAPI on Vercel (Python ASGI)
    ├── ConversationEngine (in-memory sessions*)
    ├── Mock calendar JSON (bundled)
    ├── Gemini (optional NLU)
    └── Google Calendar / Docs / Gmail (OAuth token or service account)
```

\*See [Serverless constraints](#serverless-constraints) — in-memory session/booking state does not survive cold starts across instances.

**Tech stack for deploy:** Vercel, Vite 8, React 19, FastAPI, Python ≥3.10, Google OAuth / Gemini env secrets.

---

## 1. Options considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **A. Two Vercel projects** (web + api) | Stable, clear roots, independent deploys, matches current repo layout | CORS + two dashboards | **Recommended** |
| **B. Single project + Vercel Services** (`services` in `vercel.json`) | One domain, shared routing | Experimental; more moving parts | Optional later |
| **C. Frontend on Vercel, API elsewhere** | API can be a long-lived VM | Violates “use Vercel for backend” | Out of scope |

**Recommendation:** Approach **A**. Revisit **B** only if you want a single hostname without CORS.

---

## 2. Serverless constraints

These are product/architecture limits on Vercel Functions — plan around them before go-live.

| Constraint | Impact today | Mitigations (later phases) |
|------------|--------------|----------------------------|
| **Ephemeral filesystem** | Cannot rely on writing `.secrets/google_token.json` at runtime | Pre-create OAuth token locally; store JSON in `GOOGLE_OAUTH_TOKEN_JSON` (secret) or switch to service account |
| **In-memory `SessionStore` / `BookingStore`** | Sessions/bookings can vanish on cold start or multi-instance | Accept for demo; later Vercel KV / Redis (`SESSION_STORE=redis`) |
| **Function timeout** | Gemini + Google MCP chain may need 30–60s | Set `maxDuration` (Pro) or shorten agent path |
| **No local MCP sidecar** | Separate `MCP_SERVER_PORT` process is not how prod works | Keep in-process Google tool calls (already the case via `BookingAgent`) |
| **Browser STT/TTS** | Voice stays client-side (Web Speech) | No change for Phase 5 browser voice |

---

## 3. Prerequisites

- [ ] GitHub/GitLab/Bitbucket repo connected to Vercel
- [ ] Vercel account (Hobby is enough for demo; Pro if you need longer `maxDuration`)
- [ ] Working local API + UI (`pytest`, book flow, Google tools optional)
- [ ] Google OAuth token already obtained **once** on a laptop (`get_credentials()` → `.secrets/google_token.json`) **or** a service account with Calendar/Docs/Gmail access
- [ ] Gemini API key (if NLU/agent LLM is enabled)

---

## 4. Code changes required before first deploy

Do these in the repo before linking Vercel (implementation checklist).

### 4.1 Backend — Vercel FastAPI entry

Vercel discovers a FastAPI instance named `app`. Current entry already exists:

- Module: `advisor_scheduler.api.app:app`  
  File: `src/advisor_scheduler/api/app.py`

Add at **repo root**:

**`vercel.json`** (API project — Root Directory = `.`):

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [{ "source":="/(.*)", "destination": "/api" }]
}
```

**`pyproject.toml`** — declare entrypoint for Vercel:

```toml
[tool.vercel]
entrypoint = "advisor_scheduler.api.app:app"
```

**`requirements.txt`** (Vercel Python install path — pin from current deps):

```text
fastapi>=0.110
uvicorn>=0.27
pydantic>=2.0
pydantic-settings>=2.0
python-dotenv>=1.0
fastmcp>=2.0
google-api-python-client>=2.0
google-auth>=2.0
google-auth-oauthlib>=1.0
```

Ensure `PYTHONPATH` / install includes `src/` (setuptools package `advisor-scheduler`, or set install to `pip install .`).

Prefer build command:

```bash
pip install .
```

### 4.2 Backend — CORS for production UI

Update `create_app()` CORS to read origins from env, e.g.:

```text
CORS_ORIGINS=https://advisor-scheduler-web.vercel.app,http://localhost:5173
```

Do not hardcode only localhost.

### 4.3 Backend — Google credentials on Vercel

Local browser OAuth (`InstalledAppFlow.run_local_server`) **will not work** on Vercel.

**Path A (quick demo):** Export existing refresh token JSON into a Vercel secret:

```text
GOOGLE_OAUTH_TOKEN_JSON={"token":"...","refresh_token":"...","client_id":"...","client_secret":"...","scopes":[...]}
```

Extend `google_auth.py` to load credentials from `GOOGLE_OAUTH_TOKEN_JSON` when the file path is missing.

**Path B (cleaner):** Service account JSON in `GOOGLE_SERVICE_ACCOUNT_JSON` + Calendar/Docs shared with that SA; Gmail via domain-wide delegation if required.

### 4.4 Backend — package data

Ensure `data/mock_calendar.json` is included in the deploy artifact (repo path relative to root is fine if Root Directory is `.`).

### 4.5 Frontend — API base URL

`frontend` already uses:

```ts
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
```

For production, set:

```text
VITE_API_BASE=https://<api-project>.vercel.app
```

Remove reliance on Vite dev proxy in production (proxy is local-only).

Optional `frontend/vercel.json`:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

(Only needed if you add client-side routes later; current SPA is single-page.)

### 4.6 Frontend — build settings

| Setting | Value |
|---------|--------|
| Framework Preset | Vite |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Install Command | `npm install` |

---

## 5. Environment variables

### API project (`advisor-scheduler-api`)

| Variable | Required | Notes |
|----------|----------|--------|
| `APP_ENV` | yes | `production` |
| `CORS_ORIGINS` | yes | Exact frontend origin(s), comma-separated |
| `TIMEZONE` | yes | `Asia/Kolkata` |
| `GEMINI_API_KEY` | if LLM on | From Google AI Studio |
| `LLM_MODEL` | optional | e.g. `gemini-2.0-flash` |
| `SECURE_LINK_BASE` | yes | Public prebook URL base |
| `SECURE_LINK_SECRET` | yes | Random secret for signed links |
| `GOOGLE_CALENDAR_ID` | for live MCP | Calendar ID |
| `GOOGLE_DOCS_PREBOOKINGS_ID` | for live MCP | Doc ID |
| `GMAIL_DRAFT_TO` / `ADVISOR_EMAIL` | for drafts | Recipient |
| `GOOGLE_OAUTH_TOKEN_JSON` | Path A | Full token JSON string |
| `GOOGLE_OAUTH_CLIENT_SECRETS` / client fields | Path A | If token refresh needs client |
| `GOOGLE_APPLICATION_CREDENTIALS` / `GOOGLE_SERVICE_ACCOUNT_JSON` | Path B | SA JSON |
| `MOCK_CALENDAR_PATH` | optional | Default `data/mock_calendar.json` |
| `SESSION_STORE` | optional | `memory` until KV/Redis |

Never commit `.env`, `credentials.json`, or token JSON.

### Web project (`advisor-scheduler-web`)

| Variable | Required | Notes |
|----------|----------|--------|
| `VITE_API_BASE` | yes | `https://<api-project>.vercel.app` (no trailing slash) |

`VITE_*` vars are baked in at **build** time — redeploy web after changing them.

---

## 6. Deployment steps (execution order)

### Phase 0 — Prep (local)

1. Confirm `pytest -q` passes.
2. Complete OAuth once locally; copy token JSON for Vercel secret (or prepare SA).
3. Implement sections **4.1–4.5** and merge to `main` (or deploy branch).

### Phase 1 — Deploy API first

1. Vercel → **Add New Project** → import monorepo.
2. Set **Root Directory** to `.` (repo root). Override if UI is detected: Framework = Other / FastAPI.
3. Build & install: `pip install .` (or Vercel’s Python detection + `requirements.txt`).
4. Add all API env vars (Production + Preview as needed).
5. Deploy.
6. Smoke test:

```bash
curl -s https://<api>.vercel.app/health
# expect {"status":"ok"}

curl -s -X POST https://<api>.vercel.app/sessions \
  -H 'content-type: application/json' \
  -d '{"channel":"voice"}'
```

### Phase 2 — Deploy frontend

1. Vercel → **Add New Project** → same repo.
2. **Root Directory** = `frontend`.
3. Set `VITE_API_BASE` to the API URL from Phase 1.
4. Deploy.
5. Open the web URL; start a session; complete disclaimer → book flow (text fallback is fine if mic blocked on non-HTTPS — Vercel HTTPS is fine).

### Phase 3 — Wire CORS + retest

1. Set `CORS_ORIGINS` on API to the exact web origin.
2. Redeploy API.
3. From browser DevTools → Network: `POST /sessions` and `POST /sessions/:id/message` return 200, no CORS errors.

### Phase 4 — Google live smoke (optional)

1. Book → confirm.
2. Verify Calendar hold, Docs append, Gmail draft.
3. If failures: check function logs in Vercel → Project → Deployments → Functions.

### Phase 5 — Hardening (post-MVP)

- [ ] Persist sessions/bookings (Vercel KV or Upstash Redis)
- [ ] Structured logging + request IDs
- [ ] Preview env: separate Gemini key / calendar sandbox
- [ ] Custom domains + HTTPS
- [ ] Consider Vercel Services single-project routing

---

## 7. Local parity with Vercel

```bash
# API (unchanged)
source .venv/bin/activate
python -m advisor_scheduler --serve --host 127.0.0.1 --port 8000

# UI pointing at local API
cd frontend
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

Optional: `vercel dev` in API root after `vercel link` to mimic serverless routing.

---

## 8. Rollback

- Vercel → Deployments → Promote previous **Ready** deployment.
- Keep `VITE_API_BASE` and `CORS_ORIGINS` in sync when rolling back either side.
- Feature flags: set `APP_ENV` / disable Gemini via empty `GEMINI_API_KEY` if LLM outages occur (rule-based NLU remains).

---

## 9. Success criteria

| Check | Pass condition |
|-------|----------------|
| Health | `GET /health` → `{"status":"ok"}` |
| CORS | Browser UI can create a session |
| Book (mock) | Slot offer + confirm returns `NL-XXXX` |
| Secure link | URL present in confirm meta |
| Voice (Chrome) | Mic + TTS work on HTTPS deploy URL |
| Google (if configured) | Calendar/Docs/Gmail side effects succeed |

---

## 10. Implementation task checklist

Use this when executing the plan in a later session:

- [ ] Add root `vercel.json` + `[tool.vercel] entrypoint` + `requirements.txt`
- [ ] CORS from `CORS_ORIGINS`
- [ ] Load Google creds from `GOOGLE_OAUTH_TOKEN_JSON` (or SA JSON)
- [ ] Confirm package install includes `src/advisor_scheduler` + `data/`
- [ ] Create Vercel API project; set secrets; deploy; curl health/sessions
- [ ] Create Vercel Web project; set `VITE_API_BASE`; deploy
- [ ] End-to-end book on production URLs
- [ ] Document live URLs in README
- [ ] (Optional) Redis/KV session store

---

## 11. References

- [Deploy FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Monorepos on Vercel](https://vercel.com/docs/monorepos)
- [Vercel Services (experimental)](https://vercel.com/docs/services/experimental)
- Project context: `architecture.md`, `README.md`, `.env.example`

---

## 12. Out of scope for this plan

- Implementing Redis/KV session persistence (document only)
- Migrating voice STT/TTS off the browser to cloud providers
- Custom domain purchase
- Actually running `vercel deploy` (execute only when you ask to deploy)
