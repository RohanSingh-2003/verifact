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
    <div className="panel overflow-hidden">
      <div className="hidden border-b border-line bg-surface-muted/50 px-4 py-2.5 text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase md:grid md:grid-cols-[minmax(0,1fr)_5.5rem_5.75rem_5.75rem_5.5rem_1rem] md:gap-3">
        <span>Mutation</span>
        <span>Type</span>
        <span>Actual</span>
        <span>Expected</span>
        <span className="text-right">Contribution</span>
        <span className="sr-only">Expand</span>
      </div>
      {mutations.map((mutation) => (
        <MutationRow key={mutation.id} mutation={mutation} />
      ))}
    </div>
  )
}

interface MutationTabsProps {
  mutations: MutationRecord[]
}

export function MutationTabs({ mutations }: MutationTabsProps) {
  const [tab, setTab] = useState<MutationKind>(MutationKindValue.Synonym)
  const synonym = mutations.filter((item) => item.kind === MutationKindValue.Synonym)
  const antonym = mutations.filter((item) => item.kind === MutationKindValue.Antonym)
  const visible = tab === MutationKindValue.Synonym ? synonym : antonym

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-base font-semibold tracking-tight text-ink">Mutation Analysis</h2>
        <p className="mt-1 text-sm leading-6 text-ink-secondary">
          MetaQA evaluates whether meaning-preserving and meaning-reversing mutations behave as
          expected.
        </p>
      </div>

      <div className="mb-3 flex gap-1 rounded-[var(--radius-sm)] bg-surface-muted p-1" role="tablist" aria-label="Mutation type">
        {(
          [
            [MutationKindValue.Synonym, 'Synonym', synonym.length, 'Meaning-preserving'],
            [MutationKindValue.Antonym, 'Antonym', antonym.length, 'Meaning-reversing'],
          ] as const
        ).map(([value, label, count, hint]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={classNames(
              'flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              tab === value ? 'bg-surface text-ink shadow-[var(--shadow-card)]' : 'text-ink-secondary hover:text-ink',
            )}
          >
            <span>
              {label} {count}
            </span>
            <span className="mt-0.5 hidden text-[11px] font-normal text-ink-muted sm:block">{hint}</span>
          </button>
        ))}
      </div>

      <MutationTable mutations={visible} />
    </section>
  )
}
