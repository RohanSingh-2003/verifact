import type { ReactNode } from 'react'
import { classNames } from '../../lib/format'

interface DemoBadgeProps {
  className?: string
}

export function DemoBadge({ className }: DemoBadgeProps) {
  return (
    <span
      className={classNames(
        'inline-flex items-center rounded-full border border-line bg-surface-muted px-2 py-0.5 text-[10px] font-semibold tracking-[0.08em] text-ink-muted uppercase',
        className,
      )}
    >
      Demo data
    </span>
  )
}

interface TooltipProps {
  content: string
  children: ReactNode
}

export function Tooltip({ content, children }: TooltipProps) {
  return (
    <span className="group/tooltip relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-[calc(100%+8px)] left-1/2 z-30 w-max max-w-64 -translate-x-1/2 rounded-[var(--radius-sm)] bg-ink px-2.5 py-1.5 text-xs leading-4 text-canvas opacity-0 shadow-[var(--shadow-float)] transition-opacity group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100"
      >
        {content}
      </span>
    </span>
  )
}
