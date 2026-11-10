import { scoreBand } from '../lib/format'

const chip = 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap'

export function ScoreBadge({ score }: { score: number }) {
  const band = scoreBand(score)
  const style =
    band === 'hot'
      ? 'bg-green-100 text-green-800'
      : band === 'warm'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-charcoal-200 text-charcoal-800'
  const label = band === 'hot' ? 'Hot' : band === 'warm' ? 'Warm' : 'Cold'
  return (
    <span className={`${chip} ${style}`}>
      {label} <span className="font-semibold">{score}</span>
    </span>
  )
}

export function StatusChip({ status }: { status: string | null }) {
  if (!status) return null
  if (status === 'human') return <span className={`${chip} bg-charcoal-800 text-white`}>Human handling</span>
  if (status === 'agent') return <span className={`${chip} bg-blue-100 text-blue-800`}>AI handling</span>
  if (status === 'closed') return <span className={`${chip} bg-charcoal-200 text-charcoal-800`}>Closed</span>
  return <span className={`${chip} bg-charcoal-200 text-charcoal-800`}>{status}</span>
}

export function OptedOutChip() {
  return (
    <span className={`${chip} bg-red-100 text-red-800`}>
      <span aria-hidden="true">✗</span> Opted out
    </span>
  )
}

export function HandoffChip() {
  return (
    <span className={`${chip} bg-brand-100 text-brand-text`}>
      <span aria-hidden="true">!</span> Handoff open
    </span>
  )
}