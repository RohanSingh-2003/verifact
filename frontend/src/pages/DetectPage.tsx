import { useEffect, useMemo, useRef, useState } from 'react'
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
import { AnalysisStage as Stage, RunStatus, isAnalysisFailureStatus } from '../types'
import { formatModelDisplay } from '../lib/format'

function ModeStatus({
  mode,
  provider,
  model,
}: {
  mode: 'mock' | 'live' | null
  provider: string | null
  model: string | null
}) {
  if (!mode) return null

  if (mode === 'mock') {
    return (
      <p className="mt-3 flex items-center gap-2 text-xs text-ink-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-ink-muted" aria-hidden="true" />
        <span>
          Demo / Mock
          <span className="mx-1.5 text-line-strong">·</span>
          Deterministic sample data
        </span>
      </p>
    )
  }

  if (provider === 'ollama') {
    const display = formatModelDisplay(model) ?? 'Local model'
    return (
      <p className="mt-3 flex items-center gap-2 text-xs text-ink-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
        <span>
          Local Ollama
          <span className="mx-1.5 text-line-strong">·</span>
          {display}
        </span>
      </p>
    )
  }

  return (
    <p className="mt-3 flex items-center gap-2 text-xs text-ink-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
      <span>Live LLM{model ? ` · ${formatModelDisplay(model) ?? model}` : ''}</span>
    </p>
  )
}

function stageFromRunStatus(status: AnalysisResult['status']): AnalysisStage {
  if (status === RunStatus.Completed) return Stage.Complete
  if (isAnalysisFailureStatus(status)) return Stage.AnalysisFailed
  if (status === RunStatus.VerifyingMutations || status === RunStatus.MutationsReady) {
    return Stage.VerifyingMutations
  }
  if (status === RunStatus.CalculatingScore) return Stage.CalculatingScore
  if (status === RunStatus.AnswerReady) return Stage.AnswerReady
  return Stage.GeneratingMutations
}

function analysisFailureMessage(result: AnalysisResult, mutationsVisible: boolean): string {
  const fromServer = result.analysisError?.trim()
  if (fromServer) return fromServer
  if (result.status === RunStatus.VerificationFailed || mutationsVisible) {
    return (
      'Hallucination analysis could not be completed because mutation verification failed. ' +
      'The generated answer and any mutations above are still available.'
    )
  }
  if (result.status === RunStatus.ScoringFailed) {
    return (
      'Hallucination analysis could not be completed while calculating the score. ' +
      'The generated answer and any mutations above are still available.'
    )
  }
  return (
    'Hallucination analysis could not be completed because the mutation generator did not ' +
    'return the required mutation set. The generated answer is still available above.'
  )
}

