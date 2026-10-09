import type {
  AnalysisResult,
  AnalysisStage,
  AppSettings,
  EvaluationDetail,
  EvaluationSummary,
  ExperimentDetail,
  GenerationTrace,
  HistoryRun,
  RunStatus,
  SystemHealth,
  AnswerModelOption,
} from '../types'
import { AnalysisStage as Stage, RunStatus as RunStatusValue, analysisStillRunning, isAnalysisFailureStatus } from '../types'
import { mapDetectResponse, mapRunSummary } from './mappers'
import type { DetectApiResponse, RunListResponse } from './mappers'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''
const POLL_INTERVAL_MS = 1200
const POLL_TIMEOUT_MS = 15 * 60 * 1000

export interface DetectRunOptions {
  answerModel?: string
  onStage?: (stage: AnalysisStage) => void
  onPartialResult?: (result: AnalysisResult) => void
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function statusToStage(status: RunStatus): AnalysisStage {
  if (status === RunStatusValue.AnswerReady) return Stage.AnswerReady
  if (status === RunStatusValue.GeneratingMutations) return Stage.GeneratingMutations
  if (status === RunStatusValue.MutationsReady) return Stage.VerifyingMutations
  if (status === RunStatusValue.VerifyingMutations) return Stage.VerifyingMutations
  if (status === RunStatusValue.CalculatingScore) return Stage.CalculatingScore
  if (isAnalysisFailureStatus(status)) return Stage.AnalysisFailed
  if (status === RunStatusValue.Completed) return Stage.Complete
  return Stage.GeneratingMutations
}

async function readApiError(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail) && detail[0] && typeof detail[0] === 'object' && 'msg' in detail[0]) {
        return String((detail[0] as { msg: string }).msg)
      }
    }
  } catch {
    // Fall through to status text.
  }
  if (response.status === 404) return 'The requested record was not found.'
  if (response.status === 502 || response.status === 504) {
    return 'The language model request failed. Check the backend configuration and try again.'
  }
  return `Request failed (${response.status}).`
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    throw new Error(await readApiError(response))
  }
  return response
}

export async function detectRun(
  question: string,
  options: DetectRunOptions = {},
): Promise<AnalysisResult> {
  const trimmed = question.trim()
  if (!trimmed) {
    throw new Error('Enter a factual question before running analysis.')
  }

  options.onStage?.(Stage.GeneratingAnswer)
  const started = Date.now()
  const response = await apiFetch('/api/detect', {
    method: 'POST',
    body: JSON.stringify({
      question: trimmed,
      answer_model: options.answerModel || 'gemma',
    }),
  })
  const payload = (await response.json()) as DetectApiResponse
  let result = mapDetectResponse(payload, Date.now() - started)
  options.onPartialResult?.(result)
  options.onStage?.(statusToStage(result.status))

  if (!analysisStillRunning(result)) {
    return result
  }

  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS)
    const polled = await getRun(result.id)
    if (!polled) {
      throw new Error('The analysis run could not be found while waiting for MetaQA results.')
    }
    result = {
      ...polled,
      responseTimeMs: result.responseTimeMs,
    }
    options.onPartialResult?.(result)
    options.onStage?.(statusToStage(result.status))
    // Continue while either MetaQA or Web Evidence is still running.
    // MetaQA failure alone must NOT stop polling.
    if (!analysisStillRunning(result)) {
      return result
    }
  }
  throw new Error('Hallucination analysis timed out. The AI answer is still available on this run.')
}

export async function getRun(id: string): Promise<AnalysisResult | null> {
  const response = await fetch(`${API_BASE}/api/runs/${id}`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(await readApiError(response))
  }
  const payload = (await response.json()) as DetectApiResponse
  return mapDetectResponse(payload, 0)
}

export async function getRuns(): Promise<HistoryRun[]> {
  const response = await apiFetch('/api/runs?limit=50&offset=0')
  const payload = (await response.json()) as RunListResponse
  return payload.items.map(mapRunSummary)
}

export async function runExperiment(payload?: {
  dataset?: string
  generator_models?: string[]
  verifier_models?: string[]
  synonym_count?: number
  antonym_count?: number
  threshold?: number
  trials?: number
  max_questions?: number
  confirm_live_run?: boolean
}): Promise<ExperimentDetail> {
  const settings = await getSettings()
  const live = settings.liveReady
  const generators =
    payload?.generator_models ??
    (live ? [settings.generatorModelA, settings.generatorModelB] : ['model-a', 'model-b'])
  const verifiers =
    payload?.verifier_models ??
    (live ? [settings.verifierModelA, settings.verifierModelB] : ['model-a', 'model-b'])
  const response = await apiFetch('/api/experiments/run', {
    method: 'POST',
    body: JSON.stringify({
      dataset: payload?.dataset ?? 'pilot',
      generator_models: generators,
      verifier_models: verifiers,
      synonym_count: payload?.synonym_count ?? settings.synonymCount,
      antonym_count: payload?.antonym_count ?? settings.antonymCount,
      threshold: payload?.threshold ?? settings.threshold,
      trials: payload?.trials ?? 1,
      max_questions: payload?.max_questions ?? settings.maxQuestions,
      confirm_live_run: payload?.confirm_live_run ?? false,
    }),
  })
  return (await response.json()) as ExperimentDetail
}

