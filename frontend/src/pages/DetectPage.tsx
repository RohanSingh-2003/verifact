import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { detectRun, getHealth, getRun } from '../services/api'
import { EXAMPLE_QUESTIONS } from '../data/mockData'
import { AnswerCard } from '../components/detect/AnswerCard'
import { AnalysisProgress } from '../components/detect/AnalysisProgress'
import { AnalysisSummary } from '../components/detect/AnalysisSummary'
import { MethodOverview } from '../components/detect/MethodOverview'
import { MutationTabs } from '../components/detect/MutationTabs'
import { QuestionInput } from '../components/detect/QuestionInput'
import { ScoreCard } from '../components/detect/ScoreCard'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/Status'
import type { AnalysisResult, AnalysisStage } from '../types'
import { AnalysisStage as Stage } from '../types'

export function DetectPage() {
  const [params, setParams] = useSearchParams()
  const runId = params.get('id')

  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [stage, setStage] = useState<AnalysisStage>(Stage.Idle)
  const [error, setError] = useState<string | null>(null)
  const [fetching, setFetching] = useState(Boolean(runId))
  const [appMode, setAppMode] = useState<'mock' | 'live' | null>(null)

  useEffect(() => {
    void getHealth()
      .then((h) => setAppMode(h.llm_mode))
      .catch(() => {})
  }, [])

  const loading = useMemo(
    () =>
      stage === Stage.GeneratingAnswer ||
      stage === Stage.GeneratingMutations ||
      stage === Stage.VerifyingMutations ||
      stage === Stage.CalculatingScore,
    [stage],
  )

  useEffect(() => {
    if (!runId) return
    let cancelled = false
    setFetching(true)
    void getRun(runId)
      .then((analysis) => {
        if (cancelled) return
        setFetching(false)
        if (!analysis) {
          setError('That analysis could not be found. It may have been deleted, or the id in the URL is invalid.')
          setResult(null)
          return
        }
        setQuestion(analysis.question)
        setResult(analysis)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setFetching(false)
        setError(err instanceof Error ? err.message : 'Unable to load that analysis from the server.')
      })
    return () => {
      cancelled = true
    }
  }, [runId])

  async function handleAnalyze() {
    setError(null)
    setResult(null)
    try {
      const analysis = await detectRun(question, { onStage: setStage })
      setResult(analysis)
      setStage(Stage.Complete)
      setParams({ id: analysis.id }, { replace: true })
    } catch (err) {
      setStage(Stage.Error)
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.')
    }
  }

  function handleReset() {
    setResult(null)
    setError(null)
    setStage(Stage.Idle)
    setFetching(false)
    setParams({}, { replace: true })
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-6">
        <p className="text-meta">Hallucination detector</p>
        <h1 className="mt-2 text-[1.75rem] font-semibold tracking-tight text-ink sm:text-[1.95rem]">
          Check an AI answer.
        </h1>
        <p className="mt-2 max-w-xl text-[15px] leading-6 text-ink-secondary">
          Analyze fact-conflicting hallucinations using metamorphic verification.
        </p>
        {(result?.llmMode ?? appMode) === 'mock' ? (
          <p className="mt-3 text-xs font-medium tracking-wide text-ink-muted uppercase">
            Demo / Mock Mode
          </p>
        ) : (result?.llmMode ?? appMode) === 'live' ? (
          <p className="mt-3 text-xs font-medium tracking-wide text-ink-muted uppercase">
            Live LLM Mode
          </p>
        ) : null}
      </header>

      <MethodOverview />

      <QuestionInput
        value={question}
        onChange={setQuestion}
        onSubmit={() => void handleAnalyze()}
        loading={loading}
        disabled={loading}
      />

      {!result && !loading ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setQuestion(example)}
              className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink-secondary hover:border-line-strong hover:text-ink"
            >
              {example}
            </button>
          ))}
        </div>
      ) : null}

      <div className="mt-8 space-y-8">
        {loading ? <AnalysisProgress stage={stage} /> : null}
        {fetching && !loading ? <LoadingState label="Loading analysis…" /> : null}

        {error ? <ErrorState message={error} onRetry={() => void handleAnalyze()} /> : null}

        {!loading && !fetching && !error && !result ? (
          <EmptyState
            title="No analysis yet"
            description="Enter a factual question to inspect the generated answer, mutation evidence, and hallucination score."
          />
        ) : null}

        {result && !loading ? (
          <div className="animate-fade-up space-y-8">
            <AnswerCard
              question={result.question}
              answer={result.answer}
              model={result.model}
              responseTimeMs={result.responseTimeMs}
              llmMode={result.llmMode}
            />
            <ScoreCard score={result.score} threshold={result.threshold} verdict={result.verdict} />
            <MutationTabs mutations={result.mutations} />
            <AnalysisSummary result={result} />
            <button
              type="button"
              onClick={handleReset}
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
            >
              Start a new analysis
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
