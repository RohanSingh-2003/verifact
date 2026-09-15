import { ANALYSIS_STAGE_LABEL, ANALYSIS_STAGES } from '../../types'
import type { AnalysisStage } from '../../types'
import { classNames } from '../../lib/format'

interface AnalysisProgressProps {
  stage: AnalysisStage
}

export function AnalysisProgress({ stage }: AnalysisProgressProps) {
  const currentIndex = ANALYSIS_STAGES.findIndex((item) => item === stage)
  const label =
    stage === 'idle' || stage === 'complete' || stage === 'error'
      ? 'Preparing analysis...'
      : ANALYSIS_STAGE_LABEL[stage]

  return (
    <div className="panel px-5 py-5" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
        <p className="text-sm font-medium text-ink">{label}</p>
      </div>
      <ol className="mt-4 grid grid-cols-4 gap-2" aria-hidden="true">
        {ANALYSIS_STAGES.map((item, index) => (
          <li
            key={item}
            className={classNames(
              'h-1 rounded-full',
              index < currentIndex
                ? 'bg-accent'
                : index === currentIndex
                  ? 'animate-pulse-soft bg-accent/70'
                  : 'bg-line',
            )}
          />
        ))}
      </ol>
    </div>
  )
}
