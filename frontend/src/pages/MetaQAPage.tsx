import { PageHeader } from '../components/ui/PageHeader'

const steps = [
  {
    title: 'Generate an answer',
    body: 'A generator model produces a candidate answer to a factual question. VeriFact treats this as the claim under test, not as ground truth.',
  },
  {
    title: 'Create mutations',
    body: 'Synonym mutations preserve meaning through paraphrase. Antonym mutations reverse or negate the claim. Both sets are generated from the original answer.',
  },
  {
    title: 'Verify each mutation',
    body: 'A verifier model labels each mutated statement YES, NO, or NOT SURE. Meaning-preserving mutations should keep the original decision; meaning-reversing mutations should invert it.',
  },
  {
    title: 'Score inconsistency',
    body: 'Unexpected verifier responses raise the MetaQA hallucination score. Scores above the configured threshold are classified as hallucinated.',
  },
]

export function MetaQAPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="MetaQA"
        description="A short overview of the metamorphic verification method used by VeriFact."
      />

      <article className="panel p-5 sm:p-6">
        <p className="text-sm leading-7 text-ink-secondary">
          VeriFact implements MetaQA as an analytical workflow: mutate the generated answer, verify
          those mutations, and measure whether the verifier behaves as the mutation type predicts.
          Inconsistency is evidence of a fact-conflicting hallucination, not a guarantee of truth.
        </p>
      </article>

      <ol className="mt-6 space-y-3">
        {steps.map((step, index) => (
          <li
            key={step.title}
            className="panel px-5 py-4"
          >
            <p className="text-meta">Step {index + 1}</p>
            <h2 className="mt-1 text-base font-semibold text-ink">{step.title}</h2>
            <p className="mt-1 text-sm leading-6 text-ink-secondary">{step.body}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
