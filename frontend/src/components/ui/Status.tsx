import type { ReactNode } from 'react'
import { classNames } from '../../lib/format'

interface EmptyStateProps {
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-[var(--radius-md)] border border-dashed border-line px-6 py-12 text-center">
      <h2 className="text-base font-medium text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-ink-secondary">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}

interface LoadingStateProps {
  label?: string
}

export function LoadingState({ label = 'Loading…' }: LoadingStateProps) {
  return (
    <div className="panel flex items-center gap-3 px-4 py-5">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
      <p className="text-sm text-ink-secondary">{label}</p>
    </div>
  )
}

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
}

export function ErrorState({ title = 'Request failed', message, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="rounded-[var(--radius-md)] border border-hallucinated/20 bg-hallucinated-soft px-5 py-5"
    >
      <h2 className="text-sm font-medium text-hallucinated">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-ink-secondary">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 text-sm font-medium text-ink underline-offset-4 hover:underline"
        >
          Try again
        </button>
      ) : null}
    </div>
  )
}

interface VerdictBadgeProps {
  verdict: 'reliable' | 'uncertain' | 'hallucinated'
  size?: 'sm' | 'md'
}

const verdictStyles = {
  reliable: 'bg-reliable-soft text-reliable',
  uncertain: 'bg-uncertain-soft text-uncertain',
  hallucinated: 'bg-hallucinated-soft text-hallucinated',
}

const verdictText = {
  reliable: 'Likely reliable',
  uncertain: 'Uncertain',
  hallucinated: 'Likely hallucinated',
}

export function VerdictBadge({ verdict, size = 'sm' }: VerdictBadgeProps) {
  return (
    <span
      className={classNames(
        'inline-flex items-center rounded-full font-medium',
        verdictStyles[verdict],
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs',
      )}
    >
      {verdictText[verdict]}
    </span>
  )
}
