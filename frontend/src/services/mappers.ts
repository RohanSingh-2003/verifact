import type {
  AnalysisResult,
  ExperimentSnapshot,
  HistoryRun,
  MutationRecord,
  OverallStatus,
  RunStatus,
  Verdict,
  VerificationSummary,
  WebClaimRecord,
  WebEvidenceResult,
  WebSourceRecord,
} from '../types'
import {
  EvidenceVerdict,
  ExperimentStatus,
  MutationKind,
  OverallStatus as OverallStatusValue,
  RunStatus as RunStatusValue,
  SignalRelationship,
  Verdict as VerdictValue,
  VerifierResponse,
  WebEvidenceStatus,
} from '../types'

interface DetectApiModelVerdict {
  model_id: string
  model_name: string
  model?: string
  provider: string
  verdict: string
  rationale?: string
  error?: string | null
  contribution?: number | null
  status?: string
}

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
  parse_failed?: boolean
  verdicts?: DetectApiModelVerdict[]
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
  answer_generation_ms?: number | null
  metaqa_total_ms?: number | null
  metaqa_mutation_generation_ms?: number | null
  metaqa_verification_ms?: number | null
  web_total_ms?: number | null
  web_claim_extraction_ms?: number | null
  web_search_ms?: number | null
  web_verification_ms?: number | null
  total_analysis_ms?: number | null
  number_of_tavily_searches?: number | null
  number_of_web_claims?: number | null
  number_of_ollama_calls?: number | null
}

interface DetectApiWebSource {
  title: string
  url: string
  domain: string
  snippet: string
  published_at?: string | null
  relevance_score?: number | null
  source_type?: string | null
  question_type?: string | null
  evidence_summary?: string | null
}

interface DetectApiWebClaim {
  id: string
  text: string
  search_query?: string
  verdict: string
  reason?: string
  used_fallback?: boolean
  sources?: DetectApiWebSource[]
}

interface DetectApiWebEvidence {
  status: string
  error?: string | null
  searches_used?: number
  sources_found?: number
  question_type?: string | null
  question_type_label?: string | null
  question_type_confidence?: number | null
  source_strategy_labels?: string[]
  freshness_required?: boolean
  used_fallback_search?: boolean
  total_claims?: number
  supported_claims?: number
  contradicted_claims?: number
  insufficient_claims?: number
  consistency_score?: number | null
  consistency_verdict?: string | null
  consistency_verdict_label?: string | null
  claims?: DetectApiWebClaim[]
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
  status?: RunStatus
  overall_status?: string | null
  analysis_error?: string | null
  web_evidence?: DetectApiWebEvidence | null
  verification_summary?: DetectApiVerificationSummary | null
  answer_model?: { id: string; name: string; provider: string; model_name?: string } | null
  verifiers?: Array<{ id: string; name: string; provider: string; status: string }> | null
  ai_verdicts?: Array<{
    model_id: string
    model_name: string
    provider: string
    verdict: string
    rationale?: string
    error?: string | null
    status: string
  }> | null
  timing?: DetectApiTiming | null
}

