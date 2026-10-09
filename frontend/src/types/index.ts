export const Verdict = {
  Reliable: 'reliable',
  Uncertain: 'uncertain',
  Hallucinated: 'hallucinated',
} as const

export type Verdict = (typeof Verdict)[keyof typeof Verdict]

export const VerifierResponse = {
  Yes: 'yes',
  No: 'no',
  NotSure: 'not_sure',
} as const

export type VerifierResponse = (typeof VerifierResponse)[keyof typeof VerifierResponse]

export const MutationKind = {
  Synonym: 'synonym',
  Antonym: 'antonym',
} as const

export type MutationKind = (typeof MutationKind)[keyof typeof MutationKind]

export const AnalysisStage = {
  Idle: 'idle',
  GeneratingAnswer: 'generating_answer',
  AnswerReady: 'answer_ready',
  GeneratingMutations: 'generating_mutations',
  VerifyingMutations: 'verifying_mutations',
  CalculatingScore: 'calculating_score',
  Complete: 'complete',
  Error: 'error',
  AnalysisFailed: 'analysis_failed',
} as const

export type AnalysisStage = (typeof AnalysisStage)[keyof typeof AnalysisStage]

export const RunStatus = {
  AnswerReady: 'answer_ready',
  GeneratingMutations: 'generating_mutations',
  MutationsReady: 'mutations_ready',
  VerifyingMutations: 'verifying_mutations',
  CalculatingScore: 'calculating_score',
  Completed: 'completed',
  MutationGenerationFailed: 'mutation_generation_failed',
  VerificationFailed: 'verification_failed',
  ScoringFailed: 'scoring_failed',
  Failed: 'failed',
} as const

export type RunStatus = (typeof RunStatus)[keyof typeof RunStatus]

export function isAnalysisFailureStatus(status: RunStatus | string | null | undefined): boolean {
  return (
    status === RunStatus.Failed ||
    status === RunStatus.MutationGenerationFailed ||
    status === RunStatus.VerificationFailed ||
    status === RunStatus.ScoringFailed
  )
}

export function isTerminalRunStatus(status: RunStatus | string | null | undefined): boolean {
  return status === RunStatus.Completed || isAnalysisFailureStatus(status)
}

export const EvidenceVerdict = {
  Supported: 'SUPPORTED',
  Contradicted: 'CONTRADICTED',
  InsufficientEvidence: 'INSUFFICIENT_EVIDENCE',
} as const

export type EvidenceVerdict = (typeof EvidenceVerdict)[keyof typeof EvidenceVerdict]

export const WebEvidenceStatus = {
  Pending: 'pending',
  ClassifyingQuestion: 'classifying_question',
  ExtractingClaims: 'extracting_claims',
  SearchingWeb: 'searching_web',
  VerifyingEvidence: 'verifying_evidence',
  Completed: 'completed',
  Unavailable: 'unavailable',
  Failed: 'failed',
} as const

export type WebEvidenceStatus = (typeof WebEvidenceStatus)[keyof typeof WebEvidenceStatus]

export function isWebEvidenceTerminal(status: WebEvidenceStatus | string | null | undefined): boolean {
  return (
    status === WebEvidenceStatus.Completed ||
    status === WebEvidenceStatus.Unavailable ||
    status === WebEvidenceStatus.Failed
  )
}

export const OverallStatus = {
  Running: 'running',
  Completed: 'completed',
  Partial: 'partial',
  Failed: 'failed',
} as const

export type OverallStatus = (typeof OverallStatus)[keyof typeof OverallStatus]

/** Keep polling while either MetaQA or Web Evidence is non-terminal. */
export function analysisStillRunning(analysis: {
  status: RunStatus | string | null | undefined
  webEvidence?: { status?: WebEvidenceStatus | string | null } | null
}): boolean {
  const metaqaDone = isTerminalRunStatus(analysis.status)
  const webDone = isWebEvidenceTerminal(analysis.webEvidence?.status)
  return !(metaqaDone && webDone)
}

export interface WebSourceRecord {
  title: string
  url: string
  domain: string
  snippet: string
  publishedAt?: string | null
  relevanceScore?: number | null
  sourceType?: string
  questionType?: string | null
  evidenceSummary?: string | null
}

export interface WebClaimRecord {
  id: string
  text: string
  searchQuery: string
  verdict: EvidenceVerdict
  reason: string
  usedFallback?: boolean
  sources: WebSourceRecord[]
}

