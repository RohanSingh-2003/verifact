import type { Verdict } from '../../types'
import { classNames, formatScore } from '../../lib/format'

interface ScoreGaugeProps {
  score: number
  threshold: number
  verdict: Verdict
}

const markerColor: Record<Verdict, string> = {
  reliable: 'bg-reliable',
  uncertain: 'bg-uncertain',
  hallucinated: 'bg-hallucinated',
}

const labelClass: Record<Verdict, string> = {
  reliable: 'text-reliable',
  uncertain: 'text-uncertain',
  hallucinated: 'text-hallucinated',
}

export function ScoreGauge({ score, threshold, verdict }: ScoreGaugeProps) {
  const clamped = Math.min(Math.max(score, 0), 1)
  const position = `${clamped * 100}%`
  const thresholdPosition = `${threshold * 100}%`

  return (
    <div>
      <div
        className="relative h-2 rounded-full bg-surface-muted"
        role="meter"
        aria-label="Hallucination score"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={Number(clamped.toFixed(2))}
      >
        <span
          className="absolute top-0 bottom-0 w-px bg-ink/35"
          style={{ left: thresholdPosition }}
          aria-hidden="true"
        />
        <span
          className={classNames(
            'absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white',
            markerColor[verdict],
          )}
          style={{ left: position }}
        />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-ink-muted">
        <span>0</span>
        <span>Threshold {formatScore(threshold)}</span>
        <span>1</span>
      </div>
      <div className="mt-3 grid grid-cols-3 text-[11px] font-medium">
        <span className={verdict === 'reliable' ? labelClass.reliable : 'text-ink-muted'}>
          Reliable
        </span>
        <span
          className={classNames(
            'text-center',
            verdict === 'uncertain' ? labelClass.uncertain : 'text-ink-muted',
          )}
        >
          Uncertain
        </span>
        <span
          className={classNames(
            'text-right',
            verdict === 'hallucinated' ? labelClass.hallucinated : 'text-ink-muted',
          )}
        >
          Hallucinated
        </span>
      </div>
    </div>
  )
}

interface ScoreMeterProps {
  score: number
  verdict: Verdict
}

export function ScoreMeter({ score, verdict }: ScoreMeterProps) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="relative h-1.5 w-14 overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
        <span
          className={classNames('absolute inset-y-0 left-0 rounded-full', markerColor[verdict])}
          style={{ width: `${Math.min(Math.max(score, 0), 1) * 100}%` }}
        />
      </span>
      <span className="tabular-nums text-ink">{formatScore(score)}</span>
    </span>
  )
}
