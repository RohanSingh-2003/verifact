import { ArrowDown, AlertTriangle, CheckCircle2, ShieldCheck, Sparkles, Globe, Layers } from 'lucide-react'
import { PageHeader } from '../components/ui/PageHeader'
import { MutationCard } from '../components/research/MutationCard'
import { ResearchComparisonTable, type ComparisonRow } from '../components/research/ResearchComparisonTable'

const metaqaComparisonRows: ComparisonRow[] = [
  {
    dimension: 'Core Purpose',
    research: 'Offline academic benchmark evaluation of hallucination rates across public QA datasets (FactKG, Med-HALT, TriviaQA)',
    implementation: 'Real-time interactive application providing on-demand metamorphic hallucination detection and audit persistence',
  },
  {
    dimension: 'Answer Generation',
    research: 'Evaluated across diverse target LLMs (GPT-4, GPT-3.5, Llama-3-8B, Mistral-7B)',
    implementation: 'Fixed generation exclusively by Gemma 4:26B (Ollama Cloud). Model selection is fixed in backend configuration',
  },
  {
    dimension: 'Mutation Generation',
    research: 'Prompted the evaluated model with few-shot demonstration examples',
    implementation: 'Gemma 4:26B extracts core factual claims and generates applicable synonym, antonym, and negation mutations via strict JSON schemas',
  },
  {
    dimension: 'Mutation Types',
    research: 'Synonym mutations (lexical substitution, active/passive inversion) and Antonym mutations (direct negation)',
    implementation: 'Meaning-preserving synonym mutations and meaning-contradicting antonym/negation mutations, bounded to 5–35 words (default 3 synonyms and 3 antonyms)',
  },
  {
    dimension: 'Mutation Verifier',
    research: 'Self-verification: the evaluated target LLM verified its own mutated statements',
    implementation: 'Cross-model verification: independent models (Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, and Liquid LFM-2.5) evaluate statements against the candidate answer',
  },
  {
    dimension: 'Verifier Blindness',
    research: 'Expected relation was not revealed in prompts',
    implementation: 'Strict prompt blindness: expected verdicts (YES/NO) and mutation types are never leaked to verifiers, preventing confirmation bias',
  },
  {
    dimension: 'Scoring Formulation',
    research: 'Inconsistency score formula (Eq. 5): arithmetic mean of synonym and antonym penalty scores',
    implementation: 'Exact implementation of Eq. 5: Synonym (YES=0, NO=1, NOT SURE=0.5) and Antonym (YES=1, NO=0, NOT SURE=0.5) averaged into [0.0, 1.0]',
  },
  {
    dimension: 'Classification Threshold',
    research: 'Evaluated across θ ∈ [0.1, 0.8]; default operational threshold θ = 0.5',
    implementation: 'Default threshold θ = 0.5 (configurable in backend Settings): Score ≥ θ → Likely Hallucinated, Score < θ → Likely Reliable',
  },
  {
    dimension: 'Multi-Model Cross-Verification',
    research: 'Not evaluated (focused on single-model self-consistency)',
    implementation: 'Complementary feature: independent models (Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, Liquid LFM-2.5) independently evaluate Gemma’s answer without altering MetaQA scores',
  },
  {
    dimension: 'External Evidence',
    research: 'Pure zero-resource method (no external search, databases, or retrieval)',
    implementation: 'Core MetaQA branch is zero-resource; VeriFact additionally offers an independent Web Evidence pipeline (Tavily Search) in parallel',
  },
  {
    dimension: 'System Architecture',
    research: 'Batch Python scripts executed on static datasets',
    implementation: 'Asynchronous FastAPI backend with progressive UI updates, streaming detection stages, SQLite storage, and a Vite/React frontend',
  },
]

