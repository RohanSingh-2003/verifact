import type { AnalysisResult } from '../../types'
import { formatScore, verdictLabel } from '../../lib/format'
import { VerdictBadge } from '../ui/Status'

interface AnalysisSummaryProps {
  result: AnalysisResult
}

export function AnalysisSummary({ result }: AnalysisSummaryProps) {
  return (
    <section className="panel p-5 sm:p-6">
      <h2 className="text-base font-semibold tracking-tight text-ink">Why this result?</h2>
      <ul className="mt-4 space-y-2.5">
        {result.summaryPoints.map((point) => (
          <li key={point} className="flex gap-3 text-sm leading-6 text-ink-secondary">
            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink-muted" />
            {point}
          </li>
        ))}
      </ul>

      <dl className="mt-6 grid grid-cols-3 gap-3 border-t border-line pt-4">
        <div>
          <dt className="text-meta">Threshold</dt>
          <dd className="mt-1.5 text-sm font-medium tabular-nums text-ink">
            {formatScore(result.threshold)}
          </dd>
        </div>
        <div>
          <dt className="text-meta">Score</dt>
          <dd className="mt-1.5 text-sm font-medium tabular-nums text-ink">
            {result.score != null ? formatScore(result.score) : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-meta">Decision</dt>
          <dd className="mt-1.5">
            {result.verdict ? (
              <>
                <VerdictBadge verdict={result.verdict} />
                <span className="sr-only">{verdictLabel(result.verdict)}</span>
              </>
            ) : (
              <span className="text-sm text-ink-muted">Pending</span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  )
}
