import type { ReactNode } from 'react'

export interface ComparisonRow {
  dimension: string
  research: ReactNode
  implementation: ReactNode
}

export interface ResearchComparisonTableProps {
  researchHeader: string
  implementationHeader: string
  rows: ComparisonRow[]
  note?: string
}

export function ResearchComparisonTable({
  researchHeader,
  implementationHeader,
  rows,
  note,
}: ResearchComparisonTableProps) {
  return (
    <div className="panel p-5 sm:p-6 space-y-4">
      {/* Responsive table wrapper: horizontal scroll enabled on narrow screens, fits naturally on desktop */}
      <div className="overflow-x-auto -mx-1 sm:mx-0">
        <table className="w-full min-w-[580px] sm:min-w-full table-fixed text-left text-xs">
          {/* Explicit stable column widths: 20% Dimension, 40% Research, 40% Implementation */}
          <colgroup>
            <col className="w-[20%]" />
            <col className="w-[40%]" />
            <col className="w-[40%]" />
          </colgroup>
          <thead>
            <tr className="border-b border-line text-ink-muted">
              <th scope="col" className="px-3.5 pb-3 font-semibold align-top text-left">
                Dimension
              </th>
              <th scope="col" className="px-3.5 pb-3 font-semibold align-top text-left">
                {researchHeader}
              </th>
              <th scope="col" className="px-3.5 pb-3 font-semibold align-top text-left">
                {implementationHeader}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/60 text-ink-secondary">
            {rows.map((row) => (
              <tr key={row.dimension} className="hover:bg-surface-muted/30 transition-colors">
                <td className="px-3.5 py-3 font-medium text-ink align-top [overflow-wrap:anywhere] break-words">
                  {row.dimension}
                </td>
                <td className="px-3.5 py-3 align-top leading-relaxed [overflow-wrap:anywhere] break-words">
                  {row.research}
                </td>
                <td className="px-3.5 py-3 align-top leading-relaxed [overflow-wrap:anywhere] break-words">
                  {row.implementation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {note ? (
        <p className="text-[11px] leading-5 text-ink-muted border-t border-line/60 pt-3">
          {note}
        </p>
      ) : null}
    </div>
  )
}
