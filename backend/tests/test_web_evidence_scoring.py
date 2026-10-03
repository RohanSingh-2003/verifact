"""Tests for Web Evidence Consistency Score (independent of MetaQA)."""

from __future__ import annotations

from app.web_evidence.scoring import (
    WebConsistencyVerdict,
    compute_consistency_score,
    consistency_verdict_for,
    score_explanation,
)
from app.web_evidence.types import EvidenceVerdict, VerifiedClaim


def _claim(verdict: EvidenceVerdict) -> VerifiedClaim:
    return VerifiedClaim(
        id="c1",
        text="Sample claim.",
        search_query="sample",
        verdict=verdict,
        reason="test",
    )


def test_consistency_score_all_supported() -> None:
    claims = [_claim(EvidenceVerdict.SUPPORTED) for _ in range(4)]
    assert compute_consistency_score(claims) == 1.0
    assert (
        consistency_verdict_for(score=1.0, supported=4, contradicted=0, insufficient=0)
        is WebConsistencyVerdict.STRONGLY_SUPPORTED
    )


def test_consistency_score_partial_support_not_hallucination() -> None:
    claims = [
        _claim(EvidenceVerdict.SUPPORTED),
        _claim(EvidenceVerdict.INSUFFICIENT_EVIDENCE),
        _claim(EvidenceVerdict.INSUFFICIENT_EVIDENCE),
    ]
    # (1 + 0.5 + 0.5) / 3 = 0.6667
    assert compute_consistency_score(claims) == 0.6667
    assert (
        consistency_verdict_for(score=0.6667, supported=1, contradicted=0, insufficient=2)
        is WebConsistencyVerdict.PARTIALLY_SUPPORTED
    )
    label = consistency_verdict_for(score=0.6667, supported=1, contradicted=0, insufficient=2)
    from app.web_evidence.scoring import consistency_verdict_label

    text = consistency_verdict_label(label).casefold()
    assert "partially supported" in text
    assert "hallucin" not in text
    assert "unreliable" not in text


def test_consistency_score_mixed() -> None:
    claims = [
        _claim(EvidenceVerdict.SUPPORTED),
        _claim(EvidenceVerdict.SUPPORTED),
        _claim(EvidenceVerdict.CONTRADICTED),
        _claim(EvidenceVerdict.INSUFFICIENT_EVIDENCE),
    ]
    # (1 + 1 + 0 + 0.5) / 4 = 0.625
    assert compute_consistency_score(claims) == 0.625
    assert (
        consistency_verdict_for(score=0.625, supported=2, contradicted=1, insufficient=1)
        is WebConsistencyVerdict.MIXED
    )


def test_consistency_score_all_contradicted() -> None:
    claims = [_claim(EvidenceVerdict.CONTRADICTED), _claim(EvidenceVerdict.CONTRADICTED)]
    assert compute_consistency_score(claims) == 0.0
    assert (
        consistency_verdict_for(score=0.0, supported=0, contradicted=2, insufficient=0)
        is WebConsistencyVerdict.CONTRADICTIONS_FOUND
    )


def test_consistency_score_insufficient_only() -> None:
    claims = [_claim(EvidenceVerdict.INSUFFICIENT_EVIDENCE) for _ in range(3)]
    assert compute_consistency_score(claims) == 0.5
    assert (
        consistency_verdict_for(score=0.5, supported=0, contradicted=0, insufficient=3)
        is WebConsistencyVerdict.INSUFFICIENT
    )


def test_consistency_score_empty() -> None:
    assert compute_consistency_score([]) is None
    assert (
        consistency_verdict_for(score=None, supported=0, contradicted=0, insufficient=0)
        is WebConsistencyVerdict.NO_CLAIMS
    )


def test_score_explanation_not_probability() -> None:
    text = score_explanation().casefold()
    assert "not a probability" in text or "not a calibrated" in text
    assert "metaqa" in text
