import { useMemo, useState } from 'react'
import { AlertCircle, ChevronDown, Search } from 'lucide-react'
import type { ModelVerifierVerdictRecord } from '../../types'
import { classNames } from '../../lib/format'

export function VerdictBadge({ verdict, status }: { verdict: string; status?: string }) {
  const norm = (verdict || '').toUpperCase().trim()
  const isFailed = status === 'failed' || norm.startsWith('FAILED')
  const isPending = status === 'pending' || norm === 'PENDING'

  if (isPending) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-0.5 text-[11px] font-medium text-ink-muted">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
        Evaluating…
      </span>
    )
  }

  if (isFailed) {
    const isRateLimit = norm.includes('RATE LIMIT') || norm.includes('RATE-LIMIT')
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-red-700 dark:bg-red-950/60 dark:text-red-300">
        <AlertCircle className="h-3 w-3 shrink-0" />
        {isRateLimit ? 'FAILED — Rate limit exceeded' : 'FAILED'}
      </span>
    )
  }

  if (norm === 'YES') {
    return (
      <span className="inline-flex items-center rounded-full bg-reliable-soft px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-reliable">
        YES
      </span>
    )
  }

  if (norm === 'NO') {
    return (
      <span className="inline-flex items-center rounded-full bg-surface-muted px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-ink-secondary">
        NO
      </span>
    )
  }

  if (norm === 'NOT SURE' || norm === 'NOT_SURE') {
    return (
      <span className="inline-flex items-center rounded-full bg-uncertain-soft px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-uncertain">
        NOT SURE
      </span>
    )
  }

  return (
    <span className="inline-flex items-center rounded-full bg-surface-muted px-2.5 py-0.5 text-[11px] font-semibold text-ink-secondary">
      {verdict}
    </span>
  )
}

export interface CollapsibleModelVerdictsProps {
  verdicts?: ModelVerifierVerdictRecord[]
  mutationId?: string
  pending?: boolean
}

