export function formatRupees(amount: number | null): string {
  if (amount === null || amount === undefined) return '—'
  return '₹' + amount.toLocaleString('en-IN')
}