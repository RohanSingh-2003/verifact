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

export const ExperimentStatus = {
  Loading: 'loading',
  Completed: 'completed',
} as const

export type ExperimentStatus = (typeof ExperimentStatus)[keyof typeof ExperimentStatus]

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
  llmMode?: 'mock' | 'live'
  status: RunStatus
  analysisError?: string | null
  timing?: {
    answerMs?: number | null
    mutationMs?: number | null
    verifyMs?: number | null
    totalMs?: number | null
    timeToAnswerMs?: number | null
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
  llmMode: 'mock' | 'live'
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
  llm_mode: 'mock' | 'live' | string
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

export const HALLUCINATION_ANALYSIS_STEPS = [
  { id: 'answer', label: 'Answer generated' },
  { id: 'mutations', label: 'Creating test mutations' },
  { id: 'verify', label: 'Verifying mutations' },
  { id: 'score', label: 'Calculating score' },
] as const
