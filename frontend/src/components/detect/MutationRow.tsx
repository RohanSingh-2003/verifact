import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { MutationRecord, VerifierResponse } from '../../types'
import {
  classNames,
  formatScore,
  mutationExpectationLabel,
  mutationInterpretation,
  mutationKindLabel,
  mutationMeaningLabel,
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

function PendingPill({ label }: { label: string }) {
  return (
    <span className="inline-flex min-w-[4.5rem] items-center justify-center gap-1.5 rounded-full border border-line bg-surface px-2 py-0.5 text-[11px] font-medium text-ink-muted">
      <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-accent" aria-hidden="true" />
      {label}
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
  const pending = !mutation.verified || mutation.verifier == null
  const mismatched =
    !pending && mutation.verifier != null
      ? unexpectedMutation(mutation.verifier, mutation.expected)
      : false
  const typeHint = mutationMeaningLabel(mutation.kind)
  const interpretation = mutationInterpretation(mutation.kind, mutation.verifier, mutation.expected)

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
                title={typeHint}
                className={
                  mutation.kind === 'synonym'
                    ? 'rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent'
                    : 'rounded-full bg-surface-muted px-2 py-0.5 font-medium text-ink-secondary'
                }
              >
                {mutationKindLabel(mutation.kind)}
              </span>
              {pending ? (
                <span>Verifying…</span>
              ) : mismatched ? (
                <span>Unexpected</span>
              ) : (
                <span>Matches expected</span>
              )}
            </div>
            <span className="inline-flex items-center gap-1">
              Details
              <ChevronDown className={classNames('h-3.5 w-3.5 transition-transform', open ? 'rotate-180' : '')} />
            </span>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div>
              <dt className="text-ink-muted">AI verdict</dt>
              <dd className="mt-1">
                {pending || mutation.verifier == null ? (
                  <PendingPill label="…" />
                ) : (
                  <ActualPill value={mutation.verifier} />
                )}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted" title="Verdict required by the MetaQA test">
                Expected verdict
              </dt>
              <dd className="mt-1">
                <ExpectedPill value={mutation.expected} />
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-ink-muted">Score contribution</dt>
              <dd className="mt-1 tabular-nums text-ink">
                {pending ? '—' : formatScore(mutation.score ?? 0)}
              </dd>
            </div>
          </dl>
        </div>

        <div className="hidden md:grid md:grid-cols-[minmax(0,1fr)_5.5rem_5.75rem_5.75rem_5.5rem_1rem] md:items-center md:gap-3">
          <p className="min-w-0 text-[13px] leading-5 text-ink">{mutation.mutation}</p>
          <span
            title={typeHint}
            className={classNames(
              'justify-self-start rounded-full px-2 py-0.5 text-[11px] font-medium',
              mutation.kind === 'synonym'
                ? 'bg-accent-soft text-accent'
                : 'bg-surface-muted text-ink-secondary',
            )}
          >
            {mutationKindLabel(mutation.kind)}
          </span>
          {pending || mutation.verifier == null ? (
            <PendingPill label="…" />
          ) : (
            <ActualPill value={mutation.verifier} />
          )}
          <span title="Verdict required by the MetaQA test">
            <ExpectedPill value={mutation.expected} />
          </span>
          <span
            className="text-right text-sm tabular-nums text-ink"
            title="How much this test contributes to the MetaQA hallucination score"
          >
            {pending ? '—' : formatScore(mutation.score ?? 0)}
          </span>
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
          <p className="text-meta">Why this test matters</p>

          <dl className="space-y-2.5 text-sm">
            <div>
              <dt className="text-xs text-ink-muted">Based on claim</dt>
              <dd className="mt-1 leading-6 text-ink-secondary">{mutation.original}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Mutation</dt>
              <dd className="mt-1 leading-6 text-ink">{mutation.mutation}</dd>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <dt className="text-xs text-ink-muted">Type</dt>
                <dd className="mt-1 text-ink-secondary">{mutationKindLabel(mutation.kind)}</dd>
              </div>
              <div>
                <dt className="text-xs text-ink-muted">Meaning</dt>
                <dd className="mt-1 text-ink-secondary">{typeHint}</dd>
              </div>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Verification</dt>
              <dd className="mt-1 space-y-0.5 tabular-nums text-ink-secondary">
                <p>
                  AI verdict:{' '}
                  {pending || mutation.verifier == null ? '…' : verifierLabel(mutation.verifier)}
                </p>
                <p>Expected: {verifierLabel(mutation.expected)}</p>
                <p>Score contribution: {pending ? '—' : formatScore(mutation.score ?? 0)}</p>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-ink-muted">Interpretation</dt>
              <dd className="mt-1 leading-6 text-ink">
                {pending ? 'Waiting for verifier result…' : interpretation}
              </dd>
              {!pending ? (
                <p className="mt-1.5 text-xs leading-5 text-ink-muted">
                  {mutationExpectationLabel(mutation.kind)} This explanation is for display only and
                  does not affect the MetaQA score.
                </p>
              ) : null}
            </div>
          </dl>
        </div>
      ) : null}
    </article>
  )
}