export interface WebEvidenceResult {
  status: WebEvidenceStatus
  error?: string | null
  searchesUsed: number
  sourcesFound: number
  questionType?: string | null
  questionTypeLabel?: string | null
  questionTypeConfidence?: number | null
  sourceStrategyLabels: string[]
  freshnessRequired: boolean
  usedFallbackSearch: boolean
  totalClaims: number
  supportedClaims: number
  contradictedClaims: number
  insufficientClaims: number
  consistencyScore?: number | null
  consistencyVerdict?: string | null
  consistencyVerdictLabel?: string | null
  claims: WebClaimRecord[]
}

export const SignalRelationship = {
  Agree: 'AGREE',
  Disagree: 'DISAGREE',
  BothConcerning: 'BOTH_CONCERNING',
  WebInsufficient: 'WEB_INSUFFICIENT',
  MetaqaUnavailable: 'METAQA_UNAVAILABLE',
  WebUnavailable: 'WEB_UNAVAILABLE',
  BothUnavailable: 'BOTH_UNAVAILABLE',
  Pending: 'PENDING',
} as const

export type SignalRelationship = (typeof SignalRelationship)[keyof typeof SignalRelationship]

export interface VerificationSummary {
  ready: boolean
  metaqaSignal: string
  metaqaLabel: string
  metaqaScore: number | null
  metaqaClassification: string | null
  metaqaInterpretation: string
  webSignal: string
  webLabel: string
  webInterpretation: string
  webTotalClaims: number
  webSupported: number
  webContradicted: number
  webInsufficient: number
  webConsistencyScore?: number | null
  webConsistencyVerdict?: string | null
  webConsistencyVerdictLabel?: string | null
  relationship: SignalRelationship | string
  relationshipLabel: string
  relationshipDetail: string
  attentionClaims: WebClaimRecord[]
  // Overall VeriFact Assessment
  overallVerdict?: OverallVerdict | string | null
  overallLabel?: string | null
  overallExplanation?: string
  metaqaSummaryText?: string
  webSummaryText?: string
  combinedRiskScore?: number | null
  webRiskScore?: number | null
  overallNote?: string
}

export const OverallVerdict = {
  LikelyReliable: 'LIKELY_RELIABLE',
  PotentiallyHallucinated: 'POTENTIALLY_HALLUCINATED',
  NeedsVerification: 'NEEDS_VERIFICATION',
  InsufficientEvidence: 'INSUFFICIENT_EVIDENCE',
  Unavailable: 'UNAVAILABLE',
  Pending: 'PENDING',
} as const

export type OverallVerdict = (typeof OverallVerdict)[keyof typeof OverallVerdict]

export const ExperimentStatus = {
  Loading: 'loading',
  Completed: 'completed',
} as const

export type ExperimentStatus = (typeof ExperimentStatus)[keyof typeof ExperimentStatus]

export interface ModelVerifierVerdictRecord {
  modelId: string
  modelName: string
  model?: string
  provider: string
  verdict: 'YES' | 'NO' | 'NOT SURE' | 'FAILED' | 'PENDING' | string
  rationale?: string
  error?: string | null
  contribution?: number | null
  status: 'completed' | 'failed' | 'pending' | string
}

export interface MutationRecord {
  id: string
  kind: MutationKind
  original: string
  mutation: string
  verifier: VerifierResponse | null
  expected: VerifierResponse
  score: number | null
  reasoning: string
  verified: boolean
  parseFailed?: boolean
  verdicts?: ModelVerifierVerdictRecord[]
}

export interface AnswerModelOption {
  id: string
  name: string
  provider: string
  providerDisplay: string
  modelName: string
  configured: boolean
  isDefault?: boolean
}

export interface AnswerModelInfo {
  id: string
  name: string
  provider: string
}

export interface VerifierModelInfo {
  id: string
  name: string
  provider: string
  status: string
}

export interface IndependentAiVerdict {
  modelId: string
  modelName: string
  provider: string
  verdict: 'YES' | 'NO' | 'NOT SURE' | 'FAILED' | 'PENDING' | string
  rationale?: string
  error?: string | null
  status: 'completed' | 'failed' | 'pending' | string
}

