import { Info } from 'lucide-react'
import type { Verdict } from '../../types'
import { formatScore, verdictDescription } from '../../lib/format'
import { VerdictBadge } from '../ui/Status'
import { Tooltip } from '../ui/Tooltip'
import { ScoreGauge } from './ScoreGauge'

interface ScoreCardProps {
  score: number
  threshold: number
  verdict: Verdict
}

export function ScoreCard({ score, threshold, verdict }: ScoreCardProps) {
  return (
    <section className="panel p-5 shadow-[var(--shadow-card)] sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <p className="text-meta">Hallucination Score</p>
        <Tooltip content="Score ranges from 0 (consistent verifier behavior) to 1 (high inconsistency). Classification uses the configured threshold.">
          <button
            type="button"
            className="rounded-full p-0.5 text-ink-muted hover:text-ink"
            aria-label="About the hallucination score"
          >
            <Info className="h-3.5 w-3.5" strokeWidth={1.75} />
          </button>
        </Tooltip>
      </div>

      <p className="mt-4 text-[2.75rem] leading-none font-semibold tracking-tight text-ink tabular-nums">
        {formatScore(score)}
      </p>
      <p className="mt-3 text-sm font-semibold tracking-[0.14em] text-ink uppercase">
        {verdict === 'hallucinated' ? 'Hallucinated' : verdict === 'reliable' ? 'Reliable' : 'Uncertain'}
      </p>
      <p className="mt-2 text-sm text-ink-secondary">
        Threshold: {formatScore(threshold)}
        <span className="mx-2 text-ink-muted">·</span>
        {verdictDescription(verdict)}
      </p>
      <div className="mt-2">
        <VerdictBadge verdict={verdict} size="md" />
      </div>

      <div className="mt-6">
        <ScoreGauge score={score} threshold={threshold} verdict={verdict} />
      </div>
    </section>
  )
}
