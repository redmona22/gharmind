import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from '../lib/api'
import { AuthContext } from './AuthContext'
import type { AuthState, SessionResponse, User } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  // If a token survived a page reload, we are "loading" until /auth/me confirms it.
  const [loading, setLoading] = useState<boolean>(() => getToken() !== null)

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  useEffect(() => {
    if (getToken() === null) return
    let cancelled = false
    api<User>('/auth/me')
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        setToken(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const startSession = useCallback((session: SessionResponse) => {
    setToken(session.access_token)
    setUser(session.user)
    setLoading(false)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, loading, startSession, logout }),
    [user, loading, startSession, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}