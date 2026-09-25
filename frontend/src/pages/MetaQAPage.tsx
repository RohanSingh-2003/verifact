import { PageHeader } from '../components/ui/PageHeader'

const steps = [
  {
    title: 'Generate an answer',
    body: 'A generator model produces a candidate answer to a factual question. VeriFact treats this as the claim under test, not as ground truth.',
  },
  {
    title: 'Create test versions',
    body: 'Same-meaning (synonym) tests rephrase the answer without changing the fact. Opposite-meaning (antonym) tests deliberately reverse or negate the claim.',
  },
  {
    title: 'Check each test version',
    body: 'A verifier model labels each version YES, NO, or NOT SURE. Same-meaning tests should keep the original decision; opposite-meaning tests should invert it.',
  },
  {
    title: 'Score inconsistency',
    body: 'Unexpected verifier responses raise the MetaQA hallucination score. Scores at or above the configured threshold are classified as likely hallucinated.',
  },
]

export function MetaQAPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="MetaQA"
        description="How VeriFact uses metamorphic testing to look for fact-conflicting hallucinations — without searching the web or knowing the correct answer."
      />

      <article className="panel p-5 sm:p-6">
        <p className="text-sm leading-7 text-ink-secondary">
          MetaQA does not look answers up in a database. Instead, VeriFact changes the AI&apos;s
          answer in controlled ways and checks whether the model responds consistently. Inconsistency
          is evidence of a fact-conflicting hallucination — not a guarantee that the original answer
          is true or false.
        </p>
      </article>

      <ol className="mt-6 space-y-3">
        {steps.map((step, index) => (
          <li key={step.title} className="panel px-5 py-4">
            <p className="text-meta">Step {index + 1}</p>
            <h2 className="mt-1 text-base font-semibold text-ink">{step.title}</h2>
            <p className="mt-1 text-sm leading-6 text-ink-secondary">{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
