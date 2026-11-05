"""Tests for reviewer blinding, submission isolation, and adjudication safeguards.

Verifies the security properties of the blinded annotation API:
1. Reviewer 1 cannot access Reviewer 2's annotation.
2. Reviewer 2 cannot access Reviewer 1's annotation.
3. Reviewer responses never expose Gemini predictions.
4. Reviewer responses never expose VeriFact internal scores.
5. Reviewer 1 cannot submit or modify Reviewer 2's fields.
6. Reviewer 2 cannot submit or modify Reviewer 1's fields.
7. Unauthenticated requests are rejected.
8. Submitted annotations cannot silently overwrite one another.
9. Adjudication requires both independent reviews.
10. A reviewer cannot adjudicate their own disagreement.
11. Existing formal ground-truth safeguards remain intact.
12. Existing public APIs remain unaffected.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base
from app.database.models import HumanAnnotation

# Test tokens — used only in tests, never in production
TEST_REVIEWER1_TOKEN = "test-reviewer1-secret-token-abc123"
TEST_REVIEWER2_TOKEN = "test-reviewer2-secret-token-def456"
TEST_ADJUDICATOR_TOKEN = "test-adjudicator-secret-token-ghi789"

# Headers for authenticated requests
R1_HEADERS = {"Authorization": f"Bearer {TEST_REVIEWER1_TOKEN}"}
R2_HEADERS = {"Authorization": f"Bearer {TEST_REVIEWER2_TOKEN}"}
ADJ_HEADERS = {"Authorization": f"Bearer {TEST_ADJUDICATOR_TOKEN}"}


@pytest.fixture(autouse=True)
def _patch_reviewer_tokens(monkeypatch):
    """Configure reviewer tokens for all tests."""
    monkeypatch.setenv("REVIEWER1_TOKEN", TEST_REVIEWER1_TOKEN)
    monkeypatch.setenv("REVIEWER2_TOKEN", TEST_REVIEWER2_TOKEN)
    monkeypatch.setenv("ADJUDICATOR_TOKEN", TEST_ADJUDICATOR_TOKEN)


@pytest.fixture()
def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """Create a test client with the in-memory database."""
    from app.api.deps import db_dep
    from app.config import get_settings
    from app.main import create_app

    # Clear cached settings to pick up test env vars
    get_settings.cache_clear()

    app = create_app()

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[db_dep] = override_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def seeded_annotation(db_session) -> str:
    """Seed a single HumanAnnotation record and return its ID."""
    annot = HumanAnnotation(
        evaluation_result_id="eval-res-001",
        evaluation_run_id="eval-run-001",
        question_id="tqa_0001",
        question="How long do diamonds last?",
        generated_answer="Diamonds last forever.",
        reference_answer="Diamonds last between 1 and 4 billion years.",
        judge_label="HALLUCINATED",
        judge_reasoning="The claim 'diamonds last forever' contradicts scientific evidence.",
        judge_confidence=0.95,
        validation_status="pending",
    )
    db_session.add(annot)
    db_session.commit()
    db_session.refresh(annot)
    return annot.id


@pytest.fixture()
def both_reviewed_annotation(db_session) -> str:
    """Seed an annotation with both reviewers submitted and disagreeing."""
    annot = HumanAnnotation(
        evaluation_result_id="eval-res-002",
        evaluation_run_id="eval-run-001",
        question_id="tqa_0002",
        question="What shape is the Earth?",
        generated_answer="The Earth is flat.",
        reference_answer="The Earth is an oblate spheroid.",
        judge_label="HALLUCINATED",
        judge_reasoning="Contradicts scientific consensus.",
        judge_confidence=0.99,
        reviewer1_id="reviewer1",
        reviewer1_label="HALLUCINATED",
        reviewer1_notes="Clearly wrong factual claim.",
        reviewer2_id="reviewer2",
        reviewer2_label="RELIABLE",
        reviewer2_notes="Could be interpreted as colloquial.",
        disagreement=True,
        validation_status="reviewed",
    )
    db_session.add(annot)
    db_session.commit()
    db_session.refresh(annot)
    return annot.id


# ─── Test 7: Unauthenticated Requests Are Rejected ───────────────────────────


class TestUnauthenticatedAccess:
    def test_list_tasks_no_auth(self, client):
        resp = client.get("/api/review/tasks")
        assert resp.status_code == 401

    def test_get_task_no_auth(self, client, seeded_annotation):
        resp = client.get(f"/api/review/tasks/{seeded_annotation}")
        assert resp.status_code == 401

    def test_submit_no_auth(self, client, seeded_annotation):
        resp = client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            json={"label": "RELIABLE", "notes": "test"},
        )
        assert resp.status_code == 401

    def test_stats_no_auth(self, client):
        resp = client.get("/api/review/stats")
        assert resp.status_code == 401

    def test_adjudicate_list_no_auth(self, client):
        resp = client.get("/api/review/adjudicate")
        assert resp.status_code == 401

    def test_adjudicate_submit_no_auth(self, client, both_reviewed_annotation):
        resp = client.post(
            f"/api/review/adjudicate/{both_reviewed_annotation}",
            json={"label": "HALLUCINATED", "notes": "adjudication"},
        )
        assert resp.status_code == 401

    def test_invalid_token(self, client):
        resp = client.get("/api/review/tasks", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401

    def test_malformed_auth_header(self, client):
        resp = client.get("/api/review/tasks", headers={"Authorization": "Basic abc123"})
        assert resp.status_code == 401


# ─── Tests 1-2: Reviewer Blinding ────────────────────────────────────────────


class TestReviewerBlinding:
    def test_reviewer1_cannot_see_reviewer2_label(self, client, both_reviewed_annotation):
        """Test 1: Reviewer 1 cannot access Reviewer 2's annotation."""
        resp = client.get(
            f"/api/review/tasks/{both_reviewed_annotation}",
            headers=R1_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["my_label"] == "HALLUCINATED"  # reviewer1's own label
        assert "reviewer2_label" not in data
        assert "reviewer2_notes" not in data

    def test_reviewer2_cannot_see_reviewer1_label(self, client, both_reviewed_annotation):
        """Test 2: Reviewer 2 cannot access Reviewer 1's annotation."""
        resp = client.get(
            f"/api/review/tasks/{both_reviewed_annotation}",
            headers=R2_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["my_label"] == "RELIABLE"  # reviewer2's own label
        assert "reviewer1_label" not in data
        assert "reviewer1_notes" not in data

    def test_reviewer1_list_does_not_leak_reviewer2(self, client, both_reviewed_annotation):
        resp = client.get("/api/review/tasks", headers=R1_HEADERS)
        assert resp.status_code == 200
        for task in resp.json():
            assert "reviewer2_label" not in task
            assert "reviewer2_notes" not in task
            assert "reviewer1_label" not in task  # Field is named my_label instead

    def test_reviewer2_list_does_not_leak_reviewer1(self, client, both_reviewed_annotation):
        resp = client.get("/api/review/tasks", headers=R2_HEADERS)
        assert resp.status_code == 200
        for task in resp.json():
            assert "reviewer1_label" not in task
            assert "reviewer1_notes" not in task


# ─── Tests 3-4: No Exposure of Judge Predictions or Internal Scores ──────────


class TestNoInternalScoreExposure:
    def test_reviewer_response_has_no_judge_label(self, client, seeded_annotation):
        """Test 3: Reviewer responses never expose Gemini predictions."""
        resp = client.get(
            f"/api/review/tasks/{seeded_annotation}",
            headers=R1_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "judge_label" not in data
        assert "judge_reasoning" not in data
        assert "judge_confidence" not in data

    def test_reviewer_response_has_no_verifact_scores(self, client, seeded_annotation):
        """Test 4: Reviewer responses never expose VeriFact internal scores."""
        resp = client.get(
            f"/api/review/tasks/{seeded_annotation}",
            headers=R1_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        for forbidden_field in [
            "metaqa_score",
            "web_evidence_score",
            "combined_risk_score",
            "hallucination_score",
            "predicted_label",
            "classification",
            "multi_model_consensus",
            "web_evidence_verdict",
        ]:
            assert forbidden_field not in data, f"Forbidden field '{forbidden_field}' leaked"

    def test_task_list_has_no_scores(self, client, seeded_annotation):
        resp = client.get("/api/review/tasks", headers=R2_HEADERS)
        assert resp.status_code == 200
        for task in resp.json():
            assert "judge_label" not in task
            assert "metaqa_score" not in task
            assert "combined_risk_score" not in task


# ─── Tests 5-6: Submission Isolation ─────────────────────────────────────────


class TestSubmissionIsolation:
    def test_reviewer1_submits_only_reviewer1_fields(self, client, seeded_annotation, db_session):
        """Test 5: Reviewer 1 can only write reviewer1 fields."""
        resp = client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "HALLUCINATED", "notes": "Clearly wrong."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["my_label"] == "HALLUCINATED"
        assert data["my_notes"] == "Clearly wrong."

        # Verify in database that reviewer2 fields are untouched
        row = db_session.get(HumanAnnotation, seeded_annotation)
        db_session.refresh(row)
        assert row.reviewer1_label == "HALLUCINATED"
        assert row.reviewer1_notes == "Clearly wrong."
        assert row.reviewer2_label is None
        assert row.reviewer2_notes is None

    def test_reviewer2_submits_only_reviewer2_fields(self, client, seeded_annotation, db_session):
        """Test 6: Reviewer 2 can only write reviewer2 fields."""
        resp = client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R2_HEADERS,
            json={"label": "RELIABLE", "notes": "Seems fine."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["my_label"] == "RELIABLE"

        row = db_session.get(HumanAnnotation, seeded_annotation)
        db_session.refresh(row)
        assert row.reviewer2_label == "RELIABLE"
        assert row.reviewer2_notes == "Seems fine."
        assert row.reviewer1_label is None
        assert row.reviewer1_notes is None

    def test_reviewer1_cannot_overwrite_reviewer2(self, client, both_reviewed_annotation, db_session):
        """Reviewer 1's submission cannot affect reviewer 2's stored fields."""
        resp = client.post(
            f"/api/review/tasks/{both_reviewed_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "RELIABLE", "notes": "Changed my mind."},
        )
        assert resp.status_code == 200

        row = db_session.get(HumanAnnotation, both_reviewed_annotation)
        db_session.refresh(row)
        assert row.reviewer1_label == "RELIABLE"  # updated
        assert row.reviewer2_label == "RELIABLE"  # preserved from fixture
        assert row.reviewer2_notes == "Could be interpreted as colloquial."  # preserved


# ─── Test 8: No Silent Overwrites ────────────────────────────────────────────


class TestNoSilentOverwrite:
    def test_correction_creates_audit_trail(self, client, seeded_annotation, db_session):
        """Test 8: When a reviewer changes their label, the previous label is audited."""
        # First submission
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "RELIABLE", "notes": "Initial assessment."},
        )

        # Second submission (correction)
        resp = client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "HALLUCINATED", "notes": "Revised after re-reading."},
        )
        assert resp.status_code == 200

        row = db_session.get(HumanAnnotation, seeded_annotation)
        db_session.refresh(row)
        assert row.reviewer1_label == "HALLUCINATED"
        assert "[CORRECTION" in row.reviewer1_notes
        assert "RELIABLE" in row.reviewer1_notes  # original label preserved in audit trail

    def test_concurrent_reviewer_submissions_are_independent(self, client, seeded_annotation, db_session):
        """Both reviewers can submit independently without interfering."""
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "HALLUCINATED", "notes": "R1 assessment."},
        )
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R2_HEADERS,
            json={"label": "RELIABLE", "notes": "R2 assessment."},
        )

        row = db_session.get(HumanAnnotation, seeded_annotation)
        db_session.refresh(row)
        assert row.reviewer1_label == "HALLUCINATED"
        assert row.reviewer1_notes == "R1 assessment."
        assert row.reviewer2_label == "RELIABLE"
        assert row.reviewer2_notes == "R2 assessment."
        assert row.disagreement is True
        assert row.validation_status == "reviewed"