export async function getLatestExperiment(): Promise<ExperimentDetail | null> {
  const response = await fetch(`${API_BASE}/api/experiments/latest`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(await readApiError(response))
  }
  return (await response.json()) as ExperimentDetail
}

export async function getExperiment(id: string): Promise<ExperimentDetail> {
  const found = await getExperimentOrNull(id)
  if (!found) {
    throw new Error('The requested experiment was not found.')
  }
  return found
}

export async function getExperimentOrNull(id: string): Promise<ExperimentDetail | null> {
  const response = await fetch(`${API_BASE}/api/experiments/${id}`, {
    headers: { 'Content-Type': 'application/json' },
  })
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error(await readApiError(response))
  }
  return (await response.json()) as ExperimentDetail
}

export async function getGenerationTrace(experimentId: string, generationId: string): Promise<GenerationTrace> {
  const response = await apiFetch(`/api/experiments/${experimentId}/traces/${generationId}`)
  return (await response.json()) as GenerationTrace
}

async function downloadCsv(path: string, filename: string): Promise<void> {
  const response = await apiFetch(path)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function exportExperimentCsv(id: string): Promise<void> {
  await downloadCsv(`/api/experiments/${id}/export`, `verifact-experiment-${id.slice(0, 8)}.csv`)
}

export async function exportExperimentPairedCsv(id: string): Promise<void> {
  await downloadCsv(
    `/api/experiments/${id}/export/paired`,
    `verifact-experiment-paired-${id.slice(0, 8)}.csv`,
  )
}

export async function exportExperimentSummaryCsv(id: string): Promise<void> {
  await downloadCsv(`/api/experiments/${id}/export/summary`, `verifact-experiment-summary-${id.slice(0, 8)}.csv`)
}

export async function exportExperimentFlipCsv(id: string): Promise<void> {
  await downloadCsv(`/api/experiments/${id}/export/flips`, `verifact-experiment-flips-${id.slice(0, 8)}.csv`)
}

export async function exportExperimentSweepCsv(id: string): Promise<void> {
  await downloadCsv(`/api/experiments/${id}/export/sweep`, `verifact-experiment-sweep-${id.slice(0, 8)}.csv`)
}

export async function exportExperimentConfig(id: string): Promise<void> {
  await downloadCsv(`/api/experiments/${id}/export/config`, `verifact-experiment-config-${id.slice(0, 8)}.json`)
}

export async function estimateExperiment(payload?: {
  dataset?: string
  generator_models?: string[]
  verifier_models?: string[]
  synonym_count?: number
  antonym_count?: number
  threshold?: number
  trials?: number
  max_questions?: number
}): Promise<{
  questions: number
  total_calls: number
  calls_per_question: number
  live_confirm_required?: boolean
  live_ready?: boolean
}> {
  const response = await apiFetch('/api/experiments/estimate', {
    method: 'POST',
    body: JSON.stringify({
      dataset: 'pilot',
      ...payload,
    }),
  })
  return (await response.json()) as {
    questions: number
    total_calls: number
    calls_per_question: number
    live_confirm_required?: boolean
    live_ready?: boolean
  }
}

export async function runEvaluation(
  dataset = 'pilot',
  threshold = 0.5,
  options?: { confirm_live_run?: boolean; max_questions?: number; generator_model?: string; verifier_model?: string },
): Promise<EvaluationDetail> {
  const settings = await getSettings()
  const response = await apiFetch('/api/evaluations/run', {
    method: 'POST',
    body: JSON.stringify({
      dataset,
      threshold,
      max_questions: options?.max_questions ?? settings.maxQuestions,
      confirm_live_run: options?.confirm_live_run ?? false,
      generator_model: options?.generator_model ?? (settings.liveReady ? settings.generatorModelA : undefined),
      verifier_model: options?.verifier_model ?? (settings.liveReady ? settings.verifierModelA : undefined),
    }),
  })
  return (await response.json()) as EvaluationDetail
}

export async function getEvaluations(): Promise<EvaluationSummary[]> {
  const response = await apiFetch('/api/evaluations')
  const payload = (await response.json()) as { items: EvaluationSummary[] }
  return payload.items
}

export async function getEvaluation(id: string): Promise<EvaluationDetail> {
  const response = await apiFetch(`/api/evaluations/${id}`)
  return (await response.json()) as EvaluationDetail
}

export async function exportEvaluationCsv(id: string): Promise<void> {
  await downloadCsv(`/api/evaluations/${id}/export`, `verifact-evaluation-${id.slice(0, 8)}.csv`)
}

export async function exportEvaluationSweepCsv(id: string): Promise<void> {
  await downloadCsv(`/api/evaluations/${id}/export/sweep`, `verifact-evaluation-sweep-${id.slice(0, 8)}.csv`)
}

export async function getHealth(): Promise<SystemHealth> {
  const response = await apiFetch('/api/health')
  return (await response.json()) as SystemHealth
}

export async function getSettings(): Promise<AppSettings> {
  const response = await apiFetch('/api/settings')
  const payload = (await response.json()) as {
    live_ready: boolean
    api_key_configured: boolean
    llm_provider?: string
    generator_model: string
    verifier_model: string
    generator_model_a: string
    generator_model_b: string
    verifier_model_a: string
    verifier_model_b: string
    threshold: number
    max_questions: number
    synonym_count: number
    antonym_count: number
    frozen_experiment_id?: string
    mutation_model?: string
    effective_mutation_model?: string
    effective_verifier_model?: string
    gemini_verifier_model?: string
    gemini_verifier_ready?: boolean
    tavily_search_depth?: string
    web_max_claims?: number
    web_max_searches?: number
    web_results_per_claim?: number
    web_evidence_enabled?: boolean
    web_evidence_ready?: boolean
  }
  return {
    threshold: payload.threshold,
    generatorModel: payload.generator_model,
    verifierModel: payload.verifier_model,
    liveReady: payload.live_ready,
    apiKeyConfigured: payload.api_key_configured,
    llmProvider: payload.llm_provider ?? 'openai_compatible',
    generatorModelA: payload.generator_model_a,
    generatorModelB: payload.generator_model_b,
    verifierModelA: payload.verifier_model_a,
    verifierModelB: payload.verifier_model_b,
    maxQuestions: payload.max_questions,
    synonymCount: payload.synonym_count,
    antonymCount: payload.antonym_count,
    frozenExperimentId: payload.frozen_experiment_id ?? '58baff20-fb86-4f43-b20e-895a086ceb6b',
    mutationModel: payload.mutation_model ?? '',
    effectiveMutationModel: payload.effective_mutation_model || payload.generator_model,
    effectiveVerifierModel: payload.effective_verifier_model || payload.verifier_model,
    geminiVerifierModel: payload.gemini_verifier_model ?? '',
    geminiVerifierReady: payload.gemini_verifier_ready ?? false,
    tavilySearchDepth: payload.tavily_search_depth ?? 'basic',
    webMaxClaims: payload.web_max_claims ?? 3,
    webMaxSearches: payload.web_max_searches ?? 3,
    webResultsPerClaim: payload.web_results_per_claim ?? 2,
    webEvidenceEnabled: payload.web_evidence_enabled ?? true,
    webEvidenceReady: payload.web_evidence_ready ?? false,
  }
}

export async function getAvailableModels(): Promise<AnswerModelOption[]> {
  try {
    const response = await apiFetch('/api/models')
    const data = (await response.json()) as {
      models: Array<{
        id: string
        name: string
        provider: string
        provider_display: string
        model_name: string
        configured: boolean
        is_default?: boolean
      }>
    }
    return (data.models ?? []).map((m) => ({
      id: m.id,
      name: m.name,
      provider: m.provider,
      providerDisplay: m.provider_display,
      modelName: m.model_name,
      configured: m.configured,
      isDefault: m.is_default,
    }))
  } catch {
    return [
      { id: 'gemma', name: 'Gemma 4:26B', provider: 'ollama', providerDisplay: 'Ollama Cloud', modelName: 'gemma4:26b', configured: true, isDefault: true },
      { id: 'glm', name: 'GLM-4.7-Flash', provider: 'cloudflare', providerDisplay: 'Cloudflare Workers AI', modelName: '@cf/zai-org/glm-4.7-flash', configured: true, isDefault: false },
      { id: 'qwen', name: 'Qwen', provider: 'groq', providerDisplay: 'Alibaba / Groq', modelName: 'qwen-2.5-32b', configured: true, isDefault: false },
      { id: 'openrouter', name: 'OpenRouter', provider: 'openrouter', providerDisplay: 'OpenRouter', modelName: 'liquid/lfm-2.5-2.6b:free', configured: true, isDefault: false },
      { id: 'gemini', name: 'Gemini Flash 3.8', provider: 'gemini', providerDisplay: 'Google', modelName: 'gemini-3.8-flash', configured: true, isDefault: false },
    ]
  }
}
