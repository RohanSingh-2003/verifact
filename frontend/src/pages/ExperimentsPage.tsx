import { useEffect, useMemo, useState } from 'react'
import {
  exportEvaluationCsv,
  exportEvaluationSweepCsv,
  exportExperimentCsv,
  exportExperimentConfig,
  exportExperimentFlipCsv,
  exportExperimentPairedCsv,
  exportExperimentSummaryCsv,
  exportExperimentSweepCsv,
  getEvaluation,
  getEvaluations,
  getGenerationTrace,
  getLatestExperiment,
  getExperimentOrNull,
  getSettings,
  estimateExperiment,
  runEvaluation,
  runExperiment,
} from '../services/api'
import { ConditionSummaryTable } from '../components/experiment/ConditionSummaryTable'
import { ExperimentChart } from '../components/experiment/ExperimentChart'
import { ExperimentMatrix } from '../components/experiment/ExperimentMatrix'
import { GenerationTracePanel } from '../components/experiment/GenerationTracePanel'
import { MetricCard } from '../components/experiment/MetricCard'
import { PairedQuestionsTable } from '../components/experiment/PairedQuestionsTable'
import { SelfVerificationSection } from '../components/experiment/SelfVerificationSection'
import { ConfusionMatrixCard } from '../components/evaluation/ConfusionMatrixCard'
import { EvaluationResultsTable } from '../components/evaluation/EvaluationResultsTable'
import { ThresholdSweepChart } from '../components/evaluation/ThresholdSweepChart'
import { PageHeader } from '../components/ui/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/ui/Status'
import type {
  EvaluationDetail,
  EvaluationSummary,
  ExperimentCell,
  ExperimentDetail,
  GenerationTrace,
  NamedModel,
  PairedComparison,
} from '../types'
import { formatPercent, formatScore, formatTimestamp, shortModelName } from '../lib/format'

function namedModels(ids: string[]): NamedModel[] {
  return ids.map((id, index) => ({
    id,
    name: id,
    shortName: shortModelName(id, index),
  }))
}

function cellsFromExperiment(experiment: ExperimentDetail): ExperimentCell[] {
  if (experiment.chart.length > 0) {
    return experiment.chart.map((item) => ({
      generatorId: item.generatorId,
      verifierId: item.verifierId,
      label: item.label,
      meanScore: item.meanScore,
      precision: item.precision,
      recall: item.recall,
      f1: item.f1,
      flipRate: item.flipRate,
    }))
  }
  return experiment.condition_summaries.map((item) => ({
    generatorId: item.generator_model,
    verifierId: item.verifier_model,
    label: item.label,
    meanScore: item.mean_score,
    precision: item.precision ?? 0,
    recall: item.recall ?? 0,
    f1: item.f1 ?? 0,
    flipRate: 0,
  }))
}

function datasetLabel(name: string) {
  return name.toLowerCase() === 'pilot' ? 'Pilot' : name
}