export function CollapsibleModelVerdicts({
  verdicts = [],
  mutationId = 'default',
  pending = false,
}: CollapsibleModelVerdictsProps) {
  // Collapsed by default on page load
  const [isSectionExpanded, setIsSectionExpanded] = useState(false)
  // At most one model explanation expanded per mutation at a time
  const [expandedModelId, setExpandedModelId] = useState<string | null>(null)
  // Search query for large model pools
  const [filterQuery, setFilterQuery] = useState('')

  // Derive model count and verdict counts dynamically from the actual results
  const verdictCounts = useMemo(() => {
    let yes = 0
    let no = 0
    let notSure = 0
    let failed = 0
    let pendingCount = 0

    for (const v of verdicts) {
      const norm = (v.verdict || '').toUpperCase().trim()
      const isFailed = v.status === 'failed' || norm.startsWith('FAILED') || Boolean(v.error)
      if (isFailed) {
        failed += 1
      } else if (norm === 'YES') {
        yes += 1
      } else if (norm === 'NO') {
        no += 1
      } else if (norm === 'NOT SURE' || norm === 'NOT_SURE') {
        notSure += 1
      } else if (v.status === 'pending' || norm === 'PENDING') {
        pendingCount += 1
      }
    }

    return { yes, no, notSure, failed, pending: pendingCount }
  }, [verdicts])

  const totalModels = verdicts.length
  const verifiedCount = totalModels - verdictCounts.pending
  const compactSummaryText =
    verdictCounts.pending > 0 && verifiedCount < totalModels
      ? `${verifiedCount}/${totalModels} models verified`
      : `${totalModels} model${totalModels === 1 ? '' : 's'} verified`

  const verdictSummaryString = `YES: ${verdictCounts.yes} · NO: ${verdictCounts.no} · NOT SURE: ${verdictCounts.notSure} · FAILED: ${verdictCounts.failed}`

  // Filtered models for large lists
  const filteredVerdicts = useMemo(() => {
    if (!filterQuery.trim()) return verdicts
    const q = filterQuery.toLowerCase()
    return verdicts.filter(
      (v) =>
        (v.modelName && v.modelName.toLowerCase().includes(q)) ||
        (v.provider && v.provider.toLowerCase().includes(q)) ||
        (v.model && v.model.toLowerCase().includes(q)) ||
        (v.modelId && v.modelId.toLowerCase().includes(q)) ||
        (v.verdict && v.verdict.toLowerCase().includes(q)),
    )
  }, [verdicts, filterQuery])

  const toggleModel = (modelId: string) => {
    setExpandedModelId((curr) => (curr === modelId ? null : modelId))
  }

  if (totalModels === 0) {
    return (
      <div className="rounded-lg border border-line bg-surface p-3 text-xs text-ink-muted">
        {pending ? 'Verifying mutation across all models…' : 'No verifier records available.'}
      </div>
    )
  }

  const dropdownControlId = `verdicts-dropdown-${mutationId}`
  const contentSectionId = `verdicts-content-${mutationId}`

  return (
    <div className="rounded-lg border border-line bg-surface/70 shadow-xs transition-colors overflow-hidden">
      {/* 1. Collapsible Trigger Bar */}
      <button
        id={dropdownControlId}
        type="button"
        onClick={() => setIsSectionExpanded((prev) => !prev)}
        aria-expanded={isSectionExpanded}
        aria-controls={contentSectionId}
        className={classNames(
          'w-full flex flex-wrap items-center justify-between gap-2.5 p-3 sm:px-3.5 text-left transition-colors',
          'hover:bg-surface-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
          isSectionExpanded ? 'bg-surface-muted/20 border-b border-line/60' : '',
        )}
      >
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 min-w-0">
          <div className="flex items-center gap-1.5">
            <ChevronDown
              className={classNames(
                'h-4 w-4 text-ink-muted transition-transform duration-200 shrink-0',
                isSectionExpanded ? 'rotate-180 text-accent' : '',
              )}
            />
            <span className="text-xs font-bold uppercase tracking-wider text-ink">
              AI Verdicts
            </span>
          </div>

          <span className="text-xs text-ink-muted font-medium">
            · {compactSummaryText}
          </span>

          {/* Dynamic verdict counts summary */}
          <span className="inline-flex items-center rounded-full bg-surface-muted/80 px-2.5 py-0.5 text-[11px] font-mono font-medium text-ink-secondary border border-line/40">
            {verdictSummaryString}
          </span>
        </div>

        <span className="text-[11px] font-semibold text-accent hover:underline shrink-0">
          {isSectionExpanded ? 'Hide verifiers' : 'Show verifiers'}
        </span>
      </button>

      {/* 2. Expanded Verifier Models Section */}
      {isSectionExpanded && (
        <div id={contentSectionId} className="p-3 sm:p-3.5 space-y-3 animate-fade-in">
          {/* Optional search/filter if large model pool (> 6 models) */}
          {totalModels > 6 && (
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-ink-muted pointer-events-none" />
              <input
                type="text"
                placeholder={`Filter ${totalModels} models by name, provider, or verdict…`}
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-line bg-surface text-ink placeholder:text-ink-muted focus:outline-none focus:border-accent"
              />
            </div>
          )}

          {/* List/Grid of models - scrollable container if list is large */}
          <div
            className={classNames(
              'grid gap-2',
              totalModels > 1 ? 'sm:grid-cols-2' : 'grid-cols-1',
              totalModels > 6 ? 'max-h-[500px] overflow-y-auto pr-1' : '',
            )}
          >
            {filteredVerdicts.map((v) => {
              const isEntryExpanded = expandedModelId === v.modelId
              const norm = (v.verdict || '').toUpperCase().trim()
              const isFailed = v.status === 'failed' || norm.startsWith('FAILED') || Boolean(v.error)

              return (
                <div
                  key={v.modelId}
                  className={classNames(
                    'rounded-lg border transition-all duration-150',
                    isEntryExpanded
                      ? 'border-accent/60 bg-surface shadow-xs ring-1 ring-accent/20'
                      : 'border-line bg-surface hover:border-line-strong hover:bg-surface-muted/20',
                  )}
                >
                  {/* Clickable Model Card Header */}
                  <button
                    type="button"
                    onClick={() => toggleModel(v.modelId)}
                    aria-expanded={isEntryExpanded}
                    aria-controls={`model-details-${mutationId}-${v.modelId}`}
                    className="w-full flex items-start justify-between gap-2.5 p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-lg"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-semibold text-xs text-ink truncate">
                          {v.modelName || v.model || v.modelId}
                        </span>
                        <span className="text-[10px] text-ink-muted truncate">
                          · {v.provider}
                        </span>
                      </div>
                      <span className="text-[10px] text-ink-muted mt-0.5 block">
                        {isEntryExpanded ? 'Click to collapse explanation' : 'Click to expand explanation'}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <VerdictBadge verdict={v.verdict} status={v.status} />
                      <ChevronDown
                        className={classNames(
                          'h-3.5 w-3.5 text-ink-muted transition-transform duration-200 shrink-0',
                          isEntryExpanded ? 'rotate-180 text-accent' : '',
                        )}
                      />
                    </div>
                  </button>

                  {/* Inline Expanded Explanation */}
                  {isEntryExpanded && (
                    <div
                      id={`model-details-${mutationId}-${v.modelId}`}
                      className="border-t border-line/50 px-3 py-3 space-y-2.5 bg-surface-muted/30 rounded-b-lg text-xs"
                    >
                      {/* Distinguish Verdict from Rationale */}
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                          Independent Judgment
                        </span>
                        <VerdictBadge verdict={v.verdict} status={v.status} />
                      </div>

                      {/* Explanation Block */}
                      {isFailed ? (
                        <div className="rounded-md border border-red-200 dark:border-red-900/40 bg-red-50/70 dark:bg-red-950/30 p-2.5 text-xs text-red-700 dark:text-red-300 space-y-1">
                          <div className="flex items-center gap-1 font-bold text-[10px] uppercase tracking-wider">
                            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                            <span>API Error Explanation</span>
                          </div>
                          <p className="leading-relaxed font-mono text-[11px]">
                            {v.error || 'The model API call failed without a specific error explanation.'}
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-ink-muted block">
                            Model Rationale
                          </span>
                          {v.rationale && v.rationale.trim().length > 0 ? (
                            <p className="leading-relaxed text-ink text-xs italic bg-surface p-2.5 rounded-md border border-line/60">
                              &ldquo;{v.rationale.trim()}&rdquo;
                            </p>
                          ) : (
                            <p className="text-ink-muted text-xs italic bg-surface p-2.5 rounded-md border border-line/60">
                              No explanation was returned by this model.
                            </p>
                          )}
                        </div>
                      )}

                      {/* Model & Provider Identifiers and Score Contribution */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[10px] text-ink-muted border-t border-line/40">
                        <div className="flex flex-wrap items-center gap-2">
                          <span>Provider: <strong className="text-ink font-medium">{v.provider}</strong></span>
                          {v.model && (
                            <span>· Model ID: <code className="font-mono text-[10px] bg-surface px-1 py-0.5 rounded border border-line/50 text-ink">{v.model}</code></span>
                          )}
                        </div>

                        <div>
                          {v.status === 'completed' && v.contribution != null ? (
                            <span>Score contribution: <strong className="font-mono text-ink tabular-nums font-semibold">{v.contribution}</strong></span>
                          ) : isFailed ? (
                            <span className="text-ink-muted">Score contribution: <em className="text-[10px]">Excluded (null)</em></span>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {filteredVerdicts.length === 0 && filterQuery && (
            <p className="text-xs text-ink-muted text-center py-3">
              No models matched filter &ldquo;{filterQuery}&rdquo;.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
