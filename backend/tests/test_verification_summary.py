"""Tests for deterministic MetaQA ↔ Web Evidence verification summary."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_llm_client
from app.llm.mock import MockLLMClient
from app.main import app
from app.metaqa.scoring import Classification
from app.schemas.detect import RunStatus
from app.schemas.web_evidence import WebClaimOut, WebEvidenceOut
from app.services.verification_summary import (
    MetaqaSignal,
    SignalRelationship,
    WebSignal,
    build_verification_summary,
    metaqa_signal_from_run,
    relationship_for,
    web_signal_from_evidence,
)
from app.web_evidence.types import EvidenceVerdict, WebEvidenceStatus


def _web(
    *,
    status: WebEvidenceStatus = WebEvidenceStatus.COMPLETED,
    supported: int = 0,
    contradicted: int = 0,
    insufficient: int = 0,
    claims: list[WebClaimOut] | None = None,
) -> WebEvidenceOut:
    return WebEvidenceOut(
        status=status,
        total_claims=supported + contradicted + insufficient,
        supported_claims=supported,
        contradicted_claims=contradicted,
        insufficient_claims=insufficient,
        claims=claims or [],
    )


def test_metaqa_consistent_web_supported_agree() -> None:
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.2,
        threshold=0.5,
        web_evidence=_web(supported=3),
    )
    assert summary["metaqa_signal"] == MetaqaSignal.CONSISTENT.value
    assert summary["web_signal"] == WebSignal.SUPPORTED.value
    assert summary["relationship"] == SignalRelationship.AGREE.value
    assert summary["ready"] is True
    assert summary["overall_verdict"] == "LIKELY_RELIABLE"
    assert "probability" not in summary["relationship_label"].casefold()


def test_metaqa_consistent_web_contradicted_disagree() -> None:
    claim = WebClaimOut(
        id="claim_1",
        text="Mumbai is the capital of India.",
        verdict=EvidenceVerdict.CONTRADICTED,
        reason="Sources state New Delhi is the capital.",
    )
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.1,
        threshold=0.5,
        web_evidence=_web(supported=1, contradicted=1, claims=[claim]),
    )
    assert summary["relationship"] == SignalRelationship.DISAGREE.value
    assert len(summary["attention_claims"]) >= 1
    assert summary["attention_claims"][0]["verdict"] == EvidenceVerdict.CONTRADICTED.value


def test_metaqa_inconsistent_web_supported_disagree() -> None:
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.HALLUCINATED,
        score=0.8,
        threshold=0.5,
        web_evidence=_web(supported=2),
    )
    assert summary["relationship"] == SignalRelationship.DISAGREE.value


def test_metaqa_inconsistent_web_contradicted_both_concerning() -> None:
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.HALLUCINATED,
        score=0.9,
        threshold=0.5,
        web_evidence=_web(contradicted=2),
    )
    assert summary["relationship"] == SignalRelationship.BOTH_CONCERNING.value


def test_web_insufficient_never_treated_as_hallucination() -> None:
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.1,
        threshold=0.5,
        web_evidence=_web(insufficient=3),
    )
    assert summary["web_signal"] == WebSignal.INSUFFICIENT.value
    assert summary["relationship"] == SignalRelationship.WEB_INSUFFICIENT.value
    assert "not treated as hallucination" in summary["web_interpretation"].casefold()


def test_missing_web_evidence_pending_or_unavailable() -> None:
    pending = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.2,
        threshold=0.5,
        web_evidence=None,
    )
    assert pending["web_signal"] == WebSignal.PENDING.value
    assert pending["relationship"] == SignalRelationship.PENDING.value
    assert pending["ready"] is False

    missing = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.2,
        threshold=0.5,
        web_evidence=_web(status=WebEvidenceStatus.UNAVAILABLE),
    )
    assert missing["relationship"] == SignalRelationship.WEB_UNAVAILABLE.value


def test_metaqa_failure_web_succeeds() -> None:
    summary = build_verification_summary(
        status=RunStatus.MUTATION_GENERATION_FAILED,
        classification=None,
        score=None,
        threshold=0.5,
        web_evidence=_web(supported=2),
    )
    assert summary["metaqa_signal"] == MetaqaSignal.UNAVAILABLE.value
    assert summary["web_signal"] == WebSignal.SUPPORTED.value
    assert summary["relationship"] == SignalRelationship.METAQA_UNAVAILABLE.value
    assert summary["ready"] is True


def test_web_failure_metaqa_succeeds() -> None:
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.15,
        threshold=0.5,
        web_evidence=_web(status=WebEvidenceStatus.FAILED),
    )
    assert summary["relationship"] == SignalRelationship.WEB_UNAVAILABLE.value


def test_signal_helpers() -> None:
    assert metaqa_signal_from_run(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.2,
    ) is MetaqaSignal.CONSISTENT
    assert web_signal_from_evidence(_web(contradicted=1)) is WebSignal.CONTRADICTED
    assert (
        relationship_for(MetaqaSignal.CONSISTENT, WebSignal.SUPPORTED)
        is SignalRelationship.AGREE
    )


def test_detect_response_includes_verification_summary_not_combined_score() -> None:
    fake = MockLLMClient(scenario="reliable")
    app.dependency_overrides[get_llm_client] = lambda: fake
    client = TestClient(app)
    try:
        response = client.post("/api/detect", json={"question": "What is the capital of Australia?"})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        detail = client.get(f"/api/runs/{run_id}").json()
        assert "verification_summary" in detail
        summary = detail["verification_summary"]
        assert summary is not None
        assert "relationship" in summary
        assert "metaqa_signal" in summary
        assert "web_signal" in summary
        assert "combined_score" not in detail
        assert "hallucination_probability" not in detail
        assert "combined_score" not in summary
        # Top-level fused web_evidence_score must not exist; consistency lives under web_evidence.
        assert "web_evidence_score" not in detail
        if detail["web_evidence"]["status"] == "completed":
            assert "consistency_score" in detail["web_evidence"]
        # Answer + independent signals remain visible independently.
        assert detail["base_answer"]["text"]
        assert detail["hallucination_score"] is not None or detail["status"] != "completed"
        assert detail["web_evidence"] is not None
    finally:
        app.dependency_overrides.clear()


def test_overall_scenario_1_metaqa_zero_web_perfect() -> None:
    # 1. MetaQA = 0, Web Evidence = 1.0 -> Likely Reliable
    web = _web(supported=3)
    web.consistency_score = 1.0
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.0,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "LIKELY_RELIABLE"
    assert summary["overall_label"] == "Likely Reliable"
    assert summary["combined_risk_score"] == 0.0
    assert "No consistency violations" in summary["metaqa_summary_text"]


def test_overall_scenario_2_metaqa_high_web_contradicted() -> None:
    # 2. MetaQA high, Web Evidence contradictory -> Potentially Hallucinated
    web = _web(contradicted=2)
    web.consistency_score = 0.0
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.HALLUCINATED,
        score=0.9,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "POTENTIALLY_HALLUCINATED"
    assert summary["overall_label"] == "Potentially Hallucinated"
    assert summary["combined_risk_score"] == 0.95
    assert "Both consistency checking and external evidence" in summary["overall_explanation"]


def test_overall_scenario_3_metaqa_low_web_insufficient() -> None:
    # 3. MetaQA low, Web Evidence insufficient -> Needs Verification
    web = _web(insufficient=3)
    web.consistency_score = 0.5
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.1,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "NEEDS_VERIFICATION"
    assert summary["overall_label"] == "Needs Verification"
    assert "insufficient" in summary["overall_explanation"]


def test_overall_scenario_4_metaqa_high_web_supported() -> None:
    # 4. MetaQA high, Web Evidence supported -> Needs Verification
    web = _web(supported=3)
    web.consistency_score = 1.0
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.HALLUCINATED,
        score=0.8,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "NEEDS_VERIFICATION"
    assert summary["overall_label"] == "Needs Verification"
    assert "supports the checked claims, but MetaQA detected consistency violations" in summary["overall_explanation"]


def test_overall_scenario_5_web_contradicted_metaqa_low() -> None:
    # 5. Web Evidence contains at least one contradiction -> Potentially Hallucinated even if MetaQA reliable
    web = _web(supported=2, contradicted=1)
    web.consistency_score = 0.6667
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.05,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "POTENTIALLY_HALLUCINATED"
    assert summary["overall_label"] == "Potentially Hallucinated"
    assert "contradicts one or more claims" in summary["overall_explanation"]


def test_overall_scenario_6_web_evidence_unavailable() -> None:
    # 6. Web Evidence unavailable -> do not invent score, indicate only MetaQA available
    web = _web(status=WebEvidenceStatus.UNAVAILABLE)
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.1,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "LIKELY_RELIABLE"
    assert summary["combined_risk_score"] is None
    assert "External web evidence was unavailable" in summary["overall_explanation"]


def test_overall_scenario_7_metaqa_unavailable() -> None:
    # 7. MetaQA unavailable -> do not invent score, indicate only Web Evidence available
    web = _web(supported=3)
    web.consistency_score = 1.0
    summary = build_verification_summary(
        status=RunStatus.FAILED,
        classification=None,
        score=None,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "LIKELY_RELIABLE"
    assert summary["combined_risk_score"] is None
    assert "MetaQA consistency checking was unavailable" in summary["overall_explanation"]


def test_overall_scenario_8_both_unavailable() -> None:
    # 8. Both unavailable -> overall assessment cannot be determined
    web = _web(status=WebEvidenceStatus.FAILED)
    summary = build_verification_summary(
        status=RunStatus.FAILED,
        classification=None,
        score=None,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "UNAVAILABLE"
    assert summary["combined_risk_score"] is None
    assert "cannot be determined" in summary["overall_explanation"]


def test_overall_user_example_7() -> None:
    # Example 7: MetaQA 0.00, Web Evidence Consistency 0.83 -> Combined Risk 0.085 (rounded 0.09)
    web = _web(supported=2, insufficient=1)
    web.consistency_score = 0.83
    summary = build_verification_summary(
        status=RunStatus.COMPLETED,
        classification=Classification.RELIABLE,
        score=0.00,
        threshold=0.5,
        web_evidence=web,
    )
    assert summary["overall_verdict"] == "LIKELY_RELIABLE"
    assert summary["web_risk_score"] == 0.17
    assert summary["combined_risk_score"] == 0.085
    assert "MetaQA detected no consistency violations, while web evidence supported most checked claims." in summary["overall_explanation"]

