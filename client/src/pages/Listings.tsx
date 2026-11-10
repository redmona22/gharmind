import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { useAuth } from '../auth/useAuth'
import { formatRupees } from '../lib/money'
import { humanize } from '../lib/format'
import type { Listing, ListingListResponse } from '../lib/listingTypes'
import ListingForm from '../components/ListingForm'
import ListingImport from '../components/ListingImport'

const chip = 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap'
const selectClass = 'h-10 rounded-md border border-charcoal-200 bg-white px-2 text-sm'

function StatusChip({ status }: { status: string }) {
  const style =
    status === 'available'
      ? 'bg-green-100 text-green-800'
      : status === 'held'
        ? 'bg-amber-100 text-amber-800'
        : status === 'sold' || status === 'rented'
          ? 'bg-blue-100 text-blue-800'
          : 'bg-charcoal-200 text-charcoal-800'
  return <span className={`${chip} ${style}`}>{humanize(status)}</span>
}

function NotPromotable() {
  return (
    <span className={`${chip} bg-red-100 text-red-800`}>
      <span aria-hidden="true">✗</span> Not promotable
    </span>
  )
}

function priceText(l: Listing): string {
  if (l.price === null) return '—'
  return formatRupees(l.price) + (l.listing_type === 'rent' ? ' /mo' : '')
}

