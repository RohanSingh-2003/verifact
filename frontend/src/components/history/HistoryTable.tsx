import { Search } from 'lucide-react'
import type { HistoryRun, Verdict } from '../../types'
import { Verdict as VerdictValue } from '../../types'
import { classNames, formatDate } from '../../lib/format'
import { ScoreMeter } from '../detect/ScoreGauge'
import { EmptyState, VerdictBadge } from '../ui/Status'

interface HistoryTableProps {
  runs: HistoryRun[]
  onSelect: (id: string) => void
  query: string
  onQueryChange: (value: string) => void
  verdictFilter: Verdict | 'all'
  onVerdictFilterChange: (value: Verdict | 'all') => void
}

const filters: Array<{ value: Verdict | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: VerdictValue.Reliable, label: 'Reliable' },
  { value: VerdictValue.Hallucinated, label: 'Hallucinated' },
]

export function HistoryTable({
  runs,
  onSelect,
  query,
  onQueryChange,
  verdictFilter,
  onVerdictFilterChange,
}: HistoryTableProps) {
  const emptyArchive = runs.length === 0 && !query && verdictFilter === 'all'

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="relative min-w-0 flex-1">
          <span className="sr-only">Search questions</span>
          <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-ink-muted" />
          <input
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search questions"
            autoComplete="off"
            className="w-full rounded-[var(--radius-sm)] border border-line bg-surface py-2.5 pr-3 pl-9 text-sm text-ink placeholder:text-ink-muted"
          />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by result">
          {filters.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => onVerdictFilterChange(filter.value)}
              aria-pressed={verdictFilter === filter.value}
              className={classNames(
                'rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                verdictFilter === filter.value
                  ? 'bg-ink text-white'
                  : 'bg-surface-muted text-ink-secondary hover:text-ink',
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {emptyArchive ? (
        <EmptyState
          title="No analyses yet"
          description="Run a question on Detect to start building a history of MetaQA evaluations."
        />
      ) : null}

      {!emptyArchive && runs.length === 0 ? (
        <EmptyState
          title="No matching runs"
          description="Try a different search term or clear the result filter."
        />
      ) : null}

      {runs.length > 0 ? (
        <>
          <div className="panel hidden overflow-hidden md:block">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-surface-muted/50 text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Question</th>
                  <th className="px-4 py-2.5 font-semibold">Model</th>
                  <th className="px-4 py-2.5 font-semibold">Score</th>
                  <th className="px-4 py-2.5 font-semibold">Result</th>
                  <th className="px-4 py-2.5 font-semibold">Date</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="cursor-pointer border-b border-line last:border-b-0 hover:bg-surface-muted/40"
                    onClick={() => onSelect(run.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        onSelect(run.id)
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open analysis for ${run.question}`}
                  >
                    <td className="max-w-[22rem] truncate px-4 py-3 text-ink">{run.question}</td>
                    <td className="px-4 py-3 text-ink-secondary">{run.model}</td>
                    <td className="px-4 py-3">
                      <ScoreMeter score={run.score} verdict={run.verdict} />
                    </td>
                    <td className="px-4 py-3">
                      <VerdictBadge verdict={run.verdict} />
                    </td>
                    <td className="px-4 py-3 text-ink-secondary">{formatDate(run.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="space-y-2 md:hidden">
            {runs.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => onSelect(run.id)}
                  className="panel w-full p-4 text-left"
                >
                  <p className="text-sm leading-6 text-ink">{run.question}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
                    <VerdictBadge verdict={run.verdict} />
                    <ScoreMeter score={run.score} verdict={run.verdict} />
                    <span className="text-xs text-ink-muted">{run.model}</span>
                    <span className="text-xs text-ink-muted">{formatDate(run.createdAt)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
