import { humanize, toText } from '../lib/format'

export default function KeyValues({ data }: { data: unknown }) {
  if (data === null || data === undefined || data === '') {
    return <p className="text-sm text-charcoal-400">Nothing captured yet.</p>
  }
  if (typeof data !== 'object' || Array.isArray(data)) {
    return <p className="whitespace-pre-wrap break-words text-sm text-charcoal-950">{toText(data)}</p>
  }
  const entries = Object.entries(data as Record<string, unknown>).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  )
  if (entries.length === 0) return <p className="text-sm text-charcoal-400">Nothing captured yet.</p>
  return (
    <dl className="space-y-2 text-sm">
      {entries.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs font-medium text-charcoal-600">{humanize(k)}</dt>
          <dd className="whitespace-pre-wrap break-words text-charcoal-950">{toText(v)}</dd>
        </div>
      ))}
    </dl>
  )
}