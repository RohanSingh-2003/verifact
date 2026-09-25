import { ChevronRight } from 'lucide-react'

const STEPS = [
  {
    title: 'AI generates an answer',
    detail: 'VeriFact asks the configured AI model to answer your question.',
  },
  {
    title: 'VeriFact creates test versions',
    detail:
      'It creates slightly different versions of the answer — some with the same meaning and some with the opposite meaning.',
  },
  {
    title: 'AI checks the test versions',
    detail: 'The model checks whether each version is consistent with the original answer.',
  },
  {
    title: 'VeriFact calculates a score',
    detail: 'The responses are converted into a MetaQA hallucination score.',
  },
  {
    title: 'Final result',
    detail:
      'The score is compared with the threshold to determine whether the answer is likely reliable or likely hallucinated.',
  },
] as const

export function MethodOverview() {
  return (
    <div className="mb-6 space-y-3">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-ink-secondary marker:content-none [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="h-3.5 w-3.5 text-ink-muted transition-transform group-open:rotate-90"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          How VeriFact checks an AI answer
        </summary>
        <ol className="mt-3 space-y-3 border-l border-line pl-3 sm:border-l-0 sm:pl-0 sm:grid sm:grid-cols-5 sm:gap-3 sm:space-y-0">
          {STEPS.map((step, index) => (
            <li key={step.title} className="text-xs leading-5 text-ink-secondary">
              <span className="font-semibold text-ink">
                {index + 1}. {step.title}
              </span>
              <span className="mt-1 block text-ink-muted">{step.detail}</span>
            </li>
          ))}
        </ol>
      </details>

      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-ink-secondary marker:content-none [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="h-3.5 w-3.5 text-ink-muted transition-transform group-open:rotate-90"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          What is MetaQA?
        </summary>
        <div className="mt-3 max-w-2xl space-y-3 text-xs leading-5 text-ink-secondary">
          <p>
            MetaQA is a metamorphic testing approach used here to look for fact-conflicting
            hallucinations. Instead of checking the answer against a database, VeriFact changes the
            answer in controlled ways and checks whether the AI responds consistently.
          </p>
          <dl className="space-y-2">
            <div>
              <dt className="font-medium text-ink">Same-meaning test</dt>
              <dd className="text-ink-muted">The wording changes, but the meaning stays the same.</dd>
            </div>
            <div>
              <dt className="font-medium text-ink">Opposite-meaning test</dt>
              <dd className="text-ink-muted">The meaning is deliberately changed.</dd>
            </div>
          </dl>
        </div>
      </details>
    </div>
  )
}