export interface AnalysisResult {
  id: string
  question: string
  answer: string
  model: string
  responseTimeMs: number
  score: number | null
  verdict: Verdict | null
  threshold: number
  createdAt: string
  mutations: MutationRecord[]
  summaryPoints: string[]
  status: RunStatus
  overallStatus?: OverallStatus
  analysisError?: string | null
  webEvidence?: WebEvidenceResult | null
  verificationSummary?: VerificationSummary | null
  answerModel?: AnswerModelInfo | null
  verifiers?: VerifierModelInfo[]
  aiVerdicts?: IndependentAiVerdict[]
  timing?: {
    answerMs?: number | null
    mutationMs?: number | null
    verifyMs?: number | null
    totalMs?: number | null
    timeToAnswerMs?: number | null
    answerGenerationMs?: number | null
    metaqaTotalMs?: number | null
    metaqaMutationGenerationMs?: number | null
    metaqaVerificationMs?: number | null
    webTotalMs?: number | null
    webClaimExtractionMs?: number | null
    webSearchMs?: number | null
    webVerificationMs?: number | null
    totalAnalysisMs?: number | null
    numberOfTavilySearches?: number | null
    numberOfWebClaims?: number | null
    numberOfOllamaCalls?: number | null
  }
}

export interface HistoryRun {
  id: string
  question: string
  model: string
  score: number | null
  verdict: Verdict | null
  status: RunStatus
  createdAt: string
}

export interface ExperimentCell {
  generatorId: string
  verifierId: string
  label: string
  meanScore: number
  precision: number
  recall: number
  f1: number
  flipRate: number
}

export interface NamedModel {
  id: string
  name: string
  shortName: string
}

export interface ExperimentSnapshot {
  status: ExperimentStatus
  generatorModels: NamedModel[]
  verifierModels: NamedModel[]
  dataset: string
  synonymCount: number
  antonymCount: number
  cells: ExperimentCell[]
  metrics: {
    meanHallucinationScore: number
    classificationFlipRate: number
    precision: number
    recall: number
    f1: number
  }
  keyFinding: string
  info: {
    datasetSize: number
    completedRuns: number
    models: string[]
    mutationCount: number
    timestamp: string
  }
}

export interface ExperimentConditionSummary {
  generator_model: string
  verifier_model: string
  pair_type: string
  label: string
  n: number
  mean_score: number
  median_score: number
  stdev: number
  ci95_low: number | null
  ci95_high: number | null
  reliable_count: number
  hallucinated_count: number
  reliable_rate: number
  hallucinated_rate: number
  not_sure_rate: number
  precision: number | null
  recall: number | null
  f1: number | null
  accuracy: number | null
}

export interface ExperimentHypothesisTest {
  name: string
  statistic: number | null
  p_value: number | null
  n: number
  effect_size: number | null
  notes: string
}

export interface SelfVerificationBlock {
  generator_model: string
  same_model_mean: number
  cross_model_mean: number
  self_verification_score_difference: number
  absolute_effect: number
  percent_difference: number | null
  classification_flip_rate: number
  flip_count: number
  n: number
  exploratory: boolean
  wilcoxon: ExperimentHypothesisTest
  paired_t_test: ExperimentHypothesisTest
  significant: boolean
  alpha: number
}

export interface PairedComparison {
  question_id: string
  question: string
  generator_model: string
  generation_id: string
  same_model_score: number
  cross_model_score: number
  difference: number
  same_label: string
  cross_label: string
  classification_flip: boolean
}

export interface ExperimentChartPoint {
  label: string
  generatorId: string
  verifierId: string
  meanScore: number
  pairType: string
  precision: number
  recall: number
  f1: number
  flipRate: number
}

export interface ExperimentDetail {
  id: string
  experiment_id: string
  name: string
  dataset_ref: string
  dataset_name: string
  dataset_version: string
  status: string
  created_at: string
  completed_at: string | null
  demo_data: boolean
  llm_mode: string
  generator_models: string[]
  verifier_models: string[]
  synonym_count: number
  antonym_count: number
  threshold: number
  trials: number
  question_count: number
  classification_flip_rate: number
  key_finding: string
  condition_summaries: ExperimentConditionSummary[]
  self_verification: SelfVerificationBlock[]
  paired_comparisons: PairedComparison[]
  chart: ExperimentChartPoint[]
  config: Record<string, unknown>
  mutation_reuse_valid?: boolean | null
  exclusions?: unknown[]
  incomplete?: unknown[]
  call_stats?: { success?: number; failed?: number; total?: number }
  category_analysis?: Array<{
    category: string
    generator_model: string
    n: number
    same_model_mean: number
    cross_model_mean: number
    score_difference: number
    flip_rate: number
  }>
}

export interface GenerationTraceMutation {
  id: string
  type: string
  original_text: string
  mutated_text: string
  verdict: string
  expected_verdict: string
  contribution: number
  rationale: string
}

export interface GenerationTraceCondition {
  verifier_model: string
  pair_type: string
  hallucination_score: number
  classification: string
  not_sure_rate: number
  mutations: GenerationTraceMutation[]
}

export interface GenerationTrace {
  generation_id: string
  question_id: string
  question: string
  generator_model: string
  base_answer: string
  conditions: GenerationTraceCondition[]
}

