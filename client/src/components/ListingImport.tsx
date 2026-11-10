import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { formatRupees } from '../lib/money'
import { humanize } from '../lib/format'

type PreviewRow = {
  listing_type: string
  project: string
  price: number | null
  bhk: number | null
  location: string | null
  status: string
  rera_number: string | null
}

type ImportPreview = {
  rows_total: number
  valid_count: number
  error_count: number
  errors: { row: number; messages: string[] }[]
  preview: PreviewRow[]
  missing_columns: string[]
  unrecognised_columns: string[]
  not_promotable_count: number
}

type Props = {
  onClose: () => void
  onImported: (count: number) => void
}

export default function ListingImport({ onClose, onImported }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function check(f: File) {
    setFile(f)
    setPreview(null)
    setError(null)
    if (!f.name.toLowerCase().endsWith('.xlsx')) {
      setError('Please choose an Excel .xlsx file. Save .xls or .csv files as .xlsx first.')
      return
    }
    setBusy(true)
    try {
      const raw = await f.arrayBuffer()
      setPreview(await api<ImportPreview>('/listings/import?commit=false', { raw }))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not check the file.')
    } finally {
      setBusy(false)
    }
  }

  async function commit() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const raw = await file.arrayBuffer()
      const r = await api<{ imported: number }>('/listings/import?commit=true', { raw })
      onImported(r.imported)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not import the file.')
      setBusy(false)
    }
  }

  const canImport =
    preview !== null && preview.error_count === 0 && preview.missing_columns.length === 0 && preview.valid_count > 0

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
        aria-labelledby="import-title"
        className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-t-lg bg-white p-5 md:rounded-lg"
      >
        <h2 id="import-title" className="text-xl font-semibold text-charcoal-950">
          Import listings from Excel
        </h2>
        <p className="mt-1 text-sm text-charcoal-600">
          Use an .xlsx file with a header row. Required columns: <strong>Type</strong> (sale or rent) and{' '}
          <strong>Project</strong>. Optional: Price or Rent, Deposit, BHK, Area, Location, Furnishing, Status, RERA
          number. Write prices in full rupees, like 6500000. Nothing is saved until you press Import.
        </p>

        <div className="mt-4">
          <input
            ref={input}
            type="file"
            accept=".xlsx"
            aria-label="Choose an Excel file"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void check(f)
            }}
            className="block w-full text-sm file:mr-3 file:h-10 file:rounded-md file:border file:border-charcoal-200 file:bg-white file:px-3 file:font-medium"
          />
        </div>

        {busy && <p className="mt-3 text-sm text-charcoal-600">Working...</p>}

        {error && (
          <p role="alert" className="mt-3 rounded-md border border-danger px-3 py-2 text-sm">
            <span aria-hidden="true" className="mr-1 text-danger">
              ✗
            </span>
            {error}
          </p>
        )}

        {preview && preview.missing_columns.length > 0 && (
          <p role="alert" className="mt-3 rounded-md border border-danger px-3 py-2 text-sm">
            <span aria-hidden="true" className="mr-1 text-danger">
              ✗
            </span>
            The first row must contain these columns: {preview.missing_columns.join(', ')}.
          </p>
        )}

        {preview && preview.missing_columns.length === 0 && (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-charcoal-950">
              {preview.rows_total} row(s) read: <strong>{preview.valid_count} ready</strong>
              {preview.error_count > 0 && (
                <>
                  , <strong className="text-red-800">✗ {preview.error_count} with errors</strong>
                </>
              )}
              .
            </p>

            {preview.not_promotable_count > 0 && (
              <p className="rounded-md border border-warning px-3 py-2 text-sm">
                <span aria-hidden="true" className="mr-1 text-warning">
                  !
                </span>
                {preview.not_promotable_count} sale listing(s) have no RERA number. They will import, but they are
                marked Not promotable and the agent will not show them.
              </p>
            )}

            {preview.unrecognised_columns.length > 0 && (
              <p className="text-sm text-charcoal-600">
                Ignored columns (name not recognised): {preview.unrecognised_columns.join(', ')}.
              </p>
            )}

            {preview.errors.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-charcoal-950">Fix these rows in Excel, then choose the file again</h3>
                <ul className="mt-1 max-h-48 space-y-1 overflow-y-auto rounded-md border border-charcoal-200 p-2 text-sm">
                  {preview.errors.map((e) => (
                    <li key={e.row}>
                      <span className="font-medium">Row {e.row}:</span> {e.messages.join(' ')}
                    </li>
                  ))}
                </ul>
                {preview.error_count > preview.errors.length && (
                  <p className="mt-1 text-xs text-charcoal-600">
                    Showing the first {preview.errors.length} of {preview.error_count} rows with errors.
                  </p>
                )}
              </div>
            )}

            {preview.preview.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-charcoal-950">Preview (first {preview.preview.length} ready rows)</h3>
                <div className="mt-1 overflow-x-auto rounded-md border border-charcoal-200">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead className="bg-charcoal-50 text-xs uppercase text-charcoal-600">
                      <tr>
                        <th className="px-2 py-1 font-medium">Type</th>
                        <th className="px-2 py-1 font-medium">Project</th>
                        <th className="px-2 py-1 text-right font-medium">Price / rent</th>
                        <th className="px-2 py-1 font-medium">BHK</th>
                        <th className="px-2 py-1 font-medium">Status</th>
                        <th className="px-2 py-1 font-medium">RERA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.preview.map((r, i) => (
                        <tr key={i} className="border-t border-charcoal-200">
                          <td className="px-2 py-1">{humanize(r.listing_type)}</td>
                          <td className="px-2 py-1">{r.project}</td>
                          <td className="px-2 py-1 text-right">{formatRupees(r.price)}</td>
                          <td className="px-2 py-1">{r.bhk ?? '—'}</td>
                          <td className="px-2 py-1">{humanize(r.status)}</td>
                          <td className="px-2 py-1">{r.rera_number || (r.listing_type === 'rent' ? 'Not needed' : '✗ Missing')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            disabled={!canImport || busy}
            onClick={() => void commit()}
            className="h-11 flex-1 rounded-md bg-brand-500 px-4 font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50 md:h-10"
          >
            {preview && canImport ? `Import ${preview.valid_count} listing(s)` : 'Import'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="h-11 rounded-md border border-charcoal-600 px-4 font-medium text-charcoal-950 hover:bg-charcoal-50 md:h-10"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}