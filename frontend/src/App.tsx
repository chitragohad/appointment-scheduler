import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import {
  checkHealth,
  createSession,
  getApiBase,
  sendMessage,
  type TurnResponse,
} from './api/client'
import { AppShell } from './components/AppShell'
import { BookingConfirmed } from './components/BookingConfirmed'
import { LiveCaption } from './components/LiveCaption'
import { SlotOffer } from './components/SlotOffer'
import { StepIndicator } from './components/StepIndicator'
import { VoiceOrb } from './components/VoiceOrb'
import { useSpeech } from './hooks/useSpeech'

type UiPhase = 'idle' | 'session' | 'slots' | 'confirmed'

function stepForState(state: string): 'Welcome' | 'Disclaimer' | 'Topic' | 'Time' | 'Slots' | 'Confirm' {
  if (state === 'disclaimer') return 'Disclaimer'
  if (state === 'intent' || state === 'topic' || state === 'prepare_topic') return 'Topic'
  if (state === 'preference' || state === 'reschedule_preference') return 'Time'
  if (state === 'offer_slots' || state === 'reschedule_offer') return 'Slots'
  if (
    state === 'confirm' ||
    state === 'reschedule_confirm' ||
    state === 'close' ||
    state === 'ended' ||
    state === 'orchestrate'
  )
    return 'Confirm'
  return 'Welcome'
}

function formatSlotLabel(iso: string): string {
  try {
    const dt = new Date(iso)
    return new Intl.DateTimeFormat('en-IN', {
      weekday: 'long',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'Asia/Kolkata',
      timeZoneName: 'short',
    }).format(dt)
  } catch {
    return iso
  }
}

const SUGGESTIONS = [
  { title: 'Next available', prompt: 'book a new slot', hint: 'Book a tentative advisor slot' },
  { title: 'Prepare', prompt: 'what should I prepare', hint: 'Ask what to prepare' },
  { title: 'Availability', prompt: 'what times are available', hint: 'Check availability windows' },
  { title: 'Reschedule', prompt: 'I want to reschedule', hint: 'Change an existing booking' },
] as const

const TOPICS = [
  { label: '1 · KYC/Onboarding', prompt: '1' },
  { label: '2 · SIP/Mandates', prompt: '2' },
  { label: '3 · Statements/Tax Docs', prompt: '3' },
  { label: '4 · Withdrawals & Timelines', prompt: '4' },
  { label: '5 · Account Changes/Nominee', prompt: '5' },
] as const

function speakableText(messages: string[]): string {
  return messages
    .filter((m) => {
      const lower = m.toLowerCase()
      if (lower.includes('google side effects')) return false
      if (lower.includes('mcp')) return false
      if (lower.includes('calendar_create_hold')) return false
      if (lower.includes('docs_append_prebooking')) return false
      if (lower.includes('gmail_create_draft')) return false
      if (lower.startsWith('some google mcp')) return false
      return true
    })
    .join(' ')
    .trim()
}

