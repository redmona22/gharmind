import { createContext } from 'react'

export type Role = 'salesperson' | 'admin' | 'owner'

export type User = {
  id: string
  email: string
  name: string
  role: Role
  tenant_name?: string
}

export type SessionResponse = {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export type AuthState = {
  user: User | null
  loading: boolean
  startSession: (session: SessionResponse) => void
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)