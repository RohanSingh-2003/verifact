import type { ExperimentCell, NamedModel } from '../../types'
import { classNames, formatScore } from '../../lib/format'

interface ExperimentMatrixProps {
  generators: NamedModel[]
  verifiers: NamedModel[]
  cells: ExperimentCell[]
}

function cellFor(cells: ExperimentCell[], generatorId: string, verifierId: string) {
  return cells.find((cell) => cell.generatorId === generatorId && cell.verifierId === verifierId)
}

export function ExperimentMatrix({ generators, verifiers, cells }: ExperimentMatrixProps) {
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-ink">2×2 verification matrix</h2>
          <p className="mt-1 text-sm text-ink-secondary">
            Diagonal cells are same-model. Off-diagonal cells are cross-model.
          </p>
        </div>
        <div className="flex gap-4 text-[11px] text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-accent/70" /> Same-model
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm bg-ink/25" /> Cross-model
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-sm">
          <caption className="sr-only">
            Generator by verifier mean hallucination scores. Diagonal is same-model verification.
          </caption>
          <thead>
            <tr>
              <th className="p-2 text-left text-xs font-medium text-ink-muted" scope="col">
                Generator \ Verifier
              </th>
              {verifiers.map((verifier) => (
                <th
                  key={verifier.id}
                  scope="col"
                  className="p-2 text-center text-xs font-medium text-ink-secondary"
                >
                  Verifier {verifier.shortName}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {generators.map((generator) => (
              <tr key={generator.id}>
                <th scope="row" className="p-2 text-left text-xs font-medium text-ink-secondary">
                  Generator {generator.shortName}
                </th>
                {verifiers.map((verifier) => {
                  const cell = cellFor(cells, generator.id, verifier.id)
                  const same = generator.id === verifier.id
                  return (
                    <td key={verifier.id} className="p-2">
                      <div
                        className={classNames(
                          'rounded-[var(--radius-sm)] px-3 py-3',
                          same ? 'bg-accent-soft' : 'bg-surface-muted',
                        )}
                      >
                        <p className="text-xs font-medium text-ink">{cell?.label}</p>
                        <p className="mt-1 text-lg font-semibold tabular-nums text-ink">
                          {cell ? formatScore(cell.meanScore) : '—'}
                        </p>
                        <p className="mt-0.5 text-[11px] text-ink-muted">
                          {same ? 'Same-model' : 'Cross-model'} · mean score
                        </p>
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
