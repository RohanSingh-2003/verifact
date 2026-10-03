import { useState } from 'react'
import { Check, ChevronDown, Circle, ExternalLink, X } from 'lucide-react'
import type { WebClaimRecord, WebEvidenceResult, WebSourceRecord } from '../../types'
import { EvidenceVerdict, WebEvidenceStatus } from '../../types'
import { classNames } from '../../lib/format'
import { AnalysisProgress, type ProgressStepItem, type StepState } from './AnalysisProgress'

interface WebEvidencePanelProps {
  evidence: WebEvidenceResult | null | undefined
}

function verdictLabel(verdict: EvidenceVerdict): string {
  if (verdict === EvidenceVerdict.Supported) return 'Supported'
  if (verdict === EvidenceVerdict.Contradicted) return 'Contradicted'
  return 'Insufficient evidence'
}

function verdictTone(verdict: EvidenceVerdict): string {
  if (verdict === EvidenceVerdict.Supported) return 'text-reliable bg-reliable-soft'
  if (verdict === EvidenceVerdict.Contradicted) return 'text-hallucinated bg-hallucinated-soft'
  return 'text-uncertain bg-uncertain-soft'
}

function sourceTypeLabel(value: string | undefined): string {
  const raw = (value || 'GENERAL').toUpperCase()
  if (raw === 'OFFICIAL' || raw === 'PRIMARY' || raw === 'PRIMARY_OFFICIAL') return 'Official / Primary'
  if (raw === 'GOVERNMENT') return 'Government / Official'
  if (raw === 'ACADEMIC') return 'Academic'
  if (raw === 'NEWS' || raw === 'REPUTABLE_NEWS') return 'Reputable News'
  if (raw === 'REFERENCE' || raw === 'SECONDARY') return 'Reference'
  if (raw === 'FACT_CHECK') return 'Fact check'
  if (raw === 'LOW_PRIORITY') return 'Low priority'
  return 'General Web'
}

function isAuthoritativeTier(value: string | undefined): boolean {
  const raw = (value || 'GENERAL').toUpperCase()
  return (
    raw === 'PRIMARY_OFFICIAL' ||
    raw === 'OFFICIAL' ||
    raw === 'PRIMARY' ||
    raw === 'GOVERNMENT' ||
    raw === 'ACADEMIC'
  )
}

function getWebEvidenceSteps(evidence: WebEvidenceResult | null | undefined): ProgressStepItem[] {
  if (!evidence || evidence.status === WebEvidenceStatus.Pending) {
    return [
      { id: 'type', label: 'Question type identified', state: 'pending' },
      { id: 'claims', label: 'Claims identified', state: 'pending' },
      { id: 'search', label: 'Searching recommended sources', state: 'pending' },
      { id: 'verify', label: 'Verifying evidence', state: 'pending' },
      { id: 'complete', label: 'Evidence analysis complete', state: 'pending' },
    ]
  }

  const { status, questionTypeLabel, claims } = evidence
  const isCompleted = status === WebEvidenceStatus.Completed
  const isFailed = status === WebEvidenceStatus.Failed || status === WebEvidenceStatus.Unavailable

  // 1. Question type identified
  let s1: StepState = 'pending'
  if (
    isCompleted ||
    status === WebEvidenceStatus.ExtractingClaims ||
    status === WebEvidenceStatus.SearchingWeb ||
    status === WebEvidenceStatus.VerifyingEvidence ||
    Boolean(questionTypeLabel)
  ) {
    s1 = 'done'
  } else if (status === WebEvidenceStatus.ClassifyingQuestion) {
    s1 = 'active'
  } else if (isFailed) {
    s1 = questionTypeLabel ? 'done' : 'failed'
  }

  // 2. Claims identified
  let s2: StepState = 'pending'
  if (
    isCompleted ||
    status === WebEvidenceStatus.SearchingWeb ||
    status === WebEvidenceStatus.VerifyingEvidence ||
    claims.length > 0
  ) {
    s2 = 'done'
  } else if (status === WebEvidenceStatus.ExtractingClaims) {
    s2 = 'active'
  } else if (isFailed && s1 === 'done') {
    s2 = claims.length > 0 ? 'done' : 'failed'
  }

  // 3. Searching recommended sources
  let s3: StepState = 'pending'
  if (isCompleted || status === WebEvidenceStatus.VerifyingEvidence) {
    s3 = 'done'
  } else if (status === WebEvidenceStatus.SearchingWeb) {
    s3 = 'active'
  } else if (isFailed && s2 === 'done') {
    s3 = 'failed'
  }

  // 4. Verifying evidence
  let s4: StepState = 'pending'
  if (isCompleted) {
    s4 = 'done'
  } else if (status === WebEvidenceStatus.VerifyingEvidence) {
    s4 = 'active'
  } else if (isFailed && s3 === 'done') {
    s4 = 'failed'
  }

  // 5. Evidence analysis complete
  let s5: StepState = 'pending'
  if (isCompleted) {
    s5 = 'done'
  }

  const typeLabel =
    s1 === 'done' && questionTypeLabel
      ? `Question type identified — ${questionTypeLabel}`
      : 'Question type identified'
  const claimsLabel =
    s2 === 'done' && claims.length > 0
      ? `Claims identified (${claims.length} claim${claims.length === 1 ? '' : 's'})`
      : 'Claims identified'

  return [
    { id: 'type', label: typeLabel, state: s1 },
    { id: 'claims', label: claimsLabel, state: s2 },
    { id: 'search', label: 'Searching recommended sources', state: s3 },
    { id: 'verify', label: 'Verifying evidence', state: s4 },
    { id: 'complete', label: 'Evidence analysis complete', state: s5 },
  ]
}

