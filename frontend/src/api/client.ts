export type TurnResponse = {
  messages: string[]
  state: string
  session_id: string
  events: Record<string, unknown>[]
  meta: Record<string, unknown>
}

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
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
