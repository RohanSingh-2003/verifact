from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.metaqa.scoring import Classification, MutationType, Verdict
from app.schemas.verification_summary import VerificationSummaryOut
from app.schemas.web_evidence import WebEvidenceOut


class RunStatus(str, Enum):
    ANSWER_READY = "answer_ready"
    GENERATING_MUTATIONS = "generating_mutations"
    MUTATIONS_READY = "mutations_ready"
    VERIFYING_MUTATIONS = "verifying_mutations"
    CALCULATING_SCORE = "calculating_score"
    COMPLETED = "completed"
    MUTATION_GENERATION_FAILED = "mutation_generation_failed"
    VERIFICATION_FAILED = "verification_failed"
    SCORING_FAILED = "scoring_failed"
    FAILED = "failed"

    @classmethod
    def is_failure(cls, value: str | RunStatus) -> bool:
        raw = value.value if isinstance(value, RunStatus) else value
        return raw in {
            cls.MUTATION_GENERATION_FAILED.value,
            cls.VERIFICATION_FAILED.value,
            cls.SCORING_FAILED.value,
            cls.FAILED.value,
        }

    @classmethod
    def is_terminal(cls, value: str | RunStatus) -> bool:
        raw = value.value if isinstance(value, RunStatus) else value
        return raw == cls.COMPLETED.value or cls.is_failure(raw)


class OverallStatus(str, Enum):
    """Whole-run status across answer + MetaQA + Web Evidence (not a fused score)."""

    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class DetectRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Enter a factual question.")
        return cleaned

    @property
    def cleaned_question(self) -> str:
        return self.question.strip()


class BaseAnswerOut(BaseModel):
    text: str
    model: str


class MutationOut(BaseModel):
    id: str
    type: MutationType
    original_text: str
    mutated_text: str
    verifier_model: str | None = None
    verdict: Verdict | None = None
    expected_verdict: Verdict
    contribution: float | None = None
    rationale: str = ""
    parse_failed: bool = False
    verified: bool = True


class DetectTiming(BaseModel):
    answer_ms: float | None = None
    mutation_ms: float | None = None
    verify_ms: float | None = None
    total_ms: float | None = None
    time_to_answer_ms: float | None = None
    synonym_count: int | None = None
    antonym_count: int | None = None
    verify_concurrency: int | None = None
    answer_generation_ms: float | None = None
    metaqa_total_ms: float | None = None
    metaqa_mutation_generation_ms: float | None = None
    metaqa_verification_ms: float | None = None
    web_total_ms: float | None = None
    web_claim_extraction_ms: float | None = None
    web_search_ms: float | None = None
    web_verification_ms: float | None = None
    total_analysis_ms: float | None = None
    number_of_tavily_searches: int | None = None
    number_of_web_claims: int | None = None
    number_of_ollama_calls: int | None = None


class DetectResponse(BaseModel):
    run_id: str
    question: str
    base_answer: BaseAnswerOut
    mutation_generator_model: str | None = None
    mutation_verifier_model: str | None = None
    mutations: list[MutationOut]
    hallucination_score: float | None
    threshold: float
    classification: Classification | None
    not_sure_rate: float | None
    llm_mode: str = "live"
    status: RunStatus = RunStatus.COMPLETED
    overall_status: OverallStatus = OverallStatus.COMPLETED
    analysis_error: str | None = None
    web_evidence: WebEvidenceOut | None = None
    verification_summary: VerificationSummaryOut | None = None
    created_at: datetime
    timing: DetectTiming | dict[str, float | int] | None = None


class RunSummary(BaseModel):
    id: str
    question: str
    generator_model: str
    hallucination_score: float | None
    classification: Classification | None
    status: RunStatus = RunStatus.COMPLETED
    created_at: datetime


class RunListResponse(BaseModel):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int