function getWebStatus(
  status: WebEvidenceStatus | undefined,
): 'running' | 'completed' | 'failed' | 'unavailable' | 'pending' {
  if (!status || status === WebEvidenceStatus.Pending) return 'pending'
  if (status === WebEvidenceStatus.Completed) return 'completed'
  if (status === WebEvidenceStatus.Unavailable) return 'unavailable'
  if (status === WebEvidenceStatus.Failed) return 'failed'
  return 'running'
}

const INSUFFICIENT_EVIDENCE_TEXT =
  'The retrieved source does not provide enough relevant information to verify this claim.'

function getCleanSourceEvidence(source: WebSourceRecord, claimVerdict?: EvidenceVerdict): string {
  if (source.evidenceSummary && source.evidenceSummary.trim().length > 0) {
    return source.evidenceSummary.trim()
  }

  if (claimVerdict === EvidenceVerdict.InsufficientEvidence && !source.snippet?.trim()) {
    return INSUFFICIENT_EVIDENCE_TEXT
  }

  const raw = source.snippet || ''
  if (!raw.trim()) {
    return INSUFFICIENT_EVIDENCE_TEXT
  }

  // Fallback cleaning for older runs or unsummarized sources
  const cleaned = raw
    .replace(/^#+\s+.*$/gm, '')
    .replace(/History Top Questions/gi, '')
    .replace(/Top Questions\b/gi, '')
    .replace(/Frequently Asked Questions\b/gi, '')
    .replace(/\bFAQ\b/gi, '')
    .replace(/Quick Facts?:?/gi, '')
    .replace(/Table of Contents:?/gi, '')
    .replace(/Navigation menu:?/gi, '')
    .replace(/\[\s*\.\.\.\s*\]/g, '')
    .replace(/\[\s*edit\s*\]/gi, '')
    .replace(/\[\d+\]/g, '')
    .replace(/(?:^|\s)(?:What|Who|Where|When|Why|How|Which|Did|Was|Is|Are)\s+[^?]{5,100}\?\s*/gi, '')
    .replace(/\s*[-–—|•]\s*[\w\s,&/]+(?:\.{2,})?$/i, '')
    .replace(/(?:^|\s)[#*•>-]+\s+/g, ' ')
    .replace(/\s*\.{3,}\s*/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()

  if (!cleaned || cleaned.split(/\s+/).length < 4) {
    return INSUFFICIENT_EVIDENCE_TEXT
  }

  const sentences = cleaned
    .split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
    .map((s) => s.trim())
    .filter((s) => s.split(/\s+/).length >= 4)

  if (sentences.length === 0) {
    return INSUFFICIENT_EVIDENCE_TEXT
  }

  let result = sentences.slice(0, 2).join(' ').trim()
  if (!/[.!?]$/.test(result)) {
    result += '.'
  }
  return result
}

function getClaimEvidenceSummary(claim: WebClaimRecord): string {
  if (claim.verdict === EvidenceVerdict.InsufficientEvidence || claim.sources.length === 0) {
    return 'The retrieved source does not provide enough relevant information to verify this claim.'
  }

  for (const src of claim.sources) {
    const summary = getCleanSourceEvidence(src, claim.verdict)
    if (summary && summary !== INSUFFICIENT_EVIDENCE_TEXT) {
      return summary
    }
  }

  return 'The retrieved source does not provide enough relevant information to verify this claim.'
}

function SourceCard({
  source,
  claimVerdict,
}: {
  source: WebSourceRecord
  claimVerdict: EvidenceVerdict
}) {
  const isAuth = isAuthoritativeTier(source.sourceType)
  const isLow = (source.sourceType || '').toUpperCase() === 'LOW_PRIORITY'
  const evidenceSummary = getCleanSourceEvidence(source, claimVerdict)

  return (
    <li className="rounded-[var(--radius-sm)] border border-line bg-surface p-4 sm:p-5 space-y-3">
      {/* 1. Header: Source domain & priority badges */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold tracking-wider uppercase text-ink-muted">Source</span>
          <span className="text-xs font-semibold text-ink">{source.domain || 'Web source'}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {isAuth ? (
            <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-medium text-accent">
              Preferred authoritative source
            </span>
          ) : null}
          <span
            className={classNames(
              'rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide',
              isAuth
                ? 'bg-reliable-soft text-reliable'
                : isLow
                  ? 'bg-uncertain-soft text-uncertain'
                  : 'bg-canvas text-ink-muted',
            )}
          >
            {sourceTypeLabel(source.sourceType)}
          </span>
        </div>
      </div>

      {/* 2. Source Title */}
      <p className="text-sm font-medium text-ink leading-snug">{source.title}</p>

      {/* 3. Evidence: Clean, 1–3 sentence claim-relevant summary (never raw snippets) */}
      <div className="rounded-[var(--radius-sm)] border border-line/60 bg-canvas/60 p-3 sm:p-3.5 space-y-1">
        <p className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">Evidence</p>
        <p className="text-xs sm:text-[13px] leading-relaxed text-ink-secondary [overflow-wrap:anywhere] break-words">
          {evidenceSummary}
        </p>
      </div>

      {/* 4. Divider & Footer: Source URL + Open source ↗ */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-2.5 text-xs">
        <span
          className="max-w-[260px] sm:max-w-md truncate text-[11px] text-ink-muted font-mono"
          title={source.url}
        >
          {source.url}
        </span>
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-1 font-medium text-accent hover:underline shrink-0"
        >
          <span>Open source</span>
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      </div>
    </li>
  )
}

function ClaimRow({ claim }: { claim: WebClaimRecord }) {
  const [open, setOpen] = useState(false)
  const claimEvidence = getClaimEvidenceSummary(claim)

  return (
    <article id={`web-claim-${claim.id}`} className="border-b border-line last:border-b-0 scroll-mt-24">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors hover:bg-canvas/50"
        aria-expanded={open}
      >
        <div className="min-w-0 flex-1">
          <p className="text-[13px] leading-5 text-ink">{claim.text}</p>
          {claim.usedFallback ? (
            <span className="mt-1 inline-block rounded-full bg-canvas px-2 py-0.5 text-[10px] font-medium text-ink-muted">
              Fallback search used
            </span>
          ) : null}
        </div>
        <span
          className={classNames(
            'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide',
            verdictTone(claim.verdict),
          )}
        >
          {verdictLabel(claim.verdict)}
        </span>
        <ChevronDown
          className={classNames(
            'mt-0.5 h-4 w-4 shrink-0 text-ink-muted transition-transform',
            open ? 'rotate-180' : '',
          )}
        />
      </button>
      {open ? (
        <div className="space-y-4 bg-canvas px-4 py-4 sm:px-5">
          {/* Claim */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Claim</p>
            <p className="mt-1 text-sm leading-6 text-ink">{claim.text}</p>
          </div>

          {/* Verdict */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Verdict</p>
            <span
              className={classNames(
                'mt-1 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide',
                verdictTone(claim.verdict),
              )}
            >
              {verdictLabel(claim.verdict)}
            </span>
          </div>

          {/* Evidence Summary */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Evidence</p>
            <p className="mt-1 text-sm leading-relaxed text-ink [overflow-wrap:anywhere] break-words">
              {claimEvidence}
            </p>
          </div>

          {/* Why */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Why</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-secondary [overflow-wrap:anywhere] break-words">
              {claim.reason || 'No reason provided.'}
            </p>
          </div>

          {/* Sources */}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Sources</p>
            {claim.sources.length === 0 ? (
              <p className="mt-1 text-sm text-ink-muted">No sources retrieved for this claim.</p>
            ) : (
              <ul className="mt-2.5 space-y-3">
                {claim.sources.map((source) => (
                  <SourceCard
                    key={`${claim.id}:${source.url}`}
                    source={source}
                    claimVerdict={claim.verdict}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </article>
  )
}

export function WebEvidencePanel({ evidence }: WebEvidencePanelProps) {
  const steps = getWebEvidenceSteps(evidence)
  const status = getWebStatus(evidence?.status)
  const isFailed = evidence?.status === WebEvidenceStatus.Unavailable || evidence?.status === WebEvidenceStatus.Failed
  const errorReason = isFailed ? (evidence?.error?.trim() || 'External evidence could not be retrieved.') : null
  const showClaims = Boolean(evidence && evidence.claims.length > 0)
  const completed = evidence?.status === WebEvidenceStatus.Completed
  const strategyText = evidence?.sourceStrategyLabels.filter(Boolean).join(' · ')

  return (
    <div className="space-y-6">
      <AnalysisProgress
        title="Web Evidence Analysis"
        description="VeriFact checks important claims against retrieved web evidence from relevant authoritative sources."
        status={status}
        steps={steps}
        errorReason={errorReason}
      />

      {evidence && (completed || showClaims || isFailed) ? (
        <div className="panel overflow-hidden">
          {(completed || evidence.questionTypeLabel) && evidence.questionTypeLabel ? (
            <div className="space-y-2 border-b border-line px-4 py-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Question type
                </p>
                <p className="mt-0.5 text-sm font-medium text-ink">{evidence.questionTypeLabel}</p>
              </div>
              {strategyText ? (
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                    Source strategy
                  </p>
                  <p className="mt-0.5 text-sm text-ink-secondary">{strategyText}</p>
                </div>
              ) : null}
            </div>
          ) : null}

          {completed && showClaims ? (
            <div className="border-b border-line px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Web Evidence Consistency Score
              </p>
              {evidence.consistencyScore != null ? (
                <p className="mt-1 text-2xl font-semibold tracking-tight text-ink">
                  {evidence.consistencyScore.toFixed(2)}
                  <span className="ml-1 text-sm font-normal text-ink-muted">/ 1.00</span>
                </p>
              ) : (
                <p className="mt-1 text-lg font-medium text-ink-muted">—</p>
              )}
              {evidence.consistencyVerdictLabel ? (
                <p className="mt-1 text-sm font-medium text-ink">{evidence.consistencyVerdictLabel}</p>
              ) : null}
              <p className="mt-2 text-xs leading-5 text-ink-muted">
                Mean claim contribution (SUPPORTED=1.0, INSUFFICIENT=0.5, CONTRADICTED=0.0). Insufficient
                evidence is not treated as hallucination.
              </p>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <span className="inline-flex items-center gap-1 text-reliable">
                  <Check className="h-3 w-3" aria-hidden="true" />
                  Supported: {evidence.supportedClaims}
                </span>
                <span className="inline-flex items-center gap-1 text-hallucinated">
                  <X className="h-3 w-3" aria-hidden="true" />
                  Contradicted: {evidence.contradictedClaims}
                </span>
                <span className="inline-flex items-center gap-1 text-uncertain">
                  <Circle className="h-3 w-3" aria-hidden="true" />
                  Insufficient: {evidence.insufficientClaims}
                </span>
              </div>
            </div>
          ) : null}

          {completed && !showClaims ? (
            <p className="px-4 py-4 text-sm leading-6 text-ink-muted">
              {evidence.error?.trim() ||
                'No independently verifiable factual claims were found in the answer.'}
            </p>
          ) : null}

          {showClaims ? (
            <div>
              <div className="border-b border-line bg-canvas/40 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Checked Claims & Evidence Sources
              </div>
              <div>
                {evidence.claims.map((claim) => (
                  <ClaimRow key={claim.id} claim={claim} />
                ))}
              </div>
            </div>
          ) : null}

          {isFailed && !showClaims ? (
            <p className="px-4 py-4 text-sm leading-6 text-ink-muted">
              {evidence.error?.trim() || 'Web evidence is not available for this run.'} This does not
              mean the answer is hallucinated — only that external evidence could not be verified.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
