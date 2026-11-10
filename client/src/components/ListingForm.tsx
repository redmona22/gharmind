import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from '../lib/api'
import type { Listing, ListingInput, ListingStatus, ListingType } from '../lib/listingTypes'

type Props = {
  listing: Listing | null
  onClose: () => void
  onSaved: () => void
}

const inputClass =
  'mt-1 h-11 w-full rounded-md border border-charcoal-200 bg-white px-3 text-charcoal-950 md:h-10'
const labelClass = 'block text-sm font-medium text-charcoal-950'

function toInt(raw: string, label: string, min: number, max: number): number | null {
  const t = raw.trim().replace(/,/g, '')
  if (t === '') return null
  if (!/^\d+$/.test(t)) throw new Error(`${label} must be a whole number.`)
  const n = Number(t)
  if (n < min || n > max) throw new Error(`${label} must be between ${min.toLocaleString('en-IN')} and ${max.toLocaleString('en-IN')}.`)
  return n
}

function orNull(raw: string): string | null {
  const t = raw.trim()
  return t === '' ? null : t
}

export default function ListingForm({ listing, onClose, onSaved }: Props) {
  const [type, setType] = useState<ListingType>(listing?.listing_type ?? 'sale')
  const [project, setProject] = useState(listing?.project ?? '')
  const [location, setLocation] = useState(listing?.location ?? '')
  const [price, setPrice] = useState(listing?.price?.toString() ?? '')
  const [deposit, setDeposit] = useState(listing?.deposit?.toString() ?? '')
  const [bhk, setBhk] = useState(listing?.bhk?.toString() ?? '')
  const [area, setArea] = useState(listing?.area_sqft?.toString() ?? '')
  const [furnishing, setFurnishing] = useState(listing?.furnishing ?? '')
  const [status, setStatus] = useState<ListingStatus>(listing?.status ?? 'available')
  const [rera, setRera] = useState(listing?.rera_number ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const missingRera = type === 'sale' && rera.trim() === ''

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    let payload: ListingInput
    try {
      if (project.trim() === '') throw new Error('Project name is required.')
      payload = {
        listing_type: type,
        project: project.trim(),
        price: toInt(price, type === 'rent' ? 'Monthly rent' : 'Price', 0, 10_000_000_000),
        deposit: toInt(deposit, 'Deposit', 0, 10_000_000_000),
        bhk: toInt(bhk, 'BHK', 1, 10),
        area_sqft: toInt(area, 'Area', 1, 1_000_000),
        location: orNull(location),
        furnishing: orNull(furnishing),
        status,
        rera_number: orNull(rera),
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Please check the form.')
      return
    }

    setBusy(true)
    try {
      if (listing) {
        await api(`/listings/${listing.id}`, { method: 'PUT', body: payload })
      } else {
        await api('/listings', { method: 'POST', body: payload })
      }
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the listing. Please try again.')
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
        aria-labelledby="listing-form-title"
        className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-lg bg-white p-5 md:rounded-lg"
      >
        <h2 id="listing-form-title" className="text-xl font-semibold text-charcoal-950">
          {listing ? 'Edit listing' : 'Add listing'}
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
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="lf-type" className={labelClass}>
                Type
              </label>
              <select
                id="lf-type"
                className={inputClass}
                value={type}
                onChange={(e) => setType(e.target.value as ListingType)}
              >
                <option value="sale">Sale</option>
                <option value="rent">Rent</option>
              </select>
            </div>
            <div>
              <label htmlFor="lf-status" className={labelClass}>
                Status
              </label>
              <select
                id="lf-status"
                className={inputClass}
                value={status}
                onChange={(e) => setStatus(e.target.value as ListingStatus)}
              >
                <option value="available">Available</option>
                <option value="held">Held</option>
                <option value="sold">Sold</option>
                <option value="rented">Rented</option>
                <option value="withdrawn">Withdrawn</option>
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="lf-project" className={labelClass}>
              Project name
            </label>
            <input
              id="lf-project"
              className={inputClass}
              maxLength={200}
              value={project}
              onChange={(e) => setProject(e.target.value)}
              autoFocus
              required
            />
          </div>

          <div>
            <label htmlFor="lf-location" className={labelClass}>
              Location
            </label>
            <input
              id="lf-location"
              className={inputClass}
              maxLength={200}
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="lf-price" className={labelClass}>
                {type === 'rent' ? 'Monthly rent (₹)' : 'Price (₹)'}
              </label>
              <input
                id="lf-price"
                className={inputClass}
                inputMode="numeric"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="lf-deposit" className={labelClass}>
                Deposit (₹)
              </label>
              <input
                id="lf-deposit"
                className={inputClass}
                inputMode="numeric"
                value={deposit}
                onChange={(e) => setDeposit(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="lf-bhk" className={labelClass}>
                BHK
              </label>
              <input
                id="lf-bhk"
                className={inputClass}
                inputMode="numeric"
                value={bhk}
                onChange={(e) => setBhk(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="lf-area" className={labelClass}>
                Area (sq ft)
              </label>
              <input
                id="lf-area"
                className={inputClass}
                inputMode="numeric"
                value={area}
                onChange={(e) => setArea(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label htmlFor="lf-furnishing" className={labelClass}>
              Furnishing
            </label>
            <input
              id="lf-furnishing"
              className={inputClass}
              maxLength={30}
              list="lf-furnishing-options"
              value={furnishing}
              onChange={(e) => setFurnishing(e.target.value)}
            />
            <datalist id="lf-furnishing-options">
              <option value="unfurnished" />
              <option value="semi-furnished" />
              <option value="furnished" />
            </datalist>
          </div>

          <div>
            <label htmlFor="lf-rera" className={labelClass}>
              RERA number {type === 'rent' && <span className="font-normal text-charcoal-600">(not needed for rentals)</span>}
            </label>
            <input
              id="lf-rera"
              className={inputClass}
              maxLength={100}
              value={rera}
              onChange={(e) => setRera(e.target.value)}
            />
            {missingRera && (
              <p className="mt-1 text-sm text-red-800">
                <span aria-hidden="true">✗ </span>
                Without a RERA number this sale listing will not be shown to customers.
              </p>
            )}
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={busy}
              className="h-11 flex-1 rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50 md:h-10"
            >
              {busy ? 'Saving...' : listing ? 'Save changes' : 'Add listing'}
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