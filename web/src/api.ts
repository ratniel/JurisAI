import type {
  CreateMessageResponse,
  CreateSessionResponse,
  GetSessionResponse,
} from './types'

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Request failed with status ${response.status}`)
  }

  return (await response.json()) as T
}

export async function createSession(): Promise<CreateSessionResponse> {
  return requestJson<CreateSessionResponse>('/api/chat/sessions', {
    method: 'POST',
  })
}

export async function getSession(sessionId: string): Promise<GetSessionResponse> {
  return requestJson<GetSessionResponse>(`/api/chat/sessions/${sessionId}`)
}

export async function createMessage(
  sessionId: string,
  message: string,
): Promise<CreateMessageResponse> {
  return requestJson<CreateMessageResponse>(`/api/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}

