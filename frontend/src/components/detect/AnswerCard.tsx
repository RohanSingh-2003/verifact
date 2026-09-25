import { CopyButton } from '../ui/CopyButton'
import { formatResponseTime } from '../../lib/format'

interface AnswerCardProps {
  answer: string
  model: string
  responseTimeMs: number
  llmMode?: 'mock' | 'live'
}

export function AnswerCard({ answer, model, responseTimeMs, llmMode }: AnswerCardProps) {
  return (
    <article className="panel p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-meta">AI answer</p>
        <CopyButton value={answer} />
      </div>
      <p className="mt-3 text-[15px] leading-7 text-ink">{answer}</p>
      <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
        <div className="flex gap-1.5">
          <dt>Model</dt>
          <dd className="text-ink-secondary">
            {llmMode === 'mock' ? 'MockLLM' : model}
          </dd>
        </div>
        {llmMode === 'mock' ? (
          <div className="flex gap-1.5">
            <dt>Configured generator</dt>
            <dd className="text-ink-secondary">{model}</dd>
          </div>
        ) : null}
        <div className="flex gap-1.5">
          <dt>Response</dt>
          <dd className="text-ink-secondary">{formatResponseTime(responseTimeMs)}</dd>
        </div>
      </dl>
    </article>
  )
}
