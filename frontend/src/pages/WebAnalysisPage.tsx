import {
  ArrowDown,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Globe,
  ShieldCheck,
  Layers,
  Sparkles,
} from 'lucide-react'
import { PageHeader } from '../components/ui/PageHeader'
import { ResearchComparisonTable, type ComparisonRow } from '../components/research/ResearchComparisonTable'

const claimCheckComparisonRows: ComparisonRow[] = [
  {
    dimension: 'Core Input',
    research: 'Benchmark claims from the AVeriTeC dataset (fact-checking public misinformation)',
    implementation: 'Factual claims extracted from Gemma 4:26B’s generated answer to a user question',
  },
  {
    dimension: 'Claim Decomposition',
    research: 'Claim-matching against existing fact-checking articles + few-shot question generation',
    implementation: 'Atomic claim extraction using structured LLM prompts filtering opinions, greetings, and duplicates',
  },
  {
    dimension: 'Search Formulation',
    research: 'Sub-question generation converted into queries across Google Serper & Programmable Search',
    implementation: 'Keyword-optimized queries stripping function words and prioritizing named entities, dates, and locations',
  },
  {
    dimension: 'Search Provider',
    research: 'Google Search via Serper API + Google Programmable Search',
    implementation: 'Tavily Search API with multi-pass retrieval, domain strategy routing, and ranked merging',
  },
  {
    dimension: 'Evidence Ingestion',
    research: 'Full web page scraping via Trafilatura, followed by QA model extraction and BM25 reranking',
    implementation: 'Direct snippet ingestion with source authority classification, 6-tier domain ranking, and topical relevance filtering',
  },
  {
    dimension: 'Verification Model',
    research: 'Fine-tuned Qwen2.5-7B LoRA predicting 4 AVeriTeC classes',
    implementation: 'Zero-shot evidence verifier prompted with strict evidence-only reasoning and compound-claim checks',
  },
  {
    dimension: 'Verdict Taxonomy',
    research: 'Supported, Refuted, Conflicting Evidence, Not Enough Evidence',
    implementation: 'SUPPORTED (1.0), CONTRADICTED (0.0), INSUFFICIENT_EVIDENCE (0.5), and NOT_ASSESSED_NO_RELEVANT_SOURCE (excluded from score)',
  },
  {
    dimension: 'Scoring Formulation',
    research: 'Discrete classification accuracy and macro-F1 on benchmark test splits',
    implementation: 'Deterministic Web Evidence Consistency Score: mean contribution in [0.0, 1.0] across assessed claims (excluding unassessed claims), mapped to 7 categorical verdicts',
  },
  {
    dimension: 'System Role',
    research: 'Standalone automated fact-checking system for public internet claims',
    implementation: 'Independent external grounding pillar running in parallel with MetaQA and multi-model review',
  },
]

const sourceQualityTiers = [
  {
    tier: 'Tier 1: Primary & Official',
    description: 'Government agencies (.gov, .nic.in, .gov.au), international bodies (UN, WHO), and official organizational portals.',
    badgeClass: 'text-[#2d6350] bg-[#eef6f2] border-[#cbe3d7] dark:text-[#7fbaa6] dark:bg-[#162720] dark:border-[#274639]',
  },
  {
    tier: 'Tier 2: Academic & Research',
    description: 'Universities (.edu, .ac.in), peer-reviewed repositories, scientific databases, and research institutions.',
    badgeClass: 'text-[#325b7a] bg-[#eef4f8] border-[#cce0ec] dark:text-[#8cb8d8] dark:bg-[#162633] dark:border-[#263e52]',
  },
  {
    tier: 'Tier 3: Reputable News & Fact-Check',
    description: 'Established journalistic organizations (Reuters, AP, BBC, The Hindu) and certified fact-checking outlets.',
    badgeClass: 'text-[#5a4e75] bg-[#f3f0f7] border-[#d8d0e5] dark:text-[#afa5cf] dark:bg-[#221c2e] dark:border-[#3d3350]',
  },
  {
    tier: 'Tier 4: Reference & Encyclopedias',
    description: 'Curated knowledge repositories, encyclopedias (Wikipedia, Britannica), and structured reference bases.',
    badgeClass: 'text-[#6e5833] bg-[#f6f2ec] border-[#e2d8c7] dark:text-[#cfbd9a] dark:bg-[#292217] dark:border-[#443825]',
  },
  {
    tier: 'Tier 5: General Web',
    description: 'General online publications, commercial domains, industry blogs, and standard internet articles.',
    badgeClass: 'text-[#5c5750] bg-[#f2efe9] border-[#ded9cf] dark:text-[#a69f93] dark:bg-[#201d19] dark:border-[#38332c]',
  },
  {
    tier: 'Tier 6: Low Priority',
    description: 'Marketing aggregators, user forums, content farms, and unverified blogs (deprioritized in retrieval).',
    badgeClass: 'text-[#7d776e] bg-[#f7f5f1] border-[#e5e0d7] dark:text-[#888176] dark:bg-[#191715] dark:border-[#2b2723]',
  },
]

