# Low-Level Architecture: Advisor Appointment Scheduler

Companion to [`architecture.md`](architecture.md). This document specifies **modules, APIs, state machines, data contracts, and a phase-wise build plan** for chat-first → voice-second delivery.

---

## 0. Repo layout (target)

```
advisor-appointment-scheduler/
├── README.md
├── context.md
├── architecture.md
├── architecture-low-level.md
├── pyproject.toml / requirements.txt
├── data/
│   └── mock_calendar.json
├── scripts/
│   └── utterances.md              # demo script / prompts
├── src/
│   └── advisor_scheduler/
│       ├── __init__.py
│       ├── main.py                # FastAPI / CLI entry
│       ├── api/
│       │   ├── chat.py            # POST /sessions, POST /message
│       │   └── schemas.py
│       ├── domain/
│       │   ├── topics.py
│       │   ├── codes.py
│       │   ├── slots.py
│       │   ├── booking.py
│       │   ├── calendar_mock.py
│       │   └── prepare_kb.py
│       ├── orchestrator/
│       │   ├── machine.py         # state enum + transitions
│       │   ├── handlers.py        # per-state turn handlers
│       │   ├── session.py         # SessionStore
│       │   └── events.py          # analytics events (no PII)
│       ├── nlu/
│       │   ├── classify.py
│       │   ├── extract.py
│       │   └── prompts.py
│       ├── compliance/
│       │   ├── disclaimer.py
│       │   ├── pii.py
│       │   └── advice.py
│       ├── mcp_client/
│       │   ├── protocol.py        # shared tool interface
│       │   └── google_mcp.py      # client to actual FastMCP Google tools
│       ├── mcp_server/            # FastMCP process (real Google APIs)
│       │   ├── server.py
│       │   ├── calendar_tools.py
│       │   ├── docs_tools.py
│       │   └── gmail_tools.py
│       ├── agent/                 # Phase 3: LLM agent + MCP tool calling
│       │   ├── llm_agent.py       # binds tools; invokes actual MCP on confirm
│       │   └── tool_bindings.py
│       ├── secure_link.py
│       └── voice/                 # Phase 5 only
│           ├── stt.py
│           ├── tts.py
│           └── adapter.py
└── tests/
    ├── unit/
    ├── integration/               # live Google MCP (credentials required)
    └── fixtures/
```

**Stack (recommended):** Python 3.11+, FastAPI (chat API), Pydantic models, FastMCP + `google-api-python-client` (actual Google Calendar / Docs / Gmail MCP tools), LLM agent with MCP tool calling, pytest.

---

## 1. Shared contracts (all phases)

### 1.1 Core turn API

```text
handle(user_text: str, session: Session) -> TurnResult
```

```python
class TurnResult(BaseModel):
    messages: list[str]          # assistant text(s); TTS reads these later
    state: SessionState
    session_id: str
    events: list[AnalyticsEvent] # no PII
    meta: dict                   # e.g. offered_slots, booking_code
```

Chat UI and voice adapters **only** call `handle`. No domain logic outside this path.

### 1.2 HTTP (chat harness)

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/sessions` | `{ "channel": "chat" }` | `{ "session_id", "messages", "state" }` |
| `POST` | `/sessions/{id}/message` | `{ "text": "..." }` | `TurnResult` JSON |
| `GET`  | `/sessions/{id}` | — | session snapshot (debug) |
| `GET`  | `/health` | — | ok |

### 1.3 Session model

```python
class SessionState(str, Enum):
    GREET = "greet"
    DISCLAIMER = "disclaimer"
    INTENT = "intent"
    TOPIC = "topic"
    PREFERENCE = "preference"
    OFFER_SLOTS = "offer_slots"
    CONFIRM = "confirm"
    ORCHESTRATE = "orchestrate"   # internal / brief
    WAITLIST = "waitlist"
    CLOSE = "close"
    # Secondary subgraphs
    RESCHEDULE_LOOKUP = "reschedule_lookup"
    RESCHEDULE_PREFERENCE = "reschedule_preference"
    RESCHEDULE_OFFER = "reschedule_offer"
    RESCHEDULE_CONFIRM = "reschedule_confirm"
    CANCEL_LOOKUP = "cancel_lookup"
    CANCEL_CONFIRM = "cancel_confirm"
    PREPARE_TOPIC = "prepare_topic"
    AVAILABILITY = "availability"
    ADVICE_REFUSAL = "advice_refusal"
    ENDED = "ended"

