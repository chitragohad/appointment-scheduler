import { useCallback, useEffect, useRef, useState } from 'react'

type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  onstart: (() => void) | null
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: ArrayLike<
    ArrayLike<{ transcript: string }> & { isFinal?: boolean; length: number }
  > & { length: number }
}

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
    SpeechRecognition?: new () => SpeechRecognitionLike
  }
}

type SpeakOptions = {
  onEnd?: () => void
  onStart?: () => void
}

const PREFERRED_VOICE_NAMES = [
  'Google UK English Female',
  'Google US English',
  'Samantha',
  'Karen',
  'Moira',
  'Tessa',
  'Fiona',
  'Victoria',
  'Microsoft Aria Online (Natural) - English (United States)',
  'Microsoft Jenny Online (Natural) - English (United States)',
  'Microsoft Sonia Online (Natural) - English (United Kingdom)',
  'Microsoft Neerja Online (Natural) - English (India)',
  'Microsoft Ravi Online (Natural) - English (India)',
  'Google UK English Male',
]

function scoreVoice(voice: SpeechSynthesisVoice): number {
  const name = voice.name.toLowerCase()
  let score = 0
  if (/premium|enhanced|natural|neural|online \(natural\)/.test(name)) score += 120
  if (/google/.test(name)) score += 80
  if (/samantha|karen|moira|tessa|fiona|victoria|aria|jenny|sonia|neerja/.test(name)) score += 70
  if (/microsoft/.test(name)) score += 40
  if (voice.localService) score += 15
  if (/female|woman/.test(name)) score += 8
  if (/compact|eloquence|novelty|zarvox|whisper|bad news|good news|pipes|trinoids|boing|bubbles|cellos/.test(name))
    score -= 200
  if (/espeak|robot|dummy/.test(name)) score -= 300
  if (voice.lang.toLowerCase().startsWith('en-in')) score += 25
  else if (voice.lang.toLowerCase().startsWith('en-gb')) score += 20
  else if (voice.lang.toLowerCase().startsWith('en-us')) score += 18
  else if (voice.lang.toLowerCase().startsWith('en')) score += 10
  else score -= 50
  const preferredIndex = PREFERRED_VOICE_NAMES.findIndex((n) => n.toLowerCase() === name)
  if (preferredIndex >= 0) score += 100 - preferredIndex
  return score
}

function pickBestVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null
  const english = voices.filter((v) => v.lang.toLowerCase().startsWith('en'))
  const pool = english.length ? english : voices
  return [...pool].sort((a, b) => scoreVoice(b) - scoreVoice(a))[0] ?? null
}