export function ExperimentsPage() {
  const [evaluation, setEvaluation] = useState<EvaluationDetail | null>(null)
  const [history, setHistory] = useState<EvaluationSummary[]>([])
  const [experiment, setExperiment] = useState<ExperimentDetail | null>(null)
  const [showingFrozenLock, setShowingFrozenLock] = useState(false)
  const [trace, setTrace] = useState<GenerationTrace | null>(null)
  const [selectedGenerationId, setSelectedGenerationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [runningExperiment, setRunningExperiment] = useState(false)
  const [runningEvaluation, setRunningEvaluation] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadExisting() {
    const [items, latest, settings] = await Promise.all([
      getEvaluations(),
      getLatestExperiment(),
      getSettings(),
    ])
    setHistory(items)
    const frozen = settings.frozenExperimentId
      ? await getExperimentOrNull(settings.frozenExperimentId)
      : null
    setExperiment(frozen ?? latest)
    setShowingFrozenLock(Boolean(frozen))
    if (items[0]) {
      setEvaluation(await getEvaluation(items[0].id))
    }
  }

  useEffect(() => {
    let cancelled = false
    void loadExisting()
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load experiment results. Check that the FastAPI server is running.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleRunExperiment() {
    setError(null)
    setRunningExperiment(true)
    setTrace(null)
    setSelectedGenerationId(null)
    try {
      const settings = await getSettings()
      let confirmLive = false
      if (settings.liveReady) {
        const estimate = await estimateExperiment({
          generator_models: [settings.generatorModelA, settings.generatorModelB],
          verifier_models: [settings.verifierModelA, settings.verifierModelB],
          max_questions: settings.maxQuestions,
          synonym_count: settings.synonymCount,
          antonym_count: settings.antonymCount,
        })
        confirmLive = window.confirm(
          `LIVE EXPERIMENT: ${estimate.questions} questions, about ${estimate.total_calls} LLM calls. Continue?`,
        )
        if (!confirmLive) {
          return
        }
      }
      const result = await runExperiment({
        confirm_live_run: confirmLive,
        max_questions: settings.maxQuestions,
      })
      setExperiment(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Experiment failed.')
    } finally {
      setRunningExperiment(false)
    }
  }

  async function handleRunEvaluation() {
    setError(null)
    setRunningEvaluation(true)
    try {
      const settings = await getSettings()
      let confirmLive = false
      if (settings.liveReady) {
        confirmLive = window.confirm(
          `LIVE MetaQA evaluation of up to ${settings.maxQuestions} questions. Continue?`,
        )
        if (!confirmLive) {
          return
        }
      }
      const result = await runEvaluation('pilot', 0.5, {
        confirm_live_run: confirmLive,
        max_questions: settings.maxQuestions,
      })
      setEvaluation(result)
      setHistory(await getEvaluations())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed.')
    } finally {
      setRunningEvaluation(false)
    }
  }

  async function handleSelectPaired(row: PairedComparison) {
    if (!experiment) return
    setSelectedGenerationId(row.generation_id)
    try {
      setTrace(await getGenerationTrace(experiment.id, row.generation_id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load mutation trace.')
    }
  }

  const cells = useMemo(() => (experiment ? cellsFromExperiment(experiment) : []), [experiment])
  const generators = experiment ? namedModels(experiment.generator_models) : []
  const verifiers = experiment ? namedModels(experiment.verifier_models) : []
  const isPilot = experiment?.dataset_name?.toLowerCase() === 'pilot'
  const meanScore =
    experiment && experiment.condition_summaries.length > 0
      ? experiment.condition_summaries.reduce((sum, row) => sum + row.mean_score, 0) /
        experiment.condition_summaries.length
      : null
  const meanNotSure =
    experiment && experiment.condition_summaries.length > 0
      ? experiment.condition_summaries.reduce((sum, row) => sum + row.not_sure_rate, 0) /
        experiment.condition_summaries.length
      : null
  const anySignificant = Boolean(
    experiment?.self_verification.some((block) => block.significant && !block.exploratory),
  )

  return (
    <div>
      <PageHeader
        eyebrow="Research experiment"
        title="Same-model vs cross-model verification"
        description="Controlled 2×2 study: generate each answer and its mutations once, then verify that fixed mutation set with both models."
        action={
          <button
            type="button"
            className="btn-primary"
            onClick={() => void handleRunExperiment()}
            disabled={runningExperiment}
          >
            {runningExperiment ? 'Running 2×2…' : 'Run 2×2 experiment'}
          </button>
        }
      />

      {loading ? <LoadingState label="Loading experiment…" /> : null}
      {error ? (
        <ErrorState
          message={error}
          onRetry={() => {
            setError(null)
            setLoading(true)
            void loadExisting()
              .catch((err) =>
                setError(
                  err instanceof Error
                    ? err.message
                    : 'Unable to load experiment results. Check that the FastAPI server is running.',
                ),
              )
              .finally(() => setLoading(false))
          }}
        />
      ) : null}

      {!loading && !experiment ? (
        <EmptyState
          title="No 2×2 experiment yet"
          description="Frozen research numbers live in docs/final_results_lock.md (experiment 58baff20-fb86-4f43-b20e-895a086ceb6b, mock). Run the pilot 2×2 to store a SQLite copy for this dashboard."
          action={
            <button type="button" className="btn-primary" onClick={() => void handleRunExperiment()}>
              Run pilot 2×2 experiment
            </button>
          }
        />
      ) : null}

      {experiment ? (
        <div className="space-y-10">
          {experiment.demo_data ? (
            <div
              role="status"
              className="rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3 py-2 text-xs leading-5 text-ink-secondary"
            >
              {showingFrozenLock
                ? 'DEMO / MOCK DATA — frozen research lock. Deterministic mock outputs, not live-model findings.'
                : 'DEMO / MOCK DATA — this is a later development run, not the frozen research lock. See docs/final_results_lock.md for the locked experiment ID.'}
            </div>
          ) : (
            <div
              role="status"
              className="rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3 py-2 text-xs leading-5 text-ink-secondary"
            >
              LIVE EXPERIMENT — results from configured provider models. Key finding is generated from stored scores.
            </div>
          )}

          {isPilot ? (
            <p className="text-sm text-ink-secondary">
              Dataset: <span className="font-medium text-ink">Pilot</span> ({experiment.question_count} questions).
              This is a pilot-scale run, not a full evaluation corpus.
            </p>
          ) : null}

          <section className="panel p-5">
            <p className="text-meta">Experiment</p>
            <h2 className="mt-2 text-lg font-semibold tracking-tight text-ink">{experiment.name}</h2>
            <dl className="mt-4 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-ink-muted">Dataset</dt>
                <dd className="mt-1 text-ink">
                  {datasetLabel(experiment.dataset_name)}
                  {experiment.dataset_version ? ` v${experiment.dataset_version}` : ''}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Models</dt>
                <dd className="mt-1 text-ink">{experiment.generator_models.join(' / ')}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Sample size</dt>
                <dd className="mt-1 text-ink">{experiment.question_count} questions</dd>
              </div>
              <div>
                <dt className="text-ink-muted">ID</dt>
                <dd className="mt-1 font-mono text-xs text-ink-secondary">{experiment.id}</dd>
              </div>
            </dl>
          </section>

          <section>
            <p className="text-meta mb-3">Experiment configuration</p>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
              <div>
                <dt className="text-ink-muted">Status</dt>
                <dd className="mt-1 text-ink">{experiment.status}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Dataset</dt>
                <dd className="mt-1 text-ink">
                  {datasetLabel(experiment.dataset_name)}
                  {experiment.dataset_version ? ` v${experiment.dataset_version}` : ''}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Models</dt>
                <dd className="mt-1 text-ink">
                  {generators.map((item) => item.shortName).join(' / ')}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Mutations</dt>
                <dd className="mt-1 text-ink">
                  {experiment.synonym_count} synonym + {experiment.antonym_count} antonym
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Threshold</dt>
                <dd className="mt-1 text-ink">{formatScore(experiment.threshold)}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Completed questions</dt>
                <dd className="mt-1 text-ink">{experiment.question_count}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">Mutation reuse</dt>
                <dd className="mt-1 text-ink">
                  {experiment.mutation_reuse_valid == null
                    ? 'n/a'
                    : experiment.mutation_reuse_valid
                      ? 'valid'
                      : 'violation recorded'}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">Trials</dt>
                <dd className="mt-1 text-ink">{experiment.trials}</dd>
              </div>
            </dl>
          </section>

          <ExperimentMatrix generators={generators} verifiers={verifiers} cells={cells} />

          <section className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-line py-5 lg:grid-cols-4">
            <MetricCard
              label="Mean hallucination score"
              value={meanScore == null ? '—' : formatScore(meanScore)}
            />
            <MetricCard
              label="NOT SURE rate"
              value={meanNotSure == null ? '—' : formatPercent(meanNotSure)}
            />
            <MetricCard
              label="Classification flip rate"
              value={formatPercent(experiment.classification_flip_rate)}
            />
            <MetricCard
              label="Statistical significance"
              value={anySignificant ? 'p < 0.05 (paired tests)' : 'No p < 0.05 detected'}
            />
          </section>

          <ExperimentChart cells={cells} />

          <ConditionSummaryTable rows={experiment.condition_summaries} />

          <SelfVerificationSection blocks={experiment.self_verification} />

          <section className="panel p-5">
            <p className="text-meta">Key Finding</p>
            <p className="mt-2 text-[15px] leading-7 text-ink">{experiment.key_finding}</p>
          </section>

          <PairedQuestionsTable
            rows={experiment.paired_comparisons}
            selectedId={selectedGenerationId}
            onSelect={(row) => void handleSelectPaired(row)}
          />

          {trace ? <GenerationTracePanel trace={trace} /> : null}

          <div className="flex flex-wrap gap-4">
            <button
              type="button"
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              onClick={() => void exportExperimentCsv(experiment.id)}
            >
              Export condition CSV
            </button>
            <button
              type="button"
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              onClick={() => void exportExperimentSummaryCsv(experiment.id)}
            >
              Export summary CSV
            </button>
            <button
              type="button"
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              onClick={() => void exportExperimentPairedCsv(experiment.id)}
            >
              Export paired CSV
            </button>
            <button
              type="button"
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              onClick={() => void exportExperimentFlipCsv(experiment.id)}
            >
              Export flip CSV
            </button>
            <button
              type="button"
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              onClick={() => void exportExperimentSweepCsv(experiment.id)}
            >
              Export threshold-sweep CSV
            </button>
            <button
              type="button"
              className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
              onClick={() => void exportExperimentConfig(experiment.id)}
            >
              Export experiment config
            </button>
          </div>
        </div>
      ) : null}

      <section className="mt-12 border-t border-line pt-8">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-2xl">
            <p className="text-meta mb-2">Dataset evaluation</p>
            <h2 className="text-[1.4rem] font-semibold tracking-tight text-ink">Held-out ground truth</h2>
            <p className="mt-2 text-[15px] leading-6 text-ink-secondary">
              Compare VeriFact predictions with held-out labels. Ground-truth answers are never sent into MetaQA.
            </p>
          </div>
          <button
            type="button"
            className="btn-primary shrink-0"
            onClick={() => void handleRunEvaluation()}
            disabled={runningEvaluation}
          >
            {runningEvaluation ? 'Running…' : 'Run pilot evaluation'}
          </button>
        </div>

        {evaluation?.demo_data ? (
          <div
            role="status"
            className="mb-6 rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3 py-2 text-xs leading-5 text-ink-secondary"
          >
            DEMO / MOCK DATA — this evaluation used deterministic mock responses, not a live model.
          </div>
        ) : evaluation ? (
          <div
            role="status"
            className="mb-6 rounded-[var(--radius-sm)] border border-line bg-surface-muted px-3 py-2 text-xs leading-5 text-ink-secondary"
          >
            LIVE EXPERIMENT — MetaQA detector evaluation on generated answers. Ground truth stayed out of the detector prompt.
          </div>
        ) : null}

        {!evaluation ? (
          <EmptyState
            title="No evaluation yet"
            description="Run the 40-question pilot dataset to compute precision, recall, F1, and a confusion matrix."
            action={
              <button type="button" className="btn-primary" onClick={() => void handleRunEvaluation()}>
                Run pilot evaluation
              </button>
            }
          />
        ) : (
          <div className="space-y-10">
            <section>
              <p className="text-meta mb-3">Configuration</p>
              <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
                <div>
                  <dt className="text-ink-muted">Dataset</dt>
                  <dd className="mt-1 text-ink">
                    {evaluation.dataset_name} v{evaluation.dataset_version}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Generator</dt>
                  <dd className="mt-1 text-ink">{evaluation.generator_model}</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Verifier</dt>
                  <dd className="mt-1 text-ink">{evaluation.verifier_model}</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Questions</dt>
                  <dd className="mt-1 text-ink">
                    {evaluation.completed_examples} / {evaluation.total_examples}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Threshold</dt>
                  <dd className="mt-1 text-ink">{formatScore(evaluation.threshold)}</dd>
                </div>
              </dl>
            </section>

            <section>
              <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-y border-line py-5 lg:grid-cols-4">
                <MetricCard label="Accuracy" value={formatScore(evaluation.metrics.accuracy)} />
                <MetricCard label="Precision" value={formatScore(evaluation.metrics.precision)} />
                <MetricCard label="Recall" value={formatScore(evaluation.metrics.recall)} />
                <MetricCard label="F1" value={formatScore(evaluation.metrics.f1, 3)} />
              </div>
            </section>

            <ConfusionMatrixCard {...evaluation.confusion_matrix} />

            <ThresholdSweepChart rows={evaluation.threshold_sweep} />

            <section className="border-l-2 border-accent/40 pl-4">
              <p className="text-[11px] font-semibold tracking-[0.08em] text-accent uppercase">Best F1 threshold</p>
              <p className="mt-2 text-[15px] leading-7 text-ink">
                {evaluation.best_threshold_by_f1 == null
                  ? 'Not enough labeled examples to select a threshold.'
                  : `${formatScore(evaluation.best_threshold_by_f1)} (experimental only; production threshold is unchanged).`}
              </p>
            </section>

            <section>
              <h2 className="text-base font-semibold tracking-tight text-ink">Category analysis</h2>
              <div className="panel mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-surface-muted/50 text-[11px] font-semibold tracking-[0.06em] text-ink-muted uppercase">
                    <tr>
                      <th className="px-4 py-2.5">Category</th>
                      <th className="px-4 py-2.5">Count</th>
                      <th className="px-4 py-2.5">Accuracy</th>
                      <th className="px-4 py-2.5">Mean score</th>
                      <th className="px-4 py-2.5">FP</th>
                      <th className="px-4 py-2.5">FN</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.category_metrics.map((row) => (
                      <tr key={row.category} className="border-b border-line last:border-b-0">
                        <td className="px-4 py-3">{row.category.replace('_', ' ')}</td>
                        <td className="px-4 py-3 tabular-nums">{row.count}</td>
                        <td className="px-4 py-3 tabular-nums">{formatScore(row.accuracy)}</td>
                        <td className="px-4 py-3 tabular-nums">{formatScore(row.mean_hallucination_score)}</td>
                        <td className="px-4 py-3 tabular-nums">{row.fp}</td>
                        <td className="px-4 py-3 tabular-nums">{row.fn}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <EvaluationResultsTable results={evaluation.results} />

            <div className="flex flex-wrap gap-4">
              <button
                type="button"
                className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
                onClick={() => void exportEvaluationCsv(evaluation.evaluation_id)}
              >
                Export CSV
              </button>
              <button
                type="button"
                className="text-sm text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
                onClick={() => void exportEvaluationSweepCsv(evaluation.evaluation_id)}
              >
                Export threshold-sweep CSV
              </button>
            </div>

            {history.length > 1 ? (
              <section>
                <h2 className="mb-3 text-base font-semibold tracking-tight text-ink">Previous runs</h2>
                <ul className="space-y-2 text-sm">
                  {history.slice(1, 6).map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        className="text-ink-secondary underline-offset-4 hover:text-ink hover:underline"
                        onClick={() => void getEvaluation(item.id).then(setEvaluation)}
                      >
                        {item.dataset_name} · {formatTimestamp(item.created_at)}
                        {item.llm_mode === 'mock' ? ' · DEMO' : ''}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        )}
      </section>
    </div>
  )
}