export default function Listings() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin' || user?.role === 'owner'

  const [type, setType] = useState('')
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [items, setItems] = useState<Listing[]>([])
  const [total, setTotal] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const [editing, setEditing] = useState<Listing | 'new' | null>(null)
  const [importing, setImporting] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q.trim()), 300)
    return () => clearTimeout(timer)
  }, [q])

  useEffect(() => {
    let cancelled = false
    const query = new URLSearchParams({ limit: '100' })
    if (type) query.set('type', type)
    if (status) query.set('status', status)
    if (debouncedQ) query.set('q', debouncedQ)
    api<ListingListResponse>(`/listings?${query.toString()}`)
      .then((r) => {
        if (cancelled) return
        setItems(r.items)
        setTotal(r.total)
        setError(null)
        setLoaded(true)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load listings.')
      })
    return () => {
      cancelled = true
    }
  }, [type, status, debouncedQ, tick])

  async function withdraw(l: Listing) {
    if (!window.confirm(`Withdraw "${l.project}"? It is kept for the record but never shown to customers.`)) return
    setNotice(null)
    try {
      await api(`/listings/${l.id}`, { method: 'DELETE' })
      setNotice(`"${l.project}" was withdrawn.`)
      setTick((t) => t + 1)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not withdraw the listing.')
    }
  }

  function actions(l: Listing) {
    if (!isAdmin) return null
    return (
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => {
            setNotice(null)
            setEditing(l)
          }}
          className="h-9 rounded-md border border-charcoal-200 px-3 text-sm font-medium hover:bg-charcoal-50"
        >
          Edit
        </button>
        {l.status !== 'withdrawn' && (
          <button
            type="button"
            onClick={() => void withdraw(l)}
            className="h-9 rounded-md border border-danger px-3 text-sm font-medium text-red-800 hover:bg-red-50"
          >
            Withdraw
          </button>
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-charcoal-950">Listings</h1>
          {!isAdmin && <p className="text-sm text-charcoal-600">Read-only. Admins manage listings.</p>}
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setNotice(null)
                setImporting(true)
              }}
              className="h-10 rounded-md border border-charcoal-600 px-4 font-medium text-charcoal-950 hover:bg-charcoal-50"
            >
              Import Excel
            </button>
            <button
              type="button"
              onClick={() => {
                setNotice(null)
                setEditing('new')
              }}
              className="h-10 rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600"
            >
              Add listing
            </button>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <label htmlFor="listing-search" className="sr-only">
          Search by project or location
        </label>
        <input
          id="listing-search"
          type="search"
          maxLength={100}
          placeholder="Search project or location"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="h-10 min-w-0 flex-1 rounded-md border border-charcoal-200 bg-white px-3 text-sm md:max-w-xs"
        />
        <label htmlFor="listing-type" className="sr-only">
          Type
        </label>
        <select id="listing-type" className={selectClass} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">Sale and rent</option>
          <option value="sale">Sale</option>
          <option value="rent">Rent</option>
        </select>
        <label htmlFor="listing-status" className="sr-only">
          Status
        </label>
        <select id="listing-status" className={selectClass} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="available">Available</option>
          <option value="held">Held</option>
          <option value="sold">Sold</option>
          <option value="rented">Rented</option>
          <option value="withdrawn">Withdrawn</option>
        </select>
      </div>

      {notice && (
        <p role="status" className="mt-3 rounded-md border border-success bg-white px-3 py-2 text-sm">
          <span aria-hidden="true" className="mr-1 text-success">
            ✓
          </span>
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 rounded-md border border-danger bg-white px-3 py-2 text-sm">
          <span aria-hidden="true" className="mr-1 text-danger">
            ✗
          </span>
          {error}
        </p>
      )}

      {!loaded && !error && <p className="mt-4 text-sm text-charcoal-600">Loading listings...</p>}
      {loaded && items.length === 0 && (
        <p className="mt-4 text-sm text-charcoal-600">
          No listings match these filters.{isAdmin ? ' Use Add listing or Import Excel to create the first ones.' : ''}
        </p>
      )}

      {items.length > 0 && (
        <>
          <div className="mt-4 hidden overflow-x-auto rounded-lg border border-charcoal-200 bg-white md:block">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="bg-charcoal-50 text-xs uppercase text-charcoal-600">
                <tr>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Project</th>
                  <th className="px-3 py-2 text-right font-medium">Price / rent</th>
                  <th className="px-3 py-2 text-right font-medium">Deposit</th>
                  <th className="px-3 py-2 font-medium">BHK</th>
                  <th className="px-3 py-2 font-medium">Area</th>
                  <th className="px-3 py-2 font-medium">Furnishing</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">RERA</th>
                  {isAdmin && <th className="px-3 py-2 font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {items.map((l) => (
                  <tr key={l.id} className="border-t border-charcoal-200 align-top">
                    <td className="px-3 py-2">{humanize(l.listing_type)}</td>
                    <td className="px-3 py-2">
                      <div className="font-medium text-charcoal-950">{l.project}</div>
                      {l.location && <div className="text-xs text-charcoal-600">{l.location}</div>}
                    </td>
                    <td className="px-3 py-2 text-right">{priceText(l)}</td>
                    <td className="px-3 py-2 text-right">{formatRupees(l.deposit)}</td>
                    <td className="px-3 py-2">{l.bhk ?? '—'}</td>
                    <td className="px-3 py-2">{l.area_sqft ? `${l.area_sqft.toLocaleString('en-IN')} sq ft` : '—'}</td>
                    <td className="px-3 py-2">{l.furnishing ? humanize(l.furnishing) : '—'}</td>
                    <td className="px-3 py-2">
                      <StatusChip status={l.status} />
                    </td>
                    <td className="px-3 py-2">
                      {l.listing_type === 'rent' ? (
                        <span className="text-charcoal-600">Not needed</span>
                      ) : l.promotable ? (
                        <span className="break-all">{l.rera_number}</span>
                      ) : (
                        <NotPromotable />
                      )}
                    </td>
                    {isAdmin && <td className="px-3 py-2">{actions(l)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="mt-4 space-y-3 md:hidden">
            {items.map((l) => (
              <li key={l.id} className="rounded-lg border border-charcoal-200 bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium text-charcoal-950">{l.project}</div>
                    {l.location && <div className="text-xs text-charcoal-600">{l.location}</div>}
                  </div>
                  <StatusChip status={l.status} />
                </div>
                <div className="mt-2 text-lg font-semibold text-charcoal-950">{priceText(l)}</div>
                <div className="mt-1 text-sm text-charcoal-600">
                  {humanize(l.listing_type)}
                  {l.bhk ? ` · ${l.bhk} BHK` : ''}
                  {l.area_sqft ? ` · ${l.area_sqft.toLocaleString('en-IN')} sq ft` : ''}
                  {l.furnishing ? ` · ${humanize(l.furnishing)}` : ''}
                </div>
                {l.deposit !== null && (
                  <div className="text-sm text-charcoal-600">Deposit {formatRupees(l.deposit)}</div>
                )}
                {l.listing_type === 'sale' && (
                  <div className="mt-2 text-sm">
                    {l.promotable ? (
                      <span className="text-charcoal-600">RERA {l.rera_number}</span>
                    ) : (
                      <NotPromotable />
                    )}
                  </div>
                )}
                {isAdmin && <div className="mt-3">{actions(l)}</div>}
              </li>
            ))}
          </ul>

          {total > items.length && (
            <p className="mt-3 text-center text-xs text-charcoal-600">
              Showing {items.length} of {total}. Use search or filters to narrow down.
            </p>
          )}
        </>
      )}

      {editing && (
        <ListingForm
          listing={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setNotice(editing === 'new' ? 'Listing added.' : 'Listing saved.')
            setEditing(null)
            setTick((t) => t + 1)
          }}
        />
      )}

      {importing && (
        <ListingImport
          onClose={() => setImporting(false)}
          onImported={(count) => {
            setImporting(false)
            setNotice(`${count} listing(s) imported.`)
            setTick((t) => t + 1)
          }}
        />
      )}
    </div>
  )
}