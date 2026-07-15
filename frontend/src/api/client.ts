export type TurnResponse = {
  messages: string[]
  state: string
  session_id: string
  events: Record<string, unknown>[]
  meta: Record<string, unknown>
}

function resolveApiBase(): string {
  const fromEnv = (import.meta.env.VITE_API_BASE as string | undefined)?.trim()
  if (fromEnv) return fromEnv.replace(/\/$/, '')

  // Optional runtime override: <meta name="api-base" content="https://...">
  if (typeof document !== 'undefined') {
    const meta = document.querySelector('meta[name="api-base"]')?.getAttribute('content')?.trim()
    if (meta) return meta.replace(/\/$/, '')
  }

  return ''
}

const API_BASE = resolveApiBase()

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  let res: Response
  try {
    res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      ...init,
    })
  } catch {
    throw new Error(
      `Cannot reach API at ${url || path}. Set VITE_API_BASE to your API URL ` +
        `(e.g. https://appointment-scheduler-tan.vercel.app) and redeploy the frontend.`,
    )
  }
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function getApiBase(): string {
  return API_BASE
}

export function checkHealth() {
  return request<{ status: string }>('/health')
}

export function createSession(channel: 'chat' | 'voice' = 'voice') {
  return request<TurnResponse>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ channel }),
  })
}

export function sendMessage(sessionId: string, text: string) {
  return request<TurnResponse>(`/sessions/${sessionId}/message`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}
