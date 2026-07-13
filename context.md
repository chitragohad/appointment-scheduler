# Context: Advisor Appointment Scheduler

## Overview

**Voice Agent: Advisor Appointment Scheduler** is a compliant, pre-booking voice assistant that helps users quickly secure a tentative slot with a human advisor.

It collects the consultation topic and preferred time, offers available slots, confirms the booking, and generates a unique booking code. The agent then creates a calendar hold, updates internal notes, and drafts an approval-gated email using MCP. No personal data is taken on the call; clear disclaimers are enforced; and users receive a secure link to complete details later.

This milestone tests practical voice UX, safe intent handling, and real-world AI system orchestration — not just conversation quality.

## Who This Helps

- Users who want a human consult
- PMs / Support running compliant pre-booking

## Milestone Goal

Build a voice agent that:

1. Books a tentative advisor slot
2. Collects topic + time preference
3. Offers two slots
4. Confirms the booking
5. Creates a calendar hold, notes entry, and email draft via MCP
6. Gives the caller a booking code and a secure link to finish details

## Intents (5)

| Intent | Purpose |
|--------|---------|
| Book new | Start a new tentative advisor booking |
| Reschedule | Change an existing booking |
| Cancel | Cancel an existing booking |
| What to prepare | Guidance on preparing for the consult |
| Check availability windows | Look up available time windows |

## Conversation Flow

```
greet
  → disclaimer (“informational, not investment advice”)
  → confirm topic
  → collect day/time preference
  → offer two slots (mock calendar)
  → on confirm:
       → generate booking code
       → MCP Calendar hold
       → MCP Notes/Doc entry
       → MCP Email draft (approval-gated)
       → read booking code + secure URL for contact details
```

### Topic Categories

- KYC / Onboarding
- SIP / Mandates
- Statements / Tax Docs
- Withdrawals & Timelines
- Account Changes / Nominee

### On Confirm Actions

1. **Generate Booking Code** — e.g. `NL-A742`
2. **MCP Calendar** — create tentative hold titled:  
   `Advisor Q&A — {Topic} — {Code}`
3. **MCP Notes/Doc** — append `{date, topic, slot, code}` to **Advisor Pre-Bookings**
4. **MCP Email Draft** — prepare advisor email with details (approval-gated)
5. **Caller handoff** — read the booking code aloud and provide a secure URL to complete contact details outside the call

## Key Constraints

| Constraint | Detail |
|------------|--------|
| No PII on the call | Do not collect phone, email, or account numbers |
| Time zone | State **IST**; repeat date/time on confirm |
| No matching slots | Create waitlist hold + draft email |
| No investment advice | Refuse advice; provide educational links if asked |
| Disclaimer | Enforce “informational, not investment advice” |

## Deliverables

| Deliverable | Description |
|-------------|-------------|
| Working voice demo | Live link **or** ≤3-min call recording |
| Calendar hold screenshot | Title must include booking code |
| Notes + Email draft | Screenshot or text of Notes/Doc entry and email draft |
| Script file | Short prompts/utterances used |
| README | Mock calendar JSON; how reschedule/cancel works |

## Success Criteria

- Compliant pre-booking voice UX (disclaimer + no PII)
- All five intents handled safely
- End-to-end orchestration: booking code → calendar → notes → approval-gated email
- Caller leaves with booking code + secure link to finish details offline
