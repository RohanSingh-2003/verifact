import { ArrowDown } from 'lucide-react'
import { PageHeader } from '../components/ui/PageHeader'
import { MutationCard } from '../components/research/MutationCard'
import { ResearchComparisonTable, type ComparisonRow } from '../components/research/ResearchComparisonTable'

const metaqaComparisonRows: ComparisonRow[] = [
  {
    dimension: 'Purpose',
    research: 'Offline benchmark evaluation of LLM hallucination rates',
    implementation: 'Interactive web application for real-time hallucination inspection',
  },
  {
    dimension: 'Answer Generation',
    research: 'Evaluated across GPT-4, GPT-3.5, Llama3-8B, Mistral-7B',
    implementation: 'Locally hosted Ollama model (Gemma 4:26B)',
  },
  {
    dimension: 'Mutation Generation',
    research: 'Same LLM prompted with few-shot examples',
    implementation: 'Gemma 4:26B with structured JSON schema enforcement',
  },
  {
    dimension: 'Mutation Types',
    research: 'Synonym (lexical & inversion) and Antonym (negation)',
    implementation: 'Configurable synonym & antonym mutations (default 3 each)',
  },
  {
    dimension: 'Verifier',
    research: 'Same evaluated LLM acted as self-verifier',
    implementation: 'Cross-model verifier: Google Gemini 3.8 Flash',
  },
  {
    dimension: 'Scoring',
    research: 'Averaged synonym & antonym scores (Eq. 5)',
    implementation: 'Identical scoring weights (YES/NO/NOT SURE contributions)',
  },
  {
    dimension: 'Threshold',
    research: 'Evaluated across θ ∈ [0.1, 0.8]; default 0.5',
    implementation: 'Default θ = 0.5 (configurable in Settings)',
  },
  {
    dimension: 'External Evidence',
    research: 'None (pure zero-resource method)',
    implementation: 'MetaQA branch uses none; runs in parallel with Web Analysis',
  },
  {
    dimension: 'Implementation',
    research: 'Batch Python evaluation scripts on benchmark datasets',
    implementation: 'FastAPI backend + Vite/React frontend with audit history',
  },
]

