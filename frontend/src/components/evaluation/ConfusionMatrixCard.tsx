interface ConfusionMatrixCardProps {
  tn: number
  fp: number
  fn: number
  tp: number
}

export function ConfusionMatrixCard({ tn, fp, fn, tp }: ConfusionMatrixCardProps) {
  return (
    <section>
      <h2 className="text-base font-semibold tracking-tight text-ink">Confusion matrix</h2>
      <p className="mt-1 text-sm text-ink-secondary">
        Positive class is Hallucinated. Needs Review rows are excluded.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full max-w-lg border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-28 px-3 py-2" />
              <th className="px-3 py-2 text-center text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
                Pred. Reliable
              </th>
              <th className="px-3 py-2 text-center text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
                Pred. Hallucinated
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th className="px-3 py-3 text-left text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
                Actual Reliable
              </th>
              <td className="border border-line bg-reliable-soft/60 px-3 py-4 text-center">
                <p className="text-[11px] text-ink-muted">TN</p>
                <p className="text-lg font-semibold tabular-nums text-ink">{tn}</p>
              </td>
              <td className="border border-line bg-hallucinated-soft/70 px-3 py-4 text-center">
                <p className="text-[11px] text-ink-muted">FP</p>
                <p className="text-lg font-semibold tabular-nums text-ink">{fp}</p>
              </td>
            </tr>
            <tr>
              <th className="px-3 py-3 text-left text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
                Actual Hallucinated
              </th>
              <td className="border border-line bg-hallucinated-soft/70 px-3 py-4 text-center">
                <p className="text-[11px] text-ink-muted">FN</p>
                <p className="text-lg font-semibold tabular-nums text-ink">{fn}</p>
              </td>
              <td className="border border-line bg-reliable-soft/60 px-3 py-4 text-center">
                <p className="text-[11px] text-ink-muted">TP</p>
                <p className="text-lg font-semibold tabular-nums text-ink">{tp}</p>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
