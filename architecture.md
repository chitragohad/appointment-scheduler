# Voice Agent Architecture: Advisor Appointment Scheduler

This document describes the system architecture for the compliant pre-booking voice assistant described in `context.md` and `Docs/Problem statement`.

For modules, APIs, state-machine details, and a phased build plan, see [`architecture-low-level.md`](architecture-low-level.md).

---

## Development strategy: chat first, voice second

We implement and validate all product behavior in **text (chat) mode first**, then add voice without changing the core conversation logic.

| Layer | Role |
|-------|------|
| **Core (text-in, text-out)** | The orchestrator, NLU, domain rules, MCP side effects, and compliance gates operate on user text and produce assistant text (one or more messages per turn). This is the same code path whether the UI is a chat widget, CLI, or API. |
| **Chat surface (milestones 1–N)** | A chat UI or `POST …/message` API exercises every intent, state transition, waitlist path, and MCP integration. Automated and manual tests run here fastest. |
| **Voice later** | Speech-to-text supplies the same string the chat would send into `handle(user_text, session)`. Text-to-speech reads the assistant strings the chat would display. No duplicate business logic in the voice layer—only I/O adapters and voice-specific UX (barge-in, spelling of booking codes, end-of-utterance detection). |

**End-state UX** remains a voice agent; **chat is the authoritative development and test harness** until voice adapters are plugged in.

---

## 1. Goals and boundaries

| Goal | Mechanism |
|------|-----------|
| Tentative booking with human advisor | Domain slot picker + Google Calendar MCP tentative hold |
| No PII in-session | Structured slot filling only; no capture of phone, email, or account identifiers (chat or voice) |
| Compliance | Scripted disclaimer; refuse investment advice; educational links only |
| Orchestration | Actual FastMCP tools wrapping Google APIs: Calendar (holds), Docs (pre-booking log), Gmail (approval-gated draft); LLM agent calls these tools in Phase 3+ |

**Out of scope in-session:** Collecting contact details (handled via secure URL after the session).

---

## 2. Logical architecture (layers)

**Build order:** implement everything below the dashed line using chat (text in → text out). Add everything above the dashed line only after the chat path is complete.

```
┌─────────────────────────────────────────────────────────────────┐
│  Voice adapters (later): telephony / WebRTC + STT → text,       │
│                          TTS ← text                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │ text only
┌─────────────────────────────▼───────────────────────────────────┐
│  Chat channel (first): web UI, CLI, or HTTP message API         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ user_text / assistant_messages
- - - - - - - - - - - - - - - ┼ - - - - - - - - - - - - - - - - -
┌─────────────────────────────▼───────────────────────────────────┐
│  Conversation orchestrator (state machine + policy)             │
│  • Intent routing (5 intents)                                   │
│  • Slot collection & validation                                 │
│  • Compliance gates (disclaimer, advice refusal)                │
└─────┬───────────────────┬───────────────────┬───────────────────┘
      │                   │                   │
      ▼                   ▼                   ▼
┌─────────────┐   ┌───────────────┐   ┌──────────────────────────────┐
│ NLU / LLM   │   │ Booking       │   │ Actual FastMCP server        │
│ agent       │   │ domain logic  │   │ (google-api-python-client)   │
│ (classify,  │   │ • Topic enum  │   │ • calendar_create_hold /     │
│  generate,  │──►│ • Slot picker │──►│   delete_hold                │
│  tool calls)│   │ • Codes       │   │ • docs_append_prebooking     │
└─────────────┘   │ • IST display │   │ • gmail_create_draft         │
                  └───────────────┘   └──────────────────────────────┘
```

**Principle:** The orchestrator owns turn-taking and legal/compliance transitions; the LLM assists with understanding and natural phrasing but does not bypass policy (e.g. cannot skip disclaimer or accept PII). From Phase 3, the LLM agent **must** invoke the actual Calendar / Docs / Gmail MCP tools for booking side effects—it cannot claim success without real tool results.

---

## 3. Intent model (five intents)

