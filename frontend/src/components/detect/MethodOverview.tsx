import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

const STEPS = [
  {
    title: 'AI generates an answer',
    detail: 'VeriFact uses Gemma 4:26B to generate an answer to your question.',
  },
  {
    title: 'VeriFact checks the answer',
    detail: 'VeriFact checks the answer using MetaQA, independent AI models, and Web Analysis.',
  },
  {
    title: 'Three checks, different purposes',
    detail:
      'MetaQA checks answer consistency. Independent AI models provide additional assessments. Web Analysis checks factual claims against relevant information found online.',
  },
  {
    title: 'You see the results',
    detail:
      'VeriFact displays the answer and its verification findings, helping you understand potential inconsistencies and unsupported claims.',
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
            MetaQA checks whether an AI answer stays consistent when small changes are made to it.
            This helps identify possible inconsistencies, but consistency alone does not guarantee
            that the answer is correct.
          </p>
          <p>
            VeriFact creates controlled variations of the answer, including applicable synonym,
            antonym, and negation changes, and uses verification to assess consistency. Because a
            model can consistently defend an incorrect belief under testing, a consistent answer
            can still be factually wrong.
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
            Web Analysis checks the factual claims in an AI answer against relevant information
            found online. It helps identify claims that are supported, contradicted, or not
            sufficiently verified by the available evidence.
          </p>
          <p>
            VeriFact retrieves sources through Tavily, evaluates their relevance and quality, and
            compares them with factual claims. Claims with no relevant sources are marked as not
            assessed, rather than automatically classified as true or false.
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
