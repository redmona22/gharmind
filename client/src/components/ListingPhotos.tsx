import { useCallback, useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'
import { api, apiBlob, ApiError } from '../lib/api'
import type { ListingMedia, ListingMediaResponse } from '../lib/listingTypes'

const MAX_BYTES = 5 * 1024 * 1024
const MAX_FILES = 10
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

type ThumbProps = {
  listingId: string
  item: ListingMedia
  onDelete: (item: ListingMedia) => void
  disabled: boolean
}

function Thumb({ listingId, item, onDelete, disabled }: ThumbProps) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    let created: string | null = null
    apiBlob(`/listings/${listingId}/media/${item.id}/file`)
      .then((blob) => {
        if (cancelled) return
        created = URL.createObjectURL(blob)
        setUrl(created)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
      if (created) URL.revokeObjectURL(created)
    }
  }, [listingId, item.id])

  return (
    <li className="relative h-24 w-24 shrink-0 overflow-hidden rounded-md border border-charcoal-200 bg-charcoal-50">
      {url && <img src={url} alt={item.filename} className="h-full w-full object-cover" />}
      {!url && (
        <div className="flex h-full w-full items-center justify-center px-1 text-center text-xs text-charcoal-600">
          {failed ? 'Could not load' : 'Loading...'}
        </div>
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onDelete(item)}
        aria-label={`Remove photo ${item.filename}`}
        className="absolute right-1 top-1 h-6 w-6 rounded-full bg-black/70 text-sm font-medium leading-6 text-white hover:bg-black disabled:opacity-50"
      >
        x
      </button>
    </li>
  )
}

export default function ListingPhotos({ listingId }: { listingId: string }) {
  const [items, setItems] = useState<ListingMedia[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    api<ListingMediaResponse>(`/listings/${listingId}/media`)
      .then((r) => {
        if (cancelled) return
        setItems(r.items)
        setLoaded(true)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load photos.')
        setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [listingId, tick])

  const onPick = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? [])
      e.target.value = ''
      if (files.length === 0) return

      setError(null)
      setBusy(true)
      const problems: string[] = []
      let room = MAX_FILES - items.length

      for (const f of files) {
        if (room <= 0) {
          problems.push(`A listing can have at most ${MAX_FILES} photos.`)
          break
        }
        if (!ALLOWED_TYPES.includes(f.type)) {
          problems.push(`${f.name}: only JPEG, PNG and WebP photos are allowed.`)
          continue
        }
        if (f.size > MAX_BYTES) {
          problems.push(`${f.name}: larger than 5 MB.`)
          continue
        }
        try {
          const raw = await f.arrayBuffer()
          await api(`/listings/${listingId}/media?filename=${encodeURIComponent(f.name)}`, { raw })
          room -= 1
        } catch (err) {
          problems.push(`${f.name}: ${err instanceof ApiError ? err.message : 'upload failed.'}`)
        }
      }

      setBusy(false)
      setTick((t) => t + 1)
      if (problems.length > 0) setError(problems.join(' '))
    },
    [items.length, listingId],
  )

  async function remove(item: ListingMedia) {
    if (!window.confirm(`Remove photo "${item.filename}"?`)) return
    setError(null)
    setBusy(true)
    try {
      await api(`/listings/${listingId}/media/${item.id}`, { method: 'DELETE' })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not remove the photo.')
    } finally {
      setBusy(false)
      setTick((t) => t + 1)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <span className="block text-sm font-medium text-charcoal-950">
          Photos ({items.length}/{MAX_FILES})
        </span>
        <label
          className={
            'inline-flex h-9 cursor-pointer items-center rounded-md border border-charcoal-600 px-3 text-sm font-medium text-charcoal-950 hover:bg-charcoal-50 ' +
            (busy || items.length >= MAX_FILES ? 'pointer-events-none opacity-50' : '')
          }
        >
          {busy ? 'Working...' : 'Add photos'}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            className="sr-only"
            disabled={busy || items.length >= MAX_FILES}
            onChange={(e) => void onPick(e)}
          />
        </label>
      </div>

      {error && (
        <p role="alert" className="mt-2 rounded-md border border-danger px-3 py-2 text-sm">
          {error}
        </p>
      )}

      {loaded && items.length === 0 && (
        <p className="mt-2 text-sm text-charcoal-600">No photos yet. JPEG, PNG or WebP, up to 5 MB each.</p>
      )}

      {items.length > 0 && (
        <ul className="mt-2 flex gap-2 overflow-x-auto pb-1">
          {items.map((m) => (
            <Thumb key={m.id} listingId={listingId} item={m} onDelete={(x) => void remove(x)} disabled={busy} />
          ))}
        </ul>
      )}
    </div>
  )
}