export function MetaQAPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      {/* 1. Header */}
      <header>
        <PageHeader
          title="MetaQA"
          description="How VeriFact uses metamorphic testing to detect fact-conflicting hallucinations."
        />
        <div className="mt-2 space-y-1">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            <span>
              Based on: <strong className="font-medium text-ink-secondary">Yang et al., FSE 2025</strong> —{' '}
              <em>Hallucination Detection in Large Language Models with Metamorphic Relations</em>
            </span>
          </div>
          <div className="pl-3.5">
            <a
              href="https://doi.org/10.1145/3715735"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-xs font-medium text-ink-muted underline-offset-4 hover:text-ink hover:underline"
            >
              View research paper →
            </a>
          </div>
        </div>
      </header>

      {/* 2. What is MetaQA? */}
      <section className="panel p-5 sm:p-6 space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">What is MetaQA?</h2>
        <p className="text-sm leading-7 text-ink-secondary">
          MetaQA is a self-contained approach for detecting fact-conflicting hallucinations in LLM
          responses. Instead of checking the original answer against an external database, it creates
          controlled changes to the answer and checks whether the expected relationships are preserved.
        </p>
        <p className="text-sm leading-7 text-ink-secondary border-t border-line/60 pt-3">
          VeriFact implements this MetaQA-style approach as one of its two verification methods.
          The original MetaQA framework is a zero-resource, self-contained method that does not rely on
          external search engines or knowledge bases.
        </p>
      </section>

      {/* 3. MetaQA Core Idea (Workflow Diagram) */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">MetaQA Core Idea</h2>
          <p className="mt-1 text-xs text-ink-muted">
            End-to-end metamorphic verification flow from prompt to classification.
          </p>
        </div>

        <div className="panel p-5 sm:p-6">
          <div className="mx-auto flex max-w-md flex-col items-center">
            {/* User Question */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 1</span>
              <p className="text-xs font-semibold text-ink">User Question</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Base Answer */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 2</span>
              <p className="text-xs font-semibold text-ink">Base Answer Generated</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Mutation Generation */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Step 3</span>
              <p className="text-xs font-semibold text-ink">Metamorphic Mutation Generation</p>
            </div>

            {/* Split into Synonym & Antonym */}
            <div className="w-full max-w-md pt-2">
              <div className="relative flex justify-center">
                <div className="h-4 w-px bg-line" />
              </div>
              <div className="relative">
                <div className="mx-auto h-px w-1/2 bg-line" />
                <div className="flex justify-between px-[25%]">
                  <div className="h-3 w-px bg-line" />
                  <div className="h-3 w-px bg-line" />
                </div>
              </div>

              <div className="mt-1 grid grid-cols-2 gap-3 sm:gap-4">
                {/* Synonym Column */}
                <div className="flex flex-col items-center space-y-2 rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-3 text-center">
                  <span className="rounded bg-accent-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
                    Synonym
                  </span>
                  <p className="text-[11px] leading-tight text-ink-secondary">
                    Same meaning rephrased
                  </p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <div className="w-full rounded border border-line bg-surface py-1 text-[11px] font-medium text-ink">
                    Verifier Check
                  </div>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <p className="text-[10px] font-bold text-reliable">
                    Expected: YES
                  </p>
                </div>

                {/* Antonym Column */}
                <div className="flex flex-col items-center space-y-2 rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-3 text-center">
                  <span className="rounded bg-hallucinated-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-hallucinated">
                    Antonym
                  </span>
                  <p className="text-[11px] leading-tight text-ink-secondary">
                    Opposite meaning negated
                  </p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <div className="w-full rounded border border-line bg-surface py-1 text-[11px] font-medium text-ink">
                    Verifier Check
                  </div>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <p className="text-[10px] font-bold text-hallucinated">
                    Expected: NO
                  </p>
                </div>
              </div>

              {/* Converge to Scoring */}
              <div className="mt-2">
                <div className="flex justify-between px-[25%]">
                  <div className="h-3 w-px bg-line" />
                  <div className="h-3 w-px bg-line" />
                </div>
                <div className="mx-auto h-px w-1/2 bg-line" />
                <div className="flex justify-center">
                  <div className="h-4 w-px bg-line" />
                </div>
              </div>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Score & Threshold */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2.5 text-center shadow-card">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 4</span>
              <p className="text-xs font-bold text-ink">MetaQA Inconsistency Score</p>
              <p className="text-[10px] text-ink-muted mt-0.5">Average of all mutation penalty scores</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Final Classification */}
            <div className="grid w-full max-w-xs grid-cols-2 gap-2 text-center text-xs">
              <div className="rounded-[var(--radius-sm)] border border-reliable/30 bg-reliable-soft p-2">
                <p className="text-[11px] font-bold text-reliable">Score &lt; 0.5</p>
                <p className="text-[10px] text-ink-secondary">Likely Reliable</p>
              </div>
              <div className="rounded-[var(--radius-sm)] border border-hallucinated/30 bg-hallucinated-soft p-2">
                <p className="text-[11px] font-bold text-hallucinated">Score ≥ 0.5</p>
                <p className="text-[10px] text-ink-secondary">Likely Hallucinated</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Metamorphic Relations */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Metamorphic Relations</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The mathematical and conceptual foundation of metamorphic testing.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            A metamorphic relation defines how the expected result should behave when a controlled
            change is made. In software engineering, metamorphic testing addresses the &ldquo;test oracle
            problem&rdquo;—when the true answer is unknown in advance, we test whether known invariants hold
            under input transformations.
          </p>
          <p className="text-sm leading-relaxed text-ink-secondary">
            In MetaQA, the answer is changed in controlled ways. The verifier should react differently
            depending on whether the change preserves or contradicts the original meaning.
          </p>

          {/* Example Box */}
          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Concrete Example</p>
            <div className="grid gap-2 text-xs">
              <div className="flex items-start gap-2">
                <span className="w-28 shrink-0 font-medium text-ink">Question:</span>
                <span className="text-ink-secondary">&ldquo;What is the capital of India?&rdquo;</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-28 shrink-0 font-medium text-ink">Base answer:</span>
                <span className="text-ink-secondary">&ldquo;The capital of India is New Delhi.&rdquo;</span>
              </div>
              <div className="flex items-start gap-2 border-t border-line/60 pt-2">
                <span className="w-28 shrink-0 font-medium text-accent">Synonym mutation:</span>
                <div className="flex-1">
                  <span className="text-ink-secondary">&ldquo;New Delhi serves as India&apos;s capital.&rdquo;</span>
                  <span className="ml-2 font-semibold text-reliable">→ Expected: YES</span>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-28 shrink-0 font-medium text-hallucinated">Antonym mutation:</span>
                <div className="flex-1">
                  <span className="text-ink-secondary">&ldquo;New Delhi is not the capital of India.&rdquo;</span>
                  <span className="ml-2 font-semibold text-hallucinated">→ Expected: NO</span>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-surface-muted p-3 text-xs text-ink-secondary leading-relaxed">
            <strong className="font-semibold text-ink">Implementation detail:</strong> While the expected
            verdict is part of the methodology, in the actual VeriFact verifier implementation, the
            expected verdict is <strong className="text-ink">NOT sent to the verifier (Gemini)</strong>.
            The verifier independently assesses the statement against the candidate answer without
            knowing the expected answer or whether the statement is a synonym or antonym.
          </div>
        </div>
      </section>

      {/* 5 & 6. Synonym vs Antonym Mutations */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Mutation Types</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The two transformations applied to test answer consistency.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
          <MutationCard
            badge="S"
            title="Synonym Mutations"
            badgeVariant="synonym"
            description={
              <>
                Synonym mutations change the wording while keeping the factual meaning. In the MetaQA paper,
                these include <em>lexical substitution</em> (replacing verbs or descriptive predicates) and{' '}
                <em>inversion</em> (reversing grammatical roles while preserving meaning).
              </>
            }
            original="New Delhi is the capital of India."
            mutation="New Delhi serves as India's capital."
            expectedVerdict="YES"
            verdictVariant="reliable"
          />

          <MutationCard
            badge="A"
            title="Antonym Mutations"
            badgeVariant="antonym"
            description={
              <>
                Antonym mutations intentionally reverse or contradict the factual meaning through direct
                negation. A consistent model must recognize that the mutated statement directly conflicts
                with the original claim.
              </>
            }
            original="New Delhi is the capital of India."
            mutation="New Delhi is not the capital of India."
            expectedVerdict="NO"
            verdictVariant="hallucinated"
          />
        </div>
      </section>

      {/* 7. Verifier */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">The Verifier in VeriFact</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Separation of roles between generation, mutation, and verification.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            The verifier examines each mutation relative to the candidate answer and returns{' '}
            <strong className="font-semibold text-ink">YES</strong>,{' '}
            <strong className="font-semibold text-ink">NO</strong>, or{' '}
            <strong className="font-semibold text-ink">NOT SURE</strong>.
          </p>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-[var(--radius-sm)] border border-line bg-canvas p-3.5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Generation</p>
              <p className="mt-1 text-xs font-bold text-ink">Gemma 4:26B</p>
              <p className="mt-1 text-[11px] leading-4 text-ink-secondary">
                Locally hosted via Ollama. Generates base answer and metamorphic mutations.
              </p>
            </div>

            <div className="rounded-[var(--radius-sm)] border border-line bg-canvas p-3.5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-accent">Verification</p>
              <p className="mt-1 text-xs font-bold text-ink">Google Gemini 3.8 Flash</p>
              <p className="mt-1 text-[11px] leading-4 text-ink-secondary">
                Evaluates each statement against the candidate answer in zero-shot JSON mode.
              </p>
            </div>

            <div className="rounded-[var(--radius-sm)] border border-line bg-canvas p-3.5">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Scoring</p>
              <p className="mt-1 text-xs font-bold text-ink">Deterministic Backend</p>
              <p className="mt-1 text-[11px] leading-4 text-ink-secondary">
                Python backend maps verdicts to numeric contributions and computes the average.
              </p>
            </div>
          </div>

          <p className="text-xs leading-relaxed text-ink-secondary border-t border-line/60 pt-3">
            In VeriFact, Gemini is used only for MetaQA mutation verification. It does not generate the
            original answer or the mutations. VeriFact never exposes hidden expected verdicts in the
            verifier prompt, avoiding confirmation bias.
          </p>
        </div>
      </section>

      {/* 8. MetaQA Scoring */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">MetaQA Scoring Logic</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Mathematical translation of verifier responses into a hallucination score.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-5">
          <p className="text-sm leading-relaxed text-ink-secondary">
            VeriFact assigns penalty values based on whether the verifier response violates the
            metamorphic relation:
          </p>

          {/* Scoring Mapping Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line text-ink-muted">
                  <th className="pb-2 font-medium">Mutation Type</th>
                  <th className="pb-2 font-medium text-center">YES</th>
                  <th className="pb-2 font-medium text-center">NO</th>
                  <th className="pb-2 font-medium text-center">NOT SURE</th>
                  <th className="pb-2 font-medium">Interpretation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 text-ink-secondary">
                <tr>
                  <td className="py-2.5 font-medium text-ink">Synonym (S)</td>
                  <td className="py-2.5 text-center font-bold text-reliable">0.0</td>
                  <td className="py-2.5 text-center font-bold text-hallucinated">1.0</td>
                  <td className="py-2.5 text-center font-medium text-uncertain">0.5</td>
                  <td className="py-2.5 text-[11px]">Expected to agree; rejection adds full penalty.</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-medium text-ink">Antonym (A)</td>
                  <td className="py-2.5 text-center font-bold text-hallucinated">1.0</td>
                  <td className="py-2.5 text-center font-bold text-reliable">0.0</td>
                  <td className="py-2.5 text-center font-medium text-uncertain">0.5</td>
                  <td className="py-2.5 text-[11px]">Expected to disagree; accepting contradiction adds penalty.</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Formula */}
          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas p-4 text-center">
            <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
              Hallucination Score Formula
            </p>
            <div className="font-mono text-sm font-semibold text-ink">
              S<sub>QB</sub> = ( &Sigma; SynScore(S<sub>i</sub>) + &Sigma; AntScore(A<sub>j</sub>) ) &divide; ( N + M )
            </div>
            <p className="mt-2 text-xs text-ink-secondary">
              VeriFact averages all mutation contributions to scale the score cleanly between 0.0 and 1.0.
            </p>
          </div>

          {/* Threshold rules */}
          <div className="grid gap-3 sm:grid-cols-2 text-xs">
            <div className="rounded border border-line bg-canvas/60 p-3">
              <span className="font-semibold text-ink">Score &ge; Threshold (default 0.5):</span>
              <p className="mt-1 text-ink-secondary">
                High inconsistency across metamorphic variants indicates a high likelihood of a fact-conflicting
                hallucination. Classified as <strong className="text-hallucinated">Likely Hallucinated</strong>.
              </p>
            </div>
            <div className="rounded border border-line bg-canvas/60 p-3">
              <span className="font-semibold text-ink">Score &lt; Threshold:</span>
              <p className="mt-1 text-ink-secondary">
                The verifier consistently accepted meaning-preserving synonyms and rejected contradictory
                antonyms. Classified as <strong className="text-reliable">Likely Reliable</strong>.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 9. Why MetaQA Does Not Need Web Search */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Why MetaQA Does Not Need Web Search</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The fundamental distinction between consistency testing and retrieval.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-3">
          <p className="text-sm leading-relaxed text-ink-secondary">
            MetaQA is designed to test consistency without directly looking up the correct answer on
            the web or consulting a factual database. When a model hallucinates, its internal factual
            grounding is brittle: small semantic shifts expose contradictions that an invariant fact
            would not produce.
          </p>
          <p className="text-sm leading-relaxed text-ink-secondary border-t border-line/60 pt-3">
            This makes MetaQA fundamentally different from VeriFact&apos;s Web Analysis branch, which
            explicitly searches external web sources. Together, they provide two independent perspectives:
            one on internal semantic consistency, and one on external evidentiary corroboration.
          </p>
        </div>
      </section>

      {/* 10. Research Paper vs VeriFact Comparison */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Research Paper vs VeriFact</h2>
          <p className="mt-1 text-xs text-ink-muted">
            How VeriFact translates academic research into an interactive system.
          </p>
        </div>

        <ResearchComparisonTable
          researchHeader="MetaQA Research (Yang et al., FSE 2025)"
          implementationHeader="VeriFact Implementation"
          rows={metaqaComparisonRows}
          note="VeriFact implements the MetaQA methodology as an interactive application and uses a different model configuration and engineering pipeline from the research evaluation. It does not reproduce every offline experiment from the paper, but adheres faithfully to its metamorphic relations and scoring formulation."
        />
      </section>
    </div>
  )
}
