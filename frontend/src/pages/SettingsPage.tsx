import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { getAvailableModels, getHealth, getSettings } from '../services/api'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, LoadingState } from '../components/ui/Status'
import { classNames } from '../lib/format'
import type { AnswerModelOption, AppSettings, SystemHealth } from '../types'
import { useTheme } from '../theme/ThemeProvider'
import type { ThemePreference } from '../lib/theme'

const THEME_OPTIONS: Array<{
  value: ThemePreference
  label: string
  description: string
}> = [
  { value: 'light', label: 'Light', description: 'Always use light mode with soft, high-contrast surfaces.' },
  { value: 'dark', label: 'Dark', description: 'Always use dark mode with comfortable, desaturated tones.' },
  { value: 'system', label: 'System', description: "Follow your operating system's theme preference automatically." },
]

const APP_VERSION = 'v1.0.0'
const METAQA_PAPER_URL = 'https://doi.org/10.1145/3715735'
const CLAIMCHECK_PAPER_URL = 'https://aclanthology.org/2025.knowledgenlp-1.26/'

interface VerifierCardItem {
  id: string
  name: string
  provider: string
  modelId: string
  role: string
  configured: boolean
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [availableModels, setAvailableModels] = useState<AnswerModelOption[]>([])
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { preference, setPreference } = useTheme()

