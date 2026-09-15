from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class ExperimentConfigError(ValueError):
    """Invalid experiment configuration."""


class ExperimentIntegrityError(RuntimeError):
    """The fixed-mutation control was violated."""


class ExperimentRunRequest(BaseModel):
    name: str = Field(default="Verifier comparison", max_length=255)
    dataset: str = Field(default="pilot", min_length=1, max_length=128)
    dataset_ref: str | None = Field(default=None, max_length=255)
    generator_models: list[str] = Field(default_factory=lambda: ["model-a", "model-b"])
    verifier_models: list[str] = Field(default_factory=lambda: ["model-a", "model-b"])
    synonym_count: int = Field(default=5, ge=1, le=20)
    antonym_count: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    trials: int = Field(default=1, ge=1, le=5)
    max_questions: int | None = Field(default=None, ge=1, le=500)
    confirm_live_run: bool = False
    resume_experiment_id: str | None = Field(default=None, max_length=36)

    @field_validator("generator_models", "verifier_models")
    @classmethod
    def two_distinct_models(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) != 2:
            raise ValueError("Provide exactly two model names.")
        if cleaned[0] == cleaned[1]:
            raise ValueError("The two model names must be different.")
        return cleaned

    @model_validator(mode="after")
    def dataset_alias(self) -> ExperimentRunRequest:
        if self.dataset_ref and self.dataset == "pilot":
            self.dataset = self.dataset_ref
        return self


class ExperimentOut(BaseModel):
    """Backward-compatible summary used by /latest and list views."""

    id: str
    experiment_id: str | None = None
    name: str
    dataset_ref: str
    status: str
    created_at: str | None = None
    summary_stats: dict = Field(default_factory=dict)
    condition_count: int = 0
    demo_data: bool = False


class MutationTraceOut(BaseModel):
    id: str
    type: str
    original_text: str
    mutated_text: str
    verdict: str
    expected_verdict: str
    contribution: float
    rationale: str


class ConditionTraceOut(BaseModel):
    verifier_model: str
    pair_type: str
    hallucination_score: float
    classification: str
    not_sure_rate: float
    mutations: list[MutationTraceOut]


class GenerationTraceOut(BaseModel):
    generation_id: str
    question_id: str
    question: str
    generator_model: str
    base_answer: str
    conditions: list[ConditionTraceOut]
