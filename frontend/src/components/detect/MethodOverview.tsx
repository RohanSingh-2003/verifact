import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

const STEPS = [
  {
    title: 'AI generates an answer',
    detail: 'VeriFact first asks the AI to answer your question.',
  },
  {
    title: 'VeriFact checks the answer',
    detail: 'VeriFact checks the answer in two different ways: MetaQA and Web Analysis.',
  },
  {
    title: 'Two checks, different purposes',
    detail:
      'MetaQA checks whether the AI stays consistent when the answer is changed. Web Analysis checks the answer against relevant information from the web.',
  },
  {
    title: 'You see the results',
    detail:
      "VeriFact shows the AI's answer, the MetaQA findings, and the Web Analysis findings so you can see what was checked.",
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
        <ol className="mt-3 space-y-3 border-l border-line pl-3 sm:border-l-0 sm:pl-0 sm:grid sm:grid-cols-2 sm:gap-4 sm:space-y-0">
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
        <div className="mt-3 max-w-2xl space-y-2.5 text-xs leading-5 text-ink-secondary">
          <p>
            MetaQA is one of the ways VeriFact checks an AI answer. It makes small changes to the
            answer and checks whether the AI responds consistently.
          </p>
          <div>
            <Link
              to="/metaqa"
              className="inline-flex items-center font-medium text-accent underline-offset-4 hover:underline"
            >
              Learn more about MetaQA →
            </Link>
          </div>
        </div>
      </details>

      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-sm text-ink-secondary marker:content-none [&::-webkit-details-marker]:hidden">
          <ChevronRight
            className="h-3.5 w-3.5 text-ink-muted transition-transform group-open:rotate-90"
            strokeWidth={1.75}
            aria-hidden="true"
          />
          What is Web Analysis?
        </summary>
        <div className="mt-3 max-w-2xl space-y-2.5 text-xs leading-5 text-ink-secondary">
          <p>
            Web Analysis is another way VeriFact checks an AI answer. It looks at the factual claims
            in the answer and checks them against relevant information found on the web.
          </p>
          <div>
            <Link
              to="/web-analysis"
              className="inline-flex items-center font-medium text-accent underline-offset-4 hover:underline"
            >
              Learn more about Web Analysis →
            </Link>
          </div>
        </div>
      </details>
    </div>
  )
}