export interface AppSettings {
  threshold: number
  generatorModel: string
  verifierModel: string
  liveReady: boolean
  apiKeyConfigured: boolean
  llmProvider: string
  generatorModelA: string
  generatorModelB: string
  verifierModelA: string
  verifierModelB: string
  maxQuestions: number
  synonymCount: number
  antonymCount: number
  frozenExperimentId: string
  mutationModel: string
  effectiveMutationModel: string
  effectiveVerifierModel: string
  geminiVerifierModel: string
  geminiVerifierReady: boolean
  tavilySearchDepth: string
  webMaxClaims: number
  webMaxSearches: number
  webResultsPerClaim: number
  webEvidenceEnabled: boolean
  webEvidenceReady: boolean
}

export interface SystemHealth {
  status: string
  llm_provider?: string
  live_ready?: boolean
  generator_model?: string
  verifier_model?: string
  web_evidence_ready?: boolean
  web_evidence_enabled?: boolean
  gemini_verifier_enabled?: boolean
  gemini_verifier_ready?: boolean
  gemini_verifier_model?: string
  database_connected?: boolean
}

export type EvalOutcome = 'TP' | 'TN' | 'FP' | 'FN' | 'Needs Review'

export interface EvaluationMetrics {
  threshold: number
  tp: number
  tn: number
  fp: number
  fn: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  specificity: number
  fpr: number
  fnr: number
  included_examples: number
  is_primary: boolean
}

export interface EvaluationResultRow {
  question_id: string
  question: string
  reference_answer: string
  generated_answer: string
  actual_label: string
  predicted_label: string
  hallucination_score: number
  category: string
  outcome: EvalOutcome | string
  ground_truth_source: string
  run_id: string | null
}

export interface EvaluationDetail {
  evaluation_id: string
  name: string
  status: string
  dataset_name: string
  dataset_version: string
  generator_model: string
  verifier_model: string
  synonym_count: number
  antonym_count: number
  mutation_count: number
  threshold: number
  best_threshold_by_f1: number | null
  total_examples: number
  completed_examples: number
  review_examples: number
  llm_mode: string
  demo_data: boolean
  created_at: string
  completed_at: string | null
  metrics: EvaluationMetrics
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number }
  threshold_sweep: EvaluationMetrics[]
  category_metrics: Array<{
    category: string
    count: number
    accuracy: number
    mean_hallucination_score: number
    fp: number
    fn: number
  }>
  results: EvaluationResultRow[]
}

export interface EvaluationSummary {
  id: string
  name: string
  dataset_name: string
  status: string
  llm_mode: string
  threshold: number
  completed_examples: number
  created_at: string
  f1: number | null
}

export const ANALYSIS_STAGE_LABEL: Record<
  Exclude<AnalysisStage, 'idle' | 'complete' | 'error' | 'analysis_failed' | 'answer_ready'>,
  string
> = {
  generating_answer: 'Asking the AI for an answer...',
  generating_mutations: 'Creating same-meaning and opposite-meaning tests...',
  verifying_mutations: 'Checking whether the AI responds consistently...',
  calculating_score: 'Calculating the hallucination score...',
}

export const ANALYSIS_STAGES: Array<
  Exclude<AnalysisStage, 'idle' | 'complete' | 'error' | 'analysis_failed' | 'answer_ready'>
> = [
  AnalysisStage.GeneratingAnswer,
  AnalysisStage.GeneratingMutations,
  AnalysisStage.VerifyingMutations,
  AnalysisStage.CalculatingScore,
]

export const METAQA_ANALYSIS_STEPS = [
  { id: 'mutations', label: 'Creating test mutations' },
  { id: 'verify', label: 'Verifying mutations' },
  { id: 'score', label: 'Calculating score' },
  { id: 'complete', label: 'MetaQA analysis complete' },
] as const

export const WEB_EVIDENCE_STEPS = [
  { id: 'type', label: 'Question type identified' },
  { id: 'claims', label: 'Claims identified' },
  { id: 'search', label: 'Searching recommended sources' },
  { id: 'verify', label: 'Verifying evidence' },
  { id: 'complete', label: 'Evidence analysis complete' },
] as const

/** @deprecated Use METAQA_ANALYSIS_STEPS instead */
export const HALLUCINATION_ANALYSIS_STEPS = [
  { id: 'mutations', label: 'Creating test mutations' },
  { id: 'verify', label: 'Verifying mutations' },
  { id: 'score', label: 'Calculating score' },
  { id: 'complete', label: 'MetaQA analysis complete' },
] as const
