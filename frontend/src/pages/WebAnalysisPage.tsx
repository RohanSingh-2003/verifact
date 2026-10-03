import { ArrowDown, ArrowRight, Check, Circle, X } from 'lucide-react'
import { PageHeader } from '../components/ui/PageHeader'
import { ResearchComparisonTable, type ComparisonRow } from '../components/research/ResearchComparisonTable'

const claimCheckComparisonRows: ComparisonRow[] = [
  {
    dimension: 'Input',
    research: 'Raw user or benchmark claim (AVeriTeC dataset)',
    implementation: 'Free-form AI-generated answer to a user question',
  },
  {
    dimension: 'Claim Processing',
    research: 'Claim-matching against trusted fact-checkers + novel claim reformulation',
    implementation: 'Dynamic claim extraction decomposing the AI response into atomic claims',
  },
  {
    dimension: 'Question / Query Generation',
    research: 'LLM generates targeted questions then converts them to search queries',
    implementation: 'Direct conversion of extracted claims into keyword queries with domain strategies',
  },
  {
    dimension: 'Web Search',
    research: 'Google Search via Serper API + Google Programmable Search',
    implementation: 'Tavily Search API with specialized depth and domain filters',
  },
  {
    dimension: 'Evidence Retrieval',
    research: 'Full web page scraping via Trafilatura + QA answering + LLM curation',
    implementation: 'Curated search snippets + domain credibility tiering',
  },
  {
    dimension: 'Evidence Evaluation',
    research: 'Fine-tuned Qwen2.5-7B LoRA model predicting 4 AVeriTeC classes',
    implementation: 'Zero-shot JSON verifier with strict evidence-only reasoning rules',
  },
  {
    dimension: 'Final Verdict',
    research: 'Supported, Refuted, Conflicting Evidence, Not Enough Evidence',
    implementation: 'Supported, Contradicted, Insufficient Evidence (per claim)',
  },
  {
    dimension: 'Purpose',
    research: 'Automated fact-checking of public claims and misinformation',
    implementation: 'Verifying claims from AI answers as part of dual-signal hallucination detection',
  },
]

const inspectableFields = [
  { label: 'Claim', desc: 'The extracted factual statement under evaluation' },
  { label: 'Verdict', desc: 'Supported, Contradicted, or Insufficient evidence' },
  { label: 'Explanation', desc: 'Clear reasoning comparing the claim against retrieved evidence' },
  { label: 'Source title', desc: 'Descriptive title of the cited web page or article' },
  { label: 'Source domain', desc: 'Originating domain and prioritized source tier' },
  { label: 'Source link / snippet', desc: 'Direct URL to source material and relevant excerpt' },
]

