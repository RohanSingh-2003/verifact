from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    dataset: str = Field(default="pilot", min_length=1, max_length=128)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    name: str | None = Field(default=None, max_length=255)
    max_questions: int | None = Field(default=None, ge=1, le=500)
    generator_model: str | None = Field(default=None, max_length=128)
    verifier_model: str | None = Field(default=None, max_length=128)
    confirm_live_run: bool = False
    evaluate_web_evidence: bool = True
    evaluate_multi_model: bool = True
    min_completed_verifiers: int | None = Field(default=None, ge=1, le=10)
    benchmark_mode: Literal["formal", "legacy"] = "legacy"
    evaluate_judge: bool = False


class ConfusionMatrixOut(BaseModel):
    tn: int
    fp: int
    fn: int
    tp: int


class MetricsOut(BaseModel):
    threshold: float
    tp: int
    tn: int
    fp: int
    fn: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    specificity: float
    fpr: float
    fnr: float
    included_examples: int
    is_primary: bool = False
    component: str = "metaqa"
    coverage: float = 1.0
    abstained_examples: int = 0


class CategoryMetricOut(BaseModel):
    category: str
    count: int
    accuracy: float
    mean_hallucination_score: float
    fp: int
    fn: int


class EvaluationResultOut(BaseModel):
    question_id: str
    question: str
    reference_answer: str
    generated_answer: str
    actual_label: str
    predicted_label: str
    hallucination_score: float
    category: str
    outcome: str
    ground_truth_source: str
    run_id: str | None = None
    metaqa_score: float | None = None
    metaqa_prediction: str | None = None
    metaqa_outcome: str | None = None
    web_evidence_score: float | None = None
    web_evidence_verdict: str | None = None
    web_evidence_prediction: str | None = None
    web_evidence_status: str | None = None
    web_evidence_outcome: str | None = None
    multi_model_consensus: str | None = None
    multi_model_prediction: str | None = None
    multi_model_status: str | None = None
    multi_model_agreement: float | None = None
    multi_model_outcome: str | None = None
    combined_risk_score: float | None = None
    combined_verdict: str | None = None
    combined_prediction: str | None = None
    combined_outcome: str | None = None
    latency_ms: float | None = None
    required_quorum: int | None = None
    completed_verifiers: int | None = None
    total_verifiers: int | None = None
    failed_verifiers: int | None = None
    multi_model_abstained: bool | None = None
    judge_label: str | None = None
    judge_reasoning: str | None = None
    judge_confidence: float | None = None
    judge_status: str | None = None
    reviewer1_label: str | None = None
    reviewer2_label: str | None = None
    adjudicated_label: str | None = None
    validation_status: str | None = None


class EvaluationSummary(BaseModel):
    id: str
    name: str
    dataset_name: str
    dataset_version: str
    generator_model: str
    verifier_model: str
    mutation_count: int
    threshold: float
    total_examples: int
    completed_examples: int
    review_examples: int
    status: str
    llm_mode: str
    created_at: datetime
    completed_at: datetime | None = None
    f1: float | None = None
    accuracy: float | None = None


class EvaluationDetail(BaseModel):
    evaluation_id: str
    name: str
    status: str
    dataset_name: str
    dataset_version: str
    generator_model: str
    verifier_model: str
    synonym_count: int
    antonym_count: int
    mutation_count: int
    threshold: float
    best_threshold_by_f1: float | None
    total_examples: int
    completed_examples: int
    review_examples: int
    llm_mode: str
    demo_data: bool
    created_at: datetime
    completed_at: datetime | None
    config: dict
    metrics: MetricsOut
    confusion_matrix: ConfusionMatrixOut
    threshold_sweep: list[MetricsOut]
    category_metrics: list[CategoryMetricOut]
    component_metrics: dict | None = None
    results: list[EvaluationResultOut]


class EvaluationListResponse(BaseModel):
    items: list[EvaluationSummary]
    total: int
