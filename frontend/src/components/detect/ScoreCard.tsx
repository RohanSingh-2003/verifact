import { Info } from 'lucide-react'
import type { Verdict } from '../../types'
import { formatScore, verdictDescription, verdictLabel } from '../../lib/format'
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
        <div>
          <p className="text-meta">Result</p>
          <p className="mt-3 text-[1.35rem] font-semibold tracking-tight text-ink sm:text-[1.5rem]">
            {verdictLabel(verdict).toUpperCase()}
          </p>
        </div>
        <VerdictBadge verdict={verdict} size="md" />
      </div>

      <div className="mt-5">
        <div className="flex items-center gap-1.5">
          <p className="text-meta">Hallucination score</p>
          <Tooltip content="Lower scores indicate behavior more consistent with the expected MetaQA pattern. Higher scores indicate more inconsistent behavior. Classification uses the configured threshold.">
            <button
              type="button"
              className="rounded-full p-0.5 text-ink-muted hover:text-ink"
              aria-label="About the hallucination score"
            >
              <Info className="h-3.5 w-3.5" strokeWidth={1.75} />
            </button>
          </Tooltip>
        </div>
        <p className="mt-2 text-[2.75rem] leading-none font-semibold tracking-tight text-ink tabular-nums">
          {formatScore(score)}
        </p>
      </div>

      <div className="mt-4 space-y-2 text-sm leading-6 text-ink-secondary">
        <p>
          <span className="font-medium text-ink">What this means</span>
          <span className="mx-2 text-ink-muted">·</span>
          {verdictDescription(verdict)}
        </p>
        <p className="text-xs text-ink-muted">
          Lower scores indicate behavior that is more consistent with the expected MetaQA pattern.
          Higher scores indicate more inconsistent behavior.
        </p>
        <p className="text-xs text-ink-muted">
          Threshold: {formatScore(threshold)}. Scores at or above the threshold are classified as
          likely hallucinated.
        </p>
      </div>

      <div className="mt-6">
        <ScoreGauge score={score} threshold={threshold} verdict={verdict} />
      </div>
    </section>
  )
}
