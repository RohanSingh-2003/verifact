import { useMemo, useState } from 'react'
import type { PairedComparison } from '../../types'
import { classNames, formatScore, shortModelName } from '../../lib/format'

type SortKey = 'largest' | 'smallest' | 'flips'

interface PairedQuestionsTableProps {
  rows: PairedComparison[]
  selectedId?: string | null
  onSelect: (row: PairedComparison) => void
}

export function PairedQuestionsTable({ rows, selectedId, onSelect }: PairedQuestionsTableProps) {
  const [sort, setSort] = useState<SortKey>('largest')

  const sorted = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      if (sort === 'flips') {
        if (a.classification_flip !== b.classification_flip) {
          return a.classification_flip ? -1 : 1
        }
        return Math.abs(b.difference) - Math.abs(a.difference)
      }
      const delta = Math.abs(b.difference) - Math.abs(a.difference)
      return sort === 'largest' ? delta : -delta
    })
    return copy
  }, [rows, sort])

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-ink">Question-level paired analysis</h2>
          <p className="mt-1 text-sm text-ink-secondary">
            Same questions, same mutations, different verifiers. Click a row for the mutation trace.
          </p>
        </div>
        <label className="text-xs text-ink-muted">
          Sort
          <select
            className="ml-2 rounded-[var(--radius-sm)] border border-line bg-surface px-2 py-1 text-sm text-ink"
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
          >
            <option value="largest">Largest difference</option>
            <option value="smallest">Smallest difference</option>
            <option value="flips">Classification flips</option>
          </select>
        </label>
      </div>
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/50 text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
            <tr>
              <th className="px-4 py-2.5">Question</th>
              <th className="px-4 py-2.5">Generator</th>
              <th className="px-4 py-2.5">Same score</th>
              <th className="px-4 py-2.5">Cross score</th>
              <th className="px-4 py-2.5">Difference</th>
              <th className="px-4 py-2.5">Same label</th>
              <th className="px-4 py-2.5">Cross label</th>
              <th className="px-4 py-2.5">Flip?</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const selected = row.generation_id === selectedId
              return (
                <tr
                  key={`${row.generation_id}-${row.generator_model}`}
                  className={classNames(
                    'cursor-pointer border-b border-line last:border-b-0',
                    selected ? 'bg-accent-soft/60' : 'hover:bg-surface-muted/60',
                  )}
                  onClick={() => onSelect(row)}
                >
                  <td className="max-w-[18rem] px-4 py-3">
                    <p className="truncate" title={row.question}>
                      {row.question}
                    </p>
                  </td>
                  <td className="px-4 py-3">{shortModelName(row.generator_model)}</td>
                  <td className="px-4 py-3 tabular-nums">{formatScore(row.same_model_score)}</td>
                  <td className="px-4 py-3 tabular-nums">{formatScore(row.cross_model_score)}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {row.difference > 0 ? '+' : ''}
                    {formatScore(row.difference)}
                  </td>
                  <td className="px-4 py-3">{row.same_label}</td>
                  <td className="px-4 py-3">{row.cross_label}</td>
                  <td className="px-4 py-3">{row.classification_flip ? 'Yes' : 'No'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