export function DetectPage() {
  const [params, setParams] = useSearchParams()
  const runId = params.get('id')
  const requestToken = useRef(0)
  const submitOwnsPolling = useRef(false)

  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [stage, setStage] = useState<AnalysisStage>(Stage.Idle)
  const [error, setError] = useState<string | null>(null)
  const [fetching, setFetching] = useState(Boolean(runId))
  const [appMode, setAppMode] = useState<'mock' | 'live' | null>(null)
  const [provider, setProvider] = useState<string | null>(null)
  const [healthGenerator, setHealthGenerator] = useState<string | null>(null)

  useEffect(() => {
    void getHealth()
      .then((h) => {
        setAppMode(h.llm_mode)
        setProvider(h.llm_provider ?? null)
        setHealthGenerator(h.generator_model ?? null)
      })
      .catch(() => {})
  }, [])

  const waitingForAnswer = stage === Stage.GeneratingAnswer
  const analyzing =
    stage === Stage.AnswerReady ||
    stage === Stage.GeneratingMutations ||
    stage === Stage.VerifyingMutations ||
    stage === Stage.CalculatingScore
  const inputLocked = waitingForAnswer || analyzing

  // Answer is independent of MetaQA success — show whenever we have text.
  const answerReady = useMemo(
    () => Boolean(result?.answer?.trim()) && stage !== Stage.GeneratingAnswer,
    [result, stage],
  )

  useEffect(() => {
    if (!runId) return
    if (submitOwnsPolling.current) return
    let cancelled = false
    let pollTimer: number | undefined
    setFetching(true)

    async function loadAndMaybePoll(id: string) {
      try {
        const analysis = await getRun(id)
        if (cancelled) return
        if (!analysis) {
          setFetching(false)
          setError(
            'That analysis could not be found. It may have been deleted, or the id in the URL is invalid.',
          )
          setResult(null)
          return
        }

        setQuestion(analysis.question)
        setResult(analysis)
        setError(null)
        setFetching(false)
        setStage(stageFromRunStatus(analysis.status))

        if (analysis.status === RunStatus.Completed || isAnalysisFailureStatus(analysis.status)) {
          return
        }

        const poll = async () => {
          if (cancelled || submitOwnsPolling.current) return
          try {
            const next = await getRun(id)
            if (cancelled || !next) return
            setResult(next)
            setStage(stageFromRunStatus(next.status))
            if (next.status === RunStatus.Completed || isAnalysisFailureStatus(next.status)) {
              return
            }
            pollTimer = window.setTimeout(() => {
              void poll()
            }, 1200)
          } catch (err) {
            if (cancelled) return
            setError(err instanceof Error ? err.message : 'Unable to refresh analysis status.')
          }
        }

        pollTimer = window.setTimeout(() => {
          void poll()
        }, 1200)
      } catch (err) {
        if (cancelled) return
        setFetching(false)
        setError(err instanceof Error ? err.message : 'Unable to load that analysis from the server.')
      }
    }

    void loadAndMaybePoll(runId)
    return () => {
      cancelled = true
      if (pollTimer) window.clearTimeout(pollTimer)
    }
  }, [runId])

  async function handleAnalyze() {
    const token = ++requestToken.current
    submitOwnsPolling.current = true
    setError(null)
    setResult(null)
    setStage(Stage.GeneratingAnswer)
    try {
      const analysis = await detectRun(question, {
        onStage: (next) => {
          if (requestToken.current !== token) return
          setStage(next)
        },
        onPartialResult: (partial) => {
          if (requestToken.current !== token) return
          setResult(partial)
          setParams({ id: partial.id }, { replace: true })
        },
      })
      if (requestToken.current !== token) return
      setResult(analysis)
      setParams({ id: analysis.id }, { replace: true })
      if (isAnalysisFailureStatus(analysis.status)) {
        setStage(Stage.AnalysisFailed)
        setError(null)
      } else {
        setStage(Stage.Complete)
      }
    } catch (err) {
      if (requestToken.current !== token) return
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.')
      setStage((current) => {
        // Keep the answer card if MetaQA failed after the answer was already shown.
        if (
          current === Stage.AnswerReady ||
          current === Stage.GeneratingMutations ||
          current === Stage.VerifyingMutations ||
          current === Stage.CalculatingScore ||
          current === Stage.AnalysisFailed
        ) {
          return Stage.AnalysisFailed
        }
        return Stage.Error
      })
    } finally {
      if (requestToken.current === token) {
        submitOwnsPolling.current = false
      }
    }
  }

  function handleReset() {
    requestToken.current += 1
    submitOwnsPolling.current = false
    setResult(null)
    setError(null)
    setStage(Stage.Idle)
    setFetching(false)
    setParams({}, { replace: true })
  }

  const activeMode = result?.llmMode ?? appMode
  const activeModel = result?.model ?? healthGenerator
  const analysisComplete = result?.status === RunStatus.Completed
  const analysisFailed =
    isAnalysisFailureStatus(result?.status) ||
    stage === Stage.AnalysisFailed ||
    (stage === Stage.Error && Boolean(result?.answer?.trim()))
  const mutations = result?.mutations ?? []
  const mutationsVisible = mutations.length > 0
  const verifiedCount = mutations.filter((item) => item.verified).length
  const verifyingMutations =
    stage === Stage.VerifyingMutations ||
    (analyzing && mutationsVisible && stage !== Stage.CalculatingScore && verifiedCount < mutations.length)
  const showPageLevelError = Boolean(error) && !answerReady

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-6">
        <p className="text-meta">VeriFact</p>
        <h1 className="mt-2 text-[1.75rem] font-semibold tracking-tight text-ink sm:text-[1.95rem]">
          AI Hallucination Detection
        </h1>
        <p className="mt-2 max-w-xl text-[15px] leading-6 text-ink-secondary">
          Ask a factual question. VeriFact gets an AI answer, then tests it for fact-conflicting
          hallucinations using MetaQA.
        </p>
        <ModeStatus mode={activeMode} provider={provider} model={activeModel} />
      </header>

      <MethodOverview />

      <QuestionInput
        value={question}
        onChange={setQuestion}
        onSubmit={() => void handleAnalyze()}
        loading={inputLocked}
        disabled={inputLocked}
      />

      {!result && !waitingForAnswer && !analyzing ? (
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
        {waitingForAnswer && !result ? <AnalysisProgress stage={stage} /> : null}
        {fetching && !waitingForAnswer && !analyzing && !result ? (
          <LoadingState label="Loading analysis…" />
        ) : null}

        {showPageLevelError ? (
          <ErrorState message={error ?? 'Request failed.'} onRetry={() => void handleAnalyze()} />
        ) : null}

        {!waitingForAnswer && !fetching && !error && !result && stage === Stage.Idle ? (
          <EmptyState
            title="No analysis yet"
            description="Enter a factual question. VeriFact will show the AI answer first, then continue MetaQA analysis in the background."
          />
        ) : null}

        {result && answerReady ? (
          <div className="animate-fade-up space-y-8">
            <AnswerCard
              answer={result.answer}
              model={result.model}
              responseTimeMs={result.responseTimeMs}
              llmMode={result.llmMode}
            />

            {analyzing ? (
              <AnalysisProgress
                stage={stage}
                answerVisible
                mutationsVisible={mutationsVisible}
                verifiedCount={verifiedCount}
                mutationCount={mutations.length}
              />
            ) : null}

            {analysisFailed ? (
              <div
                role="alert"
                className="rounded-[var(--radius-md)] border border-hallucinated/20 bg-hallucinated-soft px-5 py-5"
              >
                <h2 className="text-sm font-medium text-hallucinated">Hallucination analysis</h2>
                <p className="mt-1 text-base font-medium text-ink">Analysis could not be completed</p>
                <p className="mt-2 text-sm leading-6 text-ink-secondary">
                  {analysisFailureMessage(result, mutationsVisible)}
                </p>
                <p className="mt-2 text-xs leading-5 text-ink-muted">
                  The generated answer is still available above. No hallucination score was assigned.
                </p>
              </div>
            ) : null}

            {mutationsVisible ? (
              <MutationTabs mutations={mutations} verifying={verifyingMutations} />
            ) : null}

            {analysisComplete && result.score != null && result.verdict ? (
              <>
                <ScoreCard score={result.score} threshold={result.threshold} verdict={result.verdict} />
                <AnalysisSummary result={result} />
              </>
            ) : null}

            {!analyzing ? (
              <button
                type="button"
                onClick={handleReset}
                className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              >
                Start a new analysis
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
