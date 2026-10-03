import { AlertTriangle, Check, X } from 'lucide-react'
import { classNames } from '../../lib/format'

export type StepState = 'done' | 'active' | 'pending' | 'failed'

export interface ProgressStepItem {
  id: string
  label: string
  state: StepState
  detail?: string | null
}

export type AnalysisProgressStatus =
  | 'running'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'unavailable'
  | 'pending'

export interface AnalysisProgressProps {
  title: string
  description?: string
  status?: AnalysisProgressStatus
  steps: ProgressStepItem[]
  errorReason?: string | null
  className?: string
}

export function AnalysisProgress({
  title,
  description,
  status = 'pending',
  steps,
  errorReason,
  className,
}: AnalysisProgressProps) {
  return (
    <div className={classNames('panel p-5 space-y-4', className)} aria-live="polite">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold tracking-tight text-ink">{title}</h2>
          {description ? (
            <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{description}</p>
          ) : null}
        </div>

        {status === 'running' ? (
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 text-[11px] font-medium text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            In progress
          </span>
        ) : status === 'completed' ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-reliable-soft px-2.5 py-0.5 text-[11px] font-medium text-reliable">
            <Check className="h-3 w-3" strokeWidth={2.5} />
            Complete
          </span>
        ) : status === 'partial' ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-accent-soft px-2.5 py-0.5 text-[11px] font-medium text-accent">
            <Check className="h-3 w-3" strokeWidth={2.5} />
            Partial
          </span>
        ) : status === 'unavailable' ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-uncertain-soft px-2.5 py-0.5 text-[11px] font-medium text-uncertain">
            <AlertTriangle className="h-3 w-3" />
            Unavailable
          </span>
        ) : status === 'failed' ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-hallucinated-soft px-2.5 py-0.5 text-[11px] font-medium text-hallucinated">
            <X className="h-3 w-3" />
            Failed
          </span>
        ) : (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-surface-muted px-2.5 py-0.5 text-[11px] font-medium text-ink-muted">
            Pending
          </span>
        )}
      </div>

      <ol className="space-y-2.5 pt-1">
        {steps.map((step) => (
          <li key={step.id} className="flex items-center gap-2.5 text-sm">
            <span
              className={classNames(
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] transition-colors',
                step.state === 'done'
                  ? 'border-reliable bg-reliable-soft text-reliable'
                  : step.state === 'active'
                    ? 'border-accent bg-accent-soft/50 text-accent ring-2 ring-accent/20'
                    : step.state === 'failed'
                      ? 'border-hallucinated/50 bg-hallucinated-soft text-hallucinated'
                      : 'border-line bg-canvas text-ink-muted/40',
              )}
              aria-hidden="true"
            >
              {step.state === 'done' ? (
                <Check className="h-3 w-3" strokeWidth={2.5} />
              ) : step.state === 'failed' ? (
                <X className="h-3 w-3" strokeWidth={2.5} />
              ) : step.state === 'active' ? (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              ) : (
                <span className="h-1 w-1 rounded-full bg-ink-muted/40" />
              )}
            </span>
            <span
              className={classNames(
                'transition-colors',
                step.state === 'done'
                  ? 'text-ink'
                  : step.state === 'active'
                    ? 'font-medium text-ink flex items-center gap-1.5'
                    : step.state === 'failed'
                      ? 'text-hallucinated'
                      : 'text-ink-muted',
              )}
            >
              {step.label}
              {step.state === 'active' ? (
                <span className="inline-block animate-pulse text-accent">…</span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>

      {errorReason ? (
        <div
          role="alert"
          className="mt-3 rounded-[var(--radius-sm)] border border-uncertain/40 bg-uncertain-soft/60 px-3.5 py-3 text-xs leading-5"
        >
          <div className="flex items-center gap-1.5 font-medium text-uncertain">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span>{title} unavailable</span>
          </div>
          <p className="mt-1 text-ink-secondary pl-5">Reason: {errorReason}</p>
        </div>
      ) : null}
    </div>
  )
}
