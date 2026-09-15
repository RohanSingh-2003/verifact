import type { EvaluationMetrics } from '../../types'
import { formatScore } from '../../lib/format'

interface ThresholdSweepChartProps {
  rows: EvaluationMetrics[]
}

const LINES = [
  { key: 'precision' as const, label: 'Precision', color: '#2f6f5e' },
  { key: 'recall' as const, label: 'Recall', color: '#1c1917' },
  { key: 'f1' as const, label: 'F1', color: '#9a4036' },
]

export function ThresholdSweepChart({ rows }: ThresholdSweepChartProps) {
  const sorted = [...rows].sort((a, b) => a.threshold - b.threshold)
  if (sorted.length === 0) return null

  const width = 640
  const height = 240
  const pad = { left: 36, right: 12, top: 16, bottom: 28 }
  const innerW = width - pad.left - pad.right
  const innerH = height - pad.top - pad.bottom
  const minX = sorted[0].threshold
  const maxX = sorted[sorted.length - 1].threshold
  const spanX = Math.max(maxX - minX, 0.01)

  function xOf(threshold: number) {
    return pad.left + ((threshold - minX) / spanX) * innerW
  }
  function yOf(value: number) {
    return pad.top + (1 - Math.min(Math.max(value, 0), 1)) * innerH
  }

  return (
    <section className="panel p-5">
      <h2 className="text-base font-semibold tracking-tight text-ink">Threshold sensitivity</h2>
      <p className="mt-1 text-sm text-ink-secondary">
        Saved MetaQA scores re-classified across thresholds. Detection is not re-run.
      </p>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-4 w-full" role="img" aria-label="Precision, recall, and F1 by threshold">
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={yOf(tick)}
              y2={yOf(tick)}
              stroke="#e7e3db"
              strokeWidth="1"
            />
            <text x={pad.left - 8} y={yOf(tick) + 3} textAnchor="end" className="fill-ink-muted" fontSize="10">
              {tick.toFixed(2)}
            </text>
          </g>
        ))}
        {LINES.map((line) => {
          const d = sorted
            .map((row, index) => `${index === 0 ? 'M' : 'L'} ${xOf(row.threshold)} ${yOf(row[line.key])}`)
            .join(' ')
          return <path key={line.key} d={d} fill="none" stroke={line.color} strokeWidth="1.75" />
        })}
        {sorted.map((row) => (
          <text
            key={row.threshold}
            x={xOf(row.threshold)}
            y={height - 8}
            textAnchor="middle"
            className="fill-ink-muted"
            fontSize="10"
          >
            {formatScore(row.threshold)}
          </text>
        ))}
      </svg>
      <div className="mt-2 flex gap-4 text-[11px] text-ink-muted">
        {LINES.map((line) => (
          <span key={line.key} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm" style={{ background: line.color }} />
            {line.label}
          </span>
        ))}
      </div>
    </section>
  )
}
