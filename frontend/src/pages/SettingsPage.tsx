import { useEffect, useState } from 'react'
import { getSettings } from '../services/api'
import { PageHeader } from '../components/ui/PageHeader'
import { ErrorState, LoadingState } from '../components/ui/Status'
import { formatScore } from '../lib/format'
import type { AppSettings } from '../types'

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)

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
        description="Detection and experiment defaults are read from the backend configuration. They are not edited here."
      />

      {error ? <ErrorState message={error} /> : null}
      {!settings && !error ? (
        <LoadingState label="Loading settings…" />
      ) : null}
      {settings ? (
        <div className="panel space-y-6 p-5">
          <p className="text-sm text-ink-secondary">
            Mode:{' '}
            <span className="font-medium text-ink">
              {settings.llmMode === 'live' && settings.liveReady
                ? 'Live LLM Mode'
                : settings.llmMode === 'live'
                  ? 'Live configured (blocked — API key missing)'
                  : 'Demo / Mock Mode'}
            </span>
            {settings.llmMode === 'live' && !settings.apiKeyConfigured
              ? ' API keys are not returned to this page.'
              : ''}
          </p>
          <label className="block">
            <span className="text-sm font-medium text-ink">Detection threshold</span>
            <span className="mt-1 block text-xs text-ink-muted">
              Scores at or above this value are classified as hallucinated. Changing the experimental
              best-F1 threshold does not change this production value.
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

