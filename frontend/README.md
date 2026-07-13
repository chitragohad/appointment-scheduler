# Frontend — Acoustic Serenity (Stitch)

Voice-first desktop UI for **Advisor Appointment Scheduler**, built from:

- `stitch_voice_concierge_scheduler/acoustic_serenity/DESIGN.md`
- Stitch frames: idle, listening/disclaimer, slot offer, booking confirmed

## Run

Terminal 1 — API:

```bash
cd ..
source .venv/bin/activate
python -m advisor_scheduler --serve --host 127.0.0.1 --port 8000
```

Terminal 2 — UI:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:5173

Vite proxies `/sessions` and `/health` to the API.

## Notes

- Mic uses the Web Speech API (Chrome/Edge best). Typing fallback is available.
- TTS reads assistant messages aloud.
- Design tokens follow Acoustic Serenity (Playfair Display + Fira Sans, teal trust palette).
