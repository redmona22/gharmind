import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'

type Role = 'salesperson' | 'admin' | 'owner'

const inputClass =
  'mt-1 h-11 w-full rounded-md border border-charcoal-200 bg-white px-3 text-charcoal-950 md:h-10'
const labelClass = 'block text-sm font-medium text-charcoal-950'

export default function TeamForm({ onClose, onSaved }: { onClose: () => void; onSaved: (name: string) => void }) {
  const { user } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('salesperson')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password.length < 10 || password.length > 72) {
      setError('The password must be 10 to 72 characters long.')
      return
    }
    setBusy(true)
    try {
      await api('/users', {
        body: { name: name.trim(), email: email.trim(), role, password },
      })
      onSaved(name.trim())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the user. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 md:items-center md:p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="team-form-title"
        className="max-h-[92dvh] w-full max-w-md overflow-y-auto rounded-t-lg bg-white p-5 md:rounded-lg"
      >
        <h2 id="team-form-title" className="text-xl font-semibold text-charcoal-950">
          Add team member
        </h2>

        {error && (
          <p role="alert" className="mt-3 rounded-md border border-danger px-3 py-2 text-sm">
            <span aria-hidden="true" className="mr-1 text-danger">
              ✗
            </span>
            {error}
          </p>
        )}

        <form onSubmit={(e) => void submit(e)} className="mt-4 space-y-4">
          <div>
            <label htmlFor="tf-name" className={labelClass}>
              Name
            </label>
            <input
              id="tf-name"
              className={inputClass}
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              required
            />
          </div>
          <div>
            <label htmlFor="tf-email" className={labelClass}>
              Email
            </label>
            <input
              id="tf-email"
              type="email"
              className={inputClass}
              maxLength={255}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="tf-role" className={labelClass}>
              Role
            </label>
            <select id="tf-role" className={inputClass} value={role} onChange={(e) => setRole(e.target.value as Role)}>
              <option value="salesperson">Salesperson (sees only their own leads)</option>
              <option value="admin">Admin</option>
              {user?.role === 'owner' && <option value="owner">Owner</option>}
            </select>
          </div>
          <div>
            <label htmlFor="tf-password" className={labelClass}>
              Temporary password
            </label>
            <input
              id="tf-password"
              type="password"
              autoComplete="new-password"
              className={inputClass}
              maxLength={72}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <p className="mt-1 text-xs text-charcoal-600">
              10 to 72 characters. Share it privately. They set up their authenticator app on first login.
            </p>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={busy}
              className="h-11 flex-1 rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50 md:h-10"
            >
              {busy ? 'Creating...' : 'Create user'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="h-11 rounded-md border border-charcoal-600 px-4 font-medium text-charcoal-950 hover:bg-charcoal-50 md:h-10"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}