| Intent | Purpose | Typical outcome |
|--------|---------|-----------------|
| `book_new` | New tentative booking | Full happy path or waitlist |
| `reschedule` | Change existing tentative slot | Lookup by booking code (caller states code verbally), re-offer slots |
| `cancel` | Cancel tentative hold | Google Calendar release + Docs update + optional Gmail draft |
| `what_to_prepare` | Pre-visit guidance | Scripted / KB content by topic; no advice |
| `check_availability` | Windows / “when can I book?” | Query mock calendar; offer next steps toward `book_new` |

**Routing:** Hybrid approach recommended—lightweight classifier or structured LLM JSON for intent + entities; fall back to clarification prompts when confidence is low.

---

## 4. Dialogue flow (state machine)

States are linear with branches for errors, waitlist, and non-booking intents.

1. **Greet** → short value prop (chat message; later playable via TTS).
2. **Disclaimer** → mandatory: informational, not investment advice; require explicit acknowledgment (e.g. “yes” / “I understand”) before continuing.
3. **Intent detect** → if not `book_new`, branch to reschedule / cancel / prepare / availability subgraphs (each with its own mini-flow).
4. **Topic confirm** → must map to one of:
   - KYC / Onboarding
   - SIP / Mandates
   - Statements / Tax Docs
   - Withdrawals & Timelines
   - Account Changes / Nominee
5. **Day/time preference** → natural language → normalized to date + time window in **IST** (store and display always with timezone).
6. **Offer slots** → mock calendar returns two concrete options; show them in chat with IST and full date/time; on voice, read back the same strings.
7. **Confirm** → on user confirmation:
   - Generate booking code (e.g. `NL-A742` pattern).
   - **Google Calendar MCP:** create tentative event title `Advisor Q&A — {Topic} — {Code}`.
   - **Google Docs MCP:** append `{date, topic, slot, code}` to document **Advisor Pre-Bookings**.
   - **Gmail MCP:** draft advisor notification (human approval before send).
8. **Close** → output booking code and secure URL in chat (no PII collected in-session); voice uses the same strings via TTS (optionally spell the code).

### Alternate paths

| Path | Behavior |
|------|----------|
| **No-match** | If no slots available → waitlist hold (domain concept + Google Docs/Calendar as per product rules) + Gmail draft; still issue booking code if the brief requires a reference for the waitlist case (align with PM—code may be waitlist-specific). |
| **Investment advice** | If detected (keywords or intent), refuse and offer educational links only; do not enter booking unless user pivots to scheduling. |

---

## 5. Component responsibilities

### 5.1 Conversation orchestrator

- Enforces ordering: disclaimer before topic; topic before time; two slots before confirm.
- Repeats date/time in IST at confirmation.
- Blocks or redacts PII patterns (phone, email, account numbers) if user text or LLM surfaces them—respond with redirect to secure URL (same in chat and voice).
- Emits structured events for analytics (no PII in events).

### 5.2 NLU / LLM layer

- **Inputs:** transcript, current state, allowed topic list, current IST date for relative dates (“next Tuesday”).
- **Outputs:** intent label, extracted slots, or `needs_clarification` with suggested agent prompt.
- **Constraints:** System prompt + tool/schema so the model cannot invent slots or skip mandatory steps.

### 5.3 Booking domain service

- Topic validation (closed set).
- Slot picker: `findSlots(preference, timezone=IST) -> [slot1, slot2]` or empty. Uses `MockCalendarService` for local dev/test; production can query Google Calendar for real advisor availability.
- Code generation: unique, human-readable in chat; spell-out helper for TTS when voice is enabled.
- Reschedule/cancel: validate booking code against internal store or notes index (implementation choice: lightweight store keyed by code).

### 5.4 Google MCP integration layer (actual FastMCP)

We build a **FastMCP** server that exposes **actual** Google Workspace operations as MCP tools. From Phase 3, the **LLM agent** calls these tools to perform side effects on real Google resources (Calendar, Docs, Gmail)—not stubs or FakeMCP:

| Tool | Behavior |
|------|----------|
| `calendar_create_hold` / `calendar_delete_hold` | Create/update/delete tentative holds on a real Google Calendar via `google-api-python-client`; idempotent where possible using booking code as idempotency key. |
| `docs_append_prebooking` | Append-only log to **Advisor Pre-Bookings** document in Google Docs. |
| `gmail_create_draft` | Create draft with structured fields; never auto-send without approval gate in the tool or external workflow. |

**Why FastMCP:** single-process Python server exposing **actual** Google Calendar, Docs, and Gmail MCP tools (backed by `google-api-python-client`). From Phase 3 onward, the LLM agent invokes these real tools on confirm/waitlist—no FakeMCP path in the product runtime.

---

## 6. Data and state

| Data | Storage | PII |
|------|---------|-----|
| Session state (turn, slots, disclaimer ok) | Ephemeral (Redis/memory) | None |
| Booking code → slot, topic, timestamps | Short-lived store or derived from MCP responses | None in-session (chat or voice) |
| Advisor Pre-Bookings log | Via Google Docs MCP | Only what policy allows post-call |

**Timezone:** All persisted times UTC or explicit offset; all user-facing copy (chat or spoken) **IST** per requirements.

---

## 7. Security, compliance, and safety

| Control | Detail |
|---------|--------|
| **PII firewall** | Regex/heuristic + LLM refusal for account/contact details; single message pointing to secure URL. |
| **Disclaimer** | Logged acknowledgment timestamp for audit if required. |
| **Advice refusal** | Separate prompt path with static educational URLs. |
| **Email** | Draft-only through `gmail_create_draft` FastMCP tool until human approves. |

---

## 8. Observability and testing

- **Tracing:** Correlation id per call; log intent transitions and Google MCP success/failure (no transcript PII in logs if policy requires minimization).
- **Testing:** Primary dialogue tests use direct text (no STT/TTS). Domain/property tests cover “two slots,” “IST repeated on confirm,” and “five intents.” From Phase 3, integration tests and demos call **actual** Google MCP tools (Calendar, Docs, Gmail) with real credentials—verify holds, Doc appends, and draft email in the Google workspace. Add STT/TTS test harnesses only when wiring voice (Phase 5).

---

## 9. Suggested implementation order

1. **Domain + mock calendar** (pure logic, tests). Slot availability for picking remains mock JSON until/unless live free/busy is added; this is unrelated to MCP side effects.
2. **Chat loop:** state machine + NLU + topic/time slots + disclaimer and PII guards, exposed via chat UI or message API (no audio). Side effects deferred until Phase 3.
3. **Actual FastMCP + LLM agent tool use:** wire Calendar, Docs, and Gmail MCP tools (`google-api-python-client`). On confirm/waitlist the LLM agent **must call the real MCP tools** (not stubs)—retries and idempotency included—driven from the chat path.
4. **Secondary intents:** reschedule, cancel, prepare, availability (still chat-only; reschedule/cancel also hit actual Calendar/Docs/Gmail MCP tools).
5. **Voice layer:** STT feeds the same `user_text` as chat; assistant messages go to TTS; add barge-in, VAD, and code spelling only where needed.

Until step 5, **chat is the product surface** for demos and QA; step 5 is an **I/O swap**, not a rewrite of booking logic.

---

## 10. Open decisions (to lock with PM)

1. Whether waitlist receives the same booking code format as confirmed slots.
2. Whether reschedule/cancel require the user to type or speak the code only (no lookup by phone—aligned with no PII); chat validates the same flow before voice.
3. Exact secure URL issuer and token model (out of band to this voice stack).

---

## Summary

This architecture satisfies the milestone: practical voice UX, safe intent handling, and real-world orchestration via **actual** FastMCP-wrapped Google APIs (Calendar, Docs, Gmail)—with the LLM agent calling those MCP tools from Phase 3—while keeping PII off the call and advice boundaries explicit—with **chat as the build-and-test harness** and voice as a later adapter layer.