interface DetectApiVerificationSummary {
  ready?: boolean
  metaqa_signal?: string
  metaqa_label?: string
  metaqa_score?: number | null
  metaqa_classification?: string | null
  metaqa_interpretation?: string
  web_signal?: string
  web_label?: string
  web_interpretation?: string
  web_total_claims?: number
  web_supported?: number
  web_contradicted?: number
  web_insufficient?: number
  web_consistency_score?: number | null
  web_consistency_verdict?: string | null
  web_consistency_verdict_label?: string | null
  relationship?: string
  relationship_label?: string
  relationship_detail?: string
  attention_claims?: DetectApiWebClaim[]
  overall_verdict?: string | null
  overall_label?: string | null
  overall_explanation?: string
  metaqa_summary_text?: string
  web_summary_text?: string
  combined_risk_score?: number | null
  web_risk_score?: number | null
  overall_note?: string
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

function mapOverallStatus(status: string | null | undefined): OverallStatus | undefined {
  if (
    status === OverallStatusValue.Running ||
    status === OverallStatusValue.Completed ||
    status === OverallStatusValue.Partial ||
    status === OverallStatusValue.Failed
  ) {
    return status
  }
  return undefined
}

function mapVerifier(value: DetectApiMutation['verdict'] | DetectApiMutation['expected_verdict']) {
  if (value === 'YES') return VerifierResponse.Yes
  if (value === 'NO') return VerifierResponse.No
  if (value === 'NOT SURE') return VerifierResponse.NotSure
  return null
}

function mapMutation(item: DetectApiMutation): MutationRecord {
  const verified = item.verified !== false && item.verdict != null && !item.parse_failed
  const verdicts = (item.verdicts || []).map((v) => ({
    modelId: v.model_id,
    modelName: v.model_name,
    provider: v.provider,
    verdict: v.verdict,
    rationale: v.rationale || '',
    error: v.error ?? null,
    contribution: v.contribution ?? null,
    status: v.status || 'completed',
  }))

  return {
    id: item.id,
    kind: item.type === 'synonym' ? MutationKind.Synonym : MutationKind.Antonym,
    original: item.original_text,
    mutation: item.mutated_text,
    verifier: verified ? mapVerifier(item.verdict) : null,
    expected: mapVerifier(item.expected_verdict) ?? VerifierResponse.Yes,
    score: verified ? item.contribution : null,
    reasoning: item.rationale || '',
    verified,
    parseFailed: Boolean(item.parse_failed),
    verdicts,
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

function mapWebClaim(item: DetectApiWebClaim, index: number): WebClaimRecord {
  const verdictRaw = String(item.verdict || EvidenceVerdict.InsufficientEvidence)
  const verdict = Object.values(EvidenceVerdict).includes(verdictRaw as EvidenceVerdict)
    ? (verdictRaw as EvidenceVerdict)
    : EvidenceVerdict.InsufficientEvidence
  const sources: WebSourceRecord[] = (item.sources ?? [])
    .filter((source) => Boolean(source.url))
    .map((source) => ({
      title: source.title || source.url,
      url: source.url,
      domain: source.domain || '',
      snippet: source.snippet || '',
      publishedAt: source.published_at ?? null,
      relevanceScore: source.relevance_score ?? null,
      sourceType: source.source_type || 'GENERAL',
      questionType: source.question_type ?? null,
      evidenceSummary: source.evidence_summary ?? null,
    }))
  return {
    id: item.id || `claim_${index + 1}`,
    text: item.text || '',
    searchQuery: item.search_query || '',
    verdict,
    reason: item.reason || '',
    usedFallback: Boolean(item.used_fallback),
    sources,
  }
}

function mapWebEvidence(payload: DetectApiWebEvidence | null | undefined): WebEvidenceResult | null {
  if (!payload) return null
  const statusValues = Object.values(WebEvidenceStatus) as string[]
  const status = statusValues.includes(payload.status)
    ? (payload.status as WebEvidenceResult['status'])
    : WebEvidenceStatus.Pending

  const claims: WebClaimRecord[] = (payload.claims ?? []).map(mapWebClaim)

  return {
    status,
    error: payload.error ?? null,
    searchesUsed: payload.searches_used ?? 0,
    sourcesFound: payload.sources_found ?? 0,
    questionType: payload.question_type ?? null,
    questionTypeLabel: payload.question_type_label ?? null,
    questionTypeConfidence: payload.question_type_confidence ?? null,
    sourceStrategyLabels: payload.source_strategy_labels ?? [],
    freshnessRequired: Boolean(payload.freshness_required),
    usedFallbackSearch: Boolean(payload.used_fallback_search),
    totalClaims: payload.total_claims ?? claims.length,
    supportedClaims: payload.supported_claims ?? 0,
    contradictedClaims: payload.contradicted_claims ?? 0,
    insufficientClaims: payload.insufficient_claims ?? 0,
    consistencyScore: payload.consistency_score ?? null,
    consistencyVerdict: payload.consistency_verdict ?? null,
    consistencyVerdictLabel: payload.consistency_verdict_label ?? null,
    claims,
  }
}

function mapVerificationSummary(
  payload: DetectApiVerificationSummary | null | undefined,
): VerificationSummary | null {
  if (!payload) return null
  const relationshipValues = Object.values(SignalRelationship) as string[]
  const relationship = relationshipValues.includes(payload.relationship || '')
    ? (payload.relationship as VerificationSummary['relationship'])
    : SignalRelationship.Pending
  return {
    ready: Boolean(payload.ready),
    metaqaSignal: payload.metaqa_signal || 'PENDING',
    metaqaLabel: payload.metaqa_label || 'Pending',
    metaqaScore: payload.metaqa_score ?? null,
    metaqaClassification: payload.metaqa_classification ?? null,
    metaqaInterpretation: payload.metaqa_interpretation || '',
    webSignal: payload.web_signal || 'PENDING',
    webLabel: payload.web_label || 'Pending',
    webInterpretation: payload.web_interpretation || '',
    webTotalClaims: payload.web_total_claims ?? 0,
    webSupported: payload.web_supported ?? 0,
    webContradicted: payload.web_contradicted ?? 0,
    webInsufficient: payload.web_insufficient ?? 0,
    webConsistencyScore: payload.web_consistency_score ?? null,
    webConsistencyVerdict: payload.web_consistency_verdict ?? null,
    webConsistencyVerdictLabel: payload.web_consistency_verdict_label ?? null,
    relationship,
    relationshipLabel: payload.relationship_label || '',
    relationshipDetail: payload.relationship_detail || '',
    attentionClaims: (payload.attention_claims ?? []).map(mapWebClaim),
    overallVerdict: payload.overall_verdict ?? null,
    overallLabel: payload.overall_label ?? null,
    overallExplanation: payload.overall_explanation || '',
    metaqaSummaryText: payload.metaqa_summary_text || '',
    webSummaryText: payload.web_summary_text || '',
    combinedRiskScore: payload.combined_risk_score ?? null,
    webRiskScore: payload.web_risk_score ?? null,
    overallNote: payload.overall_note || '',
  }
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
    status: mapStatus(payload.status),
    overallStatus: mapOverallStatus(payload.overall_status),
    analysisError: payload.analysis_error ?? null,
    webEvidence: mapWebEvidence(payload.web_evidence),
    verificationSummary: mapVerificationSummary(payload.verification_summary),
    answerModel: payload.answer_model
      ? {
          id: payload.answer_model.id,
          name: payload.answer_model.name,
          provider: payload.answer_model.provider,
        }
      : null,
    verifiers: (payload.verifiers ?? []).map((v) => ({
      id: v.id,
      name: v.name,
      provider: v.provider,
      status: v.status,
    })),
    aiVerdicts: (payload.ai_verdicts ?? []).map((v) => ({
      modelId: v.model_id,
      modelName: v.model_name,
      provider: v.provider,
      verdict: v.verdict,
      rationale: v.rationale,
      error: v.error ?? null,
      status: v.status,
    })),
    timing: timing
      ? {
          answerMs: timing.answer_ms,
          mutationMs: timing.mutation_ms,
          verifyMs: timing.verify_ms,
          totalMs: timing.total_ms,
          timeToAnswerMs: timing.time_to_answer_ms ?? timing.answer_ms,
          answerGenerationMs: timing.answer_generation_ms ?? timing.answer_ms,
          metaqaTotalMs: timing.metaqa_total_ms ?? timing.total_ms,
          metaqaMutationGenerationMs: timing.metaqa_mutation_generation_ms ?? timing.mutation_ms,
          metaqaVerificationMs: timing.metaqa_verification_ms ?? timing.verify_ms,
          webTotalMs: timing.web_total_ms,
          webClaimExtractionMs: timing.web_claim_extraction_ms,
          webSearchMs: timing.web_search_ms,
          webVerificationMs: timing.web_verification_ms,
          totalAnalysisMs: timing.total_analysis_ms,
          numberOfTavilySearches: timing.number_of_tavily_searches,
          numberOfWebClaims: timing.number_of_web_claims,
          numberOfOllamaCalls: timing.number_of_ollama_calls,
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
