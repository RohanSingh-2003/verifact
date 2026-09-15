import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { MutationRecord, VerifierResponse } from '../../types'
import {
  classNames,
  formatScore,
  mutationKindLabel,
  unexpectedMutation,
  verifierLabel,
} from '../../lib/format'

const actualTone: Record<VerifierResponse, string> = {
  yes: 'text-reliable bg-reliable-soft',
  no: 'text-ink-secondary bg-surface-muted',
  not_sure: 'text-uncertain bg-uncertain-soft',
}

function ActualPill({ value }: { value: VerifierResponse }) {
  return (
    <span
      className={classNames(
        'inline-flex min-w-[4.5rem] justify-center rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide',
        actualTone[value],
      )}
    >
      {verifierLabel(value)}
    </span>
  )
}

function ExpectedPill({ value }: { value: VerifierResponse }) {
  return (
    <span className="inline-flex min-w-[4.5rem] justify-center rounded-full border border-line-strong bg-surface px-2 py-0.5 text-[11px] font-semibold tracking-wide text-ink-secondary">
      {verifierLabel(value)}
    </span>
  )
}

interface MutationRowProps {
  mutation: MutationRecord
}

export function MutationRow({ mutation }: MutationRowProps) {
  const [open, setOpen] = useState(false)
  const mismatched = unexpectedMutation(mutation.verifier, mutation.expected)

  return (
    <article className="border-b border-line last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="w-full px-4 py-3.5 text-left"
        aria-expanded={open}
      >
        <div className="md:hidden">
          <p className="text-sm leading-6 text-ink">{mutation.mutation}</p>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={
                  mutation.kind === 'synonym'
                    ? 'rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent'
                    : 'rounded-full bg-surface-muted px-2 py-0.5 font-medium text-ink-secondary'
                }
              >
                {mutationKindLabel(mutation.kind)}
              </span>
              {mismatched ? <span>Unexpected</span> : <span>Expected</span>}
            </div>
            <span className="inline-flex items-center gap-1">
              Rationale
              <ChevronDown className={classNames('h-3.5 w-3.5 transition-transform', open ? 'rotate-180' : '')} />
            </span>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-ink-muted">Actual verdict</dt>
              <dd className="mt-1">
                <ActualPill value={mutation.verifier} />
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Expected verdict</dt>
              <dd className="mt-1">
                <ExpectedPill value={mutation.expected} />
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-ink-muted">MetaQA contribution</dt>
              <dd className="mt-1 tabular-nums text-ink">{formatScore(mutation.score)}</dd>
            </div>
          </dl>
        </div>

        <div className="hidden md:grid md:grid-cols-[minmax(0,1fr)_5.5rem_5.75rem_5.75rem_5.5rem_1rem] md:items-center md:gap-3">
          <p className="min-w-0 text-[13px] leading-5 text-ink">{mutation.mutation}</p>
          <span
            className={classNames(
              'justify-self-start rounded-full px-2 py-0.5 text-[11px] font-medium',
              mutation.kind === 'synonym'
                ? 'bg-accent-soft text-accent'
                : 'bg-surface-muted text-ink-secondary',
            )}
          >
            {mutationKindLabel(mutation.kind)}
          </span>
          <ActualPill value={mutation.verifier} />
          <ExpectedPill value={mutation.expected} />
          <span className="text-right text-sm tabular-nums text-ink">{formatScore(mutation.score)}</span>
          <ChevronDown
            className={classNames(
              'h-4 w-4 justify-self-end text-ink-muted transition-transform',
              open ? 'rotate-180' : '',
            )}
          />
        </div>
      </button>

      {open ? (
        <div className="space-y-3 bg-canvas px-4 py-4">
          <p className="text-xs text-ink-muted">
            Original: <span className="text-ink-secondary">{mutation.original}</span>
          </p>
          <div>
            <p className="text-meta">Verifier reasoning</p>
            <p className="mt-2 text-sm leading-6 text-ink-secondary">{mutation.reasoning}</p>
            <p className="mt-2 text-xs text-ink-muted">
              Explanatory only. The MetaQA score is computed from expected versus observed verifier
              labels, not from this rationale.
            </p>
          </div>
        </div>
      ) : null}
    </article>
  )
}