const inspectableFields = [
  { label: 'Claim Text', desc: 'The exact atomic factual proposition extracted from Gemma’s answer.' },
  { label: 'Verdict Badge', desc: 'SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE, or NOT_ASSESSED_NO_RELEVANT_SOURCE with distinct visual cues.' },
  { label: 'Verifier Explanation', desc: 'Concise explanation identifying which facts substantiate, refute, or remain unassessed.' },
  { label: 'Source Title & URL', desc: 'Direct hyperlink and title of the external web document cited as evidence.' },
  { label: 'Domain & Quality Tier', desc: 'Classified domain authority (Tiers 1–6) and topical relevance score (threshold ≥ 0.20).' },
  { label: 'Snippet Excerpt', desc: 'Verbatim excerpt extracted by Tavily from the source page used to ground the verdict.' },
]

export function WebAnalysisPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-10">
      {/* 1. Header & Research Attribution */}
      <header>
        <PageHeader
          title="Web Analysis"
          description="How VeriFact verifies factual claims from an AI-generated answer against external web evidence."
        />
        <div className="mt-2 space-y-1">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
            <span>
              Academic Context: <strong className="font-medium text-ink-secondary">Putta et al., KnowledgeNLP 2025</strong> —{' '}
              <em>ClaimCheck: Automatic Fact-Checking of Textual Claims using Web Evidence</em>
            </span>
          </div>
          <div className="pl-3.5">
            <a
              href="https://aclanthology.org/2025.knowledgenlp-1.26/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-xs font-medium text-accent underline-offset-4 hover:underline"
            >
              ACL Anthology Paper (KnowledgeNLP @ COLING 2025) →
            </a>
          </div>
        </div>
      </header>

      {/* 2. What is Web Analysis? */}
      <section className="panel p-5 sm:p-6 space-y-3">
        <h2 className="text-sm font-semibold tracking-tight text-ink">What is Web Analysis?</h2>
        <p className="text-sm leading-7 text-ink-secondary">
          Web Analysis checks the factual claims in an AI answer against relevant information found online.
          It helps identify claims that are supported, contradicted, or not sufficiently verified by the available evidence.
        </p>
        <p className="text-sm leading-7 text-ink-secondary border-t border-line/60 pt-3">
          VeriFact decomposes the answer generated by Gemma 4:26B into testable, atomic propositions,
          queries the web using the Tavily Search API, prioritizes sources across six quality tiers, and evaluates each
          claim strictly against retrieved snippets. Claims with no relevant sources passing the relevance gate
          are marked as not assessed, rather than automatically classified as true or false.
        </p>
      </section>

      {/* 3. The 5-Step Web Evidence Workflow */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Web Evidence Workflow</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The 5-step evidence-grounding workflow executed by the backend pipeline from question to verified claims.
          </p>
        </div>

        <div className="panel p-5 sm:p-6">
          <div className="mx-auto flex max-w-md flex-col items-center">
            {/* Step 1: Claim Extraction */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2.5 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Step 1</span>
              <p className="text-xs font-semibold text-ink">Extract Factual Claims</p>
              <p className="text-[10px] text-ink-muted">Decomposes Gemma 4:26B’s answer into atomic factual claims</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 2: Multi-Pass Tavily Search */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-accent/40 bg-accent-soft/30 px-3.5 py-2.5 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">
                Step 2
              </span>
              <p className="text-xs font-semibold text-ink">Retrieve Evidence via Tavily</p>
              <p className="text-[10px] text-ink-muted">Executes targeted searches with multi-pass fallback for thin coverage</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 3: Source Relevance & Quality Evaluation */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2.5 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Step 3</span>
              <p className="text-xs font-semibold text-ink">Evaluate Source Relevance &amp; Quality</p>
              <p className="text-[10px] text-ink-muted">Filters off-topic snippets (threshold ≥ 0.20) &amp; ranks across 6 authority tiers</p>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 4: Compare Evidence & Verify Claims */}
            <div className="w-full max-w-md space-y-2">
              <div className="rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2 text-center shadow-card">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Step 4</span>
                <p className="text-xs font-bold text-ink">Compare Evidence Against Claims</p>
                <p className="text-[10px] text-ink-muted">Strict snippet reasoning with compound-claim coverage checks</p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-center text-xs">
                <div className="rounded-[var(--radius-sm)] border border-reliable/30 bg-reliable-soft p-1.5">
                  <span className="text-[9px] font-bold text-reliable uppercase block">SUPPORTED</span>
                  <p className="text-[9px] font-mono text-reliable mt-0.5">+1.0 score</p>
                </div>
                <div className="rounded-[var(--radius-sm)] border border-hallucinated/30 bg-hallucinated-soft p-1.5">
                  <span className="text-[9px] font-bold text-hallucinated uppercase block">CONTRADICTED</span>
                  <p className="text-[9px] font-mono text-hallucinated mt-0.5">0.0 score</p>
                </div>
                <div className="rounded-[var(--radius-sm)] border border-uncertain/30 bg-uncertain-soft p-1.5">
                  <span className="text-[9px] font-bold text-uncertain uppercase block">INSUFFICIENT</span>
                  <p className="text-[9px] font-mono text-uncertain mt-0.5">+0.5 score</p>
                </div>
                <div className="rounded-[var(--radius-sm)] border border-line bg-surface-muted p-1.5">
                  <span className="text-[9px] font-bold text-ink-secondary uppercase block">NOT ASSESSED</span>
                  <p className="text-[9px] text-ink-muted mt-0.5">Excluded from score</p>
                </div>
              </div>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Step 5: Presentation & Consistency Score */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-line bg-canvas px-3.5 py-2.5 text-center">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Step 5</span>
              <p className="text-xs font-semibold text-ink">Present Assessments &amp; Consistency Score</p>
              <p className="text-[10px] text-ink-muted">Displays score, categorical verdict, and inspectable citations</p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Claim Extraction & Query Formulation */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Claim Extraction &amp; Query Formulation</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Transforming free-form AI text into independently verifiable search queries.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            Paragraph-length AI answers typically bundle multiple factual propositions together. VeriFact
            isolates up to 3 core claims, ensuring that long narrative descriptions are broken down into
            atomic factual sentences before search.
          </p>

          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted">Decomposition Pipeline</p>
            <div className="space-y-2 text-xs">
              <div>
                <p className="font-medium text-ink">Generated Answer:</p>
                <p className="mt-0.5 text-ink-secondary italic">
                  &ldquo;Canberra is the capital city of Australia, situated within the Australian Capital Territory
                  which forms an enclave entirely within New South Wales.&rdquo;
                </p>
              </div>
              <div className="grid gap-2 border-t border-line/60 pt-2.5 sm:grid-cols-2">
                <div className="rounded border border-line bg-surface p-2.5 space-y-1">
                  <span className="font-semibold text-ink">Extracted Claim 1:</span>
                  <p className="text-ink-secondary">&ldquo;Canberra is the capital city of Australia.&rdquo;</p>
                  <p className="text-[10px] text-accent font-mono">Query: &ldquo;Canberra capital city Australia&rdquo;</p>
                </div>
                <div className="rounded border border-line bg-surface p-2.5 space-y-1">
                  <span className="font-semibold text-ink">Extracted Claim 2:</span>
                  <p className="text-ink-secondary">&ldquo;The Australian Capital Territory is an enclave within New South Wales.&rdquo;</p>
                  <p className="text-[10px] text-accent font-mono">Query: &ldquo;Australian Capital Territory enclave New South Wales&rdquo;</p>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-2 text-xs text-ink-secondary leading-relaxed border-t border-line/60 pt-3">
            <p>
              <strong className="text-ink">Query Optimization:</strong> Rather than passing raw conversational sentences
              to search engines, VeriFact strips grammatical stop words while preserving named entities, dates, numbers,
              and geographical qualifiers.
            </p>
            <p>
              <strong className="text-ink">Multi-Pass Retrieval &amp; Ranked Merging:</strong> Pass 1 executes targeted
              searches with authoritative domain routing. If initial results yield zero hits, unusable snippets, or fail
              topical relevance, an automated Pass 2 executes with query reformulations or broader search parameters.
              Hits are merged, deduplicated, and ranked by composite priority.
            </p>
          </div>
        </div>
      </section>

      {/* 5. Source Quality Tiers & Authority */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Source Quality Tiers &amp; Authority</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Hierarchical classification of retrieved domains to prioritize primary documentation.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            Not all search results carry equal evidential weight. VeriFact inspects retrieved URLs and
            categorizes sources into six prioritized quality tiers:
          </p>

          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {sourceQualityTiers.map((item) => (
              <div
                key={item.tier}
                className="rounded-[var(--radius-sm)] border border-line/80 bg-surface/80 p-3.5 space-y-2 transition-colors hover:border-line-strong"
              >
                <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-semibold border ${item.badgeClass}`}>
                  {item.tier}
                </span>
                <p className="text-[11px] leading-relaxed text-ink-secondary">{item.description}</p>
              </div>
            ))}
          </div>

          <div className="space-y-1.5 text-[11px] text-ink-muted leading-relaxed border-t border-line/60 pt-3">
            <p>
              <strong className="text-ink">Composite Priority Ranking:</strong> Sources are prioritized by tier rank
              (Tier 1 Primary &amp; Official &lt; Tier 2 Academic &lt; &hellip; &lt; Tier 6 Low Priority) merged with topical
              relevance scores. Low-priority content farms, marketing aggregators, and unverified blogs are deprioritized
              when authoritative sources are available.
            </p>
            <p>
              <strong className="text-ink">Domain Strategy Routing:</strong> The pipeline identifies question types
              (e.g., Medical, Legal, Historical, Geographical) and attaches specialized authority domain filters
              (e.g., routing Indian governance queries through official <code>.gov.in</code> portals).
            </p>
          </div>
        </div>
      </section>

      {/* 6. Evidence Verification Rules & Status Taxonomy */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Evidence Verification Rules</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Strict snippet-only reasoning rules governing claim assessments and verdicts.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-5">
          <p className="text-sm leading-relaxed text-ink-secondary">
            VeriFact sends retrieved snippets and claims to the verifier with strict instructions prohibiting
            unsupported assumptions. Claims receive one of four distinct outcomes:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-stretch">
            {/* SUPPORTED */}
            <div className="panel p-3.5 flex flex-col justify-between border-l-4 border-l-reliable space-y-2">
              <div>
                <div className="flex items-center gap-1.5 mb-1 text-reliable font-bold text-xs uppercase tracking-wide">
                  <CheckCircle2 className="h-4 w-4" />
                  SUPPORTED
                </div>
                <p className="text-[11px] text-ink-secondary leading-4">
                  Reliable evidence directly establishes the claim or confirms it through unambiguous inference.
                  Valid paraphrases qualify.
                </p>
              </div>
              <div className="rounded bg-reliable-soft p-1 text-[10px] font-semibold text-reliable text-center">
                Contribution: +1.0
              </div>
            </div>

            {/* CONTRADICTED */}
            <div className="panel p-3.5 flex flex-col justify-between border-l-4 border-l-hallucinated space-y-2">
              <div>
                <div className="flex items-center gap-1.5 mb-1 text-hallucinated font-bold text-xs uppercase tracking-wide">
                  <XCircle className="h-4 w-4" />
                  CONTRADICTED
                </div>
                <p className="text-[11px] text-ink-secondary leading-4">
                  Reliable evidence directly conflicts with the claim. The source explicitly asserts an incompatible
                  fact.
                </p>
              </div>
              <div className="rounded bg-hallucinated-soft p-1 text-[10px] font-semibold text-hallucinated text-center">
                Contribution: 0.0
              </div>
            </div>

            {/* INSUFFICIENT_EVIDENCE */}
            <div className="panel p-3.5 flex flex-col justify-between border-l-4 border-l-uncertain space-y-2">
              <div>
                <div className="flex items-center gap-1.5 mb-1 text-uncertain font-bold text-xs uppercase tracking-wide">
                  <HelpCircle className="h-4 w-4" />
                  INSUFFICIENT
                </div>
                <p className="text-[11px] text-ink-secondary leading-4">
                  Available evidence is missing, partial, vague, or fails to establish all assertions in a compound claim.
                </p>
              </div>
              <div className="rounded bg-uncertain-soft p-1 text-[10px] font-semibold text-uncertain text-center">
                Contribution: +0.5
              </div>
            </div>

            {/* NOT_ASSESSED_NO_RELEVANT_SOURCE */}
            <div className="panel p-3.5 flex flex-col justify-between border-l-4 border-l-line space-y-2">
              <div>
                <div className="flex items-center gap-1.5 mb-1 text-ink-secondary font-bold text-xs uppercase tracking-wide">
                  <ShieldCheck className="h-4 w-4 text-ink-muted" />
                  NOT ASSESSED
                </div>
                <p className="text-[11px] text-ink-secondary leading-4">
                  No retrieved source passed the topical relevance gate (threshold &ge; 0.20). Excluded from score calculation.
                </p>
              </div>
              <div className="rounded bg-surface-muted p-1 text-[10px] font-semibold text-ink-muted text-center">
                Excluded from Score
              </div>
            </div>
          </div>

          {/* Critical Clarifications Box */}
          <div className="rounded-[var(--radius-sm)] border border-line bg-surface-muted p-3.5 text-xs text-ink-secondary leading-relaxed space-y-2">
            <div className="flex items-center gap-1.5 font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-accent" />
              Essential Fact-Checking Principles in VeriFact
            </div>
            <ul className="list-disc pl-4 space-y-1 text-[11px]">
              <li>
                <strong className="text-ink">Compound-Claim Coverage Guard:</strong> If a claim contains multiple assertions
                (e.g., &ldquo;Event X happened in year Y AND was led by person Z&rdquo;), all parts must be verified by evidence.
                If evidence only confirms part of the claim while omitting others, the verdict defaults to{' '}
                <code>INSUFFICIENT_EVIDENCE</code> to prevent overconfident claims of support.
              </li>
              <li>
                <strong className="text-ink">Insufficient Evidence is Not Contradiction:</strong> A web source omitting a fact
                does not make that fact false. <code>CONTRADICTED</code> is strictly reserved for explicit factual clashes.
              </li>
              <li>
                <strong className="text-ink">Lack of Relevant Sources is Not Falsity:</strong> If no relevant source is found
                online addressing a claim, it is marked as <code>NOT_ASSESSED_NO_RELEVANT_SOURCE</code> rather than assumed to
                be true or false, and is excluded from the consistency score.
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* 7. Scoring Formula and Verdict Interpretation */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Scoring Formula &amp; Verdict Interpretation</h2>
          <p className="mt-1 text-xs text-ink-muted">
            How claim-level contributions aggregate into the overall Web Evidence Consistency Score.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-5">
          {/* Formula Display Box */}
          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4 sm:p-5 space-y-4">
            <div className="text-center space-y-2">
              <p className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">
                Web Evidence Consistency Score
              </p>
              <div className="inline-flex items-center justify-center rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2.5 shadow-xs">
                <span className="text-xs sm:text-sm font-semibold text-ink">
                  Consistency Score = Average contribution of all assessed claims
                </span>
              </div>
            </div>

            {/* Contribution Values Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              <div className="rounded border border-reliable/25 bg-reliable-soft/60 p-2.5 text-center space-y-0.5">
                <span className="text-[11px] font-semibold text-reliable block">Supported claim</span>
                <span className="text-xs font-mono font-bold text-reliable">1.0</span>
              </div>
              <div className="rounded border border-uncertain/25 bg-uncertain-soft/60 p-2.5 text-center space-y-0.5">
                <span className="text-[11px] font-semibold text-uncertain block">Insufficient evidence</span>
                <span className="text-xs font-mono font-bold text-uncertain">0.5</span>
              </div>
              <div className="rounded border border-hallucinated/25 bg-hallucinated-soft/60 p-2.5 text-center space-y-0.5">
                <span className="text-[11px] font-semibold text-hallucinated block">Contradicted claim</span>
                <span className="text-xs font-mono font-bold text-hallucinated">0.0</span>
              </div>
              <div className="rounded border border-line bg-surface-muted/70 p-2.5 text-center space-y-0.5">
                <span className="text-[11px] font-semibold text-ink-secondary block">Not assessed (no source)</span>
                <span className="text-[10px] text-ink-muted font-medium block">Excluded from calculation</span>
              </div>
            </div>

            <p className="text-xs leading-relaxed text-ink-secondary border-t border-line/60 pt-3">
              The consistency score is calculated as the average of the contributions from claims that were actually
              assessed. Claims for which no relevant source was found online are marked as not assessed and are
              excluded from both the numerator and the denominator. If there are no eligible assessed claims, no score
              is produced (<code className="text-[11px]">None</code>).
            </p>
          </div>

          {/* Categorical Verdicts Table */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-ink">Categorical Verdict Hierarchy (scoring.py):</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line text-ink-muted">
                    <th className="pb-2 font-medium">Verdict Category</th>
                    <th className="pb-2 font-medium">Trigger Condition</th>
                    <th className="pb-2 font-medium">Displayed Status Label</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60 text-ink-secondary">
                  <tr>
                    <td className="py-2 font-semibold text-reliable">STRONGLY_SUPPORTED</td>
                    <td className="py-2 font-mono text-[11px]">Score ≥ 0.85, 0 contradictions, 0 insufficient</td>
                    <td className="py-2">Strongly supported by evidence</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-semibold text-reliable">MOSTLY_SUPPORTED</td>
                    <td className="py-2 font-mono text-[11px]">All claims supported, 0 contradictions</td>
                    <td className="py-2">Mostly supported by evidence</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-semibold text-accent">PARTIALLY_SUPPORTED</td>
                    <td className="py-2 font-mono text-[11px]">Supported &gt; 0, 0 contradictions, insufficient &gt; 0</td>
                    <td className="py-2">Partially supported by evidence</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-semibold text-hallucinated">MIXED</td>
                    <td className="py-2 font-mono text-[11px]">Supported &gt; 0 and Contradicted &gt; 0</td>
                    <td className="py-2">Mixed — some claims contradicted</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-semibold text-hallucinated">CONTRADICTIONS_FOUND</td>
                    <td className="py-2 font-mono text-[11px]">Contradicted &gt; 0, 0 supported</td>
                    <td className="py-2">Potential factual contradiction detected</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-semibold text-uncertain">INSUFFICIENT</td>
                    <td className="py-2 font-mono text-[11px]">Supported = 0, Contradicted = 0</td>
                    <td className="py-2">Not enough external evidence to fully verify</td>
                  </tr>
                  <tr>
                    <td className="py-2 font-semibold text-ink-muted">NO_CLAIMS</td>
                    <td className="py-2 font-mono text-[11px]">Score is None and 0 assessed claims</td>
                    <td className="py-2">No eligible assessed claims to score</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-[var(--radius-sm)] border border-uncertain/30 bg-uncertain-soft/40 p-3.5 text-xs text-ink-secondary leading-relaxed">
            <strong className="text-ink font-semibold">Scientific Interpretation Caution:</strong> The Web Evidence
            Consistency Score is an empirical metric of online evidentiary corroboration,{' '}
            <strong className="text-ink">not a calibrated mathematical probability of factual truth</strong>. An answer
            is not mathematically verified merely because web sources agree, and lack of web evidence is not proof of
            hallucination.
          </div>
        </div>
      </section>

      {/* 8. Inspectable Source Metadata in the UI */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Source Transparency &amp; Citations</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Inspectable citation metadata presented in the Web Evidence results panel.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4">
          <p className="text-sm leading-relaxed text-ink-secondary">
            VeriFact avoids opaque &ldquo;black-box&rdquo; outputs by providing direct clickable citations and
            verbatim excerpts for every verified claim:
          </p>

          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/60 p-4">
            <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-3">
              Inspectable Fields in Web Evidence Panel
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
        </div>
      </section>

      {/* 9. Comparison with ClaimCheck (Putta et al., 2025) */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Research Context: ClaimCheck vs. VeriFact</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Comparing the automated fact-checking benchmark with VeriFact’s interactive implementation.
          </p>
        </div>

        <ResearchComparisonTable
          researchHeader="ClaimCheck Research (Putta et al., KnowledgeNLP 2025)"
          implementationHeader="VeriFact Production Web Evidence"
          rows={claimCheckComparisonRows}
          note="ClaimCheck benchmarks automated fact-checking of public misinformation claims on AVeriTeC using web scraping and fine-tuned models. VeriFact adapts evidence retrieval to evaluate claims dynamically extracted from AI-generated answers, designed for interactive dual-signal hallucination detection."
        />
      </section>

      {/* 10. System Architecture: Verified Backend Execution Flow */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">System Architecture &amp; Execution Flow</h2>
          <p className="mt-1 text-xs text-ink-muted">
            The verified execution flow across MetaQA, Direct-Answer Multi-Model Review, and Web Evidence.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-5">
          {/* Architecture Diagram */}
          <div className="mx-auto flex max-w-xl flex-col items-center">
            {/* Input & Generator */}
            <div className="w-full max-w-xs rounded-[var(--radius-sm)] border border-accent/40 bg-accent-soft/30 px-4 py-2.5 text-center shadow-card">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">Fixed Answer Generator</span>
              <p className="text-xs font-bold text-ink">Gemma 4:26B Answer</p>
              <p className="text-[10px] text-ink-muted">Single candidate answer under test</p>
            </div>

            {/* Fork to 3 concurrent processes */}
            <div className="w-full pt-3">
              <div className="relative flex justify-center">
                <div className="h-4 w-px bg-line" />
              </div>
              <div className="relative">
                <div className="mx-auto h-px w-5/6 bg-line" />
                <div className="flex justify-between px-[8.33%]">
                  <div className="h-3 w-px bg-line" />
                  <div className="h-3 w-px bg-line" />
                  <div className="h-3 w-px bg-line" />
                </div>
              </div>

              <div className="mt-1 grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Branch 1: MetaQA Pipeline */}
                <div className="flex flex-col space-y-2 rounded-[var(--radius-sm)] border border-line bg-canvas p-3 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-ink">
                    <Sparkles className="h-3.5 w-3.5 text-accent" />
                    MetaQA Pipeline
                  </div>
                  <div className="rounded border border-line/70 bg-surface-muted/60 p-1.5 text-[10px] text-ink-secondary space-y-0.5">
                    <span className="font-semibold text-ink block">1. Mutation Generation</span>
                    Gemma generates synonyms, antonyms &amp; negations
                  </div>
                  <ArrowDown className="mx-auto h-3 w-3 text-ink-muted" />
                  <div className="rounded border border-accent/30 bg-accent-soft/40 p-1.5 text-[10px] text-ink font-medium space-y-0.5">
                    <span className="font-bold text-accent block">2. Multi-Model Mutation Verifier</span>
                    Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B &amp; Liquid LFM-2.5
                  </div>
                  <ArrowDown className="mx-auto h-3 w-3 text-ink-muted" />
                  <div className="mt-auto rounded bg-surface p-1.5 border border-line text-[10px] font-bold text-ink">
                    MetaQA Score &amp; Status
                    <span className="block text-[9px] font-normal text-ink-muted">Eq. 5 penalty average (0.0 to 1.0)</span>
                  </div>
                </div>

                {/* Branch 2: Direct-Answer Multi-Model Review */}
                <div className="flex flex-col space-y-2 rounded-[var(--radius-sm)] border border-line bg-canvas p-3 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-ink">
                    <Layers className="h-3.5 w-3.5 text-accent" />
                    Direct-Answer Review
                  </div>
                  <div className="rounded border border-line/70 bg-surface-muted/60 p-1.5 text-[10px] text-ink-secondary space-y-0.5">
                    <span className="font-semibold text-ink block">Input Context Enriched</span>
                    Question + Answer + Claims + Mutations + Web snippets
                  </div>
                  <ArrowDown className="mx-auto h-3 w-3 text-ink-muted" />
                  <div className="rounded border border-accent/30 bg-accent-soft/40 p-1.5 text-[10px] text-ink font-medium space-y-0.5">
                    <span className="font-bold text-accent block">Cross-Model Evaluation</span>
                    Independent models assess overall answer
                  </div>
                  <ArrowDown className="mx-auto h-3 w-3 text-ink-muted" />
                  <div className="mt-auto rounded bg-surface p-1.5 border border-line text-[10px] font-bold text-ink">
                    Consensus Summary
                    <span className="block text-[9px] font-normal text-ink-muted">Consensus / Disagreements / Contradictions</span>
                  </div>
                </div>

                {/* Branch 3: Web Evidence Pipeline */}
                <div className="flex flex-col space-y-2 rounded-[var(--radius-sm)] border border-reliable/30 bg-reliable-soft/20 p-3 text-center">
                  <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-ink">
                    <Globe className="h-3.5 w-3.5 text-reliable" />
                    Web Evidence Pipeline
                  </div>
                  <div className="rounded border border-line/70 bg-surface-muted/60 p-1.5 text-[10px] text-ink-secondary space-y-0.5">
                    <span className="font-semibold text-ink block">1. Claim Extraction</span>
                    Isolates up to 3 atomic factual claims
                  </div>
                  <ArrowDown className="mx-auto h-3 w-3 text-ink-muted" />
                  <div className="rounded border border-reliable/30 bg-reliable-soft/40 p-1.5 text-[10px] text-ink font-medium space-y-0.5">
                    <span className="font-bold text-reliable block">2. Tavily Search &amp; Tiering</span>
                    Multi-pass retrieval + 6-tier ranking
                  </div>
                  <ArrowDown className="mx-auto h-3 w-3 text-ink-muted" />
                  <div className="mt-auto rounded bg-surface p-1.5 border border-line text-[10px] font-bold text-ink">
                    Web Evidence Score
                    <span className="block text-[9px] font-normal text-ink-muted">Supported / Contradicted / Insufficient</span>
                  </div>
                </div>
              </div>

              {/* Converge to Unified Findings */}
              <div className="mt-3">
                <div className="flex justify-between px-[8.33%]">
                  <div className="h-3 w-px bg-line" />
                  <div className="h-3 w-px bg-line" />
                  <div className="h-3 w-px bg-line" />
                </div>
                <div className="mx-auto h-px w-5/6 bg-line" />
                <div className="flex justify-center">
                  <div className="h-4 w-px bg-line" />
                </div>
              </div>
            </div>

            <ArrowDown className="my-1.5 h-4 w-4 text-ink-muted shrink-0" aria-hidden="true" />

            {/* Findings Card */}
            <div className="w-full max-w-sm rounded-[var(--radius-sm)] border border-line bg-surface px-4 py-2 text-center shadow-card">
              <p className="text-xs font-bold text-ink">VeriFact Multi-Faceted Findings</p>
              <p className="text-[10px] text-ink-muted">Three orthogonal signals presented side by side without score blending</p>
            </div>
          </div>

          {/* Codebase Grounding & Explanations */}
          <div className="rounded-[var(--radius-sm)] border border-line bg-canvas/70 p-4 space-y-3 text-xs text-ink-secondary leading-relaxed">
            <h3 className="font-semibold text-ink">Verified Backend Execution Architecture:</h3>
            <p>
              When a question is answered in <code>/api/detect</code>, Gemma 4:26B generates the base response. The backend
              scheduler (<code>routes_detect.py::_run_parallel_verification</code>) then launches three coordinated background tasks:
            </p>
            <ol className="list-decimal pl-4 space-y-2">
              <li>
                <strong className="text-ink">MetaQA Pipeline (<code>_continue_metaqa_analysis</code>):</strong> Gemma generates
                synonym, antonym, and negation mutations (<code>mutation.py</code>). Rather than acting as a separate outside silo, the{' '}
                <strong className="text-ink">multi-model verifier pool acts directly as the mutation verifier stage</strong> inside
                MetaQA (<code>metaqa/multi_verifier.py::verify_all_mutations_multi_model</code>). All independent models
                (Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, Liquid LFM-2.5) evaluate each mutation concurrently, and their
                discrete verdicts (YES=0/1, NO=1/0, NOT SURE=0.5) determine the MetaQA Inconsistency Score.
              </li>
              <li>
                <strong className="text-ink">Direct-Answer Multi-Model Review (<code>_continue_independent_verdicts</code>):</strong>{' '}
                Concurrently, all independent models evaluate Gemma’s complete answer directly (<code>independent_verifiers.py</code>).
                This process receives the user question, Gemma’s generated answer, extracted key claims, mutation context, and
                retrieved web snippets as inputs, outputting structured verdicts (<code>Correct</code>, <code>Incorrect</code>,{' '}
                <code>Uncertain</code>), concise reasoning, and identified contradictory statements.
              </li>
              <li>
                <strong className="text-ink">Web Evidence Pipeline (<code>_continue_web_evidence</code>):</strong> Operates as an
                independent external grounding pipeline (<code>web_evidence/pipeline.py</code>). It decomposes Gemma&apos;s answer
                into testable claims, executes keyword queries via Tavily with multi-pass fallback, tiers sources across 6 authority
                levels, filters off-topic sources (threshold &ge; 0.20), and scores claim support without altering MetaQA scores.
              </li>
            </ol>
            <p className="text-[11px] text-ink-muted border-t border-line/60 pt-2">
              <strong>Source Files:</strong> [routes_detect.py](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/api/routes_detect.py),{' '}
              [multi_verifier.py](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/metaqa/multi_verifier.py),{' '}
              [independent_verifiers.py](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/services/independent_verifiers.py),{' '}
              and [pipeline.py](file:///c:/Users/Rohan/Desktop/mini-project/verifact/backend/app/web_evidence/pipeline.py).
            </p>
          </div>
        </div>
      </section>

      {/* 11. Evidence Quality & Limitations */}
      <section className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Evidence Quality &amp; Practical Limitations</h2>
          <p className="mt-1 text-xs text-ink-muted">
            Important constraints to consider when interpreting Web Evidence findings.
          </p>
        </div>

        <div className="panel p-5 sm:p-6 space-y-4 text-xs leading-relaxed text-ink-secondary">
          <ul className="list-disc pl-4 space-y-2.5">
            <li>
              <strong className="text-ink">Omission is Not Contradiction:</strong> A web page omitting a specific
              detail does not prove that the detail is false. The verifier assigns <code>INSUFFICIENT_EVIDENCE</code>{' '}
              when information is missing, reserving <code>CONTRADICTED</code> exclusively for explicit factual clashes.
            </li>
            <li>
              <strong className="text-ink">Lack of Relevant Sources is Not Falsity:</strong> When no relevant web sources
              are found online addressing a claim, the claim is marked <code>NOT_ASSESSED_NO_RELEVANT_SOURCE</code> and
              excluded from the consistency score. Absence of online documentation must not be conflated with evidence of falsehood.
            </li>
            <li>
              <strong className="text-ink">Search Engine Coverage &amp; Freshness:</strong> Search engines can return
              outdated, partial, or SEO-manipulated content. Even authoritative domains can host legacy information that
              has since been superseded.
            </li>
            <li>
              <strong className="text-ink">Snippet Truncation:</strong> VeriFact inspects search snippets rather than
              full page bodies to maintain low latency. Highly technical or nuanced claims may require full-text
              inspection to achieve complete verification.
            </li>
            <li>
              <strong className="text-ink">Multi-Model Peer Review Distinction:</strong> The independent verifier models
              (Phi-4 Reasoning, GLM-4.7-Flash, Qwen-2.5-32B, and Liquid LFM-2.5) conduct cross-model review of Gemma&apos;s answer.
              Their peer agreement demonstrates architectural consensus, but does not substitute for external factual documentation
              and does not alter the Web Evidence score.
            </li>
          </ul>
        </div>
      </section>
    </div>
  )
}
