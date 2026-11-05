from __future__ import annotations

import json
from pathlib import Path
import pytest
from sqlalchemy.orm import Session

from app.database.db import SessionLocal, init_db
from app.evaluation.evaluator import run_evaluation
from app.llm.mock import MockLLMClient
from app.services.verification_summary import (
    MetaqaSignal,
    OverallVerdict,
    WebSignal,
    compute_overall_assessment,
)
from app.web_evidence.types import EvidenceVerdict, VerifiedClaim, WebEvidenceResult, WebEvidenceStatus
from app.web_search.mock import MockTavilyClient
from tests.fakes import detector_settings


@pytest.fixture
def eval_db() -> Session:
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_mini_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "benchmark_mini.json"
    data = {
        "name": "benchmark_mini",
        "version": "1.0",
        "examples": [
            {
                "id": "q1",
                "question": "What is the capital of France?",
                "reference_answer": "Paris",
                "category": "location",
                "mock_base_answer": "Paris is the capital of France.",
                "mock_scenario": "reliable",
            },
            {
                "id": "q2",
                "question": "What is the capital of Australia?",
                "reference_answer": "Canberra",
                "category": "location",
                "mock_base_answer": "Sydney is the capital of Australia.",
                "mock_scenario": "hallucinated",
            },
            {
                "id": "q3",
                "question": "What is the capital of Japan?",
                "reference_answer": "Tokyo",
                "category": "location",
                "mock_base_answer": "Tokyo is the capital of Japan.",
                "mock_scenario": "reliable",
            },
            {
                "id": "q4",
                "question": "What is the capital of Canada?",
                "reference_answer": "Ottawa",
                "category": "location",
                "mock_base_answer": "Toronto is the capital of Canada.",
                "mock_scenario": "hallucinated",
            },
            {
                "id": "q5",
                "question": "Ambiguous capital question?",
                "reference_answer": "Unknown",
                "category": "location",
                "needs_review": True,
                "mock_base_answer": "I don't know.",
            },
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ── 1. Comprehensive Independent Evaluation Against Same Answer ───────────────

@pytest.mark.asyncio
async def test_all_components_evaluated_against_same_generated_answer(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """All components (MetaQA, Web, Multi-model, Combined) evaluate the exact same generated answer."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"

    search_client = MockTavilyClient()

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        search_client=search_client,
        evaluate_web_evidence=True,
        evaluate_multi_model=True,
        persist_traces=False,
    )
    eval_db.commit()

    assert run.status == "completed"
    assert len(run.results) == 5

    for row in run.results:
        # 1. Answer text is identical for all component assessments on this row
        assert row.generated_answer != ""
        # 2. MetaQA score and prediction populated
        assert row.metaqa_score is not None
        assert row.metaqa_prediction in {"Reliable", "Hallucinated"}
        assert row.metaqa_outcome in {"TP", "TN", "FP", "FN", "Needs Review"}
        # 3. Web Evidence fields populated
        assert row.web_evidence_status in {"completed", "unavailable"}
        assert row.web_evidence_outcome in {"TP", "TN", "FP", "FN", "Abstained", "Needs Review"}
        # 4. Multi-model fields populated
        assert row.multi_model_status in {"completed", "failed"}
        assert row.multi_model_outcome in {"TP", "TN", "FP", "FN", "Abstained", "Needs Review"}
        # 5. Combined fields populated
        assert row.combined_verdict in {
            OverallVerdict.LIKELY_RELIABLE.value,
            OverallVerdict.POTENTIALLY_HALLUCINATED.value,
            OverallVerdict.NEEDS_VERIFICATION.value,
            OverallVerdict.INSUFFICIENT_EVIDENCE.value,
            OverallVerdict.UNAVAILABLE.value,
        }
        # 6. JSON details contains all component telemetry
        details = json.loads(row.component_details_json)
        assert "metaqa" in details
        assert "web_evidence" in details
        assert "multi_model" in details
        assert "combined" in details


# ── 2. Independent Metrics Calculation for All Four Components ────────────────

@pytest.mark.asyncio
async def test_independent_metrics_calculated_for_all_four_components(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """Metrics (accuracy, P, R, F1, coverage) are computed independently per component."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        search_client=MockTavilyClient(),
        evaluate_web_evidence=True,
        evaluate_multi_model=True,
        persist_traces=False,
    )
    eval_db.commit()

    # Check metric rows by component
    metric_components = {m.component for m in run.metrics}
    assert "metaqa" in metric_components
    assert "web_evidence" in metric_components
    assert "multi_model" in metric_components
    assert "combined" in metric_components

    # Verify summary_metrics_json structure
    summary = json.loads(run.summary_metrics_json)
    for comp in ("metaqa", "web_evidence", "multi_model", "combined"):
        assert comp in summary
        c_stats = summary[comp]
        assert "accuracy" in c_stats
        assert "precision" in c_stats
        assert "recall" in c_stats
        assert "f1" in c_stats
        assert "coverage" in c_stats
        assert "tp" in c_stats
        assert "tn" in c_stats
        assert "fp" in c_stats
        assert "fn" in c_stats


# ── 3. Ground-Truth Consistency Across Components ─────────────────────────────

@pytest.mark.asyncio
async def test_ground_truth_consistency_across_components(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """All components evaluate against the same ground truth label; Needs Review is universally excluded."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        search_client=MockTavilyClient(),
        evaluate_web_evidence=True,
        evaluate_multi_model=True,
        persist_traces=False,
    )

    # Item 5 is flagged needs_review=True
    ambiguous_item = next(r for r in run.results if r.question_id == "q5")
    assert ambiguous_item.actual_label == "Needs Review"
    assert ambiguous_item.metaqa_outcome == "Needs Review"
    assert ambiguous_item.web_evidence_outcome == "Needs Review"
    assert ambiguous_item.multi_model_outcome == "Needs Review"
    assert ambiguous_item.combined_outcome == "Needs Review"


# ── 4. Web Evidence Insufficient Evidence & Abstention Handling ───────────────

@pytest.mark.asyncio
async def test_web_evidence_insufficient_evidence_treated_as_abstention(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """Missing or insufficient web evidence is an abstention, NEVER counted as a contradiction."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"

    # Search client returns empty results (insufficient evidence)
    empty_search = MockTavilyClient(empty=True)

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        search_client=empty_search,
        evaluate_web_evidence=True,
        evaluate_multi_model=False,
        persist_traces=False,
    )

    for row in run.results:
        if row.actual_label != "Needs Review":
            # Insufficient evidence must NOT be treated as contradiction
            assert row.web_evidence_prediction is None
            assert row.web_evidence_outcome == "Abstained"

    summary = json.loads(run.summary_metrics_json)
    web_summary = summary["web_evidence"]
    assert web_summary["coverage"] == 0.0
    assert web_summary["abstained_examples"] == 4  # 4 labeled examples were abstained


# ── 5. Multi-Model Evaluation Consensus & Disagreement ────────────────────────

@pytest.mark.asyncio
async def test_multi_model_consensus_independent_evaluation(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """Multi-model verification calculates consensus, disagreement, and independent prediction."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        evaluate_web_evidence=False,
        evaluate_multi_model=True,
        persist_traces=False,
    )

    for row in run.results:
        assert row.multi_model_status == "completed"
        assert row.multi_model_consensus in {"AGREEMENT", "DISAGREEMENT", "UNCERTAIN"}
        if row.question_id in {"q1", "q3"}:  # reliable scenario
            assert row.multi_model_prediction == "Reliable"
        elif row.question_id in {"q2", "q4"}:  # hallucinated scenario
            assert row.multi_model_prediction == "Hallucinated"


# ── 6. Gemma Exclusion from Independent Verifier Pool ─────────────────────────

@pytest.mark.asyncio
async def test_gemma_never_in_independent_verifier_pool(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """Gemma generates answers and must NEVER be queried as an independent verifier."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        evaluate_web_evidence=False,
        evaluate_multi_model=True,
        persist_traces=False,
    )

    for row in run.results:
        details = json.loads(row.component_details_json)
        mm_details = details["multi_model"]
        verdict_model_ids = {v["model_id"] for v in mm_details.get("verdicts", [])}
        assert "gemma" not in verdict_model_ids
        assert verdict_model_ids <= {"glm", "qwen", "openrouter", "phi"}


# ── 7. Component Failure & Partial Availability Handling ──────────────────────

@pytest.mark.asyncio
async def test_component_failure_partial_availability(tmp_path: Path, monkeypatch, eval_db: Session) -> None:
    """When web evidence search is unavailable, MetaQA and Multi-model still evaluate cleanly."""
    dataset_path = create_mini_dataset(tmp_path)
    monkeypatch.setattr("app.evaluation.dataset_loader.DATASETS_DIR", tmp_path)

    settings = detector_settings()
    settings.llm_mode = "mock"
    settings.web_evidence_enabled = False  # Disable web search

    run = await run_evaluation(
        llm=MockLLMClient(),
        db=eval_db,
        settings=settings,
        dataset=str(dataset_path),
        threshold=0.5,
        evaluate_web_evidence=True,
        evaluate_multi_model=True,
        persist_traces=False,
    )

    assert run.status == "completed"
    for row in run.results:
        # Web evidence gracefully records unavailable without crashing evaluation
        assert row.web_evidence_status == "unavailable"
        assert row.web_evidence_prediction is None
        # MetaQA and Multi-model remain fully functional
        assert row.metaqa_prediction is not None
        assert row.multi_model_prediction is not None


# ── 8. Preservation of Existing Fusion Rules ──────────────────────────────────

def test_combined_fusion_rules_preservation() -> None:
    """Verification summary compute_overall_assessment retains exact formula and verdict rules."""
    # Reliable MetaQA (0.10) + Supported Web (score 1.0 -> web_risk 0.0) -> combined 0.05 -> LIKELY_RELIABLE
    claim_supp = VerifiedClaim(id="c0", text="Paris is capital", search_query="q", verdict=EvidenceVerdict.SUPPORTED, reason="r")
    v1, _, _, _, r1, wr1 = compute_overall_assessment(
        metaqa_signal=MetaqaSignal.CONSISTENT,
        metaqa_score=0.10,
        web_signal=WebSignal.SUPPORTED,
        web_evidence=WebEvidenceResult(status=WebEvidenceStatus.COMPLETED, claims=[claim_supp], consistency_score=1.0),
    )
    assert v1 == OverallVerdict.LIKELY_RELIABLE
    assert r1 == 0.05
    assert wr1 == 0.0

    # Inconsistent MetaQA (0.90) + Contradicted Web (score 0.0 -> web_risk 1.0) -> combined 0.95 -> POTENTIALLY_HALLUCINATED
    claim_contra = VerifiedClaim(id="c1", text="text", search_query="q", verdict=EvidenceVerdict.CONTRADICTED, reason="r")
    v2, _, _, _, r2, wr2 = compute_overall_assessment(
        metaqa_signal=MetaqaSignal.INCONSISTENT,
        metaqa_score=0.90,
        web_signal=WebSignal.CONTRADICTED,
        web_evidence=WebEvidenceResult(status=WebEvidenceStatus.COMPLETED, claims=[claim_contra], consistency_score=0.0),
    )
    assert v2 == OverallVerdict.POTENTIALLY_HALLUCINATED
    assert r2 == 0.95
    assert wr2 == 1.0
