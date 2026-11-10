import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'
import type { DeactivateResponse, TeamListResponse, TeamUser } from '../lib/teamTypes'
import TeamForm from '../components/TeamForm'

const chip = 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap'

const ROLE_LABEL: Record<string, string> = { salesperson: 'Salesperson', admin: 'Admin', owner: 'Owner' }

function ActiveChip({ active }: { active: boolean }) {
  return active ? (
    <span className={`${chip} bg-green-100 text-green-800`}>
      <span aria-hidden="true">{'\u2713'}</span> Active
    </span>
  ) : (
    <span className={`${chip} bg-red-100 text-red-800`}>
      <span aria-hidden="true">{'\u2717'}</span> Deactivated
    </span>
  )
}

function MfaChip({ enrolled }: { enrolled: boolean }) {
  return enrolled ? (
    <span className="text-charcoal-950">Set up</span>
  ) : (
    <span className="text-charcoal-600">Not yet (first login)</span>
  )
}

export default function Team() {
  const { user: me } = useAuth()
  const [items, setItems] = useState<TeamUser[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    api<TeamListResponse>('/users')
      .then((r) => {
        if (cancelled) return
        setItems(r.items)
        setError(null)
        setLoaded(true)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load the team.')
      })
    return () => {
      cancelled = true
    }
  }, [tick])

  async function deactivate(u: TeamUser) {
    if (
      !window.confirm(
        `Deactivate ${u.name}? They are signed out immediately and cannot log in. Their leads are handed to the other salespeople. You can reactivate them later from this page.`,
      )
    )
      return
    setNotice(null)
    setError(null)
    try {
      const r = await api<DeactivateResponse>(`/users/${u.id}/deactivate`, { method: 'POST' })
      const moved = r.leads_reassigned ?? 0
      const someoneLeft = items.some((x) => x.id !== u.id && x.active && x.role === 'salesperson')
      let text = `${u.name} was deactivated.`
      if (moved > 0) {
        const leads = moved === 1 ? '1 lead' : `${moved} leads`
        const was = moved === 1 ? 'was' : 'were'
        text += someoneLeft
          ? ` ${leads} ${was} moved to the remaining salespeople.`
          : ` ${leads} ${was} left unassigned because no active salesperson remains.`
      }
      setNotice(text)
      setTick((t) => t + 1)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not deactivate this user.')
    }
  }

  async function reactivate(u: TeamUser) {
    setNotice(null)
    setError(null)
    try {
      await api<TeamUser>(`/users/${u.id}/reactivate`, { method: 'POST' })
      setNotice(
        `${u.name} was reactivated and can log in again with their old password and authenticator. Leads that were moved away stay where they are. Assign leads to ${u.name} from the lead profile if needed.`,
      )
      setTick((t) => t + 1)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reactivate this user.')
    }
  }

  function action(u: TeamUser) {
    if (u.id === me?.id) return <span className="text-xs text-charcoal-600">This is you</span>
    if (u.role === 'owner' && me?.role !== 'owner') return null
    if (!u.active) {
      return (
        <button
          type="button"
          onClick={() => void reactivate(u)}
          className="h-9 rounded-md border border-charcoal-200 px-3 text-sm font-medium text-charcoal-950 hover:bg-charcoal-50"
        >
          Reactivate
        </button>
      )
    }
    return (
      <button
        type="button"
        onClick={() => void deactivate(u)}
        className="h-9 rounded-md border border-danger px-3 text-sm font-medium text-red-800 hover:bg-red-50"
      >
        Deactivate
      </button>
    )
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-charcoal-950">Team</h1>
        <button
          type="button"
          onClick={() => {
            setNotice(null)
            setAdding(true)
          }}
          className="h-10 rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600"
        >
          Add team member
        </button>
      </div>

      {notice && (
        <p role="status" className="mt-3 rounded-md border border-success bg-white px-3 py-2 text-sm">
          <span aria-hidden="true" className="mr-1 text-success">
            {'\u2713'}
          </span>
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 rounded-md border border-danger bg-white px-3 py-2 text-sm">
          <span aria-hidden="true" className="mr-1 text-danger">
            {'\u2717'}
          </span>
          {error}
        </p>
      )}
      {!loaded && !error && <p className="mt-4 text-sm text-charcoal-600">Loading team...</p>}

      {items.length > 0 && (
        <>
          <div className="mt-4 hidden overflow-x-auto rounded-lg border border-charcoal-200 bg-white md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-charcoal-50 text-xs uppercase text-charcoal-600">
                <tr>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Email</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Authenticator</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((u) => (
                  <tr key={u.id} className="border-t border-charcoal-200">
                    <td className="px-3 py-2 font-medium text-charcoal-950">{u.name}</td>
                    <td className="px-3 py-2">{u.email}</td>
                    <td className="px-3 py-2">{ROLE_LABEL[u.role] ?? u.role}</td>
                    <td className="px-3 py-2">
                      <MfaChip enrolled={u.mfa_enrolled} />
                    </td>
                    <td className="px-3 py-2">
                      <ActiveChip active={u.active} />
                    </td>
                    <td className="px-3 py-2">{action(u)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="mt-4 space-y-3 md:hidden">
            {items.map((u) => (
              <li key={u.id} className="rounded-lg border border-charcoal-200 bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium text-charcoal-950">{u.name}</div>
                    <div className="break-all text-sm text-charcoal-600">{u.email}</div>
                  </div>
                  <ActiveChip active={u.active} />
                </div>
                <div className="mt-2 text-sm text-charcoal-600">
                  {ROLE_LABEL[u.role] ?? u.role} {'\u00B7'} Authenticator: <MfaChip enrolled={u.mfa_enrolled} />
                </div>
                <div className="mt-3">{action(u)}</div>
              </li>
            ))}
          </ul>
        </>
      )}

      {adding && (
        <TeamForm
          onClose={() => setAdding(false)}
          onSaved={(name) => {
            setAdding(false)
            setNotice(`${name} was added. Share their password privately.`)
            setTick((t) => t + 1)
          }}
        />
      )}
    </div>
  )
}