/** Soften TTS text and keep chunks short so Chrome does not cut mid-phrase. */
function prepareSpeechChunks(text: string): string[] {
  const cleaned = text
    .replace(/\s+/g, ' ')
    .replace(/NL-/gi, 'N L dash ')
    .replace(/\bIST\b/g, 'I S T')
    .replace(/\bMCP\b/g, '')
    .replace(/calendar_create_hold|docs_append_prebooking|gmail_create_draft/gi, '')
    .replace(/Google side effects completed via[^.]+\.?/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()

  if (!cleaned) return []

  const sentences = cleaned.match(/[^.!?]+[.!?]+|[^.!?]+$/g) ?? [cleaned]
  const chunks: string[] = []

  for (const raw of sentences) {
    const sentence = raw.trim()
    if (!sentence) continue
    if (sentence.length <= 180) {
      chunks.push(sentence)
      continue
    }
    // Split long sentences on commas / semicolons
    let buf = ''
    for (const part of sentence.split(/(?<=[,;:])\s+/)) {
      const next = buf ? `${buf} ${part}` : part
      if (next.length > 180 && buf) {
        chunks.push(buf.trim())
        buf = part
      } else {
        buf = next
      }
    }
    if (buf.trim()) chunks.push(buf.trim())
  }

  return chunks.filter(Boolean)
}

export function useSpeech() {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(false)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const onFinalRef = useRef<((text: string) => void) | null>(null)
  const onErrorRef = useRef<((message: string) => void) | null>(null)
  const intentionalStopRef = useRef(false)
  const finalBufferRef = useRef('')
  const speakEndRef = useRef<(() => void) | null>(null)
  const speakingRef = useRef(false)
  const speakTokenRef = useRef(0)
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null)
  const resumeTimerRef = useRef<number | null>(null)

  const clearResumeTimer = useCallback(() => {
    if (resumeTimerRef.current != null) {
      window.clearInterval(resumeTimerRef.current)
      resumeTimerRef.current = null
    }
  }, [])

  const refreshVoice = useCallback(() => {
    if (!('speechSynthesis' in window)) return
    const voices = window.speechSynthesis.getVoices()
    if (voices.length) voiceRef.current = pickBestVoice(voices)
  }, [])

  useEffect(() => {
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition
    setSupported(Boolean(Ctor))
    refreshVoice()
    if ('speechSynthesis' in window) {
      window.speechSynthesis.addEventListener('voiceschanged', refreshVoice)
    }
    return () => {
      intentionalStopRef.current = true
      speakTokenRef.current += 1
      speakingRef.current = false
      clearResumeTimer()
      recognitionRef.current?.abort()
      if ('speechSynthesis' in window) {
        window.speechSynthesis.removeEventListener('voiceschanged', refreshVoice)
        window.speechSynthesis.cancel()
      }
    }
  }, [clearResumeTimer, refreshVoice])

  const stopSpeaking = useCallback(() => {
    speakTokenRef.current += 1
    speakingRef.current = false
    speakEndRef.current = null
    clearResumeTimer()
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  }, [clearResumeTimer])

  const speak = useCallback(
    (text: string, opts?: SpeakOptions) => {
      if (!('speechSynthesis' in window) || !text.trim()) {
        opts?.onEnd?.()
        return
      }

      refreshVoice()
      const chunks = prepareSpeechChunks(text)
      if (!chunks.length) {
        opts?.onEnd?.()
        return
      }

      // Cancel previous speech cleanly, then wait a beat so audio does not crack
      speakTokenRef.current += 1
      const token = speakTokenRef.current
      speakingRef.current = true
      speakEndRef.current = opts?.onEnd ?? null
      clearResumeTimer()
      window.speechSynthesis.cancel()

      const voice = voiceRef.current
      let started = false
      let index = 0

      const finish = () => {
        if (token !== speakTokenRef.current) return
        speakingRef.current = false
        clearResumeTimer()
        const end = speakEndRef.current
        speakEndRef.current = null
        end?.()
      }

      const speakNext = () => {
        if (token !== speakTokenRef.current) return
        if (index >= chunks.length) {
          finish()
          return
        }

        const utter = new SpeechSynthesisUtterance(chunks[index])
        index += 1

        if (voice) {
          utter.voice = voice
          utter.lang = voice.lang
        } else {
          utter.lang = 'en-GB'
        }

        // Slightly slower + neutral pitch reads more natural / less robotic
        utter.rate = 0.92
        utter.pitch = 1.02
        utter.volume = 1

        utter.onstart = () => {
          if (token !== speakTokenRef.current) return
          if (!started) {
            started = true
            opts?.onStart?.()
            // Chrome can silently pause long sessions; nudge only while speaking
            clearResumeTimer()
            resumeTimerRef.current = window.setInterval(() => {
              if (!speakingRef.current || token !== speakTokenRef.current) {
                clearResumeTimer()
                return
              }
              if (window.speechSynthesis.paused) window.speechSynthesis.resume()
            }, 5000)
          }
        }

        utter.onend = () => {
          if (token !== speakTokenRef.current) return
          // Tiny gap between chunks sounds more human than a hard cut
          window.setTimeout(speakNext, 90)
        }

        utter.onerror = () => {
          if (token !== speakTokenRef.current) return
          // Skip broken chunk and continue rather than aborting the whole turn
          window.setTimeout(speakNext, 60)
        }

        window.speechSynthesis.speak(utter)
      }

      window.setTimeout(speakNext, 80)
    },
    [clearResumeTimer, refreshVoice],
  )

  const stopListening = useCallback(() => {
    intentionalStopRef.current = true
    const rec = recognitionRef.current
    recognitionRef.current = null
    try {
      rec?.abort()
    } catch {
      /* ignore */
    }
    setListening(false)
  }, [])

  const startListening = useCallback(
    (
      onFinal: (text: string) => void,
      opts?: { onError?: (message: string) => void },
    ) => {
      const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition
      if (!Ctor) return false

      // Mic and TTS fight for the audio channel — stop speech first
      stopSpeaking()

      intentionalStopRef.current = true
      try {
        recognitionRef.current?.abort()
      } catch {
        /* ignore */
      }
      recognitionRef.current = null
      intentionalStopRef.current = false
      finalBufferRef.current = ''
      onFinalRef.current = onFinal
      onErrorRef.current = opts?.onError ?? null

      const recognition = new Ctor()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-IN'

      recognition.onstart = () => setListening(true)

      recognition.onresult = (event) => {
        let interim = ''
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const piece = event.results[i]
          const transcript = piece?.[0]?.transcript?.trim() ?? ''
          if (!transcript) continue
          if (piece.isFinal) {
            finalBufferRef.current = `${finalBufferRef.current} ${transcript}`.trim()
          } else {
            interim = transcript
          }
        }

        if (finalBufferRef.current) {
          const spoken = finalBufferRef.current
          finalBufferRef.current = ''
          intentionalStopRef.current = true
          try {
            recognition.stop()
          } catch {
            /* ignore */
          }
          setListening(false)
          onFinalRef.current?.(spoken)
          return
        }

        void interim
      }

      recognition.onerror = (event) => {
        setListening(false)
        if (intentionalStopRef.current) return
        if (event.error === 'aborted' || event.error === 'no-speech') return
        if (event.error === 'not-allowed') {
          onErrorRef.current?.(
            'Microphone permission blocked. Allow mic access, then tap the orb to speak.',
          )
          return
        }
        onErrorRef.current?.(`Voice error: ${event.error}. Tap the orb and try again.`)
      }

      recognition.onend = () => {
        setListening(false)
        recognitionRef.current = null
        if (!intentionalStopRef.current && finalBufferRef.current) {
          const spoken = finalBufferRef.current
          finalBufferRef.current = ''
          onFinalRef.current?.(spoken)
        }
      }

      recognitionRef.current = recognition
      try {
        recognition.start()
        setListening(true)
        return true
      } catch {
        window.setTimeout(() => {
          try {
            recognition.start()
            setListening(true)
          } catch {
            onErrorRef.current?.('Could not start the microphone. Tap the orb to try again.')
            setListening(false)
          }
        }, 250)
        return true
      }
    },
    [stopSpeaking],
  )

  return { listening, supported, speak, stopSpeaking, startListening, stopListening }
}
