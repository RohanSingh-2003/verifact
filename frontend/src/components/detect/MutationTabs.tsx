import { useState } from 'react'
import type { MutationKind, MutationRecord } from '../../types'
import { MutationKind as MutationKindValue } from '../../types'
import { classNames } from '../../lib/format'
import { MutationRow } from './MutationRow'

interface MutationTableProps {
  mutations: MutationRecord[]
}

export function MutationTable({ mutations }: MutationTableProps) {
  return (
    <div className="panel overflow-hidden divide-y divide-line">
      {mutations.map((mutation, idx) => (
        <MutationRow key={mutation.id} mutation={mutation} index={idx + 1} />
      ))}
    </div>
  )
}

interface MutationTabsProps {
  mutations: MutationRecord[]
  /** When true, verification is still in progress. */
  verifying?: boolean
}

export function MutationTabs({ mutations, verifying = false }: MutationTabsProps) {
  const [tab, setTab] = useState<MutationKind>(MutationKindValue.Synonym)
  const synonym = mutations.filter((item) => item.kind === MutationKindValue.Synonym)
  const antonym = mutations.filter((item) => item.kind === MutationKindValue.Antonym)
  const visible = tab === MutationKindValue.Synonym ? synonym : antonym
  const verifiedCount = mutations.filter((item) => item.verified).length
  const allVerified = mutations.length > 0 && verifiedCount === mutations.length

  return (
    <section className="animate-fade-up">
      <div className="mb-4">
        <h2 className="text-base font-semibold tracking-tight text-ink">MetaQA Analysis</h2>
        <p className="mt-1 text-sm leading-6 text-ink-secondary">
          VeriFact creates controlled changes to the AI&apos;s answer and checks whether the model
          reacts consistently.
        </p>
        {verifying && !allVerified ? (
          <p className="mt-2 text-xs text-ink-muted" aria-live="polite">
            Verifying mutations… {verifiedCount}/{mutations.length} complete
          </p>
        ) : null}
      </div>

      <div
        className="mb-3 flex gap-1 rounded-[var(--radius-sm)] bg-surface-muted p-1"
        role="tablist"
        aria-label="Mutation type"
      >
        {(
          [
            [
              MutationKindValue.Synonym,
              'Synonym Tests',
              synonym.length,
              'Same meaning',
              'Changes the wording without changing the fact.',
            ],
            [
              MutationKindValue.Antonym,
              'Antonym Tests',
              antonym.length,
              'Opposite meaning',
              'Changes the fact in the opposite direction.',
            ],
          ] as const
        ).map(([value, label, count, hint, detail]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            title={detail}
            onClick={() => setTab(value)}
            className={classNames(
              'flex-1 rounded-md px-3 py-2 text-left text-sm font-medium transition-colors',
              tab === value
                ? 'bg-surface text-ink shadow-[var(--shadow-card)]'
                : 'text-ink-secondary hover:text-ink',
            )}
          >
            <span className="block">
              {label}
              <span className="ml-1 font-normal text-ink-muted">· {count} tests</span>
            </span>
            <span className="mt-0.5 block text-[11px] font-normal text-ink-muted">{hint}</span>
          </button>
        ))}
      </div>

      <MutationTable mutations={visible} />
    </section>
  )
}
