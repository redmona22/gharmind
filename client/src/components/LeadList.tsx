import type { ChangeEvent } from 'react'
import type { LeadItem } from '../lib/types'
import { relTime } from '../lib/format'
import { OptedOutChip, ScoreBadge, StatusChip } from './Badges'

export type Filters = { q: string; status: string; scoreMin: string; assigned: string }

// The server now also sends the assignee's name.
type LeadRow = LeadItem & { assigned_user_name?: string | null }

const selectClass = 'h-10 min-w-0 flex-1 rounded-md border border-charcoal-200 bg-white px-2 text-sm'

type Props = {
  items: LeadItem[]
  total: number
  loaded: boolean
  error: string | null
  filters: Filters
  onFilters: (next: Filters) => void
  selectedId: string | undefined
  isAdmin: boolean
  onSelect: (id: string) => void
}

export default function LeadList({
  items,
  total,
  loaded,
  error,
  filters,
  onFilters,
  selectedId,
  isAdmin,
  onSelect,
}: Props) {
  function set(key: keyof Filters) {
    return (e: ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
      onFilters({ ...filters, [key]: e.target.value })
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 border-b border-charcoal-200 p-3">
        <label htmlFor="lead-search" className="sr-only">
          Search leads by name or phone
        </label>
        <input
          id="lead-search"
          type="search"
          maxLength={100}
          placeholder="Search name or phone"
          value={filters.q}
          onChange={set('q')}
          className="h-10 w-full rounded-md border border-charcoal-200 bg-white px-3 text-sm"
        />
        <div className="flex gap-2">
          <label className="sr-only" htmlFor="filter-status">
            Conversation status
          </label>
          <select id="filter-status" className={selectClass} value={filters.status} onChange={set('status')}>
            <option value="">All chats</option>
            <option value="agent">AI handling</option>
            <option value="human">Human handling</option>
            <option value="closed">Closed</option>
          </select>
          <label className="sr-only" htmlFor="filter-score">
            Minimum score
          </label>
          <select id="filter-score" className={selectClass} value={filters.scoreMin} onChange={set('scoreMin')}>
            <option value="">Any score</option>
            <option value="70">Hot (70+)</option>
            <option value="40">Warm and up (40+)</option>
          </select>
        </div>
        {isAdmin && (
          <>
            <label className="sr-only" htmlFor="filter-assigned">
              Assigned to
            </label>
            <select
              id="filter-assigned"
              className={`${selectClass} w-full`}
              value={filters.assigned}
              onChange={set('assigned')}
            >
              <option value="">All leads</option>
              <option value="me">Assigned to me</option>
              <option value="none">Unassigned</option>
            </select>
          </>
        )}
      </div>

      {error && (
        <p role="alert" className="m-3 rounded-md border border-danger px-3 py-2 text-sm">
          <span aria-hidden="true" className="mr-1 text-danger">
            {'\u2717'}
          </span>
          {error}
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!loaded && !error && <p className="p-4 text-sm text-charcoal-600">Loading leads...</p>}
        {loaded && items.length === 0 && !error && (
          <p className="p-4 text-sm text-charcoal-600">No leads match these filters.</p>
        )}
        <ul>
          {items.map((item) => {
            const lead = item as LeadRow
            const selected = lead.id === selectedId
            return (
              <li key={lead.id}>
                <button
                  type="button"
                  onClick={() => onSelect(lead.id)}
                  aria-current={selected ? 'true' : undefined}
                  className={`block w-full border-b border-charcoal-200 p-3 text-left hover:bg-charcoal-50 ${
                    selected ? 'bg-brand-100 hover:bg-brand-100' : 'bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate font-medium text-charcoal-950">
                      {lead.name || lead.phone}
                    </span>
                    <ScoreBadge score={lead.lead_score} />
                  </div>
                  {lead.name && <div className="truncate text-xs text-charcoal-600">{lead.phone}</div>}
                  <p className="mt-1 truncate text-sm text-charcoal-600">
                    {lead.last_message ? lead.last_message.content : 'No messages yet'}
                  </p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <StatusChip status={lead.conversation_status} />
                    {lead.consent_status === 'opted_out' && <OptedOutChip />}
                    {!lead.assigned_user_id ? (
                      <span className="text-xs text-charcoal-600">Unassigned</span>
                    ) : (
                      isAdmin &&
                      lead.assigned_user_name && (
                        <span className="max-w-[10rem] truncate text-xs text-charcoal-600">
                          Assigned to {lead.assigned_user_name}
                        </span>
                      )
                    )}
                    {lead.last_message && (
                      <span className="ml-auto text-xs text-charcoal-400">{relTime(lead.last_message.at)}</span>
                    )}
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
        {loaded && total > items.length && (
          <p className="p-3 text-center text-xs text-charcoal-600">
            Showing {items.length} of {total}. Use search or filters to narrow down.
          </p>
        )}
      </div>
    </div>
  )
}