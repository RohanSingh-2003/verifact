import type { AnalysisResult, ExperimentSnapshot, HistoryRun, MutationRecord, RunStatus, Verdict } from '../types'
import { ExperimentStatus, MutationKind, RunStatus as RunStatusValue, Verdict as VerdictValue, VerifierResponse } from '../types'

interface DetectApiMutation {
  id: string
  type: 'synonym' | 'antonym'
  original_text: string
  mutated_text: string
  verdict: 'YES' | 'NO' | 'NOT SURE' | null
  expected_verdict: 'YES' | 'NO' | 'NOT SURE'
  contribution: number | null
  rationale: string
  verified?: boolean
}

interface DetectApiTiming {
  answer_ms?: number | null
  mutation_ms?: number | null
  verify_ms?: number | null
  total_ms?: number | null
  time_to_answer_ms?: number | null
  synonym_count?: number | null
  antonym_count?: number | null
  verify_concurrency?: number | null
}

interface DetectApiResponse {
  run_id: string
  question: string
  base_answer: { text: string; model: string }
  mutations: DetectApiMutation[]
  hallucination_score: number | null
  threshold: number
  classification: 'Hallucinated' | 'Reliable' | null
  not_sure_rate: number | null
  created_at: string
  llm_mode?: 'mock' | 'live'
  status?: RunStatus
  analysis_error?: string | null
  timing?: DetectApiTiming | null
}

interface RunListResponse {
  items: Array<{
    id: string
    question: string
    generator_model: string
    hallucination_score: number | null
    classification: 'Hallucinated' | 'Reliable' | null
    status?: RunStatus
    created_at: string
  }>
  total: number
}

function mapVerdict(value: 'Hallucinated' | 'Reliable' | null | undefined): Verdict | null {
  if (value === 'Hallucinated') return VerdictValue.Hallucinated
  if (value === 'Reliable') return VerdictValue.Reliable
  return null
}

function mapStatus(value: string | undefined): RunStatus {
  if (value === RunStatusValue.AnswerReady) return RunStatusValue.AnswerReady
  if (value === RunStatusValue.GeneratingMutations) return RunStatusValue.GeneratingMutations
  if (value === RunStatusValue.MutationsReady) return RunStatusValue.MutationsReady
  if (value === RunStatusValue.VerifyingMutations) return RunStatusValue.VerifyingMutations
  if (value === RunStatusValue.CalculatingScore) return RunStatusValue.CalculatingScore
  if (value === RunStatusValue.MutationGenerationFailed) return RunStatusValue.MutationGenerationFailed
  if (value === RunStatusValue.VerificationFailed) return RunStatusValue.VerificationFailed
  if (value === RunStatusValue.ScoringFailed) return RunStatusValue.ScoringFailed
  if (value === RunStatusValue.Failed) return RunStatusValue.Failed
  if (value === RunStatusValue.Completed) return RunStatusValue.Completed
  return RunStatusValue.Completed
}

function mapVerifier(value: DetectApiMutation['verdict'] | DetectApiMutation['expected_verdict']) {
  if (value === 'YES') return VerifierResponse.Yes
  if (value === 'NO') return VerifierResponse.No
  if (value === 'NOT SURE') return VerifierResponse.NotSure
  return null
}

function mapMutation(item: DetectApiMutation): MutationRecord {
  const verified = item.verified !== false && item.verdict != null
  return {
    id: item.id,
    kind: item.type === 'synonym' ? MutationKind.Synonym : MutationKind.Antonym,
    original: item.original_text,
    mutation: item.mutated_text,
    verifier: verified ? mapVerifier(item.verdict) : null,
    expected: mapVerifier(item.expected_verdict) ?? VerifierResponse.Yes,
    score: verified ? item.contribution : null,
    reasoning: verified ? item.rationale : '',
    verified,
  }
}

function meanContribution(items: DetectApiMutation[]): string {
  const verified = items.filter((item) => item.verified !== false && item.contribution != null)
  if (verified.length === 0) return 'n/a'
  const mean = verified.reduce((sum, item) => sum + (item.contribution ?? 0), 0) / verified.length
  return mean.toFixed(2)
}

function summaryPoints(result: DetectApiResponse): string[] {
  if (!result.mutations.length || result.hallucination_score == null || !result.classification) {
    return []
  }
  const verifiedMutations = result.mutations.filter((item) => item.verified !== false && item.verdict != null)
  const unexpected = verifiedMutations.filter((item) => item.verdict !== item.expected_verdict).length
  const synonyms = result.mutations.filter((item) => item.type === 'synonym')
  const antonyms = result.mutations.filter((item) => item.type === 'antonym')
  return [
    `${result.mutations.length} mutations evaluated (${synonyms.length} synonym, ${antonyms.length} antonym).`,
    `${unexpected} inconsistent verifier response${unexpected === 1 ? '' : 's'} relative to the expected MetaQA verdict.`,
    `Synonym contribution (mean): ${meanContribution(synonyms)}.`,
    `Antonym contribution (mean): ${meanContribution(antonyms)}.`,
    `Final score: ${result.hallucination_score.toFixed(2)}.`,
    `Threshold: ${result.threshold.toFixed(2)}.`,
    `Final classification: ${result.classification}.`,
    `NOT SURE rate: ${((result.not_sure_rate ?? 0) * 100).toFixed(0)}% (diagnostic only; rationales do not affect the score).`,
  ]
}

export function mapDetectResponse(payload: DetectApiResponse, responseTimeMs: number): AnalysisResult {
  const timing = payload.timing
  const timeToAnswer = timing?.time_to_answer_ms ?? timing?.answer_ms ?? null
  return {
    id: payload.run_id,
    question: payload.question,
    answer: payload.base_answer.text,
    model: payload.base_answer.model,
    responseTimeMs: timeToAnswer != null ? Math.round(timeToAnswer) : responseTimeMs,
    score: payload.hallucination_score,
    verdict: mapVerdict(payload.classification),
    threshold: payload.threshold,
    createdAt: payload.created_at,
    mutations: (payload.mutations ?? []).map(mapMutation),
    summaryPoints: summaryPoints(payload),
    llmMode: payload.llm_mode,
    status: mapStatus(payload.status),
    analysisError: payload.analysis_error ?? null,
    timing: timing
      ? {
          answerMs: timing.answer_ms,
          mutationMs: timing.mutation_ms,
          verifyMs: timing.verify_ms,
          totalMs: timing.total_ms,
          timeToAnswerMs: timing.time_to_answer_ms ?? timing.answer_ms,
        }
      : undefined,
  }
}

export function mapRunSummary(item: RunListResponse['items'][number]): HistoryRun {
  return {
    id: item.id,
    question: item.question,
    model: item.generator_model,
    score: item.hallucination_score,
    verdict: mapVerdict(item.classification),
    status: mapStatus(item.status),
    createdAt: item.created_at,
  }
}

export function emptyExperimentSnapshot(): ExperimentSnapshot {
  return {
    status: ExperimentStatus.Loading,
    generatorModels: [],
    verifierModels: [],
    dataset: 'Not configured',
    synonymCount: 5,
    antonymCount: 5,
    cells: [],
    metrics: {
      meanHallucinationScore: 0,
      classificationFlipRate: 0,
      precision: 0,
      recall: 0,
      f1: 0,
    },
    keyFinding: 'The full 2×2 experiment has not been run yet.',
    info: {
      datasetSize: 0,
      completedRuns: 0,
      models: [],
      mutationCount: 10,
      timestamp: new Date().toISOString(),
    },
  }
}

export type { DetectApiResponse, RunListResponse }
