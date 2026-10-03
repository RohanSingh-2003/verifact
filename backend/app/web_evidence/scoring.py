"""Web Evidence Consistency Score — claim-level, not a hallucination probability.

Formula (deterministic):
    For each verified claim assign a contribution:
        SUPPORTED              → 1.0
        INSUFFICIENT_EVIDENCE  → 0.5
        CONTRADICTED           → 0.0

    consistency_score = mean(contributions) ∈ [0.0, 1.0]

    If there are no claims, consistency_score is None.

Interpretation:
    Higher values mean a larger share of checked claims were supported by
    retrieved evidence. This is NOT a calibrated P(hallucination) and must
    never be averaged with the MetaQA score.
"""

from __future__ import annotations

from enum import Enum

from app.web_evidence.types import EvidenceVerdict, VerifiedClaim


class WebConsistencyVerdict(str, Enum):
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    MOSTLY_SUPPORTED = "MOSTLY_SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    MIXED = "MIXED"
    CONTRADICTIONS_FOUND = "CONTRADICTIONS_FOUND"
    INSUFFICIENT = "INSUFFICIENT"
    NO_CLAIMS = "NO_CLAIMS"


_CONTRIBUTION = {
    EvidenceVerdict.SUPPORTED: 1.0,
    EvidenceVerdict.INSUFFICIENT_EVIDENCE: 0.5,
    EvidenceVerdict.CONTRADICTED: 0.0,
}

_VERDICT_LABELS = {
    WebConsistencyVerdict.STRONGLY_SUPPORTED: "Strongly supported by evidence",
    WebConsistencyVerdict.MOSTLY_SUPPORTED: "Mostly supported by evidence",
    WebConsistencyVerdict.PARTIALLY_SUPPORTED: "Partially supported by evidence",
    WebConsistencyVerdict.MIXED: "Mixed — some claims contradicted",
    WebConsistencyVerdict.CONTRADICTIONS_FOUND: "Potential factual contradiction detected",
    WebConsistencyVerdict.INSUFFICIENT: "Not enough external evidence to fully verify",
    WebConsistencyVerdict.NO_CLAIMS: "No claims to score",
}


def claim_contribution(verdict: EvidenceVerdict) -> float:
    return _CONTRIBUTION.get(verdict, 0.5)


def compute_consistency_score(claims: list[VerifiedClaim]) -> float | None:
    """Mean claim contribution in [0, 1], or None when there are no claims."""
    if not claims:
        return None
    total = sum(claim_contribution(claim.verdict) for claim in claims)
    return round(total / len(claims), 4)


def consistency_verdict_for(
    *,
    score: float | None,
    supported: int,
    contradicted: int,
    insufficient: int,
) -> WebConsistencyVerdict:
    if score is None and supported + contradicted + insufficient == 0:
        return WebConsistencyVerdict.NO_CLAIMS
    if contradicted > 0 and supported > 0:
        return WebConsistencyVerdict.MIXED
    if contradicted > 0:
        return WebConsistencyVerdict.CONTRADICTIONS_FOUND
    if supported == 0:
        return WebConsistencyVerdict.INSUFFICIENT
    # Supported present, zero contradictions.
    if insufficient > 0:
        return WebConsistencyVerdict.PARTIALLY_SUPPORTED
    if score is not None and score >= 0.85:
        return WebConsistencyVerdict.STRONGLY_SUPPORTED
    return WebConsistencyVerdict.MOSTLY_SUPPORTED


def consistency_verdict_label(value: str | WebConsistencyVerdict) -> str:
    raw = value.value if isinstance(value, WebConsistencyVerdict) else str(value or "")
    try:
        return _VERDICT_LABELS[WebConsistencyVerdict(raw)]
    except ValueError:
        return raw or "Unknown"


def score_explanation() -> str:
    return (
        "Web Evidence Consistency Score = mean claim contribution "
        "(SUPPORTED=1.0, INSUFFICIENT_EVIDENCE=0.5, CONTRADICTED=0.0). "
        "Insufficient evidence is not hallucination. Contradiction is the primary "
        "negative signal. This score is not a probability that the answer is "
        "hallucinated, and is not combined with MetaQA."
    )