# ─── Tests 9-10: Adjudication Safeguards ─────────────────────────────────────


class TestAdjudicationSafeguards:
    def test_adjudication_requires_both_reviews(self, client, seeded_annotation):
        """Test 9: Adjudication requires both independent reviews."""
        resp = client.post(
            f"/api/review/adjudicate/{seeded_annotation}",
            headers=ADJ_HEADERS,
            json={"label": "HALLUCINATED", "notes": "test"},
        )
        assert resp.status_code == 409
        assert "Both reviewers must submit" in resp.json()["detail"]

    def test_reviewer_cannot_adjudicate(self, client, both_reviewed_annotation):
        """Test 10: A reviewer cannot adjudicate their own disagreement."""
        resp = client.post(
            f"/api/review/adjudicate/{both_reviewed_annotation}",
            headers=R1_HEADERS,
            json={"label": "HALLUCINATED", "notes": "self-adjudication"},
        )
        assert resp.status_code == 403

        resp2 = client.post(
            f"/api/review/adjudicate/{both_reviewed_annotation}",
            headers=R2_HEADERS,
            json={"label": "HALLUCINATED", "notes": "self-adjudication"},
        )
        assert resp2.status_code == 403

    def test_adjudicator_can_resolve_disagreement(self, client, both_reviewed_annotation, db_session):
        resp = client.post(
            f"/api/review/adjudicate/{both_reviewed_annotation}",
            headers=ADJ_HEADERS,
            json={"label": "HALLUCINATED", "notes": "Factually incorrect claim.", "evidence": "Scientific consensus."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjudicated_label"] == "HALLUCINATED"
        assert data["validation_status"] == "adjudicated"

        # Verify original reviewer labels are preserved
        row = db_session.get(HumanAnnotation, both_reviewed_annotation)
        db_session.refresh(row)
        assert row.reviewer1_label == "HALLUCINATED"
        assert row.reviewer2_label == "RELIABLE"
        assert row.adjudicated_label == "HALLUCINATED"
        assert row.adjudicator_id == "adjudicator"

    def test_adjudicator_cannot_access_reviewer_endpoints(self, client):
        resp = client.get("/api/review/tasks", headers=ADJ_HEADERS)
        assert resp.status_code == 403

        resp = client.get("/api/review/stats", headers=ADJ_HEADERS)
        assert resp.status_code == 403


# ─── Test 11: Ground-Truth Safeguards Remain Intact ──────────────────────────


class TestGroundTruthSafeguards:
    def test_formal_mode_unvalidated_label_returns_none(self):
        """Test 11: Existing formal ground-truth safeguards remain intact."""
        from app.evaluation.ground_truth import resolve_ground_truth
        from app.evaluation.schemas import DatasetExample, GroundTruthSource

        example = DatasetExample(
            id="test_gt",
            question="What is the capital of France?",
            reference_answer="Paris",
            ground_truth_label=None,
            ground_truth_source=GroundTruthSource.UNVALIDATED,
        )
        decision = resolve_ground_truth("Paris", example, mode="formal")
        assert decision.label is None
        assert decision.source == GroundTruthSource.UNVALIDATED

    def test_adjudicated_label_takes_precedence(self):
        from app.evaluation.ground_truth import resolve_ground_truth
        from app.evaluation.schemas import DatasetExample, GroundTruthSource
        from app.metaqa.scoring import Classification

        example = DatasetExample(
            id="test_adj",
            question="Is the Earth flat?",
            reference_answer="No, the Earth is an oblate spheroid.",
        )
        decision = resolve_ground_truth(
            "The Earth is flat.",
            example,
            mode="formal",
            adjudicated_label=Classification.HALLUCINATED,
        )
        assert decision.label == Classification.HALLUCINATED
        assert decision.source == GroundTruthSource.ADJUDICATED


# ─── Test 12: Public APIs Remain Unaffected ──────────────────────────────────


class TestPublicAPIsUnaffected:
    def test_health_endpoint_works_without_auth(self, client):
        """Test 12: Public endpoints remain accessible without auth."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_settings_endpoint_works_without_auth(self, client):
        resp = client.get("/api/settings")
        assert resp.status_code == 200

    def test_existing_annotations_endpoint_blocks_reviewers(self, client):
        """The unrestricted /api/annotations endpoint rejects reviewer identities and unauthenticated requests."""
        # Unauthenticated rejected
        resp_anon = client.get("/api/annotations")
        assert resp_anon.status_code == 401

        # Reviewer 1 rejected with 403
        resp_r1 = client.get("/api/annotations", headers=R1_HEADERS)
        assert resp_r1.status_code == 403
        assert "Reviewer identities cannot access unrestricted" in resp_r1.json()["detail"]

        # Reviewer 2 rejected with 403
        resp_r2 = client.get("/api/annotations", headers=R2_HEADERS)
        assert resp_r2.status_code == 403

        # Adjudicator permitted
        resp_adj = client.get("/api/annotations", headers=ADJ_HEADERS)
        assert resp_adj.status_code == 200

    def test_evaluations_list_endpoint_works(self, client):
        resp = client.get("/api/evaluations")
        assert resp.status_code == 200


# ─── Additional Edge Cases ───────────────────────────────────────────────────


class TestEdgeCases:
    def test_pending_only_filter(self, client, seeded_annotation):
        # Not yet submitted → appears in pending
        resp = client.get("/api/review/tasks?pending_only=true", headers=R1_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_stats_show_progress(self, client, seeded_annotation):
        resp = client.get("/api/review/stats", headers=R1_HEADERS)
        data = resp.json()
        assert data["total_assigned"] >= 1
        assert data["my_completed"] == 0
        assert data["my_remaining"] >= 1

        # Submit and check again
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "RELIABLE"},
        )
        resp2 = client.get("/api/review/stats", headers=R1_HEADERS)
        data2 = resp2.json()
        assert data2["my_completed"] == 1
        assert data2["my_remaining"] == data["my_remaining"] - 1

    def test_adjudicator_list_only_disagreements(self, client, both_reviewed_annotation, seeded_annotation):
        resp = client.get("/api/review/adjudicate", headers=ADJ_HEADERS)
        assert resp.status_code == 200
        tasks = resp.json()
        # Only the disagreement should appear (not the un-reviewed one)
        assert all(t["reviewer1_label"] is not None and t["reviewer2_label"] is not None for t in tasks)

    def test_not_found_annotation(self, client):
        resp = client.get("/api/review/tasks/nonexistent-id", headers=R1_HEADERS)
        assert resp.status_code == 404

    def test_empty_bearer_token(self, client):
        resp = client.get("/api/review/tasks", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401



# ─── Evaluation Blinding & Export Fixtures ─────────────────────────────────────


@pytest.fixture()
def seeded_evaluation(db_session) -> str:
    """Seed an EvaluationRun with a Metric and an EvaluationResult."""
    from app.database.models import EvaluationMetric, EvaluationResult, EvaluationRun

    run = EvaluationRun(
        id="eval-test-001",
        name="Blinding Test Eval",
        dataset_name="hallucination_benchmark_frozen",
        dataset_version="1.0",
        generator_model="gemma",
        verifier_model="gemma",
        threshold=0.5,
        total_examples=1,
        completed_examples=1,
        status="completed",
        config_json='{"best_threshold_by_f1": 0.5}',
        category_metrics_json='[{"category": "general", "count": 1, "accuracy": 1.0, "mean_hallucination_score": 0.1, "fp": 0, "fn": 0}]',
        summary_metrics_json="{}",
    )
    metric = EvaluationMetric(
        evaluation_run_id=run.id,
        threshold=0.5,
        accuracy=1.0,
        precision=1.0,
        recall=1.0,
        f1=1.0,
        tp=1,
        tn=0,
        fp=0,
        fn=0,
        specificity=1.0,
        fpr=0.0,
        fnr=0.0,
        included_examples=1,
        is_primary=True,
    )
    result = EvaluationResult(
        evaluation_run_id=run.id,
        question_id="q1",
        question="What is carbon?",
        reference_answer="An element",
        generated_answer="Carbon is an element.",
        actual_label="RELIABLE",
        predicted_label="RELIABLE",
        hallucination_score=0.05,
        category="general",
        outcome="TP",
        ground_truth_source="reference_match",
        metaqa_score=0.05,
        position=0,
    )
    db_session.add(run)
    db_session.add(metric)
    db_session.add(result)
    db_session.commit()
    return run.id


@pytest.fixture()
def seeded_run(db_session) -> str:
    """Seed a single Run record."""
    from app.database.models import Run

    run = Run(
        id="run-test-001",
        question="Is carbon an element?",
        generator_model="gemma",
        base_answer="Yes, carbon is a chemical element.",
        threshold=0.5,
        hallucination_score=0.05,
        classification="Reliable",
        status="completed",
    )
    db_session.add(run)
    db_session.commit()
    return run.id


# ─── Tests 13-16: Evaluation & Run API Blinding Protection ────────────────────


class TestEvaluationBlinding:
    def test_reviewer1_blocked_from_evaluation_detail(self, client, seeded_evaluation):
        resp = client.get(f"/api/evaluations/{seeded_evaluation}", headers=R1_HEADERS)
        assert resp.status_code == 403
        assert "Reviewer identities are restricted" in resp.json()["detail"]

    def test_reviewer2_blocked_from_evaluation_detail(self, client, seeded_evaluation):
        resp = client.get(f"/api/evaluations/{seeded_evaluation}", headers=R2_HEADERS)
        assert resp.status_code == 403
        assert "Reviewer identities are restricted" in resp.json()["detail"]

    def test_reviewer_blocked_from_evaluation_export(self, client, seeded_evaluation):
        resp1 = client.get(f"/api/evaluations/{seeded_evaluation}/export", headers=R1_HEADERS)
        assert resp1.status_code == 403
        resp2 = client.get(f"/api/evaluations/{seeded_evaluation}/export", headers=R2_HEADERS)
        assert resp2.status_code == 403

    def test_reviewer_blocked_from_sweep_export(self, client, seeded_evaluation):
        resp1 = client.get(f"/api/evaluations/{seeded_evaluation}/export/sweep", headers=R1_HEADERS)
        assert resp1.status_code == 403
        resp2 = client.get(f"/api/evaluations/{seeded_evaluation}/export/sweep", headers=R2_HEADERS)
        assert resp2.status_code == 403

    def test_reviewer_blocked_from_runs_endpoints(self, client, seeded_run):
        resp_list = client.get("/api/runs", headers=R1_HEADERS)
        assert resp_list.status_code == 403
        resp_detail = client.get(f"/api/runs/{seeded_run}", headers=R2_HEADERS)
        assert resp_detail.status_code == 403

    def test_reviewer_blocked_from_evaluations_list(self, client, seeded_evaluation):
        resp1 = client.get("/api/evaluations", headers=R1_HEADERS)
        assert resp1.status_code == 403
        resp2 = client.get("/api/evaluations", headers=R2_HEADERS)
        assert resp2.status_code == 403

    def test_anonymous_gets_aggregate_only_when_tokens_configured(self, client, seeded_evaluation):
        """Anonymous callers retain aggregate metric visibility, but question results are suppressed."""
        resp = client.get(f"/api/evaluations/{seeded_evaluation}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"]["accuracy"] == 1.0
        assert data["confusion_matrix"]["tp"] == 1
        assert len(data["category_metrics"]) >= 1
        assert data["results"] == []  # Question-level scores suppressed!

    def test_anonymous_export_unauthorized_when_tokens_configured(self, client, seeded_evaluation):
        """Evaluation CSV exports require adjudicator authorization when reviewer tokens are set."""
        resp = client.get(f"/api/evaluations/{seeded_evaluation}/export")
        assert resp.status_code == 401
        assert "Adjudicator authorization required" in resp.json()["detail"]

    def test_anonymous_can_export_sweep(self, client, seeded_evaluation):
        """Sweep exports contain only aggregate thresholds and are publicly accessible."""
        resp = client.get(f"/api/evaluations/{seeded_evaluation}/export/sweep")
        assert resp.status_code == 200
        assert "threshold" in resp.text

    def test_adjudicator_gets_full_evaluation_detail(self, client, seeded_evaluation):
        resp = client.get(f"/api/evaluations/{seeded_evaluation}", headers=ADJ_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["question_id"] == "q1"

    def test_adjudicator_can_export_evaluation(self, client, seeded_evaluation):
        resp = client.get(f"/api/evaluations/{seeded_evaluation}/export", headers=ADJ_HEADERS)
        assert resp.status_code == 200
        assert "q1" in resp.text


# ─── Tests 17-21: Token Validation & Fail-Closed Behavior ─────────────────────


class TestTokenValidation:
    def test_duplicate_tokens_rejected(self, monkeypatch):
        from app.config import Settings
        monkeypatch.setenv("REVIEWER1_TOKEN", "shared-token-value-1234567890")
        monkeypatch.setenv("REVIEWER2_TOKEN", "shared-token-value-1234567890")
        monkeypatch.setenv("ADJUDICATOR_TOKEN", "distinct-token-value-12345678")
        with pytest.raises(ValueError, match="Duplicate reviewer tokens detected"):
            Settings()

    def test_short_token_rejected(self, monkeypatch):
        from app.config import Settings
        monkeypatch.setenv("REVIEWER1_TOKEN", "too-short")
        monkeypatch.setenv("REVIEWER2_TOKEN", "valid-length-token-1234567890")
        monkeypatch.setenv("ADJUDICATOR_TOKEN", "another-valid-token-123456789")
        with pytest.raises(ValueError, match="too weak"):
            Settings()

    def test_placeholder_token_rejected(self, monkeypatch):
        from app.config import Settings
        monkeypatch.setenv("REVIEWER1_TOKEN", "replace-with-reviewer1-secret-token")
        monkeypatch.setenv("REVIEWER2_TOKEN", "valid-length-token-1234567890")
        monkeypatch.setenv("ADJUDICATOR_TOKEN", "another-valid-token-123456789")
        with pytest.raises(ValueError, match="must not be a placeholder"):
            Settings()

    def test_incomplete_token_configuration_rejected(self, monkeypatch):
        from app.config import Settings
        monkeypatch.setenv("REVIEWER1_TOKEN", "valid-length-token-1234567890")
        monkeypatch.setenv("REVIEWER2_TOKEN", "")
        monkeypatch.setenv("ADJUDICATOR_TOKEN", "")
        with pytest.raises(ValueError, match="Incomplete reviewer token configuration"):
            Settings()

    def test_production_requires_all_tokens(self, monkeypatch):
        from app.config import Settings
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("REVIEWER1_TOKEN", "")
        monkeypatch.setenv("REVIEWER2_TOKEN", "")
        monkeypatch.setenv("ADJUDICATOR_TOKEN", "")
        with pytest.raises(ValueError, match="Production environment requires REVIEWER1_TOKEN"):
            Settings()


# ─── Tests 22-25: Immutable Annotation Audit Logs ─────────────────────────────


class TestAnnotationAuditLog:
    def test_initial_submission_creates_audit_log(self, client, seeded_annotation, db_session):
        from sqlalchemy import select
        from app.database.models import AnnotationAuditLog

        resp = client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "HALLUCINATED", "notes": "Initial assessment"},
        )
        assert resp.status_code == 200

        logs = db_session.scalars(
            select(AnnotationAuditLog).where(AnnotationAuditLog.annotation_id == seeded_annotation)
        ).all()
        assert len(logs) == 1
        assert logs[0].action == "initial_submission"
        assert logs[0].actor_role == "reviewer1"
        assert logs[0].previous_label is None
        assert logs[0].new_label == "HALLUCINATED"
        assert logs[0].new_notes == "Initial assessment"

    def test_label_correction_creates_audit_log(self, client, seeded_annotation, db_session):
        from sqlalchemy import select
        from app.database.models import AnnotationAuditLog

        # Step 1: initial
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "HALLUCINATED", "notes": "First guess"},
        )
        # Step 2: correction
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "RELIABLE", "notes": "Corrected verdict"},
        )

        logs = db_session.scalars(
            select(AnnotationAuditLog)
            .where(AnnotationAuditLog.annotation_id == seeded_annotation)
            .order_by(AnnotationAuditLog.created_at)
        ).all()
        assert len(logs) == 2
        assert logs[1].action == "label_correction"
        assert logs[1].actor_role == "reviewer1"
        assert logs[1].previous_label == "HALLUCINATED"
        assert logs[1].new_label == "RELIABLE"
        assert logs[1].new_notes == "Corrected verdict"

    def test_notes_correction_preserves_history(self, client, seeded_annotation, db_session):
        from sqlalchemy import select
        from app.database.models import AnnotationAuditLog

        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "RELIABLE", "notes": "First notes"},
        )
        client.post(
            f"/api/review/tasks/{seeded_annotation}/submit",
            headers=R1_HEADERS,
            json={"label": "RELIABLE", "notes": "Second notes"},
        )

        logs = db_session.scalars(
            select(AnnotationAuditLog)
            .where(AnnotationAuditLog.annotation_id == seeded_annotation)
            .order_by(AnnotationAuditLog.created_at)
        ).all()
        assert len(logs) == 2
        assert logs[0].action == "initial_submission"
        assert logs[1].action == "notes_correction"
        assert logs[1].previous_notes == "First notes"
        assert logs[1].new_notes == "Second notes"

    def test_adjudication_creates_audit_log(self, client, both_reviewed_annotation, db_session):
        from sqlalchemy import select
        from app.database.models import AnnotationAuditLog

        resp = client.post(
            f"/api/review/adjudicate/{both_reviewed_annotation}",
            headers=ADJ_HEADERS,
            json={"label": "HALLUCINATED", "notes": "Adjudicated as hallucinated", "evidence": "Scientific evidence"},
        )
        assert resp.status_code == 200

        logs = db_session.scalars(
            select(AnnotationAuditLog)
            .where(AnnotationAuditLog.annotation_id == both_reviewed_annotation)
        ).all()
        assert len(logs) == 1
        assert logs[0].action == "initial_adjudication"
        assert logs[0].actor_role == "adjudicator"
        assert logs[0].previous_label is None
        assert logs[0].new_label == "HALLUCINATED"
        assert logs[0].new_notes == "Adjudicated as hallucinated"
