import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { MutationRecord } from '../../types'
import {
  classNames,
  formatScore,
  mutationExpectationLabel,
  mutationInterpretation,
  mutationKindLabel,
  mutationMeaningLabel,
  verifierLabel,
} from '../../lib/format'
import { CollapsibleModelVerdicts } from './CollapsibleModelVerdicts'

function ExpectedBadge({ expected }: { expected: string }) {
  const norm = expected.toUpperCase().trim()
  const isYes = norm === 'YES'
  const isNo = norm === 'NO'

  return (
    <div className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-canvas px-2.5 py-0.5 text-xs shadow-xs">
      <span className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
        Expected:
      </span>
      <span
        className={classNames(
          'font-bold',
          isYes ? 'text-reliable' : isNo ? 'text-ink' : 'text-uncertain',
        )}
      >
        {norm}
      </span>
    </div>
  )
}



interface MutationRowProps {
  mutation: MutationRecord
  index?: number
}

export function MutationRow({ mutation, index }: MutationRowProps) {
  const [showMeta, setShowMeta] = useState(false)
  const failed =
    Boolean(mutation.parseFailed) ||
    (!mutation.verified && mutation.score === null && Boolean(mutation.reasoning))
  const pending = !failed && (!mutation.verified || mutation.verifier == null)
  const typeHint = mutationMeaningLabel(mutation.kind)
  const interpretation = mutationInterpretation(
    mutation.kind,
    mutation.verifier,
    mutation.expected,
  )
  const verdicts = mutation.verdicts || []

  return (
    <article className="border-b border-line last:border-b-0 p-4 sm:p-5 space-y-3.5 transition-colors hover:bg-surface-muted/15">
      {/* 1. Header Row: Mutation #, Type, Expected MetaQA Verdict, Score Contribution */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {index != null && (
            <span className="font-bold uppercase tracking-wider text-ink text-xs">
              Mutation {index}
            </span>
          )}
          <span
            title={typeHint}
            className={classNames(
              'rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-wide uppercase',
              mutation.kind === 'synonym'
                ? 'bg-accent-soft text-accent'
                : 'bg-surface-muted text-ink-secondary',
            )}
          >
            {mutationKindLabel(mutation.kind)}
          </span>

          {/* Explicit, visually separated MetaQA expected verdict */}
          <ExpectedBadge expected={verifierLabel(mutation.expected)} />
        </div>

        {/* Mutation-level Score Contribution */}
        <div className="flex items-center gap-2 rounded-md bg-surface px-2.5 py-1 border border-line text-xs">
          <span className="text-ink-muted">Score contribution:</span>
          <span className="font-semibold tabular-nums text-ink text-sm">
            {pending || failed ? '—' : formatScore(mutation.score ?? 0)}
          </span>
        </div>
      </div>

      {/* 2. Mutation Statement Text */}
      <blockquote className="rounded-lg border-l-4 border-accent/80 bg-surface-muted/30 px-4 py-3 text-sm font-medium leading-relaxed text-ink">
        &ldquo;{mutation.mutation}&rdquo;
      </blockquote>

      {/* 3. INDEPENDENT MODEL VERDICTS SECTION (Collapsible with Expandable Explanations) */}
      <div className="pt-1">
        <CollapsibleModelVerdicts
          verdicts={verdicts}
          mutationId={mutation.id}
          pending={pending}
        />
      </div>

      {/* 4. Methodology & Claim Context Toggle */}
      <div className="pt-1">
        <button
          type="button"
          onClick={() => setShowMeta((v) => !v)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink transition-colors"
          aria-expanded={showMeta}
        >
          <ChevronDown
            className={classNames(
              'h-3.5 w-3.5 transition-transform duration-200',
              showMeta ? 'rotate-180' : '',
            )}
          />
          <span>{showMeta ? 'Hide claim source & methodology' : 'Show claim source & methodology'}</span>
        </button>

        {showMeta && (
          <div className="mt-3 rounded-lg border border-line bg-canvas/70 p-3.5 space-y-3 text-xs">
            <div>
              <span className="font-bold text-[10px] uppercase tracking-wider text-ink-muted block">
                Original Claim from Candidate Answer:
              </span>
              <p className="mt-1 leading-relaxed text-ink-secondary">{mutation.original}</p>
            </div>
            <div>
              <span className="font-bold text-[10px] uppercase tracking-wider text-ink-muted block">
                MetaQA Test Objective & Interpretation:
              </span>
              <p className="mt-1 leading-relaxed text-ink-secondary">
                {interpretation}. {mutationExpectationLabel(mutation.kind)}
              </p>
            </div>
          </div>
        )}
      </div>
    </article>
  )
}