export function MetaQAPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      {/* 1. Header & Attribution */}
      <header>
        <PageHeader
          title="MetaQA"
          description="How VeriFact applies metamorphic relation testing to detect fact-conflicting hallucinations."
        />
        <div className="mt-2 space-y-1">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            <span>
              Academic Foundation: <strong className="font-medium text-ink-secondary">Yang et al., FSE 2025</strong> —{' '}
              <em>Hallucination Detection in Large Language Models with Metamorphic Relations</em>
            </span>
          </div>
          <div className="pl-3.5">
            <a
              href="https://doi.org/10.1145/3715735"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-xs font-medium text-accent underline-offset-4 hover:underline"
            >
              Official Paper (ACM DOI: 10.1145/3715735) →
            </a>
          </div>
        </div>
      </header>

      {/* 2. What is MetaQA? */}
      <section className="panel p-5 sm:p-6 space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">What is MetaQA?</h2>
        <p className="text-sm leading-7 text-ink-secondary">
          MetaQA tests whether an AI-generated answer remains consistent when relevant changes are made to it.
          This helps identify possible internal inconsistencies, but <strong>consistency alone does not guarantee
          that the answer is factually correct</strong>—an AI model can consistently repeat an incorrect claim.
        </p>
        <p className="text-sm leading-7 text-ink-secondary border-t border-line/60 pt-3">
          Traditional fact-checking requires querying external databases or search engines. MetaQA provides a
          <strong>zero-resource, reference-free</strong> detection methodology that addresses the software engineering{' '}
          <em>test oracle problem</em>—where external ground truth is unknown in advance. By generating controlled
          perturbations called <strong>metamorphic relations</strong> (including synonym variations, antonyms, and
          explicit negations), VeriFact verifies whether the model’s stated assertions remain invariant under rephrasing
          and strictly reject contradictory variants.
        </p>
      </section>

      {/* 3. The VeriFact End-to-End Workflow Diagram */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">VeriFact MetaQA Workflow</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The verified execution flow implemented in VeriFact from user question to final classification.
          </p>
        </div>

        <div className="panel p-5 sm:p-6">
          <div className="mx-auto flex max-w-md flex-col items-center">
            {/* Step 1: User Question */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 1</span>
              <p className="text-xs font-semibold text-ink">User Question Submitted</p>
              <p className="text-[10px] text-ink-muted">User inputs prompt without model selection</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 2: Fixed Gemma Generation */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-accent/40 bg-accent-soft/30 px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Step 2</span>
              <p className="text-xs font-semibold text-ink">Gemma 4:26B Answer Generation</p>
              <p className="text-[10px] text-ink-muted">Fixed answer model generates candidate response</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 3: Claim Extraction & Metamorphic Mutations */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 3</span>
              <p className="text-xs font-semibold text-ink">Claim Extraction &amp; Mutation Generation</p>
              <p className="text-[10px] text-ink-muted">Gemma extracts claims and generates synonym, antonym &amp; negation mutations</p>
            </div>

            {/* Metamorphic Split */}
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
                {/* Synonym Branch */}
                <div className="flex flex-col items-center space-y-2 rounded-[var(--radius-sm)] border border-accent/30 bg-canvas/70 p-3 text-center">
                  <span className="rounded bg-accent-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
                    Synonym Mutations
                  </span>
                  <p className="text-[11px] leading-tight text-ink-secondary">
                    Preserves factual meaning
                  </p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <div className="w-full rounded border border-line bg-surface py-1 px-1.5 text-[10px] font-medium text-ink">
                    Multi-Model Verifiers
                    <span className="block text-[9px] text-ink-muted font-normal">Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, Liquid LFM-2.5</span>
                  </div>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <div className="rounded bg-reliable-soft px-2 py-0.5 text-[10px] font-bold text-reliable">
                    Expected: YES (0.0)
                  </div>
                  <p className="text-[9px] text-ink-muted">NO adds 1.0 penalty</p>
                </div>

                {/* Antonym Branch */}
                <div className="flex flex-col items-center space-y-2 rounded-[var(--radius-sm)] border border-hallucinated/30 bg-canvas/70 p-3 text-center">
                  <span className="rounded bg-hallucinated-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-hallucinated">
                    Antonym &amp; Negation
                  </span>
                  <p className="text-[11px] leading-tight text-ink-secondary">
                    Contradicts factual meaning
                  </p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <div className="w-full rounded border border-line bg-surface py-1 px-1.5 text-[10px] font-medium text-ink">
                    Multi-Model Verifiers
                    <span className="block text-[9px] text-ink-muted font-normal">Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, Liquid LFM-2.5</span>
                  </div>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <div className="rounded bg-reliable-soft px-2 py-0.5 text-[10px] font-bold text-reliable">
                    Expected: NO (0.0)
                  </div>
                  <p className="text-[9px] text-ink-muted">YES adds 1.0 penalty</p>
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

            {/* Step 4: Deterministic Scoring */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2.5 text-center shadow-card">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 4</span>
              <p className="text-xs font-bold text-ink">MetaQA Inconsistency Score</p>
              <p className="text-[10px] font-medium text-ink-secondary mt-0.5">S = (Mean SynScore + Mean AntScore) / 2</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 5: Classification */}
            <div className="w-full max-w-xs space-y-1.5">
              <div className="text-center text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
                Step 5: Classification (Threshold θ = 0.5)
              </div>
              <div className="grid grid-cols-2 gap-2 text-center text-xs">
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

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 6: Presentation */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Step 6</span>
              <p className="text-xs font-semibold text-ink">Results &amp; Verification Findings</p>
              <p className="text-[10px] text-ink-muted">Gemma answer, MetaQA score, independent model verdicts &amp; web evidence</p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Metamorphic Relations & Mutation Types */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Metamorphic Relations Explained</h2>
          <p className="mt-1 text-xs text-ink-muted">
            How controlled sentence transformations uncover internal logical inconsistencies.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            In classical testing, an oracle checks whether an output matches a known reference. In metamorphic
            testing, we test the relationships between outputs across transformed inputs. MetaQA defines two
            complementary metamorphic relations applied to the claims generated by the LLM:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-stretch">
            <MutationCard
              badge="S"
              title="Synonym Mutations (Meaning-Preserving)"
              badgeVariant="synonym"
              description={
                <>
                  Transforms the wording while maintaining the factual proposition (e.g., lexical substitution,
                  active/passive voice inversion, or syntactic rephrasing). If the model holds solid parametric knowledge,
                  it must agree with this variation.
                </>
              }
              original="Alexander Fleming discovered penicillin in 1928."
              mutation="Penicillin was identified by Alexander Fleming in the year 1928."
              expectedVerdict="YES"
              verdictVariant="reliable"
            />

            <MutationCard
              badge="A"
              title="Antonym & Negation Mutations (Meaning-Contradicting)"
              badgeVariant="antonym"
              description={
                <>
                  Inverts or contradicts the core factual proposition through explicit negation or contrasting
                  factual attributes. A consistent model must recognize that this statement conflicts with its answer.
                </>
              }
              original="Alexander Fleming discovered penicillin in 1928."
              mutation="Alexander Fleming did not discover penicillin in 1928."
              expectedVerdict="NO"
              verdictVariant="hallucinated"
            />
          </div>

          {/* Prompt Blindness Box */}
          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-surface-muted p-3.5 text-xs text-ink-secondary leading-relaxed space-y-1.5">
            <div className="flex items-center gap-1.5 font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-accent" />
              Verifier Blindness in VeriFact
            </div>
            <p>
              In VeriFact’s verifier implementation, the expected verdict (<code>YES</code> or <code>NO</code>)
              and the mutation classification (<code>synonym</code> vs. <code>antonym</code>) are{' '}
              <strong className="text-ink">never disclosed to the verifier</strong>. The verifier receives only
              the question, candidate answer, and the candidate statement, judging strictly whether the
              statement preserves or contradicts the answer. This guarantees objective evaluation without confirmation bias.
            </p>
          </div>
        </div>
      </section>

      {/* 5. Verifier Response Mapping and Scoring Logic */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Scoring Logic &amp; Mathematical Formulation</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Direct mapping of verifier labels to penalty contributions and overall hallucination score.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-5">
          <p className="text-sm leading-relaxed text-ink-secondary">
            The verifier evaluates each mutated statement and returns one of three discrete labels:{' '}
            <strong className="font-semibold text-ink">YES</strong>,{' '}
            <strong className="font-semibold text-ink">NO</strong>, or{' '}
            <strong className="font-semibold text-ink">NOT SURE</strong>. The backend assigns a numeric
            penalty based on whether the label violates the expected metamorphic relation:
          </p>

          {/* Scoring Mapping Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-line text-ink-muted">
                  <th className="pb-2 font-medium">Mutation Type</th>
                  <th className="pb-2 font-medium text-center">Expected</th>
                  <th className="pb-2 font-medium text-center">YES</th>
                  <th className="pb-2 font-medium text-center">NO</th>
                  <th className="pb-2 font-medium text-center">NOT SURE</th>
                  <th className="pb-2 font-medium">Scoring Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 text-ink-secondary">
                <tr>
                  <td className="py-2.5 font-medium text-ink">Synonym (S)</td>
                  <td className="py-2.5 text-center font-bold text-reliable">YES</td>
                  <td className="py-2.5 text-center font-bold text-reliable">0.0</td>
                  <td className="py-2.5 text-center font-bold text-hallucinated">1.0</td>
                  <td className="py-2.5 text-center font-medium text-uncertain">0.5</td>
                  <td className="py-2.5 text-[11px]">Rejection of equivalent statement indicates factual fragility.</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-medium text-ink">Antonym (A)</td>
                  <td className="py-2.5 text-center font-bold text-hallucinated">NO</td>
                  <td className="py-2.5 text-center font-bold text-hallucinated">1.0</td>
                  <td className="py-2.5 text-center font-bold text-reliable">0.0</td>
                  <td className="py-2.5 text-center font-medium text-uncertain">0.5</td>
                  <td className="py-2.5 text-[11px]">Acceptance of contradiction indicates fact-conflicting hallucination.</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Mathematical Formula Box */}
          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4 sm:p-5 space-y-4">
            <div className="text-center space-y-2.5">
              <p className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">
                Mathematical Score Formula (Equation 5, Yang et al.)
              </p>
              <div className="inline-flex flex-wrap items-center justify-center gap-x-2 gap-y-2 rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-3 shadow-xs text-xs sm:text-sm font-medium text-ink">
                <span className="font-semibold text-ink">S<sub>MetaQA</sub></span>
                <span className="text-ink-muted">=</span>
                <span className="inline-flex flex-col items-center justify-center text-[10px] sm:text-xs leading-none">
                  <span className="border-b border-line-strong px-1 pb-0.5">1</span>
                  <span className="px-1 pt-0.5">2</span>
                </span>
                <span className="text-ink-muted">&times;</span>
                <span className="text-base sm:text-lg text-ink-muted font-light">[</span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-flex flex-col items-center justify-center text-[10px] sm:text-xs leading-none">
                    <span className="border-b border-line-strong px-1 pb-0.5">1</span>
                    <span className="px-1 pt-0.5">N</span>
                  </span>
                  <span>&sum;<sub>i=1</sub><sup>N</sup> SynScore(S<sub>i</sub>)</span>
                </span>
                <span className="text-ink-muted">+</span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-flex flex-col items-center justify-center text-[10px] sm:text-xs leading-none">
                    <span className="border-b border-line-strong px-1 pb-0.5">1</span>
                    <span className="px-1 pt-0.5">M</span>
                  </span>
                  <span>&sum;<sub>j=1</sub><sup>M</sup> AntScore(A<sub>j</sub>)</span>
                </span>
                <span className="text-base sm:text-lg text-ink-muted font-light">]</span>
              </div>
            </div>

            <div className="border-t border-line/60 pt-3 space-y-2 text-xs text-ink-secondary leading-relaxed">
              <p className="font-medium text-ink">How to understand this formula:</p>
              <ul className="list-disc pl-4 space-y-1.5 text-[11px]">
                <li>
                  <strong className="text-ink">Synonym mutations</strong> measure whether meaning-preserving changes produce inconsistent responses (expected verdict: <code>YES</code>, penalty: 0.0).
                </li>
                <li>
                  <strong className="text-ink">Antonym and negation mutations</strong> test consistency under meaning-changing variations (expected verdict: <code>NO</code>, penalty: 0.0).
                </li>
                <li>
                  <strong className="text-ink">The final score</strong> combines the contributions from both mutation groups and remains bounded between <code>0.0</code> and <code>1.0</code>.
                </li>
              </ul>
              <p className="text-[11px] text-ink-muted pt-1">
                When the number of synonym mutations (<em>N</em>) equals antonym mutations (<em>M</em>) (the default is 3 each),
                this formula simplifies to the simple arithmetic average of all mutation penalties.
              </p>
            </div>
          </div>

          {/* Classification Threshold Rules */}
          <div className="grid gap-3 sm:grid-cols-2 text-xs">
            <div className="rounded border border-reliable/30 bg-reliable-soft/40 p-3 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-reliable">
                <CheckCircle2 className="h-4 w-4" />
                Score &lt; Threshold (default 0.5): Likely Reliable
              </div>
              <p className="text-ink-secondary">
                The verifier consistently affirmed meaning-preserving synonym statements and rejected contradictory
                antonym statements. The response demonstrates robust parametric consistency.
              </p>
            </div>
            <div className="rounded border border-hallucinated/30 bg-hallucinated-soft/40 p-3 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold text-hallucinated">
                <AlertTriangle className="h-4 w-4" />
                Score &ge; Threshold (default 0.5): Likely Hallucinated
              </div>
              <p className="text-ink-secondary">
                The model exhibited high inconsistency across variants (e.g. agreeing with contradictions or rejecting
                paraphrases), indicating a high probability of a fact-conflicting hallucination.
              </p>
            </div>
          </div>

          <p className="text-[11px] text-ink-muted leading-relaxed border-t border-line/60 pt-3">
            <strong>Error Handling &amp; Parsing:</strong> In the backend implementation, unparseable verifier payloads
            or timeouts in single-model mode default conservatively to <code>NOT SURE</code> (penalty <code>0.5</code>).
            In multi-verifier mode, network or API errors are isolated as <code>FAILED</code> and excluded from
            numerical aggregation so that transient provider issues never fabricate false penalties.
          </p>
        </div>
      </section>

      {/* 6. System Verification Architecture: Verified Execution Flow */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">System Verification Architecture</h2>
          <p className="mt-1 text-xs text-ink-muted">
            How MetaQA, Direct-Answer Multi-Model Review, and Web Evidence execute across the backend.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-stretch">
          <div className="panel p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                <Sparkles className="h-4 w-4" />
                1. MetaQA Pipeline
              </div>
              <h3 className="mt-1.5 text-xs font-bold text-ink">Metamorphic Mutation Testing</h3>
              <p className="mt-2 text-xs text-ink-secondary leading-5">
                Gemma 4:26B extracts factual claims and generates synonym, antonym, and negation mutations. The{' '}
                <strong className="text-ink">multi-model verifier pool</strong> (Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, and Liquid LFM-2.5)
                acts as the mutation verifier stage, evaluating every variant to compute the MetaQA Inconsistency Score.
              </p>
            </div>
            <div className="rounded bg-surface-muted p-2 text-[11px] text-ink-muted">
              <strong>Source:</strong> <code>metaqa/multi_verifier.py</code> &amp; <code>scoring.py</code>
            </div>
          </div>

          <div className="panel p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                <Layers className="h-4 w-4" />
                2. Direct-Answer Review
              </div>
              <h3 className="mt-1.5 text-xs font-bold text-ink">Independent Peer Evaluation</h3>
              <p className="mt-2 text-xs text-ink-secondary leading-5">
                In parallel, the same independent models evaluate Gemma’s original answer directly, receiving the
                user question, candidate answer, extracted claims, mutation context, and external web snippets to flag
                disagreements and contradictory statements.
              </p>
            </div>
            <div className="rounded bg-surface-muted p-2 text-[11px] text-ink-muted">
              <strong>Source:</strong> <code>independent_verifiers.py</code>
            </div>
          </div>

          <div className="panel p-4 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold text-accent">
                <Globe className="h-4 w-4" />
                3. Web Evidence
              </div>
              <h3 className="mt-1.5 text-xs font-bold text-ink">External Grounding Retrieval</h3>
              <p className="mt-2 text-xs text-ink-secondary leading-5">
                An independent pipeline that extracts factual claims, executes concurrent Tavily searches with multi-pass fallback,
                tiers sources by authority, and verifies claims strictly against retrieved snippets.
              </p>
            </div>
            <div className="rounded bg-surface-muted p-2 text-[11px] text-ink-muted">
              <strong>Source:</strong> <code>web_evidence/pipeline.py</code> &amp; <code>scoring.py</code>
            </div>
          </div>
        </div>

        <div className="panel p-4 bg-canvas/60 text-xs text-ink-secondary leading-relaxed space-y-2">
          <p>
            <strong className="text-ink font-semibold">Dual Role of Independent Models:</strong> In VeriFact, the non-Gemma
            models operate in two distinct architectural capacities:
          </p>
          <ol className="list-decimal pl-4 space-y-1 text-ink-secondary">
            <li>
              <strong>Inside the MetaQA Pipeline:</strong> They act as the mutation-verification stage in{' '}
              <code>verify_all_mutations_multi_model</code>, scoring every synonym, antonym, and negation statement to determine the
              MetaQA Inconsistency Score without knowledge of the expected verdict.
            </li>
            <li>
              <strong>In Direct-Answer Evaluation:</strong> They independently assess Gemma’s complete answer in{' '}
              <code>evaluate_all_independent_verifiers</code> (enriched with claim, mutation, and web snippet context) to
              produce a transparent peer consensus summary without altering the MetaQA score.
            </li>
          </ol>
        </div>
      </section>

      {/* 7. Research Paper vs VeriFact Comparison Table */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Research Paper vs. VeriFact Implementation</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Detailed mapping between the original FSE 2025 paper and the VeriFact system.
          </p>
        </div>

        <ResearchComparisonTable
          researchHeader="MetaQA Research (Yang et al., FSE 2025)"
          implementationHeader="VeriFact Production Implementation"
          rows={metaqaComparisonRows}
          note="VeriFact implements the core mathematical and conceptual principles of MetaQA (metamorphic relations, synonym/antonym mutations, and Eq. 5 scoring). VeriFact incorporates fixed Gemma answer generation, cross-model verifier blindness, independent multi-model peer review, and parallel web evidence retrieval as specialized system extensions."
        />
      </section>

      {/* 8. Scientific Limitations & Practical Considerations */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Scientific Limitations &amp; Considerations</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Key operational constraints and practical considerations when interpreting results.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4 text-xs leading-relaxed text-ink-secondary">
          <ul className="list-disc pl-4 space-y-2.5">
            <li>
              <strong className="text-ink">Consistency Does Not Prove Factual Correctness:</strong> Metamorphic testing
              evaluates internal semantic invariance. An AI model that firmly holds a widespread factual misconception
              or incorrect belief can answer consistently across variations and negations while remaining factually
              wrong in reality.
            </li>
            <li>
              <strong className="text-ink">Model Agreement is Not Proof of Truth:</strong> When independent verifier
              models agree, it demonstrates high consensus among today’s frontier architectures, but cannot be treated
              as mathematical proof of ground truth.
            </li>
            <li>
              <strong className="text-ink">Mutation Quality &amp; Nuance:</strong> The accuracy of MetaQA depends on the
              linguistic quality of generated mutations. If a synonym generator inadvertently alters subtle semantics or
              an antonym generator creates ambiguous phrasing, the verifier’s score can be impacted.
            </li>
            <li>
              <strong className="text-ink">Non-Calibrated Heuristic Metric:</strong> The MetaQA Inconsistency Score is
              a deterministic, method-specific heuristic metric measuring metamorphic stability, not a calibrated Bayesian
              probability that the statement is true.
            </li>
          </ul>
        </div>
      </section>
    </div>
  )
}