  useEffect(() => {
    let cancelled = false

    Promise.all([
      getSettings(),
      getAvailableModels(),
      getHealth().catch(() => null),
    ])
      .then(([settingsData, modelsData, healthData]) => {
        if (cancelled) return
        setSettings(settingsData)
        setAvailableModels(modelsData)
        setHealth(healthData)
        setError(null)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to load settings. Check that the FastAPI server is running.',
        )
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  // Resolve model configuration statuses from active registry models
  const gemmaModel = availableModels.find((m) => m.id === 'gemma')
  const phiModel = availableModels.find((m) => m.id === 'phi')
  const glmModel = availableModels.find((m) => m.id === 'glm')
  const qwenModel = availableModels.find((m) => m.id === 'qwen')
  const liquidModel = availableModels.find((m) => m.id === 'openrouter')

  // Answer generator status
  const isGemmaConfigured = gemmaModel?.configured ?? settings?.apiKeyConfigured ?? false

  // The 4 independent cross-model verifiers
  const verifiers: VerifierCardItem[] = [
    {
      id: 'phi',
      name: 'Microsoft Phi-4 Reasoning',
      provider: 'OpenRouter (Microsoft)',
      modelId: settings?.phiVerifierModel || phiModel?.modelName || 'microsoft/phi-4-reasoning:free',
      role: 'MetaQA mutation reasoning & direct-answer peer review',
      configured: phiModel?.configured ?? settings?.phiVerifierReady ?? false,
    },
    {
      id: 'glm',
      name: 'GLM-4.7-Flash',
      provider: 'Cloudflare Workers AI',
      modelId: glmModel?.modelName || '@cf/zai-org/glm-4.7-flash',
      role: 'High-throughput cross-model mutation & answer verification',
      configured: glmModel?.configured ?? false,
    },
    {
      id: 'qwen',
      name: 'Qwen-2.5-32B',
      provider: 'Groq (Alibaba / Groq)',
      modelId: qwenModel?.modelName || 'qwen-2.5-32b',
      role: 'Ultra-low-latency semantic consistency & consensus analysis',
      configured: qwenModel?.configured ?? false,
    },
    {
      id: 'openrouter',
      name: 'Liquid LFM-2.5',
      provider: 'OpenRouter (Liquid AI)',
      modelId: liquidModel?.modelName || 'liquid/lfm-2.5-2.6b:free',
      role: 'Non-transformer hybrid neural architecture evaluation',
      configured: liquidModel?.configured ?? false,
    },
  ]

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Settings"
        description="Appearance preferences, active model providers, and verification architecture configuration."
      />

      {/* 1. Appearance */}
      <section className="panel space-y-4 p-5">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-ink">Appearance</h2>
          <p className="mt-0.5 text-xs text-ink-muted">Choose how VeriFact looks on this device.</p>
        </div>
        <div
          className="flex rounded-[var(--radius-sm)] bg-surface-muted p-1"
          role="radiogroup"
          aria-label="Appearance theme"
        >
          {THEME_OPTIONS.map((option) => {
            const selected = preference === option.value
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setPreference(option.value)}
                className={classNames(
                  'flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  selected
                    ? 'bg-surface text-ink shadow-[var(--shadow-card)]'
                    : 'text-ink-secondary hover:text-ink',
                )}
              >
                {option.label}
              </button>
            )
          })}
        </div>
        <p className="text-xs text-ink-muted">
          {THEME_OPTIONS.find((option) => option.value === preference)?.description}
        </p>
      </section>

      {error ? <ErrorState message={error} /> : null}
      {loading && !settings ? <LoadingState label="Loading settings and provider status…" /> : null}

      {settings ? (
        <>
          {/* 2. Answer Generation */}
          <section className="panel space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-line/60 pb-3">
              <div>
                <h2 className="text-sm font-semibold tracking-tight text-ink">Answer Generation</h2>
                <p className="mt-0.5 text-xs text-ink-muted">
                  Primary model responsible for generating answers and metamorphic mutations.
                </p>
              </div>
              <span
                className={classNames(
                  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold',
                  isGemmaConfigured
                    ? 'bg-reliable-soft text-reliable'
                    : 'bg-surface-muted text-ink-muted',
                )}
              >
                {isGemmaConfigured ? (
                  <>
                    <CheckCircle2 className="h-3 w-3" />
                    Configured
                  </>
                ) : (
                  <>
                    <XCircle className="h-3 w-3" />
                    Not configured
                  </>
                )}
              </span>
            </div>

            <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3.5 space-y-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-sm font-bold text-ink">Gemma 4:26B</span>
                <span className="text-xs font-medium text-ink-secondary">
                  Provider: <strong className="text-ink">Ollama Cloud</strong>
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                <span>Model Identifier:</span>
                <code className="rounded border border-line/70 bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink">
                  {settings.generatorModel || 'gemma4:26b'}
                </code>
              </div>
              <p className="text-xs text-ink-secondary leading-relaxed pt-1">
                Generates the initial factual answer and produces semantic mutations (synonyms, antonyms,
                and negations) for consistency testing. Gemma is strictly excluded from the verifier pool
                to prevent self-confirmation bias and sycophancy.
              </p>
            </div>
          </section>

          {/* 3. Independent Verifier Pool */}
          <section className="panel space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-line/60 pb-3">
              <div>
                <h2 className="text-sm font-semibold tracking-tight text-ink">
                  Independent Verifier Pool
                </h2>
                <p className="mt-0.5 text-xs text-ink-muted">
                  Four diverse cloud models evaluate mutations and conduct direct-answer peer review.
                </p>
              </div>
              <span className="text-[11px] font-medium text-ink-muted">
                4 independent models
              </span>
            </div>

            <div className="rounded-[var(--radius-sm)] border border-line/70 bg-canvas/60 p-3 text-xs text-ink-secondary leading-relaxed">
              <strong className="text-ink">Architectural Independence:</strong> The answer generator
              (Gemma) is never permitted to evaluate its own answers or mutations. All verification
              duties are distributed across this independent multi-model pool.
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {verifiers.map((v) => (
                <div
                  key={v.id}
                  className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3.5 flex flex-col justify-between space-y-2"
                >
                  <div className="space-y-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-bold text-ink">{v.name}</span>
                      <span
                        className={classNames(
                          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold shrink-0',
                          v.configured
                            ? 'bg-reliable-soft text-reliable'
                            : 'bg-surface-muted text-ink-muted',
                        )}
                      >
                        {v.configured ? (
                          <>
                            <CheckCircle2 className="h-2.5 w-2.5" />
                            Configured
                          </>
                        ) : (
                          <>
                            <XCircle className="h-2.5 w-2.5" />
                            Not configured
                          </>
                        )}
                      </span>
                    </div>
                    <p className="text-[11px] text-ink-secondary">
                      Provider: <span className="font-medium text-ink">{v.provider}</span>
                    </p>
                    <div className="flex items-center gap-1 text-[11px] text-ink-muted pt-0.5">
                      <span>ID:</span>
                      <code className="truncate rounded border border-line/60 bg-surface px-1 py-0.2 font-mono text-[10px] text-ink">
                        {v.modelId}
                      </code>
                    </div>
                  </div>
                  <p className="text-[11px] text-ink-muted pt-1 border-t border-line/40">
                    {v.role}
                  </p>
                </div>
              ))}
            </div>

            <p className="text-[11px] text-ink-muted pt-1">
              Note: Google Gemini is legacy and inactive; it is not included in the active verification pool.
            </p>
          </section>

          {/* 4. Web Evidence Retrieval & Grounding */}
          <section className="panel space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-line/60 pb-3">
              <div>
                <h2 className="text-sm font-semibold tracking-tight text-ink">
                  Web Evidence Grounding
                </h2>
                <p className="mt-0.5 text-xs text-ink-muted">
                  External factual retrieval via Tavily Search API across 6 authority tiers.
                </p>
              </div>
              <span
                className={classNames(
                  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold',
                  settings.webEvidenceReady
                    ? 'bg-reliable-soft text-reliable'
                    : 'bg-surface-muted text-ink-muted',
                )}
              >
                {settings.webEvidenceReady ? (
                  <>
                    <CheckCircle2 className="h-3 w-3" />
                    Configured
                  </>
                ) : (
                  <>
                    <XCircle className="h-3 w-3" />
                    Not configured
                  </>
                )}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3 space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-ink-muted block">
                  Search Engine
                </span>
                <span className="font-semibold text-ink text-sm">Tavily Search API</span>
                <span className="text-[11px] text-ink-muted block">Multi-pass targeted retrieval</span>
              </div>
              <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3 space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-ink-muted block">
                  Search Depth &amp; Limits
                </span>
                <span className="font-semibold text-ink text-sm capitalize">
                  {settings.tavilySearchDepth || 'Basic'} Depth
                </span>
                <span className="text-[11px] text-ink-muted block">
                  Max {settings.webMaxClaims} claims · {settings.webMaxSearches} searches/claim
                </span>
              </div>
              <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3 space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-ink-muted block">
                  Filtering &amp; Ranking
                </span>
                <span className="font-semibold text-ink text-sm">6 Authority Tiers</span>
                <span className="text-[11px] text-ink-muted block">Relevance threshold &ge; 0.20</span>
              </div>
            </div>

            <p className="text-xs text-ink-secondary leading-relaxed">
              Web Evidence acts as an orthogonal factual pipeline. Extracted claims are verified
              strictly against retrieved web snippets and assigned individual contribution scores
              (Supported: 1.0, Insufficient: 0.5, Contradicted: 0.0). Results are never blended into MetaQA scores.
            </p>
          </section>

          {/* 5. Research & Scoring Parameters */}
          <section className="panel space-y-4 p-5">
            <div className="border-b border-line/60 pb-3">
              <h2 className="text-sm font-semibold tracking-tight text-ink">
                Research &amp; Scoring Parameters
              </h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                Deterministic thresholds and metamorphic perturbation counts.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3 space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-ink-muted block">
                  MetaQA Decision Boundary
                </span>
                <span className="font-mono font-bold text-ink text-sm">
                  &theta; = {settings.threshold.toFixed(2)}
                </span>
                <span className="text-[11px] text-ink-muted block">
                  Score &ge; 0.5 &rarr; Hallucinated
                </span>
              </div>

              <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3 space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-ink-muted block">
                  Synonym Mutations
                </span>
                <span className="font-bold text-ink text-sm">
                  {settings.synonymCount} variants / sentence
                </span>
                <span className="text-[11px] text-ink-muted block">Meaning-preserving tests</span>
              </div>

              <div className="rounded-[var(--radius-sm)] border border-line/70 bg-surface-muted/30 p-3 space-y-1">
                <span className="text-[10px] uppercase font-bold tracking-wider text-ink-muted block">
                  Antonym &amp; Negation
                </span>
                <span className="font-bold text-ink text-sm">
                  {settings.antonymCount} variants / sentence
                </span>
                <span className="text-[11px] text-ink-muted block">Meaning-reversing tests</span>
              </div>
            </div>
          </section>

          {/* 6. System & Runtime Environment */}
          <section className="panel space-y-4 p-5">
            <div className="border-b border-line/60 pb-3">
              <h2 className="text-sm font-semibold tracking-tight text-ink">
                System &amp; Runtime Environment
              </h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                Execution status and database connectivity.
              </p>
            </div>

            <div className="divide-y divide-line/60 text-xs">
              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-ink-secondary">Execution Mode</span>
                <span className="font-medium text-ink">
                  {settings.liveReady ? 'Live Cloud Mode' : 'Mock Mode'}
                </span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-ink-secondary">Database</span>
                <span className="inline-flex items-center gap-1.5 font-medium text-ink">
                  SQLite (db/verifact.db) ·{' '}
                  <span
                    className={classNames(
                      'inline-flex items-center gap-1 font-semibold text-[11px]',
                      health?.database_connected ? 'text-reliable' : 'text-ink-muted',
                    )}
                  >
                    {health?.database_connected ? 'Connected' : 'Connection status unavailable'}
                  </span>
                </span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-ink-secondary">Backend Framework</span>
                <span className="font-medium text-ink">Python 3.12 · FastAPI</span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-ink-secondary">Frontend Framework</span>
                <span className="font-medium text-ink">React 19 · TypeScript · Vite</span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-ink-secondary">Frozen Experiment Audit ID</span>
                <code className="font-mono text-[11px] text-ink-muted">
                  {settings.frozenExperimentId}
                </code>
              </div>
            </div>
          </section>

          {/* 7. About VeriFact & Citations */}
          <section className="panel space-y-5 p-5">
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-ink">About VeriFact</h2>
              <p className="mt-0.5 text-xs leading-relaxed text-ink-secondary">
                VeriFact is a dual-pipeline hallucination detection and analysis framework combining
                metamorphic mutation testing with external web evidence retrieval.
              </p>
            </div>

            {/* Product Overview */}
            <div className="divide-y divide-line/60">
              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-xs font-medium text-ink-muted">Product</span>
                <span className="text-xs font-medium text-ink">VeriFact</span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-xs font-medium text-ink-muted">Purpose</span>
                <span className="text-xs font-medium text-ink">AI Hallucination Detection</span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-xs font-medium text-ink-muted">Version</span>
                <span className="font-mono text-xs font-medium text-ink">{APP_VERSION}</span>
              </div>

              <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                <span className="text-xs font-medium text-ink-muted">Status</span>
                <span className="text-xs font-medium text-ink">Research Prototype</span>
              </div>
            </div>

            {/* Research Subsection */}
            <div className="border-t border-line/60 pt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Research Foundations
              </h3>
              <div className="mt-2.5 space-y-3">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <div>
                    <span className="text-xs font-medium text-ink">MetaQA</span>
                    <span className="ml-2 text-xs text-ink-muted">Yang et al., FSE 2025</span>
                  </div>
                  <a
                    href={METAQA_PAPER_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-accent hover:underline"
                  >
                    View research paper &rarr;
                  </a>
                </div>

                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <div>
                    <span className="text-xs font-medium text-ink">Web Evidence</span>
                    <span className="ml-2 text-xs text-ink-muted">
                      ClaimCheck, KnowledgeNLP 2025
                    </span>
                  </div>
                  <a
                    href={CLAIMCHECK_PAPER_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-accent hover:underline"
                  >
                    View research paper &rarr;
                  </a>
                </div>
              </div>
            </div>

            {/* Architecture Summary */}
            <div className="border-t border-line/60 pt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Active Architecture Summary
              </h3>
              <div className="mt-2.5 divide-y divide-line/60">
                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Answer Generator</span>
                  <span className="text-xs font-medium text-ink">
                    Ollama Cloud · Gemma 4:26B
                  </span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Independent Verifiers</span>
                  <span className="text-xs font-medium text-ink">
                    Phi-4 Reasoning · GLM-4.7-Flash · Qwen-2.5-32B · Liquid LFM-2.5
                  </span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Web Grounding</span>
                  <span className="text-xs font-medium text-ink">Tavily Search API (6 Tiers)</span>
                </div>
              </div>
            </div>

            {/* Tagline & Footer */}
            <div className="border-t border-line/60 pt-3 text-center sm:text-left">
              <p className="text-xs italic text-ink-secondary">&ldquo;Verify what AI says.&rdquo;</p>
              <p className="mt-1 text-[11px] text-ink-muted">
                VeriFact {APP_VERSION} · Research prototype for AI hallucination detection.
              </p>
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}
