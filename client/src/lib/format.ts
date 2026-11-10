export function relTime(iso: string): string {
  const minutes = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'now'
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d`
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export function clock(iso: string): string {
  const d = new Date(iso)
  const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
  if (d.toDateString() === new Date().toDateString()) return time
  return `${d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}, ${time}`
}

export function humanize(key: string): string {
  const t = key.replace(/_/g, ' ').trim()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export function toText(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  if (Array.isArray(v)) return v.map(toText).join(', ')
  try {
    return JSON.stringify(v)
  } catch {
    return ''
  }
}

// 6000000 -> "\u20B960,00,000" (Indian digit grouping)
export function formatRupees(n: number): string {
  return '\u20B9' + n.toLocaleString('en-IN')
}

export type ScoreBand = 'hot' | 'warm' | 'cold'

// Matches scoring.py: Hot 70+, Warm 40-69, Cold below 40.
export function scoreBand(score: number): ScoreBand {
  if (score >= 70) return 'hot'
  if (score >= 40) return 'warm'
  return 'cold'
}

const LANGUAGES: Record<string, string> = { en: 'English', hi: 'Hindi', or: 'Odia' }

export function languageName(code: string | null): string {
  if (!code) return ''
  return LANGUAGES[code.toLowerCase()] ?? code
}