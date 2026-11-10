import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'
import type { LeadDetailData } from '../lib/types'
import type { TeamListResponse, TeamUser } from '../lib/teamTypes'
import { formatRupees, humanize, languageName } from '../lib/format'
import { OptedOutChip, ScoreBadge } from './Badges'
import KeyValues from './KeyValues'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5 text-sm">
      <dt className="text-charcoal-600">{label}</dt>
      <dd className="min-w-0 break-words text-right text-charcoal-950">{children}</dd>
    </div>
  )
}

// Shows budgets as rupees (60,00,000) instead of the raw number (6000000).
function prettyQualification<T>(q: T): T {
  if (!q || typeof q !== 'object' || Array.isArray(q)) return q
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(q as Record<string, unknown>)) {
    const n = typeof value === 'number' ? value : typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : NaN
    out[key] = key.toLowerCase().includes('budget') && Number.isFinite(n) ? formatRupees(n) : value
  }
  return out as T
}

export default function ProfilePanel({
  detail,
  currentUserId,
}: {
  detail: LeadDetailData
  currentUserId: string | undefined
}) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin' || user?.role === 'owner'
  const optedOut = detail.consent_status === 'opted_out'
  const assigneeName = (detail as LeadDetailData & { assigned_user_name?: string | null }).assigned_user_name

  const [assignedId, setAssignedId] = useState(detail.assigned_user_id ?? '')
  const [team, setTeam] = useState<TeamUser[]>([])
  const [saving, setSaving] = useState(false)
  const [assignError, setAssignError] = useState<string | null>(null)

  useEffect(() => {
    setAssignedId(detail.assigned_user_id ?? '')
  }, [detail.assigned_user_id])

  useEffect(() => {
    if (!isAdmin) return
    let cancelled = false
    api<TeamListResponse>('/users')
      .then((r) => {
        if (!cancelled) setTeam(r.items.filter((u) => u.active))
      })
      .catch(() => {
        if (!cancelled) setAssignError('Could not load the team list.')
      })
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  async function assign(value: string) {
    setSaving(true)
    setAssignError(null)
    try {
      await api(`/leads/${detail.id}/assign`, { method: 'PATCH', body: { user_id: value === '' ? null : value } })
      setAssignedId(value)
    } catch (err) {
      setAssignError(err instanceof ApiError ? err.message : 'Could not change the assignment.')
    } finally {
      setSaving(false)
    }
  }

  const assignedText = detail.assigned_user_id
    ? detail.assigned_user_id === currentUserId
      ? 'You'
      : assigneeName || 'A team member'
    : 'Unassigned'

  const knownAssignee = assignedId === '' || team.some((u) => u.id === assignedId)

  return (
    <div className="space-y-5 p-4">
      <section>
        <h2 className="text-base font-semibold text-charcoal-950">{detail.name || 'Unnamed lead'}</h2>
        <dl className="mt-2 divide-y divide-charcoal-200">
          <Row label="Phone">{detail.phone}</Row>
          <Row label="Language">{languageName(detail.language) || '\u2014'}</Row>
          <Row label="Source">{detail.source ? humanize(detail.source) : '\u2014'}</Row>
          <Row label="Score">
            <ScoreBadge score={detail.lead_score} />
          </Row>
          <Row label="Consent">
            {optedOut ? <OptedOutChip /> : detail.consent_status ? humanize(detail.consent_status) : '\u2014'}
          </Row>
          {!isAdmin && <Row label="Assigned to">{assignedText}</Row>}
        </dl>
      </section>

      {isAdmin && (
        <section>
          <label htmlFor="assign-select" className="mb-1 block text-sm font-semibold text-charcoal-950">
            Assigned to
          </label>
          <select
            id="assign-select"
            value={assignedId}
            disabled={saving}
            onChange={(e) => void assign(e.target.value)}
            className="h-10 w-full rounded-md border border-charcoal-200 bg-white px-2 text-sm disabled:opacity-50"
          >
            <option value="">Unassigned</option>
            {!knownAssignee && (
              <option value={assignedId}>{assigneeName ? `${assigneeName} (deactivated)` : 'Former team member'}</option>
            )}
            {team.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({humanize(u.role)})
                {u.id === currentUserId ? ' - you' : ''}
              </option>
            ))}
          </select>
          {assignError && (
            <p role="alert" className="mt-2 rounded-md border border-danger px-3 py-2 text-sm">
              <span aria-hidden="true" className="mr-1 text-danger">
                {'\u2717'}
              </span>
              {assignError}
            </p>
          )}
        </section>
      )}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-charcoal-950">Qualification</h3>
        <KeyValues data={prettyQualification(detail.qualification)} />
      </section>
    </div>
  )
}