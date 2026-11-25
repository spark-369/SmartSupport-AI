/** Typed fetch wrapper with single-flight access-token refresh on 401. */

import type { ChatErrorBody, TokenPair } from '@/types'

const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let accessToken: string | null = null
let refreshInFlight: Promise<string | null> | null = null

/** Called by the auth store so the wrapper never imports it (no cycles). */
export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

async function parseError(response: Response): Promise<ChatErrorBody['error']> {
  try {
    const body = (await response.json()) as ChatErrorBody
    return body.error ?? { code: 'unknown_error', message: response.statusText }
  } catch {
    return { code: 'unknown_error', message: response.statusText || 'Request failed' }
  }
}

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) return null
      const pair = (await response.json()) as TokenPair
      accessToken = pair.access_token
      window.dispatchEvent(new CustomEvent('ss:token-refreshed', { detail: pair.access_token }))
      return pair.access_token
    } catch {
      return null
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean; retry?: boolean } = {},
): Promise<T> {
  const { auth = true, retry = true, ...init } = options
  const headers = new Headers(init.headers)
  if (auth && accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })

  if (response.status === 401 && auth && retry) {
    const token = await refreshAccessToken()
    if (token) {
      return request<T>(path, { ...options, retry: false })
    }
    window.dispatchEvent(new CustomEvent('ss:session-expired'))
    throw new ApiError(401, 'unauthorized', 'Session expired. Please sign in again.')
  }

  if (!response.ok) {
    const error = await parseError(response)
    throw new ApiError(response.status, error.code, error.message, error.details)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Download a binary endpoint (e.g. an original manual) with auth + 401 retry. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const doFetch = (token: string | null) =>
    fetch(`${API_BASE}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
    })

  let response = await doFetch(accessToken)
  if (response.status === 401) {
    const token = await refreshAccessToken()
    if (token) response = await doFetch(token)
  }
  if (!response.ok) {
    const error = await parseError(response)
    throw new ApiError(response.status, error.code, error.message, error.details)
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
}
