export default function ComingSoon({ title, note }: { title: string; note: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-charcoal-950">{title}</h1>
      <p className="mt-2 text-charcoal-600">{note}</p>
    </div>
  )
}