export default function App() {
  const { listening, supported, speak, stopSpeaking, startListening, stopListening } = useSpeech()
  const [phase, setPhase] = useState<UiPhase>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [state, setState] = useState('idle')
  const [messages, setMessages] = useState<string[]>([])
  const [meta, setMeta] = useState<Record<string, unknown>>({})
  const [orbMode, setOrbMode] = useState<'idle' | 'listening' | 'speaking' | 'processing' | 'success'>('idle')
  const [statusLabel, setStatusLabel] = useState('Start talking')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  const busyRef = useRef(false)
  const phaseRef = useRef<UiPhase>('idle')
  const sessionIdRef = useRef<string | null>(null)
  const listenAfterSpeakRef = useRef(true)
  const handleUserTextRef = useRef<(text: string) => Promise<void>>(async () => {})

  useEffect(() => {
    busyRef.current = busy
  }, [busy])
  useEffect(() => {
    phaseRef.current = phase
  }, [phase])
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        await checkHealth()
      } catch (err) {
        if (cancelled) return
        const base = getApiBase() || '(same origin)'
        setError(
          err instanceof Error
            ? err.message
            : `API health check failed. Current API base: ${base}`,
        )
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const caption =
    [...messages].reverse().find((m) => Boolean(speakableText([m]))) ??
    messages[messages.length - 1] ??
    ''

  const slots = useMemo(() => {
    const raw = (meta.offered_slots as Array<{ id: string; start: string }> | undefined) ?? []
    return raw.map((s, i) => ({
      id: s.id,
      label: `Option ${i + 1}`,
      startText: formatSlotLabel(s.start),
    }))
  }, [meta])

  const beginListening = useCallback(() => {
    if (busyRef.current) return
    if (phaseRef.current === 'idle' || phaseRef.current === 'confirmed') return

    const ok = startListening(
      (text) => {
        void handleUserTextRef.current(text)
      },
      {
        onError: (message) => {
          setError(message)
          setOrbMode('idle')
          setStatusLabel('Tap mic to speak')
        },
      },
    )

    if (ok) {
      setError(null)
      setOrbMode('listening')
      setStatusLabel('Listening… speak now')
    } else {
      setError('Voice recognition is not available in this browser. Use the text box below.')
      setOrbMode('idle')
      setStatusLabel('Type below')
    }
  }, [startListening])

  const applyTurn = useCallback(
    (turn: TurnResponse, opts?: { speakMessages?: boolean; listenAfter?: boolean }) => {
      setSessionId(turn.session_id)
      sessionIdRef.current = turn.session_id
      setState(turn.state)
      setMessages(turn.messages)
      setMeta(turn.meta ?? {})

      const done = turn.state === 'close' || turn.state === 'ended'
      const offering = turn.state === 'offer_slots' || turn.state === 'reschedule_offer'

      if (offering) {
        setPhase('slots')
        phaseRef.current = 'slots'
      } else if (done) {
        setPhase('confirmed')
        phaseRef.current = 'confirmed'
        setOrbMode('success')
        setStatusLabel('Confirmed')
      } else {
        setPhase('session')
        phaseRef.current = 'session'
      }

      const shouldSpeak = opts?.speakMessages !== false
      const shouldListen = opts?.listenAfter !== false && !done
      listenAfterSpeakRef.current = shouldListen

      if (!shouldSpeak) {
        if (shouldListen) {
          window.setTimeout(() => beginListening(), 200)
        }
        return
      }

      const joined = speakableText(turn.messages)
      if (!joined) {
        if (shouldListen) window.setTimeout(() => beginListening(), 200)
        return
      }

      setOrbMode('speaking')
      setStatusLabel('Agent speaking…')
      window.setTimeout(() => {
        speak(joined, {
          onEnd: () => {
            if (!listenAfterSpeakRef.current) return
            if (phaseRef.current === 'confirmed' || phaseRef.current === 'idle') return
            // Brief gap so TTS releases the mic before STT starts (avoid prompt echo)
            window.setTimeout(() => beginListening(), 900)
          },
        })
      }, 160)
    },
    [beginListening, speak],
  )

  const handleUserText = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || busyRef.current) return
      busyRef.current = true
      setBusy(true)
      setError(null)
      listenAfterSpeakRef.current = false
      stopSpeaking()
      stopListening()
      setOrbMode('processing')
      setStatusLabel('Processing…')

      try {
        const activeSession = sessionIdRef.current
        let turn: TurnResponse
        if (!activeSession) {
          turn = await createSession('voice')
          applyTurn(turn, { speakMessages: true, listenAfter: false })
          if (trimmed.toLowerCase() !== 'start') {
            const follow = await sendMessage(turn.session_id, trimmed)
            applyTurn(follow)
          } else {
            listenAfterSpeakRef.current = true
            window.setTimeout(() => beginListening(), 400)
          }
        } else {
          turn = await sendMessage(activeSession, trimmed)
          applyTurn(turn)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Something went wrong')
        setOrbMode('idle')
        setStatusLabel('Tap mic to speak')
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [applyTurn, beginListening, stopListening, stopSpeaking],
  )

  handleUserTextRef.current = handleUserText

  const startSession = useCallback(async () => {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setError(null)
    stopSpeaking()
    stopListening()
    setOrbMode('processing')
    setStatusLabel('Connecting…')
    try {
      const turn = await createSession('voice')
      applyTurn(turn)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start session')
      setOrbMode('idle')
      setStatusLabel('Start talking')
      setPhase('idle')
      phaseRef.current = 'idle'
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [applyTurn, stopListening, stopSpeaking])

  const toggleMic = useCallback(() => {
    if (busyRef.current) return
    if (phaseRef.current === 'idle') {
      void startSession()
      return
    }
    if (phaseRef.current === 'confirmed') return
    if (listening) {
      stopListening()
      setOrbMode('idle')
      setStatusLabel('Tap mic to speak')
      return
    }
    listenAfterSpeakRef.current = false
    stopSpeaking()
    beginListening()
  }, [beginListening, listening, startSession, stopListening, stopSpeaking])

  const endSession = useCallback(() => {
    listenAfterSpeakRef.current = false
    stopSpeaking()
    stopListening()
    setPhase('idle')
    phaseRef.current = 'idle'
    setSessionId(null)
    sessionIdRef.current = null
    setState('idle')
    setMessages([])
    setMeta({})
    setOrbMode('idle')
    setStatusLabel('Start talking')
    setError(null)
    setDraft('')
  }, [stopListening, stopSpeaking])

  const onSubmitDraft = (e: FormEvent) => {
    e.preventDefault()
    const value = draft
    setDraft('')
    void handleUserText(value)
  }

  const bookingCode = String(meta.booking_code ?? '')
  const secureUrl = String(meta.secure_details_url ?? '')
  const selectedWhen =
    typeof meta.selected_slot_start === 'string'
      ? formatSlotLabel(meta.selected_slot_start)
      : typeof meta.slot_start === 'string'
        ? formatSlotLabel(meta.slot_start)
        : ''
  const whenText =
    selectedWhen ||
    slots[0]?.startText ||
    (typeof meta.selected_slot_id === 'string' ? 'your selected IST slot' : 'your confirmed IST slot')

  return (
    <AppShell
      onIntent={(prompt) => {
        void handleUserText(prompt)
      }}
    >
      {phase === 'idle' && (
        <section className="relative flex flex-1 flex-col items-center justify-center overflow-hidden px-gutter py-xl">
          <div
            className="pointer-events-none absolute h-80 w-80 rounded-full opacity-40"
            style={{
              background:
                'radial-gradient(circle at center, #95d1d1 0%, #0c5252 70%, transparent 100%)',
              filter: 'blur(40px)',
            }}
            aria-hidden
          />
          <div className="relative z-10 flex w-full max-w-[1140px] flex-col items-center space-y-lg text-center">
            <div className="space-y-base">
              <h1 className="mx-auto max-w-3xl text-display-brand text-primary max-md:text-headline-lg">
                ADVISOR APPOINTMENT SCHEDULER
              </h1>
              <p className="mx-auto w-full max-w-2xl text-center text-body-lg text-secondary">
                Book a tentative advisor appointment by voice · IST
              </p>
            </div>

            <VoiceOrb mode={orbMode} statusLabel={statusLabel} onClick={toggleMic} />

            <div className="grid w-full grid-cols-1 gap-base pt-lg opacity-90 md:grid-cols-2 lg:grid-cols-4">
              {SUGGESTIONS.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => void handleUserText(item.prompt)}
                  className="rounded-lg border border-outline-variant bg-surface-container-lowest p-md text-left transition hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  <p className="mb-xs text-label-sm uppercase tracking-wider text-secondary">
                    {item.title}
                  </p>
                  <p className="text-body-md font-medium text-primary">{item.hint}</p>
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {phase === 'session' && (
        <section className="relative flex flex-1 flex-col items-center px-gutter pb-lg pt-xl">
          <div className="absolute inset-0 -z-10 bg-gradient-to-b from-surface-container-low to-background" />
          <StepIndicator active={stepForState(state)} />
          {state === 'disclaimer' && (
            <p className="mb-md w-full max-w-2xl text-center text-label-md leading-relaxed text-amber-caution">
              Informational only — not investment advice. Please say “I understand”.
            </p>
          )}
          <VoiceOrb
            mode={listening ? 'listening' : orbMode}
            statusLabel={listening ? 'Listening… speak now' : statusLabel}
            onClick={toggleMic}
          />
          <p className="mt-md w-full max-w-2xl text-center text-body-lg leading-relaxed text-on-surface-variant opacity-80">
            {state === 'disclaimer'
              ? 'Please confirm you understand the disclosure.'
              : 'Speak naturally, or type below.'}
          </p>
          <LiveCaption text={caption} />
          {state === 'topic' && (
            <div className="mt-lg grid w-full max-w-2xl grid-cols-1 gap-sm sm:grid-cols-2">
              {TOPICS.map((topic) => (
                <button
                  key={topic.prompt}
                  type="button"
                  onClick={() => void handleUserText(topic.prompt)}
                  className="rounded-lg border border-outline-variant bg-surface-container-lowest px-md py-sm text-left text-body-md text-primary transition hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  {topic.label}
                </button>
              ))}
            </div>
          )}
          <div className="mt-lg flex w-full max-w-2xl flex-wrap items-center justify-center gap-md">
            {state === 'disclaimer' && (
              <button
                type="button"
                className="rounded-lg bg-primary px-lg py-sm text-label-md text-on-primary hover:bg-primary-container"
                onClick={() => void handleUserText('I understand')}
              >
                I understand
              </button>
            )}
            {(state === 'confirm' || state === 'reschedule_confirm') && (
              <>
                <button
                  type="button"
                  className="rounded-lg bg-primary px-lg py-sm text-label-md text-on-primary hover:bg-primary-container"
                  onClick={() => void handleUserText('yes')}
                >
                  Yes, confirm
                </button>
                <button
                  type="button"
                  className="rounded-lg border border-primary px-lg py-sm text-label-md text-primary hover:bg-surface-container"
                  onClick={() => void handleUserText('pick again')}
                >
                  No / pick again
                </button>
              </>
            )}
            <button
              type="button"
              className="rounded-lg border border-secondary px-lg py-sm text-label-md text-secondary hover:bg-surface-container"
              onClick={endSession}
            >
              End session
            </button>
          </div>
        </section>
      )}

      {phase === 'slots' && (
        <section className="flex flex-1 flex-col items-center px-gutter pb-lg pt-xl">
          <StepIndicator active="Slots" />
          <VoiceOrb
            mode={listening ? 'listening' : orbMode}
            statusLabel={listening ? 'Listening… speak now' : statusLabel}
            onClick={toggleMic}
          />
          <SlotOffer
            slots={slots}
            caption={caption || 'I have two slots available. Would you like option one or two?'}
            onSelect={(n) => void handleUserText(String(n))}
            onEnd={endSession}
          />
        </section>
      )}

      {phase === 'confirmed' && (
        <section className="flex flex-1 flex-col items-center px-gutter py-xl">
          <StepIndicator active="Confirm" />
          <BookingConfirmed
            code={bookingCode || 'NL-----'}
            whenText={whenText}
            secureUrl={secureUrl}
            onOpenSecureLink={() => {
              if (secureUrl) window.open(secureUrl, '_blank', 'noopener,noreferrer')
            }}
          />
          <button
            type="button"
            className="mt-xl rounded-lg border border-outline px-lg py-sm text-label-md text-secondary hover:border-primary hover:text-primary"
            onClick={endSession}
          >
            Book another appointment
          </button>
        </section>
      )}

      {phase !== 'idle' && phase !== 'confirmed' && (
        <form
          onSubmit={onSubmitDraft}
          className="relative z-20 mx-auto mb-lg flex w-full max-w-2xl gap-sm px-gutter"
        >
          <label className="sr-only" htmlFor="voice-fallback">
            Type instead of speaking
          </label>
          <input
            id="voice-fallback"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={supported ? 'Type instead of speaking…' : 'Type your reply…'}
            className="flex-1 border-0 border-b-2 border-outline-variant bg-transparent px-sm py-sm text-body-md text-on-surface outline-none transition focus:border-primary"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="rounded-lg bg-primary px-md py-sm text-label-md text-on-primary disabled:opacity-40"
          >
            Send
          </button>
        </form>
      )}

      {error && (
        <div className="mx-auto mb-md w-full max-w-xl rounded-lg border border-error-container bg-error-container/40 px-md py-sm text-center text-label-md text-on-error-container">
          {error}
        </div>
      )}
    </AppShell>
  )
}
