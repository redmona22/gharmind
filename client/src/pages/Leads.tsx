import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'
import type { LeadItem, LeadListResponse } from '../lib/types'
import LeadList from '../components/LeadList'
import type { Filters } from '../components/LeadList'
import LeadDetail from '../components/LeadDetail'

export default function Leads() {
  const params = useParams()
  const contactId = params.contactId
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin' || user?.role === 'owner'

  const [filters, setFilters] = useState<Filters>({ q: '', status: '', scoreMin: '', assigned: '' })
  const [debouncedQ, setDebouncedQ] = useState('')
  const [items, setItems] = useState<LeadItem[]>([])
  const [total, setTotal] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(filters.q.trim()), 300)
    return () => clearTimeout(timer)
  }, [filters.q])

  useEffect(() => {
    let cancelled = false
    const query = new URLSearchParams({ limit: '100' })
    if (debouncedQ) query.set('q', debouncedQ)
    if (filters.status) query.set('status', filters.status)
    if (filters.scoreMin) query.set('score_min', filters.scoreMin)
    if (isAdmin && filters.assigned) query.set('assigned_to', filters.assigned)

    const run = () => {
      api<LeadListResponse>(`/leads?${query.toString()}`)
        .then((r) => {
          if (cancelled) return
          setItems(r.items)
          setTotal(r.total)
          setError(null)
          setLoaded(true)
        })
        .catch((err) => {
          if (cancelled) return
          setError(err instanceof ApiError ? err.message : 'Could not load leads.')
        })
    }
    run()
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') run()
    }, 15000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [debouncedQ, filters.status, filters.scoreMin, filters.assigned, isAdmin, tick])

  return (
    <div className="flex h-[calc(100dvh-9rem)] overflow-hidden rounded-lg border border-charcoal-200 bg-white md:h-[calc(100dvh-6.5rem)]">
      <section
        aria-label="Leads"
        className={`${contactId ? 'hidden md:flex' : 'flex'} w-full flex-col border-r border-charcoal-200 md:w-80 md:shrink-0`}
      >
        <LeadList
          items={items}
          total={total}
          loaded={loaded}
          error={error}
          filters={filters}
          onFilters={setFilters}
          selectedId={contactId}
          isAdmin={isAdmin}
          onSelect={(id) => navigate(`/leads/${id}`)}
        />
      </section>
      <section aria-label="Conversation" className={`${contactId ? 'flex' : 'hidden md:flex'} min-w-0 flex-1`}>
        {contactId ? (
          <LeadDetail
            key={contactId}
            contactId={contactId}
            onBack={() => navigate('/leads')}
            onChanged={() => setTick((t) => t + 1)}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6 text-charcoal-600">
            Select a lead to read the chat.
          </div>
        )}
      </section>
    </div>
  )
}