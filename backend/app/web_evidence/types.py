from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.web_search.base import WebSource


class EvidenceVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class WebEvidenceStatus(str, Enum):
    PENDING = "pending"
    CLASSIFYING_QUESTION = "classifying_question"
    EXTRACTING_CLAIMS = "extracting_claims"
    SEARCHING_WEB = "searching_web"
    VERIFYING_EVIDENCE = "verifying_evidence"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"

    @classmethod
    def is_terminal(cls, value: str | WebEvidenceStatus) -> bool:
        raw = value.value if isinstance(value, WebEvidenceStatus) else value
        return raw in {
            cls.COMPLETED.value,
            cls.UNAVAILABLE.value,
            cls.FAILED.value,
        }


@dataclass
class ExtractedClaim:
    id: str
    text: str


@dataclass
class VerifiedClaim:
    id: str
    text: str
    search_query: str
    verdict: EvidenceVerdict
    reason: str
    sources: list[WebSource] = field(default_factory=list)
    used_fallback: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "search_query": self.search_query,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "used_fallback": self.used_fallback,
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass
class WebEvidenceResult:
    status: WebEvidenceStatus
    claims: list[VerifiedClaim] = field(default_factory=list)
    error: str | None = None
    searches_used: int = 0
    sources_found: int = 0
    question_type: str | None = None
    question_type_label: str | None = None
    question_type_confidence: float | None = None
    source_strategy_labels: list[str] = field(default_factory=list)
    freshness_required: bool = False
    used_fallback_search: bool = False
    consistency_score: float | None = None
    consistency_verdict: str | None = None
    consistency_verdict_label: str | None = None
    timing_ms: dict[str, float] = field(default_factory=dict)

    @property
    def total_claims(self) -> int:
        return len(self.claims)

    @property
    def supported_claims(self) -> int:
        return sum(1 for item in self.claims if item.verdict is EvidenceVerdict.SUPPORTED)

    @property
    def contradicted_claims(self) -> int:
        return sum(1 for item in self.claims if item.verdict is EvidenceVerdict.CONTRADICTED)

    @property
    def insufficient_claims(self) -> int:
        return sum(
            1 for item in self.claims if item.verdict is EvidenceVerdict.INSUFFICIENT_EVIDENCE
        )

    def finalize_score(self) -> None:
        """Attach consistency score/verdict from claim outcomes (does not touch MetaQA)."""
        from app.web_evidence.scoring import (
            compute_consistency_score,
            consistency_verdict_for,
            consistency_verdict_label,
        )

        score = compute_consistency_score(self.claims)
        verdict = consistency_verdict_for(
            score=score,
            supported=self.supported_claims,
            contradicted=self.contradicted_claims,
            insufficient=self.insufficient_claims,
        )
        self.consistency_score = score
        self.consistency_verdict = verdict.value
        self.consistency_verdict_label = consistency_verdict_label(verdict)

    def to_dict(self) -> dict:
        if self.consistency_verdict is None:
            self.finalize_score()
        return {
            "status": self.status.value,
            "error": self.error,
            "searches_used": self.searches_used,
            "sources_found": self.sources_found,
            "question_type": self.question_type,
            "question_type_label": self.question_type_label,
            "question_type_confidence": self.question_type_confidence,
            "source_strategy_labels": list(self.source_strategy_labels),
            "freshness_required": self.freshness_required,
            "used_fallback_search": self.used_fallback_search,
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "contradicted_claims": self.contradicted_claims,
            "insufficient_claims": self.insufficient_claims,
            "consistency_score": self.consistency_score,
            "consistency_verdict": self.consistency_verdict,
            "consistency_verdict_label": self.consistency_verdict_label,
            "timing": self.timing_ms,
            "claims": [claim.to_dict() for claim in self.claims],
        }
