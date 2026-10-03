import { useEffect, useState } from 'react'
import { getSettings } from '../services/api'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, LoadingState } from '../components/ui/Status'
import { classNames, formatModelDisplay, formatProviderDisplay } from '../lib/format'
import type { AppSettings } from '../types'
import { useTheme } from '../theme/ThemeProvider'
import type { ThemePreference } from '../lib/theme'

const THEME_OPTIONS: Array<{
  value: ThemePreference
  label: string
  description: string
}> = [
  { value: 'light', label: 'Light', description: 'Always use light mode.' },
  { value: 'dark', label: 'Dark', description: 'Always use dark mode.' },
  { value: 'system', label: 'System', description: "Follow your computer's system theme." },
]

const APP_VERSION = 'v1.0.0'
const METAQA_PAPER_URL = 'https://doi.org/10.1145/3715735'
const CLAIMCHECK_PAPER_URL = 'https://aclanthology.org/2025.knowledgenlp-1.26/'

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { preference, setPreference } = useTheme()

  useEffect(() => {
    let cancelled = false

    getSettings()
      .then((settingsData) => {
        if (cancelled) return
        setSettings(settingsData)
        setError(null)
      })
      .catch((err: Error) => {
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

  // Resolve verifier model and provider
  const verifierModelName =
    settings?.effectiveVerifierModel ||
    settings?.geminiVerifierModel ||
    settings?.verifierModel ||
    'gemini-3.8-flash'

  const isGeminiVerifier =
    verifierModelName.toLowerCase().includes('gemini') ||
    Boolean(settings?.geminiVerifierReady)

  const verifierProviderName = isGeminiVerifier
    ? 'Google Gemini'
    : formatProviderDisplay(settings?.llmProvider, verifierModelName)

  const generatorModelDisplay = formatModelDisplay(settings?.generatorModel) ?? 'Gemma 4:26B'
  const generatorProviderDisplay =
    formatProviderDisplay(settings?.llmProvider, settings?.generatorModel) || 'Ollama'
  const verifierModelDisplay = formatModelDisplay(verifierModelName) ?? 'Gemini 3.8 Flash'

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Settings"
        description="Appearance preferences and active AI services."
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
      {loading && !settings ? <LoadingState label="Loading settings…" /> : null}

      {settings ? (
        <>
          {/* 2. AI Configuration */}
          <section className="panel space-y-4 p-5">
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-ink">AI Configuration</h2>
              <p className="mt-0.5 text-xs text-ink-muted">
                Models and services currently used by VeriFact.
              </p>
            </div>

            <div className="divide-y divide-line/60">
              <div className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                <span className="text-sm font-medium text-ink">Answer generation</span>
                <span className="text-sm text-ink-secondary">
                  <span className="font-medium text-ink">{generatorModelDisplay}</span> ·{' '}
                  {generatorProviderDisplay}
                </span>
              </div>

              <div className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                <span className="text-sm font-medium text-ink">MetaQA verification</span>
                <span className="text-sm text-ink-secondary">
                  <span className="font-medium text-ink">{verifierModelDisplay}</span> ·{' '}
                  {verifierProviderName}
                </span>
              </div>

              <div className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                <span className="text-sm font-medium text-ink">Web evidence</span>
                <span className="text-sm font-medium text-ink">Tavily</span>
              </div>
            </div>
          </section>

          {/* 3. About VeriFact */}
          <section className="panel space-y-5 p-5">
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-ink">About VeriFact</h2>
              <p className="mt-0.5 text-xs leading-relaxed text-ink-secondary">
                VeriFact helps examine AI-generated answers using two complementary approaches:
                MetaQA consistency checking and Web Evidence Analysis.
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
                Research
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
                    className="text-xs font-medium text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
                  >
                    View research paper →
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
                    className="text-xs font-medium text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
                  >
                    View research paper →
                  </a>
                </div>
              </div>
            </div>

            {/* Technology Subsection */}
            <div className="border-t border-line/60 pt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
                Technology
              </h3>
              <div className="mt-2.5 divide-y divide-line/60">
                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Frontend</span>
                  <span className="text-xs font-medium text-ink">React · TypeScript · Vite</span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Backend</span>
                  <span className="text-xs font-medium text-ink">Python · FastAPI</span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Database</span>
                  <span className="text-xs font-medium text-ink">SQLite</span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Local AI</span>
                  <span className="text-xs font-medium text-ink">
                    {generatorProviderDisplay} · {generatorModelDisplay}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">MetaQA Verification</span>
                  <span className="text-xs font-medium text-ink">
                    {verifierProviderName} · {verifierModelDisplay}
                  </span>
                </div>

                <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                  <span className="text-xs font-medium text-ink-muted">Web Evidence</span>
                  <span className="text-xs font-medium text-ink">Tavily</span>
                </div>
              </div>
            </div>

            {/* Tagline & Footer */}
            <div className="border-t border-line/60 pt-3 text-center sm:text-left">
              <p className="text-xs italic text-ink-secondary">"Verify what AI says."</p>
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

