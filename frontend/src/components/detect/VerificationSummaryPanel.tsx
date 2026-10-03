import { useState } from 'react'
import { AlertTriangle, Check, ExternalLink, X } from 'lucide-react'
import type { VerificationSummary, WebClaimRecord } from '../../types'
import { EvidenceVerdict } from '../../types'
import { classNames } from '../../lib/format'

interface VerificationSummaryPanelProps {
  summary: VerificationSummary | null | undefined
  onFocusClaim?: (claimId: string) => void
}

function verdictLabel(verdict: EvidenceVerdict | string): string {
  if (verdict === EvidenceVerdict.Supported) return 'Supported'
  if (verdict === EvidenceVerdict.Contradicted) return 'Contradicted'
  return 'Insufficient evidence'
}

function verdictTone(verdict: EvidenceVerdict | string): string {
  if (verdict === EvidenceVerdict.Supported) return 'text-reliable bg-reliable-soft'
  if (verdict === EvidenceVerdict.Contradicted) return 'text-hallucinated bg-hallucinated-soft'
  return 'text-uncertain bg-uncertain-soft'
}

function AttentionClaim({
  claim,
  onFocusClaim,
}: {
  claim: WebClaimRecord
  onFocusClaim?: (claimId: string) => void
}) {
  const [open, setOpen] = useState(claim.verdict === EvidenceVerdict.Contradicted)
  return (
    <article className="border-b border-line last:border-b-0">
      <button
        type="button"
        onClick={() => {
          setOpen((value) => !value)
          onFocusClaim?.(claim.id)
        }}
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <p className="text-[13px] leading-5 text-ink">{claim.text}</p>
        </div>
        <span
          className={classNames(
            'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide',
            verdictTone(claim.verdict),
          )}
        >
          {verdictLabel(claim.verdict)}
        </span>
      </button>
      {open ? (
        <div className="space-y-3 bg-canvas px-4 py-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Why</p>
            <p className="mt-1 text-sm leading-6 text-ink-secondary">
              {claim.reason ||
                (claim.verdict === EvidenceVerdict.InsufficientEvidence
                  ? 'The retrieved sources were not sufficient to verify this claim.'
                  : 'No reason provided.')}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Sources
            </p>
            {claim.sources.length === 0 ? (
              <p className="mt-1 text-sm text-ink-muted">No sources retrieved for this claim.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {claim.sources.map((source) => (
                  <li
                    key={`${claim.id}:${source.url}`}
                    className="rounded-[var(--radius-sm)] border border-line bg-surface px-3 py-2.5"
                  >
                    <p className="text-sm font-medium text-ink">{source.title}</p>
                    <p className="mt-0.5 text-xs text-ink-muted">{source.domain || source.url}</p>
                    {source.snippet ? (
                      <p className="mt-1.5 text-xs leading-5 text-ink-secondary">{source.snippet}</p>
                    ) : null}
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                    >
                      Open source
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </article>
  )
}

function overallTone(verdict: string | undefined): {
  border: string
  badge: string
} {
  const raw = (verdict || '').toUpperCase()
  if (raw === 'LIKELY_RELIABLE') {
    return {
      border: 'border-l-reliable',
      badge: 'bg-reliable-soft text-reliable border border-reliable/30',
    }
  }
  if (raw === 'POTENTIALLY_HALLUCINATED') {
    return {
      border: 'border-l-hallucinated',
      badge: 'bg-hallucinated-soft text-hallucinated border border-hallucinated/30',
    }
  }
  return {
    border: 'border-l-uncertain',
    badge: 'bg-uncertain-soft text-uncertain border border-uncertain/30',
  }
}

export function VerificationSummaryPanel({
  summary,
  onFocusClaim,
}: VerificationSummaryPanelProps) {
  if (!summary || !summary.ready) return null

  const tone = overallTone(summary.overallVerdict ?? undefined)
  const isReliable = (summary.overallVerdict || '').toUpperCase() === 'LIKELY_RELIABLE'
  const isHallucinated = (summary.overallVerdict || '').toUpperCase() === 'POTENTIALLY_HALLUCINATED'

  // Dynamic short status for MetaQA branch card
  const metaqaShortStatus =
    summary.metaqaSignal === 'CONSISTENT'
      ? 'No consistency violations'
      : summary.metaqaSignal === 'INCONSISTENT'
        ? 'Consistency violations detected'
        : summary.metaqaLabel || 'Analysis unavailable'

  // Dynamic short status for Web Evidence branch card
  const webShortStatus =
    summary.webContradicted > 0
      ? `${summary.webContradicted} claim${summary.webContradicted === 1 ? '' : 's'} contradicted`
      : summary.webConsistencyVerdictLabel
        ? summary.webConsistencyVerdictLabel.replace(/ by evidence$/i, '')
        : summary.webLabel || 'Checked'

  const webScorePercent =
    summary.webConsistencyScore != null
      ? `${Math.round(summary.webConsistencyScore * 100)}%`
      : '—'

  return (
    <section className="space-y-4">
      {/* COMPACT FINAL RESULT CARD */}
      <div className={classNames('panel p-4 sm:p-5 space-y-3.5 border-l-4 shadow-sm', tone.border)}>
        {/* Header: Title & short explanation on left; Verdict & combined risk on right */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div className="min-w-0">
            <h2 className="text-[11px] font-bold uppercase tracking-wider text-ink-muted">
              VeriFact Result
            </h2>
            {summary.overallExplanation ? (
              <p className="mt-0.5 text-xs text-ink-secondary leading-snug">
                {summary.overallExplanation}
              </p>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center sm:justify-end gap-2.5 shrink-0">
            <span
              className={classNames(
                'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs sm:text-sm font-bold uppercase tracking-wider',
                tone.badge,
              )}
            >
              {isReliable ? (
                <Check className="h-3.5 w-3.5 stroke-[2.5]" aria-hidden="true" />
              ) : isHallucinated ? (
                <X className="h-3.5 w-3.5 stroke-[2.5]" aria-hidden="true" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 stroke-[2.5]" aria-hidden="true" />
              )}
              {summary.overallLabel || summary.overallVerdict?.replace(/_/g, ' ') || 'Assessment Ready'}
            </span>

            {summary.combinedRiskScore != null ? (
              <span className="text-xs text-ink-muted">
                Combined Risk{' '}
                <span className="font-mono font-bold text-ink">
                  {summary.combinedRiskScore.toFixed(2)}
                </span>
              </span>
            ) : null}
          </div>
        </div>

        {/* 3 Compact Equal-Width Score Columns in One Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Column 1: MetaQA */}
          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-canvas/60 px-3.5 py-2.5 space-y-0.5">
            <p className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">MetaQA</p>
            <p className="font-mono text-xl sm:text-2xl font-bold tracking-tight text-ink tabular-nums leading-tight">
              {summary.metaqaScore != null ? summary.metaqaScore.toFixed(2) : '—'}
            </p>
            <p className="text-xs text-ink-secondary truncate">{metaqaShortStatus}</p>
          </div>

          {/* Column 2: Web Evidence */}
          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-canvas/60 px-3.5 py-2.5 space-y-0.5">
            <p className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">Web Evidence</p>
            <p className="font-mono text-xl sm:text-2xl font-bold tracking-tight text-ink tabular-nums leading-tight">
              {webScorePercent}
            </p>
            <p className="text-xs text-ink-secondary truncate">{webShortStatus}</p>
          </div>

          {/* Column 3: Combined Risk */}
          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-canvas/60 px-3.5 py-2.5 space-y-0.5">
            <p className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">Combined Risk</p>
            <p className="font-mono text-xl sm:text-2xl font-bold tracking-tight text-ink tabular-nums leading-tight">
              {summary.combinedRiskScore != null ? summary.combinedRiskScore.toFixed(2) : '—'}
            </p>
            <p className="text-xs text-ink-secondary truncate">Hallucination risk</p>
          </div>
        </div>

        {/* Small Muted Disclaimer */}
        <p className="text-[11px] leading-relaxed text-ink-muted pt-0.5">
          Combined risk is an application-level VeriFact signal based on both verification branches.
          It is not a calibrated probability of hallucination.
        </p>
      </div>

      {/* Contradicted Claims Drawer (if any exist) */}
      {summary.attentionClaims.length > 0 ? (
        <div className="panel overflow-hidden">
          <div className="border-b border-line px-4 py-3">
            <h3 className="text-sm font-semibold text-ink">Claims with contradictions</h3>
            <p className="mt-0.5 text-xs text-ink-muted">
              Only contradicted claims are listed here. Insufficient evidence is not treated as
              hallucination.
            </p>
          </div>
          <div>
            {summary.attentionClaims.map((claim) => (
              <AttentionClaim key={claim.id} claim={claim} onFocusClaim={onFocusClaim} />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}

