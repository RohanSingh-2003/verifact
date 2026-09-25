import { Check, X } from 'lucide-react'
import type { AnalysisStage } from '../../types'
import { AnalysisStage as Stage, HALLUCINATION_ANALYSIS_STEPS } from '../../types'
import { classNames } from '../../lib/format'

interface AnalysisProgressProps {
  stage: AnalysisStage
  /** When true, answer is already visible above this panel. */
  answerVisible?: boolean
  /** When true, mutation texts are already visible. */
  mutationsVisible?: boolean
  /** Verified mutation count for contextual verify label. */
  verifiedCount?: number
  /** Total mutation count once mutations exist. */
  mutationCount?: number
}

function stepState(
  stepId: string,
  stage: AnalysisStage,
  answerVisible: boolean,
  mutationsVisible: boolean,
  allVerified: boolean,
): 'done' | 'active' | 'pending' | 'failed' {
  if (stage === Stage.Complete) return 'done'
  if (stage === Stage.AnalysisFailed || stage === Stage.Error) {
    if (stepId === 'answer' && answerVisible) return 'done'
    if (stepId === 'mutations' && mutationsVisible) return 'done'
    if (stepId === 'verify' && allVerified) return 'done'
    if (stepId === 'verify' && mutationsVisible) return 'failed'
    if (stepId === 'score') return 'failed'
    if (stepId === 'mutations' && answerVisible) return 'failed'
    return 'pending'
  }

  const order = ['answer', 'mutations', 'verify', 'score'] as const
  const current =
    stage === Stage.GeneratingAnswer
      ? 'answer'
      : stage === Stage.AnswerReady || stage === Stage.GeneratingMutations
        ? 'mutations'
        : stage === Stage.VerifyingMutations
          ? 'verify'
          : stage === Stage.CalculatingScore
            ? 'score'
            : answerVisible
              ? 'mutations'
              : 'answer'

  const currentIndex = order.indexOf(current)
  const stepIndex = order.indexOf(stepId as (typeof order)[number])
  if (stepId === 'answer' && answerVisible) return 'done'
  if (stepId === 'mutations' && mutationsVisible) return 'done'
  if (stepIndex < currentIndex) return 'done'
  if (stepIndex === currentIndex) return 'active'
  return 'pending'
}

function stepLabel(
  stepId: string,
  state: 'done' | 'active' | 'pending' | 'failed',
  verifiedCount: number,
  mutationCount: number,
): string {
  if (stepId === 'answer') {
    return state === 'done' ? 'Answer generated' : 'Generating answer'
  }
  if (stepId === 'mutations') {
    if (state === 'done') return 'Test mutations created'
    if (state === 'failed') return 'Unable to generate mutation tests'
    return 'Creating test mutations'
  }
  if (stepId === 'verify') {
    if (state === 'done') return 'Mutations verified'
    if (state === 'failed') return 'Unable to complete mutation verification'
    if (state === 'active' && mutationCount > 0) {
      return `Verifying mutations (${verifiedCount}/${mutationCount})`
    }
    return 'Verifying mutations'
  }
  if (state === 'done') return 'Score calculated'
  if (state === 'failed') return 'Unable to calculate final score'
  return 'Calculating score'
}

export function AnalysisProgress({
  stage,
  answerVisible = false,
  mutationsVisible = false,
  verifiedCount = 0,
  mutationCount = 0,
}: AnalysisProgressProps) {
  const failed = stage === Stage.AnalysisFailed || stage === Stage.Error
  const allVerified = mutationCount > 0 && verifiedCount >= mutationCount
  const title = failed
    ? 'Hallucination analysis'
    : answerVisible
      ? 'Hallucination analysis in progress'
      : 'Working…'

  return (
    <div className="panel px-5 py-5" aria-live="polite">
      <div className="flex items-center gap-3">
        {!failed ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
        ) : null}
        <p className="text-sm font-medium text-ink">{title}</p>
      </div>

      <ol className="mt-4 space-y-2.5">
        {HALLUCINATION_ANALYSIS_STEPS.map((step) => {
          const state = stepState(step.id, stage, answerVisible, mutationsVisible, allVerified)
          const label = stepLabel(step.id, state, verifiedCount, mutationCount)
          return (
            <li key={step.id} className="flex items-center gap-2.5 text-sm">
              <span
                className={classNames(
                  'flex h-5 w-5 items-center justify-center rounded-full border text-[11px]',
                  state === 'done'
                    ? 'border-accent bg-accent-soft text-accent'
                    : state === 'active'
                      ? 'border-accent text-accent'
                      : state === 'failed'
                        ? 'border-hallucinated/40 bg-hallucinated-soft text-hallucinated'
                        : 'border-line text-ink-muted',
                )}
                aria-hidden="true"
              >
                {state === 'done' ? (
                  <Check className="h-3 w-3" strokeWidth={2.5} />
                ) : state === 'failed' ? (
                  <X className="h-3 w-3" strokeWidth={2.5} />
                ) : state === 'active' ? (
                  <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent" />
                ) : (
                  <span className="h-1 w-1 rounded-full bg-ink-muted/50" />
                )}
              </span>
              <span
                className={classNames(
                  state === 'done'
                    ? 'text-ink'
                    : state === 'active'
                      ? 'font-medium text-ink'
                      : state === 'failed'
                        ? 'text-hallucinated'
                        : 'text-ink-muted',
                )}
              >
                {label}
                {state === 'active' ? '…' : ''}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
