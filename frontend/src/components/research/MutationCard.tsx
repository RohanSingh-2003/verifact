import type { ReactNode } from 'react'
import { classNames } from '../../lib/format'

export interface MutationCardProps {
  badge: string
  title: string
  badgeVariant: 'synonym' | 'antonym'
  description: ReactNode
  original: string
  mutation: string
  expectedVerdict: 'YES' | 'NO'
  verdictVariant: 'reliable' | 'hallucinated'
}

export function MutationCard({
  badge,
  title,
  badgeVariant,
  description,
  original,
  mutation,
  expectedVerdict,
  verdictVariant,
}: MutationCardProps) {
  return (
    <div className="panel p-5 sm:p-6 flex flex-col h-full">
      {/* 1. Header with identical icon badge and title alignment */}
      <div className="flex items-center gap-2.5">
        <span
          className={classNames(
            'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold',
            badgeVariant === 'synonym'
              ? 'bg-accent-soft text-accent'
              : 'bg-hallucinated-soft text-hallucinated',
          )}
          aria-hidden="true"
        >
          {badge}
        </span>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
      </div>

      {/* 2. Description area with flex-1 to equalize vertical space */}
      <div className="flex-1 my-3 text-xs leading-5 text-ink-secondary">
        {description}
      </div>

      {/* 3. Example box anchored with mt-auto, identical rows and vertical height */}
      <div className="mt-auto rounded-[var(--radius-sm)] border border-line bg-canvas p-3.5 text-xs space-y-2">
        <div className="space-y-0.5">
          <span className="text-[11px] font-medium text-ink-muted">Original:</span>
          <p className="text-ink font-medium leading-relaxed">&ldquo;{original}&rdquo;</p>
        </div>
        <div className="border-t border-line/60 pt-1.5 space-y-0.5">
          <span className="text-[11px] font-medium text-ink-muted">Mutation:</span>
          <p className="text-ink-secondary leading-relaxed">&ldquo;{mutation}&rdquo;</p>
        </div>
        <div className="border-t border-line/60 pt-1.5 flex items-center justify-between">
          <span className="text-[11px] font-medium text-ink-muted">Expected Verifier Verdict:</span>
          <span
            className={classNames(
              'text-[11px] font-bold tracking-wide',
              verdictVariant === 'reliable' ? 'text-reliable' : 'text-hallucinated',
            )}
          >
            {expectedVerdict}
          </span>
        </div>
      </div>
    </div>
  )
}
