import type { AnalysisResult, ExperimentSnapshot, HistoryRun, MutationRecord, Verdict } from '../types'
import { ExperimentStatus, MutationKind, Verdict as VerdictValue, VerifierResponse } from '../types'

interface DetectApiMutation {
  id: string
  type: 'synonym' | 'antonym'
  original_text: string
  mutated_text: string
  verdict: 'YES' | 'NO' | 'NOT SURE'
  expected_verdict: 'YES' | 'NO' | 'NOT SURE'
  contribution: number
  rationale: string
}

interface DetectApiResponse {
  run_id: string
  question: string
  base_answer: { text: string; model: string }
  mutations: DetectApiMutation[]
  hallucination_score: number
  threshold: number
  classification: 'Hallucinated' | 'Reliable'
  not_sure_rate: number
  created_at: string
  llm_mode?: 'mock' | 'live'
}

interface RunListResponse {
  items: Array<{
    id: string
    question: string
    generator_model: string
    hallucination_score: number
    classification: 'Hallucinated' | 'Reliable'
    created_at: string
  }>
  total: number
}

function mapVerdict(value: 'Hallucinated' | 'Reliable'): Verdict {
  return value === 'Hallucinated' ? VerdictValue.Hallucinated : VerdictValue.Reliable
}

function mapVerifier(value: DetectApiMutation['verdict']) {
  if (value === 'YES') return VerifierResponse.Yes
  if (value === 'NO') return VerifierResponse.No
  return VerifierResponse.NotSure
}

function mapMutation(item: DetectApiMutation): MutationRecord {
  return {
    id: item.id,
    kind: item.type === 'synonym' ? MutationKind.Synonym : MutationKind.Antonym,
    original: item.original_text,
    mutation: item.mutated_text,
    verifier: mapVerifier(item.verdict),
    expected: mapVerifier(item.expected_verdict),
    score: item.contribution,
    reasoning: item.rationale,
  }
}

function meanContribution(items: DetectApiMutation[]): string {
  if (items.length === 0) return 'n/a'
  const mean = items.reduce((sum, item) => sum + item.contribution, 0) / items.length
  return mean.toFixed(2)
}

function summaryPoints(result: DetectApiResponse): string[] {
  const unexpected = result.mutations.filter((item) => item.verdict !== item.expected_verdict).length
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
    `NOT SURE rate: ${(result.not_sure_rate * 100).toFixed(0)}% (diagnostic only; rationales do not affect the score).`,
  ]
}

export function mapDetectResponse(payload: DetectApiResponse, responseTimeMs: number): AnalysisResult {
  return {
    id: payload.run_id,
    question: payload.question,
    answer: payload.base_answer.text,
    model: payload.base_answer.model,
    responseTimeMs,
    score: payload.hallucination_score,
    verdict: mapVerdict(payload.classification),
    threshold: payload.threshold,
    createdAt: payload.created_at,
    mutations: payload.mutations.map(mapMutation),
    summaryPoints: summaryPoints(payload),
    llmMode: payload.llm_mode,
  }
}

export function mapRunSummary(item: RunListResponse['items'][number]): HistoryRun {
  return {
    id: item.id,
    question: item.question,
    model: item.generator_model,
    score: item.hallucination_score,
    verdict: mapVerdict(item.classification),
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