class Session(BaseModel):
    session_id: str
    state: SessionState
    disclaimer_acked_at: datetime | None
    intent: Intent | None
    topic: Topic | None
    preference: TimePreference | None
    offered_slots: list[Slot]      # length 0 or 2
    selected_slot: Slot | None
    booking_code: str | None
    booking_status: BookingStatus | None  # tentative | waitlist | cancelled
    correlation_id: str
    channel: Literal["chat", "voice"]
```

### 1.4 Domain enums

```python
class Intent(str, Enum):
    BOOK_NEW = "book_new"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    WHAT_TO_PREPARE = "what_to_prepare"
    CHECK_AVAILABILITY = "check_availability"

class Topic(str, Enum):
    KYC_ONBOARDING = "KYC/Onboarding"
    SIP_MANDATES = "SIP/Mandates"
    STATEMENTS_TAX = "Statements/Tax Docs"
    WITHDRAWALS = "Withdrawals & Timelines"
    ACCOUNT_NOMINEE = "Account Changes/Nominee"

class BookingStatus(str, Enum):
    TENTATIVE = "tentative"
    WAITLIST = "waitlist"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
```

### 1.5 Slot & preference

```python
class Slot(BaseModel):
    id: str
    start: datetime   # aware; store with offset or UTC
    end: datetime
    status: Literal["available", "held", "waitlist"]

class TimePreference(BaseModel):
    date_ist: date | None
    window_start_ist: time | None
    window_end_ist: time | None
    raw_text: str
```

### 1.6 Mock calendar JSON (`data/mock_calendar.json`)

```json
{
  "timezone": "Asia/Kolkata",
  "slots": [
    {
      "id": "slot_20260715_1000",
      "start": "2026-07-15T10:00:00+05:30",
      "end": "2026-07-15T10:30:00+05:30",
      "status": "available"
    }
  ]
}
```

### 1.7 Booking record (store)

```python
class BookingRecord(BaseModel):
    code: str                    # NL-[A-Z0-9]{4}
    topic: Topic
    slot_id: str | None
    slot_start: datetime | None
    status: BookingStatus
    calendar_event_id: str | None
    secure_details_url: str
    created_at: datetime
    updated_at: datetime
```

### 1.8 MCP tool signatures (actual Google MCP)

These are the **real** FastMCP tool contracts. Phase 3+ calls them against live Google Workspace—there is no FakeMCP product path.

```python
class CalendarTools(Protocol):
    def create_hold(self, *, code: str, topic: str, start: datetime, end: datetime) -> str: ...
    def delete_hold(self, *, code: str, event_id: str | None) -> None: ...
    def update_hold(self, *, code: str, event_id: str, start: datetime, end: datetime, topic: str) -> str: ...

class DocsTools(Protocol):
    def append_prebooking(self, *, date: str, topic: str, slot: str, code: str, action: str) -> None: ...

class GmailTools(Protocol):
    def create_draft(self, *, subject: str, body: str, to: str | None = None) -> str: ...
