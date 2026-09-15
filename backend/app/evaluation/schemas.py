from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.metaqa.scoring import Classification

ALLOWED_CATEGORIES = frozenset(
    {"named_entity", "date", "numeric", "location", "general_fact"}
)


class GroundTruthSource(str, Enum):
    MANUAL = "manual"
    REFERENCE_MATCH = "reference_match"
    NEEDS_REVIEW = "needs_review"


class DatasetExample(BaseModel):
    """One labeled factual QA item. Ground-truth fields are evaluation-only."""

    id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1)
    reference_answer: str = Field(min_length=1)
    ground_truth_label: Classification | None = None
    category: str = "general_fact"
    source: str = "curated"
    aliases: list[str] = Field(default_factory=list)
    needs_review: bool = False
    mock_base_answer: str | None = None
    mock_scenario: str | None = None

    @field_validator("id", "question", "reference_answer", "category", "source")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank.")
        return cleaned

    @field_validator("category")
    @classmethod
    def category_must_be_known(cls, value: str) -> str:
        if value not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"Unsupported category '{value}'. Allowed: {sorted(ALLOWED_CATEGORIES)}"
            )
        return value

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]

    @field_validator("mock_scenario")
    @classmethod
    def clean_scenario(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


class DatasetBundle(BaseModel):
    name: str
    version: str = "1.0"
    description: str = ""
    license: str = ""
    source: str = ""
    examples: list[DatasetExample]


class GroundTruthDecision(BaseModel):
    label: Classification | None
    source: GroundTruthSource
    matched: bool | None = None
    notes: str = ""

    @property
    def is_review(self) -> bool:
        return self.source is GroundTruthSource.NEEDS_REVIEW or self.label is None
