from __future__ import annotations

from pydantic import BaseModel, Field

from app.web_evidence.types import EvidenceVerdict, WebEvidenceStatus


class WebSourceOut(BaseModel):
    title: str
    url: str
    domain: str
    snippet: str
    published_at: str | None = None
    relevance_score: float | None = None
    source_type: str = "GENERAL"
    question_type: str | None = None
    evidence_summary: str | None = None


class WebClaimOut(BaseModel):
    id: str
    text: str
    search_query: str = ""
    verdict: EvidenceVerdict
    reason: str = ""
    used_fallback: bool = False
    sources: list[WebSourceOut] = Field(default_factory=list)


class WebEvidenceOut(BaseModel):
    status: WebEvidenceStatus
    error: str | None = None
    searches_used: int = 0
    sources_found: int = 0
    question_type: str | None = None
    question_type_label: str | None = None
    question_type_confidence: float | None = None
    source_strategy_labels: list[str] = Field(default_factory=list)
    freshness_required: bool = False
    used_fallback_search: bool = False
    total_claims: int = 0
    supported_claims: int = 0
    contradicted_claims: int = 0
    insufficient_claims: int = 0
    consistency_score: float | None = None
    consistency_verdict: str | None = None
    consistency_verdict_label: str | None = None
    claims: list[WebClaimOut] = Field(default_factory=list)
