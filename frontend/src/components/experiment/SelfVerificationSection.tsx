import type { SelfVerificationBlock } from '../../types'
import { formatPercent, formatPValue, formatScore, shortModelName } from '../../lib/format'

interface SelfVerificationSectionProps {
  blocks: SelfVerificationBlock[]
}

export function SelfVerificationSection({ blocks }: SelfVerificationSectionProps) {
  return (
    <section>
      <h2 className="text-base font-semibold tracking-tight text-ink">Self-verification score difference</h2>
      <p className="mt-1 max-w-2xl text-sm leading-6 text-ink-secondary">
        Difference = mean(same-model score) − mean(cross-model score). Negative values mean same-model
        verification produced lower hallucination scores. This is a measured difference, not a labeled bias.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {blocks.map((block) => (
          <article key={block.generator_model} className="panel p-5">
            <p className="text-meta">Generator {shortModelName(block.generator_model)}</p>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <div>
                <dt className="text-ink-muted">Same-model score</dt>
                <dd className="mt-1 tabular-nums text-ink">{formatScore(block.same_model_mean)}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Cross-model score</dt>
                <dd className="mt-1 tabular-nums text-ink">{formatScore(block.cross_model_mean)}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Difference</dt>
                <dd className="mt-1 tabular-nums text-ink">
                  {block.self_verification_score_difference > 0 ? '+' : ''}
                  {formatScore(block.self_verification_score_difference)}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Flip rate</dt>
                <dd className="mt-1 tabular-nums text-ink">{formatPercent(block.classification_flip_rate)}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Wilcoxon p-value</dt>
                <dd className="mt-1 tabular-nums text-ink">{formatPValue(block.wilcoxon.p_value)}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">n / alpha</dt>
                <dd className="mt-1 tabular-nums text-ink">
                  {block.n} / {block.alpha}
                </dd>
              </div>
            </dl>
            {block.exploratory ? (
              <p className="mt-3 text-xs leading-5 text-ink-muted">
                Sample is small; treat this result as exploratory.
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  )
}
