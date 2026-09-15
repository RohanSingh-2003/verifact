import type { ExperimentCell } from '../../types'
import { classNames } from '../../lib/format'

interface ExperimentChartProps {
  cells: ExperimentCell[]
}

export function ExperimentChart({ cells }: ExperimentChartProps) {
  return (
    <section className="panel p-5">
      <h2 className="text-base font-semibold tracking-tight text-ink">
        Hallucination Score by Generator / Verifier
      </h2>
      <p className="mt-1 text-sm text-ink-secondary">
        Mean hallucination score on a 0–1 scale by generator → verifier pair.
      </p>

      <ul className="mt-6 space-y-3">
        {cells.map((cell) => {
          const same = cell.generatorId === cell.verifierId
          return (
            <li key={cell.label} className="grid grid-cols-[4.25rem_1fr_2.5rem] items-center gap-3">
              <span className="text-xs font-medium text-ink-secondary">{cell.label}</span>
              <div className="h-5 overflow-hidden rounded bg-surface-muted">
                <div
                  className={classNames('h-5', same ? 'bg-accent/75' : 'bg-ink/55')}
                  style={{ width: `${Math.min(Math.max(cell.meanScore, 0), 1) * 100}%` }}
                />
              </div>
              <span className="text-right text-sm tabular-nums text-ink">
                {cell.meanScore.toFixed(2)}
              </span>
            </li>
          )
        })}
      </ul>

      <div className="mt-4 flex justify-between text-[11px] text-ink-muted">
        <span>0</span>
        <span className="inline-flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-accent/75" /> Same-model
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-ink/55" /> Cross-model
          </span>
        </span>
        <span>1</span>
      </div>
    </section>
  )
}
