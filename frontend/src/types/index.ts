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
  verdict: 'Correct' | 'Incorrect' | 'Uncertain' | 'YES' | 'NO' | 'NOT SURE' | 'FAILED' | 'PENDING' | string
  reasoning?: string
  rationale?: string
  contradictoryClaims?: string[]
  confidence?: number | null
  error?: string | null
  status: 'completed' | 'failed' | 'pending' | string
}

export interface MultiModelVerificationSummary {
  totalVerifiers: number
  completedVerifiers: number
  correctCount: number
  incorrectCount: number
  uncertainCount: number
  failedCount: number
  agreementState: 'AGREEMENT' | 'DISAGREEMENT' | 'UNCERTAIN' | 'FAILED' | 'PENDING' | string
  summaryText: string
  disagreementsDetected: boolean
  contradictoryClaims: string[]
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
  multiModelSummary?: MultiModelVerificationSummary | null
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
  combinedRiskScore: number | null
  metaqaScore: number | null
  webConsistencyScore: number | null
  verdict: Verdict | null
  overallVerdict: string | null
  overallLabel: string | null
  metaqaClassification: string | null
  status: RunStatus
  createdAt: string
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
