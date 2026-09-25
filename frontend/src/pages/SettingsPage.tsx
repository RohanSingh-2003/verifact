import { useEffect, useState } from 'react'
import { getSettings } from '../services/api'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, LoadingState } from '../components/ui/Status'
import { classNames, formatScore } from '../lib/format'
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

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { preference, setPreference } = useTheme()

  useEffect(() => {
    void getSettings()
      .then((value) => {
        setSettings(value)
        setError(null)
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to load settings. Check that the FastAPI server is running.',
        )
      })
  }, [])

  return (
    <div className="mx-auto max-w-xl">
      <PageHeader
        title="Settings"
        description="Appearance preferences are saved in this browser. Detection defaults are read from the backend and are not edited here."
      />

      <section className="panel mb-6 space-y-4 p-5">
        <div>
          <h2 className="text-sm font-medium text-ink">Theme</h2>
          <p className="mt-1 text-xs text-ink-muted">Choose how VeriFact looks on this device.</p>
        </div>
        <div
          className="flex rounded-[var(--radius-sm)] bg-surface-muted p-1"
          role="radiogroup"
          aria-label="Theme"
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
      {!settings && !error ? <LoadingState label="Loading settings…" /> : null}
      {settings ? (
        <div className="panel space-y-6 p-5">
          <p className="text-sm text-ink-secondary">
            Mode:{' '}
            <span className="font-medium text-ink">
              {settings.llmMode === 'live' && settings.llmProvider === 'ollama'
                ? 'Live Mode — Local Ollama'
                : settings.llmMode === 'live' && settings.liveReady
                  ? 'Live LLM Mode'
                  : settings.llmMode === 'live'
                    ? 'Live configured (blocked — API key missing)'
                    : 'Demo / Mock Mode'}
            </span>
            {settings.llmMode === 'live' && settings.llmProvider === 'ollama'
              ? ` · Model: ${settings.generatorModel}`
              : ''}
            {settings.llmMode === 'live' &&
            settings.llmProvider !== 'ollama' &&
            !settings.apiKeyConfigured
              ? ' API keys are not returned to this page.'
              : ''}
          </p>
          <label className="block">
            <span className="text-sm font-medium text-ink">Detection threshold</span>
            <span className="mt-1 block text-xs text-ink-muted">
              Scores at or above this value are classified as likely hallucinated. Changing the
              experimental best-F1 threshold does not change this production value.
            </span>
            <div className="mt-3 flex items-center gap-4">
              <input
                type="range"
                min={0.1}
                max={0.9}
                step={0.05}
                value={settings.threshold}
                disabled
                className="w-full accent-accent"
              />
              <span className="w-10 text-sm tabular-nums text-ink">
                {formatScore(settings.threshold)}
              </span>
            </div>
          </label>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-ink-muted">Generator A</dt>
              <dd className="mt-1 text-ink">{settings.generatorModelA}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Generator B</dt>
              <dd className="mt-1 text-ink">{settings.generatorModelB}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Verifier A</dt>
              <dd className="mt-1 text-ink">{settings.verifierModelA}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Verifier B</dt>
              <dd className="mt-1 text-ink">{settings.verifierModelB}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">MAX_QUESTIONS</dt>
              <dd className="mt-1 text-ink">{settings.maxQuestions}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Mutations</dt>
              <dd className="mt-1 text-ink">
                {settings.synonymCount} synonym + {settings.antonymCount} antonym
              </dd>
            </div>
          </dl>
        </div>
      ) : null}
    </div>
  )
}
