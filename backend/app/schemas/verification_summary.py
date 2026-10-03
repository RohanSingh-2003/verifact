from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.web_evidence import WebClaimOut


class VerificationSummaryOut(BaseModel):
    """Side-by-side MetaQA vs Web Evidence comparison — not a fused score."""

    ready: bool = False
    metaqa_signal: str
    metaqa_label: str
    metaqa_score: float | None = None
    metaqa_classification: str | None = None
    metaqa_interpretation: str = ""
    web_signal: str
    web_label: str
    web_interpretation: str = ""
    web_total_claims: int = 0
    web_supported: int = 0
    web_contradicted: int = 0
    web_insufficient: int = 0
    web_consistency_score: float | None = None
    web_consistency_verdict: str | None = None
    web_consistency_verdict_label: str | None = None
    relationship: str
    relationship_label: str
    relationship_detail: str = ""
    attention_claims: list[WebClaimOut] = Field(default_factory=list)
    # Overall VeriFact Assessment
    overall_verdict: str | None = None
    overall_label: str | None = None
    overall_explanation: str = ""
    metaqa_summary_text: str = ""
    web_summary_text: str = ""
    combined_risk_score: float | None = None
    web_risk_score: float | None = None
    overall_note: str = ""
