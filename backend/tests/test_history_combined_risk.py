import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.database.models import Run
from app.main import app
from app.metaqa.scoring import Classification
from app.schemas.detect import RunStatus
from app.services.run_service import _to_run_summary, to_detect_response


def test_history_run_summary_exact_008_example() -> None:
    """Verifies that an analysis with MetaQA=0.0 and Web=0.8333 produces Combined Risk 0.08,

    matching the Analysis page, while keeping MetaQA and Web evidence scores separate.
    """
    web_evidence_payload = {
        "status": "completed",
        "consistency_score": 0.8333,
        "total_claims": 3,
        "supported_claims": 2,
        "contradicted_claims": 0,
        "insufficient_claims": 1,
        "claims": [
            {"id": "c1", "text": "Claim 1", "verdict": "SUPPORTED", "sources": []},
            {"id": "c2", "text": "Claim 2", "verdict": "SUPPORTED", "sources": []},
            {"id": "c3", "text": "Claim 3", "verdict": "INSUFFICIENT_EVIDENCE", "sources": []},
        ],
    }

    run = Run(
        id="test-run-008",
        question="What is the effect of planetary rotation?",
        generator_model="Gemma 4:26B",
        base_answer="Rotation decreases day length.",
        hallucination_score=0.0,
        threshold=0.5,
        classification="Reliable",
        status=RunStatus.COMPLETED.value,
        web_evidence_status="completed",
        web_evidence_json=json.dumps(web_evidence_payload),
        created_at=datetime.now(UTC),
    )

    summary = _to_run_summary(run)

    # Combined risk must match the Analysis page calculation: 0.5 * 0.0 + 0.5 * (1.0 - 0.8333) = 0.0833
    assert summary.combined_risk_score is not None
    assert round(summary.combined_risk_score, 2) == 0.08
    assert summary.combined_risk_score == 0.0833

    # Result classification matches Analysis page
    assert summary.overall_verdict == "LIKELY_RELIABLE"
    assert summary.overall_label == "Likely Reliable"

    # MetaQA and Web evidence scores remain separately available and not overwritten
    assert summary.hallucination_score == 0.0
    assert summary.classification == Classification.RELIABLE
    assert summary.web_consistency_score == 0.8333

    # Also verify consistency with to_detect_response (Analysis page payload)
    detect_resp = to_detect_response(run)
    assert detect_resp.verification_summary is not None
    assert detect_resp.verification_summary.combined_risk_score == summary.combined_risk_score
    assert detect_resp.verification_summary.overall_verdict == summary.overall_verdict
    assert detect_resp.verification_summary.overall_label == summary.overall_label


def test_history_older_records_without_combined_risk() -> None:
    """Older records without web evidence or combined risk must safely have

    combined_risk_score=None and not silently invent 0.00.
    """
    run = Run(
        id="legacy-run-no-web",
        question="What is gravity?",
        generator_model="Gemma 4:26B",
        base_answer="Gravity is a force.",
        hallucination_score=0.25,
        threshold=0.5,
        classification="Reliable",
        status=RunStatus.COMPLETED.value,
        web_evidence_status="pending",
        web_evidence_json="",
        created_at=datetime.now(UTC),
    )

    summary = _to_run_summary(run)

    # Must NOT default to 0.00
    assert summary.combined_risk_score is None
    # MetaQA score is preserved accurately
    assert summary.hallucination_score == 0.25
    assert summary.classification == Classification.RELIABLE


def test_history_persisted_combined_risk_used_directly() -> None:
    """When combined_risk_score is already persisted on the Run row, it is returned directly."""
    run = Run(
        id="persisted-run",
        question="What is photosythesis?",
        generator_model="Gemma 4:26B",
        base_answer="Plants make food.",
        hallucination_score=0.1,
        threshold=0.5,
        classification="Reliable",
        status=RunStatus.COMPLETED.value,
        combined_risk_score=0.15,
        overall_verdict="NEEDS_VERIFICATION",
        created_at=datetime.now(UTC),
    )

    summary = _to_run_summary(run)
    assert summary.combined_risk_score == 0.15
    assert summary.overall_verdict == "NEEDS_VERIFICATION"
    assert summary.overall_label == "Needs Verification"


def test_runs_api_endpoint_serialization() -> None:
    """Test that GET /api/runs returns combined_risk_score and overall_verdict."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    web_evidence_payload = {
        "status": "completed",
        "consistency_score": 0.8333,
        "total_claims": 3,
        "supported_claims": 2,
        "contradicted_claims": 0,
        "insufficient_claims": 1,
        "claims": [
            {"id": "c1", "text": "Claim 1", "verdict": "SUPPORTED", "sources": []},
            {"id": "c2", "text": "Claim 2", "verdict": "SUPPORTED", "sources": []},
            {"id": "c3", "text": "Claim 3", "verdict": "INSUFFICIENT_EVIDENCE", "sources": []},
        ],
    }

    db: Session = TestingSessionLocal()
    try:
        run = Run(
            id="api-test-run",
            question="What causes tides?",
            generator_model="Gemma 4:26B",
            base_answer="The gravitational pull of the Moon.",
            hallucination_score=0.0,
            threshold=0.5,
            classification="Reliable",
            status=RunStatus.COMPLETED.value,
            web_evidence_status="completed",
            web_evidence_json=json.dumps(web_evidence_payload),
            created_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()

        from app.api.deps import db_dep
        app.dependency_overrides[db_dep] = lambda: db

        client = TestClient(app)
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        item = next(it for it in data["items"] if it["id"] == "api-test-run")

        assert item["combined_risk_score"] == 0.0833
        assert item["hallucination_score"] == 0.0
        assert item["overall_verdict"] == "LIKELY_RELIABLE"
        assert item["overall_label"] == "Likely Reliable"
        assert item["web_consistency_score"] == 0.8333
    finally:
        app.dependency_overrides.clear()
        db.close()
