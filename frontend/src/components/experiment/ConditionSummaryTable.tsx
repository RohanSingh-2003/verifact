import type { ExperimentConditionSummary } from '../../types'
import { formatPercent, formatScore, shortModelName } from '../../lib/format'

interface ConditionSummaryTableProps {
  rows: ExperimentConditionSummary[]
}

export function ConditionSummaryTable({ rows }: ConditionSummaryTableProps) {
  return (
    <section>
      <h2 className="text-base font-semibold tracking-tight text-ink">2×2 result summary</h2>
      <div className="panel mt-3 overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/50 text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
            <tr>
              <th className="px-4 py-2.5">Generator</th>
              <th className="px-4 py-2.5">Verifier</th>
              <th className="px-4 py-2.5">Pair type</th>
              <th className="px-4 py-2.5">Mean score</th>
              <th className="px-4 py-2.5">Reliable %</th>
              <th className="px-4 py-2.5">Hallucinated %</th>
              <th className="px-4 py-2.5">NOT SURE %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.generator_model}-${row.verifier_model}`} className="border-b border-line last:border-b-0">
                <td className="px-4 py-3">{shortModelName(row.generator_model)}</td>
                <td className="px-4 py-3">{shortModelName(row.verifier_model)}</td>
                <td className="px-4 py-3 capitalize">{row.pair_type === 'same' ? 'Same' : 'Cross'}</td>
                <td className="px-4 py-3 tabular-nums">{formatScore(row.mean_score)}</td>
                <td className="px-4 py-3 tabular-nums">{formatPercent(row.reliable_rate)}</td>
                <td className="px-4 py-3 tabular-nums">{formatPercent(row.hallucinated_rate)}</td>
                <td className="px-4 py-3 tabular-nums">{formatPercent(row.not_sure_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
