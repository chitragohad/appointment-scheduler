# Google Stitch Prompt — Voice AI Agent Desktop UI

Copy everything below the line into Google Stitch.

---

Design a **desktop web UI (1440×900)** for **Advisor Appointment Scheduler** — a **voice-first AI agent** that books a **tentative** appointment with a human financial advisor. The primary interaction is **talking to the agent**, not typing in a chat box. Product name must be the hero-level brand signal on the first viewport.

## Product job (one screen)

One composition, not a dashboard. First viewport job: **start a voice call with the AI agent and book an advisor appointment**.  

Voice does the booking. The UI supports listening, speaking, and confirming — it does not look like a generic chatbot or call-center console.

No PII on the call (no phone, email, or account-number fields). Contact details are completed later via a secure link after the booking code is issued.

## Primary flow to design for (Book Appointment)

Voice journey the UI must make visible:

1. **Start voice session** (tap mic / “Talk to agent”)  
2. **Disclaimer** — agent speaks: informational, **not investment advice**; user says “I understand”  
3. **Topic** — KYC/Onboarding · SIP/Mandates · Statements/Tax Docs · Withdrawals & Timelines · Account Changes/Nominee  
4. **Time preference** — day/window in **IST**  
5. **Two slot offers** — agent reads two options; user picks “one” or “two”  
6. **Confirm** — agent repeats full date/time + IST  
7. **Done** — booking code (`NL-A742`) + secure link on screen while agent spells the code aloud  

Secondary voice intents (quiet, not competing with Book): Reschedule, Cancel, What to prepare, Check availability — code-only for reschedule/cancel.

## Layout (desktop, voice-first)

Single focused composition — **voice stage is the hero**, not a transcript sidebar.

- **Center stage (dominant):** Brand wordmark, one short line (“Book a tentative advisor appointment by voice”), large **voice orb / waveform**, primary CTA **Start talking**, live state label (Idle / Listening / Agent speaking / Processing).  
- **Supporting strip (secondary):** live caption of the last agent line (accessibility + trust), optional compact step indicator for the book flow (Disclaimer → Topic → Time → Slots → Confirm).  
- **No** chat composer as the main control. Optional small “type instead” link only, visually demoted.  
- Avoid dashboards, KPI strips, card grids in the hero, floating promo badges, or sticker overlays on the voice visual.

Suggested wireframe:

```
+------------------------------------------------------------------+
|                         ADVISOR APPOINTMENT SCHEDULER            |
|              Book a tentative advisor slot by voice · IST        |
+------------------------------------------------------------------+
|                                                                  |
|                         [  VOICE ORB / WAVE  ]                   |
|                      status: Listening…                          |
|                                                                  |
|              [  Start talking  ]     [  End session  ]           |
|                                                                  |
|   Live caption: “This is informational, not investment advice…”  |
|                                                                  |
|   Steps: Disclaimer · Topic · Time · Slots · Confirm             |
+------------------------------------------------------------------+
| Quiet intents: Reschedule · Cancel · Prepare · Availability      |
| Footer: No PII on call · Secure link after booking · IST         |
+------------------------------------------------------------------+
```

## Key UI states to show (design 3–4 desktop frames)

1. **Idle / ready to book** — brand hero + Start talking; calm atmosphere; no clutter.  
2. **Listening / agent speaking** — clear mic active vs agent TTS state; caption shows disclaimer or topic prompt.  
3. **Slot offer (voice + visual)** — two IST appointment options shown as selectable rows while agent reads them; user can click or say “option one / two”.  
4. **Appointment booked** — success state with booking code `NL-A742` (large, readable for spelling), confirmed IST datetime, secure details link CTA. No PII form.

## Visual direction

Voice-AI appointment desk for Indian wealth/ops users — trustworthy, calm, modern. Feels like a **spoken concierge**, not a consumer bank ad and not a neon “AI demo”.

- **Atmosphere:** soft layered background (muted teal–slate gradient or quiet acoustic grain). Avoid flat white; avoid purple/indigo glow AI clichés; avoid cream + terracotta serif cliché; avoid dark-mode neon.  
- **Typography:** expressive brand display used sparingly + clear humanist sans for captions and booking code. No Inter/Roboto/Arial as the brand face.  
- **Color tokens (propose named hex):** deep ink, mist ground, teal trust accent, amber for disclaimer attention, pine for booked success.  
- **Voice visual:** one distinctive orb/waveform signature — restrained motion, not particle fireworks.  
- **Controls:** primary mic CTA, secondary End session; slot rows without heavy card chrome. No emoji, no rounded-full pill clusters, no multi-layer shadows.  
- **Motion (2–3 only):** orb pulse while listening, caption fade-in, booking-code reveal. No decorative noise.

## Content rules for mock copy

- Brand: **Advisor Appointment Scheduler** (hero-level).  
- Headline support: “Book a tentative advisor appointment by voice.”  
- Disclaimer line must include **“informational, not investment advice.”**  
- Times always labeled **IST**.  
- Booking code format: `NL-XXXX`.  
- CTAs: “Start talking”, “I understand”, “Option 1 / Option 2”, “End session”, “Open secure link”.  
- Never show phone / email / account inputs.

## Accessibility

- Desktop-first (also readable at 1280px).  
- Live captions for agent speech.  
- Visible focus on mic and slot rows; high contrast.  
- Respect reduced-motion: static orb alternative.

## Deliverables from Stitch

1. High-fidelity **voice-first** desktop home (book appointment)  
2. Frames for Listening/Speaking, Slot offer, Booking confirmed  
3. Component notes: voice orb, mic CTA, live caption, step indicator, slot row, booking-code block  

Brand test: if you remove the nav, the first viewport must still read as **Advisor Appointment Scheduler** — a voice agent to book an advisor appointment — not a generic AI voice widget.
