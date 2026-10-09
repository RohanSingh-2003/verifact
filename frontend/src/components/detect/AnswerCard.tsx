import { Check } from 'lucide-react'
import { CopyButton } from '../ui/CopyButton'
import { classNames, formatModelDisplay, formatResponseTime } from '../../lib/format'
import type { WebClaimRecord } from '../../types'
import { EvidenceVerdict } from '../../types'

interface AnswerCardProps {
  answer?: string
  model?: string
  answerModel?: { id: string; name: string; provider: string; modelName?: string } | null
  responseTimeMs?: number
  isGenerating?: boolean
  claims?: WebClaimRecord[]
  onFocusClaim?: (claimId: string) => void
}

function claimBadge(verdict: EvidenceVerdict): { label: string; className: string } {
  if (verdict === EvidenceVerdict.Supported) {
    return { label: 'Supported', className: 'text-reliable bg-reliable-soft' }
  }
  if (verdict === EvidenceVerdict.Contradicted) {
    return { label: 'Contradicted', className: 'text-hallucinated bg-hallucinated-soft' }
  }
  return { label: 'Insufficient', className: 'text-uncertain bg-uncertain-soft' }
}

export function AnswerCard({
  answer,
  model,
  answerModel,
  responseTimeMs,
  isGenerating = false,
  claims,
  onFocusClaim,
}: AnswerCardProps) {
  if (isGenerating) {
    return (
      <article className="panel p-5 animate-fade-up">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-meta">AI answer</span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 text-[11px] font-medium text-accent">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              Generating answer…
            </span>
          </div>
        </div>
        <p className="mt-3 text-sm italic text-ink-muted">
          Generating initial AI answer before verification begins…
        </p>
        {answerModel ? (
          <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
            <div className="flex gap-1.5">
              <dt>Target model</dt>
              <dd className="font-medium text-ink-secondary">
                {answerModel.name} · {answerModel.provider}
              </dd>
            </div>
          </dl>
        ) : null}
      </article>
    )
  }

  if (!answer) return null

  const showClaims = Boolean(claims && claims.length > 0)

  return (
    <article className="panel p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-meta uppercase tracking-wider text-ink-muted text-[11px] font-semibold">Answer Model</span>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-ink">
              {answerModel ? answerModel.name : (formatModelDisplay(model) ?? model ?? 'Answer Model')}
            </h3>
            {answerModel?.provider ? (
              <span className="rounded-full bg-surface border border-line px-2.5 py-0.5 text-xs text-ink-secondary font-medium">
                {answerModel.provider}
              </span>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-reliable-soft px-2.5 py-0.5 text-[11px] font-medium text-reliable">
            <Check className="h-3 w-3" strokeWidth={2.5} />
            Generated
          </span>
          <CopyButton value={answer} />
        </div>
      </div>

      <div className="mt-4">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Generated Answer</span>
        <p className="mt-1.5 text-[15px] leading-7 text-ink">{answer}</p>
      </div>

      <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
        {responseTimeMs != null ? (
          <div className="flex gap-1.5">
            <dt>Response time</dt>
            <dd className="text-ink-secondary">{formatResponseTime(responseTimeMs)}</dd>
          </div>
        ) : null}
      </dl>

      {showClaims ? (
        <div className="mt-5 border-t border-line pt-4">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Checked claims
          </p>
          <ul className="mt-3 space-y-2">
            {claims!.map((claim) => {
              const badge = claimBadge(claim.verdict)
              return (
                <li key={claim.id}>
                  <button
                    type="button"
                    onClick={() => onFocusClaim?.(claim.id)}
                    className="flex w-full items-start gap-3 rounded-[var(--radius-sm)] border border-line bg-canvas px-3 py-2.5 text-left hover:border-line-strong"
                  >
                    <p className="min-w-0 flex-1 text-[13px] leading-5 text-ink">{claim.text}</p>
                    <span
                      className={classNames(
                        'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide',
                        badge.className,
                      )}
                    >
                      {badge.label}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
    </article>
  )
}
