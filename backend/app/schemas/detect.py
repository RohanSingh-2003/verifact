from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.metaqa.scoring import Classification, MutationType, Verdict


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
    verdict: Verdict
    expected_verdict: Verdict
    contribution: float
    rationale: str
    parse_failed: bool = False


class DetectResponse(BaseModel):
    run_id: str
    question: str
    base_answer: BaseAnswerOut
    mutations: list[MutationOut]
    hallucination_score: float
    threshold: float
    classification: Classification
    not_sure_rate: float
    llm_mode: str = "live"
    created_at: datetime


class RunSummary(BaseModel):
    id: str
    question: str
    generator_model: str
    hallucination_score: float
    classification: Classification
    created_at: datetime


class RunListResponse(BaseModel):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int