```

Calendar event title: `Advisor Q&A — {Topic} — {Code}`.

Implementation: `mcp_server/*` exposes these via FastMCP; `mcp_client/google_mcp.py` and the Phase 3 LLM agent invoke them over MCP.

### 1.9 Compliance helpers

| Module | API | Behavior |
|--------|-----|----------|
| `pii.detect(text)` | `PiiHit \| None` | Phone / email / account patterns |
| `pii.firewall_reply()` | `str` | Redirect to secure URL; do not store hit |
| `advice.is_advice_request(text, nlu)` | `bool` | Keywords + NLU flag |
| `advice.refusal_messages()` | `list[str]` | Educational links only |
| `disclaimer.script()` | `str` | Fixed copy |
| `disclaimer.is_ack(text)` | `bool` | yes / I understand / etc. |

### 1.10 IST display helper

```python
def format_ist(dt: datetime) -> str:
    """Always user-facing: full date + time + 'IST'."""
```

Confirmation messages **must** call `format_ist` on the selected slot.

### 1.11 Booking code

```python
def generate_booking_code() -> str:
    # Pattern: NL- + 4 alphanumeric, e.g. NL-A742
    # Collision check against BookingStore
```

```python
def spell_code_for_tts(code: str) -> str:
    # Phase 5: "N L dash A 7 4 2"
```

### 1.12 Secure link

```python
def issue_secure_details_url(code: str) -> str:
    # Placeholder token model until PM locks issuer
    # e.g. https://example.com/prebook/{code}?t=...
```

---

## 2. State machine (detail)

### 2.1 `book_new` happy path

```
GREET
  → (auto or first user turn) DISCLAIMER
  → (ack) INTENT
  → (book_new) TOPIC
  → (valid topic) PREFERENCE
  → (normalized pref) OFFER_SLOTS     # findSlots → 2 options
  → (user picks 1 or 2) CONFIRM
  → (yes) ORCHESTRATE                 # code + MCP side effects
  → CLOSE → ENDED
```

### 2.2 Guards (enforced in orchestrator, not LLM)

| From | To | Guard |
|------|----|-------|
| any | next booking step | `disclaimer_acked_at` set |
| TOPIC → PREFERENCE | topic ∈ Topic enum |
| PREFERENCE → OFFER_SLOTS | preference normalized or clarification loop |
| OFFER_SLOTS → CONFIRM | `len(offered_slots) == 2` and selection valid |
| CONFIRM → ORCHESTRATE | explicit yes |
| any user turn | ADVICE_REFUSAL | advice detected (returnable) |
| any user turn | stay + firewall message | PII detected |

### 2.3 No-match / waitlist

```
OFFER_SLOTS with empty findSlots
  → WAITLIST
  → generate waitlist code (format TBD — see open decisions)
  → docs_append + gmail_create_draft (+ optional calendar waitlist marker)
  → CLOSE
```

### 2.4 Secondary intents (after disclaimer)

```
INTENT
  ├─ reschedule → RESCHEDULE_LOOKUP → … → CLOSE
  ├─ cancel     → CANCEL_LOOKUP → CANCEL_CONFIRM → CLOSE
  ├─ prepare    → PREPARE_TOPIC → (optional) INTENT|ENDED
  └─ availability → AVAILABILITY → soft handoff to TOPIC|ENDED
```

---

## 3. Phase-wise implementation

### Phase 0 — Project skeleton (½ day)

**Goal:** Runnable package, config, test harness.

| Deliverable | Detail |
|-------------|--------|
| Package layout | As in §0 |
| Config | `.env.example`: `GOOGLE_*`, `LLM_*`, `SECURE_LINK_BASE`, `ADVISOR_EMAIL` |
| Entry points | `uvicorn` for API; `python -m advisor_scheduler` CLI chat |
| CI smoke | `pytest -q` green with one placeholder test |

**Exit criteria:** `GET /health` returns 200; empty CLI loop prints prompt.

---

### Phase 1 — Domain + mock calendar (pure logic)

**Goal:** Slot picking, topics, codes, IST formatting — **no LLM, no HTTP, no Google**.

#### Modules to build

| Module | Functions / types |
|--------|-------------------|
| `domain/topics.py` | `Topic`, `parse_topic(text) -> Topic \| None` |
| `domain/calendar_mock.py` | `MockCalendarService.load(path)`, `list_available()`, `mark_held(id)`, `release(id)` |
| `domain/slots.py` | `find_slots(pref, calendar, n=2) -> list[Slot]` |
| `domain/codes.py` | `generate_booking_code(existing: set[str])`, `normalize_code(text)`, `spell_code_for_tts` |
| `domain/booking.py` | `BookingRecord`, `BookingStore` (in-memory dict) |
| `secure_link.py` | `issue_secure_details_url(code)` |

#### `find_slots` algorithm

1. Filter `status == available`.
2. Score by distance to preference date/window (IST).
3. Return top **2**; if fewer than 2 after filter, return what exists; if **0**, empty → waitlist path later.
4. Never invent slots not in JSON.

#### Tests (property / unit)

- Exactly two slots when ≥2 available near preference.
- Empty when none match.
- Codes unique and match `^NL-[A-Z0-9]{4}$`.
- `format_ist` always contains `IST`.
- Topic parser rejects unknown topics.

**Exit criteria:** Domain tests pass; README stub documents `mock_calendar.json` shape.

---

### Phase 2 — Chat orchestrator + compliance + NLU (MCP deferred)

**Goal:** Full `book_new` dialogue in chat with disclaimer, PII firewall, advice refusal, two-slot offer, confirm copy — **Google MCP not wired yet**. Confirm may generate a local booking code + secure URL and stop before Calendar/Docs/Gmail; Phase 3 replaces that gap with actual MCP tool calls via the LLM agent.

#### Modules

| Module | Responsibility |
|--------|----------------|
| `orchestrator/machine.py` | Allowed transitions table |
| `orchestrator/handlers.py` | `on_greet`, `on_disclaimer`, … |
| `orchestrator/session.py` | In-memory `SessionStore` |
| `compliance/*` | Disclaimer, PII, advice |
| `nlu/classify.py` | Intent (+ advice flag) via structured LLM JSON **or** rules fallback |
| `nlu/extract.py` | Topic, preference, yes/no, slot choice index |
| `api/chat.py` | HTTP endpoints |
| Simple web UI or CLI | Text in → print `messages` |

#### NLU contract

```python
class NluResult(BaseModel):
    intent: Intent | None
    confidence: float
    topic: Topic | None
    preference_raw: str | None
    preference: TimePreference | None
    confirmation: Literal["yes", "no", "unknown"] | None
    slot_choice: Literal[1, 2] | None
    is_advice: bool
    needs_clarification: bool
    clarification_prompt: str | None
```

If `confidence < threshold` or `needs_clarification`: stay in state; ask clarifying question from `clarification_prompt` or static template.

#### Orchestrate placeholder (Phase 2 only)

```python
def orchestrate_confirm(session) -> TurnResult:
    code = generate_booking_code(...)
    url = issue_secure_details_url(code)
    store.save(BookingRecord(..., status=TENTATIVE))
    # Intentionally no MCP yet — Phase 3 LLM agent calls actual Google MCP tools
    return messages including code, format_ist(slot), url
```

#### Tests

- Disclaimer required before topic (cannot skip).
- PII in user text → firewall reply; state unchanged; nothing stored.
- Advice → refusal + edu links; no booking.
- Confirm message repeats full IST datetime.
- `POST /message` drives GREET→…→CLOSE for happy path (without asserting Google side effects).

**Exit criteria:** Manual chat demo completes book_new dialogue through CLOSE with local code/URL; automated flow test green. MCP integration is Phase 3.

---

### Phase 3 — Actual Google MCP via LLM agent

**Goal:** On confirm/waitlist, the **LLM agent calls actual MCP tools** for Google Calendar, Docs, and Gmail—creating a real tentative hold, appending **Advisor Pre-Bookings**, and creating an approval-gated email draft. Still chat-only for the channel; **no FakeMCP**.

#### FastMCP server (`mcp_server/`) — real Google APIs

| Tool name | Args | Side effect |
|-----------|------|-------------|
| `calendar_create_hold` | `code`, `topic`, `start_iso`, `end_iso` | **Actual** Google Calendar tentative event; title `Advisor Q&A — {topic} — {code}`; return `event_id` |
| `calendar_delete_hold` | `code`, `event_id?` | Delete/cancel event on real calendar; idempotent by `code` |
| `calendar_update_hold` | `code`, `event_id`, new times, `topic` | Reschedule on real calendar |
| `docs_append_prebooking` | `date`, `topic`, `slot`, `code`, `action` | Append line to live **Advisor Pre-Bookings** Google Doc |
| `gmail_create_draft` | `subject`, `body` | Create **real** Gmail draft only — **never send** |

#### LLM agent tool calling (`agent/`)

```python
# Pseudocode — Phase 3 runtime path
tools = bind_mcp_tools([
    "calendar_create_hold",
    "calendar_delete_hold",
    "calendar_update_hold",
    "docs_append_prebooking",
    "gmail_create_draft",
])  # connected to the live FastMCP server

def orchestrate_confirm(session) -> TurnResult:
    code = generate_booking_code(...)
    url = issue_secure_details_url(code)
    # LLM agent MUST invoke the actual MCP tools (policy-ordered):
    agent.run_with_tools(
        goal="Create tentative advisor pre-booking side effects",
        required_tools_in_order=[
            "calendar_create_hold",
            "docs_append_prebooking",
            "gmail_create_draft",
        ],
        args={...code, topic, slot IST fields...},
    )
    store.save(BookingRecord(..., calendar_event_id=..., status=TENTATIVE))
    return messages including code, format_ist(slot), url
```

**Policy:** The orchestrator still owns ordering and compliance. The LLM agent may phrase tool args / handle retries, but **cannot skip** required MCP tools or invent successful side effects without tool results. Tool results come only from the live MCP server.

#### Client wiring

```python
# mcp_client/google_mcp.py — always targets the actual FastMCP Google tools
# Requires GOOGLE_* credentials; product path never substitutes FakeMCP
```

Orchestrator `ORCHESTRATE` / `WAITLIST` steps (ordered):

1. Generate code (if not waitlist-deferred).
2. LLM agent → `calendar_create_hold` (actual Calendar MCP).
3. LLM agent → `docs_append_prebooking` (actual Docs MCP).
4. LLM agent → `gmail_create_draft` (actual Gmail MCP).
5. Persist `BookingRecord` with `calendar_event_id` from tool result.
6. Emit CLOSE messages.

#### Retry & idempotency

- Retry each **actual** MCP tool **once** on transient errors.
- Idempotency key = `booking_code` (search calendar by title suffix / private extended property).
- Partial failure: return honest message listing which Google steps succeeded; keep code + secure URL if booking record exists.

#### Auth / config

- Service account or OAuth desktop credentials via env (**required** for Phase 3).
- Document IDs: `GOOGLE_CALENDAR_ID`, `GOOGLE_DOCS_PREBOOKINGS_ID`, `GMAIL_DRAFT_TO` (advisor).

#### Tests / verification

- Integration tests against **live** Google MCP (credentials in env): confirm path creates Calendar hold → Docs append → Gmail draft in order.
- Waitlist path: actual Docs + Gmail (and calendar waitlist marker if used).
- Manual QA: screenshot Calendar title (with code), Docs entry, and Gmail draft.
- Unit tests may still cover domain/orchestrator without MCP; they must not claim Google side effects succeeded.

**Exit criteria:** Chat confirm produces visible **real** Calendar hold, Docs line, and Gmail draft via actual MCP tools invoked by the LLM agent.

---

### Phase 4 — Secondary intents (chat-only)

**Goal:** All five intents work through the same `handle` path. Reschedule/cancel use the **same actual** Calendar / Docs / Gmail MCP tools via the LLM agent.

#### 4.1 Reschedule

```
RESCHEDULE_LOOKUP
  → extract/normalize code (typed or spoken style "N L A 7 4 2")
  → BookingStore.get(code); if missing → clarify
  → RESCHEDULE_PREFERENCE → OFFER (find_slots) → CONFIRM
  → calendar_update_hold + docs_append(action=reschedule) + gmail_create_draft
  → CLOSE with new IST readback
```

#### 4.2 Cancel

```
CANCEL_LOOKUP → CONFIRM ("say yes to cancel")
  → calendar_delete_hold
  → docs_append(action=cancel)
  → gmail_create_draft (optional cancel notice)
  → BookingStatus.CANCELLED → CLOSE
```

#### 4.3 What to prepare

- `domain/prepare_kb.py`: static map `Topic → bullet list` (educational, non-advice).
- Flow: confirm topic if missing → return KB → offer “book a slot?” soft handoff.

#### 4.4 Check availability

- Summarize next N available windows from mock calendar in IST.
- Soft handoff into `TOPIC` / `PREFERENCE` for `book_new`.

#### Tests

- Each intent has at least one end-to-end chat transcript test.
- Reschedule/cancel require code only (no phone lookup).
- Prepare never calls calendar create.

**Exit criteria:** README documents reschedule/cancel behavior + mock calendar; all five intents demoable in chat.

---

### Phase 5 — Voice adapters (I/O swap)

**Goal:** End-state voice UX without rewriting booking logic.

#### Modules

| Module | Role |
|--------|------|
| `voice/stt.py` | Audio → `user_text` |
| `voice/tts.py` | `messages[]` → audio; optional `spell_code_for_tts` on CLOSE |
| `voice/adapter.py` | Session loop: STT → `handle` → TTS; barge-in / VAD |

```python
# Pseudocode
text = stt.transcribe(audio_frame)
result = handle(text, session)
tts.speak(result.messages, spell_codes=True)
```

#### Voice-only UX (no business rules)

- Barge-in cancels current TTS.
- End-of-utterance / VAD before calling `handle`.
- On CLOSE, spell booking code once after full read.
- Same disclaimer ack phrases as chat.

#### Tests

- STT/TTS test harnesses: assert `handle` receives identical strings as chat fixtures.
- One recorded or live demo ≤3 min **or** live link.

**Exit criteria:** Milestone deliverables: voice demo, calendar/docs/email evidence, `scripts/utterances.md`, README complete.

---

## 4. Phase dependency graph

```
Phase 0 Skeleton
    └─► Phase 1 Domain + Mock Calendar
            └─► Phase 2 Chat Orchestrator + NLU + Compliance
                    └─► Phase 3 Actual Google MCP via LLM agent
                            └─► Phase 4 Secondary Intents
                                    └─► Phase 5 Voice Adapters
```

No phase skips the chat harness: Phases 3–4 are validated via `/message` before Phase 5. Phase 3 requires live Google credentials; the LLM agent calls **actual** MCP tools only.

---

## 5. Per-phase Definition of Done (checklist)

| Phase | DoD |
|-------|-----|
| **0** | Package installs; health check; pytest runs |
| **1** | Mock calendar + `find_slots` + codes + IST helpers tested |
| **2** | Chat happy path `book_new` with disclaimer/PII/advice gates; MCP deferred |
| **3** | LLM agent calls **actual** Calendar / Docs / Gmail MCP tools on confirm; screenshot-backed Google side effects |
| **4** | Five intents; waitlist path; reschedule/cancel hit actual MCP; README for calendar JSON + reschedule/cancel |
| **5** | Voice demo; STT/TTS are pure adapters; utterances script committed |

---

## 6. Observability (implement from Phase 2)

```python
class AnalyticsEvent(BaseModel):
    correlation_id: str
    session_id: str
    name: str   # e.g. state_transition, mcp_success, mcp_failure, pii_blocked, advice_refused
    from_state: str | None
    to_state: str | None
    intent: str | None
    mcp_tool: str | None
    # NEVER: raw user text if policy requires minimization; NEVER: phone/email/account
```

Log **actual** MCP latency and success/failure per Google tool.

---

## 7. Test matrix

| Concern | Phase | Style |
|---------|-------|-------|
| Two slots offered | 1–2 | Property / flow |
| IST repeated on confirm | 2 | Snapshot / string assert |
| Five intents | 4 | Transcript fixtures |
| MCP order & idempotency | 3 | Live Google MCP integration (Calendar → Docs → Gmail) |
| Disclaimer gate | 2 | Negative tests (skip attempt) |
| PII firewall | 2 | Injection cases |
| Advice refusal | 2 | Keyword + NLU flag |
| Voice = same handle | 5 | Adapter unit test |

---

## 8. Open decisions (carry into implementation flags)

| ID | Decision | Interim default |
|----|----------|-----------------|
| OD-1 | Waitlist code same format as tentative? | Same `NL-XXXX`; `status=waitlist` |
| OD-2 | Reschedule/cancel by code only? | Yes (chat + voice) |
| OD-3 | Secure URL issuer / token model | Signed path under `SECURE_LINK_BASE` placeholder |

---

## 9. Mapping to milestone deliverables

| Deliverable | Produced in |
|-------------|-------------|
| Working voice demo or ≤3-min recording | Phase 5 |
| Calendar hold screenshot (title incl. code) | Phase 3 (actual Calendar MCP) |
| Notes/Doc + Email draft evidence | Phase 3 (actual Docs + Gmail MCP) |
| Script file (utterances) | Phase 2 (draft) → Phase 5 (final) |
| README: mock calendar JSON; reschedule/cancel | Phase 1 + Phase 4 |

---

## 10. Summary

Low-level delivery is **five build phases** on one text core: domain purity first, chat state machine second, **actual FastMCP Google side effects via the LLM agent** third, remaining intents fourth, voice I/O last. Every product rule (disclaimer, PII, IST, two slots, MCP order) is enforced in the orchestrator and proven in chat before STT/TTS are attached. There is **no FakeMCP** runtime—Phase 3+ always calls real Calendar, Docs, and Gmail MCP tools.
