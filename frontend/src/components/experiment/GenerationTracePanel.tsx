import type { GenerationTrace } from '../../types'
import { formatPercent, formatScore, shortModelName } from '../../lib/format'

interface GenerationTracePanelProps {
  trace: GenerationTrace
}

export function GenerationTracePanel({ trace }: GenerationTracePanelProps) {
  return (
    <section className="panel p-5">
      <p className="text-meta">Mutation / verifier trace</p>
      <h3 className="mt-1 text-base font-semibold tracking-tight text-ink">{trace.question}</h3>
      <p className="mt-2 text-sm leading-6 text-ink-secondary">
        Generator {shortModelName(trace.generator_model)} · the mutation texts below are identical across
        verifier conditions.
      </p>
      <p className="mt-3 text-sm leading-6 text-ink">
        <span className="text-ink-muted">Base answer: </span>
        {trace.base_answer}
      </p>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        {trace.conditions.map((condition) => (
          <article key={condition.verifier_model} className="rounded-[var(--radius-sm)] border border-line p-4">
            <p className="text-xs font-semibold tracking-[0.06em] text-ink-muted uppercase">
              {condition.pair_type === 'same' ? 'Same-model' : 'Cross-model'} · Verifier{' '}
              {shortModelName(condition.verifier_model)}
            </p>
            <p className="mt-2 text-sm text-ink">
              Score {formatScore(condition.hallucination_score)} · {condition.classification} · NOT SURE{' '}
              {formatPercent(condition.not_sure_rate)}
            </p>
            <ol className="mt-3 space-y-2 text-xs leading-5">
              {condition.mutations.map((mutation, index) => (
                <li key={mutation.id} className="border-t border-line pt-2 first:border-t-0 first:pt-0">
                  <span className="font-medium text-ink-muted">
                    M{index + 1} {mutation.type}
                  </span>
                  <p className="mt-1 text-ink">{mutation.mutated_text}</p>
                  <p className="mt-1 text-ink-secondary">
                    {mutation.verdict} · expected {mutation.expected_verdict} · contribution{' '}
                    {formatScore(mutation.contribution)}
                  </p>
                </li>
              ))}
            </ol>
          </article>
        ))}
      </div>
    </section>
  )
}
