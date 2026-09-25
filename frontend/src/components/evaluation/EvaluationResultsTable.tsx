import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { EvaluationResultRow } from '../../types'
import { classNames, formatScore } from '../../lib/format'

interface EvaluationResultsTableProps {
  results: EvaluationResultRow[]
}

const OUTCOMES = ['all', 'FP', 'FN', 'Correct', 'Needs Review'] as const
const CATEGORIES = ['all', 'named_entity', 'date', 'numeric', 'location', 'general_fact'] as const

function isCorrect(outcome: string) {
  return outcome === 'TP' || outcome === 'TN'
}

export function EvaluationResultsTable({ results }: EvaluationResultsTableProps) {
  const navigate = useNavigate()
  const [outcome, setOutcome] = useState<(typeof OUTCOMES)[number]>('all')
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>('all')

  const filtered = useMemo(() => {
    return results.filter((row) => {
      const matchesOutcome =
        outcome === 'all' ||
        (outcome === 'Correct' && isCorrect(row.outcome)) ||
        row.outcome === outcome
      const matchesCategory = category === 'all' || row.category === category
      return matchesOutcome && matchesCategory
    })
  }, [results, outcome, category])

  return (
    <section>
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-base font-semibold tracking-tight text-ink">Per-question results</h2>
        <div className="flex flex-wrap gap-1.5">
          {OUTCOMES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setOutcome(value)}
              className={classNames(
                'rounded-full px-3 py-1.5 text-xs font-medium',
                outcome === value ? 'bg-ink text-canvas' : 'bg-surface-muted text-ink-secondary hover:text-ink',
              )}
            >
              {value === 'all' ? 'All' : value}
            </button>
          ))}
        </div>
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {CATEGORIES.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setCategory(value)}
            className={classNames(
              'rounded-full px-3 py-1.5 text-xs font-medium',
              category === value ? 'bg-ink text-canvas' : 'bg-surface-muted text-ink-secondary hover:text-ink',
            )}
          >
            {value === 'all' ? 'All categories' : value.replace('_', ' ')}
          </button>
        ))}
      </div>

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/50 text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
            <tr>
              <th className="px-4 py-2.5 font-semibold">Question</th>
              <th className="px-4 py-2.5 font-semibold">Actual</th>
              <th className="px-4 py-2.5 font-semibold">Predicted</th>
              <th className="px-4 py-2.5 font-semibold">Score</th>
              <th className="px-4 py-2.5 font-semibold">Category</th>
              <th className="px-4 py-2.5 font-semibold">Outcome</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr
                key={row.question_id}
                className={classNames(row.run_id ? 'cursor-pointer hover:bg-surface-muted/40' : '')}
                onClick={() => {
                  if (row.run_id) navigate(`/?id=${row.run_id}`)
                }}
              >
                <td className="max-w-sm px-4 py-3 text-ink">{row.question}</td>
                <td className="px-4 py-3 text-ink-secondary">{row.actual_label}</td>
                <td className="px-4 py-3 text-ink-secondary">{row.predicted_label}</td>
                <td className="px-4 py-3 tabular-nums text-ink">{formatScore(row.hallucination_score)}</td>
                <td className="px-4 py-3 text-ink-secondary">{row.category.replace('_', ' ')}</td>
                <td className="px-4 py-3 font-medium text-ink">{row.outcome}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? (
          <p className="px-4 py-6 text-sm text-ink-secondary">No rows match these filters.</p>
        ) : null}
      </div>
    </section>
  )
}
