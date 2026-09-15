interface MetricCardProps {
  label: string
  value: string
}

export function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="min-w-0">
      <p className="text-meta">{label}</p>
      <p className="mt-2 text-lg font-semibold tabular-nums tracking-tight text-ink">{value}</p>
    </div>
  )
}
