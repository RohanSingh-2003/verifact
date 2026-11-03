from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

AnnotationLabel = Literal["RELIABLE", "HALLUCINATED", "NEEDS_REVIEW"]
ValidationStatus = Literal["pending", "reviewed", "adjudicated", "legacy_inferred", "unreviewed"]


class AnnotationCreateRequest(BaseModel):
    evaluation_result_id: str
    evaluation_run_id: str | None = None
    question_id: str
    question: str
    generated_answer: str
    reference_answer: str
    judge_label: AnnotationLabel | None = None
    judge_reasoning: str | None = None
    judge_confidence: float | None = None
    reviewer1_id: str | None = None
    reviewer1_label: AnnotationLabel | None = None
    reviewer1_notes: str | None = None
    reviewer2_id: str | None = None
    reviewer2_label: AnnotationLabel | None = None
    reviewer2_notes: str | None = None
    adjudicated_label: AnnotationLabel | None = None
    adjudicator_id: str | None = None
    adjudication_notes: str | None = None
    adjudication_evidence: str | None = None


class AnnotationUpdateRequest(BaseModel):
    reviewer1_id: str | None = None
    reviewer1_label: AnnotationLabel | None = None
    reviewer1_notes: str | None = None
    reviewer2_id: str | None = None
    reviewer2_label: AnnotationLabel | None = None
    reviewer2_notes: str | None = None
    adjudicated_label: AnnotationLabel | None = None
    adjudicator_id: str | None = None
    adjudication_notes: str | None = None
    adjudication_evidence: str | None = None


class AnnotationOut(BaseModel):
    id: str
    evaluation_result_id: str
    evaluation_run_id: str | None
    question_id: str
    question: str
    generated_answer: str
    reference_answer: str
    judge_label: str | None
    judge_reasoning: str | None
    judge_confidence: float | None
    reviewer1_id: str | None
    reviewer1_label: str | None
    reviewer1_notes: str | None
    reviewer2_id: str | None
    reviewer2_label: str | None
    reviewer2_notes: str | None
    disagreement: bool
    adjudicated_label: str | None
    adjudicator_id: str | None
    adjudication_notes: str | None
    adjudication_evidence: str | None
    validation_status: str
    created_at: datetime
    updated_at: datetime


class AgreementStatsOut(BaseModel):
    total_annotated: int
    both_reviewed_count: int
    human_cohens_kappa: float | None
    human_observed_agreement: float | None
    disagreements_count: int
    adjudicated_count: int
    judge_human_observed_agreement: float | None
    judge_human_cohens_kappa: float | None
    label_distribution: dict[str, int] = Field(default_factory=dict)

