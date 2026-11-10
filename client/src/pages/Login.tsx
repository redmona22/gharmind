import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'
import type { SessionResponse } from '../auth/AuthContext'

type Step = 'password' | 'code' | 'enroll'
type LoginResponse = { challenge_token: string; mfa_enrolled: boolean }
type EnrollResponse = { enroll_token: string; secret: string; otpauth_uri: string }

const inputClass =
  'mt-1 h-11 w-full rounded-md border border-charcoal-600 bg-charcoal-950 px-3 text-white placeholder:text-charcoal-400 md:h-10'
const labelClass = 'block text-sm font-medium text-charcoal-200'
const primaryButton =
  'h-11 w-full rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50 md:h-10'
const ghostButton =
  'h-11 w-full rounded-md px-4 font-medium text-charcoal-200 hover:bg-charcoal-800 md:h-10'

export default function Login() {
  const { user, startSession } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [step, setStep] = useState<Step>('password')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [challengeToken, setChallengeToken] = useState('')
  const [enroll, setEnroll] = useState<EnrollResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={from} replace />

  function backToPassword(message: string | null) {
    setStep('password')
    setPassword('')
    setCode('')
    setChallengeToken('')
    setEnroll(null)
    setError(message)
  }

  function fail(err: unknown) {
    if (err instanceof ApiError) {
      // An expired challenge or enrol token means the person has to start again.
      if (err.status === 401 && step !== 'password' && err.message !== 'invalid code') {
        backToPassword('Your sign-in timed out. Please log in again.')
        return
      }
      setError(err.message)
      return
    }
    setError('Something went wrong. Please try again.')
  }

  function finish(session: SessionResponse) {
    startSession(session)
    navigate(from, { replace: true })
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const res = await api<LoginResponse>('/auth/login', { body: { email, password } })
      setChallengeToken(res.challenge_token)
      setCode('')
      if (res.mfa_enrolled) {
        setStep('code')
      } else {
        const en = await api<EnrollResponse>('/auth/mfa/enroll', {
          body: { challenge_token: res.challenge_token },
        })
        setEnroll(en)
        setStep('enroll')
      }
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const session = await api<SessionResponse>('/auth/mfa/verify', {
        body: { challenge_token: challengeToken, code },
      })
      finish(session)
    } catch (err) {
      setCode('')
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  async function submitEnroll(e: FormEvent) {
    e.preventDefault()
    if (!enroll) return
    setError(null)
    setBusy(true)
    try {
      const session = await api<SessionResponse>('/auth/mfa/confirm', {
        body: { enroll_token: enroll.enroll_token, code },
      })
      finish(session)
    } catch (err) {
      setCode('')
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  const codeField = (
    <div>
      <label htmlFor="code" className={labelClass}>
        6-digit code
      </label>
      <input
        id="code"
        className={`${inputClass} text-center text-lg tracking-widest`}
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={8}
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
        autoFocus
        required
      />
    </div>
  )

  return (
    <div className="flex min-h-full items-center justify-center bg-charcoal-950 p-4">
      <div className="w-full max-w-sm rounded-lg border border-charcoal-600 bg-charcoal-900 p-6 text-white">
        <h1 className="text-2xl font-semibold">Gharmind</h1>
        <p className="mt-1 text-charcoal-200">
          {step === 'password' && 'Sign in to your dashboard'}
          {step === 'code' && 'Enter the code from your authenticator app'}
          {step === 'enroll' && 'Set up your authenticator app'}
        </p>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md border border-danger bg-charcoal-950 px-3 py-2 text-sm text-white"
          >
            <span aria-hidden="true" className="mr-1 text-danger">
              ✗
            </span>
            {error}
          </p>
        )}

        {step === 'password' && (
          <form onSubmit={submitPassword} className="mt-4 space-y-4">
            <div>
              <label htmlFor="email" className={labelClass}>
                Email
              </label>
              <input
                id="email"
                className={inputClass}
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div>
              <label htmlFor="password" className={labelClass}>
                Password
              </label>
              <input
                id="password"
                className={inputClass}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <button type="submit" className={primaryButton} disabled={busy}>
              {busy ? 'Signing in...' : 'Continue'}
            </button>
          </form>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="mt-4 space-y-4">
            {codeField}
            <button type="submit" className={primaryButton} disabled={busy || code.length < 6}>
              {busy ? 'Checking...' : 'Verify and sign in'}
            </button>
            <button type="button" className={ghostButton} onClick={() => backToPassword(null)}>
              Back
            </button>
          </form>
        )}

        {step === 'enroll' && enroll && (
          <form onSubmit={submitEnroll} className="mt-4 space-y-4">
            <p className="text-sm text-charcoal-200">
              Scan this QR code with Google Authenticator, Microsoft Authenticator or a similar app, then enter
              the 6-digit code it shows.
            </p>
            <div className="flex justify-center rounded-md bg-white p-3">
              <QRCodeSVG value={enroll.otpauth_uri} size={176} />
            </div>
            <p className="text-sm text-charcoal-200">
              Can't scan? Enter this key by hand:
              <br />
              <span className="break-all font-mono text-white">{enroll.secret}</span>
            </p>
            {codeField}
            <button type="submit" className={primaryButton} disabled={busy || code.length < 6}>
              {busy ? 'Checking...' : 'Confirm and sign in'}
            </button>
            <button type="button" className={ghostButton} onClick={() => backToPassword(null)}>
              Cancel
            </button>
          </form>
        )}
      </div>
    </div>
  )
}