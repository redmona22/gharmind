const BASE: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'gharmind.token'

let accessToken: string | null = null
try {
  accessToken = sessionStorage.getItem(TOKEN_KEY)
} catch {
  accessToken = null
}

let unauthorizedHandler: (() => void) | null = null

export function getToken(): string | null {
  return accessToken
}

export function setToken(token: string | null): void {
  accessToken = token
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // sessionStorage can be unavailable; the in-memory copy still works.
  }
}

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  unauthorizedHandler = fn
}

export class ApiError extends Error {
  status: number
  code: string | null

  constructor(status: number, message: string, code: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type Options = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  // Raw file bytes (for example an .xlsx upload). Sent as-is, not as JSON.
  raw?: ArrayBuffer
}

function describeError(status: number, data: unknown): { message: string; code: string | null } {
  const detail =
    data && typeof data === 'object' && 'detail' in data
      ? (data as { detail: unknown }).detail
      : null

  if (typeof detail === 'string') return { message: detail, code: detail }

  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const d = detail as { code?: unknown; error?: unknown; message?: unknown }
    const code = typeof d.code === 'string' ? d.code : typeof d.error === 'string' ? d.error : null
    const message = typeof d.message === 'string' ? d.message : (code ?? `Request failed (${status})`)
    return { message, code }
  }

  if (Array.isArray(detail)) {
    return { message: 'Some fields are invalid. Please check and try again.', code: 'validation_error' }
  }

  return { message: `Request failed (${status})`, code: null }
}

export async function api<T = unknown>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const hasRaw = options.raw !== undefined
  if (hasRaw) headers['Content-Type'] = 'application/octet-stream'
  else if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  const token = accessToken
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      method: options.method ?? (hasRaw || options.body !== undefined ? 'POST' : 'GET'),
      headers,
      body: hasRaw ? options.raw : options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.', 'network_error')
  }

  if (response.status === 204) return undefined as T

  let data: unknown = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    // A 401 only means "session expired" if we actually sent a session token.
    // During login there is no token, so a 401 there is a normal failure.
    if (response.status === 401 && token) {
      setToken(null)
      if (unauthorizedHandler) unauthorizedHandler()
    }
    const { message, code } = describeError(response.status, data)
    throw new ApiError(response.status, message, code)
  }

  return data as T
}
// Downloads a protected file (for example a listing photo) with the login token.
export async function apiBlob(path: string): Promise<Blob> {
  const token = accessToken
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.', 'network_error')
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      setToken(null)
      if (unauthorizedHandler) unauthorizedHandler()
    }
    throw new ApiError(response.status, `Request failed (${response.status})`, null)
  }
  return response.blob()
}