export function WebAnalysisPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      {/* 1. Header */}
      <header>
        <PageHeader
          title="Web Analysis"
          description="How VeriFact checks factual claims from an AI-generated answer using external web evidence."
        />
        <div className="mt-2 space-y-1">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            <span>
              Related research: <strong className="font-medium text-ink-secondary">Putta et al., KnowledgeNLP 2025</strong> —{' '}
              <em>ClaimCheck: Automatic Fact-Checking of Textual Claims using Web Evidence</em>
            </span>
          </div>
          <div className="pl-3.5">
            <a
              href="https://aclanthology.org/2025.knowledgenlp-1.26/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-xs font-medium text-ink-muted underline-offset-4 hover:text-ink hover:underline"
            >
              View research paper →
            </a>
          </div>
        </div>
      </header>

      {/* 2. What is Web Analysis? */}
      <section className="panel p-5 sm:p-6 space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">What is Web Analysis?</h2>
        <p className="text-sm leading-7 text-ink-secondary">
          Web Analysis checks factual claims from an AI-generated answer against relevant information
          found on the web.
        </p>
        <p className="text-sm leading-7 text-ink-secondary border-t border-line/60 pt-3">
          VeriFact uses this as a separate verification branch alongside MetaQA. Instead of relying
          solely on the model&apos;s internal reasoning, VeriFact retrieves external evidence and evaluates
          whether that evidence supports, contradicts, or is insufficient to verify each claim.
        </p>
      </section>

      {/* 3. Core Web Evidence Workflow Diagram */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Core Web Evidence Workflow</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The sequential pipeline from user prompt to external evidence verification.
          </p>
        </div>

        <div className="panel p-5 sm:p-6">
          <div className="mx-auto flex max-w-md flex-col items-center">
            {/* Step 1: AI Question */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Input</span>
              <p className="text-xs font-semibold text-ink">AI Question</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 2: AI Generated Answer */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Generation</span>
              <p className="text-xs font-semibold text-ink">AI Generated Answer</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 3: Claim Extraction */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                Extraction
              </span>
              <p className="text-xs font-semibold text-ink">Claim Extraction</p>
              <p className="text-[10px] text-ink-muted">Break answer into atomic testable statements</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 4: Search Query */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Query Formulation</span>
              <p className="text-xs font-semibold text-ink">Search Query Generation</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 5: Web Search (Tavily) */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Search Provider</span>
              <p className="text-xs font-semibold text-ink">Web Search via Tavily</p>
              <p className="text-[10px] text-ink-muted">Search trusted web sources with domain tiering</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 6: Retrieved Evidence */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Sources</span>
              <p className="text-xs font-semibold text-ink">Retrieved Evidence Snippets</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 7: Evidence Verification */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2 text-center shadow-card">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Evaluation</span>
              <p className="text-xs font-bold text-ink">Evidence Verification</p>
              <p className="text-[10px] text-ink-muted">Compare claim strictly against snippet text</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 8: Verdict Output */}
            <div className="grid w-full max-w-md grid-cols-3 gap-2 text-center text-xs">
              <div className="rounded-[var(--radius-sm)] border border-reliable/30 bg-reliable-soft p-2">
                <span className="text-[10px] font-bold text-reliable uppercase">SUPPORTED</span>
                <p className="mt-0.5 text-[9px] text-ink-secondary">Evidence agrees</p>
              </div>
              <div className="rounded-[var(--radius-sm)] border border-hallucinated/30 bg-hallucinated-soft p-2">
                <span className="text-[10px] font-bold text-hallucinated uppercase">CONTRADICTED</span>
                <p className="mt-0.5 text-[9px] text-ink-secondary">Evidence conflicts</p>
              </div>
              <div className="rounded-[var(--radius-sm)] border border-uncertain/30 bg-uncertain-soft p-2">
                <span className="text-[10px] font-bold text-uncertain uppercase">INSUFFICIENT</span>
                <p className="mt-0.5 text-[9px] text-ink-secondary">Evidence inconclusive</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Claim Extraction */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Claim Extraction</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Deconstructing paragraph-length AI answers into checkable propositions.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            An AI answer can contain several factual statements. VeriFact identifies the claims that can
            be checked separately. Rather than treating a compound response as a monolith, atomic
            decomposition isolates specific factual anchors (such as dates, locations, numbers, or
            events).
          </p>

          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Example Breakdown</p>
            <div className="space-y-2 text-xs">
              <div>
                <p className="font-medium text-ink">AI Answer:</p>
                <p className="mt-0.5 text-ink-secondary italic">
                  &ldquo;New Delhi is the capital of India. It is also the seat of the Indian government.&rdquo;
                </p>
              </div>
              <div className="grid gap-2 border-t border-line/60 pt-2.5 sm:grid-cols-2">
                <div className="rounded border border-line bg-surface p-2.5">
                  <span className="font-semibold text-ink">Claim 1:</span>
                  <p className="mt-1 text-ink-secondary">&ldquo;New Delhi is the capital of India.&rdquo;</p>
                </div>
                <div className="rounded border border-line bg-surface p-2.5">
                  <span className="font-semibold text-ink">Claim 2:</span>
                  <p className="mt-1 text-ink-secondary">&ldquo;New Delhi is the seat of the Indian government.&rdquo;</p>
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-surface-muted p-3 text-xs text-ink-secondary leading-relaxed">
            <strong className="font-semibold text-ink">VeriFact Implementation:</strong> VeriFact uses an
            LLM prompt with strict validation rules to extract atomic, self-contained factual sentences.
            It filters out greetings, pure conversational filler, vague conclusions, and duplicate
            claims, ensuring only verifiable statements enter the search pipeline.
          </div>
        </div>
      </section>

      {/* 5. Search / Evidence Retrieval */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Search & Evidence Retrieval</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Translating claims into targeted web queries with prioritized sources.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            For each claim, VeriFact searches the web for relevant evidence. Direct natural-language claims
            often make poor search engine queries, so VeriFact formulates focused keyword queries.
          </p>

          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-center text-xs">
              <div className="w-full sm:w-auto flex-1 rounded border border-line bg-surface p-2 font-medium text-ink">
                Factual Claim
              </div>
              <ArrowRight className="h-4 w-4 text-ink-muted hidden sm:block shrink-0" />
              <ArrowDown className="h-4 w-4 text-ink-muted sm:hidden shrink-0" />
              <div className="w-full sm:w-auto flex-1 rounded border border-line bg-surface p-2 font-medium text-ink">
                Targeted Query
              </div>
              <ArrowRight className="h-4 w-4 text-ink-muted hidden sm:block shrink-0" />
              <ArrowDown className="h-4 w-4 text-ink-muted sm:hidden shrink-0" />
              <div className="w-full sm:w-auto flex-1 rounded border border-emerald-500/30 bg-emerald-500/10 p-2 font-semibold text-emerald-700 dark:text-emerald-400">
                Tavily Search
              </div>
              <ArrowRight className="h-4 w-4 text-ink-muted hidden sm:block shrink-0" />
              <ArrowDown className="h-4 w-4 text-ink-muted sm:hidden shrink-0" />
              <div className="w-full sm:w-auto flex-1 rounded border border-line bg-surface p-2 font-medium text-ink">
                Relevant Evidence
              </div>
            </div>
          </div>

          <div className="space-y-2 text-xs text-ink-secondary leading-relaxed">
            <p>
              <strong className="font-semibold text-ink">Search Provider:</strong> VeriFact uses{' '}
              <strong className="font-semibold text-ink">Tavily</strong> as its current search provider.
              Tavily is an AI-optimized search engine designed to extract relevant snippets from web
              pages.
            </p>
            <p>
              <strong className="font-semibold text-ink">Important distinction:</strong> Tavily does NOT
              decide whether a claim is true or false. Tavily merely retrieves candidate information from
              the web. The subsequent verification stage independently evaluates the relationship
              between the claim and the retrieved text.
            </p>
          </div>
        </div>
      </section>

      {/* 6. Evidence Verification */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Evidence Verification</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Grounding truth judgments strictly in retrieved textual excerpts.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            Retrieved evidence is compared with the claim to determine whether the available information
            supports it, contradicts it, or is not enough to decide.
          </p>

          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4">
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 text-center text-xs">
              <div className="rounded border border-line bg-surface px-4 py-2 font-medium text-ink">
                Claim + Retrieved Evidence
              </div>
              <ArrowRight className="h-4 w-4 text-ink-muted hidden sm:block shrink-0" />
              <ArrowDown className="h-4 w-4 text-ink-muted sm:hidden shrink-0" />
              <div className="rounded border border-accent/30 bg-accent-soft px-4 py-2 font-semibold text-accent">
                Evidence Evaluation
              </div>
              <ArrowRight className="h-4 w-4 text-ink-muted hidden sm:block shrink-0" />
              <ArrowDown className="h-4 w-4 text-ink-muted sm:hidden shrink-0" />
              <div className="rounded border border-line bg-surface px-4 py-2 font-semibold text-ink">
                Verdict & Reasoning
              </div>
            </div>
          </div>

          <div className="rounded-[var(--radius-sm)] border border-line/80 bg-surface-muted p-3 text-xs text-ink-secondary leading-relaxed">
            <strong className="font-semibold text-ink">Verification Rules:</strong> VeriFact instructs the
            verifier to judge solely from snippet text. It must never use prior ungrounded assumptions,
            never treat the absence of search results as a contradiction, and never cite a domain or URL
            as proof without corroborating snippet content.
          </div>
        </div>
      </section>

      {/* 7. Verdict Types */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Evidence Verdict Types</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Three mutually exclusive categories for claim evaluation.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-stretch">
          {/* Supported */}
          <div className="panel p-5 flex flex-col h-full border-l-4 border-l-reliable">
            <div className="flex items-center gap-2 mb-2.5">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-reliable-soft text-reliable" aria-hidden="true">
                <Check className="h-3 w-3" />
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-reliable">
                Supported
              </span>
            </div>
            <p className="flex-1 text-xs leading-5 text-ink-secondary">
              The available evidence supports the claim. A retrieved snippet explicitly confirms the same
              factual content.
            </p>
          </div>

          {/* Contradicted */}
          <div className="panel p-5 flex flex-col h-full border-l-4 border-l-hallucinated">
            <div className="flex items-center gap-2 mb-2.5">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-hallucinated-soft text-hallucinated" aria-hidden="true">
                <X className="h-3 w-3" />
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-hallucinated">
                Contradicted
              </span>
            </div>
            <p className="flex-1 text-xs leading-5 text-ink-secondary">
              The available evidence conflicts with the claim. A retrieved snippet explicitly states an
              incompatible fact about the subject.
            </p>
          </div>

          {/* Insufficient */}
          <div className="panel p-5 flex flex-col h-full border-l-4 border-l-uncertain">
            <div className="flex items-center gap-2 mb-2.5">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-uncertain-soft text-uncertain" aria-hidden="true">
                <Circle className="h-3 w-3" />
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-uncertain">
                Insufficient Evidence
              </span>
            </div>
            <p className="flex-1 text-xs leading-5 text-ink-secondary">
              The available evidence is not enough to confidently verify the claim. Snippets may be
              missing, off-topic, or too vague.
            </p>
          </div>
        </div>

        <p className="text-xs text-ink-muted">
          Note: These verdicts reflect available online documentation. They are evidence categories,
          not calibrated hallucination probabilities.
        </p>
      </section>

      {/* 8. Sources */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Source Transparency & Metadata</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Every verified claim links directly to its underlying citations in the UI.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            VeriFact displays detailed citation information in the Web Evidence panel so that results
            can be independently checked and audited.
          </p>

          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/60 p-4">
            <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-3">
              Inspectable Fields in the Web Evidence Panel
            </p>
            <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 text-xs text-ink-secondary">
              {inspectableFields.map((field) => (
                <li key={field.label} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  <span>
                    <strong className="font-semibold text-ink">{field.label}:</strong> {field.desc}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="text-xs leading-relaxed text-ink-secondary space-y-1.5 border-t border-line/60 pt-3">
            <p className="font-medium text-ink">Source Quality Tiers:</p>
            <p className="text-ink-muted">
              VeriFact classifies web sources into prioritized quality tiers: <em>Official / Primary</em>,{' '}
              <em>Government</em>, <em>Academic</em>, <em>Reputable News</em>, <em>Reference</em>, and{' '}
              <em>General Web</em>.
            </p>
          </div>
        </div>
      </section>

      {/* 9. ClaimCheck vs VeriFact Comparison */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Research Approach vs VeriFact</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Comparing ClaimCheck (Putta et al., 2025) with VeriFact&apos;s Web Analysis.
          </p>
        </div>

        <ResearchComparisonTable
          researchHeader="ClaimCheck (Putta et al., KnowledgeNLP 2025)"
          implementationHeader="VeriFact Web Analysis"
          rows={claimCheckComparisonRows}
          note="ClaimCheck is an automated fact-checking system for textual claims benchmarked on AVeriTeC. VeriFact applies a related evidence-retrieval approach specifically to claims extracted from AI-generated answers, optimized for real-time interactive hallucination detection."
        />
      </section>

      {/* 10. How Web Analysis fits into VeriFact */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">How Web Analysis Fits into VeriFact</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The dual-branch architecture combining internal consistency with external evidence.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-5">
          {/* Dual Branch Flow Diagram */}
          <div className="mx-auto flex max-w-md flex-col items-center">
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-4 py-2.5 text-center shadow-card">
              <p className="text-xs font-bold text-ink">AI Generated Answer</p>
              <p className="text-[10px] text-ink-muted">Single candidate answer under test</p>
            </div>

            {/* Split */}
            <div className="w-full max-w-sm pt-2">
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

              <div className="mt-1 grid grid-cols-2 gap-4">
                {/* MetaQA Branch */}
                <div className="flex flex-col items-center space-y-1.5 rounded-[var(--radius-sm)] border border-line bg-canvas p-3 text-center">
                  <p className="text-xs font-bold text-ink">MetaQA</p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <p className="text-[11px] text-ink-secondary">Controlled changes</p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <p className="text-[11px] font-medium text-accent">Consistency check</p>
                </div>

                {/* Web Analysis Branch */}
                <div className="flex flex-col items-center space-y-1.5 rounded-[var(--radius-sm)] border border-line bg-canvas p-3 text-center">
                  <p className="text-xs font-bold text-ink">Web Analysis</p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <p className="text-[11px] text-ink-secondary">External evidence</p>
                  <ArrowDown className="h-3 w-3 text-ink-muted" />
                  <p className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400">Claim verification</p>
                </div>
              </div>

              {/* Converge */}
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

            {/* Findings */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2.5 text-center shadow-card">
              <p className="text-xs font-bold text-ink">VeriFact Findings</p>
              <p className="mt-0.5 text-[10px] text-ink-muted">Two independent perspectives presented together</p>
            </div>
          </div>

          {/* Explanation */}
          <div className="grid gap-3 sm:grid-cols-2 text-xs border-t border-line/60 pt-4">
            <div className="rounded border border-line bg-canvas/60 p-3 space-y-1">
              <span className="font-semibold text-ink">MetaQA answers:</span>
              <p className="text-ink-secondary italic">
                &ldquo;Does the model behave consistently when the answer is deliberately changed?&rdquo;
              </p>
            </div>
            <div className="rounded border border-line bg-canvas/60 p-3 space-y-1">
              <span className="font-semibold text-ink">Web Analysis answers:</span>
              <p className="text-ink-secondary italic">
                &ldquo;Does available external evidence support or contradict the factual claims?&rdquo;
              </p>
            </div>
          </div>

          <p className="text-xs text-ink-muted leading-relaxed">
            MetaQA and Web Analysis answer different questions. VeriFact does not force their results into
            a single artificial mathematical score. Instead, both signals are displayed side by side so
            users can evaluate whether an answer is internally inconsistent, contradicted by web sources,
            or both.
          </p>
        </div>
      </section>
    </div>
  )
}
